# Adding AI insights to Orion — 4 changes, ~10 minutes

## Step 1 — Add your API key

Create a `.streamlit/secrets.toml` file in your project folder:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

Or set it as an environment variable:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Get a key at: https://console.anthropic.com
Cost: ~$0.003 per analysis (negligible)

---

## Step 2 — Copy the file

Put `orion_ai_insights.py` in the same folder as your `app.py`.

---

## Step 3 — Add the import (top of app.py)

Find your existing imports at the top and add one line:

```python
# ADD THIS LINE alongside your other imports
from orion_ai_insights import generate_portfolio_insights, render_insights_card
```

---

## Step 4 — Call it in screen_map()

Find this block in `screen_map()` — it's right after the tab layout setup,
around where `tab1, tab2, tab3, tab4 = st.tabs(...)` is defined.

Add these 6 lines BEFORE the tab layout, right after the warnings block:

```python
    # ── AI insights ───────────────────────────────────────────────
    st.markdown("---")
    with st.spinner("Generating AI insights…"):
        insights = generate_portfolio_insights(holdings, geo_agg, sector_agg, info_map)
    render_insights_card(insights)
    st.markdown("---")

    # ── TAB LAYOUT ─────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(...)   # this line already exists
```

---

## What you'll see

Four to five cards like these, generated fresh from your actual portfolio data:

```
🔵 OBSERVATION
71% of your portfolio is US equities
Between your Apple and Microsoft holdings and the MSCI World ETF, the United
States accounts for 71% of your total exposure — more than two-thirds in a
single market.

⚠️ CONCENTRATION
Taiwan Semiconductor appears in 3 of your holdings
Your combined exposure to TSMC across your ETFs is approximately 4.1% of your
total portfolio. This is a meaningful single-company concentration you may not
have intended.

✅ OPPORTUNITY
Your bond positions provide $8,400 in annual income
At a yield on cost of 5.8%, your fixed income holdings are generating above
inflation returns and cushion roughly 18% of your total portfolio value.
```

---

## Caching

Insights are cached for **1 hour** — so Streamlit rerenders won't trigger
repeated API calls. To force a refresh, add a button:

```python
if st.button("🔄 Refresh insights"):
    st.cache_data.clear()
    st.rerun()
```

---

## Troubleshooting

**"AI insights unavailable"** → ANTHROPIC_API_KEY not found. Check secrets.toml or env var.

**"Could not parse AI response"** → Rare, retry usually fixes it. The model occasionally
adds markdown fences around the JSON despite instructions not to — the code strips these
but edge cases exist.

**Slow loading** → First load takes 3–5 seconds (API call). Subsequent loads within
1 hour are instant (cached). Normal.
