# Orion — project guide for Claude Code

Orion is a **single-page portfolio risk app**. The entire frontend is one static file: `orion.html`.
Two small backends support it. Keep the single-file architecture — do not split `orion.html` into modules.

## Active goal
Execute the **Phase 1 reframe** described in `REFRAME_PLAN.md`: shift Orion from a net-worth tracker
to a **risk early-warning system**. This phase is copy, layout, hierarchy, and the AI-briefing prompt —
**no new features, no auth, no data-layer work.**

Apply this gate to every change: **"Does this help someone see or avoid a portfolio risk?"**
If no, don't ship it.

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
2. Do the `REFRAME_PLAN.md` checklist as **separate prompts**, reviewing each diff.
3. The AI briefing rewrite must pull computed numbers from the existing risk/findings engine — never hardcode.
