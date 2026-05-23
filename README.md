# Orion

A single-page portfolio intelligence app: live prices, AI briefings, risk diagnostics, and crisis simulations.

## What's in here

| File | Purpose |
|------|---------|
| `orion.html` | The entire app. Open it in a browser. |
| `orion_api.py` | Python service that fetches ISIN metadata (OpenFIGI) and live + historical quotes (Yahoo Finance via yfinance). |
| `worker.js` | Cloudflare Worker that proxies requests to the Anthropic API so the AI key never touches the browser. |
| `wrangler.toml` | Cloudflare Worker config. |
| `Dockerfile` | Builds a container for `orion_api.py`, so the pricing API can be hosted on any Docker-friendly PaaS. |
| `requirements-api.txt` | Python deps for `orion_api.py`. |
| `sample_portfolio.csv` | Example holdings file for the CSV import flow. |

## Running locally

```bash
# 1. Pricing API (terminal 1)
pip install -r requirements-api.txt
python orion_api.py             # serves http://127.0.0.1:8787

# 2. AI proxy (terminal 2) — needs Wrangler + an Anthropic key
wrangler dev --port 8788        # serves http://127.0.0.1:8788

# 3. Open orion.html in a browser.
```

When the page is served from `localhost`, `127.0.0.1`, or `file://`, the app automatically points at the two local services. From any other origin, it uses the deployed URLs configured at the top of `orion.html` (`ORION_CONFIG`).

## Deploying

### AI proxy → Cloudflare Workers

```bash
wrangler login
wrangler deploy
wrangler secret put ANTHROPIC_API_KEY   # paste sk-ant-...
```

Copy the resulting `https://*.workers.dev` URL into `ORION_CONFIG.PROD.AI_PROXY` in `orion.html`.

### Pricing API → any Docker-friendly host (Render, Railway, Fly.io)

1. Connect this repo to your host of choice.
2. Point the service at this repo's `Dockerfile`. The container exposes whatever port the host injects via `PORT`.
3. Copy the resulting public URL into `ORION_CONFIG.PROD.ORION_API` in `orion.html`.

### Static frontend

`orion.html` is a single static file. Drop it on GitHub Pages, Netlify, Vercel, or any static host. Anyone with the link will hit the deployed backends automatically.
