# Orion Wealth

Orion Wealth is the V2 financial-life planning experience. It maps actual salary history, the current balance sheet, future income changes, major purchases, property contributions, windfalls, inheritance, and retirement on one age-based timeline.

It is intentionally isolated from `../orion.html`, which remains Orion Classic. Both versions share the Orion name, but Classic keeps its portfolio-understanding purpose while Wealth develops the broader planning journey.

## Run locally

From the repository root:

```bash
python3 -m http.server 8080
```

Then open `http://127.0.0.1:8080/wealth/`.

## Verify

```bash
node wealth/test_engine.mjs
```

The V2 engine is deterministic. Historical salary entries are records only; Orion does not fabricate a past balance sheet from incomplete data. Future projections begin from the current balance sheet and apply dated income assumptions and life events year by year.

AI should eventually explain calculations and generate alternatives, but it must not invent financial inputs, returns, tax rules, or computed outcomes.
