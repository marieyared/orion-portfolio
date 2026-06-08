# Orion — The Moat

> **North star:** A competitor can clone the overlap lens or the warning UI in a weekend.
> They cannot clone two years of a specific user's risk history. **Time is the moat.**

Early on we have no moat — that's expected. This doc is the moat we are deliberately
building *toward*, and the bets that get us there. Apply it as a tiebreaker: when two
roadmap items compete, ship the one that deepens the history-and-trust moat.

---

## 1. The thesis (one sentence)
Orion's moat is a **longitudinal, trustworthy record of an affluent investor's portfolio
risk over time**, narrated by an AI that has that entire history as context. The value
compounds daily and leaving means losing the record.

## 2. Who it's for (the wedge)
**Mass-affluent, self-directed investors** — roughly $200K–$1M in the tracked account,
~$5M total net worth. They can pay a flat subscription, they *expect* accuracy, and their
books are complex enough that risk (especially hidden overlap) is not obvious to them.
Reach them through **one deliberately chosen niche community** (e.g. FatFIRE / ChubbyFIRE,
Bogleheads, select finance circles) — not broad paid acquisition. The community choice is
half the distribution moat.

## 3. The two layers (do not confuse them)
| Layer | What it is | Job |
|---|---|---|
| **Acquisition wedge** (day one) | The hidden-overlap + dollar-warning insight | Deliver value *before any history exists* — earns the first click from the community |
| **Retention moat** (compounding) | The risk-history timeline + the trust that the numbers are right | Make leaving costly; make the AI smarter the longer they stay |

A wedge with no moat is a toy people screenshot once and leave. A moat with no wedge never
starts (a new user has zero history on day one). We need both, built and marketed differently.

## 4. The moat inputs, ranked
1. **Risk-history tracking over time** — the longitudinal record. This *is* the switching
   cost and the retention hook in one. Highest priority; it compounds from the first session.
2. **Trust that the numbers are right** — see the data stance below. History no one believes
   is worthless, so credibility is a precondition for the history moat, not a separate feature.
3. **History-aware AI** — the defensible version of the AI hook (see §5).
4. **The niche community** — distribution that competitors don't notice early.

## 5. Why the AI is defensible (and the trap)
Raw AI is a commodity — anyone calls the same model. Orion's AI is defensible **only when it
reasons over the user's own accumulated history**, not generic macro. The trap is "research +
contextualize" that just summarizes this week's news — anyone can do that. The moated version:

> *"Your tech exposure is now higher than at any point in the last 18 months — the same setup
> that would have cost you $X in 2022."*

Only Orion can say that, because only Orion has the history. **Rule: every agentic/AI feature
must lean on data a fresh competitor cannot reproduce.** If a brand-new install could produce
the same output, it isn't a moat.

## 6. Data stance — *no paid APIs yet* (deliberate)
Trustworthy data is pillar #2 of the moat, but **we are not paying for institutional data now —
it's too early.** Near-term stance:
- **Stay on free sources** (Yahoo via yfinance, CoinGecko, metals, ECB FX, FMP free tier).
- **Bridge the credibility gap with honesty, not spend** — the existing provenance / data-confidence
  surfaces ("9 of 12 positions live · 2 fallback · 1 manual", floor-estimate labels) are the
  cheap substitute for paid accuracy. Keep and strengthen them.
- **Institutional / paid data is a *later* phase** — revisit only once retention is proven and
  revenue justifies it. When we do, buy accuracy where the user sees it (prices, fund
  constituents), not prestige; a mid-tier source likely gets ~95% of the credibility at a
  fraction of the cost.

## 7. Monetization
**Flat subscription.** Simple, fits mass-affluent willingness to pay. (Trade-off vs. freemium:
weaker top-of-funnel, so the community wedge has to carry acquisition.)

## 8. The gate
For any new feature, ask: **"Does this deepen the risk-history record, the trust in it, or the
AI's ability to use it?"** If a brand-new user with no history would get the identical result,
it is not building the moat — it's a wedge feature at best. Ship wedge features to acquire;
ship moat features to keep.

---
*Companion to `REFRAME_PLAN.md` (positioning) and `CLAUDE.md` / `AGENTS.md` (build rules).*
