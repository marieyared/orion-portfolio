import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
import json

st.set_page_config(
    page_title="Orion — Portfolio Intelligence",
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
        margin-bottom: 1rem;
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
        width: 100%;
    }
    .stButton > button:hover { opacity: 0.85 !important; }

    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #e8e6e0;
        border-radius: 10px;
        padding: 1rem;
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
            data = resp.json()
            if data and data[0].get("data"):
                item = data[0]["data"][0]
                result = {
                    "name": item.get("name", isin),
                    "type": item.get("securityType", "—"),
                    "exchange": item.get("exchCode", "—"),
                    "currency": item.get("marketSector", "—"),
                }
                st.session_state.isin_cache[isin] = result
                return result
    except Exception:
        pass
    return None

# ── look-through data (top UCITS ETFs) ────────────────────────────
ETF_LOOKTHROUGH = {
    "IE00B4L5Y983": {
        "name": "iShares MSCI World ETF",
        "geo": {"US":67.2,"JP":6.1,"GB":4.8,"FR":3.8,"CA":3.6,"CH":3.1,"DE":2.9,"AU":2.4,"NL":1.8,"Other":4.3},
        "sectors": {"Technology":22.1,"Financials":15.3,"Healthcare":12.8,"Industrials":10.2,"Consumer":9.4,"Energy":5.1,"Other":25.1},
        "overlaps": ["AAPL","MSFT","NVDA","AMZN","GOOGL"]
    },
    "IE00BKM4GZ66": {
        "name": "iShares EM IMI ETF",
        "geo": {"CN":30.2,"TW":16.1,"IN":14.8,"KR":12.3,"BR":5.2,"SA":4.1,"Other":17.3},
        "sectors": {"Technology":21.0,"Financials":22.0,"Consumer":14.0,"Materials":8.0,"Energy":7.0,"Other":28.0},
        "overlaps": ["BABA","TSMC","RELIANCE"]
    },
    "IE00B5BMR087": {
        "name": "iShares Core S&P 500 ETF",
        "geo": {"US":100.0},
        "sectors": {"Technology":29.0,"Financials":13.0,"Healthcare":12.0,"Consumer":10.0,"Industrials":8.5,"Other":27.5},
        "overlaps": ["AAPL","MSFT","NVDA","AMZN","META"]
    },
    "IE00B3RBWM25": {
        "name": "Vanguard FTSE All-World ETF",
        "geo": {"US":62.0,"JP":6.0,"GB":4.0,"CN":3.5,"FR":3.0,"CA":2.8,"CH":2.5,"DE":2.2,"AU":2.0,"Other":12.0},
        "sectors": {"Technology":23.0,"Financials":15.0,"Healthcare":11.0,"Industrials":10.0,"Consumer":9.0,"Energy":5.0,"Other":27.0},
        "overlaps": ["AAPL","MSFT","NVDA","AMZN","GOOGL"]
    },
    "US78462F1030": {
        "name": "SPDR S&P 500 ETF",
        "geo": {"US":100.0},
        "sectors": {"Technology":29.0,"Financials":13.0,"Healthcare":12.0,"Consumer":10.0,"Industrials":8.5,"Other":27.5},
        "overlaps": ["AAPL","MSFT","NVDA","AMZN","META"]
    },
}

EQUITY_GEO = {
    "US0378331005": {"name":"Apple Inc.",       "geo":{"US":43,"CN":19,"EU":22,"JP":8,"Other":8},   "sectors":{"Technology":100}},
    "US5949181045": {"name":"Microsoft Corp.",  "geo":{"US":55,"EU":20,"CN":10,"Other":15},          "sectors":{"Technology":100}},
    "US88160R1014": {"name":"Tesla Inc.",        "geo":{"US":45,"CN":22,"EU":20,"Other":13},          "sectors":{"Consumer":100}},
    "US67066G1040": {"name":"NVIDIA Corp.",      "geo":{"US":60,"TW":15,"CN":10,"Other":15},          "sectors":{"Technology":100}},
    "US02079K3059": {"name":"Alphabet Inc.",     "geo":{"US":55,"EU":20,"Other":25},                  "sectors":{"Technology":100}},
    "US30303M1027": {"name":"Meta Platforms",    "geo":{"US":50,"EU":20,"Other":30},                  "sectors":{"Technology":100}},
    "SA14TG012N13": {"name":"Saudi Aramco",      "geo":{"SA":100},                                    "sectors":{"Energy":100}},
    "US4592001014": {"name":"IBM Corp.",          "geo":{"US":60,"EU":20,"Other":20},                  "sectors":{"Technology":100}},
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
def aggregate_portfolio(holdings):
    total_value = sum(h["current"] for h in holdings)
    if total_value == 0:
        return {}, {}
    geo_agg = {}
    sector_agg = {}
    for h in holdings:
        weight = h["current"] / total_value
        isin = h["isin"].upper()
        source = ETF_LOOKTHROUGH.get(isin) or EQUITY_GEO.get(isin)
        if source:
            for country, pct in source["geo"].items():
                geo_agg[country] = geo_agg.get(country, 0) + pct * weight
            for sector, pct in source["sectors"].items():
                sector_agg[sector] = sector_agg.get(sector, 0) + pct * weight
        else:
            code = country_from_isin(isin)
            geo_agg[code] = geo_agg.get(code, 0) + 100 * weight
            sector_agg["Other"] = sector_agg.get("Other", 0) + 100 * weight
    return geo_agg, sector_agg

# ══════════════════════════════════════════════════════════════════
# SCREEN 1 — ENTRY
# ══════════════════════════════════════════════════════════════════
def screen_entry():
    st.markdown('<div class="orion-logo">ORION / PORTFOLIO INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="orion-headline">Enter your holdings</div>', unsafe_allow_html=True)
    st.markdown('<div class="orion-sub">Find your ISIN on any broker statement — UBS, Baraka, eToro. Enter the current value and your purchase details.</div>', unsafe_allow_html=True)
    st.markdown('<div class="hint-box">💡 Your ISIN is a 12-character code on every broker statement — e.g. <b>IE00B4L5Y983</b> for iShares MSCI World. We look it up automatically.</div>', unsafe_allow_html=True)

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
                    known = ETF_LOOKTHROUGH.get(isin) or EQUITY_GEO.get(isin)
                    if known:
                        st.markdown(f'<div class="instrument-found">✓ {known["name"]}</div>', unsafe_allow_html=True)
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

    ca, cb = st.columns([1, 3])
    with ca:
        if st.button("＋  Add holding"):
            st.session_state.entry_rows.append(
                {"isin":"","current":0.0,"date":date.today(),"paid":0.0})
            st.rerun()
    with cb:
        if st.button("🔭  Build my portfolio map →"):
            valid = [r for r in st.session_state.entry_rows
                     if len(r["isin"]) == 12 and r["current"] > 0]
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

    total_current = sum(h["current"] for h in holdings)
    total_paid    = sum(h["paid"]    for h in holdings)
    total_pnl     = total_current - total_paid
    total_pct     = (total_pnl / total_paid * 100) if total_paid > 0 else 0

    geo_agg, sector_agg = aggregate_portfolio(holdings)

    # ── nav ────────────────────────────────────────────────────────
    st.markdown('<div class="orion-logo">ORION / PORTFOLIO INTELLIGENCE</div>', unsafe_allow_html=True)
    if st.button("← Back to holdings"):
        st.session_state.screen = "entry"
        st.rerun()
    st.markdown("---")

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

    # ── overlap alert ──────────────────────────────────────────────
    all_overlaps = []
    for h in holdings:
        etf = ETF_LOOKTHROUGH.get(h["isin"].upper())
        if etf:
            all_overlaps.extend(etf.get("overlaps", []))
    if all_overlaps:
        st.markdown(f'<div class="alert-box">⚠ Overlap detected — your ETFs contain stocks that may also appear as direct holdings. Look-through analysis is applied below.</div>',
                    unsafe_allow_html=True)

    st.markdown("---")

    # ── TAB LAYOUT ─────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["🗺 Portfolio map", "🌍 World exposure", "📊 Performance"])

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
            is_etf  = isin in ETF_LOOKTHROUGH
            info    = ETF_LOOKTHROUGH.get(isin) or EQUITY_GEO.get(isin)
            name    = info["name"] if info else isin
            color   = COLORS[i % len(COLORS)]
            pnl_str = f"+${pnl:,.0f} (+{pnl_p:.1f}%)" if pnl >= 0 else f"-${abs(pnl):,.0f} ({pnl_p:.1f}%)"
            badge   = "Look-through" if is_etf else "Direct equity"

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
                    # unique label per holding
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
                # Direct equity: ONE sub-rectangle = listed country, no further breakdown
                if info and "geo" in info:
                    # pick the primary country (largest geo entry)
                    primary = max(info["geo"].items(), key=lambda x: x[1])
                    code, _ = primary
                else:
                    # fall back to the 2-letter ISIN prefix (ISO 3166-1 alpha-2)
                    code = country_from_isin(isin)
                flag  = FLAGS.get(code, "")
                cname = COUNTRY_NAMES.get(code, code)
                child_lbl = f"{flag} {cname} (listed)||{isin}"
                labels.append(child_lbl)
                parents.append(name)
                values.append(cur)
                colors.append(color + "99")
                hovers.append(
                    f"<b>{flag} {cname}</b><br>"
                    f"Listed: {name}<br>"
                    f"Direct equity — single listing<br>"
                    f"Value: ${cur:,.0f}"
                )
                texts.append(f"{flag} {cname}<br>Listed")

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
            info = ETF_LOOKTHROUGH.get(isin) or EQUITY_GEO.get(isin)
            if info and "geo" in info:
                for c in info["geo"]:
                    country_sources.setdefault(c, []).append(info.get("name", isin))
            elif isin not in ETF_LOOKTHROUGH:
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
        st.markdown("### Performance — by holding")

        perf_rows = []
        for i, h in enumerate(holdings):
            isin  = h["isin"].upper()
            cur   = h["current"]
            paid  = h["paid"]
            pnl   = cur - paid
            pnl_p = (pnl / paid * 100) if paid > 0 else 0
            port_p = (cur / total_current * 100) if total_current > 0 else 0
            info  = ETF_LOOKTHROUGH.get(isin) or EQUITY_GEO.get(isin)
            name  = info["name"] if info else isin
            days  = (date.today() - h["date"]).days if h.get("date") else "—"
            perf_rows.append({
                "Holding":        name,
                "ISIN":           isin,
                "Days held":      days,
                "% of portfolio": round(port_p, 1),
                "Invested ($)":   round(paid),
                "Current ($)":    round(cur),
                "Gain/Loss ($)":  round(pnl),
                "Gain/Loss (%)":  round(pnl_p, 1),
            })

        perf_df = pd.DataFrame(perf_rows)

        def color_pnl(val):
            if isinstance(val, (int, float)):
                color = "#15803d" if val >= 0 else "#dc2626"
                return f"color: {color}; font-weight: 500"
            return ""

        styled = perf_df.style.map(
            color_pnl, subset=["Gain/Loss ($)", "Gain/Loss (%)"]
        ).format({
            "Invested ($)":   "${:,.0f}",
            "Current ($)":    "${:,.0f}",
            "Gain/Loss ($)":  lambda v: f"+${v:,.0f}" if v >= 0 else f"-${abs(v):,.0f}",
            "Gain/Loss (%)":  lambda v: f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%",
            "% of portfolio": "{:.1f}%",
        })
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.markdown("### Allocation — current weights")
        donut_df = pd.DataFrame([{
            "name": (ETF_LOOKTHROUGH.get(h["isin"].upper()) or
                     EQUITY_GEO.get(h["isin"].upper()) or {}).get("name", h["isin"]),
            "value": h["current"]
        } for h in holdings])

        fig_donut = px.pie(
            donut_df, names="name", values="value",
            hole=0.6,
            color_discrete_sequence=COLORS,
        )
        fig_donut.update_traces(textposition="outside", textinfo="percent+label")
        fig_donut.update_layout(
            height=380,
            showlegend=False,
            margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="white",
        )
        st.plotly_chart(fig_donut, use_container_width=True)

# ══════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════
if st.session_state.screen == "entry":
    screen_entry()
elif st.session_state.screen == "map":
    screen_map()
