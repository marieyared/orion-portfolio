/**
 * Orion AI Proxy — Cloudflare Worker
 *
 * Proxies requests to the Anthropic API so the key never touches the browser.
 * Deploy steps are in the README or below:
 *
 * 1. Go to dash.cloudflare.com → Workers & Pages → Create → Worker
 * 2. Paste this entire file, click Deploy
 * 3. Go to the Worker's Settings → Variables → Secrets → Add secret
 *    Name:  ANTHROPIC_API_KEY
 *    Value: sk-ant-... (your real key)
 * 4. Copy your worker URL (e.g. https://orion-ai.yourname.workers.dev)
 * 5. Paste it into orion.html as AI_PROXY_URL
 */

const ANTHROPIC_API = "https://api.anthropic.com/v1/messages";

// Explicit allowlist. Add new origins here when you deploy to another host.
const ALLOWED_ORIGINS = new Set([
  "https://marieyared.github.io",
]);
const LOCALHOST_RE = /^https?:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$/;

// Decide whether to accept a request based on its Origin header.
// Returns the value to echo back in Access-Control-Allow-Origin, or null to reject.
function resolveAllowedOrigin(reqOrigin) {
  // file:// opens send Origin: "null" (or omit it). Allow for local-only use.
  if (!reqOrigin || reqOrigin === "null") return "null";
  if (ALLOWED_ORIGINS.has(reqOrigin)) return reqOrigin;
  if (LOCALHOST_RE.test(reqOrigin)) return reqOrigin;
  return null;
}

export default {
  async fetch(request, env) {
    const reqOrigin = request.headers.get("Origin") || "";
    const allowedOrigin = resolveAllowedOrigin(reqOrigin);

    // Reject unknown origins before doing anything else — this is the
    // gate that stops a random visitor from draining the API key.
    if (allowedOrigin === null) {
      return new Response(
        JSON.stringify({ error: "Origin not allowed." }),
        { status: 403, headers: { "Content-Type": "application/json" } }
      );
    }

    const corsHeaders = {
      "Access-Control-Allow-Origin": allowedOrigin,
      "Vary": "Origin",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405, headers: corsHeaders });
    }

    if (!env.ANTHROPIC_API_KEY) {
      return new Response(
        JSON.stringify({ error: "ANTHROPIC_API_KEY secret not set in Worker settings." }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response(
        JSON.stringify({ error: "Invalid JSON body." }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const upstream = await fetch(ANTHROPIC_API, {
      method: "POST",
      headers: {
        "x-api-key": env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await upstream.json();

    return new Response(JSON.stringify(data), {
      status: upstream.status,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  },
};
