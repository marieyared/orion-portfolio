# Orion — The Reframe (Phase 1)

> ⚠️ **Superseded by `EQUITY_RESEARCH_PLAN.md`.** Orion's whole-product direction is now the
> equity-research / conviction workspace. This document still governs the **risk module's**
> positioning and copy — but "risk is the hero" now reads as "risk is one module," and the
> kill-list below applies to that module, not to the new research features. Read
> `EQUITY_RESEARCH_PLAN.md` first.

> **North star:** "Orion tells you what breaks your portfolio — before it breaks it."
> Orion is a **risk early-warning system**, not a net-worth tracker. This phase is copy,
> layout, hierarchy, and the AI-briefing prompt — **no new features, no auth/data-layer work.**

## The gate (apply to every change)
**"Does this help someone see or avoid a portfolio risk?"** If no, don't ship it — no matter how cool.

---

## 1. Positioning shift (stop leading with the left, start leading with the right)
| From — stop being | To — become |
|---|---|
| A dashboard you glance at | A warning you can't ignore |
| "Your wealth, intelligently understood" | "What breaks your portfolio — before it does" |
| Net worth / balances / holdings up front | Risk, exposure, "what breaks you first" up front |
| Serves "everyone with a portfolio" | Serves the serious investor who is *afraid* |
| AI says good morning | AI flags the risk building this week |

## 2. New copy (paste-ready)
- **Hero headline:** "Know what breaks your portfolio — before it breaks it."
- **Sub-headline:** "Add your holdings. Orion stress-tests them against every crisis that matters and tells you, in dollars, what to fix first." *(No account linking yet — holdings are entered manually / via CSV. Don't promise "connect.")*
- **Primary button:** "Stress-test my portfolio" (not "Get started" / "View dashboard")
- **Section renames:** "Overview" → **"What breaks you first."**  "Intelligence" → **"Your weekly risk warning."**

### The AI briefing — highest-impact rewrite
- **Before (a glance):** "Good morning. Your portfolio is worth $182,853, up 0.4% today. Largest asset class is ETFs."
- **After (a warning):** "Emerging risk this week: your tech concentration just crossed 38% — the same exposure that lost 31% in 2022. A repeat would cost ~$56,000. Here's the one trade that cuts it most."
- **Important:** the numbers must be **computed by the existing risk/findings engine and fed into the prompt**, not hardcoded. The briefing should pull the top risk + dollar impact from the engine, then have the AI narrate it.

## 3. Promote / Demote / Delete
**Promote (top billing):**
1. The Risk Engine — "what breaks you first," ranked by $ impact (Stress Lab, factor exposure, concentration, **hidden overlap**, rate-sensitivity). This *is* the product.
2. The Warning Briefing — the reframed AI above.
3. Memory & Trust — persistence + reliable data (so risk can be tracked over time).

**Demote (keep as plumbing that feeds risk, never the hero):** net-worth/holdings table; Wealth-Map treemap (concentration lens only); income calendar & performance; CSV import.

**Delete (cut now / never build):** "track/glance at your wealth" framing; live market charts & index browsing; tax/estate findings *as a headline*; any new asset class or analytic that doesn't end in a *warning*; "for everyone" copy; **a "potential reward" / risk-adjusted / composite risk-reward rating or star score** — it turns Orion into a screener/robo-advisor (commoditized, advice-regulated, and a dilution of the warning identity). The moat is the discipline, not the feature surface.

## 3a. The one scoring addition worth making: hidden overlap
We considered going further into "financial scoring" (rating risk, reward, overlap). Run each through the gate:
- **Hidden overlap → build it.** The risk people *cannot* see for themselves: five ETFs that are 58% the same ten mega-caps. "Your diversification is an illusion — your true single-name concentration is X%, and a tech repeat would cost ~$Y." It's a *warning*, it's differentiated, no brokerage hands it to you, and it leans on look-through aggregation the app already computes (sector/geo). Promote it as a first-class risk lens.
- **A second composite risk score → don't.** We already have a health score. Another abstract number competes with the dollar figure that makes the warning land. Keep **dollars as the lede; any score is the at-a-glance summary that drills into them**, never the headline.
- **Reward / risk-adjusted rating → never (see kill-list).** The moment Orion rates "reward potential" it stops being a warning system and becomes a robo-advisor.

**Discipline:** every scoring surface must end in a dollar-denominated warning + one action. A number that doesn't is a tracker metric in disguise — cut it.

## 4. One-week checklist (done-when)
1. Rewrite landing hero + subhead + button → *"Stress-test" is the first thing a new visitor sees.*
2. Make the Risk Engine the default view on load → *App opens on "what breaks you first," not net worth.*
3. Re-prompt the AI briefing into the Warning Briefing → *Briefing leads with a risk + a $ figure + one action.*
4. Demote holdings/treemap/income to secondary tabs → *No "glance at your wealth" content above the fold.*
5. Delete the kill-list items → *Markets browsing & tax headline are gone.*
6. Rename sections to risk language → *Nav reads as a risk tool, not a tracker.*
7. One-line app/link-preview description → *It says "risk," not "net worth."*

## 5. How you'll know it worked
Ship it, show 10 target users (serious self-directed investors who fear the next crash). Look for: (1) they lean in at the headline, (2) they ask "what would a 2022 do to me?" unprompted, (3) they want to be told when a risk crosses a line. Only then invest in Phase 2 (accounts, persistence, reliable data).

---
*Suggested Claude Code workflow: `git commit` current state first → do tasks 1–7 as separate prompts → review each diff → paste the gate (above) into each prompt so it doesn't add features.*
