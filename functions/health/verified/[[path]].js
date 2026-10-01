import { readVerified } from "../../_lib/signed-health.js";

const headers = { "Cache-Control": "no-store", "Content-Type": "application/json" };

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const match = url.pathname.match(/^\/health\/verified\/(latest|[0-9a-f]{64})\.json$/);
  if (!match || match[0] !== url.pathname) return new Response('{"error":"not_found"}', { status: 404, headers });
  if (context.request.method !== "GET") return new Response('{"error":"method_not_allowed"}', { status: 405, headers });
  // Caller-supplied floors can strengthen acceptance only. They are never signed
  // claims and independent consumers must enforce their own retained floor.
  const params = [...url.searchParams.keys()];
  if (params.some(key => key !== "minimum_observed_at") || url.searchParams.getAll("minimum_observed_at").length > 1) {
    return new Response('{"error":"invalid_request"}', { status: 400, headers });
  }
  try {
    const { body } = await readVerified(context, match[1], {
      clock: () => Date.now() / 1000,
      ...(url.searchParams.has("minimum_observed_at") ? { minimumObservedAt: url.searchParams.get("minimum_observed_at") } : {}),
    });
    return new Response(body, { status: 200, headers });
  } catch (_) {
    // No unsigned static fallback, including when runtime crypto is unavailable.
    return new Response('{"error":"verified_health_unavailable"}', { status: 503, headers });
  }
}
