# Orion — Positioning (single source of truth)

> This file supersedes and reconciles every earlier positioning statement. Where
> `README.md`, `CLAUDE.md`, or any older plan disagree with this document, **this wins.**
> Orion has been described three different ways across the repo (a *risk early-warning
> system*, an *equity-research / conviction workspace*, and informally as *beginner
> financial education*). Those were not three products. They were three names for one job,
> discovered in stages. This document states the job once, plainly.

## One sentence

**Orion helps you understand what you own and why** — company by company, and across your
whole portfolio.

And the part that makes it *not generic*:

> **Orion remembers why you bought — and tells you when reality stops agreeing.**

The first sentence is the wedge (it gets people in the door). The second is the moat (it's
what no competitor can copy, and what keeps people). See *What makes Orion unique* below.

## The job

Most tools either *advise* you (build you a portfolio, tell you what to buy) or *educate*
you (generic articles about what a P/E ratio is). Orion does neither. Orion **illuminates**:
it takes the holdings you already have and the companies you already care about, and makes
them legible — the thesis behind each name, and the shape and risk of the whole book.

The posture is *explain, don't advise*. That single choice resolves the old confusion:
the "education" instinct was never a separate product — it was this comprehension posture,
aimed at the user's own portfolio instead of at generic content.

## Two zoom levels (one product)

- **Per-company — the "why."** Equity research: the dossier, the quality-compounder
  scorecard, and the user's own written thesis and sell rules. This is the depth.
- **Portfolio-wide — the "what and the risk."** What you actually hold, look-through
  exposure, and where it breaks first. This is the breadth.

Same job — *understand what you hold and why* — at two levels of zoom.

## The front door (decided)

**Understanding leads. Research deepens it.**

A first-time user opens Orion onto *"here's what you own and what's risky about it"* — the
low-barrier, high-comprehension view. Equity research is the second thing they discover, and
it's what makes the understanding *deep* instead of generic. Risk monitoring is **one lens
inside understanding**, not the headline product. (This is the deliberate correction to the
old README, which led with "the product is the warning." The product is the *understanding*;
the warning is one expression of it.)

## Who it's for

Investors who pick their own quality, long-term compounders and want to genuinely understand
their holdings — not be told what to buy, and not be fed beginner content they could get
anywhere. US-first (non-US holdings get a warning).

## What makes Orion unique (the memory)

At the feature level, Orion is **not** unique — "understand your portfolio + equity research"
is a crowded shelf (Morningstar, Seeking Alpha, Simply Wall St, Sharesight, and more). Any of
them could clone Orion's screens in a quarter. Features are never the moat.

Uniqueness comes from one thing a competitor cannot get even by cloning every screen: **the
user's accumulated record of their own conviction, over time.** Orion's differentiator is the
*time axis* — it holds your *present* portfolio accountable to your *past* thinking.

Two layers make this real:

- **The psychology of the buy.** At purchase, Orion captures not just the financial case but
  the human one: what you actually believed, what you feared, and what would have to be true
  for you to sell. This is the reasoning every investor forgets first and needs most.
- **The divergence alert.** Over time, the AI compares that recorded conviction against
  reality and surfaces when they part ways — *"you bought this for three reasons; two have
  broken, and you haven't acknowledged it."* Orion becomes a **behavioral accountability
  mirror**: it shows you your own past self, so you sell on broken theses instead of panic and
  hold on intact ones instead of ego.

Why this is defensible: it isn't a feature, it's *your history.* A competitor launching
tomorrow starts every user at zero. After a year, Orion has each user's year of theses, sell
rules, and reasoning — which compounds and cannot be reproduced.

The two hard problems this creates (and the real product work):

1. **Capture must be frictionless.** If logging the real reasoning — especially the emotional
   why — feels like homework, there's no memory to reason over later. Making capture nearly
   effortless at buy time is the central design challenge.
2. **The divergence message must feel like a mirror, not a critic.** It lands on someone who
   is often emotional about money and invested in being right. It has to feel like the user's
   own past self talking to them, not an accusation. That voice is itself part of the moat.

The catch: this moat is *latent*. It's worth almost nothing on day one (no history yet) and
nearly everything by month twelve. So the governing design question is: **make day one
valuable enough — via the understanding wedge — that users stay long enough for the memory to
thicken.**

## What Orion is NOT

- **Not an advisor** — it does not build portfolios or issue buy/sell recommendations.
- **Not generic financial education** — every insight is grounded in *your* holdings and
  *your* written record, never content a fresh session could reproduce.
- **Not "just a risk widget"** — risk is one module inside the larger understanding workspace.

## The moat gate (unchanged — this still governs the roadmap)

Apply to every feature: **"Does this deepen the user's research record, the trust in it, or
the AI's ability to reason over it — in a way a brand-new user or a fresh session could not
reproduce?"** If no, it's a wedge feature (good for acquiring) not a moat feature (what keeps
people). The accumulated, personal record — theses, sell rules, history — is the defensible
asset. Comprehension of *your* portfolio is defensible; explaining a P/E ratio is not.

## Locked decisions (carried forward)

- **Tribe:** quality / long-term compounders. Lives in one isolated, swappable place so the
  workflow is opinionated but the tribe can be changed.
- **Data:** SEC EDGAR + FMP, US-first.
- **Dossiers:** pre-generated static JSON committed to the repo (cache-once-serve-many —
  never a per-user model call).
- **Persistence:** `localStorage` for the MVP. Accounts / sync are a later phase.
- **Architecture:** single static frontend (`orion.html`) + two small backends. Do not split.

## The next move (not a build task — a reality check)

The direction is no longer the blocker; evidence is. Ship the smallest version of *"understand
what you own"* to ~5 people who pick their own stocks, and watch where they get confused or
bounce. That tells you what "more useful" actually means — which is unknowable from inside the
build.
