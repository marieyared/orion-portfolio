"""
simulation_engine.py
────────────────────
Deterministic monthly portfolio simulation.

No randomness — same inputs always produce the same output.
Scenarios are explicit shock multipliers applied on top of baseline drift.

Public API
----------
get_asset_breakdown(holdings)  →  dict  {asset_class: total_value}
run_tick(breakdown, scenario)  →  dict  updated breakdown after one month
total_value(breakdown)         →  float sum of all asset class values
"""

# Monthly drift rates per asset class.
# Conservative long-run monthly return assumptions.
# Equities ≈ +6%/yr, real estate ≈ +3.7%/yr, cash ≈ +0.4%/yr (savings).
MONTHLY_DRIFT = {
    "equities":    0.005,   # +0.5%/month  ≈ +6.2%/year
    "bonds":       0.002,   # +0.2%/month  ≈ +2.4%/year
    "cash":        0.0003,  # +0.03%/month ≈ +0.4%/year
    "real_estate": 0.003,   # +0.3%/month  ≈ +3.7%/year
    "crypto":      0.010,   # +1.0%/month  (high-growth assumption)
    "commodity":   0.002,   # +0.2%/month
}


def get_holding_value(h: dict) -> float:
    """
    Return the current market value of a holding.
    Different asset types store their value under different keys:
      - ISIN equities / bonds / cash  → "current"
      - crypto / commodity            → "current_value"
      - real estate                   → "value"
      - debt                          → "amount"  (caller decides whether to include)
    Falls back through all four keys in order; returns 0.0 if none are set.
    """
    for key in ("current", "current_value", "value", "amount"):
        v = h.get(key)
        if v is not None:
            return float(v)
    return 0.0


def get_asset_class(holding: dict) -> str | None:
    """
    Map one holding dict to an asset class key (one of MONTHLY_DRIFT's keys).
    Returns None for debt — debt is not simulated, only tracked in resilience.
    """
    h_type     = holding.get("type", "")
    asset_type = holding.get("asset_type", "")

    if h_type == "debt":
        return None
    if h_type == "real_estate":
        return "real_estate"
    if h_type == "crypto":
        return "crypto"
    if h_type == "commodity":
        return "commodity"
    if asset_type == "bond":
        return "bonds"
    if asset_type == "cash":
        return "cash"
    # Default: equity / ETF (ISIN-based holding with asset_type "stock_etf")
    return "equities"


def get_asset_breakdown(holdings: list) -> dict:
    """
    Build an asset-class value breakdown from the holdings list.

    Returns a dict like:
        {"equities": 120000, "bonds": 50000, "cash": 10000,
         "real_estate": 0, "crypto": 0, "commodity": 0}

    Debt holdings are excluded (they reduce net worth but are handled
    separately in the resilience score, not in the simulation ticks).
    """
    breakdown = {cls: 0.0 for cls in MONTHLY_DRIFT}
    for h in holdings:
        asset_class = get_asset_class(h)
        if asset_class is None:
            continue
        breakdown[asset_class] += get_holding_value(h)
    return breakdown


def run_tick(breakdown: dict, scenario: dict | None = None) -> dict:
    """
    Apply one monthly simulation turn.

    Order of operations:
      1. Apply baseline monthly drift to each asset class (compounding).
      2. If a scenario dict is given, multiply each class by (1 + shock).

    Scenario shocks are designed to be one-time events (e.g. a crash).
    app.py should clear st.session_state.sim_active_scenario to None
    immediately after calling run_tick() with a scenario, so the shock
    does not carry forward into the next month automatically.

    Args:
        breakdown: current asset-class value dict
        scenario:  a scenario dict from scenarios.json, or None for baseline only

    Returns:
        A new breakdown dict — the input is NOT modified.
    """
    new_breakdown = {}
    for asset_class, value in breakdown.items():
        drift = MONTHLY_DRIFT.get(asset_class, 0.0)
        new_value = value * (1.0 + drift)               # step 1: drift
        if scenario:
            shock = scenario.get("shocks", {}).get(asset_class, 0.0)
            new_value = new_value * (1.0 + shock)       # step 2: shock
        new_breakdown[asset_class] = max(0.0, new_value)
    return new_breakdown


def total_value(breakdown: dict) -> float:
    """Sum all asset class values in a breakdown dict."""
    return sum(breakdown.values())
