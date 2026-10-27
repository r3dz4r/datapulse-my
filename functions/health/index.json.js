const HEALTH_INDEX_KEY = "health-index.json";

const unavailable = reason => {
  console.error(`health index unavailable: ${reason}`);
  return new Response('{"error":"health index unavailable"}', {
    status: 503,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "application/json",
    },
  });
};

export async function onRequest(context) {
  const binding = context.env.DATAPULSE_HEALTH_INDEX;
  if (!binding || typeof binding.get !== "function") {
    return unavailable("KV binding missing");
  }

  try {
    const assetUrl = new URL("/health/latest.json", context.request.url);
    const asset = await context.env.ASSETS?.fetch(assetUrl);
    if (asset?.ok) {
      return new Response(asset.body, {
        status: 200,
        headers: {
          "Cache-Control": "public, max-age=300, stale-while-revalidate=60",
          "Content-Type": "application/json",
        },
      });
    }
  } catch (_) {
    // Keep the dashboard available through KV when the accepted asset is absent.
  }

  try {
    const bytes = await binding.get(HEALTH_INDEX_KEY, "arrayBuffer");
    if (!(bytes instanceof ArrayBuffer) || bytes.byteLength === 0) {
      return unavailable("KV value missing or empty");
    }
    return new Response(bytes, {
      status: 200,
      headers: {
        "Cache-Control": "public, max-age=300, stale-while-revalidate=60",
        "Content-Type": "application/json",
      },
    });
  } catch (_) {
    return unavailable("KV read failed");
  }
}
