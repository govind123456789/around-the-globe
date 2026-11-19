/* Around the Globe Worker: serves the static site, and puts optional API keys and usage tiers in front of
   the open data API (/v1/*). Everything degrades to the plain static site:
   - no RATE_* bindings  -> no rate limits
   - no DB (D1) binding   -> keys are not checked and the signup endpoint answers 503
   Anonymous access to /v1/* always works, at the anonymous limit.

   Tiers (requests per minute; see TIERS):
     anonymous  60   by client IP
     free       600  by key, with attribution required (CC BY 4.0)
     commercial placeholder, same limit as free until a plan exists

   Keys arrive as the "x-api-key" header or "?key=" parameter. Only a SHA-256 hash of each key is stored. */

export const TIERS = {
  anonymous: { perMinute: 60, label: "Anonymous" },
  free: { perMinute: 600, label: "Free key" },
  commercial: { perMinute: 600, label: "Commercial (placeholder)" },
};

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8", "access-control-allow-origin": "*" };
const json = (body, status = 200, extra = {}) => new Response(JSON.stringify(body), { status, headers: { ...JSON_HEADERS, ...extra } });

export async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}

export function newKey() {
  const b = crypto.getRandomValues(new Uint8Array(24));
  return "atg_" + [...b].map(x => x.toString(16).padStart(2, "0")).join("");
}

const EMAIL = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,24}$/;

async function lookupKey(env, key) {
  if (!env.DB || !key) return null;
  const row = await env.DB.prepare("SELECT key_hash, tier, status FROM api_keys WHERE key_hash = ?").bind(await sha256(key)).first();
  return row && row.status === "active" ? row : null;
}

async function countUse(env, ctx, id, tier) {
  if (!env.DB) return;
  const day = new Date().toISOString().slice(0, 10);
  ctx.waitUntil(env.DB.prepare(
    "INSERT INTO api_usage (subject, tier, day, n) VALUES (?, ?, ?, 1) ON CONFLICT(subject, day) DO UPDATE SET n = n + 1"
  ).bind(id, tier, day).run().catch(() => {}));
}

async function limited(binding, id) {
  if (!binding) return false;
  try { const { success } = await binding.limit({ key: id }); return !success; } catch { return false; }
}

export async function handleApi(request, env, ctx) {
  const url = new URL(request.url);
  const key = request.headers.get("x-api-key") || url.searchParams.get("key");
  let tier = "anonymous", subject = "ip:" + (request.headers.get("cf-connecting-ip") || "unknown");
  if (key) {
    const row = await lookupKey(env, key);
    if (env.DB && !row) return json({ error: "Unknown or revoked API key. Remove it to use anonymous access, or get one at /data/api/." }, 401);
    if (row) { tier = row.tier in TIERS ? row.tier : "free"; subject = "key:" + row.key_hash.slice(0, 16); }
  }
  const binding = tier === "anonymous" ? env.RATE_ANON : env.RATE_KEYED;
  if (await limited(binding, subject)) {
    return json({ error: `Rate limit reached (${TIERS[tier].perMinute} requests a minute for ${TIERS[tier].label}). Wait a minute, or use a free API key for higher limits.` },
      429, { "retry-after": "60" });
  }
  // usage counts never store a raw IP address: anonymous callers are counted under a hash that changes daily
  const stored = tier === "anonymous" ? "ip:" + (await sha256(subject + new Date().toISOString().slice(0, 10))).slice(0, 16) : subject;
  countUse(env, ctx, stored, tier);
  // drop the key from the URL before serving the file, so caches see one URL per file
  if (url.searchParams.has("key")) { url.searchParams.delete("key"); request = new Request(url.toString(), request); }
  const res = await env.ASSETS.fetch(request);
  const out = new Response(res.body, res);
  out.headers.set("access-control-allow-origin", "*");
  out.headers.set("x-api-tier", tier);
  out.headers.set("x-ratelimit-limit", String(TIERS[tier].perMinute));
  return out;
}

export async function handleSignup(request, env) {
  if (request.method !== "POST") return json({ error: "POST an email address." }, 405);
  if (!env.DB) return json({ error: "API keys are not switched on yet. Anonymous access works without a key." }, 503);
  const ip = request.headers.get("cf-connecting-ip") || "unknown";
  if (await limited(env.RATE_SIGNUP, "signup:" + ip)) return json({ error: "Too many sign-ups from this address. Try again later." }, 429);
  let email = "";
  const type = request.headers.get("content-type") || "";
  if (type.includes("application/json")) email = String((await request.json().catch(() => ({}))).email || "");
  else email = String((await request.formData().catch(() => new FormData())).get("email") || "");
  email = email.trim().toLowerCase();
  if (!EMAIL.test(email)) return json({ error: "Enter a valid email address." }, 400);
  const key = newKey();
  await env.DB.prepare("INSERT INTO api_keys (key_hash, email, tier, status, created_at) VALUES (?, ?, 'free', 'active', ?)")
    .bind(await sha256(key), email, new Date().toISOString()).run();
  return json({ key, tier: "free", perMinute: TIERS.free.perMinute,
    note: "Keep this key: it is shown once and only a hash is stored. Send it as the x-api-key header. Attribution (CC BY 4.0) is required." }, 201);
}

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    if (pathname === "/api/keys" ) return handleSignup(request, env);
    if (pathname.startsWith("/v1/")) return handleApi(request, env, ctx);
    return env.ASSETS.fetch(request);
  },
};
