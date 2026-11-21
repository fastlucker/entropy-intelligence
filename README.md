# Entropy Intelligence Web — Vercel Edition V5.2

Independent, read-only markets tool. No wallet access, no private keys, no login.

## Publish on Vercel

1. Upload the **contents** of this folder to a GitHub repository (keep `index.html`, `api/`, `vercel.json` in the root).
2. In Vercel choose **Add New > Project**, import that repository, select **Other** as framework, and deploy. Root directory `./`, no build command or environment secrets needed.
3. After publication, open your project `*.vercel.app` URL; test `/api/variational`, `/api/extended`, `/api/arcus` and the scanner itself.
4. If Variational responds 429, check the JSON `retry_after_seconds` and respect it. Vercel does not eliminate upstream API quotas or guarantee source access.

## Architecture

Static `index.html`; Vercel Python functions:
- `POST /api/info` Hyperliquid info, constrained to 4 read-only methods
- `GET /api/extended` / `GET /api/arcus` / `GET /api/variational`

Responses for GET providers are cached by **Vercel CDN**, for 90/90/300 seconds, respectively. Failed calls are not cached. Serverless function memory is NOT a persistent, cross-visitor cache. There is no historical database or background collector. To obtain persistent timeseries, add a managed database and scheduled collector. A stale state must never be represented as live in trade rankings.

**Important:** Quote data at Variational is RFQ by fixed notional tier (1k/100k/1m), not an executable order book. Prices, fees, spread and funding forecasts are indicative, not guarantees.

## Quick test

`python -m compileall -q api`

Use `vercel dev` after installing the Vercel CLI to simulate serverless locally; for deployment preview, use the Vercel project dashboard.
