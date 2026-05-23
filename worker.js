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

// Optional: restrict to your domain once deployed publicly.
// Change "*" to e.g. "https://your-app.netlify.app"
const ALLOWED_ORIGIN = "*";

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";

    const corsHeaders = {
      "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
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
