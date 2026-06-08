// test_findings.mjs — self-contained verification for the Orion findings engine.
//
// Imports NOTHING from the browser app. It pastes in the helpers + the eight
// rule functions exactly as they appear in orion.html, then feeds three
// synthetic portfolios and asserts the right rules fire. Run:  node test_findings.mjs
//
// The rules are pure (holdings, ctx) => Finding[]; in the app runFindings()
// builds ctx from buildPortfolioSummary()/currentAllocation()/state. Here we
// build ctx by hand so the test needs no app globals.

/* ── Stubs for the few app symbols the rules lean on ───────────────────── */
const fmt = n => Math.round(n || 0).toLocaleString("en-US");

// Which ISINs the app's isETF() would treat as funds. In the app this reads
// state.isinCache/keywords; here we declare them explicitly per fixture.
const TEST_ETFS = new Set(["IE00B4L5Y983", "IE00B4L5YX21"]);
function isETF(isin) { return TEST_ETFS.has((isin || "").toUpperCase()); }

// Names live in infoMap in the app; mirror that so _fName resolves real names.
const state = {
  infoMap: {
    "IE00B4L5Y983": { name: "iShares Core S&P 500 UCITS ETF USD (Acc)" },
    "IE00B4L5YX21": { name: "iShares Core S&P 500 UCITS ETF USD (Dist)" },
    "US0378331005": { name: "Apple Inc." },
    "US67066G1040": { name: "NVIDIA Corp" },
  }
};

// Verbatim from orion.html (asset-class bucketing).
function holdingClass(h) {
  if (h.asset_type === "bond")   return "Bond";
  if (h.asset_type === "cash")   return "Cash";
  if (h.type === "real_estate")  return "Real Estate";
  if (h.type === "crypto")       return "Crypto";
  if (h.type === "commodity")    return "Commodity";
  if (h.isin && isETF(h.isin))   return "ETF";
  return "Equity";
}

/* ════════════════════════════════════════════════════════════════════════
   PASTED FROM orion.html — FINDINGS ENGINE (helpers + rules + orchestrator)
   ════════════════════════════════════════════════════════════════════════ */

function domicileOf(h) {
  const isin = (h.isin || "").toUpperCase();
  if (h.manualDomicile) return h.manualDomicile;
  if (isin.startsWith("US")) return "US";
  if (isin.startsWith("IE") || isin.startsWith("LU")) return "UCITS";
  if (isin.length === 12) return isin.slice(0, 2);
  return "UNKNOWN";
}
function isUSSitus(h) {
  const cls = holdingClass(h);
  const d = domicileOf(h);
  if (cls === "Equity") return d === "US";
  if (cls === "ETF")    return d === "US";
  if (h.type === "crypto" && h.isin) return d === "US";
  return false;
}
function pctOf(valueUSD, total) { return total ? (valueUSD / total * 100) : 0; }

function _fName(h) {
  if (h.isin) { const info = state.infoMap[h.isin.toUpperCase()] || {}; return info.name || h.ticker || h.isin; }
  if (h.type === "real_estate") return h.address || h.city || "Real estate";
  if (h.type === "crypto")      return h.crypto_type || "Crypto";
  if (h.type === "commodity")   return h.commodity_type || "Commodity";
  return h.isin || "Holding";
}
function _fSymbol(h) {
  return String(h.ticker || (h.type === "crypto" ? h.crypto_type : "") || h.isin || "");
}

function f_usSitusEstate(holdings, ctx) {
  const p = ctx.profile;
  if (!p || p.isUSPerson !== false) return [];
  const situs = holdings.filter(isUSSitus);
  const exposed = situs.reduce((a, h) => a + (h.current || 0), 0);
  const line = p.ceilings?.usSitusUSD ?? 60000;
  if (exposed <= line) return [];
  const over = exposed - line;
  const estTax = Math.round(over * 0.40);
  const keep = new Set((p.convictionHolds || []).map(s => s.toUpperCase()));
  const reWrap = situs.filter(h => !keep.has(_fSymbol(h).toUpperCase()) && !keep.has(_fName(h).toUpperCase()));
  return [{
    id: "us_situs_estate", severity: "high", userDecision: false,
    title: `US-situs assets $${fmt(exposed)} — $${fmt(over)} over the $${fmt(line)} line`,
    body: `As a non-US person, US-situs assets above $${fmt(line)} can face US estate tax up to 40%. ` +
          `Re-wrapping US-listed names into UCITS ETFs removes situs while keeping the exposure.`,
    valueUSD: exposed, costUSD: estTax,
    evidence: situs.map(h => ({ label: _fName(h), value: `$${fmt(h.current || 0)} (${domicileOf(h)})` })),
    action: reWrap.length
      ? `Convert ${reWrap.map(_fSymbol).filter(Boolean).join(", ") || reWrap.map(_fName).join(", ")} into UCITS S&P/Nasdaq wrappers; ` +
        `keeps ${[...keep].join(", ") || "core holds"} untouched and drops situs below the line.`
      : `Re-wrap US-listed exposure into UCITS equivalents to drop situs below the line.`,
    disclaimer: "General NRA rules; no US treaty assumed. Confirm with cross-border tax counsel before acting."
  }];
}

function f_wrapperWithholding(holdings, ctx) {
  const p = ctx.profile;
  if (!p || p.isUSPerson !== false) return [];
  const usFunds = holdings.filter(h => holdingClass(h) === "ETF" && domicileOf(h) === "US");
  if (!usFunds.length) return [];
  const v = usFunds.reduce((a, h) => a + (h.current || 0), 0);
  return [{
    id: "wrapper_withholding", severity: "medium", userDecision: false,
    title: `$${fmt(v)} in US-domiciled funds — 30% dividend withholding vs 15% via UCITS`,
    body: "US-domiciled funds withhold US dividends at 30% for many non-US holders; an Irish UCITS equivalent typically reduces this to 15% and removes US estate situs.",
    valueUSD: v,
    evidence: usFunds.map(h => ({ label: _fName(h), value: `$${fmt(h.current || 0)}` })),
    action: "Prefer the Irish-domiciled UCITS share class of the same index for future buys and re-wraps.",
    disclaimer: "Withholding depends on the holder's treaty position; confirm specifics."
  }];
}

function f_factorConcentration(holdings, ctx) {
  const usLargeCap = ctx.geoAgg?.["US"] || 0;
  const tech = (ctx.sectorAgg?.["Technology"] || 0) + (ctx.sectorAgg?.["Communication Services"] || 0);
  const findings = [];
  if (usLargeCap >= 40) findings.push({
    id: "factor_us_engine", severity: "medium", userDecision: false,
    title: `~${usLargeCap.toFixed(0)}% of the book rides one US large-cap engine`,
    body: "S&P, Nasdaq, income-overlay funds and US single names mostly draw on the same ~30 mega-caps. A US tech drawdown hits most of them at once, regardless of ticker count.",
    valueUSD: Math.round(usLargeCap / 100 * ctx.total),
    evidence: [{ label: "US (look-through)", value: `${usLargeCap.toFixed(0)}%` },
               { label: "Tech + Comms", value: `${tech.toFixed(0)}%` }],
    action: "Treat ticker-count diversification as cosmetic here; diversify by risk factor (size, geography, style), not by adding more US mega-cap lines."
  });
  return findings;
}

function f_ceilingBreach(holdings, ctx) {
  const cap = ctx.profile?.ceilings?.aiTechPct;
  if (cap == null) return [];
  const tech = (ctx.sectorAgg?.["Technology"] || 0) + (ctx.sectorAgg?.["Communication Services"] || 0);
  if (tech < cap - 2) return [];
  return [{
    id: "ceiling_ai_tech", severity: "info", userDecision: false,
    title: `AI/tech ~${tech.toFixed(0)}% is at your ${cap}% ceiling`,
    body: "You have essentially no room to add AI/tech under your own rule. Adding would require trimming elsewhere first — this is the rule working as intended.",
    valueUSD: Math.round(tech / 100 * ctx.total),
    evidence: [{ label: "Tech + Comms (look-through)", value: `${tech.toFixed(0)}%` },
               { label: "Your ceiling", value: `${cap}%` }],
    action: "Park new AI ideas on a watchlist; only add after trimming an existing tech line."
  }];
}

function f_redundancy(holdings, ctx) {
  const out = [];
  const keyOf = n => (n || "").replace(/\b(acc|dist|distributing|accumulating)\b/ig, "")
                              .replace(/\s+/g, " ").trim().toLowerCase();
  const groups = {};
  holdings.forEach(h => { const k = keyOf(_fName(h)); if (k) (groups[k] ||= []).push(h); });
  Object.values(groups).forEach(g => {
    if (g.length > 1 && /s&p|msci|nasdaq|index/i.test(_fName(g[0]))) {
      const v = g.reduce((a, h) => a + (h.current || 0), 0);
      out.push({
        id: "redundant_index_" + keyOf(_fName(g[0])).slice(0, 12).replace(/\s/g, "_"),
        severity: "medium", userDecision: false, valueUSD: v,
        title: `Duplicate index exposure: ${g.map(_fName).join(" + ")}`,
        body: "You hold two share classes of the same index doing the same job. If the goal is growth, the distributing class pays taxable income you may not want.",
        evidence: g.map(h => ({ label: _fName(h), value: `$${fmt(h.current || 0)}` })),
        action: "Consolidate into the accumulating share class unless you specifically need the distributions."
      });
    }
  });
  if (ctx.profile?.returnObjective && /growth|beat/.test(ctx.profile.returnObjective)) {
    holdings.filter(h => /equity premium income|covered call|buywrite|qyld|jepi|jepq/i.test(_fName(h)))
      .forEach(h => out.push({
        id: "income_in_growth_" + _fSymbol(h).toLowerCase(), severity: "low", userDecision: true,
        title: `${_fName(h)} caps upside in a growth mandate`, valueUSD: h.current || 0,
        body: "A covered-call income product trades away upside for yield — the opposite of a pure-growth objective.",
        evidence: [{ label: _fName(h), value: `$${fmt(h.current || 0)}` }],
        action: "Decide deliberately: keep as a volatility dampener, or swap for plain growth exposure."
      }));
  }
  return out;
}

function f_drift(holdings, ctx) {
  if (!ctx.baseline || !ctx.alloc) return [];
  const out = [];
  Object.entries(ctx.alloc.class).forEach(([cls, cur]) => {
    const tgt = ctx.baseline.class?.[cls];
    if (tgt == null) return;
    const gap = cur - tgt;
    if (Math.abs(gap) >= 8) out.push({
      id: "drift_" + cls.toLowerCase(), severity: Math.abs(gap) >= 15 ? "medium" : "info",
      userDecision: true, valueUSD: Math.round(cur / 100 * ctx.total),
      title: `${cls} is ${cur.toFixed(0)}% vs ~${tgt}% target — ${gap > 0 ? "overweight" : "underweight"} by drift`,
      body: `This weight may reflect price drift rather than a deliberate choice. If you'd pick ${cur.toFixed(0)}% on a blank sheet today, keep it; if not, it's a rebalancing candidate.`,
      evidence: [{ label: `${cls} current`, value: `${cur.toFixed(0)}%` },
                 { label: "Baseline target", value: `${tgt}%` }],
      action: `Set an explicit target for ${cls} and rebalance the difference.`
    });
  });
  return out;
}

function f_idleCash(holdings, ctx) {
  const cash = (ctx.classes.Cash || 0);
  if (!cash) return [];
  const buffer = ctx.profile?.nearTermCashNeedUSD ?? Math.min(20000, cash * 0.25);
  const idle = Math.max(0, cash - buffer);
  if (idle < 5000) return [];
  const mmfRate = 0.04;
  return [{
    id: "idle_cash", severity: "medium", userDecision: false,
    title: `~$${fmt(idle)} idle cash earning near 0%`,
    body: "Cash beyond a sensible buffer is an opportunity cost while short-term rates are ~4%.",
    valueUSD: idle, costUSD: Math.round(idle * mmfRate),
    evidence: [{ label: "Total cash", value: `$${fmt(cash)}` },
               { label: "Buffer kept", value: `$${fmt(buffer)}` },
               { label: "Idle", value: `$${fmt(idle)}` }],
    action: `Keep ~$${fmt(buffer)} as buffer; move the rest into a USD money-market / short T-bill fund at ~4%.`
  }];
}

function f_goalStructure(holdings, ctx) {
  const p = ctx.profile;
  if (!p || p.returnObjective !== "beat_benchmark") return [];
  const equity = pctOf((ctx.classes.Equities || 0) + (ctx.classes.ETFs || 0), ctx.total);
  const defensive = 100 - equity;
  if (defensive < 25) return [];
  return [{
    id: "goal_structure", severity: "high", userDecision: true,
    title: `Goal says "beat ${p.benchmark || "the index"}" but ${defensive.toFixed(0)}% is defensive`,
    body: `A book that is ${defensive.toFixed(0)}% in gold/bonds/cash structurally trails an equity index by that block's drag. You can't have maximum safety and index-beating returns from the same book — pick which goal wins.`,
    valueUSD: Math.round(defensive / 100 * ctx.total),
    evidence: [{ label: "Equity (incl. ETFs)", value: `${equity.toFixed(0)}%` },
               { label: "Defensive (bonds/cash/alts)", value: `${defensive.toFixed(0)}%` }],
    action: `Either lift equity toward 70%+ (accepting deeper worst-case drawdown), or change the stated goal to "balanced growth." The engine won't choose for you — but it will hold you to choosing.`
  }];
}

const RULES = [f_usSitusEstate, f_wrapperWithholding, f_factorConcentration,
               f_ceilingBreach, f_redundancy, f_drift, f_idleCash, f_goalStructure];
const SEVERITY_RANK = { high: 0, medium: 1, low: 2, info: 3 };

// Mirror of runFindings()'s core, but taking a hand-built ctx (no app globals).
function runRules(holdings, ctx) {
  const findings = RULES.flatMap(fn => {
    try { return fn(holdings, ctx) || []; }
    catch (e) { console.warn("rule failed", fn.name, e.message); return []; }
  });
  findings.sort((a, b) => (SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity])
                       || ((b.costUSD || 0) - (a.costUSD || 0)));
  return findings;
}

// BASELINE (class dimension only — all f_drift needs). Copied from orion.html.
const BASELINE = {
  Balanced: { class: { Equity: 60, Bonds: 25, Cash: 5,  Alternatives: 10 } },
  Growth:   { class: { Equity: 80, Bonds: 5,  Cash: 3,  Alternatives: 12 } },
};

/* ════════════════════════════════════════════════════════════════════════
   SYNTHETIC PORTFOLIOS
   ════════════════════════════════════════════════════════════════════════ */

// (a) NRA with $105k US-situs (Apple $60k + NVDA $45k, NVDA is a conviction
//     hold) + $40k idle cash + a duplicate S&P pair (Acc + Dist, UCITS).
const holdingsA = [
  { isin: "US0378331005", ticker: "AAPL", asset_type: "stock_etf", current: 60000 },
  { isin: "US67066G1040", ticker: "NVDA", asset_type: "stock_etf", current: 45000 },
  { isin: "IE00B4L5Y983", ticker: "CSP1", asset_type: "stock_etf", current: 25000 }, // S&P UCITS (Acc)
  { isin: "IE00B4L5YX21", ticker: "CSPX", asset_type: "stock_etf", current: 25000 }, // S&P UCITS (Dist)
];
const ctxA = {
  total: 195000,
  classes: { Equities: 105000, ETFs: 50000, Bonds: 0, Cash: 40000, "Real Estate": 0, Crypto: 0, Commodities: 0 },
  sectorAgg: { Technology: 60 }, geoAgg: { US: 80 },
  profile: { isUSPerson: false, convictionHolds: ["NVDA"], ceilings: {}, returnObjective: null, nearTermCashNeedUSD: null },
  baseline: BASELINE.Balanced,
  alloc: { class: { Equity: 79, Bonds: 0, Cash: 21, Alternatives: 0 } },
};

// (b) US-person, growth-shaped (all equity/ETF). Situs rules must stay silent.
const holdingsB = [
  { isin: "US0378331005", ticker: "AAPL", asset_type: "stock_etf", current: 120000 },
  { isin: "IE00B4L5Y983", ticker: "CSP1", asset_type: "stock_etf", current: 80000 }, // UCITS ETF
];
const ctxB = {
  total: 200000,
  classes: { Equities: 120000, ETFs: 80000, Bonds: 0, Cash: 0, "Real Estate": 0, Crypto: 0, Commodities: 0 },
  sectorAgg: { Technology: 60 }, geoAgg: { US: 90 },
  profile: { isUSPerson: true, convictionHolds: [], ceilings: {}, returnObjective: "balanced_growth" },
  baseline: BASELINE.Growth,
  alloc: { class: { Equity: 100, Bonds: 0, Cash: 0, Alternatives: 0 } },
};

// (c) Empty profile — must degrade gracefully (no crash, no profile-gated rule).
const holdingsC = [
  { isin: "US0378331005", ticker: "AAPL", asset_type: "stock_etf", current: 50000 },
];
const ctxC = {
  total: 50000,
  classes: { Equities: 50000, ETFs: 0, Bonds: 0, Cash: 0, "Real Estate": 0, Crypto: 0, Commodities: 0 },
  sectorAgg: {}, geoAgg: {},
  profile: null,
  baseline: BASELINE.Balanced,
  alloc: { class: { Equity: 100, Bonds: 0, Cash: 0, Alternatives: 0 } },
};

/* ════════════════════════════════════════════════════════════════════════
   ASSERTIONS
   ════════════════════════════════════════════════════════════════════════ */
const results = [];
const check = (name, cond) => results.push({ name, pass: !!cond });

// (a)
const fa = runRules(holdingsA, ctxA);
const idsA = fa.map(f => f.id);
check("(a) NRA fires us_situs_estate",            idsA.includes("us_situs_estate"));
check("(a) NRA fires idle_cash",                  idsA.includes("idle_cash"));
check("(a) NRA fires redundancy (duplicate S&P)", idsA.some(id => id.startsWith("redundant_index")));
const situsA = fa.find(f => f.id === "us_situs_estate");
check("(a) us_situs_estate is $105k over $60k line", situsA && /105,000/.test(situsA.title) && /45,000/.test(situsA.title));
// The spec guard: a conviction hold must never appear in a SELL/CONVERT action.
// NVDA may (and should) still show in evidence and in a "keeps NVDA untouched"
// clause — what's prohibited is NVDA being in the list of things to convert.
const convertClauseA = (((situsA && situsA.action) || "").match(/\bConvert\s+(.*?)\s+into\b/i) || [])[1] || "";
check("(a) conviction hold NVDA NOT in the convert list", !/NVDA/i.test(convertClauseA));
check("(a) convert list DOES target the non-conviction name (AAPL)", /AAPL/i.test(convertClauseA));

// (b)
const fb = runRules(holdingsB, ctxB);
const idsB = fb.map(f => f.id);
check("(b) US-person does NOT fire us_situs_estate",   !idsB.includes("us_situs_estate"));
check("(b) US-person does NOT fire wrapper_withholding", !idsB.includes("wrapper_withholding"));

// (c)
let fc = null, crashed = false;
try { fc = runRules(holdingsC, ctxC); } catch (e) { crashed = true; }
check("(c) empty profile does not crash", !crashed && Array.isArray(fc));
check("(c) empty profile fires no situs rules",
  fc && !fc.map(f => f.id).includes("us_situs_estate") && !fc.map(f => f.id).includes("wrapper_withholding"));

/* ── Report ─────────────────────────────────────────────────────────────── */
console.log("\n  Orion findings engine — verification\n  " + "─".repeat(52));
for (const r of results) console.log(`  ${r.pass ? "PASS" : "FAIL"}   ${r.name}`);
const failed = results.filter(r => !r.pass).length;
console.log("  " + "─".repeat(52));
console.log(`  ${results.length - failed}/${results.length} passed${failed ? `  —  ${failed} FAILED` : "  —  all green"}\n`);

// Show what fired in each case, for eyeballing.
const fired = (label, f) => console.log(`  ${label}: ${f.map(x => x.id).join(", ") || "(none)"}`);
console.log("  Rules fired per portfolio:");
fired("(a) NRA           ", fa);
fired("(b) US growth     ", fb);
fired("(c) empty profile ", fc || []);
console.log("");

process.exit(failed ? 1 : 0);
