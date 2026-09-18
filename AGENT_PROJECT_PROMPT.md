# Build prompt — Personal Equity-Research Agent

> Paste this into your coding agent (Claude Code, etc.) to start the project.
> Start it in a **fresh directory**, not inside the Orion repo.

---

## Context & goals

I'm building an autonomous **equity-research agent** in Python. I have two real goals, and the
code should serve both:

1. **I will use this myself** on my own real holdings. So it has to be genuinely trustworthy:
   every claim cited to a source filing, numbers verified, and it must *explain, never advise*
   (no buy/sell recommendations — it makes companies legible so I decide).
2. **It's a portfolio/CV piece.** I'm learning to build AI agents. The repo must clearly
   demonstrate the skills employers screen for: tool/function calling, a multi-step planning
   loop, RAG over documents, and — the part most portfolio projects skip — an **evaluation
   harness** and a **self-verification step**.

I have prior code I can reuse for SEC EDGAR and FMP (Financial Modeling Prep) data fetching and
a set of pre-computed company JSON files — treat those as available building blocks / test data.

## What the agent does

Given a ticker (or a list of my holdings), the agent autonomously:
- Plans a short research task (decides which tools it needs).
- Pulls the latest 10-K / 10-Q from SEC EDGAR.
- Retrieves the relevant sections (RAG: chunk + embed + retrieve).
- Computes a few key financial ratios with a calculator tool (not from memory).
- Optionally checks recent news.
- Writes a concise, **fully cited** analysis — every factual claim linked to its source.
- **Verifies its own numbers** against the source before finalizing, and flags anything it
  couldn't confirm.

Interface: start with a **CLI**; a thin Streamlit UI is a nice-to-have for v2+.

## Architecture requirements

- **Tool-calling loop**, not a fixed script. The agent chooses the next tool based on state.
  Tools to implement: `fetch_filing(ticker)`, `search_filing(query)` (RAG retrieval),
  `compute_ratio(...)`, `get_quote(ticker)`, `search_news(ticker)`.
- **RAG** over filings: chunk, embed (local model or API), store in FAISS or Chroma, retrieve
  top-k for each question.
- **Guardrails:** the agent must (a) cite a source for every factual claim, (b) never output a
  buy/sell recommendation, (c) say "I couldn't verify this" rather than guess.
- **Self-verification:** after drafting, re-check each numeric claim against the retrieved
  source text; downgrade or flag unverified claims.

## Evaluation (this is the differentiator — do not skip)

- An `evals/` folder with a small fixed set of test questions + known-good answers drawn from
  real filings.
- Measure and report: **citation accuracy** and **hallucination rate** (claims not supported by
  a retrieved source).
- Print the metrics in the README. This is the headline of the project.

## Stack

Python, the Anthropic or OpenAI SDK with function calling (or LangGraph if I want to show
orchestration-framework fluency), FAISS or Chroma for the vector store, pytest for tests/evals.

## Build order (keep scope tight — finish each before the next)

- **v1 (one weekend):** single ticker, one tool (`fetch_filing`), answer one question with a
  citation. Runnable end to end. Ship it.
- **v2:** add the full tool-calling loop and the remaining tools; add RAG retrieval.
- **v3:** add the `evals/` harness + self-verification layer, and report the metrics.

## Repo hygiene (for the CV)

- Clean README: one-line pitch, a GIF/screenshot of it running, setup steps, the eval metrics
  up front, and a short "what I learned / design decisions" section.
- `requirements.txt`, sensible module layout, `.env.example` for API keys (never commit keys).
- A few pytest tests beyond the evals.
- Meaningful commit history.

## First task

Set up the repo skeleton, implement the `fetch_filing(ticker)` EDGAR tool, and get v1 running:
I type a ticker, it pulls the latest 10-K, and answers one question with a citation. Then stop
and show me what you built before moving to v2.
