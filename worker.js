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
const ALLOWED_MODEL = "claude-sonnet-4-6";
const MAX_OUTPUT_TOKENS = 1500;
const MAX_PROMPT_CHARS = 50000;
const MAX_SEARCH_USES = 4;
const ALLOWED_BODY_KEYS = new Set(["model", "max_tokens", "messages", "tools"]);

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

function jsonResponse(payload, status, corsHeaders = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function validateRequestBody(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return "Request body must be a JSON object.";
  }
  if (Object.keys(body).some(key => !ALLOWED_BODY_KEYS.has(key))) {
    return "Request contains unsupported AI options.";
  }
  if (body.model !== ALLOWED_MODEL) {
    return `Only ${ALLOWED_MODEL} is allowed.`;
  }
  if (!Number.isInteger(body.max_tokens) || body.max_tokens < 1 || body.max_tokens > MAX_OUTPUT_TOKENS) {
    return `max_tokens must be between 1 and ${MAX_OUTPUT_TOKENS}.`;
  }
  if (!Array.isArray(body.messages) || body.messages.length !== 1 || body.messages[0]?.role !== "user") {
    return "Exactly one user message is required.";
  }
  const content = body.messages[0]?.content;
  if (typeof content !== "string" || content.length === 0 || content.length > MAX_PROMPT_CHARS) {
    return `Prompt must be between 1 and ${MAX_PROMPT_CHARS} characters.`;
  }
  if (body.tools !== undefined) {
    if (!Array.isArray(body.tools) || body.tools.length !== 1) {
      return "Only the configured web search tool is allowed.";
    }
    const tool = body.tools[0];
    if (tool?.type !== "web_search_20250305" || tool?.name !== "web_search"
        || !Number.isInteger(tool?.max_uses) || tool.max_uses < 1 || tool.max_uses > MAX_SEARCH_USES) {
      return `Web search max_uses must be between 1 and ${MAX_SEARCH_USES}.`;
    }
  }
  return null;
}

export default {
  async fetch(request, env) {
    const reqOrigin = request.headers.get("Origin") || "";
    const allowedOrigin = resolveAllowedOrigin(reqOrigin);

    // Reject unknown origins before doing anything else — this is the
    // gate that stops a random visitor from draining the API key.
    if (allowedOrigin === null) {
      return jsonResponse({ error: { message: "Origin not allowed." } }, 403);
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
      return jsonResponse(
        { error: { message: "ANTHROPIC_API_KEY secret not set in Worker settings." } },
        500,
        corsHeaders,
      );
    }

    // Emergency stop: set AI_PROXY_ENABLED=false in Worker variables to
    // immediately block paid requests without changing or redeploying code.
    if (String(env.AI_PROXY_ENABLED || "true").toLowerCase() !== "true") {
      return jsonResponse(
        { error: { message: "AI requests are disabled to prevent additional spending." } },
        503,
        corsHeaders,
      );
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return jsonResponse({ error: { message: "Invalid JSON body." } }, 400, corsHeaders);
    }

    const validationError = validateRequestBody(body);
    if (validationError) {
      return jsonResponse({ error: { message: validationError } }, 400, corsHeaders);
    }

    let upstream;
    try {
      upstream = await fetch(ANTHROPIC_API, {
        method: "POST",
        headers: {
          "x-api-key": env.ANTHROPIC_API_KEY,
          "anthropic-version": "2023-06-01",
          "content-type": "application/json",
        },
        body: JSON.stringify(body),
      });
    } catch {
      return jsonResponse(
        { error: { message: "The AI provider is temporarily unreachable." } },
        502,
        corsHeaders,
      );
    }

    const data = await upstream.json().catch(() => ({
      error: { message: "The AI provider returned an invalid response." },
    }));

    // Anthropic enforces the workspace spending limit. Once reached, stop and
    // return a stable message instead of retrying or hiding the reason.
    if (upstream.status === 429) {
      return jsonResponse(
        { error: { message: "AI spending or rate limit reached. No request was retried." } },
        429,
        corsHeaders,
      );
    }

    return jsonResponse(data, upstream.status, corsHeaders);
  },
};
