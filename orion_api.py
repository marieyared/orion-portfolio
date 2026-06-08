import json
import math
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import requests
import yfinance as yf


# Hosting: PaaS providers (Render, Railway, Fly, Heroku) inject PORT and expect
# the server to bind 0.0.0.0. Locally, default to 127.0.0.1:8787.
_IN_CLOUD = bool(os.getenv("PORT"))
HOST = os.getenv("ORION_API_HOST", "0.0.0.0" if _IN_CLOUD else "127.0.0.1")
PORT = int(os.getenv("PORT") or os.getenv("ORION_API_PORT") or "8787")

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_QS_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
FRANKFURTER_URL = "https://api.frankfurter.dev/v1"

# Financial Modeling Prep is used as a fallback for sector/industry/country
# whenever Yahoo's quoteSummary endpoint is rate-limited (which is most of
# the time on Render's shared IPs). Free tier is 250 req/day; with the 24h
# PROFILE_CACHE that's plenty for a personal portfolio. No key set → fallback
# is silently skipped.
FMP_API_KEY = os.getenv("FMP_API_KEY", "").strip()
# /api/v3/profile was retired 2025-08-31. New endpoint takes `symbol` as a
# query param, not a path segment.
FMP_PROFILE_URL = "https://financialmodelingprep.com/stable/profile"

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

# OpenFIGI exchCode → Yahoo Finance ticker suffix (None = US, no suffix).
FIGI_EXCH_TO_YAHOO = {
    "LN": ".L",   "NA": ".AS",  "GR": ".DE",  "GY": ".DE",  "FP": ".PA",
    "IM": ".MI",  "SM": ".MC",  "SW": ".SW",  "VX": ".SW",  "AU": ".AX",
    "SS": ".ST",  "HE": ".HE",  "CN": ".CO",  "BB": ".BR",  "PL": ".LS",
    "ID": ".IR",  "AV": ".VI",  "PW": ".WA",  "CT": ".TO",  "JT": ".T",
    "JP": ".T",   "HK": ".HK",  "SP": ".SI",  "BZ": ".SA",  "MM": ".MX",
    "SJ": ".JO",  "NZ": ".NZ",  "TT": ".TW",  "KS": ".KS",  "TI": ".IS",
}
US_EXCHANGES = {"US", "UN", "UQ", "UR", "UV", "UW", "UA", "UD", "UF", "UO", "UP", "UV"}

# Preferred Yahoo suffix per ISIN country code. Used to rank listings so a
# German ISIN doesn't end up trying its illiquid Mexican secondary listing.
# Empty string means "bare ticker" (US-style, no suffix).
ISIN_COUNTRY_PREF = {
    "US": "", "CA": ".TO", "GB": ".L",  "IE": ".L",  "DE": ".DE", "FR": ".PA",
    "CH": ".SW","NL": ".AS","IT": ".MI","ES": ".MC","SE": ".ST","FI": ".HE",
    "DK": ".CO","NO": ".OL","BE": ".BR","PT": ".LS","AT": ".VI","PL": ".WA",
    "LU": ".DE","JP": ".T", "HK": ".HK","AU": ".AX","BR": ".SA","ZA": ".JO",
    "TW": ".TW","KR": ".KS","IS": ".IS","NZ": ".NZ",
}

# Caches
ISIN_CACHE: dict[str, dict] = {}
QUOTE_CACHE: dict[str, tuple[float, dict]] = {}  # (timestamp, payload)
PROFILE_CACHE: dict[str, dict] = {}
FX_CACHE: dict[str, tuple[float, dict]] = {}  # (timestamp, payload)
# ETF sector weights are cached *separately* from the price quote: Yahoo's
# funds_data endpoint rate-limits Render's shared IPs aggressively, so we
# can't afford to discard a successful fetch every 60s. Sector mixes also
# drift on a timescale of weeks, not minutes — a day is fine. Empty / failed
# fetches do NOT poison this cache: only positive results land here.
ETF_SECTOR_CACHE: dict[str, tuple[float, list]] = {}  # symbol -> (ts, weights)
# ETF single-name constituents (top ~10 holdings + weights), cached and
# fallen back on exactly like sector weights: same rate-limit pressure, same
# weeks-not-minutes drift. Powers the hidden-overlap risk lens (true
# single-name concentration across funds that look diversified by ticker).
ETF_HOLDINGS_CACHE: dict[str, tuple[float, list]] = {}  # symbol -> (ts, holdings)
LIVE_TTL_SECONDS = 60       # current-price freshness
FX_TTL_SECONDS = 3600       # ECB rates publish once per business day
ETF_SECTOR_TTL = 24 * 3600  # ETF sector weights: cache full day
ETF_HOLDINGS_TTL = 24 * 3600  # ETF top holdings: cache full day
API_RATE_LIMIT_REQUESTS = int(os.getenv("API_RATE_LIMIT_REQUESTS", "120"))
API_RATE_LIMIT_WINDOW = int(os.getenv("API_RATE_LIMIT_WINDOW_SECONDS", "60"))


# ── Upstream health monitor ───────────────────────────────────────────────
# In-memory rolling counters per upstream. Counts only ACTUAL upstream
# calls — cache hits don't count. Drives /health and the alert engine.
# ThreadingHTTPServer can hit these from many threads at once; RLock so
# health_snapshot() can call window_stats()/fmp_quota() under the same lock.
class UpstreamMonitor:
    UPSTREAMS = ("yahoo_chart", "yahoo_profile", "openfigi", "fmp", "frankfurter")

    def __init__(self):
        self._lock = threading.RLock()
        # deque keeps the last 100 events per upstream — cheap to scan for
        # window stats; auto-evicts old entries without housekeeping.
        self._events = {u: deque(maxlen=100) for u in self.UPSTREAMS}  # [(ts, outcome)]
        self._stats = {u: {"consecutive_failures": 0,
                           "last_success_ts": 0.0, "last_failure_ts": 0.0}
                       for u in self.UPSTREAMS}
        self._fmp_day = None   # YYYY-MM-DD (UTC); rolls over silently
        self._fmp_calls = 0
        # alert_key -> last fired ts, used by Part C's debounce.
        self._alerts: dict[str, float] = {}

    def record(self, upstream: str, outcome: str) -> None:
        """outcome ∈ {'success','failure','empty'}. Unknown upstream is a no-op."""
        if upstream not in self._events:
            return
        now = time.time()
        with self._lock:
            self._events[upstream].append((now, outcome))
            st = self._stats[upstream]
            if outcome == "success":
                st["consecutive_failures"] = 0
                st["last_success_ts"] = now
            elif outcome == "failure":
                st["consecutive_failures"] += 1
                st["last_failure_ts"] = now
            else:  # "empty" — rate-limit proxy, has its own alert path via
                   # empty_rate. Does NOT trip consecutive_failures (which
                   # escalates to "down") because a rate-limited Yahoo is
                   # degraded, not unreachable.
                st["last_failure_ts"] = now
            if upstream == "fmp":
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if self._fmp_day != today:
                    self._fmp_day = today
                    self._fmp_calls = 0
                self._fmp_calls += 1

    def window_stats(self, upstream: str, window: int = 900) -> dict:
        with self._lock:
            now = time.time()
            s = f = e = 0
            for ts, oc in self._events[upstream]:
                if now - ts > window:
                    continue
                if oc == "success":   s += 1
                elif oc == "failure": f += 1
                elif oc == "empty":   e += 1
            total = s + f + e
            return {"window_count": total,
                    "successes": s, "failures": f, "empties": e,
                    "failure_rate": (f / total) if total else 0.0,
                    "empty_rate":   (e / total) if total else 0.0}

    def fmp_quota(self) -> dict:
        with self._lock:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if self._fmp_day != today:
                # Roll the day silently on read so a quiet day reports 0/250.
                self._fmp_day = today
                self._fmp_calls = 0
            return {"today": today, "calls": self._fmp_calls,
                    "limit": 250, "remaining": max(0, 250 - self._fmp_calls)}

    def health_snapshot(self) -> dict:
        """Read-only snapshot for /health. No upstream calls."""
        # Thresholds read at snapshot time so an env change doesn't require
        # a restart to take effect for the status classification.
        cons_thr  = int(os.getenv("ALERT_CONSECUTIVE_FAILURES",     "5"))
        fail_thr  = float(os.getenv("ALERT_FAILURE_RATE_THRESHOLD", "0.5"))
        empty_thr = float(os.getenv("ALERT_EMPTY_RATE_THRESHOLD",   "0.6"))
        with self._lock:
            upstreams = {}
            overall = "ok"
            for u in self.UPSTREAMS:
                w = self.window_stats(u)
                st = self._stats[u]
                cons = st["consecutive_failures"]
                if cons >= cons_thr:
                    status = "down"
                elif w["window_count"] > 0 and (
                    w["failure_rate"] > fail_thr or w["empty_rate"] > empty_thr
                ):
                    status = "degraded"
                else:
                    status = "ok"
                if   status == "down":     overall = "down"
                elif status == "degraded" and overall != "down": overall = "degraded"
                upstreams[u] = {
                    "status": status,
                    "window_count": w["window_count"],
                    "failure_rate": round(w["failure_rate"], 3),
                    "empty_rate":   round(w["empty_rate"], 3),
                    "consecutive_failures": cons,
                    "last_success_ts": st["last_success_ts"],
                    "last_failure_ts": st["last_failure_ts"],
                }
            return {"overall": overall, "upstreams": upstreams,
                    "fmp_quota": self.fmp_quota()}

    def should_alert(self, key: str, cooldown: int) -> bool:
        """Returns True the first time per cooldown window, False inside it.
        Mutates last-fired so the second call inside the window returns False."""
        with self._lock:
            now = time.time()
            last = self._alerts.get(key, 0.0)
            if now - last < cooldown:
                return False
            self._alerts[key] = now
            return True


monitor = UpstreamMonitor()


class RequestRateLimiter:
    """Small in-memory per-client limiter for the expensive public API routes."""

    def __init__(self, limit: int, window: int):
        self.limit = max(1, limit)
        self.window = max(1, window)
        self._lock = threading.Lock()
        self._requests: dict[str, deque] = {}

    def allow(self, client: str) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            events = self._requests.setdefault(client, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(events[0] + self.window - now) + 1)
                return False, retry_after
            events.append(now)
            # Prevent abandoned client entries from accumulating forever.
            if len(self._requests) > 5000:
                self._requests = {k: v for k, v in self._requests.items() if v and v[-1] > cutoff}
            return True, 0


rate_limiter = RequestRateLimiter(API_RATE_LIMIT_REQUESTS, API_RATE_LIMIT_WINDOW)


YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Accept": "application/json,text/javascript,*/*;q=0.01",
}


# ── ISIN helpers ───────────────────────────────────────────────────────────

def normalize_isin(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (raw or "")).upper()


def is_valid_isin(isin: str) -> bool:
    if not ISIN_RE.match(isin):
        return False
    expanded = []
    for ch in isin:
        if ch.isdigit():
            expanded.append(ch)
        else:
            expanded.append(str(ord(ch) - 55))
    digits = "".join(expanded)
    total = 0
    double = False
    for ch in reversed(digits):
        value = int(ch)
        if double:
            value *= 2
            if value > 9:
                value -= 9
        total += value
        double = not double
    return total % 10 == 0


def openfigi_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("OPENFIGI_API_KEY", "").strip()
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key
    return headers


def lookup_isin(isin: str) -> dict | None:
    if isin in ISIN_CACHE:
        return ISIN_CACHE[isin]
    try:
        response = requests.post(
            OPENFIGI_URL,
            headers=openfigi_headers(),
            json=[{"idType": "ID_ISIN", "idValue": isin}],
            timeout=8,
        )
        response.raise_for_status()
    except requests.RequestException:
        monitor.record("openfigi", "failure")
        raise
    try:
        payload = response.json()
    except ValueError as exc:
        monitor.record("openfigi", "failure")
        raise requests.RequestException("OpenFIGI returned invalid JSON.") from exc
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        monitor.record("openfigi", "failure")
        raise requests.RequestException("OpenFIGI returned an invalid response.")
    data = payload[0].get("data")
    if not data:
        monitor.record("openfigi", "empty")
        return None
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        monitor.record("openfigi", "failure")
        raise requests.RequestException("OpenFIGI returned invalid instrument data.")
    # Dedupe on (ticker, exchange) so dual-listed names like SAP — quoted as
    # "SAP" on both Swiss (SW) and Xetra (GR) — keep both entries. The earlier
    # ticker-only dedup silently dropped the domestic listing whenever an
    # alternate venue happened to come first in OpenFIGI's response.
    seen = set()
    listings = []
    for item in data:
        ticker = item.get("ticker", "")
        exch = item.get("exchCode", "")
        if not ticker:
            continue
        key = (ticker, exch)
        if key not in seen:
            seen.add(key)
            listings.append({"ticker": ticker, "exch": exch})
    first = data[0]
    result = {
        "isin": isin,
        "name": first.get("name", isin),
        "type": first.get("securityType") or first.get("securityType2") or "",
        "exchange": first.get("exchCode", ""),
        "ticker": first.get("ticker", ""),
        "market_sector": first.get("marketSector", ""),
        "figi": first.get("figi", ""),
        "composite_figi": first.get("compositeFIGI", ""),
        "share_class_figi": first.get("shareClassFIGI", ""),
        "listings": listings,
    }
    ISIN_CACHE[isin] = result
    monitor.record("openfigi", "success")
    return result


# ── Yahoo helpers ──────────────────────────────────────────────────────────

def pick_yahoo_symbols(instrument: dict) -> list[str]:
    """Return Yahoo symbols ordered by likely-to-work for this ISIN.

    First builds all candidates from OpenFIGI listings, then sorts so the
    suffix that matches the ISIN's country of issue (e.g. .DE for German
    ISINs) is tried first. Prevents German/UK ISINs from getting routed
    to illiquid Mexican secondary listings.
    """
    out: list[tuple[int, str]] = []  # (priority, symbol)
    seen: set[str] = set()
    # listings is already (ticker, exch)-deduped by lookup_isin, with the
    # primary entry first. No need to prepend or re-filter here.
    listings = list(instrument.get("listings") or [])
    isin = instrument.get("isin") or ""
    country = isin[:2].upper() if len(isin) >= 2 else ""
    preferred_suffix = ISIN_COUNTRY_PREF.get(country)  # None if unknown country
    for l in listings:
        ticker = (l.get("ticker") or "").strip()
        exch = (l.get("exch") or "").strip()
        if not ticker or any(c in ticker for c in " /"):
            continue
        if exch in US_EXCHANGES:
            symbol = ticker
            suffix = ""
        elif exch in FIGI_EXCH_TO_YAHOO:
            suffix = FIGI_EXCH_TO_YAHOO[exch]
            symbol = f"{ticker}{suffix}"
        else:
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        # Lower priority = tried earlier. Exact country match wins.
        if preferred_suffix is not None and suffix == preferred_suffix:
            prio = 0
        elif suffix == "":
            # US/bare ticker is a strong fallback for any ISIN (ADRs etc.)
            prio = 1
        else:
            prio = 2
        out.append((prio, symbol))
    out.sort(key=lambda x: x[0])
    return [sym for _, sym in out]


def fetch_yahoo_chart(symbol: str, target_date: str | None = None) -> dict | None:
    """Use yfinance (handles cookie/crumb) to fetch current or historical price."""
    # Bad date format is user input, not an upstream call — skip monitoring.
    if target_date:
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            return None
    try:
        ticker = yf.Ticker(symbol)
        if target_date:
            dt = datetime.strptime(target_date, "%Y-%m-%d")
            start = (dt - timedelta(days=10)).strftime("%Y-%m-%d")
            end   = (dt + timedelta(days=10)).strftime("%Y-%m-%d")
            hist = ticker.history(start=start, end=end, auto_adjust=False)
            if hist is None or hist.empty:
                monitor.record("yahoo_chart", "empty")
                return None
            # Pick the row closest to the target date.
            target_ts = dt.timestamp()
            best_i, best_diff = -1, 1e18
            for i in range(len(hist)):
                ts = hist.index[i].to_pydatetime().timestamp()
                d = abs(ts - target_ts)
                if d < best_diff:
                    best_diff, best_i = d, i
            if best_i < 0:
                monitor.record("yahoo_chart", "empty")
                return None
            row = hist.iloc[best_i]
            price = float(row["Close"])
            if not math.isfinite(price):
                monitor.record("yahoo_chart", "empty")
                return None
            info = ticker.fast_info
            monitor.record("yahoo_chart", "success")
            return {
                "price": price,
                "currency": getattr(info, "currency", "USD") or "USD",
                "symbol": symbol,
                "as_of": hist.index[best_i].strftime("%Y-%m-%d"),
                "exchange": getattr(info, "exchange", "") or "",
            }
        # Live/current quote: use the latest actual market bar so "as_of"
        # reflects when the price traded, including on weekends and holidays.
        info = ticker.fast_info
        hist = ticker.history(period="5d", interval="1m", auto_adjust=False, prepost=False)
        if hist is not None and not hist.empty:
            price = float(hist.iloc[-1]["Close"])
            market_time = hist.index[-1].to_pydatetime()
            if market_time.tzinfo is None:
                market_time = market_time.replace(tzinfo=timezone.utc)
            as_of = market_time.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        else:
            # Some thinly traded funds expose a current price but no intraday
            # bars. Return the price without inventing a market timestamp.
            price = float(getattr(info, "last_price", float("nan")))
            as_of = "Market timestamp unavailable"
        if not math.isfinite(price):
            monitor.record("yahoo_chart", "empty")
            return None
        monitor.record("yahoo_chart", "success")
        return {
            "price": float(price),
            "currency": getattr(info, "currency", "USD") or "USD",
            "symbol": symbol,
            "as_of": as_of,
            "exchange": getattr(info, "exchange", "") or "",
        }
    except Exception:
        monitor.record("yahoo_chart", "failure")
        return None


def _coerce_sector_weights(raw) -> list:
    """Normalize yfinance sectorWeightings into a list of {sector_key: weight} dicts."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        # Some versions return a flat dict {sector_key: weight}
        return [{k: v} for k, v in raw.items()]
    return []


def _coerce_top_holdings(raw) -> list:
    """Normalize yfinance funds_data.top_holdings into a JSON-safe list of
    {symbol, name, weight} dicts. yfinance returns a DataFrame indexed by the
    holding's symbol with 'Name' and 'Holding Percent' columns; weight is a
    0..1 fraction. Anything unparseable yields []."""
    if raw is None:
        return []
    out = []
    try:
        if hasattr(raw, "iterrows"):  # pandas DataFrame
            for idx, row in raw.iterrows():
                try:
                    pct = row.get("Holding Percent")
                except Exception:
                    pct = None
                if pct is None:
                    continue
                try:
                    weight = float(pct)
                except (TypeError, ValueError):
                    continue
                out.append({
                    "symbol": str(idx),
                    "name": str(row.get("Name", "") or ""),
                    "weight": weight,
                })
        elif isinstance(raw, dict):
            for k, v in raw.items():
                try:
                    out.append({"symbol": str(k), "name": "", "weight": float(v)})
                except (TypeError, ValueError):
                    continue
    except Exception:
        return []
    return out


def fetch_fmp_profile(symbol: str) -> dict | None:
    """Sector / industry / country fallback via Financial Modeling Prep.
    Returns a dict of the fields FMP knows about, or None if no API key is
    configured or the upstream call fails."""
    if not FMP_API_KEY or not symbol:
        return None
    try:
        r = requests.get(
            FMP_PROFILE_URL,
            params={"symbol": symbol, "apikey": FMP_API_KEY},
            timeout=6,
        )
        if not r.ok:
            monitor.record("fmp", "failure")
            return None
        data = r.json()
        if not isinstance(data, list) or not data:
            monitor.record("fmp", "empty")
            return None
        item = data[0] or {}
        monitor.record("fmp", "success")
        return {
            "sector":    item.get("sector") or "",
            "industry":  item.get("industry") or "",
            "country":   item.get("country") or "",
            "long_name": item.get("companyName") or "",
        }
    except (requests.RequestException, ValueError):
        monitor.record("fmp", "failure")
        return None


def fetch_yahoo_profile(symbol: str) -> dict | None:
    if symbol in PROFILE_CACHE:
        return PROFILE_CACHE[symbol]
    try:
        ticker = yf.Ticker(symbol)
        # .info is the rich blob — sector, industry, country, longName, quoteType
        try:
            info = ticker.info or {}
        except Exception:
            info = {}
        quote_type = info.get("quoteType") or info.get("typeDisp") or ""
        sector = info.get("sector") or ""
        industry = info.get("industry") or ""
        country = info.get("country") or ""
        long_name = info.get("longName") or info.get("shortName") or ""
        # Track where the sector/country metadata actually came from so the
        # frontend can surface "this number was filled in by the FMP
        # fallback" instead of showing it as if Yahoo authoritative.
        yahoo_had_meta = bool(sector or country)
        # If Yahoo gave us nothing (rate-limited on Render's IPs), try FMP for
        # the metadata fields. FMP doesn't know about quote_type — we leave
        # that empty; downstream ETF detection falls back to OpenFIGI type +
        # name patterns when quote_type is missing.
        if not sector:
            fmp = fetch_fmp_profile(symbol)
            if fmp:
                sector    = sector    or fmp["sector"]
                industry  = industry  or fmp["industry"]
                country   = country   or fmp["country"]
                long_name = long_name or fmp["long_name"]
        if yahoo_had_meta:
            profile_source = "yahoo"
        elif sector or country:
            profile_source = "fmp"
        else:
            profile_source = "none"
        # ETF look-through if available. The Yahoo funds_data endpoint gets
        # rate-limited from Render's IPs much more often than the chart
        # endpoint, so we keep a 24h cache of *successful* fetches per
        # symbol and fall back to it whenever the live call fails or is
        # blocked. Empty/error results do NOT overwrite a good cache.
        sector_weights = []
        top_holdings = []
        funds_data = None
        try:
            funds_data = getattr(ticker, "funds_data", None)
        except Exception:
            funds_data = None
        if funds_data is not None:
            # Isolate the two look-through calls: top_holdings can raise for a
            # non-fund even when sector_weightings succeeded, so one failing
            # must not discard the other.
            try:
                sector_weights = _coerce_sector_weights(
                    getattr(funds_data, "sector_weightings", None))
            except Exception:
                pass
            try:
                top_holdings = _coerce_top_holdings(
                    getattr(funds_data, "top_holdings", None))
            except Exception:
                pass
        if sector_weights:
            ETF_SECTOR_CACHE[symbol] = (time.time(), sector_weights)
        else:
            cached = ETF_SECTOR_CACHE.get(symbol)
            if cached and time.time() - cached[0] < ETF_SECTOR_TTL:
                sector_weights = cached[1]
        if top_holdings:
            ETF_HOLDINGS_CACHE[symbol] = (time.time(), top_holdings)
        else:
            cached_h = ETF_HOLDINGS_CACHE.get(symbol)
            if cached_h and time.time() - cached_h[0] < ETF_HOLDINGS_TTL:
                top_holdings = cached_h[1]
        profile = {
            "symbol": symbol,
            "long_name": long_name,
            "quote_type": str(quote_type).upper(),
            "sector": sector,
            "industry": industry,
            "country": country,
            "currency": info.get("currency") or "",
            "fund_family": info.get("family") or "",
            "fund_category": info.get("category") or "",
            "sector_weights": sector_weights,
            "top_holdings": top_holdings,
            "profile_source": profile_source,
        }
        # Only cache when we actually got something back from Yahoo. If the
        # info call was rate-limited or otherwise empty (sector + quote_type +
        # long_name + sector_weights all blank), don't poison the cache — let
        # the next request retry. Otherwise the dashboard ends up with an
        # "—" bucket holding every stock that hit a rate-limit on first fetch.
        useful = bool(sector or quote_type or long_name or sector_weights or top_holdings)
        if useful:
            PROFILE_CACHE[symbol] = profile
            monitor.record("yahoo_profile", "success")
        else:
            # Yahoo .info came back empty — strong rate-limit signal on
            # Render's shared IPs. Counts toward empty_rate, not toward
            # consecutive_failures.
            monitor.record("yahoo_profile", "empty")
        return profile
    except Exception:
        monitor.record("yahoo_profile", "failure")
        return None


def build_quote_payload(isin: str, target_date: str | None) -> dict:
    """Combine ISIN → Yahoo price + profile."""
    instrument = lookup_isin(isin)
    if not instrument:
        return {"ok": False, "status": 404, "error": "ISIN not found in OpenFIGI."}
    candidates = pick_yahoo_symbols(instrument)
    if not candidates:
        return {"ok": False, "status": 404, "error": "No tradeable Yahoo symbol mapped for this ISIN.",
                "name": instrument.get("name", ""), "isin": isin}
    cache_key = f"{isin}|{target_date or 'live'}"
    if not target_date and cache_key in QUOTE_CACHE:
        ts, payload = QUOTE_CACHE[cache_key]
        if time.time() - ts < LIVE_TTL_SECONDS:
            # The price-cache entry may have been written during a rate-limit
            # window when sector_weights came back empty. If we now have a
            # better cached sector list for this symbol, overlay it before
            # returning so the dashboard isn't stuck on stale empties.
            sym = payload.get("symbol")
            if sym and not payload.get("sector_weights"):
                cached_sw = ETF_SECTOR_CACHE.get(sym)
                if cached_sw and time.time() - cached_sw[0] < ETF_SECTOR_TTL:
                    payload = {**payload, "sector_weights": cached_sw[1]}
            if sym and not payload.get("top_holdings"):
                cached_h = ETF_HOLDINGS_CACHE.get(sym)
                if cached_h and time.time() - cached_h[0] < ETF_HOLDINGS_TTL:
                    payload = {**payload, "top_holdings": cached_h[1]}
            # Overlay current freshness — the stored entry was tagged "live"
            # at cache time but the caller is reading it later.
            return {**payload,
                    "price_freshness": "cached",
                    "cache_age_seconds": int(time.time() - ts)}
    last_err = "Yahoo did not return a price."
    for symbol in candidates:
        chart = fetch_yahoo_chart(symbol, target_date)
        if not chart:
            last_err = f"Yahoo had no data for {symbol}."
            continue
        profile = fetch_yahoo_profile(symbol) if not target_date else None
        # Honest ETF classification
        name_upper = (instrument.get("name") or "").upper()
        is_etf = (
            (profile and profile.get("quote_type") in ("ETF", "MUTUALFUND"))
            or any(k in (instrument.get("type") or "")
                   for k in ("ETP", "ETF", "Open-End Fund", "Fund"))
            or any(k in name_upper for k in ("ETF", "UCITS", "ISHARES", "VANGUARD",
                                              "SPDR", "INVESCO", "AMUNDI", "LYXOR",
                                              "XTRACKERS", "WISDOMTREE"))
        )
        asset_class = "etf" if is_etf else (
            "bond" if (profile and "bond" in (profile.get("quote_type", "").lower()))
            else "equity"
        )
        payload = {
            "ok": True,
            "isin": isin,
            "name": (profile and profile.get("long_name")) or instrument.get("name", ""),
            "symbol": chart["symbol"],
            "exchange": chart.get("exchange", ""),
            "price": chart["price"],
            "currency": chart["currency"],
            "as_of": chart["as_of"],
            "asset_class": asset_class,
            "sector": (profile or {}).get("sector", ""),
            "industry": (profile or {}).get("industry", ""),
            "country": (profile or {}).get("country", ""),
            "fund_category": (profile or {}).get("fund_category", ""),
            "sector_weights": (profile or {}).get("sector_weights", []),
            "top_holdings": (profile or {}).get("top_holdings", []),
            # Provenance: where the price came from, how fresh, and whether
            # OpenFIGI gave us multiple plausible listings (silent-wrong-
            # ticker risk if we picked the wrong one).
            "price_source": f"yahoo:{chart['symbol']}",
            "price_freshness": "historical" if target_date else "live",
            "cache_age_seconds": 0,
            "mapping_ambiguous": len(candidates) > 1,
            "mapping_alternates": max(0, len(candidates) - 1),
            "profile_source": (profile or {}).get("profile_source", "none"),
        }
        if not target_date:
            QUOTE_CACHE[cache_key] = (time.time(), payload)
        return payload
    return {"ok": False, "status": 502, "error": last_err,
            "name": instrument.get("name", ""), "isin": isin}


# ── FX rates ───────────────────────────────────────────────────────────────

CCY_RE = re.compile(r"^[A-Z]{3}$")


def fetch_fx_rate(from_ccy: str, to_ccy: str, target_date: str | None) -> dict:
    """ECB reference rates via Frankfurter. Cached so a busy dashboard doesn't
    hammer the upstream — and so a transient Frankfurter outage doesn't blank
    out every user's portfolio at once."""
    from_ccy = (from_ccy or "").upper()
    to_ccy = (to_ccy or "").upper()
    if not CCY_RE.match(from_ccy) or not CCY_RE.match(to_ccy):
        return {"ok": False, "status": 400, "error": "Currency must be a 3-letter ISO code."}
    if from_ccy == to_ccy:
        return {"ok": True, "rate": 1.0, "date": target_date or "today", "fx_source": "identity"}
    cache_key = f"{from_ccy}-{to_ccy}-{target_date or 'live'}"
    cached = FX_CACHE.get(cache_key)
    if cached:
        ts, payload = cached
        # Historical rates are immutable — cache forever. Live rates expire.
        if target_date or time.time() - ts < FX_TTL_SECONDS:
            return payload
    url = f"{FRANKFURTER_URL}/{target_date or 'latest'}?from={from_ccy}&to={to_ccy}"
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        monitor.record("frankfurter", "failure")
        return {"ok": False, "status": 502, "error": f"FX upstream failed: {exc}"}
    if not isinstance(data, dict):
        monitor.record("frankfurter", "failure")
        return {"ok": False, "status": 502, "error": "FX upstream returned an invalid response."}
    rates = data.get("rates") or {}
    rate = rates.get(to_ccy) if isinstance(rates, dict) else None
    if not isinstance(rate, (int, float)):
        monitor.record("frankfurter", "empty")
        return {"ok": False, "status": 502, "error": f"No rate for {to_ccy} in upstream response."}
    monitor.record("frankfurter", "success")
    payload = {"ok": True, "rate": float(rate), "date": data.get("date") or (target_date or ""), "fx_source": "ECB/Frankfurter"}
    FX_CACHE[cache_key] = (time.time(), payload)
    return payload


# ── HTTP layer ─────────────────────────────────────────────────────────────

class OrionAPIHandler(BaseHTTPRequestHandler):
    server_version = "OrionAPI/2.0"

    def _send_json(self, status: int, payload: dict, extra_headers: dict | None = None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _client_key(self) -> str:
        cloudflare_ip = self.headers.get("CF-Connecting-IP")
        if cloudflare_ip:
            return cloudflare_ip.strip()
        forwarded = self.headers.get("X-Forwarded-For")
        if forwarded:
            # Use the proxy-appended rightmost address so a caller cannot
            # bypass the limiter by prepending arbitrary X-Forwarded-For IPs.
            return forwarded.rsplit(",", 1)[-1].strip()
        return self.client_address[0]

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/health":
            health = monitor.health_snapshot()
            self._send_json(200, {"ok": health["overall"] != "down",
                                  "service": "orion-api", "version": "2.0",
                                  "yfinance": getattr(yf, "__version__", "unknown"),
                                  "fmp_key_set": bool(FMP_API_KEY),
                                  "status": health["overall"],
                                  "upstreams": health["upstreams"],
                                  "fmp_quota": health["fmp_quota"],
                                  "rate_limit": {"requests": API_RATE_LIMIT_REQUESTS,
                                                 "window_seconds": API_RATE_LIMIT_WINDOW}})
            return

        if path.startswith("/api/"):
            allowed, retry_after = rate_limiter.allow(self._client_key())
            if not allowed:
                self._send_json(
                    429,
                    {"ok": False, "error": "Too many requests. Try again shortly."},
                    {"Retry-After": str(retry_after)},
                )
                return

        if path.startswith("/api/isin/"):
            isin = normalize_isin(path.rsplit("/", 1)[-1])
            if not is_valid_isin(isin):
                self._send_json(400, {"ok": False, "error": "Invalid ISIN format or checksum."})
                return
            try:
                instrument = lookup_isin(isin)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 502
                self._send_json(status, {"ok": False, "error": f"OpenFIGI failed: {status}."})
                return
            except requests.RequestException as exc:
                self._send_json(502, {"ok": False, "error": f"OpenFIGI request failed: {exc}"})
                return
            if not instrument:
                self._send_json(404, {"ok": False, "error": "ISIN not found."})
                return
            self._send_json(200, {"ok": True, "instrument": instrument})
            return

        if path.startswith("/api/fx/"):
            parts = path.split("/")
            if len(parts) != 5 or not parts[3] or not parts[4]:
                self._send_json(400, {"ok": False, "error": "Use /api/fx/{from}/{to}"})
                return
            target_date = (query.get("date") or [None])[0]
            payload = fetch_fx_rate(parts[3], parts[4], target_date)
            self._send_json(payload.get("status", 200) if payload.get("ok") else payload.get("status", 502),
                            {k: v for k, v in payload.items() if k != "status"})
            return

        if path.startswith("/api/quote/"):
            isin = normalize_isin(path.rsplit("/", 1)[-1])
            if not is_valid_isin(isin):
                self._send_json(400, {"ok": False, "error": "Invalid ISIN format or checksum."})
                return
            target_date = (query.get("date") or [None])[0]
            try:
                payload = build_quote_payload(isin, target_date)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 502
                self._send_json(status, {"ok": False, "error": f"Upstream failed: {status}."})
                return
            except requests.RequestException as exc:
                self._send_json(502, {"ok": False, "error": f"Upstream request failed: {exc}"})
                return
            if not payload.get("ok"):
                self._send_json(payload.get("status", 502), {k: v for k, v in payload.items() if k != "status"})
                return
            self._send_json(200, payload)
            return

        self._send_json(404, {"ok": False, "error": "Not found."})

    def log_message(self, fmt: str, *args):
        return


def main():
    server = ThreadingHTTPServer((HOST, PORT), OrionAPIHandler)
    print(f"Orion API v2 listening on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
