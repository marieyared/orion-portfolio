#!/usr/bin/env python3
"""
build_dossiers.py — Orion dossier generator (EQUITY_RESEARCH_PLAN §9 step 2)

Produces ONE static JSON dossier per ticker, committed to the repo under
`dossiers/`. This is the "compute once, serve many" path (§7): the model is
NEVER called here — every number is deterministic from SEC EDGAR XBRL. The AI
narrative is a separate, later language-only step; this file leaves a `narrative`
slot null on purpose.

Data source: SEC EDGAR (free, no key). Needs a descriptive User-Agent per SEC
fair-access policy. US-first by design (§8).

Usage:
    python3 build_dossiers.py AAPL MSFT GOOGL        # specific tickers
    python3 build_dossiers.py                        # rebuild DEFAULT_UNIVERSE

The quality-compounder scorecard keys below MUST match PHILOSOPHY.lenses in
orion.html. If you swap the philosophy there, re-derive the scorecard here.
"""

import json, os, sys, time, urllib.request, urllib.error
from datetime import date

UA = "Orion Research (orion-dossier-builder; contact: marieyared10@gmail.com)"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dossiers")
YEARS = 6  # how many recent fiscal years to keep

# Pre-cover a small, on-tribe set: durable compounders + the mega-caps users
# will type first. Cost scales with companies covered, not users (§7).
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "NVDA", "META", "V", "MA", "COST",
    "UNH", "HD", "ADBE", "NKE", "SBUX", "AMZN",
]

# ── EDGAR concept preferences (first present tag wins) ──────────────────────
# Durations (flow) — full-year values.
FLOW = {
    "revenue":          ["RevenueFromContractWithCustomerExcludingAssessedTax",
                         "Revenues", "RevenueFromContractWithCustomerIncludingAssessedTax",
                         "SalesRevenueNet"],
    "grossProfit":      ["GrossProfit"],
    "operatingIncome":  ["OperatingIncomeLoss"],
    "pretaxIncome":     ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                         "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "taxExpense":       ["IncomeTaxExpenseBenefit"],
    "netIncome":        ["NetIncomeLoss", "ProfitLoss",
                         "NetIncomeLossAvailableToCommonStockholdersBasic"],
    "cfo":              ["NetCashProvidedByUsedInOperatingActivities",
                         "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex":            ["PaymentsToAcquirePropertyPlantAndEquipment",
                         "PaymentsToAcquireProductiveAssets"],
    "dilutedShares":    ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}
# Instants (stock) — fiscal year-end balances.
STOCK = {
    "assets":       ["Assets"],
    "equity":       ["StockholdersEquity",
                     "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "cash":         ["CashAndCashEquivalentsAtCarryingValue"],
    "longTermDebt": ["LongTermDebtNoncurrent", "LongTermDebt"],
}


def fetch(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


_TICKER_MAP = None
def ticker_to_cik(ticker):
    global _TICKER_MAP
    if _TICKER_MAP is None:
        data = fetch("https://www.sec.gov/files/company_tickers.json")
        _TICKER_MAP = {v["ticker"].upper(): (str(v["cik_str"]).zfill(10), v["title"])
                       for v in data.values()}
    return _TICKER_MAP.get(ticker.upper())


def annual_series(concept_facts, instant):
    """Map a us-gaap concept's USD units to {fiscalYear: value} using 10-K filings.

    Durations: keep entries spanning ~a year (350–380 days). Instants: keep the
    year-end balance. Keyed by the year of the period-end; latest-filed wins."""
    out = {}
    units = concept_facts.get("units", {})
    series = units.get("USD") or units.get("shares") or next(iter(units.values()), [])
    for u in series:
        form = u.get("form", "")
        if not form.startswith("10-K"):
            continue
        end = u.get("end")
        if not end:
            continue
        yr = int(end[:4])
        if instant:
            keep = True
        else:
            start = u.get("start")
            if not start:
                continue
            span = (date.fromisoformat(end) - date.fromisoformat(start)).days
            keep = 350 <= span <= 380
        if not keep:
            continue
        prev = out.get(yr)
        # Prefer the most recently filed value for that fiscal year.
        if prev is None or u.get("filed", "") >= prev[1]:
            out[yr] = (u["val"], u.get("filed", ""))
    return {yr: v[0] for yr, v in out.items()}


def pick(facts_gaap, names, instant):
    """Choose the best candidate concept. A company may report the same line under
    several tags (e.g. NVDA carries both `Revenues` through today and a legacy
    `RevenueFromContract…` that stops in 2022). Don't take the first present tag —
    take the one whose series reaches the most recent year, then has the widest
    coverage. Fill any remaining year gaps from the other candidates."""
    series = [(n, annual_series(facts_gaap[n], instant)) for n in names if n in facts_gaap]
    series = [(n, s) for n, s in series if s]
    if not series:
        return {}
    best = max(series, key=lambda ns: (max(ns[1]), len(ns[1])))[1]
    merged = dict(best)
    for _, s in series:
        for y, v in s.items():
            merged.setdefault(y, v)  # backfill older years the winner lacks
    return merged


def safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def round_or_none(x, n=4):
    return None if x is None else round(x, n)


def build(ticker):
    hit = ticker_to_cik(ticker)
    if not hit:
        print(f"  ! {ticker}: not found in SEC ticker map (US-listed only)")
        return None
    cik, title = hit
    facts = fetch(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    subs = fetch(f"https://data.sec.gov/submissions/CIK{cik}.json")
    gaap = facts.get("facts", {}).get("us-gaap", {})

    fin = {}
    for k, names in FLOW.items():
        fin[k] = pick(gaap, names, instant=False)
    for k, names in STOCK.items():
        fin[k] = pick(gaap, names, instant=True)

    # FCF = CFO − capex, per year present in both.
    fin["fcf"] = {y: fin["cfo"][y] - fin["capex"].get(y, 0)
                  for y in fin["cfo"] if y in fin["cfo"]}

    # Universe of fiscal years we actually have revenue + net income for.
    years = sorted(set(fin["revenue"]) & set(fin["netIncome"]))[-YEARS:]
    if len(years) < 2:
        print(f"  ! {ticker}: too few annual periods, skipping")
        return None

    def g(k, y):
        return fin.get(k, {}).get(y)

    metrics = {m: {} for m in ["grossMargin", "operatingMargin", "netMargin",
                               "roic", "roe", "fcfConversion", "fcfMargin",
                               "fcfPerShare", "eps", "bookValuePerShare"]}
    for y in years:
        rev, ni, op = g("revenue", y), g("netIncome", y), g("operatingIncome", y)
        gp, fcf = g("grossProfit", y), g("fcf", y)
        eq, cash, debt = g("equity", y), g("cash", y), g("longTermDebt", y)
        tax, pretax = g("taxExpense", y), g("pretaxIncome", y)
        sh = g("dilutedShares", y)
        eff_tax = safe_div(tax, pretax)
        if eff_tax is None or eff_tax < 0 or eff_tax > 0.6:
            eff_tax = 0.21  # statutory fallback when the ratio is nonsense
        nopat = op * (1 - eff_tax) if op is not None else None
        invested = None
        if eq is not None:
            invested = eq + (debt or 0) - (cash or 0)
        metrics["grossMargin"][y]     = round_or_none(safe_div(gp, rev))
        metrics["operatingMargin"][y] = round_or_none(safe_div(op, rev))
        metrics["netMargin"][y]       = round_or_none(safe_div(ni, rev))
        metrics["roic"][y]            = round_or_none(safe_div(nopat, invested))
        metrics["roe"][y]             = round_or_none(safe_div(ni, eq))
        metrics["fcfConversion"][y]   = round_or_none(safe_div(fcf, ni))
        metrics["fcfMargin"][y]       = round_or_none(safe_div(fcf, rev))
        metrics["fcfPerShare"][y]     = round_or_none(safe_div(fcf, sh), 2)
        metrics["eps"][y]             = round_or_none(safe_div(ni, sh), 2)
        metrics["bookValuePerShare"][y] = round_or_none(safe_div(eq, sh), 2)

    scorecard = build_scorecard(metrics, fin, years)

    latest = years[-1]
    exch = (subs.get("exchanges") or ["—"])[0]
    return {
        "schema": 1,
        "ticker": ticker.upper(),
        "name": subs.get("name") or title,
        "cik": cik,
        "sic": subs.get("sic", ""),
        "sicDescription": subs.get("sicDescription", ""),
        "exchange": exch,
        "fiscalYearEnd": subs.get("fiscalYearEnd", ""),
        "latestFiscalYear": latest,
        "asOf": _latest_end(gaap, latest),
        "source": "SEC EDGAR — XBRL companyfacts (10-K)",
        "currency": "USD",
        "fiscalYears": years,
        "financials": {k: {str(y): v.get(y) for y in years} for k, v in fin.items()},
        "metrics": {k: {str(y): v.get(y) for y in years} for k, v in metrics.items()},
        "scorecard": scorecard,
        "narrative": None,   # AI business summary — wired in a later (language-only) step
    }


def _latest_end(gaap, year):
    rev = gaap.get("RevenueFromContractWithCustomerExcludingAssessedTax") or gaap.get("Revenues") or {}
    ends = [u.get("end") for u in rev.get("units", {}).get("USD", [])
            if u.get("end", "").startswith(str(year)) and u.get("form", "").startswith("10-K")]
    return max(ends) if ends else f"{year}-12-31"


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _trend(series, years):
    """+1 improving, −1 deteriorating, 0 flat — first vs last available."""
    vals = [series.get(y) for y in years if series.get(y) is not None]
    if len(vals) < 2:
        return 0
    d = vals[-1] - vals[0]
    eps = 0.02 * abs(vals[0]) if vals[0] else 0.01
    return 1 if d > eps else (-1 if d < -eps else 0)


def _pct(x):
    return None if x is None else f"{x*100:.0f}%"


def build_scorecard(m, fin, years):
    """One row per PHILOSOPHY lens. Thresholds are explicit and documented so the
    rating is auditable — not a black box and not AI-generated."""
    rows = []

    # 1) Returns on capital — high & stable ROIC.
    roic_avg = _avg([m["roic"].get(y) for y in years])
    roic_last = m["roic"].get(years[-1])
    r = ("strong" if (roic_avg or 0) >= 0.20 else
         "ok" if (roic_avg or 0) >= 0.12 else
         "weak" if roic_avg is not None else "na")
    rows.append({
        "key": "roic", "label": "Returns on capital", "rating": r,
        "headline": f"ROIC {_pct(roic_last)} (last) · {_pct(roic_avg)} {len(years)}y avg" if roic_avg is not None else "ROIC unavailable",
        "detail": "NOPAT ÷ (equity + LT debt − cash). High, stable ROIC is the core compounder signal.",
    })

    # 2) Moat — durable, high gross margin holding up over time (pricing power proxy).
    gm_avg = _avg([m["grossMargin"].get(y) for y in years])
    gm_tr = _trend(m["grossMargin"], years)
    r = ("strong" if (gm_avg or 0) >= 0.50 and gm_tr >= 0 else
         "ok" if (gm_avg or 0) >= 0.35 else
         "weak" if gm_avg is not None else "na")
    rows.append({
        "key": "moat", "label": "Moat", "rating": r,
        "headline": f"Gross margin {_pct(gm_avg)} avg, {'rising/stable' if gm_tr>=0 else 'eroding'}" if gm_avg is not None else "Gross margin unavailable",
        "detail": "Sustained high gross margin is circumstantial evidence of pricing power. Not a substitute for judging the source of the moat.",
    })

    # 3) Owner earnings — reported profit converting to real cash.
    conv_avg = _avg([m["fcfConversion"].get(y) for y in years])
    r = ("strong" if (conv_avg or 0) >= 0.90 else
         "ok" if (conv_avg or 0) >= 0.70 else
         "weak" if conv_avg is not None else "na")
    rows.append({
        "key": "owner_earnings", "label": "Owner earnings", "rating": r,
        "headline": f"FCF ÷ net income {_pct(conv_avg)} avg" if conv_avg is not None else "Cash conversion unavailable",
        "detail": "Free cash flow (CFO − capex) as a share of reported net income. Persistent <70% means earnings aren't turning into cash.",
    })

    # 4) Management & capital allocation — ROIC level + share count discipline.
    sh = fin.get("dilutedShares", {})
    sh_tr = _trend(sh, years)  # falling share count (buybacks) = −1 trend here
    shrinking = sh_tr < 0
    r = ("strong" if (roic_avg or 0) >= 0.15 and not (sh_tr > 0) else
         "ok" if (roic_avg or 0) >= 0.10 else
         "weak" if roic_avg is not None else "na")
    rows.append({
        "key": "management", "label": "Management & capital allocation", "rating": r,
        "headline": ("Reinvests at high ROIC; share count " +
                     ("shrinking" if shrinking else "rising" if sh_tr > 0 else "flat")) if roic_avg is not None else "Insufficient data",
        "detail": "Proxy: returns on reinvested capital plus diluted-share-count trend. Real capital-allocation judgement still needs the proxy statement.",
    })

    # 5) Price vs. value — needs a live price; computed client-side from per-share data.
    rows.append({
        "key": "valuation", "label": "Price vs. value", "rating": "na",
        "headline": "Needs live price — computed in-app",
        "detail": "EPS, FCF/share and book value are in the dossier; Orion computes P/E and FCF yield against the live quote so valuation is never stale.",
    })
    return rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tickers = [t.upper() for t in sys.argv[1:]] or DEFAULT_UNIVERSE
    manifest = []
    for t in tickers:
        print(f"• {t} …")
        try:
            d = build(t)
        except Exception as e:
            print(f"  ! {t}: {e}")
            continue
        if not d:
            continue
        with open(os.path.join(OUT_DIR, f"{t}.json"), "w") as f:
            json.dump(d, f, separators=(",", ":"))
        manifest.append({"ticker": t, "name": d["name"],
                         "sector": d["sicDescription"], "latestFiscalYear": d["latestFiscalYear"]})
        print(f"  ✓ {t}: {d['name']} — FY{d['latestFiscalYear']}, {len(d['fiscalYears'])}y")
        time.sleep(0.3)  # be polite to EDGAR
    manifest.sort(key=lambda x: x["ticker"])
    index = {"covered": manifest, "philosophy": "quality-compounder"}
    with open(os.path.join(OUT_DIR, "index.json"), "w") as f:
        json.dump(index, f, indent=2)

    # Browser bundle. The per-ticker JSONs above are the canonical, diff-friendly
    # artifacts; this bundle is what orion.html actually loads, because a <script>
    # tag works even when the app is opened as a file:// URL (where fetch() of a
    # local JSON is blocked by CORS). orion.html prefers window.ORION_DOSSIERS and
    # falls back to fetch() when served over HTTP.
    bundle = {"index": index, "dossiers": {}}
    for entry in manifest:
        t = entry["ticker"]
        with open(os.path.join(OUT_DIR, f"{t}.json")) as f:
            bundle["dossiers"][t] = json.load(f)
    with open(os.path.join(OUT_DIR, "dossiers.js"), "w") as f:
        f.write("window.ORION_DOSSIERS=" + json.dumps(bundle, separators=(",", ":")) + ";\n")

    print(f"\nWrote {len(manifest)} dossiers + index.json + dossiers.js to {OUT_DIR}")


if __name__ == "__main__":
    main()
