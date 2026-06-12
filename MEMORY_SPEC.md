# Orion — The Memory Loop (mechanism spec)

> The one thing a chat can never be is *you over time*. This spec defines the loop that makes
> Orion irreplaceable: **capture the why → store it (versioned) → watch reality → fire on
> divergence.** Everything here is buildable against what Orion already has (`localStorage`,
> the dossier scorecard, the price API, the risk/findings engine). The model only ever
> *phrases* the output — the moat is the data, the capture moment, and the watch.

---

## 1. Capture — what gets recorded at buy time

When a user adds (or adds to) a holding, Orion captures a **thesis record**. Two halves: the
financial case and the psychology. The trick that makes it checkable later is that each
*reason* is tied to a metric the engine already tracks.

```json
{
  "ticker": "NVDA",
  "created_at": "2026-06-12T14:03:00Z",
  "price_at_entry": 118.40,
  "weight_at_entry": 0.08,
  "horizon_years": 5,

  "pillars": [
    { "claim": "Revenue keeps growing >15%/yr", "metric": "revenue_growth_yoy", "op": ">=", "threshold": 15, "status": "holding" },
    { "claim": "Operating margin stays above 25%", "metric": "operating_margin", "op": ">=", "threshold": 25, "status": "holding" }
  ],

  "sell_rules": [
    { "rule": "Rev growth < 8% for two straight quarters", "metric": "revenue_growth_yoy", "op": "<", "threshold": 8, "consecutive_q": 2 },
    { "rule": "I'd sell if the AI-compute story stops being the growth engine", "metric": null, "manual": true }
  ],

  "psychology": {
    "conviction": 5,                       // 1–5
    "why_really": "Believe AI compute demand is structural, not a cycle.",
    "what_im_afraid_of": "That I'm buying the top on hype.",
    "emotion_tags": ["high-conviction", "some-FOMO"]
  }
}
```

Design rules for capture:
- **Pillars must be falsifiable.** 1–3 short claims, each mapped to a metric key the dossier
  scorecard already computes where possible (`revenue_growth_yoy`, `operating_margin`, `roic`,
  `fcf_margin`, …). A pillar with no metric is allowed but flagged `manual` (checked by prompt,
  not math).
- **Sell rules are pre-committed exit conditions** — the user's own line in the sand, set
  while calm. These are the highest-value signal in the whole system.
- **Psychology is required, not optional** — even one sentence. It's the half a chat can never
  reconstruct, and the half that powers behavioral feedback later.
- **Capture must be near-frictionless.** Smart defaults from the dossier (pre-fill suggested
  pillars from the scorecard; user edits/confirms). If this feels like homework, the moat
  dies. This is the make-or-break of the whole product.

---

## 2. Store — versioned, append-only

- MVP persistence: `localStorage`, keyed per holding: `orion.thesis.<TICKER>`.
- Each holding owns a **`thesis_history[]`** array. Records are **immutable and timestamped.**
- Editing a thesis **appends a new version**; it never overwrites. The history of *how your
  conviction changed* is itself part of the moat — "you downgraded conviction 5→3 in Jan, then
  bought more in March."
- The current thesis = last entry. Older entries stay for the timeline and for divergence
  context.

> Why this can't be a chat: the record is proprietary, longitudinal, and structured. A cold
> session has none of it. A smarter model doesn't conjure data it was never given.

---

## 3. Watch — the reality feed

Reality signals Orion already has or can compute, each mapped to the metric keys used in
pillars/sell rules:

| Signal source | Examples | Already in repo |
|---|---|---|
| Price / return | drawdown, return since entry | `orion_api.py` |
| Fundamentals + quality scorecard | revenue growth, margins, ROIC, FCF | `dossiers/*.json`, `build_dossiers.py` |
| Risk / findings engine | concentration, factor exposure, crisis breaks | `orion.html` engine |
| *(later)* news / filings | guidance cuts, 8-K events | not yet |

The watch runs on app open (MVP) and later on a schedule. For each holding it pulls the
current value of every metric referenced by a pillar or sell rule.

---

## 4. Fire — the divergence check

For each pillar / sell rule, compare **stored conviction** against **current reality** and
assign a state:

- **Holding** — condition still true. (Silent.)
- **Watch** — drifting toward the line (e.g. within 10% of a threshold, or 1 of 2 required
  quarters met). (Soft surface.)
- **Broken** — a pillar is falsified or a pre-committed **sell rule fires.** (Alert.)

An alert is raised when a pillar flips to Watch/Broken or a sell rule triggers. `manual`
pillars (no metric) are evaluated by an AI prompt that is *fed the computed numbers* — never
left to summarize freely.

**The message is a mirror, not a critic.** It always quotes the user's own past words + the
pre-committed rule + the computed number, and stops. It does not tell them what to do.

> *"In Mar 2026 you bought NVDA because 'operating margin stays above 25%' (conviction 5/5).
> Latest: 24%, second quarter below your line. You wrote: 'sell if it falls below 25%.' That's
> your rule, not ours. Revisit, or amend the thesis?"*

And the psychology tie-in, gently:

> *"You also flagged 'some-FOMO' as a reason here. Two of your three pillars have since moved to
> Watch. Worth a look at whether the original case still holds."*

Mirror rules: quote their past self; show the number; name the rule they pre-committed; never
editorialize or instruct; offer "amend thesis" as a first-class action (with the change
versioned, per §2).

---

## 5. Why this is irreplaceable (the gate, satisfied)

A cold Claude chat (a) has **no stored versioned record** of what you believed and when,
(b) **wasn't present at capture** to record the real why and the pre-committed sell line, and
(c) **isn't running the periodic check** that compares your past conviction to a live metric
feed. None of those three are *intelligence* — so a smarter model makes them *more* valuable,
not redundant. The model is the phrasing layer; Orion owns the data + the moment + the watch.

---

## 6. Build order (MVP → later)

**MVP (the loop, end to end, thin):**
1. Capture form at add-holding: pillars (pre-filled from scorecard), sell rules, conviction +
   one-line why + one-line fear.
2. Versioned `localStorage` store (§2).
3. On-open watch against the **metrics the dossier scorecard + price API already provide.**
4. Divergence states + alert on sell-rule breach / pillar break, phrased as a mirror.

**Later:**
- News/filing signals; drift/trend detection; scheduled (push) checks.
- Cross-holding psychology patterns ("you've panic-sold after a 20% drawdown 3 times").
- Thesis-overlap view ("12 names, 3 real bets") built on the same pillar data.

**The single make-or-break:** will a user tell Orion the truth at capture? If yes, the moat
compounds. If no, there's no data and Orion is a wrapper. Everything else is secondary to
making step 1 effortless and worth doing.
