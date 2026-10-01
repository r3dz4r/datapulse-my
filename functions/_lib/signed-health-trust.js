// Bounded trusted-registry delivery for the verified health reader.
//
// Trust is independent of the signed package and of KV storage. The registry is
// read only from the fixed same-deployment static asset path, and the package
// can never supply a URL or a key. This module never reads a registry from
// storage, so a KV-provided registry cannot become signing authority.
export const TRUSTED_REGISTRY_ASSET = "/.well-known/datapulse-probe-keys.json";
export const MAX_REGISTRY_BYTES = 256 * 1024;

async function boundedBytes(response, limit) {
  if (!response.ok || !response.body) throw new Error("trusted_registry_unavailable");
  const reader = response.body.getReader(), chunks = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > limit) throw new Error("trusted_registry_oversized");
      chunks.push(value);
    }
  } finally { await reader.cancel(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return bytes;
}

export async function loadTrustedRegistry(context) {
  const assets = context.env.ASSETS;
  if (!assets || typeof assets.fetch !== "function") throw new Error("trust_or_storage_unavailable");
  // Fixed same-deployment asset. No package-provided URL and no network fallback.
  const url = new URL(TRUSTED_REGISTRY_ASSET, context.request.url);
  const response = await assets.fetch(new Request(url, { headers: { "Cache-Control": "no-store" } }));
  return boundedBytes(response, MAX_REGISTRY_BYTES);
}
