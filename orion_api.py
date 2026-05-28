import json
import os
import re
import time
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
LIVE_TTL_SECONDS = 60   # current-price freshness
FX_TTL_SECONDS = 3600   # ECB rates publish once per business day

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
    response = requests.post(
        OPENFIGI_URL,
        headers=openfigi_headers(),
        json=[{"idType": "ID_ISIN", "idValue": isin}],
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload or not payload[0].get("data"):
        return None
    # Dedupe on (ticker, exchange) so dual-listed names like SAP — quoted as
    # "SAP" on both Swiss (SW) and Xetra (GR) — keep both entries. The earlier
    # ticker-only dedup silently dropped the domestic listing whenever an
    # alternate venue happened to come first in OpenFIGI's response.
    seen = set()
    listings = []
    for item in payload[0]["data"]:
        ticker = item.get("ticker", "")
        exch = item.get("exchCode", "")
        if not ticker:
            continue
        key = (ticker, exch)
        if key not in seen:
            seen.add(key)
            listings.append({"ticker": ticker, "exch": exch})
    first = payload[0]["data"][0]
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
    try:
        ticker = yf.Ticker(symbol)
        if target_date:
            try:
                dt = datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError:
                return None
            start = (dt - timedelta(days=10)).strftime("%Y-%m-%d")
            end   = (dt + timedelta(days=10)).strftime("%Y-%m-%d")
            hist = ticker.history(start=start, end=end, auto_adjust=False)
            if hist is None or hist.empty:
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
                return None
            row = hist.iloc[best_i]
            info = ticker.fast_info
            return {
                "price": float(row["Close"]),
                "currency": getattr(info, "currency", "USD") or "USD",
                "symbol": symbol,
                "as_of": hist.index[best_i].strftime("%Y-%m-%d"),
                "exchange": getattr(info, "exchange", "") or "",
            }
        # Live current price
        info = ticker.fast_info
        price = getattr(info, "last_price", None)
        if price is None:
            return None
        return {
            "price": float(price),
            "currency": getattr(info, "currency", "USD") or "USD",
            "symbol": symbol,
            "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "exchange": getattr(info, "exchange", "") or "",
        }
    except Exception:
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
        # ETF look-through if available
        sector_weights = []
        try:
            funds_data = getattr(ticker, "funds_data", None)
            if funds_data is not None:
                sw = getattr(funds_data, "sector_weightings", None)
                sector_weights = _coerce_sector_weights(sw)
        except Exception:
            pass
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
        }
        PROFILE_CACHE[symbol] = profile
        return profile
    except Exception:
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
            return payload
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
        return {"ok": True, "rate": 1.0, "date": target_date or "today"}
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
    except requests.RequestException as exc:
        return {"ok": False, "status": 502, "error": f"FX upstream failed: {exc}"}
    rate = (data.get("rates") or {}).get(to_ccy)
    if not isinstance(rate, (int, float)):
        return {"ok": False, "status": 502, "error": f"No rate for {to_ccy} in upstream response."}
    payload = {"ok": True, "rate": float(rate), "date": data.get("date") or (target_date or "")}
    FX_CACHE[cache_key] = (time.time(), payload)
    return payload


# ── HTTP layer ─────────────────────────────────────────────────────────────

class OrionAPIHandler(BaseHTTPRequestHandler):
    server_version = "OrionAPI/2.0"

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/health":
            self._send_json(200, {"ok": True, "service": "orion-api", "version": "2.0",
                                  "yfinance": getattr(yf, "__version__", "unknown")})
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
