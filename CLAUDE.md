# Orion — project guide for Claude Code

Orion **helps you understand what you own and why** — company by company, and across your whole
portfolio. Understanding is the front door; equity research deepens it; risk monitoring is one
module inside it (no longer the headline). The entire frontend is one static file: `orion.html`.
Two small backends support it. Keep the single-file architecture — do not split `orion.html` into
modules.

The differentiator (the moat) is **memory**: Orion remembers *why* you bought — the financial case
and the psychology behind it — and tells you when reality stops agreeing. See `POSITIONING.md`.

## Companion docs (read the one that matches your task)
| Doc | Answers | Read when |
|-----|---------|-----------|
| `POSITIONING.md` | **Single source of truth** — what Orion is, who it's for, what makes it unique (wedge vs. moat), what it's NOT | Any strategy, scope, positioning, or roadmap call |
| `README.md` | What Orion is; how to run & deploy | Setting up or deploying |
| `CLAUDE.md` (this file) | **Build rules** — how to work in the code | Any code change (this is the canonical build guide) |

> Earlier strategy docs (`EQUITY_RESEARCH_PLAN.md`, `MOAT.md`, `REFRAME_PLAN.md`) are retired and no
> longer in the repo. `POSITIONING.md` absorbs and supersedes them. If anything here conflicts with
> `POSITIONING.md`, that doc wins.

## Active goal
Build the **understand-what-you-own** product: a per-company view (dossier + the user's own thesis
and sell rules) and a portfolio-wide view (holdings, look-through, risk). Sequence: **dossier MVP →
thesis + psychology capture → thesis-vs-reality (divergence) alerts → fold risk in as a module.**
Understanding leads (the acquisition wedge); the accumulating personal record retains (the moat).

Apply this gate to every change: **"Does this deepen the user's research record, the trust in it, or
the AI's ability to reason over it — in a way a brand-new user or a fresh Claude session could not
reproduce?"** If no, it's a wedge feature at best — ship wedge features to acquire, moat features to keep.

Locked decisions (see `POSITIONING.md` + project memory): tribe = quality/long-term
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
| `build_dossiers.py` | **Dossier generator.** Pulls SEC EDGAR XBRL, computes the quality-compounder scorecard deterministically (no model call), and writes `dossiers/*.json` + `dossiers/dossiers.js`. Re-run when the covered universe or a filing changes. |
| `dossiers/` | **Pre-generated, committed** company dossiers (cache-once-serve-many). `*.json` = canonical per-name data; `index.json` = coverage manifest; `dossiers.js` = `window.ORION_DOSSIERS` bundle that orion.html loads (file://-safe). Generated — edit `build_dossiers.py`, not these. |
| `test_findings.mjs` | Node test for the findings engine. Run before wiring findings into the live prompt. |
| `wrangler.toml`, `Dockerfile`, `requirements-api.txt` | Deploy/config. |

## Do NOT read or edit for this work
- `docs/` — human reference only (reviews, specs, screenshots, sample CSVs, old versions). Not source.
  Notable: `docs/orion_expansion_spec.html` (a *separate*, deferred direction — the findings/advisory
  engine; ignore it for the reframe), `docs/deliverables/` (review PDFs), `docs/samples/` (test CSVs),
  `docs/archive/` (old builds).

## Workflow
1. `git commit` before starting.
2. Work the roadmap (see `POSITIONING.md` → *Active goal* sequence) as **separate prompts**, reviewing each diff.
3. Every AI feature must pull computed numbers from the engine (risk/findings, fundamentals) — never
   hardcode — and must lean on the user's own accumulated record (thesis/psychology/history), never generic
   summarization a fresh Claude session could reproduce.
