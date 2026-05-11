import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import json
import os

st.set_page_config(
    page_title="Orion: Portfolio Intelligence",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .main { background-color: #f8f7f4; }
    .block-container { padding: 2rem 2rem 4rem; max-width: 960px; }
    h1 { font-size: 24px !important; font-weight: 500 !important; }
    h2 { font-size: 18px !important; font-weight: 500 !important; }
    h3 { font-size: 15px !important; font-weight: 500 !important; }
    .orion-logo { font-family: 'DM Mono', monospace; font-size: 11px; letter-spacing: 0.14em; color: #aaa; margin-bottom: 0.25rem; text-transform: uppercase; }
    .orion-headline { font-size: 26px; font-weight: 300; color: #1a1a1a; margin-bottom: 0.4rem; line-height: 1.3; }
    .orion-sub { font-size: 14px; color: #777; margin-bottom: 2rem; line-height: 1.6; }
    .hint-box { background: #f0f0ec; border-radius: 8px; padding: 0.75rem 1rem; font-size: 13px; color: #666; margin-bottom: 1.5rem; line-height: 1.6; }
    .instrument-found { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 5px 10px; font-size: 12px; color: #15803d; margin-top: 3px; }
    .instrument-error { background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 5px 10px; font-size: 12px; color: #dc2626; margin-top: 3px; }
    .alert-box { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #dc2626; margin-bottom: 1rem; }
    .warn-box { background: #fefce8; border: 1px solid #fde68a; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #92400e; margin-bottom: 1rem; }
    .stButton > button { background: #1a1a1a !important; color: white !important; border: none !important; border-radius: 9px !important; padding: 0.6rem 1.5rem !important; font-size: 14px !important; font-weight: 500 !important; font-family: 'DM Sans', sans-serif !important; width: 100%; }
    .stButton > button:hover { opacity: 0.85 !important; }
    div[data-testid="stMetric"] { background: white; border: 1px solid #e8e6e0; border-radius: 10px; padding: 1rem; }
    div[data-testid="stMetricLabel"] p { white-space: normal !important; word-break: break-word; }
    .stDataFrame { border-radius: 10px; overflow: hidden; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════
for k, v in [("holdings",[]),("screen","entry"),("isin_cache",{}),("api_issues",{})]:
    if k not in st.session_state:
        st.session_state[k] = v

def set_issue(svc, msg): st.session_state.api_issues[svc] = msg
def clr_issue(svc):      st.session_state.api_issues.pop(svc, None)

def get_cfg(name):
    try:
        v = st.secrets[name]
        if v: return str(v).strip()
    except Exception: pass
    return os.getenv(name, "").strip()

FMP_KEY = get_cfg("FMP_API_KEY")

# ══════════════════════════════════════════════════════════════════
# REFERENCE DATA
# ══════════════════════════════════════════════════════════════════
COUNTRY_MAP = {
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
ISO3 = {
    "US":"USA","JP":"JPN","GB":"GBR","FR":"FRA","CA":"CAN","CH":"CHE","DE":"DEU",
    "AU":"AUS","NL":"NLD","CN":"CHN","TW":"TWN","IN":"IND","KR":"KOR","BR":"BRA",
    "SA":"SAU","SE":"SWE","NO":"NOR","DK":"DNK","FI":"FIN","ES":"ESP","IT":"ITA",
    "PT":"PRT","BE":"BEL","AT":"AUT","IE":"IRL","LU":"LUX","SG":"SGP","HK":"HKG",
    "ZA":"ZAF","MX":"MEX","RU":"RUS","PL":"POL","CZ":"CZE","HU":"HUN","TR":"TUR",
    "IL":"ISR","AE":"ARE","QA":"QAT","TH":"THA","ID":"IDN","MY":"MYS","PH":"PHL",
    "VN":"VNM","CL":"CHL","CO":"COL","AR":"ARG","NZ":"NZL","GR":"GRC",
    "EU":None,"Other":None,
}
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
COLORS = ["#378ADD","#1D9E75","#EF9F27","#7F77DD","#D85A30","#5DCAA5","#D4537E","#639922"]
_ETF_TYPES = {"ETP","ETF","Open-End Fund","Exchange Traded Fund","UCITS","Fund","Mutual Fund"}
_ETF_KW    = ("ETF","UCITS","INDEX FUND","ISHARES","VANGUARD","SPDR","INVESCO","AMUNDI","LYXOR","XTRACKERS","WISDOMTREE")
EXCH_SUFFIX = {
    "LN":".L","NA":".AS","GR":".DE","FP":".PA","IM":".MI","SM":".MC",
    "SW":".SW","AU":".AX","SS":".ST","HE":".HE","CO":".CO","BB":".BR",
    "VX":".SW","TO":".TO","HK":".HK","JP":".T","TY":".T",
}
_WIKI_SECTORS = {
    "software":"Technology","semiconductor":"Technology","computer":"Technology",
    "internet":"Technology","electronics":"Technology","cloud":"Technology",
    "bank":"Financials","insurance":"Financials","financial":"Financials",
    "investment":"Financials","asset management":"Financials",
    "pharmaceutical":"Healthcare","biotechnology":"Healthcare","health":"Healthcare",
    "medical":"Healthcare","hospital":"Healthcare",
    "retail":"Consumer","apparel":"Consumer","luxury":"Consumer",
    "automobile":"Consumer","automotive":"Consumer","restaurant":"Consumer",
    "food":"Consumer Defensive","beverage":"Consumer Defensive",
    "supermarket":"Consumer Defensive","tobacco":"Consumer Defensive",
    "oil":"Energy","gas":"Energy","energy":"Energy","petroleum":"Energy",
    "mining":"Materials","chemical":"Materials","steel":"Materials","metal":"Materials",
    "aerospace":"Industrials","defence":"Industrials","defense":"Industrials",
    "logistics":"Industrials","manufacturing":"Industrials","industrial":"Industrials",
    "telecommunication":"Communication","telecom":"Communication",
    "media":"Communication","entertainment":"Communication",
    "real estate":"Real Estate","reit":"Real Estate",
    "utility":"Utilities","electric":"Utilities","water":"Utilities",
}

# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════
def country_from_isin(isin):
    c = isin[:2].upper()
    return c if c in COUNTRY_NAMES else "Other"

def holding_is_etf(isin):
    c = st.session_state.isin_cache.get(isin, {})
    if c.get("type","") in _ETF_TYPES: return True
    return any(kw in c.get("name","").upper() for kw in _ETF_KW)

def _is_domicile_only(geo, isin):
    domiciles = {"IE","LU","DE","FR","GB"}
    if len(geo) == 1:
        only = list(geo.keys())[0]
        if only in domiciles and only == isin[:2].upper():
            return True
    return False

def _pct(s):
    try: return float(str(s).replace("%","").strip())
    except: return 0.0

def _etf_tickers(all_listings):
    """
    From OpenFIGI all_listings, produce an ordered list of tickers to try.
    Returns [(ticker_with_suffix_or_raw, base_ticker)].
    Exchange-suffixed tickers come first (more likely to work with FMP/Yahoo).
    Then raw base tickers (for US-listed equivalents).
    """
    seen, out = set(), []
    # Pass 1: exchange-mapped suffix
    for ticker, exch in all_listings:
        sfx = EXCH_SUFFIX.get(exch, "")
        t = ticker + sfx if sfx else ticker
        if t not in seen:
            seen.add(t); out.append(t)
    # Pass 2: raw base tickers (catches US cross-listed)
    for ticker, _ in all_listings:
        if ticker not in seen:
            seen.add(ticker); out.append(ticker)
    return out

# ══════════════════════════════════════════════════════════════════
# API — OpenFIGI
# ══════════════════════════════════════════════════════════════════
def lookup_isin(isin):
    isin = isin.strip().upper()
    if not isin or len(isin) != 12: return None
    if isin in st.session_state.isin_cache:
        return st.session_state.isin_cache[isin]
    try:
        r = requests.post(
            "https://api.openfigi.com/v3/mapping",
            headers={"Content-Type":"application/json"},
            json=[{"idType":"ID_ISIN","idValue":isin}],
            timeout=5,
        )
        if r.status_code == 200:
            clr_issue("openfigi")
            data = r.json()
            if data and data[0].get("data"):
                item = data[0]["data"][0]
                seen, listings = set(), []
                for d in data[0]["data"]:
                    t = d.get("ticker","")
                    if t and t not in seen:
                        seen.add(t)
                        listings.append((t, d.get("exchCode","")))
                result = {
                    "name":         item.get("name", isin),
                    "type":         item.get("securityType","N/A"),
                    "exchange":     item.get("exchCode","N/A"),
                    "ticker":       item.get("ticker",""),
                    "all_listings": listings,
                }
                st.session_state.isin_cache[isin] = result
                return result
        elif r.status_code == 429:
            set_issue("openfigi","OpenFIGI rate limit reached. Please wait a minute.")
        else:
            set_issue("openfigi",f"OpenFIGI lookup failed (status {r.status_code}).")
    except Exception as e:
        set_issue("openfigi",f"OpenFIGI error: {e}")
    return None

# ══════════════════════════════════════════════════════════════════
# API — FMP
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=86400, show_spinner=False)
def _fmp_etf_country(ticker):
    if not FMP_KEY or not ticker: return {}
    try:
        r = requests.get(
            f"https://financialmodelingprep.com/api/v3/etf-country-weightings/{ticker}",
            params={"apikey":FMP_KEY}, timeout=8,
        )
        if r.status_code == 200:
            geo = {}
            for item in r.json():
                pct  = _pct(item.get("weightPercentage","0"))
                code = COUNTRY_MAP.get(item.get("country",""),"Other")
                geo[code] = geo.get(code,0) + pct
            return geo
        elif r.status_code in (401,403): set_issue("fmp","FMP API key rejected. Check FMP_API_KEY in secrets.")
        elif r.status_code == 429:       set_issue("fmp","FMP rate limit reached.")
    except Exception as e:
        set_issue("fmp",f"FMP error: {e}")
    return {}

@st.cache_data(ttl=86400, show_spinner=False)
def _fmp_etf_sector(ticker):
    if not FMP_KEY or not ticker: return {}
    try:
        r = requests.get(
            f"https://financialmodelingprep.com/api/v3/etf-sector-weightings/{ticker}",
            params={"apikey":FMP_KEY}, timeout=8,
        )
        if r.status_code == 200:
            sectors = {}
            for item in r.json():
                pct  = _pct(item.get("weightPercentage","0"))
                name = item.get("sector","Other")
                sectors[name] = sectors.get(name,0) + pct
            return sectors
    except Exception: pass
    return {}

@st.cache_data(ttl=86400, show_spinner=False)
def _fmp_etf_holders(ticker):
    """Individual stock holdings inside an ETF — the key UCITS look-through endpoint."""
    if not FMP_KEY or not ticker: return []
    try:
        r = requests.get(
            f"https://financialmodelingprep.com/api/v3/etf-holder/{ticker}",
            params={"apikey":FMP_KEY}, timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data,list) and data:
                holders = []
                for item in data:
                    sym = item.get("asset","")
                    pct = _pct(item.get("weightPercentage","0"))
                    if sym and pct > 0:
                        holders.append({"symbol":sym,"name":item.get("name",sym),"weight":round(pct,2)})
                return sorted(holders, key=lambda x:-x["weight"])
    except Exception: pass
    return []

@st.cache_data(ttl=86400, show_spinner=False)
def _fmp_stock_country(ticker):
    if not FMP_KEY or not ticker: return None
    try:
        r = requests.get(
            f"https://financialmodelingprep.com/api/v3/profile/{ticker}",
            params={"apikey":FMP_KEY}, timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data,list):
                mapped = COUNTRY_MAP.get(data[0].get("country",""))
                return mapped if mapped and mapped != "Other" else None
    except Exception: pass
    return None

@st.cache_data(ttl=86400, show_spinner=False)
def _fmp_stock_sector(ticker):
    if not FMP_KEY or not ticker: return "—"
    try:
        r = requests.get(
            f"https://financialmodelingprep.com/api/v3/profile/{ticker}",
            params={"apikey":FMP_KEY}, timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            if data and isinstance(data,list):
                return data[0].get("sector","—") or "—"
    except Exception: pass
    return "—"

# ══════════════════════════════════════════════════════════════════
# API — Yahoo Finance (secondary, works on local/some cloud envs)
# ══════════════════════════════════════════════════════════════════
_YAHOO_SECTOR_MAP = {
    "realestate":"Real Estate","consumer_cyclical":"Consumer",
    "basic_materials":"Materials","consumer_defensive":"Consumer Defensive",
    "technology":"Technology","communication_services":"Communication",
    "financial_services":"Financials","utilities":"Utilities",
    "industrials":"Industrials","energy":"Energy","healthcare":"Healthcare",
}
_ALL_YAHOO_SUFFIXES = [".L",".AS",".DE",".PA",".MI",".MC",".SW",".ST",".HE",".CO",".BR",".TO",".AX",""]

@st.cache_data(ttl=86400, show_spinner=False)
def _yahoo_top_holdings(ticker):
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}",
            params={"modules":"topHoldings"},
            headers={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            timeout=8,
        )
        if r.status_code != 200: return None
        result = r.json().get("quoteSummary",{}).get("result")
        if not result: return None
        top = result[0].get("topHoldings",{})
        if not top.get("holdings") and not top.get("sectorWeightings"): return None
        return top
    except Exception: return None

@st.cache_data(ttl=86400, show_spinner=False)
def _yahoo_stock_country(ticker):
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}",
            params={"modules":"assetProfile"},
            headers={"User-Agent":"Mozilla/5.0"}, timeout=5,
        )
        if r.status_code == 200:
            res = r.json().get("quoteSummary",{}).get("result")
            if res:
                c = res[0].get("assetProfile",{}).get("country","")
                return COUNTRY_MAP.get(c,"Other")
    except Exception: pass
    return "Other"

# ══════════════════════════════════════════════════════════════════
# API — Wikidata sector fallback
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=86400, show_spinner=False)
def _wikidata_sector(isin):
    q = f"""SELECT ?industryLabel WHERE {{
      ?company wdt:P946 "{isin}" . ?company wdt:P452 ?industry .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
    }} LIMIT 5"""
    try:
        r = requests.get("https://query.wikidata.org/sparql",
                         params={"query":q,"format":"json"},
                         headers={"User-Agent":"OrionPortfolioApp/1.0"}, timeout=8)
        if r.status_code == 200:
            for b in r.json().get("results",{}).get("bindings",[]):
                label = b.get("industryLabel",{}).get("value","").lower()
                for kw, sector in _WIKI_SECTORS.items():
                    if kw in label: return sector
    except Exception: pass
    return None

# ══════════════════════════════════════════════════════════════════
# CORE — ETF full look-through
# FMP is primary (reliable from Streamlit Cloud).
# Yahoo is secondary (works in local dev / some cloud envs).
# ══════════════════════════════════════════════════════════════════
def _fetch_etf_full(all_listings, isin):
    tickers = _etf_tickers(all_listings)

    # ── FMP pass ──────────────────────────────────────────────────
    for t in tickers:
        geo     = _fmp_etf_country(t)
        sectors = _fmp_etf_sector(t)
        holders = _fmp_etf_holders(t)

        if geo and not _is_domicile_only(geo, isin):
            clr_issue("fmp")
            return {"geo":geo, "sectors":sectors or {"Other":100}, "top_holdings":holders}

        # FMP returned holders but no country data — derive country from each stock
        if holders and not geo:
            derived = {}
            for h in holders[:25]:
                code = _fmp_stock_country(h["symbol"])
                if code:
                    derived[code] = derived.get(code,0) + h["weight"]
            if derived and not _is_domicile_only(derived, isin):
                clr_issue("fmp")
                return {"geo":derived, "sectors":sectors or {"Other":100}, "top_holdings":holders}

    # ── Yahoo pass (fallback for local / envs where Yahoo works) ──
    tried = set()
    for ticker, exch in all_listings:
        for sfx in ([EXCH_SUFFIX.get(exch,"")] if EXCH_SUFFIX.get(exch) else []) + _ALL_YAHOO_SUFFIXES:
            yt = ticker + sfx
            if yt in tried: continue
            tried.add(yt)
            top = _yahoo_top_holdings(yt)
            if not top: continue

            holdings_raw = top.get("holdings",[])
            country_exp  = top.get("countryExposure",[])
            sector_exp   = top.get("sectorWeightings",[])

            top_holdings = [
                {"symbol":h.get("symbol",""),"name":h.get("holdingName",h.get("symbol","")),"weight":round(float(h.get("holdingPercent",0))*100,2)}
                for h in holdings_raw if h.get("symbol") and float(h.get("holdingPercent",0))>0
            ]
            sectors = {}
            for sd in sector_exp:
                for key,val in sd.items():
                    label = _YAHOO_SECTOR_MAP.get(key, key.replace("_"," ").title())
                    sectors[label] = round(float(val)*100,2)

            geo = {}
            if country_exp:
                for c in country_exp:
                    pct  = round(float(c.get("exposure",0))*100,2)
                    code = COUNTRY_MAP.get(c.get("country",""),"Other")
                    geo[code] = geo.get(code,0)+pct
            elif top_holdings:
                for h in top_holdings:
                    code = _yahoo_stock_country(h["symbol"])
                    geo[code] = geo.get(code,0)+h["weight"]

            if geo and not _is_domicile_only(geo, isin):
                return {"geo":geo, "sectors":sectors or {"Other":100}, "top_holdings":top_holdings}

    return None  # complete failure

# ══════════════════════════════════════════════════════════════════
# CORE — single stock info
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=86400, show_spinner=False)
def _stock_info(ticker, exch_code, isin):
    out = {"sector":"—","country":None}
    if not ticker: return out

    if FMP_KEY:
        try:
            r = requests.get(f"https://financialmodelingprep.com/api/v3/profile/{ticker}",
                             params={"apikey":FMP_KEY}, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data,list):
                    s = data[0].get("sector","")
                    c = COUNTRY_MAP.get(data[0].get("country",""))
                    if s: out["sector"] = s
                    if c and c!="Other": out["country"] = c
                    if out["sector"]!="—" and out["country"]: return out
        except Exception: pass

    sfx = EXCH_SUFFIX.get(exch_code,"")
    for yt in ([ticker+sfx] if sfx else []) + [ticker]:
        try:
            r = requests.get(f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{yt}",
                             params={"modules":"assetProfile"},
                             headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
            if r.status_code == 200:
                res = r.json().get("quoteSummary",{}).get("result")
                if res:
                    p = res[0].get("assetProfile",{})
                    if p.get("sector") and out["sector"]=="—": out["sector"] = p["sector"]
                    if not out["country"]:
                        c = COUNTRY_MAP.get(p.get("country",""))
                        if c and c!="Other": out["country"] = c
                    if out["sector"]!="—" and out["country"]: return out
        except Exception: continue
    return out

# ══════════════════════════════════════════════════════════════════
# CORE — get_holding_info (main entry point)
# ══════════════════════════════════════════════════════════════════
def get_holding_info(isin):
    cached   = st.session_state.isin_cache.get(isin,{})
    name     = cached.get("name", isin)
    listings = cached.get("all_listings") or (
        [(cached["ticker"], cached.get("exchange",""))] if cached.get("ticker") else []
    )

    if holding_is_etf(isin):
        result = _fetch_etf_full(listings, isin)
        if result:
            return {"name":name, **result}
        return {"name":name, "geo":{}, "sectors":{}, "top_holdings":[]}
    else:
        ticker = cached.get("ticker","")
        exch   = cached.get("exchange","")
        info   = _stock_info(ticker, exch, isin) if ticker else {"sector":"—","country":None}
        sector = info["sector"]
        code   = info["country"] or country_from_isin(isin)
        if sector == "—":
            sector = _wikidata_sector(isin) or "—"
        return {"name":name, "geo":{code:100}, "sectors":{sector:100}, "top_holdings":[]}

# ══════════════════════════════════════════════════════════════════
# AGGREGATION
# ══════════════════════════════════════════════════════════════════
def aggregate_portfolio(holdings, info_map):
    total = sum(h["current"] for h in holdings)
    if not total: return {}, {}
    geo_agg, sec_agg = {}, {}
    for h in holdings:
        w   = h["current"] / total
        src = info_map.get(h["isin"].upper(), {})
        for c, pct in src.get("geo",{}).items():
            geo_agg[c] = geo_agg.get(c,0) + pct*w
        for s, pct in src.get("sectors",{}).items():
            sec_agg[s] = sec_agg.get(s,0) + pct*w
    return geo_agg, sec_agg

# ══════════════════════════════════════════════════════════════════
# SCREEN 1 — ENTRY
# ══════════════════════════════════════════════════════════════════
def screen_entry():
    st.markdown('<div class="orion-logo">ORION / PORTFOLIO INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="orion-headline">Enter your holdings</div>', unsafe_allow_html=True)
    st.markdown('<div class="orion-sub">Find your ISIN on any broker statement — UBS, Baraka, eToro, IBKR. Enter the current value and purchase details.</div>', unsafe_allow_html=True)
    st.markdown('<div class="hint-box">💡 Your ISIN is a 12-character code on every broker statement — e.g. <b>IE00B4L5Y983</b> for iShares MSCI World. We look it up automatically.</div>', unsafe_allow_html=True)

    if not FMP_KEY:
        st.error("⚠ FMP_API_KEY not found. ETF look-through (seeing what's inside each fund) requires FMP. "
                 "Get a free key at financialmodelingprep.com and add it to Streamlit secrets as FMP_API_KEY.")
    for svc in ["fmp","openfigi"]:
        if svc in st.session_state.api_issues:
            st.warning(st.session_state.api_issues[svc])

    if "entry_rows" not in st.session_state:
        st.session_state.entry_rows = [
            {"isin":"IE00B4L5Y983","current":90000.0,"date":date(2022,3,15),"paid":71000.0},
            {"isin":"US0378331005","current":52000.0,"date":date(2021,6,10),"paid":38000.0},
            {"isin":"SA14TG012N13","current":45000.0,"date":date(2023,1,20),"paid":39000.0},
            {"isin":"US5949181045","current":38000.0,"date":date(2022,9,5), "paid":28500.0},
            {"isin":"IE00BKM4GZ66","current":22500.0,"date":date(2023,7,12),"paid":20000.0},
        ]

    c_isin,c_cur,c_date,c_paid,c_del = st.columns([2.2,1.3,1.3,1.3,0.4])
    with c_isin: st.markdown("**ISIN**")
    with c_cur:  st.markdown("**Current value ($)**")
    with c_date: st.markdown("**Purchase date**")
    with c_paid: st.markdown("**Amount paid ($)**")
    with c_del:  st.markdown("&nbsp;", unsafe_allow_html=True)

    to_del = []
    for i, row in enumerate(st.session_state.entry_rows):
        c1,c2,c3,c4,c5 = st.columns([2.2,1.3,1.3,1.3,0.4])
        with c1:
            isin = st.text_input("ISIN",value=row["isin"],key=f"isin_{i}",
                                  label_visibility="collapsed",placeholder="e.g. IE00B4L5Y983",
                                  max_chars=12).upper().strip()
            st.session_state.entry_rows[i]["isin"] = isin
            if len(isin)==12:
                info = lookup_isin(isin)
                if info:
                    st.markdown(f'<div class="instrument-found">✓ {info["name"]} · {info["type"]}</div>',unsafe_allow_html=True)
                else:
                    st.markdown('<div class="instrument-error">ISIN not recognised</div>',unsafe_allow_html=True)
        with c2:
            st.session_state.entry_rows[i]["current"] = st.number_input(
                "Cur",value=float(row["current"]),min_value=0.0,step=1000.0,
                key=f"cur_{i}",label_visibility="collapsed",format="%.0f")
        with c3:
            st.session_state.entry_rows[i]["date"] = st.date_input(
                "Date",value=row["date"],key=f"date_{i}",
                label_visibility="collapsed",min_value=date(2000,1,1))
        with c4:
            st.session_state.entry_rows[i]["paid"] = st.number_input(
                "Paid",value=float(row["paid"]),min_value=0.0,step=1000.0,
                key=f"paid_{i}",label_visibility="collapsed",format="%.0f")
        with c5:
            if st.button("✕",key=f"del_{i}"): to_del.append(i)

    for i in sorted(to_del,reverse=True):
        st.session_state.entry_rows.pop(i)
    if to_del: st.rerun()

    st.markdown("&nbsp;",unsafe_allow_html=True)
    ca,cb = st.columns([1,3])
    with ca:
        if st.button("＋  Add holding"):
            st.session_state.entry_rows.append({"isin":"","current":0.0,"date":date.today(),"paid":0.0})
            st.rerun()
    with cb:
        if st.button("🔭  Build my portfolio map →"):
            valid = [r for r in st.session_state.entry_rows if len(r["isin"])==12 and r["current"]>0]
            if not valid: st.error("Please enter at least one valid holding.")
            else:
                st.session_state.holdings = valid
                st.session_state.screen   = "map"
                st.rerun()

# ══════════════════════════════════════════════════════════════════
# SCREEN 2 — MAP
# ══════════════════════════════════════════════════════════════════
def screen_map():
    holdings = st.session_state.holdings
    if not holdings: st.session_state.screen="entry"; st.rerun()

    info_map = {h["isin"].upper(): get_holding_info(h["isin"].upper()) for h in holdings}

    total_cur  = sum(h["current"] for h in holdings)
    total_paid = sum(h["paid"]    for h in holdings)
    total_pnl  = total_cur - total_paid
    total_pct  = (total_pnl / total_paid * 100) if total_paid else 0
    geo_agg, sec_agg = aggregate_portfolio(holdings, info_map)

    st.markdown('<div class="orion-logo">ORION / PORTFOLIO INTELLIGENCE</div>',unsafe_allow_html=True)
    if st.button("← Back to holdings"):
        st.session_state.screen="entry"; st.rerun()
    st.markdown("---")

    for svc in ["fmp","openfigi"]:
        if svc in st.session_state.api_issues:
            st.warning(st.session_state.api_issues[svc])

    failed = [info_map[h["isin"].upper()]["name"]
              for h in holdings
              if holding_is_etf(h["isin"].upper()) and not info_map[h["isin"].upper()].get("geo")]
    if failed:
        st.markdown(
            f'<div class="warn-box">⚠ ETF look-through failed for: <b>{", ".join(failed)}</b>. '
            f'Ensure <b>FMP_API_KEY</b> is set in Streamlit secrets and the key is valid.</div>',
            unsafe_allow_html=True)

    # Summary cards
    s1,s2,s3,s4 = st.columns(4)
    sg = lambda v: "+" if v>=0 else ""
    for col,lbl,val in [
        (s1,"Total invested",f"${total_paid:,.0f}"),
        (s2,"Current value",f"${total_cur:,.0f}"),
        (s3,"Gain / loss",f"{sg(total_pnl)}${abs(total_pnl):,.0f}"),
        (s4,"Holdings",str(len(holdings))),
    ]: col.metric(lbl,val)

    clr = "#15803d" if total_pnl>=0 else "#dc2626"
    st.markdown(f'<div style="text-align:center;font-size:13px;color:{clr};margin:-0.5rem 0 1rem;">'
                f'{sg(total_pct)}{total_pct:.1f}% total return</div>',unsafe_allow_html=True)

    if any(holding_is_etf(h["isin"].upper()) for h in holdings):
        st.markdown('<div class="alert-box">⚠ Overlap possible — ETFs may contain stocks that also appear as direct holdings. Look-through analysis is applied below.</div>',unsafe_allow_html=True)

    st.markdown("---")
    tab1,tab2,tab3,tab4 = st.tabs(["Portfolio map","World exposure","Performance","Holdings"])

    # ──────────────────────────────────────────────────────────────
    # TAB 1 — TREEMAP
    # ──────────────────────────────────────────────────────────────
    with tab1:
        st.markdown("### Holdings — look-through map")
        st.caption("ETFs show real country breakdown inside each block (via FMP look-through). Direct equities show listed country.")

        labels,parents,values,colors,hovers,texts = ["Portfolio"],[""], [total_cur],["#ffffff"],[""],[""]

        for i,h in enumerate(holdings):
            isin   = h["isin"].upper()
            cur    = h["current"]; paid=h["paid"]
            pnl    = cur-paid; pnl_p=(pnl/paid*100) if paid else 0
            port_p = (cur/total_cur*100) if total_cur else 0
            is_etf = holding_is_etf(isin)
            info   = info_map.get(isin,{})
            name   = info.get("name",isin)
            color  = COLORS[i % len(COLORS)]
            pnl_s  = f"+${pnl:,.0f} (+{pnl_p:.1f}%)" if pnl>=0 else f"-${abs(pnl):,.0f} ({pnl_p:.1f}%)"

            labels.append(name); parents.append("Portfolio"); values.append(cur)
            colors.append(color)
            hovers.append(f"<b>{name}</b><br>{'ETF look-through' if is_etf else 'Direct equity'}<br>"
                          f"ISIN: {isin}<br>Value: ${cur:,.0f}<br>Weight: {port_p:.1f}%<br>P&L: {pnl_s}")
            texts.append(f"<b>{name}</b><br>{port_p:.1f}%")

            geo = info.get("geo",{})
            has_real = geo and not _is_domicile_only(geo,isin)

            if is_etf and has_real:
                total_g = sum(geo.values()) or 1
                for code,pct in sorted(geo.items(),key=lambda x:-x[1]):
                    flag=FLAGS.get(code,""); cname=COUNTRY_NAMES.get(code,code)
                    cval=cur*(pct/total_g); tpct=cval/total_cur*100
                    lbl=f"{flag} {cname}||{isin}"
                    labels.append(lbl); parents.append(name); values.append(cval)
                    colors.append(color+"99")
                    hovers.append(f"<b>{flag} {cname}</b><br>Inside: {name}<br>"
                                  f"Fund allocation: {pct:.1f}%<br>True portfolio weight: {tpct:.1f}%<br>Value: ${cval:,.0f}")
                    texts.append(f"{flag} {cname}<br>{pct:.1f}%")

            elif is_etf and not geo:
                lbl=f"⚠ No data||{isin}"
                labels.append(lbl); parents.append(name); values.append(cur)
                colors.append(color+"44")
                hovers.append(f"<b>{name}</b><br>Look-through unavailable<br>Check FMP_API_KEY")
                texts.append("⚠ No data")

            else:
                code=max(geo.items(),key=lambda x:x[1])[0] if geo else country_from_isin(isin)
                flag=FLAGS.get(code,""); cname=COUNTRY_NAMES.get(code,code)
                lbl=f"{flag} {cname} (listed)||{isin}"
                labels.append(lbl); parents.append(name); values.append(cur)
                colors.append(color+"99")
                hovers.append(f"<b>{flag} {cname}</b><br>Listed: {name}<br>Direct equity<br>Value: ${cur:,.0f}")
                texts.append(f"{flag} {cname}<br>Listed")

        display=[l.split("||")[0] for l in labels]
        fig=go.Figure(go.Treemap(
            labels=display,ids=labels,parents=parents,values=values,
            customdata=hovers,text=texts,
            hovertemplate="%{customdata}<extra></extra>",texttemplate="%{text}",
            marker=dict(colors=colors,line=dict(width=3,color="white"),pad=dict(t=28,l=4,r=4,b=4)),
            textfont=dict(family="DM Sans",size=11,color="white"),
            pathbar=dict(visible=True,thickness=28,textfont=dict(size=11,color="#444",family="DM Sans"),edgeshape=">"),
            tiling=dict(packing="squarify",pad=3,squarifyratio=1),root_color="#f8f7f4",branchvalues="total",
        ))
        fig.update_layout(height=520,margin=dict(l=0,r=0,t=0,b=0),paper_bgcolor="white",uniformtext=dict(minsize=10,mode="hide"))
        st.plotly_chart(fig,use_container_width=True)

        # Aggregated true country treemap
        st.markdown("### Aggregated exposure — true country weights")
        st.caption("All holdings combined after look-through. Your real geographic exposure.")
        if geo_agg:
            cs=["#0C447C","#185FA5","#378ADD","#85B7EB","#B5D4F4","#dbeafe","#eff6ff"]
            al,ap,av,ac,ah,at2=(["Your portfolio"],[""], [100],["#ffffff"],[""],[""])
            for j,(code,pct) in enumerate(sorted(geo_agg.items(),key=lambda x:-x[1])):
                flag=FLAGS.get(code,""); cname=COUNTRY_NAMES.get(code,code); amt=total_cur*pct/100
                al.append(f"{flag} {cname}"); ap.append("Your portfolio")
                av.append(pct); ac.append(cs[min(j,len(cs)-1)])
                ah.append(f"<b>{flag} {cname}</b><br>True exposure: {pct:.1f}%<br>Value: ${amt:,.0f}")
                at2.append(f"<b>{flag} {cname}</b><br>{pct:.1f}%")
            fig2=go.Figure(go.Treemap(
                labels=al,parents=ap,values=av,customdata=ah,text=at2,
                hovertemplate="%{customdata}<extra></extra>",texttemplate="%{text}",
                marker=dict(colors=ac,line=dict(width=3,color="white"),pad=dict(t=28,l=4,r=4,b=4)),
                textfont=dict(family="DM Sans",size=12,color="white"),textposition="middle center",
                pathbar=dict(visible=False),tiling=dict(packing="squarify",pad=3,squarifyratio=1),
                root_color="#f8f7f4",branchvalues="total",
            ))
            fig2.update_layout(height=380,margin=dict(l=0,r=0,t=0,b=0),paper_bgcolor="white")
            st.plotly_chart(fig2,use_container_width=True)

        # Concentration alerts
        csrc={}
        for h in holdings:
            isin=h["isin"].upper()
            for c in info_map.get(isin,{}).get("geo",{}):
                csrc.setdefault(c,[]).append(info_map[isin].get("name",isin))
        for code,srcs in {c:s for c,s in csrc.items() if len(s)>=2 and c!="Other"}.items():
            flag=FLAGS.get(code,""); cname=COUNTRY_NAMES.get(code,code)
            st.markdown(f'<div class="alert-box">⚠ Hidden concentration: {flag} {cname} across {len(srcs)} holdings — true exposure {round(geo_agg.get(code,0),1)}%</div>',unsafe_allow_html=True)

        # Sector pie
        st.markdown("### Sector breakdown — after look-through")
        if sec_agg:
            ss=sorted(sec_agg.items(),key=lambda x:-x[1])
            fig3=go.Figure(go.Pie(
                labels=[s[0] for s in ss],values=[round(s[1],1) for s in ss],hole=0.55,
                marker=dict(colors=COLORS[:len(ss)],line=dict(color="white",width=3)),
                textinfo="label+percent",textfont=dict(family="DM Sans",size=12),
                hovertemplate="<b>%{label}</b><br>%{value:.1f}%<extra></extra>",
                direction="clockwise",sort=True,
            ))
            fig3.update_layout(height=360,showlegend=False,margin=dict(l=20,r=20,t=20,b=20),paper_bgcolor="white")
            st.plotly_chart(fig3,use_container_width=True)

    # ──────────────────────────────────────────────────────────────
    # TAB 2 — WORLD MAP
    # ──────────────────────────────────────────────────────────────
    with tab2:
        st.markdown("### Geographic exposure — after look-through")
        st.caption("Aggregated across all holdings including ETF internals.")
        if geo_agg:
            mdata=[{"iso3":ISO3[c],"country":f"{FLAGS.get(c,'')} {COUNTRY_NAMES.get(c,c)}",
                    "pct":round(pct,1),"amount":round(total_cur*pct/100)}
                   for c,pct in geo_agg.items() if ISO3.get(c)]
            figm=px.choropleth(
                pd.DataFrame(mdata),locations="iso3",color="pct",hover_name="country",
                hover_data={"iso3":False,"pct":True,"amount":True},
                color_continuous_scale=["#E6F1FB","#0C447C"],
                labels={"pct":"Exposure %","amount":"Value ($)"},
            )
            figm.update_layout(
                height=440,
                geo=dict(showframe=False,showcoastlines=True,coastlinecolor="#e0e0da",
                         showland=True,landcolor="#f5f5f0",showocean=True,oceancolor="#f0f4f8",
                         projection_type="natural earth"),
                coloraxis_colorbar=dict(title="Exposure %"),
                margin=dict(l=0,r=0,t=0,b=0),paper_bgcolor="white",
            )
            st.plotly_chart(figm,use_container_width=True)
            st.markdown("#### Country breakdown")
            sg2=sorted(geo_agg.items(),key=lambda x:-x[1]); mx=sg2[0][1] if sg2 else 1
            for code,pct in sg2:
                flag=FLAGS.get(code,""); cname=COUNTRY_NAMES.get(code,code)
                amt=total_cur*pct/100; bar=int(pct/mx*100)
                c1,c2,c3,c4=st.columns([2,3,0.8,1.2])
                with c1: st.markdown(f"{flag} {cname}")
                with c2: st.markdown(f'<div style="background:#e8e6e0;border-radius:4px;height:8px;margin-top:10px;"><div style="background:#378ADD;width:{bar}%;height:100%;border-radius:4px;"></div></div>',unsafe_allow_html=True)
                with c3: st.markdown(f"**{pct:.1f}%**")
                with c4: st.markdown(f"${amt:,.0f}")

    # ──────────────────────────────────────────────────────────────
    # TAB 3 — PERFORMANCE
    # ──────────────────────────────────────────────────────────────
    with tab3:
        st.markdown("### Performance — by holding")
        rows=[]
        for h in holdings:
            isin=h["isin"].upper(); cur=h["current"]; paid=h["paid"]
            pnl=cur-paid; pnl_p=(pnl/paid*100) if paid else 0
            port_p=(cur/total_cur*100) if total_cur else 0
            info=info_map.get(isin,{}); days=(date.today()-h["date"]).days if h.get("date") else "—"
            rows.append({"Holding":info.get("name",isin),"ISIN":isin,"Days held":days,
                         "% of portfolio":round(port_p,1),"Invested ($)":round(paid),
                         "Current ($)":round(cur),"Gain/Loss ($)":round(pnl),"Gain/Loss (%)":round(pnl_p,1)})
        def cpnl(v):
            if isinstance(v,(int,float)): return f"color:{'#15803d' if v>=0 else '#dc2626'};font-weight:500"
            return ""
        st.dataframe(
            pd.DataFrame(rows).style.map(cpnl,subset=["Gain/Loss ($)","Gain/Loss (%)"]).format({
                "Invested ($)":"${:,.0f}","Current ($)":"${:,.0f}",
                "Gain/Loss ($)":lambda v:f"+${v:,.0f}" if v>=0 else f"-${abs(v):,.0f}",
                "Gain/Loss (%)":lambda v:f"+{v:.1f}%" if v>=0 else f"{v:.1f}%",
                "% of portfolio":"{:.1f}%",
            }),use_container_width=True,hide_index=True)

        st.markdown("### Allocation — current weights")
        def wrap(t,n=22):
            words=t.split(); lines,cur2=[],""
            for w in words:
                if cur2 and len(cur2)+len(w)+1>n: lines.append(cur2); cur2=w
                else: cur2=(cur2+" "+w).strip()
            if cur2: lines.append(cur2)
            return "<br>".join(lines)
        donut=pd.DataFrame([{"name":wrap(info_map.get(h["isin"].upper(),{}).get("name",h["isin"].upper())),"value":h["current"]} for h in holdings])
        fig4=px.pie(donut,names="name",values="value",hole=0.6,color_discrete_sequence=COLORS)
        fig4.update_traces(textposition="outside",textinfo="percent+label",automargin=True)
        fig4.update_layout(height=420,showlegend=False,margin=dict(l=80,r=80,t=40,b=40),paper_bgcolor="white")
        st.plotly_chart(fig4,use_container_width=True)

    # ──────────────────────────────────────────────────────────────
    # TAB 4 — HOLDINGS TABLE + ETF DRILL-DOWN
    # ──────────────────────────────────────────────────────────────
    with tab4:
        st.markdown("### Holdings: name, country & sector")
        trows=[]
        for h in holdings:
            isin=h["isin"].upper(); cur=h["current"]; port_p=(cur/total_cur*100) if total_cur else 0
            info=info_map.get(isin,{}); geo=info.get("geo",{})
            code=max(geo.items(),key=lambda x:x[1])[0] if geo else country_from_isin(isin)
            sector="ETF / Fund" if holding_is_etf(isin) else max(info.get("sectors",{"—":1}).items(),key=lambda x:x[1])[0]
            trows.append({"Name":info.get("name",isin),"ISIN":isin,
                          "Country":f"{FLAGS.get(code,'')} {COUNTRY_NAMES.get(code,code)}",
                          "Sector":sector,"Value ($)":round(cur),"Weight":round(port_p,1)})
        st.dataframe(pd.DataFrame(trows).style.format({"Value ($)":"${:,.0f}","Weight":"{:.1f}%"}),
                     use_container_width=True,hide_index=True)

        etfs=[(h,info_map[h["isin"].upper()]) for h in holdings if holding_is_etf(h["isin"].upper())]
        if etfs:
            st.markdown("### What's inside each ETF")
            st.caption("Individual holdings and geographic breakdown via FMP — UCITS look-through applied")
            for h,info in etfs:
                isin=h["isin"].upper(); name=info.get("name",isin)
                top=info.get("top_holdings",[]); sectors=info.get("sectors",{})
                geo=info.get("geo",{}); cur=h["current"]
                has_real=geo and not _is_domicile_only(geo,isin)
                with st.expander(f"{name}  ·  ${cur:,.0f}"):
                    if not has_real:
                        st.warning("Look-through unavailable. Ensure FMP_API_KEY is set correctly in Streamlit secrets.")
                    if top:
                        col_h,col_s=st.columns([3,2])
                        with col_h:
                            st.markdown("**Top stock holdings**")
                            df_top=pd.DataFrame(top); df_top.columns=["Symbol","Name","Weight (%)"]
                            st.dataframe(df_top.style.format({"Weight (%)":"{:.2f}%"}),
                                         use_container_width=True,hide_index=True)
                        with col_s:
                            st.markdown("**Sector breakdown**")
                            if sectors and sectors!={"Other":100}:
                                ss2=sorted(sectors.items(),key=lambda x:-x[1]); mx2=ss2[0][1] if ss2 else 1
                                for sec,pct in ss2:
                                    bar=int(pct/mx2*100)
                                    c1,c2=st.columns([3,1])
                                    with c1: st.markdown(f'<div style="font-size:12px;margin-bottom:2px">{sec}</div><div style="background:#e8e6e0;border-radius:3px;height:6px;margin-bottom:6px"><div style="background:#378ADD;width:{bar}%;height:100%;border-radius:3px"></div></div>',unsafe_allow_html=True)
                                    with c2: st.markdown(f'<div style="font-size:12px;padding-top:2px">{pct:.1f}%</div>',unsafe_allow_html=True)
                            else:
                                st.info("Sector data not available")
                        st.caption(f"Source: FMP · {len(top)} holdings shown")
                    elif has_real:
                        st.info("Individual holdings not available but geographic breakdown shown below.")
                    else:
                        st.info("No data. Add FMP_API_KEY to Streamlit secrets.")

                    if has_real:
                        st.markdown("**Geographic breakdown (look-through)**")
                        gs=sorted(geo.items(),key=lambda x:-x[1]); mg=gs[0][1] if gs else 1
                        for code,pct in gs[:15]:
                            flag=FLAGS.get(code,""); cname=COUNTRY_NAMES.get(code,code); bar=int(pct/mg*100)
                            c1,c2,c3=st.columns([2,3,1])
                            with c1: st.markdown(f'<div style="font-size:12px">{flag} {cname}</div>',unsafe_allow_html=True)
                            with c2: st.markdown(f'<div style="background:#e8e6e0;border-radius:3px;height:6px;margin-top:8px"><div style="background:#1D9E75;width:{bar}%;height:100%;border-radius:3px"></div></div>',unsafe_allow_html=True)
                            with c3: st.markdown(f'<div style="font-size:12px;padding-top:4px">{pct:.1f}%</div>',unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════
if st.session_state.screen == "entry":
    screen_entry()
elif st.session_state.screen == "map":
    screen_map()
