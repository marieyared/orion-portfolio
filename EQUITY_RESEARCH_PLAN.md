# Orion — Vision & the move into Equity Research

> **North star:** Orion is where a serious self-directed investor **builds and keeps their conviction.**
> You research a company, write down *why* you'd own it, and Orion holds that thesis as living
> memory — pulling the numbers, tracking what changes, and telling you when reality drifts from
> what you believed. Research → conviction → monitoring, fused into one record that compounds.

This doc answers three things: **what the vision actually is** (so you stop feeling like you're
building without one), **why equity research is the move that centers it** (honestly — including
where it's only "good, not spectacular"), and **the plan to get there**, scored against five
startup-evaluator personas with a target of **7.5–8/10**.

It builds directly on `MOAT.md` (history-is-the-moat) and `REFRAME_PLAN.md` (the risk reframe).
It does **not** throw those away — it absorbs them.

---

## 1. The vision problem, named

You feel like you're building without vision because Orion today is a **feature, not a home**:
"a risk warning you glance at." A warning is narrow. It's something a user opens occasionally,
not a place they *live*. Narrow tools get screenshotted once and abandoned — which is exactly
the "wedge with no moat" trap your own `MOAT.md` warns about.

Equity research fixes this not by adding features, but by **changing what Orion is for**:

| From (a feature) | To (a vision) |
|---|---|
| A risk widget you check | The place you do your investing *thinking* |
| "We warn you what breaks your portfolio" | "We hold your conviction and tell you when it's wrong" |
| Passive — you glance, you leave | Active — you research here, so your work lives here |
| Risk history is the only record | Your **research and theses** are the record (a far stickier one) |

Risk-monitoring doesn't disappear. It becomes **one module** inside the research home — the
"is my thesis still intact?" part. That's the upgrade: same user, same moat principle, a much
bigger and more central reason to exist.

## 2. Do I actually believe equity research serves the vision? (honest)

**Yes — with conditions.** Here's the real case, not a pep talk.

**Why it's right:**
- It reuses your single best strategic asset. `MOAT.md` already says the moat is *the user's own
  accumulated record that a fresh competitor can't reproduce.* A **living research/thesis library**
  is a stronger version of that than risk-history alone — it's where the user's judgment lives, and
  judgment is the most painful thing to leave behind.
- It's the same user you already chose (mass-affluent, self-directed) and the same distribution
  (one niche community). You're deepening a wedge, not opening a new front.
- It passes your own "survives Claude" test cleanly (see §5). Risk-warning was always a thin
  surface; research-with-memory is genuinely defensible.
- It gives you a one-sentence vision you can say out loud and build against — which is the thing
  you said is missing.

**Where it's only good, not spectacular (so you go in clear-eyed):**
- The space has real, funded incumbents (Koyfin, Seeking Alpha, Simply Wall St, Finchat). You
  **cannot** win "a research tool for everyone." The vision only works if it's narrow (§4, §6).
- It's a durable, cash-flowing software business — not a venture rocket. Given you want
  sustainable ~$10k/month and low drama, that's a feature, not a bug. But don't expect a persona
  panel to score it a 10 on "scale"; aim for the strong, honest 7.5–8.

**The honest verdict:** equity research is the right move *if* you accept that the vision is
"**the conviction workspace for one specific kind of investor**," not "a better Bloomberg." Narrow
is the whole strategy. If you're in on narrow, I believe in it.

## 3. "It can't be for everyone" — who it's for

Lifted from `MOAT.md` and sharpened: **serious, self-directed, fundamentals-driven investors**
who do real homework — roughly the mass-affluent investor with a complex book, *and* the
prosumer who invests by a clear philosophy. Pick **one tribe and one philosophy** to build the
opinionated workflow around (recommended default: **quality / long-term compounder investors** —
ROIC, owner-earnings, moat, management quality), reached through **one niche community**
(FatFIRE/ChubbyFIRE, Bogleheads-adjacent, a specific finance circle). The philosophy you choose
*is* the product's point of view — it's what makes the workspace opinionated instead of a neutral
terminal anyone can clone.

> Decision needed from you: which tribe/philosophy, and which single community. This choice drives
> the entire opinionated workflow and the first 100 users.

## 4. The repositioning (what leads, what supports)

| Layer | Role | Status |
|---|---|---|
| **Equity research workspace** | The new front door — research a company, build a thesis | **Promote to hero** |
| **Living thesis memory** | Orion remembers *why* you own things and your own rules | **New — the heart of the moat** |
| **Risk / "what breaks you" monitoring** | "Is my thesis still intact?" — the existing engine | **Demote to a module** (keep, don't lead) |
| Net-worth / holdings table, treemap, prices | Plumbing that feeds the workspace | Keep as support |

## 5. The moat, extended (and the survives-Claude rule)

`MOAT.md`'s rule stands and gets sharper: **every AI feature must lean on data a fresh competitor —
or a fresh Claude session — cannot reproduce.**

- **Commodity (don't sell this):** "summarize this 10-K," "explain this business." Claude does it.
- **Moated (the product):** *"This contradicts the thesis you wrote in March — you said you'd
  exit if gross margin fell below 60%; this quarter it printed 57%."* Only Orion can say that,
  because only Orion holds your thesis and the history. The library of your living research is the
  switching cost.

The defensible core is **persistent, structured, updating research tied to the user's own
judgment** — not generated prose. If a brand-new install could produce the identical output, it's
a wedge feature, not the moat.

## 6. Wedge vs. moat (the two layers, applied to research)

| | Acquisition wedge (day one) | Retention moat (compounds) |
|---|---|---|
| **What** | The AI auto-assembles a clean, opinionated deep-dive on any company in minutes — the homework, done | Your thesis library + Orion tracking each thesis against live results over time |
| **Job** | Deliver value before any history exists — earn the first click from the community | Make leaving mean losing your accumulated conviction record |
| **Claude-proof?** | Partly (the *speed + opinionated structure* is the edge, not the text) | Fully (your own accumulated judgment can't be re-prompted) |

## 7. AI-cost architecture (a first-class design principle)

Research content is **shared, not personal** — so design for it, or credits will eat the margin:
- **Compute once, serve many.** Generate each company's dossier once per filing, cache it, serve
  it to all users. Cost scales with *companies covered × filing calendar*, not with users.
- **Code, not AI, for structured data.** Financials, ratios, charts, guidance diffs = deterministic
  from EDGAR / a cheap fundamentals API. Reserve AI for the language tasks only.
- **Small models for the grunt work**, the good model only where judgment quality shows.
- **Meter the per-user part** ("ask anything about this name") with retrieval + caps on free tier.

Target: at ~$10k MRR, inference is a low-hundreds-per-month line item, not a per-user bleed.

## 8. Data stance (extends MOAT.md §6)

Stay free-first and **US-first**: SEC EDGAR for filings (free), a cheap fundamentals API for
statements, free price/FX sources. Skip expensive real-time and transcript feeds until retention
is proven. Bridge credibility with honest provenance labels, exactly as the risk product already
does. Buy accuracy later, only where the user sees it.

## 9. Roadmap (done-when, sequenced)

1. **Pick the tribe + community** → *the opinionated workflow has a clear point of view and a first
   100 target users.* (Decision, not code.)
2. **Dossier MVP** → *add a ticker, get an auto-assembled, opinionated deep-dive (financials,
   business, risks, guidance changes) from EDGAR + a free fundamentals source — cached.*
3. **Thesis capture** → *the user writes why they'd own it and their own rules; it's saved and tied
   to the company.* (This is the moat's seed — ship it early.)
4. **Thesis-vs-reality alerts** → *when a company reports, Orion flags what changed against the
   user's written thesis.* (The "only Orion can say this" moment.)
5. **Fold risk in as a module** → *the existing "what breaks you" engine becomes "is your thesis
   still intact across the portfolio."*
6. **One community launch** → *ship to the chosen niche; measure whether they research a second
   company and come back next week.*

## 10. The gate (apply to every feature)

> **"Does this deepen the user's research record, the trust in it, or the AI's ability to reason
> over it — in a way a brand-new user or a fresh Claude session could not reproduce?"**
> If no, it's a wedge feature at best. Ship wedge features to acquire; ship moat features to keep.

---

## 11. The 5-persona scorecard

Five evaluators rate the startup 0–10. I show **today** (scattered, "building without vision") vs.
**after this move, executed**, with the honest reason. (If you have a specific 5-persona rubric in
mind, tell me and I'll re-score against it.)

| Persona (what they care about) | Today | After this move | Why |
|---|---|---|---|
| **1. The Investor** — durable demand, defensibility, why-now | 5.5 | **7.5** | A real compounding moat (thesis library) and a clear "why now" (AI makes deep research fast). Capped below 9 because it's a durable cash-flow business, not a venture rocket — which matches your goal. |
| **2. The Target Customer** (serious self-directed investor) — real pain, will I pay, will I stay | 6 | **8** | Research is fragmented across tabs and spreadsheets; a fast, opinionated, *remembering* workspace is a real "yes, and I'll pay $20–40/mo." Retention rises because their work lives there. |
| **3. The Incumbent / Competitor** (Koyfin, Seeking Alpha, Finchat) — can we crush you | 4.5 | **7.5** | The narrow tribe + opinionated philosophy + the user's own thesis memory is the lane they don't serve. Not a 9: they're funded and could copy features — your defense is focus and the personal record, so you must stay narrow. |
| **4. The Builder / CTO** — solo-buildable, unit economics, time-to-MVP | 6 | **8** | Reuses your Orion stack; the AI-cost problem is solved by caching (§7); EDGAR-first keeps data cheap. A genuinely one-person MVP. |
| **5. The Skeptic / "just use Claude"** — is the moat durable against AI | 5 | **8** | This is the move's strongest axis: research-with-memory-and-your-own-rules is exactly what a stateless model can't reproduce. The vision is now focused, not scattered. |

**Average: ~5.4 → ~7.8.** The move clears your 7.5–8 minimum **on the condition that you stay
narrow** (one tribe, one community) and **hold the gate** (§10). The two scores most at risk are
the Investor and the Competitor — both rise or fall on focus, not features. Scatter the product to
"everyone" and they drop back toward 5; that is precisely the failure mode you named.

---

### The honest summary
Equity research is the right move because it stops Orion being a risk widget and makes it the one
thing a serious investor's work *lives inside* — research, conviction, and risk fused into a record
that compounds and can't be re-prompted. That cures the "no vision" feeling by forcing a single
north star and a single user. It is a strong, durable 7.5–8 business — not a moonshot — and it only
stays a 7.5–8 if you resist the urge to serve everyone. Pick the tribe, hold the gate, and build the
memory before the features.
