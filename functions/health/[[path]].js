const HEALTH_PREFIX = "health/";
const HEALTH_ARTIFACTS = new Set([
  "latest.json",
  "history_daily.json",
  "drift.json",
  "trends.json",
  "reconciliation.json",
  "evidence-coverage.json",
]);

const unavailable = reason => {
  console.error(`health index unavailable: ${reason}`);
  return new Response('{"error":"health index unavailable"}', {
    status: 503,
    headers: { "Cache-Control": "no-store", "Content-Type": "application/json" },
  });
};

async function staticAsset(context) {
  if (context.env.ASSETS && typeof context.env.ASSETS.fetch === "function") {
    return context.env.ASSETS.fetch(context.request);
  }
  return fetch(new Request(context.request));
}

export async function onRequest(context) {
  const pathname = new URL(context.request.url).pathname;
  if (!pathname.startsWith("/health/")) {
    return new Response("Not found", { status: 404 });
  }
  const name = pathname.slice("/health/".length);
  if (!HEALTH_ARTIFACTS.has(name) || name.includes("..")) {
    return new Response("Not found", { status: 404 });
  }

  const binding = context.env.DATAPULSE_HEALTH_INDEX;
  if (!binding || typeof binding.get !== "function") return unavailable("KV binding missing");

  if (name === "latest.json" && context.env.ASSETS && typeof context.env.ASSETS.fetch === "function") {
    try {
      const asset = await staticAsset(context);
      if (asset.ok) {
        return new Response(asset.body, {
          status: 200,
          headers: { "Cache-Control": "public, max-age=300, stale-while-revalidate=60", "Content-Type": "application/json" },
        });
      }
    } catch (_) {
      // KV remains available when Pages cannot serve the assembled asset.
    }
  }

  try {
    const bytes = await binding.get(`${HEALTH_PREFIX}${name}`, "arrayBuffer");
    if (!(bytes instanceof ArrayBuffer) || bytes.byteLength === 0) {
      return name === "latest.json" ? unavailable("static asset and KV value missing") : staticAsset(context);
    }
    return new Response(bytes, {
      status: 200,
      headers: { "Cache-Control": "public, max-age=300, stale-while-revalidate=60", "Content-Type": "application/json" },
    });
  } catch (_) {
    return unavailable("KV read failed");
  }
}
