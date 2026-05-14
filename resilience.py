"""
resilience.py
─────────────
Portfolio resilience scoring: 0–100.

Four components of 25 points each:
  1. Asset class diversification  — HHI across the six asset classes
  2. Concentration risk           — weight of the single largest holding
  3. Liquidity ratio              — weighted sum by asset-class liquidity tier
  4. Debt burden                  — total debt vs gross assets

Formulas are intentionally simple — no complex finance math, easy to modify.

Public API
----------
compute_resilience(holdings, breakdown) → dict with keys:
    "score"      float  0–100
    "label"      str    "Critical" | "Vulnerable" | "Stable" | "Resilient" | "Fortress"
    "components" dict   {"diversification": float, "concentration": float,
                         "liquidity": float, "debt": float}
"""

# How liquid each asset class is. 1.0 = instantly liquid, 0.0 = illiquid.
LIQUIDITY_TIER = {
    "cash":        1.0,
    "equities":    0.9,
    "bonds":       0.7,
    "commodity":   0.5,
    "crypto":      0.4,
    "real_estate": 0.1,
}

# Label thresholds: (minimum score, label)
SCORE_LABELS = [
    (90, "Fortress"),
    (75, "Resilient"),
    (60, "Stable"),
    (40, "Vulnerable"),
    (0,  "Critical"),
]


# ── helpers ────────────────────────────────────────────────────────────────────

def _hhi(values: list) -> float:
    """
    Herfindahl-Hirschman Index.
    Returns 1/n (perfectly diversified) to 1.0 (fully concentrated).
    """
    total = sum(values)
    if total == 0:
        return 1.0
    shares = [v / total for v in values]
    return sum(s ** 2 for s in shares)


# ── sub-scores (each 0–25) ──────────────────────────────────────────────────────

def _score_diversification(breakdown: dict) -> float:
    """
    Measure spread across the six asset classes using HHI.
    One non-zero class  → HHI = 1.0 → 0 pts.
    Six equal classes   → HHI = 1/6 → 25 pts.
    """
    values = [v for v in breakdown.values() if v > 0]
    if not values or len(values) == 1:
        return 0.0
    hhi      = _hhi(values)
    n        = len(values)
    best_hhi = 1.0 / n          # theoretical minimum HHI for n classes
    # Linear scale: HHI = best_hhi → 25 pts, HHI = 1.0 → 0 pts
    score = (1.0 - hhi) / (1.0 - best_hhi) * 25
    return round(min(25.0, max(0.0, score)), 1)


def _score_concentration(holdings: list, gross_assets: float) -> float:
    """
    Penalise portfolios where a single holding dominates.
    Top holding < 20%  → 25 pts (full marks)
    Top holding 20–50% → partial, linear
    Top holding ≥ 50%  → 0 pts
    """
    if gross_assets == 0 or not holdings:
        return 0.0
    values = [
        h.get("current", 0.0)
        for h in holdings
        if h.get("type") != "debt" and h.get("current", 0.0) > 0
    ]
    if not values:
        return 0.0
    max_weight = max(values) / gross_assets
    if max_weight >= 0.50:
        return 0.0
    if max_weight >= 0.20:
        return round((0.50 - max_weight) / 0.30 * 25, 1)
    return 25.0


def _score_liquidity(breakdown: dict, gross_assets: float) -> float:
    """
    Weighted portfolio liquidity.
    100% cash → 25 pts.  100% real estate → 2.5 pts.
    """
    if gross_assets == 0:
        return 0.0
    liquid_value = sum(
        breakdown.get(cls, 0.0) * tier
        for cls, tier in LIQUIDITY_TIER.items()
    )
    return round(min(25.0, liquid_value / gross_assets * 25), 1)


def _score_debt(holdings: list, gross_assets: float) -> float:
    """
    Debt burden as a fraction of gross assets.
    No debt       → 25 pts
    Debt ≥ 60% of gross assets → 0 pts
    Linear between.
    """
    debt_total = sum(
        h.get("amount", 0.0)
        for h in holdings
        if h.get("type") == "debt"
    )
    if debt_total == 0:
        return 25.0
    total_gross = gross_assets + debt_total
    if total_gross == 0:
        return 0.0
    debt_ratio = debt_total / total_gross
    return round(max(0.0, (0.60 - debt_ratio) / 0.60 * 25), 1)


# ── public API ─────────────────────────────────────────────────────────────────

def get_score_label(score: float) -> str:
    for threshold, label in SCORE_LABELS:
        if score >= threshold:
            return label
    return "Critical"


def compute_resilience(holdings: list, breakdown: dict) -> dict:
    """
    Compute the full resilience score.

    Args:
        holdings:  original holdings list from st.session_state.holdings
                   (used for per-holding concentration check and debt totals)
        breakdown: asset-class value dict — use the CURRENT simulated breakdown
                   (from simulation_engine.get_asset_breakdown or a later tick)

    Returns:
        {
            "score":      float,  # 0–100
            "label":      str,
            "components": {
                "diversification": float,   # 0–25
                "concentration":   float,   # 0–25
                "liquidity":       float,   # 0–25
                "debt":            float,   # 0–25
            }
        }
    """
    gross_assets = sum(v for v in breakdown.values() if v > 0)

    d = _score_diversification(breakdown)
    c = _score_concentration(holdings, gross_assets)
    liq = _score_liquidity(breakdown, gross_assets)
    b = _score_debt(holdings, gross_assets)

    score = d + c + liq + b

    return {
        "score":      round(score, 1),
        "label":      get_score_label(score),
        "components": {
            "diversification": d,
            "concentration":   c,
            "liquidity":       liq,
            "debt":            b,
        },
    }
