// node --test worker/   (Node 20+: fetch, Request, Response and crypto.subtle are built in)
import test from "node:test";
import assert from "node:assert/strict";
import worker, { sha256 } from "./index.js";

const assets = { fetch: async req => new Response(JSON.stringify({ path: new URL(req.url).pathname, q: new URL(req.url).search }), { status: 200 }) };
const ctx = { waitUntil: p => p };
const limiter = max => { const n = {}; return { limit: async ({ key }) => ({ success: (n[key] = (n[key] || 0) + 1) <= max }) }; };

function fakeDb() {
  const keys = new Map(), usage = [];
  return {
    keys, usage,
    prepare(sql) {
      return {
        bind(...a) {
          return {
            first: async () => (sql.startsWith("SELECT") ? keys.get(a[0]) || null : null),
            run: async () => { if (sql.startsWith("INSERT INTO api_keys")) keys.set(a[0], { key_hash: a[0], email: a[1], tier: "free", status: "active" }); else usage.push(a); },
          };
        },
      };
    },
  };
}
const get = (path, headers = {}) => new Request("https://x.test" + path, { headers: { "cf-connecting-ip": "1.2.3.4", ...headers } });

test("anonymous /v1 works with no bindings at all (the plain static site)", async () => {
  const r = await worker.fetch(get("/v1/latest/indicators.json"), { ASSETS: assets }, ctx);
  assert.equal(r.status, 200);
  assert.equal(r.headers.get("x-api-tier"), "anonymous");
});

test("anonymous requests are rate-limited when the binding exists", async () => {
  const env = { ASSETS: assets, RATE_ANON: limiter(2) };
  for (let i = 0; i < 2; i++) assert.equal((await worker.fetch(get("/v1/a.json"), env, ctx)).status, 200);
  const r = await worker.fetch(get("/v1/a.json"), env, ctx);
  assert.equal(r.status, 429);
  assert.equal(r.headers.get("retry-after"), "60");
});

test("signup issues a key, stores only its hash, and the key gets the free tier", async () => {
  const env = { ASSETS: assets, DB: fakeDb(), RATE_ANON: limiter(1), RATE_KEYED: limiter(100), RATE_SIGNUP: limiter(5) };
  const res = await worker.fetch(new Request("https://x.test/api/keys", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: "Me@Example.org" }) }), env, ctx);
  assert.equal(res.status, 201);
  const { key } = await res.json();
  assert.match(key, /^atg_[0-9a-f]{48}$/);
  assert.ok(env.DB.keys.has(await sha256(key)));
  assert.ok(![...env.DB.keys.keys()].includes(key));
  for (let i = 0; i < 3; i++) {                              // above the anonymous limit of 1
    const r = await worker.fetch(get("/v1/a.json?key=" + key), env, ctx);
    assert.equal(r.status, 200);
    assert.equal(r.headers.get("x-api-tier"), "free");
    assert.equal((await r.json()).q, "");                    // the key is not passed on to the asset
  }
});

test("an unknown key is refused when keys are switched on", async () => {
  const r = await worker.fetch(get("/v1/a.json", { "x-api-key": "atg_nope" }), { ASSETS: assets, DB: fakeDb() }, ctx);
  assert.equal(r.status, 401);
});

test("signup without a database answers 503, and bad emails 400", async () => {
  const post = body => new Request("https://x.test/api/keys", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  assert.equal((await worker.fetch(post({ email: "a@b.org" }), { ASSETS: assets }, ctx)).status, 503);
  assert.equal((await worker.fetch(post({ email: "nope" }), { ASSETS: assets, DB: fakeDb() }, ctx)).status, 400);
});

test("pages outside /v1 and /api go straight to the static site", async () => {
  const r = await worker.fetch(get("/countries/india/"), { ASSETS: assets }, ctx);
  assert.equal((await r.json()).path, "/countries/india/");
});
