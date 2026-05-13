"""
orion_ai_insights.py
────────────────────
Drop this file next to your main app.py and call generate_portfolio_insights()
from screen_map() to show AI-generated plain-English insights.

Usage in your app:
    from orion_ai_insights import generate_portfolio_insights, render_insights_card

    # Inside screen_map(), after you compute geo_agg / sector_agg:
    insights = generate_portfolio_insights(holdings, geo_agg, sector_agg, info_map)
    render_insights_card(insights)
"""

import json
import os
import requests
import streamlit as st
from datetime import date


# ── CSS for the insight cards ──────────────────────────────────────
INSIGHT_CSS = """
<style>
.orion-insights-header {
    font-size: 15px;
    font-weight: 500;
    color: #1a1a1a;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 8px;
}
.orion-insight-card {
    background: white;
    border: 1px solid #e8e6e0;
    border-left: 3px solid #378ADD;
    border-radius: 10px;
    padding: 0.85rem 1.1rem;
    margin-bottom: 0.6rem;
    font-size: 14px;
    color: #2a2a2a;
    line-height: 1.65;
}
.orion-insight-card.warn { border-left-color: #EF9F27; }
.orion-insight-card.risk { border-left-color: #D85A30; }
.orion-insight-card.positive { border-left-color: #1D9E75; }
.orion-insight-label {
    font-size: 10px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: #999;
    margin-bottom: 4px;
}
.orion-insight-text { color: #2a2a2a; }
.orion-ai-badge {
    font-size: 11px;
    background: #f0f0ec;
    color: #777;
    padding: 2px 8px;
    border-radius: 20px;
    font-family: monospace;
}
</style>
"""

_TYPE_TO_CLASS = {
    "concentration": "warn",
    "risk":          "risk",
    "opportunity":   "positive",
    "observation":   "",
    "performance":   "",
}

_TYPE_TO_EMOJI = {
    "concentration": "⚠️",
    "risk":          "🔴",
    "opportunity":   "✅",
    "observation":   "🔵",
    "performance":   "📈",
}


def _get_api_key() -> str:
    """Try every possible way to get the Anthropic API key."""
    # 1. Environment variable
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key and key.startswith("sk-"):
        return key

    # 2. Streamlit secrets — direct key access
    try:
        key = str(st.secrets["ANTHROPIC_API_KEY"]).strip()
        if key and key.startswith("sk-"):
            return key
    except Exception:
        pass

    # 3. Streamlit secrets — via get()
    try:
        key = str(st.secrets.get("ANTHROPIC_API_KEY", "")).strip()
        if key and key.startswith("sk-"):
            return key
    except Exception:
        pass

    # 4. Streamlit secrets — nested under [anthropic] section
    try:
        key = str(st.secrets["anthropic"]["ANTHROPIC_API_KEY"]).strip()
        if key and key.startswith("sk-"):
            return key
    except Exception:
        pass

    return ""


def _build_analytics(holdings, geo_agg, sector_agg, info_map):
    """Crunch all numbers in Python. AI only writes sentences — no math."""
    total_current = sum(h["current"] for h in holdings)
    total_paid    = sum(h["paid"]    for h in holdings)
    total_pnl     = total_current - total_paid
    total_pct     = (total_pnl / total_paid * 100) if total_paid else 0

    equity_val = sum(h["current"] for h in holdings if h.get("asset_type", "stock_etf") == "stock_etf")
    bond_val   = sum(h["current"] for h in holdings if h.get("asset_type") == "bond")
    cash_val   = sum(h["current"] for h in holdings if h.get("asset_type") == "cash")

    top_geo     = sorted(geo_agg.items(),    key=lambda x: -x[1])[:5]
    top_sectors = sorted(sector_agg.items(), key=lambda x: -x[1])[:5]

    holding_details = []
    for h in holdings:
        isin   = h["isin"].upper()
        paid   = h["paid"]
        cur    = h["current"]
        pnl    = cur - paid
        pnl_p  = (pnl / paid * 100) if paid else 0
        name   = info_map.get(isin, {}).get("name", isin)
        weight = (cur / total_current * 100) if total_current else 0
        holding_details.append({
            "name":       name,
            "isin":       isin,
            "type":       h.get("asset_type", "stock_etf"),
            "weight_pct": round(weight, 1),
            "pnl_pct":    round(pnl_p, 1),
            "pnl_usd":    round(pnl, 0),
            "current":    round(cur, 0),
        })

    biggest = max(holding_details, key=lambda x: x["weight_pct"]) if holding_details else {}

    bond_income = 0.0
    for h in holdings:
        if h.get("asset_type") == "bond":
            bond_income += h["face_value"] * h["quantity"] * (h["coupon"] / 100)

    concentration_alerts = []
    for code, pct in geo_agg.items():
        if pct >= 55:
            concentration_alerts.append(f"{pct:.0f}% in {code}")
    for sec, pct in sector_agg.items():
        if pct >= 35 and sec not in ("Cash", "Fixed Income", "ETF / Fund", "—"):
            concentration_alerts.append(f"{pct:.0f}% in {sec}")

    return {
        "summary": {
            "total_value_usd":    round(total_current, 0),
            "total_invested_usd": round(total_paid, 0),
            "total_pnl_usd":      round(total_pnl, 0),
            "total_return_pct":   round(total_pct, 1),
            "n_holdings":         len(holdings),
        },
        "allocation": {
            "equity_pct": round(equity_val / total_current * 100, 1) if total_current else 0,
            "bond_pct":   round(bond_val   / total_current * 100, 1) if total_current else 0,
            "cash_pct":   round(cash_val   / total_current * 100, 1) if total_current else 0,
        },
        "top_geographies": [{"country": c, "pct": round(p, 1)} for c, p in top_geo],
        "top_sectors":     [{"sector": s,  "pct": round(p, 1)} for s, p in top_sectors],
        "holdings":        holding_details,
        "biggest_holding": biggest,
        "bond_annual_income_usd": round(bond_income, 0),
        "concentration_alerts":   concentration_alerts,
    }


def _call_claude(analytics: dict) -> list[dict]:
    api_key = _get_api_key()

    if not api_key:
        return [{
            "type":  "observation",
            "title": "AI insights unavailable",
            "body":  (
                "No API key found. In Streamlit Cloud: go to your app settings → Secrets "
                "and add: ANTHROPIC_API_KEY = \"sk-ant-...\" (with your real key in quotes). "
                "Then reboot the app from the dashboard."
            ),
        }]

    system_prompt = """You are a portfolio intelligence engine for Orion, a visual finance app.
Analyze the user's portfolio data and generate 4-5 concise, specific, genuinely useful insights.

Rules:
- Each insight must reference specific numbers from the data. Never be vague.
- Write in plain English. No jargon. Like explaining to a smart friend, not a client.
- Be direct. Say "you are heavily concentrated in US tech" not "there may be some concentration."
- Do not give investment advice or recommend specific actions.
- One insight per idea. No padding.

Return ONLY valid JSON — a list of objects. No markdown, no backticks, no preamble.
Each object must have exactly these keys:
  "type": one of: concentration | risk | opportunity | observation | performance
  "title": max 8 words, sentence case
  "body": 1-2 sentences, specific numbers, plain English"""

    user_message = f"Generate 4-5 insights for this portfolio:\n\n{json.dumps(analytics, indent=2)}"

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-haiku-4-5",
                "max_tokens": 1024,
                "system":     system_prompt,
                "messages":   [{"role": "user", "content": user_message}],
            },
            timeout=25,
        )

        if resp.status_code == 200:
            raw = resp.json()["content"][0]["text"].strip()
            # Strip accidental markdown fences
            if "```" in raw:
                parts = raw.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("[") or part.startswith("json\n["):
                        raw = part.replace("json\n", "").strip()
                        break
            return json.loads(raw)

        elif resp.status_code == 401:
            return [{"type": "risk", "title": "Invalid API key",
                     "body": "The Anthropic API key was rejected (401). Double-check it in Streamlit Secrets — it should start with sk-ant-"}]

        elif resp.status_code == 429:
            return [{"type": "observation", "title": "Rate limit hit — try again shortly",
                     "body": "The Anthropic API is rate-limiting requests. Wait 30 seconds and refresh."}]

        else:
            return [{"type": "observation", "title": "API error",
                     "body": f"Status {resp.status_code}: {resp.text[:200]}"}]

    except json.JSONDecodeError as e:
        return [{"type": "observation", "title": "Could not parse AI response",
                 "body": f"JSON error: {e}"}]
    except Exception as e:
        return [{"type": "observation", "title": "AI insights temporarily unavailable",
                 "body": str(e)}]


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_insights(analytics_json: str) -> list[dict]:
    analytics = json.loads(analytics_json)
    return _call_claude(analytics)


def generate_portfolio_insights(
    holdings:   list,
    geo_agg:    dict,
    sector_agg: dict,
    info_map:   dict,
) -> list[dict]:
    analytics      = _build_analytics(holdings, geo_agg, sector_agg, info_map)
    analytics_json = json.dumps(analytics, default=str, sort_keys=True)
    return _cached_insights(analytics_json)


def render_insights_card(insights: list[dict]):
    st.markdown(INSIGHT_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="orion-insights-header">'
        '🔭 AI insights'
        '<span class="orion-ai-badge">claude</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    for ins in insights:
        card_class = _TYPE_TO_CLASS.get(ins.get("type", "observation"), "")
        emoji      = _TYPE_TO_EMOJI.get(ins.get("type", "observation"), "🔵")
        title      = ins.get("title", "")
        body       = ins.get("body", "")
        st.markdown(
            f'<div class="orion-insight-card {card_class}">'
            f'<div class="orion-insight-label">{emoji} {ins.get("type","insight").upper()}</div>'
            f'<div class="orion-insight-text"><b>{title}</b><br>{body}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
