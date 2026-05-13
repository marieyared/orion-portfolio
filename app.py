import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
import json
import os
import calendar as _calendar
from concurrent.futures import ThreadPoolExecutor
from orion_ai_insights import generate_portfolio_insights, render_insights_card


st.set_page_config(
    page_title="Orion: Portfolio Intelligence",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }
    .main { background-color: #f8f7f4; }
    .block-container { padding: 2rem 2rem 4rem; max-width: 900px; }

    h1 { font-size: 24px !important; font-weight: 500 !important; }
    h2 { font-size: 18px !important; font-weight: 500 !important; }
    h3 { font-size: 15px !important; font-weight: 500 !important; }

    .orion-logo {
        font-family: 'DM Mono', monospace;
        font-size: 12px;
        letter-spacing: 0.12em;
        color: #999;
        margin-bottom: 0.25rem;
    }
    .orion-headline {
        font-size: 26px;
        font-weight: 300;
        color: #1a1a1a;
        margin-bottom: 0.4rem;
        line-height: 1.3;
    }
    .orion-sub {
        font-size: 14px;
        color: #777;
        margin-bottom: 2rem;
        line-height: 1.6;
    }
    .hint-box {
        background: #f0f0ec;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-size: 13px;
        color: #666;
        margin-bottom: 1.5rem;
        line-height: 1.6;
    }
    .instrument-found {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        color: #15803d;
        margin-top: 4px;
        font-family: 'DM Sans', sans-serif;
    }
    .instrument-error {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
        color: #dc2626;
        margin-top: 4px;
    }
    .summary-card {
        background: white;
        border: 1px solid #e8e6e0;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
    }
    .summary-label {
        font-size: 11px;
        color: #999;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
    }
    .summary-value {
        font-family: 'DM Mono', monospace;
        font-size: 22px;
        font-weight: 500;
        color: #1a1a1a;
    }
    .summary-value.pos { color: #15803d; }
    .summary-value.neg { color: #dc2626; }

    .alert-box {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 13px;
        color: #dc2626;
        margin-bottom: 0.5rem;
    }
    .warn-box {
        background: #fffbeb;
        border: 1px solid #fcd34d;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 13px;
        color: #92400e;
        margin-bottom: 0.5rem;
    }
    .stButton > button {
        background: #1a1a1a !important;
        color: white !important;
        border: none !important;
        border-radius: 9px !important;
        padding: 0.6rem 1.5rem !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        font-family: 'DM Sans', sans-serif !important;
        white-space: nowrap !important;
        width: 100%;
    }
    .stButton > button:hover { opacity: 0.85 !important; }

    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #e8e6e0;
        border-radius: 10px;
        padding: 1rem;
    }
    div[data-testid="stMetricLabel"] p {
        white-space: normal !important;
        word-break: break-word;
    }
    .stDataFrame { border-radius: 10px; overflow: hidden; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── session state ──────────────────────────────────────────────────
if "holdings" not in st.session_state:
    st.session_state.holdings = []
if "screen" not in st.session_state:
    st.session_state.screen = "entry"
if "isin_cache" not in st.session_state:
    st.session_state.isin_cache = {}
if "api_issues" not in st.session_state:
    st.session_state.api_issues = {}
if "cash_rows" not in st.session_state:
    st.session_state.cash_rows = []
if "bond_rows" not in st.session_state:
    st.session_state.bond_rows = []


def set_api_issue(service: str, message: str):
    st.session_state.api_issues[service] = message


def clear_api_issue(service: str):
    st.session_state.api_issues.pop(service, None)


def get_config_value(name: str) -> str:
    try:
        value = st.secrets[name]
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.getenv(name, "").strip()

# ── OpenFIGI lookup ────────────────────────────────────────────────
def lookup_isin(isin):
    isin = isin.strip().upper()
    if not isin or len(isin) != 12:
        return None
    if isin in st.session_state.isin_cache:
        return st.session_state.isin_cache[isin]
    try:
        resp = requests.post(
            "https://api.openfigi.com/v3/mapping",
            headers={"Content-Type": "application/json"},
            json=[{"idType": "ID_ISIN", "idValue": isin}],
            timeout=5
        )
        if resp.status_code == 200:
            clear_api_issue("openfigi")
            data = resp.json()
            if data and data[0].get("data"):
                item = data[0]["data"][0]
                seen = set()
                all_listings = []
                for d in data[0]["data"]:
                    t = d.get("ticker", "")
                    if t and t not in seen:
                        seen.add(t)
                        all_listings.append((t, d.get("exchCode", "")))
                result = {
                    "name": item.get("name", isin),
                    "type": item.get("securityType", "N/A"),
                    "exchange": item.get("exchCode", "N/A"),
                    "currency": item.get("marketSector", "N/A"),
                    "ticker": item.get("ticker", ""),
                    "all_listings": all_listings,
                }
                st.session_state.isin_cache[isin] = result
                return result
        elif resp.status_code == 429:
            set_api_issue("openfigi", "OpenFIGI rate limit reached. Please wait a minute and try again.")
        else:
            set_api_issue("openfigi", f"OpenFIGI lookup failed with status {resp.status_code}.")
    except requests.RequestException as exc:
        set_api_issue("openfigi", f"OpenFIGI request failed: {exc}")
    return None

FMP_COUNTRY_MAP = {
    "United States":"US","Japan":"JP","United Kingdom":"GB","France":"FR",
    "Canada":"CA","Switzerland":"CH","Germany":"DE","Australia":"AU",
    "Netherlands":"NL","China":"CN","Taiwan":"TW","India":"IN",
    "South Korea":"KR","Korea":"KR","Brazil":"BR","Saudi Arabia":"SA",
    "Sweden":"SE","Norway":"NO","Denmark":"DK","Finland":"FI","Spain":"ES",
    "Italy":"IT","Portugal":"PT","Belgium":"BE","Austria":"AT","Ireland":"IE",
    "Luxembourg":"LU","Singapore":"SG","Hong Kong":"HK","South Africa":"ZA",
    "Mexico":"MX","Russia":"RU","Poland":"PL","Czech Republic":"CZ",
    "Hungary":"HU","Turkey":"TR","Israel":"IL","United Arab Emirates":"AE",
    "UAE":"AE","Qatar":"QA","Thailand":"TH","Indonesia":"ID","Malaysia":"MY",
    "Philippines":"PH","Vietnam":"VN","Chile":"CL","Colombia":"CO",
    "Argentina":"AR","New Zealand":"NZ","Greece":"GR",
}

# OpenFIGI exchCode → Yahoo Finance ticker suffix
_FIGI_EXCH_TO_YAHOO = {
    "LN": ".L", "NA": ".AS", "GR": ".DE", "FP": ".PA",
    "IM": ".MI", "SM": ".MC", "SW": ".SW", "AU": ".AX",
    "SS": ".ST", "HE": ".HE", "CO": ".CO", "BB": ".BR",
}

_YAHOO_SECTOR_MAP = {
    "realestate": "Real Estate", "consumer_cyclical": "Consumer",
    "basic_materials": "Materials", "consumer_defensive": "Consumer Defensive",
    "technology": "Technology", "communication_services": "Communication",
    "financial_services": "Financials", "utilities": "Utilities",
    "industrials": "Industrials", "energy": "Energy", "healthcare": "Healthcare",
}

# ── Bond & Cash helpers ──────────────────────────────────────────
_BOND_PREFIXES = {"XS", "XD", "XA", "XB", "XC", "XE", "XF"}
_BOND_SEC_TYPES = {"Bond", "Corporate Bond", "Government Bond", "Note", "Debenture"}

_CURRENCY_FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "CHF": "🇨🇭", "CAD": "🇨🇦", "AUD": "🇦🇺", "CNY": "🇨🇳",
    "HKD": "🇭🇰", "SGD": "🇸🇬", "NOK": "🇳🇴", "SEK": "🇸🇪",
    "DKK": "🇩🇰", "SAR": "🇸🇦", "AED": "🇦🇪", "INR": "🇮🇳",
    "BRL": "🇧🇷", "MXN": "🇲🇽", "ZAR": "🇿🇦", "TRY": "🇹🇷",
}
_CURRENCY_COUNTRY = {
    "USD": "US", "EUR": "EU", "GBP": "GB", "JPY": "JP",
    "CHF": "CH", "CAD": "CA", "AUD": "AU", "CNY": "CN",
    "HKD": "HK", "SGD": "SG", "NOK": "NO", "SEK": "SE",
    "DKK": "DK", "SAR": "SA", "AED": "AE", "INR": "IN",
    "BRL": "BR", "MXN": "MX", "ZAR": "ZA", "TRY": "TR",
}
_CURRENCIES = list(_CURRENCY_FLAGS.keys())

def isin_is_likely_bond(isin: str) -> bool:
    if isin[:2].upper() in _BOND_PREFIXES:
        return True
    sec_type = st.session_state.isin_cache.get(isin.upper(), {}).get("type", "")
    return any(bt.lower() in sec_type.lower() for bt in _BOND_SEC_TYPES)

def find_last_coupon_date(maturity: date, today: date) -> date:
    """Semi-annual coupon dates anchored to the maturity month/day."""
    m_month, m_day = maturity.month, maturity.day
    candidates = []
    for yr in [today.year - 1, today.year, today.year + 1]:
        for offset in [0, 6]:
            mo = (m_month - 1 + offset) % 12 + 1
            yr_adj = yr + (m_month - 1 + offset) // 12
            last = _calendar.monthrange(yr_adj, mo)[1]
            candidates.append(date(yr_adj, mo, min(m_day, last)))
    past = [d for d in candidates if d <= today]
    return max(past) if past else today

def bond_accrued_interest(face_value: float, quantity: float, coupon_pct: float, maturity: date) -> float:
    today = date.today()
    last_coupon = find_last_coupon_date(maturity, today)
    days_accrued = max(0, (today - last_coupon).days)
    annual = face_value * quantity * (coupon_pct / 100)
    return annual * (days_accrued / 365.0)

def bond_annual_income(face_value: float, quantity: float, coupon_pct: float) -> float:
    return face_value * quantity * (coupon_pct / 100)


@st.cache_data(ttl=86400, show_spinner=False)
def _stock_country(ticker: str) -> str:
    """ISO-2 country for a single stock ticker from Yahoo assetProfile."""
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}",
            params={"modules": "assetProfile"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        if r.status_code == 200:
            res = r.json().get("quoteSummary", {}).get("result")
            if res:
                c = res[0].get("assetProfile", {}).get("country", "")
                return FMP_COUNTRY_MAP.get(c, "Other")
    except Exception:
        pass
    return "Other"

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_etf_data_yahoo(ticker: str, exch_code: str = ""):
    """Yahoo Finance ETF look-through: sector weights + country weights + top holdings.
    Works for both US ETFs (countryExposure filled) and European UCITS (derives country
    from top holdings when countryExposure is empty)."""
    if not ticker or ticker == "N/A":
        return None
    suffix = _FIGI_EXCH_TO_YAHOO.get(exch_code, "")
    candidates = []
    if suffix:
        candidates.append(ticker + suffix)
    candidates.append(ticker)
    if not suffix:
        candidates += [ticker + s for s in [".L", ".AS", ".DE", ".PA", ".MI"]]
    for yt in candidates:
        try:
            resp = requests.get(
                f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{yt}",
                params={"modules": "topHoldings"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=4,
            )
            if resp.status_code != 200:
                continue
            result = resp.json().get("quoteSummary", {}).get("result")
            if not result:
                continue
            top         = result[0].get("topHoldings", {})
            holdings_raw = top.get("holdings", [])
            country_exp  = top.get("countryExposure", [])
            sector_exp   = top.get("sectorWeightings", [])

            # Need at least sector or holdings data — don't require countryExposure
            if not holdings_raw and not sector_exp:
                continue

            # Top individual stock holdings
            top_holdings = [
                {
                    "symbol": h.get("symbol", ""),
                    "name":   h.get("holdingName", h.get("symbol", "")),
                    "weight": round(float(h.get("holdingPercent", 0)) * 100, 2),
                }
                for h in holdings_raw
                if h.get("symbol") and float(h.get("holdingPercent", 0)) > 0
            ]

            # Sector weights
            sectors = {}
            for s_dict in sector_exp:
                for key, val in s_dict.items():
                    label = _YAHOO_SECTOR_MAP.get(key, key.replace("_", " ").title())
                    sectors[label] = round(float(val) * 100, 2)

            # Country weights — use countryExposure when available;
            # fall back to per-stock country lookup from top holdings
            geo = {}
            if country_exp:
                for c in country_exp:
                    pct  = round(float(c.get("exposure", 0)) * 100, 2)
                    code = FMP_COUNTRY_MAP.get(c.get("country", ""), "Other")
                    geo[code] = geo.get(code, 0) + pct
            elif top_holdings:
                symbols = [h["symbol"] for h in top_holdings]
                with ThreadPoolExecutor(max_workers=min(len(symbols), 8)) as ex:
                    codes = list(ex.map(_stock_country, symbols))
                for h, code in zip(top_holdings, codes):
                    geo[code] = geo.get(code, 0) + h["weight"]

            return {
                "geo":          geo or {"Other": 100},
                "sectors":      sectors or {"Other": 100},
                "top_holdings": top_holdings,
            }
        except Exception:
            continue
    return None

def _map_country(c: str):
    if not c:
        return None
    if c in COUNTRY_NAMES:
        return c
    mapped = FMP_COUNTRY_MAP.get(c)
    return mapped if mapped and mapped != "Other" else None

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_stock_info(ticker: str, exch_code: str = "") -> dict:
    """Fetch sector and country of operations for a single stock via FMP then Yahoo."""
    out = {"sector": "—", "country": None}
    if not ticker or ticker == "N/A":
        return out
    FMP_KEY = get_config_value("FMP_API_KEY")
    if FMP_KEY:
        try:
            r = requests.get(
                f"https://financialmodelingprep.com/api/v3/profile/{ticker}",
                params={"apikey": FMP_KEY}, timeout=5,
            )
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data, list):
                    s = data[0].get("sector", "")
                    if s:
                        out["sector"] = s
                    if not out["country"]:
                        out["country"] = _map_country(data[0].get("country", ""))
                    if out["sector"] != "—" and out["country"]:
                        return out
        except Exception:
            pass
    suffix = _FIGI_EXCH_TO_YAHOO.get(exch_code, "")
    candidates = [ticker + suffix] if suffix else []
    candidates.append(ticker)
    for yt in candidates:
        try:
            r = requests.get(
                f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{yt}",
                params={"modules": "assetProfile"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=4,
            )
            if r.status_code == 200:
                res = r.json().get("quoteSummary", {}).get("result")
                if res:
                    profile = res[0].get("assetProfile", {})
                    s = profile.get("sector", "")
                    c = profile.get("country", "")
                    if s and out["sector"] == "—":
                        out["sector"] = s
                    if not out["country"]:
                        out["country"] = _map_country(c)
                    if out["sector"] != "—" and out["country"]:
                        return out
        except Exception:
            continue
    return out

_WIKIDATA_SECTOR_MAP = {
    "software": "Technology", "semiconductor": "Technology", "computer": "Technology",
    "internet": "Technology", "electronics": "Technology", "artificial intelligence": "Technology",
    "e-commerce": "Technology", "cloud": "Technology",
    "bank": "Financials", "insurance": "Financials", "financial": "Financials",
    "investment": "Financials", "asset management": "Financials",
    "pharmaceutical": "Healthcare", "biotechnology": "Healthcare", "health": "Healthcare",
    "medical": "Healthcare", "hospital": "Healthcare",
    "retail": "Consumer", "apparel": "Consumer", "luxury": "Consumer",
    "automobile": "Consumer", "automotive": "Consumer", "restaurant": "Consumer",
    "food": "Consumer Defensive", "beverage": "Consumer Defensive",
    "supermarket": "Consumer Defensive", "tobacco": "Consumer Defensive",
    "oil": "Energy", "gas": "Energy", "energy": "Energy", "petroleum": "Energy",
    "mining": "Materials", "chemical": "Materials", "steel": "Materials", "metal": "Materials",
    "aerospace": "Industrials", "defence": "Industrials", "defense": "Industrials",
    "logistics": "Industrials", "manufacturing": "Industrials", "industrial": "Industrials",
    "railway": "Industrials", "airline": "Industrials",
    "telecommunication": "Communication", "telecom": "Communication",
    "media": "Communication", "entertainment": "Communication", "broadcasting": "Communication",
    "real estate": "Real Estate", "reit": "Real Estate",
    "utility": "Utilities", "electric": "Utilities", "water": "Utilities",
}

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_sector_wikidata(isin: str) -> str | None:
    """Query Wikidata SPARQL for industry/sector by ISIN — no API key needed."""
    query = f"""
    SELECT ?industryLabel WHERE {{
      ?company wdt:P946 "{isin}" .
      ?company wdt:P452 ?industry .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
    }} LIMIT 5
    """
    try:
        r = requests.get(
            "https://query.wikidata.org/sparql",
            params={"query": query, "format": "json"},
            headers={"User-Agent": "OrionPortfolioApp/1.0"},
            timeout=8,
        )
        if r.status_code == 200:
            bindings = r.json().get("results", {}).get("bindings", [])
            for b in bindings:
                label = b.get("industryLabel", {}).get("value", "").lower()
                for kw, sector in _WIKIDATA_SECTOR_MAP.items():
                    if kw in label:
                        return sector
    except Exception:
        pass
    return None

_ETF_TYPES = {"ETP", "ETF", "Open-End Fund", "Exchange Traded Fund",
              "UCITS", "Fund", "Mutual Fund"}
_ETF_NAME_KEYWORDS = ("ETF", "UCITS", "INDEX FUND", "ISHARES", "VANGUARD",
                      "SPDR", "INVESCO", "AMUNDI", "LYXOR", "XTRACKERS", "WISDOMTREE")

def holding_is_etf(isin: str, isin_cache: dict = None) -> bool:
    cache  = isin_cache if isin_cache is not None else st.session_state.isin_cache
    cached = cache.get(isin, {})
    if cached.get("type", "") in _ETF_TYPES:
        return True
    name = cached.get("name", "").upper()
    return any(kw in name for kw in _ETF_NAME_KEYWORDS)

def get_holding_info(isin: str, isin_cache: dict = None, asset_type: str = "stock_etf") -> dict:
    """Return {name, geo, sectors} for an ISIN — always returns a dict, never None."""
    if asset_type == "cash":
        currency = isin.replace("CASH_", "")
        flag = _CURRENCY_FLAGS.get(currency, "")
        country = _CURRENCY_COUNTRY.get(currency, "Other")
        return {"name": f"{flag} Cash ({currency})", "geo": {country: 100}, "sectors": {"Cash": 100}}
    if asset_type == "bond":
        cache = isin_cache if isin_cache is not None else st.session_state.isin_cache
        cached_figi = cache.get(isin, {})
        name = cached_figi.get("name", isin)
        code = country_from_isin(isin)
        return {"name": name, "geo": {code: 100}, "sectors": {"Fixed Income": 100}}
    cache       = isin_cache if isin_cache is not None else st.session_state.isin_cache
    cached_figi = cache.get(isin, {})
    name     = cached_figi.get("name", isin)
    listings = cached_figi.get("all_listings") or (
        [(cached_figi["ticker"], cached_figi.get("exchange", ""))] if cached_figi.get("ticker") else []
    )
    if holding_is_etf(isin, cache):
        yahoo_data = None
        for t, e in listings:
            d = fetch_etf_data_yahoo(t, e)
            if d:
                yahoo_data = d
                break
        if yahoo_data:
            merged = {"name": name}
            merged["geo"] = yahoo_data["geo"]
            merged["sectors"] = yahoo_data["sectors"]
            merged["top_holdings"] = yahoo_data.get("top_holdings", [])
            return merged
        # Fallback: ETF domicile from ISIN prefix, no look-through available
        code = country_from_isin(isin)
        return {"name": name, "geo": {code: 100}, "sectors": {"ETF / Fund": 100}}
    else:
        # Direct equity: country of operations from FMP/Yahoo, fall back to ISIN prefix
        ticker = cached_figi.get("ticker", "")
        exch   = cached_figi.get("exchange", "")
        if ticker:
            stock_data = fetch_stock_info(ticker, exch)
            sector = stock_data["sector"]
            code   = stock_data["country"] or country_from_isin(isin)
        else:
            code   = country_from_isin(isin)
            sector = "—"
        if sector == "—":
            sector = fetch_sector_wikidata(isin) or "—"
        return {"name": name, "geo": {code: 100}, "sectors": {sector: 100}}

FLAGS = {
    "US":"🇺🇸","JP":"🇯🇵","GB":"🇬🇧","FR":"🇫🇷","CA":"🇨🇦","CH":"🇨🇭","DE":"🇩🇪",
    "AU":"🇦🇺","NL":"🇳🇱","CN":"🇨🇳","TW":"🇹🇼","IN":"🇮🇳","KR":"🇰🇷","BR":"🇧🇷",
    "SA":"🇸🇦","EU":"🇪🇺","SE":"🇸🇪","NO":"🇳🇴","DK":"🇩🇰","FI":"🇫🇮","ES":"🇪🇸",
    "IT":"🇮🇹","PT":"🇵🇹","BE":"🇧🇪","AT":"🇦🇹","IE":"🇮🇪","LU":"🇱🇺","SG":"🇸🇬",
    "HK":"🇭🇰","ZA":"🇿🇦","MX":"🇲🇽","RU":"🇷🇺","PL":"🇵🇱","CZ":"🇨🇿","HU":"🇭🇺",
    "TR":"🇹🇷","IL":"🇮🇱","AE":"🇦🇪","QA":"🇶🇦","TH":"🇹🇭","ID":"🇮🇩","MY":"🇲🇾",
    "PH":"🇵🇭","VN":"🇻🇳","CL":"🇨🇱","CO":"🇨🇴","AR":"🇦🇷","NZ":"🇳🇿","GR":"🇬🇷",
    "Other":"🌍",
}

COUNTRY_NAMES = {
    "US":"United States","JP":"Japan","GB":"United Kingdom","FR":"France",
    "CA":"Canada","CH":"Switzerland","DE":"Germany","AU":"Australia",
    "NL":"Netherlands","CN":"China","TW":"Taiwan","IN":"India",
    "KR":"South Korea","BR":"Brazil","SA":"Saudi Arabia","EU":"Europe (other)",
    "SE":"Sweden","NO":"Norway","DK":"Denmark","FI":"Finland","ES":"Spain",
    "IT":"Italy","PT":"Portugal","BE":"Belgium","AT":"Austria","IE":"Ireland",
    "LU":"Luxembourg","SG":"Singapore","HK":"Hong Kong","ZA":"South Africa",
    "MX":"Mexico","RU":"Russia","PL":"Poland","CZ":"Czech Republic","HU":"Hungary",
    "TR":"Turkey","IL":"Israel","AE":"UAE","QA":"Qatar","TH":"Thailand",
    "ID":"Indonesia","MY":"Malaysia","PH":"Philippines","VN":"Vietnam",
    "CL":"Chile","CO":"Colombia","AR":"Argentina","NZ":"New Zealand","GR":"Greece",
    "Other":"Rest of world",
}

ISO3_MAP = {
    "US":"USA","JP":"JPN","GB":"GBR","FR":"FRA","CA":"CAN","CH":"CHE",
    "DE":"DEU","AU":"AUS","NL":"NLD","CN":"CHN","TW":"TWN","IN":"IND",
    "KR":"KOR","BR":"BRA","SA":"SAU","SE":"SWE","NO":"NOR","DK":"DNK",
    "FI":"FIN","ES":"ESP","IT":"ITA","PT":"PRT","BE":"BEL","AT":"AUT",
    "IE":"IRL","LU":"LUX","SG":"SGP","HK":"HKG","ZA":"ZAF","MX":"MEX",
    "RU":"RUS","PL":"POL","CZ":"CZE","HU":"HUN","TR":"TUR","IL":"ISR",
    "AE":"ARE","QA":"QAT","TH":"THA","ID":"IDN","MY":"MYS","PH":"PHL",
    "VN":"VNM","CL":"CHL","CO":"COL","AR":"ARG","NZ":"NZL","GR":"GRC",
    "EU":None,"Other":None,
}

# Derive country from the 2-letter ISIN prefix (ISO 3166-1 alpha-2).
# Returns a geo dict like {"XX": 100} for use as a fallback.
def country_from_isin(isin):
    code = isin[:2].upper()
    if code in COUNTRY_NAMES:
        return code
    return "Other"

COLORS = ["#378ADD","#1D9E75","#EF9F27","#7F77DD","#D85A30","#5DCAA5","#D4537E","#639922"]

# ── aggregate geo + sectors across all holdings ────────────────────
def aggregate_portfolio(holdings, info_map):
    total_value = sum(h["current"] for h in holdings)
    if total_value == 0:
        return {}, {}
    geo_agg = {}
    sector_agg = {}
    for h in holdings:
        weight = h["current"] / total_value
        source = info_map.get(h["isin"].upper())
        if source:
            for country, pct in source["geo"].items():
                geo_agg[country] = geo_agg.get(country, 0) + pct * weight
            for sector, pct in source["sectors"].items():
                sector_agg[sector] = sector_agg.get(sector, 0) + pct * weight
    return geo_agg, sector_agg

_GEO_WARN_PCT    = 60.0
_SECTOR_WARN_PCT = 40.0

def compute_warnings(geo_agg: dict, sector_agg: dict) -> list:
    msgs = []
    for code, pct in geo_agg.items():
        if pct >= _GEO_WARN_PCT:
            flag = FLAGS.get(code, "")
            name = COUNTRY_NAMES.get(code, code)
            msgs.append(f"{flag} <b>{name}</b> is <b>{pct:.0f}%</b> of your portfolio — consider diversifying geographically.")
    for sector, pct in sector_agg.items():
        if pct >= _SECTOR_WARN_PCT and sector not in ("ETF / Fund", "—", "Other", "Cash", "Fixed Income"):
            msgs.append(f"<b>{pct:.0f}% in {sector}</b> — high concentration in one sector.")
    return msgs


def build_info_map(holdings: list) -> dict:
    cache = dict(st.session_state.isin_cache)
    def _get(h):
        return get_holding_info(h["isin"].upper(), cache, h.get("asset_type", "stock_etf"))
    isins = [h["isin"].upper() for h in holdings]
    with ThreadPoolExecutor(max_workers=min(len(isins), 8)) as ex:
        infos = list(ex.map(_get, holdings))
    return dict(zip(isins, infos))


# ══════════════════════════════════════════════════════════════════
# SCREEN 1 — ENTRY
# ══════════════════════════════════════════════════════════════════
def screen_entry():
    st.markdown('<div class="orion-logo">ORION / PORTFOLIO INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="orion-headline">Enter your holdings</div>', unsafe_allow_html=True)
    st.markdown('<div class="orion-sub">Find your ISIN on any broker statement — UBS, Baraka, eToro. Enter the current value and your purchase details.</div>', unsafe_allow_html=True)
    st.markdown('<div class="hint-box">💡 Your ISIN is a 12-character code on every broker statement — e.g. <b>IE00B4L5Y983</b> for iShares MSCI World. We look it up automatically.</div>', unsafe_allow_html=True)
    if "openfigi" in st.session_state.api_issues:
        st.warning(st.session_state.api_issues["openfigi"])

    if "entry_rows" not in st.session_state:
        st.session_state.entry_rows = [
            {"isin":"IE00B4L5Y983","current":90000.0,"date":date(2022,3,15),"paid":71000.0},
            {"isin":"US0378331005","current":52000.0,"date":date(2021,6,10),"paid":38000.0},
            {"isin":"SA14TG012N13","current":45000.0,"date":date(2023,1,20),"paid":39000.0},
            {"isin":"US5949181045","current":38000.0,"date":date(2022,9,5), "paid":28500.0},
            {"isin":"IE00BKM4GZ66","current":22500.0,"date":date(2023,7,12),"paid":20000.0},
        ]

    col_isin, col_cur, col_date, col_paid, col_del = st.columns([2.2, 1.3, 1.3, 1.3, 0.4])
    with col_isin:  st.markdown("**ISIN**")
    with col_cur:   st.markdown("**Current value ($)**")
    with col_date:  st.markdown("**Purchase date**")
    with col_paid:  st.markdown("**Amount paid ($)**")
    with col_del:   st.markdown("&nbsp;", unsafe_allow_html=True)

    rows_to_delete = []
    for i, row in enumerate(st.session_state.entry_rows):
        c1, c2, c3, c4, c5 = st.columns([2.2, 1.3, 1.3, 1.3, 0.4])
        with c1:
            isin = st.text_input("ISIN", value=row["isin"], key=f"isin_{i}",
                                  label_visibility="collapsed",
                                  placeholder="e.g. IE00B4L5Y983",
                                  max_chars=12).upper().strip()
            st.session_state.entry_rows[i]["isin"] = isin
            if len(isin) == 12:
                info = lookup_isin(isin)
                if info:
                    st.markdown(f'<div class="instrument-found">✓ {info["name"]} · {info["type"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="instrument-error">ISIN not recognised</div>', unsafe_allow_html=True)
        with c2:
            st.session_state.entry_rows[i]["current"] = st.number_input(
                "Current", value=float(row["current"]), min_value=0.0, step=1000.0,
                key=f"cur_{i}", label_visibility="collapsed", format="%.0f")
        with c3:
            st.session_state.entry_rows[i]["date"] = st.date_input(
                "Date", value=row["date"], key=f"date_{i}",
                label_visibility="collapsed", min_value=date(2000,1,1))
        with c4:
            st.session_state.entry_rows[i]["paid"] = st.number_input(
                "Paid", value=float(row["paid"]), min_value=0.0, step=1000.0,
                key=f"paid_{i}", label_visibility="collapsed", format="%.0f")
        with c5:
            if st.button("✕", key=f"del_{i}", help="Remove"):
                rows_to_delete.append(i)

    for i in sorted(rows_to_delete, reverse=True):
        st.session_state.entry_rows.pop(i)
    if rows_to_delete:
        st.rerun()

    st.markdown("&nbsp;", unsafe_allow_html=True)
    if st.button("＋  Add stock / ETF"):
        st.session_state.entry_rows.append(
            {"isin": "", "current": 0.0, "date": date.today(), "paid": 0.0})
        st.rerun()

    # ── Cash section ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Cash positions")
    st.markdown(
        '<div class="hint-box">💵 Enter cash balances by currency. '
        'Amount is treated as current value with no market-price risk.</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.cash_rows:
        ch1, ch2, ch3 = st.columns([1.5, 2.5, 0.4])
        ch1.markdown("**Currency**")
        ch2.markdown("**Amount ($)**")
        ch3.markdown("&nbsp;", unsafe_allow_html=True)

    cash_to_delete = []
    for i, crow in enumerate(st.session_state.cash_rows):
        cc1, cc2, cc3 = st.columns([1.5, 2.5, 0.4])
        with cc1:
            cur_options = _CURRENCIES
            cur_idx = cur_options.index(crow.get("currency", "USD")) if crow.get("currency", "USD") in cur_options else 0
            st.session_state.cash_rows[i]["currency"] = st.selectbox(
                "Currency", cur_options, index=cur_idx,
                key=f"cash_cur_{i}", label_visibility="collapsed",
            )
        with cc2:
            st.session_state.cash_rows[i]["amount"] = st.number_input(
                "Amount", value=float(crow.get("amount", 0.0)),
                min_value=0.0, step=1000.0, format="%.0f",
                key=f"cash_amt_{i}", label_visibility="collapsed",
            )
        with cc3:
            if st.button("✕", key=f"cash_del_{i}", help="Remove"):
                cash_to_delete.append(i)

    for i in sorted(cash_to_delete, reverse=True):
        st.session_state.cash_rows.pop(i)
    if cash_to_delete:
        st.rerun()

    if st.button("＋  Add cash position"):
        st.session_state.cash_rows.append({"currency": "USD", "amount": 0.0})
        st.rerun()

    # ── Bond section ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Bond holdings")
    st.markdown(
        '<div class="hint-box">🔗 Enter your bond ISIN — we\'ll look it up and detect the type. '
        '<b>XS</b> and <b>XD</b> prefix ISINs are Eurobonds. '
        'Provide coupon rate, maturity, face value, and quantity to estimate annual income and accrued interest.</div>',
        unsafe_allow_html=True,
    )

    bonds_to_delete = []
    for i, brow in enumerate(st.session_state.bond_rows):
        with st.container(border=True):
            bisin_col, bdel_col = st.columns([11, 0.5])
            with bisin_col:
                bisin = st.text_input(
                    "Bond ISIN", value=brow.get("isin", ""),
                    key=f"bond_isin_{i}", label_visibility="collapsed",
                    placeholder="e.g. XS2479923143 or DE0001102580",
                    max_chars=12,
                ).upper().strip()
                st.session_state.bond_rows[i]["isin"] = bisin
                if len(bisin) == 12:
                    binfo = lookup_isin(bisin)
                    if binfo:
                        likely = isin_is_likely_bond(bisin)
                        badge_cls = "instrument-found" if likely else "instrument-found"
                        bond_label = "Bond confirmed" if likely else "Instrument found — verify it is a bond"
                        st.markdown(
                            f'<div class="{badge_cls}">✓ {binfo["name"]} · {binfo["type"]} · {bond_label}</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown('<div class="instrument-error">ISIN not recognised</div>', unsafe_allow_html=True)
            with bdel_col:
                if st.button("✕", key=f"bond_del_{i}", help="Remove bond"):
                    bonds_to_delete.append(i)

            b1, b2, b3, b4 = st.columns(4)
            with b1:
                st.session_state.bond_rows[i]["coupon"] = st.number_input(
                    "Coupon rate (% / yr)", value=float(brow.get("coupon", 5.0)),
                    min_value=0.0, max_value=50.0, step=0.25, format="%.2f",
                    key=f"bond_coupon_{i}",
                )
            with b2:
                st.session_state.bond_rows[i]["maturity"] = st.date_input(
                    "Maturity date",
                    value=brow.get("maturity", date(date.today().year + 5, 1, 1)),
                    key=f"bond_mat_{i}", min_value=date.today(),
                )
            with b3:
                st.session_state.bond_rows[i]["face_value"] = st.number_input(
                    "Face value per bond ($)", value=float(brow.get("face_value", 1000.0)),
                    min_value=1.0, step=100.0, format="%.0f",
                    key=f"bond_fv_{i}",
                )
            with b4:
                st.session_state.bond_rows[i]["quantity"] = st.number_input(
                    "Quantity (bonds)", value=int(brow.get("quantity", 1)),
                    min_value=1, step=1, key=f"bond_qty_{i}",
                )

            b5, b6, b7 = st.columns(3)
            with b5:
                st.session_state.bond_rows[i]["purchase_date"] = st.date_input(
                    "Purchase date", value=brow.get("purchase_date", date.today()),
                    key=f"bond_pdate_{i}", min_value=date(2000, 1, 1), max_value=date.today(),
                )
            with b6:
                st.session_state.bond_rows[i]["purchase_price"] = st.number_input(
                    "Purchase price (% of par)", value=float(brow.get("purchase_price", 100.0)),
                    min_value=0.1, max_value=200.0, step=0.5, format="%.2f",
                    key=f"bond_pp_{i}",
                )
            with b7:
                st.session_state.bond_rows[i]["current_price"] = st.number_input(
                    "Current price (% of par)", value=float(brow.get("current_price", 100.0)),
                    min_value=0.1, max_value=200.0, step=0.5, format="%.2f",
                    key=f"bond_cp_{i}",
                )

            # Live computed estimates
            fv   = st.session_state.bond_rows[i]["face_value"]
            qty  = st.session_state.bond_rows[i]["quantity"]
            coup = st.session_state.bond_rows[i]["coupon"]
            mat  = st.session_state.bond_rows[i]["maturity"]
            cp   = st.session_state.bond_rows[i]["current_price"]
            pp   = st.session_state.bond_rows[i]["purchase_price"]
            par      = fv * qty
            curr_val = par * (cp / 100)
            paid_val = par * (pp / 100)
            ann_inc  = bond_annual_income(fv, qty, coup)
            accrued  = bond_accrued_interest(fv, qty, coup, mat)
            pnl      = curr_val - paid_val
            pnl_sign = "+" if pnl >= 0 else ""
            pnl_col  = "#15803d" if pnl >= 0 else "#dc2626"
            st.markdown(
                f'<div style="background:#f8f7f4;border-radius:8px;padding:0.6rem 1rem;'
                f'font-size:13px;color:#555;margin-top:0.5rem;line-height:2;">'
                f'Par value: <b>${par:,.0f}</b>'
                f'&nbsp;&nbsp;|&nbsp;&nbsp;Current value: <b>${curr_val:,.0f}</b>'
                f'&nbsp;&nbsp;|&nbsp;&nbsp;P&L: <b style="color:{pnl_col};">{pnl_sign}${abs(pnl):,.0f}</b>'
                f'&nbsp;&nbsp;|&nbsp;&nbsp;Annual income: <b style="color:#15803d;">${ann_inc:,.0f}</b>'
                f'&nbsp;&nbsp;|&nbsp;&nbsp;Accrued interest: <b>${accrued:,.2f}</b>'
                f'</div>',
                unsafe_allow_html=True,
            )

    for i in sorted(bonds_to_delete, reverse=True):
        st.session_state.bond_rows.pop(i)
    if bonds_to_delete:
        st.rerun()

    if st.button("＋  Add bond"):
        st.session_state.bond_rows.append({
            "isin": "", "face_value": 1000.0, "quantity": 1,
            "coupon": 5.0, "maturity": date(date.today().year + 5, 1, 1),
            "purchase_date": date.today(), "purchase_price": 100.0, "current_price": 100.0,
        })
        st.rerun()

    # ── Build button ──────────────────────────────────────────────
    st.markdown("&nbsp;", unsafe_allow_html=True)
    if st.button("🔭  Build my portfolio map →", use_container_width=True):
        valid = [r for r in st.session_state.entry_rows
                 if len(r["isin"]) == 12 and r["current"] > 0]

        # Aggregate cash by currency
        cash_by_currency: dict[str, float] = {}
        for crow in st.session_state.cash_rows:
            cur = crow.get("currency", "USD")
            cash_by_currency[cur] = cash_by_currency.get(cur, 0.0) + crow.get("amount", 0.0)
        for currency, amount in cash_by_currency.items():
            if amount > 0:
                valid.append({
                    "isin": f"CASH_{currency}",
                    "current": amount, "paid": amount,
                    "date": date.today(),
                    "asset_type": "cash", "currency": currency,
                })

        # Bond holdings
        for brow in st.session_state.bond_rows:
            bisin = brow.get("isin", "").strip()
            if len(bisin) == 12 and brow.get("face_value", 0) > 0 and brow.get("quantity", 0) > 0:
                fv  = brow["face_value"]
                qty = brow["quantity"]
                valid.append({
                    "isin": bisin,
                    "current": fv * qty * (brow.get("current_price", 100.0) / 100),
                    "paid":    fv * qty * (brow.get("purchase_price", 100.0) / 100),
                    "date":    brow.get("purchase_date", date.today()),
                    "asset_type": "bond",
                    "face_value":  fv,
                    "quantity":    qty,
                    "coupon":      brow.get("coupon", 0.0),
                    "maturity":    brow.get("maturity", date.today()),
                    "current_price": brow.get("current_price", 100.0),
                })

        if not valid:
            st.error("Please enter at least one valid holding.")
        else:
            st.session_state.holdings = valid
            st.session_state.screen = "map"
            st.rerun()

# ══════════════════════════════════════════════════════════════════
# SCREEN 2 — MAP + PERFORMANCE
# ══════════════════════════════════════════════════════════════════
def screen_map():
    holdings = st.session_state.holdings
    if not holdings:
        st.session_state.screen = "entry"
        st.rerun()

    # Build info_map once per unique set of holdings; cache in session state
    # to avoid redundant API calls on every Streamlit rerender.
    holdings_key = tuple(h["isin"].upper() for h in holdings)
    if st.session_state.get("_info_map_key") != holdings_key:
        with st.spinner("Fetching portfolio data…"):
            st.session_state._info_map     = build_info_map(holdings)
            st.session_state._info_map_key = holdings_key
    info_map = st.session_state._info_map

    total_current = sum(h["current"] for h in holdings)
    total_paid    = sum(h["paid"]    for h in holdings)
    total_pnl     = total_current - total_paid
    total_pct     = (total_pnl / total_paid * 100) if total_paid > 0 else 0

    geo_agg, sector_agg = aggregate_portfolio(holdings, info_map)

    # ── nav ────────────────────────────────────────────────────────
    st.markdown('<div class="orion-logo">ORION / PORTFOLIO INTELLIGENCE</div>', unsafe_allow_html=True)
    if st.button("← Back to holdings"):
        st.session_state.screen = "entry"
        st.rerun()
    st.markdown("---")
    if "openfigi" in st.session_state.api_issues:
        st.warning(st.session_state.api_issues["openfigi"])

    # ── summary cards ──────────────────────────────────────────────
    s1, s2, s3, s4 = st.columns(4)
    pnl_sign  = "+" if total_pnl  >= 0 else ""
    pnl_class = "pos" if total_pnl >= 0 else "neg"
    pct_sign  = "+" if total_pct  >= 0 else ""

    for col, label, val in [
        (s1, "Total invested",   f"${total_paid:,.0f}"),
        (s2, "Current value",    f"${total_current:,.0f}"),
        (s3, "Total gain / loss",f"{pnl_sign}${abs(total_pnl):,.0f}"),
        (s4, "Holdings",         str(len(holdings))),
    ]:
        with col:
            st.metric(label, val)

    pnl_color = "#15803d" if total_pnl >= 0 else "#dc2626"
    st.markdown(f'<div style="text-align:center;font-size:13px;color:{pnl_color};margin:-0.5rem 0 1rem;">'
                f'{pct_sign}{total_pct:.1f}% total return</div>', unsafe_allow_html=True)

    # ── net worth breakdown by asset type ──────────────────────────
    equity_val = sum(h["current"] for h in holdings if h.get("asset_type", "stock_etf") == "stock_etf")
    bond_val   = sum(h["current"] for h in holdings if h.get("asset_type") == "bond")
    cash_val   = sum(h["current"] for h in holdings if h.get("asset_type") == "cash")
    equity_pct = equity_val / total_current * 100 if total_current else 0
    bond_pct   = bond_val   / total_current * 100 if total_current else 0
    cash_pct   = cash_val   / total_current * 100 if total_current else 0

    total_annual_income = sum(
        bond_annual_income(h["face_value"], h["quantity"], h["coupon"])
        for h in holdings if h.get("asset_type") == "bond"
    )
    total_accrued = sum(
        bond_accrued_interest(h["face_value"], h["quantity"], h["coupon"], h["maturity"])
        for h in holdings if h.get("asset_type") == "bond"
    )
    n_equities = sum(1 for h in holdings if h.get("asset_type", "stock_etf") == "stock_etf")
    n_bonds    = sum(1 for h in holdings if h.get("asset_type") == "bond")
    n_cash_cur = len({h.get("currency") for h in holdings if h.get("asset_type") == "cash"})

    nw_rows = []
    if equity_val > 0:
        nw_rows.append(("Equities", equity_val, equity_pct, "#378ADD",
                         f"{n_equities} holding{'s' if n_equities != 1 else ''}"))
    if bond_val > 0:
        inc_str = f" · ${total_annual_income:,.0f}/yr income" if total_annual_income else ""
        nw_rows.append(("Bonds", bond_val, bond_pct, "#1D9E75",
                         f"{n_bonds} bond{'s' if n_bonds != 1 else ''}{inc_str}"))
    if cash_val > 0:
        nw_rows.append(("Cash", cash_val, cash_pct, "#EF9F27",
                         f"{n_cash_cur} currency{'ies' if n_cash_cur != 1 else ''}"))

    if len(nw_rows) >= 1:
        st.markdown("#### Net worth by asset type")
        nw_left, nw_right = st.columns([1, 1.5])

        with nw_left:
            pie_labels = [r[0] for r in nw_rows]
            pie_values = [r[1] for r in nw_rows]
            pie_colors = [r[3] for r in nw_rows]

            def _fmt_center(n):
                if n >= 1_000_000:
                    return f"${n/1_000_000:.1f}M"
                return f"${n/1_000:.0f}k"

            fig_nw = go.Figure(go.Pie(
                labels=pie_labels,
                values=pie_values,
                hole=0.62,
                marker=dict(colors=pie_colors, line=dict(color="white", width=3)),
                textinfo="percent",
                textfont=dict(family="DM Sans", size=12, color="white"),
                hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
                direction="clockwise",
                sort=False,
            ))
            fig_nw.add_annotation(
                text=f"{_fmt_center(total_current)}<br>total",
                x=0.5, y=0.5, showarrow=False,
                font=dict(family="DM Mono", size=14, color="#1a1a1a"),
                align="center",
            )
            fig_nw.update_layout(
                height=210,
                showlegend=False,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="white",
            )
            st.plotly_chart(fig_nw, use_container_width=True)

        with nw_right:
            max_pct = max(r[2] for r in nw_rows)
            for label, val, pct, color, detail in nw_rows:
                bar_w = int(pct / max_pct * 100) if max_pct else 0
                st.markdown(
                    f'<div style="margin-bottom:0.9rem;">'
                    f'  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;">'
                    f'    <span style="font-size:13px;font-weight:500;color:#1a1a1a;">'
                    f'      <span style="display:inline-block;width:9px;height:9px;border-radius:50%;'
                    f'background:{color};margin-right:7px;vertical-align:middle;"></span>'
                    f'      {label}</span>'
                    f'    <span style="font-family:DM Mono,monospace;font-size:13px;">'
                    f'      ${val:,.0f}&nbsp;<span style="color:#aaa;font-size:12px;">{pct:.1f}%</span></span>'
                    f'  </div>'
                    f'  <div style="background:#e8e6e0;border-radius:4px;height:6px;margin-bottom:4px;">'
                    f'    <div style="background:{color};width:{bar_w}%;height:100%;border-radius:4px;"></div>'
                    f'  </div>'
                    f'  <div style="font-size:11px;color:#aaa;">{detail}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if bond_val > 0 and total_annual_income > 0:
                yoc = total_annual_income / bond_val * 100
                liq = cash_val / total_current * 100 if total_current else 0
                st.markdown(
                    f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;'
                    f'padding:0.5rem 0.85rem;font-size:12px;color:#15803d;margin-top:0.25rem;line-height:1.9;">'
                    f'Annual bond income&nbsp;<b>${total_annual_income:,.0f}</b>'
                    f'&nbsp;&nbsp;·&nbsp;&nbsp;Accrued&nbsp;<b>${total_accrued:,.2f}</b>'
                    f'&nbsp;&nbsp;·&nbsp;&nbsp;Yield on cost&nbsp;<b>{yoc:.2f}%</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if cash_val > 0:
                    st.markdown(
                        f'<div style="font-size:11px;color:#aaa;margin-top:6px;">'
                        f'Liquidity ratio (cash): {liq:.1f}% of portfolio</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown("---")

    # ── alerts + warnings ──────────────────────────────────────────
    if any(holding_is_etf(h["isin"].upper()) for h in holdings):
        st.markdown('<div class="alert-box">⚠ Overlap possible — your ETFs may contain stocks that also appear as direct holdings. Look-through analysis is applied below.</div>',
                    unsafe_allow_html=True)
    for w in compute_warnings(geo_agg, sector_agg):
        st.markdown(f'<div class="warn-box">⚠ {w}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── AI insights ───────────────────────────────────────────────

    st.markdown("---")

    with st.spinner("Generating AI insights…"):

        insights = generate_portfolio_insights(holdings, geo_agg, sector_agg, info_map)

    render_insights_card(insights)

    st.markdown("---")


    # ── TAB LAYOUT ─────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["Portfolio map", "World exposure", "Performance", "Holdings"])

    # ── TAB 1: TREEMAP ─────────────────────────────────────────────
    with tab1:

        # ── 1A: HOLDINGS TREEMAP ───────────────────────────────────
        st.markdown("### Holdings — look-through map")
        st.caption("ETFs are broken down by country (look-through). Direct equities show as one block (listed country). Click any ETF to drill in.")

        labels  = ["Portfolio"]
        parents = [""]
        values  = [total_current]
        colors  = ["#ffffff"]
        hovers  = [""]
        texts   = [""]

        for i, h in enumerate(holdings):
            isin    = h["isin"].upper()
            cur     = h["current"]
            paid    = h["paid"]
            pnl     = cur - paid
            pnl_p   = (pnl / paid * 100) if paid > 0 else 0
            port_p  = (cur / total_current * 100) if total_current > 0 else 0
            is_etf  = holding_is_etf(isin)
            is_bond = h.get("asset_type") == "bond"
            is_cash = h.get("asset_type") == "cash"
            info    = info_map.get(isin, {})
            name    = info.get("name", isin)
            color   = COLORS[i % len(COLORS)]
            pnl_str = f"+${pnl:,.0f} (+{pnl_p:.1f}%)" if pnl >= 0 else f"-${abs(pnl):,.0f} ({pnl_p:.1f}%)"
            badge   = ("Look-through" if is_etf else
                       "Bond" if is_bond else
                       "Cash" if is_cash else "Direct equity")

            labels.append(name)
            parents.append("Portfolio")
            values.append(cur)
            colors.append(color)
            hovers.append(
                f"<b>{name}</b><br>"
                f"{badge}<br>"
                f"ISIN: {isin}<br>"
                f"Value: ${cur:,.0f}<br>"
                f"Weight: {port_p:.1f}%<br>"
                f"P&L: {pnl_str}"
            )
            texts.append(f"<b>{name}</b><br>{port_p:.1f}% · {badge}")

            if is_etf and info and "geo" in info:
                # ETF: subdivide by country (look-through)
                geo       = info["geo"]
                total_geo = sum(geo.values())
                for country_code, country_pct in sorted(geo.items(), key=lambda x: -x[1]):
                    flag      = FLAGS.get(country_code, "")
                    cname     = COUNTRY_NAMES.get(country_code, country_code)
                    child_val = cur * (country_pct / total_geo)
                    true_pct  = child_val / total_current * 100
                    child_lbl = f"{flag} {cname}||{isin}"
                    labels.append(child_lbl)
                    parents.append(name)
                    values.append(child_val)
                    colors.append(color + "99")
                    hovers.append(
                        f"<b>{flag} {cname}</b><br>"
                        f"Inside: {name}<br>"
                        f"Fund allocation: {country_pct:.1f}%<br>"
                        f"True portfolio weight: {true_pct:.1f}%<br>"
                        f"Value: ${child_val:,.0f}"
                    )
                    texts.append(f"{flag} {cname}<br>{country_pct:.1f}%")
            else:
                # Direct equity: ONE sub-rectangle = listed country
                code, _ = max(info["geo"].items(), key=lambda x: x[1])
                flag  = FLAGS.get(code, "")
                cname = COUNTRY_NAMES.get(code, code)
                child_lbl = f"{flag} {cname} (listed)||{isin}"
                labels.append(child_lbl)
                parents.append(name)
                values.append(cur)
                colors.append(color + "99")
                detail = ("Bond" if is_bond else "Cash" if is_cash else "Direct equity")
                hovers.append(
                    f"<b>{flag} {cname}</b><br>"
                    f"{detail}: {name}<br>"
                    f"Value: ${cur:,.0f}"
                )
                texts.append(f"{flag} {cname}<br>{detail}")

        # clean display labels (strip the ||ISIN dedup suffix)
        display_labels = [l.split("||")[0] for l in labels]

        fig_tree = go.Figure(go.Treemap(
            labels=display_labels,
            ids=labels,
            parents=parents,
            values=values,
            customdata=hovers,
            text=texts,
            hovertemplate="%{customdata}<extra></extra>",
            texttemplate="%{text}",
            marker=dict(
                colors=colors,
                line=dict(width=3, color="white"),
                pad=dict(t=28, l=4, r=4, b=4),
            ),
            textfont=dict(family="DM Sans", size=11, color="white"),
            pathbar=dict(
                visible=True,
                thickness=28,
                textfont=dict(size=11, color="#444", family="DM Sans"),
                edgeshape=">",
            ),
            tiling=dict(packing="squarify", pad=3, squarifyratio=1),
            root_color="#f8f7f4",
            branchvalues="total",
        ))
        fig_tree.update_layout(
            height=520,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="white",
            uniformtext=dict(minsize=10, mode="hide"),
        )
        st.plotly_chart(fig_tree, use_container_width=True)

        # ── 1B: AGGREGATED EXPOSURE TREEMAP ────────────────────────
        st.markdown("### Aggregated exposure — true country weights")
        st.caption("All holdings combined after look-through. This is your real geographic exposure.")

        if geo_agg:
            agg_labels  = ["Your portfolio"]
            agg_parents = [""]
            agg_values  = [100]
            agg_colors  = ["#ffffff"]
            agg_hovers  = [""]
            agg_texts   = [""]

            sorted_geo = sorted(geo_agg.items(), key=lambda x: -x[1])
            color_scale = ["#0C447C","#185FA5","#378ADD","#85B7EB","#B5D4F4","#dbeafe","#eff6ff"]

            for j, (code, pct) in enumerate(sorted_geo):
                flag   = FLAGS.get(code, "")
                cname  = COUNTRY_NAMES.get(code, code)
                amount = total_current * pct / 100
                cidx   = min(j, len(color_scale) - 1)
                agg_labels.append(f"{flag} {cname}")
                agg_parents.append("Your portfolio")
                agg_values.append(pct)
                agg_colors.append(color_scale[cidx])
                agg_hovers.append(
                    f"<b>{flag} {cname}</b><br>"
                    f"True exposure: {pct:.1f}%<br>"
                    f"Value: ${amount:,.0f}"
                )
                agg_texts.append(f"<b>{flag} {cname}</b><br>{pct:.1f}%")

            fig_agg = go.Figure(go.Treemap(
                labels=agg_labels,
                parents=agg_parents,
                values=agg_values,
                customdata=agg_hovers,
                text=agg_texts,
                hovertemplate="%{customdata}<extra></extra>",
                texttemplate="%{text}",
                marker=dict(
                    colors=agg_colors,
                    line=dict(width=3, color="white"),
                    pad=dict(t=28, l=4, r=4, b=4),
                ),
                textfont=dict(family="DM Sans", size=12, color="white"),
                textposition="middle center",
                pathbar=dict(visible=False),
                tiling=dict(packing="squarify", pad=3, squarifyratio=1),
                root_color="#f8f7f4",
                branchvalues="total",
            ))
            fig_agg.update_layout(
                height=380,
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="white",
            )
            st.plotly_chart(fig_agg, use_container_width=True)

        # concentration alert
        country_sources = {}
        for h in holdings:
            isin = h["isin"].upper()
            info = info_map.get(isin, {})
            if info and "geo" in info:
                for c in info["geo"]:
                    country_sources.setdefault(c, []).append(info.get("name", isin))
            elif not holding_is_etf(isin):
                code = country_from_isin(isin)
                country_sources.setdefault(code, []).append(isin)
        concentrated = {c: s for c, s in country_sources.items() if len(s) >= 2 and c != "Other"}
        if concentrated:
            msgs = []
            for code, srcs in list(concentrated.items())[:3]:
                flag     = FLAGS.get(code, "")
                cname    = COUNTRY_NAMES.get(code, code)
                true_pct = round(geo_agg.get(code, 0), 1)
                msgs.append(f"{flag} {cname} across {len(srcs)} holdings — true exposure {true_pct}%")
            st.markdown(
                '<div class="alert-box">⚠ Hidden concentration: ' + " · ".join(msgs) + "</div>",
                unsafe_allow_html=True)

        # ── 1C: SECTOR PIE ─────────────────────────────────────────
        st.markdown("### Sector breakdown — after look-through")
        if sector_agg:
            sec_sorted = sorted(sector_agg.items(), key=lambda x: -x[1])
            sec_labels = [s[0] for s in sec_sorted]
            sec_values = [round(s[1], 1) for s in sec_sorted]

            fig_pie = go.Figure(go.Pie(
                labels=sec_labels,
                values=sec_values,
                hole=0.55,
                marker=dict(
                    colors=COLORS[:len(sec_labels)],
                    line=dict(color="white", width=3),
                ),
                textinfo="label+percent",
                textfont=dict(family="DM Sans", size=12),
                hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>",
                direction="clockwise",
                sort=True,
            ))
            fig_pie.update_layout(
                height=360,
                showlegend=False,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor="white",
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    # ── TAB 2: WORLD MAP ──────────────────────────────────────────
    with tab2:
        st.markdown("### Geographic exposure — after look-through")
        st.caption("Aggregated across all holdings including ETF internals. Hover any country for details.")

        if geo_agg:
            map_data = []
            for code, pct in geo_agg.items():
                iso3 = ISO3_MAP.get(code)
                if iso3:
                    name = COUNTRY_NAMES.get(code, code)
                    flag = FLAGS.get(code, "")
                    amount = total_current * pct / 100
                    map_data.append({
                        "iso3": iso3,
                        "country": f"{flag} {name}",
                        "pct": round(pct, 1),
                        "amount": round(amount)
                    })

            map_df = pd.DataFrame(map_data)

            fig_map = px.choropleth(
                map_df,
                locations="iso3",
                color="pct",
                hover_name="country",
                hover_data={"iso3": False, "pct": True, "amount": True},
                color_continuous_scale=["#E6F1FB", "#0C447C"],
                labels={"pct": "Exposure %", "amount": "Value ($)"},
            )
            fig_map.update_layout(
                height=440,
                geo=dict(
                    showframe=False,
                    showcoastlines=True,
                    coastlinecolor="#e0e0da",
                    showland=True,
                    landcolor="#f5f5f0",
                    showocean=True,
                    oceancolor="#f0f4f8",
                    projection_type="natural earth",
                ),
                coloraxis_colorbar=dict(title="Exposure %"),
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="white",
            )
            st.plotly_chart(fig_map, use_container_width=True)

            st.markdown("#### Country breakdown")
            sorted_geo = sorted(geo_agg.items(), key=lambda x: -x[1])
            max_pct = sorted_geo[0][1] if sorted_geo else 1
            for code, pct in sorted_geo:
                flag = FLAGS.get(code, "")
                name = COUNTRY_NAMES.get(code, code)
                amount = total_current * pct / 100
                bar_width = int(pct / max_pct * 100)
                col_name, col_bar, col_pct, col_amt = st.columns([2, 3, 0.8, 1.2])
                with col_name: st.markdown(f"{flag} {name}")
                with col_bar:
                    st.markdown(
                        f'<div style="background:#e8e6e0;border-radius:4px;height:8px;margin-top:10px;">'
                        f'<div style="background:#378ADD;width:{bar_width}%;height:100%;border-radius:4px;"></div></div>',
                        unsafe_allow_html=True)
                with col_pct: st.markdown(f"**{pct:.1f}%**")
                with col_amt: st.markdown(f"${amount:,.0f}")

    # ── TAB 3: PERFORMANCE ────────────────────────────────────────
    with tab3:
        st.markdown(
            '<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:0.75rem;">'
            '<span style="font-size:17px;font-weight:500;color:#1a1a1a;">Performance — by holding</span>'
            '<span style="font-size:12px;color:#aaa;">Gain / loss since purchase</span>'
            '</div>'
            '<div style="display:flex;align-items:center;padding:0 1.25rem 0.5rem;">'
            '<div style="flex:2.5;font-size:11px;color:#aaa;letter-spacing:0.07em;text-transform:uppercase;">Holding</div>'
            '<div style="flex:1.5;text-align:right;font-size:11px;color:#aaa;letter-spacing:0.07em;text-transform:uppercase;">% of Portfolio</div>'
            '<div style="flex:1;text-align:right;font-size:11px;color:#aaa;letter-spacing:0.07em;text-transform:uppercase;">Invested</div>'
            '<div style="flex:1;text-align:right;font-size:11px;color:#aaa;letter-spacing:0.07em;text-transform:uppercase;">Current</div>'
            '<div style="flex:1;text-align:right;font-size:11px;color:#aaa;letter-spacing:0.07em;text-transform:uppercase;">Gain / Loss $</div>'
            '<div style="flex:1;text-align:right;font-size:11px;color:#aaa;letter-spacing:0.07em;text-transform:uppercase;">Gain / Loss %</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        max_port_p = max(h["current"] for h in holdings) / total_current * 100

        for i, h in enumerate(holdings):
            isin      = h["isin"].upper()
            cur       = h["current"]
            paid      = h["paid"]
            pnl       = cur - paid
            pnl_p     = (pnl / paid * 100) if paid > 0 else 0
            port_p    = (cur / total_current * 100) if total_current > 0 else 0
            info      = info_map.get(isin, {})
            name      = info.get("name", isin)
            h_type    = h.get("asset_type", "stock_etf")
            kind      = ("ETF" if holding_is_etf(isin) else
                         "Bond" if h_type == "bond" else
                         "Cash" if h_type == "cash" else "Equity")
            color     = COLORS[i % len(COLORS)]
            bought_str = f"{h['date'].day} {h['date'].strftime('%b %Y')}" if h.get("date") else "—"
            days      = (date.today() - h["date"]).days if h.get("date") else None
            days_str  = f"{days:,} days held" if days is not None else "—"
            pnl_color = "#15803d" if pnl >= 0 else "#dc2626"
            pnl_sign  = "+" if pnl >= 0 else ""
            pnlp_sign = "+" if pnl_p >= 0 else ""
            bar_w     = round(port_p / max_port_p * 100)

            st.markdown(
                f'<div style="background:white;border:1px solid #e8e6e0;border-radius:12px;'
                f'padding:1rem 1.25rem;margin-bottom:0.5rem;display:flex;align-items:center;">'
                f'  <div style="flex:2.5;">'
                f'    <div style="font-size:15px;font-weight:500;color:#1a1a1a;margin-bottom:2px;">{name}</div>'
                f'    <div style="font-size:12px;color:#aaa;">{isin} · {kind}</div>'
                f'    <div style="font-size:12px;color:#aaa;">Bought {bought_str} · {days_str}</div>'
                f'  </div>'
                f'  <div style="flex:1.5;display:flex;flex-direction:column;align-items:flex-end;gap:5px;padding-right:1rem;">'
                f'    <span style="font-family:DM Mono,monospace;font-size:14px;font-weight:500;">{port_p:.1f}%</span>'
                f'    <div style="width:120px;background:#e8e6e0;border-radius:4px;height:6px;">'
                f'      <div style="width:{bar_w}%;background:{color};height:100%;border-radius:4px;"></div>'
                f'    </div>'
                f'  </div>'
                f'  <div style="flex:1;text-align:right;font-family:DM Mono,monospace;font-size:13px;color:#555;">${paid:,.0f}</div>'
                f'  <div style="flex:1;text-align:right;font-family:DM Mono,monospace;font-size:13px;color:#555;">${cur:,.0f}</div>'
                f'  <div style="flex:1;text-align:right;font-family:DM Mono,monospace;font-size:13px;font-weight:500;color:{pnl_color};">{pnl_sign}${abs(pnl):,.0f}</div>'
                f'  <div style="flex:1;text-align:right;font-family:DM Mono,monospace;font-size:13px;font-weight:500;color:{pnl_color};">{pnlp_sign}{pnl_p:.1f}%</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if h_type == "bond":
                ann_inc = bond_annual_income(h["face_value"], h["quantity"], h["coupon"])
                accrued = bond_accrued_interest(h["face_value"], h["quantity"], h["coupon"], h["maturity"])
                mat_str = h["maturity"].strftime("%-d %b %Y")
                st.markdown(
                    f'<div style="background:#f8f7f4;border-radius:8px;padding:0.5rem 1rem;'
                    f'margin-bottom:0.75rem;font-size:12px;color:#666;line-height:2;">'
                    f'Coupon: <b>{h["coupon"]:.2f}%</b>'
                    f'&nbsp;&nbsp;·&nbsp;&nbsp;Maturity: <b>{mat_str}</b>'
                    f'&nbsp;&nbsp;·&nbsp;&nbsp;Par: <b>${h["face_value"] * h["quantity"]:,.0f}</b>'
                    f'&nbsp;&nbsp;·&nbsp;&nbsp;Current price: <b>{h["current_price"]:.2f}%</b>'
                    f'&nbsp;&nbsp;·&nbsp;&nbsp;Annual income: <b style="color:#15803d;">${ann_inc:,.0f}</b>'
                    f'&nbsp;&nbsp;·&nbsp;&nbsp;Accrued interest: <b>${accrued:,.2f}</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("### Allocation — current weights")

        def _wrap_pie_label(text, max_chars=22):
            words = text.split()
            lines, current = [], ""
            for word in words:
                if current and len(current) + len(word) + 1 > max_chars:
                    lines.append(current)
                    current = word
                else:
                    current = (current + " " + word).strip()
            if current:
                lines.append(current)
            return "<br>".join(lines)

        donut_df = pd.DataFrame([{
            "name": _wrap_pie_label(info_map.get(h["isin"].upper(), {}).get("name", h["isin"].upper())),
            "value": h["current"]
        } for h in holdings])

        fig_donut = px.pie(
            donut_df, names="name", values="value",
            hole=0.6,
            color_discrete_sequence=COLORS,
        )
        fig_donut.update_traces(
            textposition="outside",
            textinfo="percent+label",
            automargin=True,
        )
        fig_donut.update_layout(
            height=420,
            showlegend=False,
            margin=dict(l=80, r=80, t=40, b=40),
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # ── TAB 4: HOLDINGS BREAKDOWN ─────────────────────────────────
    with tab4:
        st.markdown("### Holdings: name, country & sector")
        st.caption("Country from ISIN prefix · Sector from Financial Modeling Prep or Yahoo Finance · Edit or remove holdings inline")

        if "_editing_holding" not in st.session_state:
            st.session_state._editing_holding = None

        # Header row
        hcols = st.columns([3, 1.5, 1.8, 1.2, 0.9, 1.0, 1.0])
        for col, lbl in zip(hcols, ["Name / ISIN", "Country", "Sector", "Value ($)", "Weight", "", ""]):
            col.markdown(
                f'<div style="font-size:11px;color:#aaa;text-transform:uppercase;'
                f'letter-spacing:0.07em;padding-bottom:6px;border-bottom:2px solid #e8e6e0;">'
                f'{lbl}</div>',
                unsafe_allow_html=True,
            )

        for i, h in enumerate(holdings):
            isin   = h["isin"].upper()
            cur    = h["current"]
            paid   = h["paid"]
            port_p = (cur / total_current * 100) if total_current > 0 else 0
            h_type = h.get("asset_type", "stock_etf")

            info   = info_map.get(isin, {})
            name   = info.get("name", isin)
            geo    = info.get("geo") or {"Other": 100}
            secs   = info.get("sectors") or {"Other": 100}
            code   = max(geo.items(), key=lambda x: x[1])[0]
            flag   = FLAGS.get(code, "")
            cname  = COUNTRY_NAMES.get(code, code)
            sector = "ETF / Fund" if holding_is_etf(isin) else max(secs.items(), key=lambda x: x[1])[0]
            is_editing = st.session_state._editing_holding == i
            editable   = h_type == "stock_etf"

            rc0, rc1, rc2, rc3, rc4, rc5, rc6 = st.columns([3, 1.5, 1.8, 1.2, 0.9, 1.0, 1.0])
            with rc0:
                st.markdown(
                    f'<div style="font-size:14px;font-weight:500;color:#1a1a1a;padding-top:6px;">{name}</div>'
                    f'<div style="font-size:12px;color:#aaa;">{isin}</div>',
                    unsafe_allow_html=True,
                )
            with rc1:
                st.markdown(f'<div style="padding-top:8px;">{flag} {cname}</div>', unsafe_allow_html=True)
            with rc2:
                st.markdown(f'<div style="padding-top:8px;font-size:13px;">{sector}</div>', unsafe_allow_html=True)
            with rc3:
                st.markdown(f'<div style="padding-top:8px;font-family:DM Mono,monospace;">${cur:,.0f}</div>', unsafe_allow_html=True)
            with rc4:
                st.markdown(f'<div style="padding-top:8px;font-family:DM Mono,monospace;">{port_p:.1f}%</div>', unsafe_allow_html=True)
            with rc5:
                if editable:
                    edit_lbl = "Cancel" if is_editing else "Edit"
                    if st.button(edit_lbl, key=f"edit_h_{i}", use_container_width=True):
                        st.session_state._editing_holding = None if is_editing else i
                        st.rerun()
            with rc6:
                if st.button("Delete", key=f"del_h_{i}", use_container_width=True):
                    deleted = st.session_state.holdings.pop(i)
                    st.session_state.entry_rows = [r for r in st.session_state.entry_rows if r is not deleted]
                    st.session_state._editing_holding = None
                    if not st.session_state.holdings:
                        st.session_state.screen = "entry"
                    st.rerun()

            if editable and is_editing:
                with st.container(border=True):
                    st.markdown(f"**Editing: {name}**")
                    with st.form(key=f"edit_form_{i}"):
                        fc1, fc2, fc3 = st.columns(3)
                        with fc1:
                            new_cur = st.number_input(
                                "Current value ($)", value=float(cur),
                                min_value=0.0, step=1000.0, format="%.0f",
                            )
                        with fc2:
                            new_paid = st.number_input(
                                "Amount paid ($)", value=float(paid),
                                min_value=0.0, step=1000.0, format="%.0f",
                            )
                        with fc3:
                            new_date = st.date_input(
                                "Purchase date",
                                value=h.get("date", date.today()),
                                min_value=date(2000, 1, 1),
                            )
                        saved     = st.form_submit_button("Save", type="primary")
                        cancelled = st.form_submit_button("Cancel")

                    if saved:
                        h["current"] = new_cur
                        h["paid"]    = new_paid
                        h["date"]    = new_date
                        st.session_state._editing_holding = None
                        st.rerun()
                    if cancelled:
                        st.session_state._editing_holding = None
                        st.rerun()

            if h_type == "bond":
                ann_inc = bond_annual_income(h["face_value"], h["quantity"], h["coupon"])
                accrued = bond_accrued_interest(h["face_value"], h["quantity"], h["coupon"], h["maturity"])
                mat_str = h["maturity"].strftime("%-d %b %Y")
                st.markdown(
                    f'<div style="background:#f8f7f4;border-radius:6px;padding:0.4rem 1rem;'
                    f'margin:2px 0 4px;font-size:12px;color:#666;line-height:2;">'
                    f'Coupon <b>{h["coupon"]:.2f}%</b>'
                    f'&nbsp;·&nbsp; Maturity <b>{mat_str}</b>'
                    f'&nbsp;·&nbsp; Par <b>${h["face_value"] * h["quantity"]:,.0f}</b>'
                    f'&nbsp;·&nbsp; Current price <b>{h["current_price"]:.2f}%</b>'
                    f'&nbsp;·&nbsp; Annual income <b style="color:#15803d;">${ann_inc:,.0f}</b>'
                    f'&nbsp;·&nbsp; Accrued interest <b>${accrued:,.2f}</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<div style="border-top:1px solid #f0ede8;margin:4px 0 2px;"></div>', unsafe_allow_html=True)

        # ── What's inside each ETF ─────────────────────────────────
        etf_holdings = [(h, info_map[h["isin"].upper()])
                        for h in holdings if holding_is_etf(h["isin"].upper())]
        if etf_holdings:
            st.markdown("### What's inside each ETF")
            st.caption("Top holdings fetched live from Yahoo Finance")
            for h, info in etf_holdings:
                isin     = h["isin"].upper()
                name     = info["name"]
                top      = info.get("top_holdings", [])
                sectors  = info.get("sectors", {})
                cur      = h["current"]

                with st.expander(f"{name}  ·  ${cur:,.0f}"):
                    if top:
                        col_h, col_s = st.columns([3, 2])
                        with col_h:
                            st.markdown("**Top stock holdings**")
                            top_df = pd.DataFrame(top)
                            top_df.columns = ["Symbol", "Name", "Weight (%)"]
                            st.dataframe(
                                top_df.style.format({"Weight (%)": "{:.2f}%"}),
                                use_container_width=True,
                                hide_index=True,
                            )
                        with col_s:
                            st.markdown("**Sector breakdown**")
                            if sectors and sectors != {"Other": 100}:
                                sec_sorted = sorted(sectors.items(), key=lambda x: -x[1])
                                max_s = sec_sorted[0][1] if sec_sorted else 1
                                for sec, pct in sec_sorted:
                                    bar = int(pct / max_s * 100)
                                    c1, c2 = st.columns([3, 1])
                                    with c1:
                                        st.markdown(
                                            f'<div style="font-size:12px;margin-bottom:2px">{sec}</div>'
                                            f'<div style="background:#e8e6e0;border-radius:3px;height:6px;margin-bottom:6px">'
                                            f'<div style="background:#378ADD;width:{bar}%;height:100%;border-radius:3px"></div></div>',
                                            unsafe_allow_html=True)
                                    with c2:
                                        st.markdown(f'<div style="font-size:12px;padding-top:2px">{pct:.1f}%</div>',
                                                    unsafe_allow_html=True)
                            else:
                                st.info("Sector data not available")
                        st.caption(f"Source: Yahoo Finance · Top {len(top)} holdings shown")
                    else:
                        st.info("Holdings data not available from Yahoo Finance for this ETF.")

# ══════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════
if st.session_state.screen == "entry":
    screen_entry()
elif st.session_state.screen == "map":
    screen_map()
