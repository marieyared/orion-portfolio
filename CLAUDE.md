# Orion — project guide for Claude Code

Orion is a **single-page equity-research / conviction workspace** (risk monitoring is one module
inside it). The entire frontend is one static file: `orion.html`. Two small backends support it.
Keep the single-file architecture — do not split `orion.html` into modules.

## Companion docs (read the one that matches your task)
| Doc | Answers | Read when |
|-----|---------|-----------|
| `EQUITY_RESEARCH_PLAN.md` | **Vision & direction** — the conviction workspace (current source of truth; absorbs MOAT + REFRAME) | Any strategy, scope, or roadmap call |
| `README.md` | What Orion is; how to run & deploy | Setting up or deploying |
| `MOAT.md` | **Differentiation** — the history-is-the-moat principle (still holds; now applied to the research record) | Prioritising features / strategy calls |
| `REFRAME_PLAN.md` | **Positioning of the risk module** — superseded as whole-product positioning | Working on the risk module's copy/hierarchy |
| `CLAUDE.md` (this file) | **Build rules** — how to work in the code | Any code change (this is the canonical guide) |

## Active goal
Execute the **EQUITY_RESEARCH_PLAN.md roadmap (§9)**: evolve Orion from a risk widget into an
**equity-research / conviction workspace** — research a company, write the thesis + sell rules, and
have Orion track reality against it. Sequence: **dossier MVP → thesis capture → thesis-vs-reality
alerts → fold risk in as a module.** Risk monitoring stays, demoted to one module.

Apply this gate to every change: **"Does this deepen the user's research record, the trust in it, or
the AI's ability to reason over it — in a way a brand-new user or a fresh Claude session could not
reproduce?"** If no, it's a wedge feature at best — ship wedge features to acquire, moat features to keep.

Locked decisions (see `EQUITY_RESEARCH_PLAN.md` + project memory): tribe = quality/long-term
compounders; data = SEC EDGAR + FMP, US-first (warn on non-US holdings); dossiers = pre-generated
static JSON committed to the repo (cache-once-serve-many — never a per-user model call); MVP
persistence stays `localStorage` (accounts/sync are a later phase); the investing philosophy lives
in one isolated, swappable place so the workflow is opinionated but the tribe can be changed.

## Source files (the only things to edit)
| File | What it is |
|------|------------|
| `orion.html` | The whole app — UI, state, risk/findings engine, prompts. Edit here. |
| `orion_api.py` | Python pricing API (OpenFIGI ISIN lookup + Yahoo Finance quotes). |
| `worker.js` | Cloudflare Worker proxying the Anthropic API (keeps the key off the browser). |
| `test_findings.mjs` | Node test for the findings engine. Run before wiring findings into the live prompt. |
| `wrangler.toml`, `Dockerfile`, `requirements-api.txt` | Deploy/config. |

## Do NOT read or edit for this work
- `docs/` — human reference only (reviews, specs, screenshots, sample CSVs, old versions). Not source.
  Notable: `docs/orion_expansion_spec.html` (a *separate*, deferred direction — the findings/advisory
  engine; ignore it for the reframe), `docs/deliverables/` (review PDFs), `docs/samples/` (test CSVs),
  `docs/archive/` (old builds).

## Workflow
1. `git commit` before starting.
2. Do the `EQUITY_RESEARCH_PLAN.md` §9 roadmap as **separate prompts**, reviewing each diff.
3. Every AI feature must pull computed numbers from the engine (risk/findings, fundamentals) — never
   hardcode — and must lean on the user's own accumulated record (thesis/history), never generic
   summarization a fresh Claude session could reproduce.
