// Staged verifier: trust assets and package storage are separate inputs.
// All time/age decisions use the consumer clock, not cryptographic time.
const PACKAGE_SCHEMA = "datapulse/v1/signed-health-package";
const BINDING_SCHEMA = "datapulse/v1/signed-health-binding";
const RESPONSE_SCHEMA = "datapulse/v1/signed-health-response";
const POINTER_SCHEMA = "datapulse/v1/signed-health-pointer";
const PURPOSE = "attestation-chain-signing";
const POLICY = "health-observation-36h-v1";
const DOMAIN = new TextEncoder().encode("datapulse/v1/signed-health-binding\0");
const PREFIX = "signed-health/v1/";
const MAX_PACKAGE = 8 * 1024 * 1024;
const MAX_HEALTH = 5 * 1024 * 1024;
const MAX_BINDING = 4096;
const MAX_REGISTRY = 256 * 1024;
const DIGEST = /^[0-9a-f]{64}$/;
const KEY_ID = /^ed25519-[0-9a-f]{16}$/;
const encoder = new TextEncoder();
const decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true });
const packageFields = ["schema", "version", "health_base64", "binding_base64", "signature_base64"];
const bindingFields = ["schema", "version", "subject", "health_sha256", "health_bytes", "observed_at", "assembled_at", "signed_at", "source_commit", "key_id", "signer_public_key_sha256", "algorithm", "key_purpose", "policy", "claim_scope", "source_truth_verified"];

function require(condition, reason) {
  if (!condition) throw new Error(reason);
}
function object(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
function fields(value, names) {
  return object(value) && Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
}
function token(value, pattern, reason) {
  // JS $ also matches before a final newline; checking the match length is required.
  const match = typeof value === "string" ? value.match(pattern) : null;
  require(match && match[0] === value, reason);
  return value;
}

export function strictJSON(bytes, limit, integerFields = []) {
  require(bytes instanceof Uint8Array && bytes.length > 0 && bytes.length <= limit, "invalid_json_size");
  const text = decoder.decode(bytes);
  // JSON.parse alone silently accepts duplicate keys. Parse structure before
  // interpretation, including duplicates encoded using escaped property names.
  let pos = 0;
  const whitespace = () => { while (/[ \t\r\n]/.test(text[pos] || "x")) pos++; };
  const string = () => {
    require(text[pos] === '"', "invalid_json");
    const start = pos++;
    while (pos < text.length) {
      if (text[pos] === "\\") { pos += 2; continue; }
      if (text[pos++] === '"') return JSON.parse(text.slice(start, pos));
    }
    throw new Error("invalid_json");
  };
  const value = depth => {
    require(depth <= 64, "invalid_json_depth");
    whitespace();
    if (text[pos] === '"') return string();
    if (text[pos] === "{" || text[pos] === "[") {
      const isObject = text[pos++] === "{";
      const result = isObject ? Object.create(null) : [];
      const seen = new Set();
      const closing = isObject ? "}" : "]";
      whitespace();
      if (text[pos] === closing) { pos++; return result; }
      while (true) {
        whitespace();
        if (isObject) {
          const key = string();
          require(!seen.has(key), "duplicate_json_key");
          seen.add(key);
          whitespace();
          require(text[pos++] === ":", "invalid_json");
          whitespace();
          const start = pos;
          result[key] = value(depth + 1);
          if (integerFields.includes(key)) require(/^-?(?:0|[1-9][0-9]*)$/.test(text.slice(start, pos)), "invalid_integer_type");
        } else result.push(value(depth + 1));
        whitespace();
        if (text[pos] === closing) { pos++; return result; }
        require(text[pos++] === ",", "invalid_json");
      }
    }
    const match = text.slice(pos).match(/^(?:true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)/);
    require(match, "invalid_json");
    pos += match[0].length;
    const parsed = JSON.parse(match[0]);
    require(typeof parsed !== "number" || Number.isFinite(parsed), "invalid_json_number");
    return parsed;
  };
  const result = value(0);
  whitespace();
  require(pos === text.length && object(result), "invalid_json_object");
  return result;
}

function base64(bytes) {
  // Chunk to avoid call-stack limits on full snapshots.
  const chunks = [];
  for (let i = 0; i < bytes.length; i += 16384) chunks.push(String.fromCharCode(...bytes.subarray(i, i + 16384)));
  return btoa(chunks.join(""));
}
function unbase64(value, limit) {
  require(typeof value === "string" && value.length <= 4 * Math.ceil(limit / 3), "invalid_base64");
  const binary = atob(value);
  const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
  require(bytes.length <= limit && base64(bytes) === value, "invalid_base64");
  return bytes;
}
async function sha(bytes) {
  require(globalThis.crypto && crypto.subtle, "crypto_unavailable");
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), byte => byte.toString(16).padStart(2, "0")).join("");
}
function time(value) {
  token(value, /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)$/, "invalid_timestamp");
  const base = value.slice(0, 19) + "Z";
  const ms = Date.parse(base);
  require(Number.isFinite(ms) && new Date(ms).toISOString().slice(0, 19) === value.slice(0, 19) && !value.startsWith("0000"), "invalid_timestamp");
  const fraction = value.slice(19).match(/^\.([0-9]+)/);
  return ms / 1000 + (fraction ? Number("0." + fraction[1]) : 0);
}

async function trustedKey(registry, keyId, signedAt, now) {
  require(object(registry) && registry.schema === "datapulse/v2/probe-key-registry" && registry.version === 2 && Array.isArray(registry.keys) && registry.keys.length > 0 && registry.keys.every(object), "invalid_registry");
  const ids = registry.keys.map(row => token(row.key_id, KEY_ID, "invalid_key_identity"));
  require(new Set(ids).size === ids.length, "ambiguous_key");
  const active = registry.keys.filter(row => row.purpose === PURPOSE && row.status === "active");
  require(active.length === 1 && active[0].key_id === keyId && registry.current_key_id === keyId, "inactive_or_ambiguous_key");
  const row = active[0];
  require(row.algorithm === "Ed25519", "wrong_algorithm");
  require(row.compromised_at == null && row.revoked_at == null, "revoked_or_compromised_key");
  const start = time(row.not_before), end = time(row.not_after);
  require(start <= signedAt && signedAt <= end && start <= now && now <= end, "key_outside_window");
  const raw = unbase64(row.public_key_base64, 32);
  require(raw.length === 32 && "ed25519-" + (await sha(raw)).slice(0, 16) === keyId, "key_identity_mismatch");
  return raw;
}

export async function verifyPackage(packageBytes, registry, { now, expectedPublication, minimumObservedAt } = {}) {
  require(Number.isFinite(now), "consumer_clock_required");
  const identity = await sha(packageBytes);
  if (expectedPublication !== undefined) {
    token(expectedPublication, DIGEST, "invalid_publication");
    require(identity === expectedPublication, "publication_mismatch");
  }
  const pkg = strictJSON(packageBytes, MAX_PACKAGE, ["version"]);
  require(fields(pkg, packageFields) && pkg.schema === PACKAGE_SCHEMA && pkg.version === 1, "invalid_package");
  const healthBytes = unbase64(pkg.health_base64, MAX_HEALTH);
  const bindingBytes = unbase64(pkg.binding_base64, MAX_BINDING);
  const signature = unbase64(pkg.signature_base64, 64);
  const binding = strictJSON(bindingBytes, MAX_BINDING, ["version", "health_bytes"]);
  require(fields(binding, bindingFields) && binding.schema === BINDING_SCHEMA && binding.version === 1, "invalid_binding");
  require(binding.subject === "health/latest.json" && binding.claim_scope === "exact-health-snapshot" && binding.source_truth_verified === false, "invalid_claim_scope");
  require(binding.policy === POLICY, "unsupported_policy");
  require(binding.algorithm === "Ed25519" && binding.key_purpose === PURPOSE, "wrong_signing_purpose");
  token(binding.source_commit, /^[0-9a-f]{40}$/, "invalid_source_commit");
  token(binding.health_sha256, DIGEST, "invalid_health_digest");
  token(binding.signer_public_key_sha256, DIGEST, "invalid_signer_digest");
  token(binding.key_id, KEY_ID, "invalid_key_identity");
  require(Number.isSafeInteger(binding.health_bytes) && binding.health_bytes === healthBytes.length, "health_size_mismatch");
  require(await sha(healthBytes) === binding.health_sha256, "health_digest_mismatch");
  const health = strictJSON(healthBytes, MAX_HEALTH);
  require(health.schema === "datapulse/v0.4/dataset-health" && object(health._trust_summary) && Array.isArray(health.datasets) && health.datasets.length > 0, "invalid_health");
  const ids = new Set();
  for (const row of health.datasets) {
    require(object(row) && typeof row.dataset_id === "string" && row.dataset_id.length > 0 && !ids.has(row.dataset_id) && typeof row.status === "string" && row.status.length > 0, "invalid_health");
    ids.add(row.dataset_id);
  }
  require(health.checked_at === binding.observed_at, "observation_mismatch");
  const observed = time(binding.observed_at), assembled = time(binding.assembled_at), signed = time(binding.signed_at);
  require(observed <= assembled && assembled <= signed && signed <= now + 300, "invalid_time_order");
  require(now - observed >= -300 && now - observed <= 129600, "outside_freshness_policy");
  if (minimumObservedAt !== undefined) require(observed >= time(minimumObservedAt), "replay_below_floor");
  const publicBytes = await trustedKey(registry, binding.key_id, signed, now);
  require(await sha(publicBytes) === binding.signer_public_key_sha256, "signer_identity_mismatch");
  require(signature.length === 64, "invalid_signature");
  const signedBytes = new Uint8Array(DOMAIN.length + bindingBytes.length);
  signedBytes.set(DOMAIN); signedBytes.set(bindingBytes, DOMAIN.length);
  // importKey/verify throwing for unsupported Ed25519 MUST remain a failure.
  const publicKey = await crypto.subtle.importKey("raw", publicBytes, { name: "Ed25519" }, false, ["verify"]);
  require(await crypto.subtle.verify("Ed25519", publicKey, signature, signedBytes), "invalid_signature");
  return { publication_sha256: identity, observed_at: binding.observed_at, age_seconds: now - observed, age_authenticated: false, policy: POLICY, source_truth_verified: false };
}

async function boundedAsset(response, limit) {
  require(response.ok && response.body, "trusted_registry_unavailable");
  const reader = response.body.getReader(), chunks = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      require(size <= limit, "trusted_registry_oversized");
      chunks.push(value);
    }
  } finally { await reader.cancel(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return bytes;
}

export async function readVerified(context, identity, options) {
  const kv = context.env.DATAPULSE_HEALTH_INDEX, assets = context.env.ASSETS;
  require(kv && typeof kv.get === "function" && assets && typeof assets.fetch === "function", "trust_or_storage_unavailable");
  // Fixed same-deployment trusted asset. No package-provided URL and no network fallback.
  const assetURL = new URL("/.well-known/datapulse-probe-keys.json", context.request.url);
  const registryResponse = await assets.fetch(new Request(assetURL, { headers: { "Cache-Control": "no-store" } }));
  const registry = strictJSON(await boundedAsset(registryResponse, MAX_REGISTRY), MAX_REGISTRY, ["version"]);
  if (identity === "latest") {
    const pointerRaw = await kv.get(PREFIX + "latest.json", "arrayBuffer");
    require(pointerRaw instanceof ArrayBuffer, "missing_pointer");
    const pointer = strictJSON(new Uint8Array(pointerRaw), 1024);
    require(fields(pointer, ["schema", "publication_sha256"]) && pointer.schema === POINTER_SCHEMA, "invalid_pointer");
    identity = token(pointer.publication_sha256, DIGEST, "invalid_publication");
  } else token(identity, DIGEST, "invalid_publication");
  const raw = await kv.get(PREFIX + "objects/" + identity + ".json", "arrayBuffer");
  require(raw instanceof ArrayBuffer, "missing_package");
  const bytes = new Uint8Array(raw);
  require(bytes.length <= MAX_PACKAGE, "oversized_package");
  // Read the consumer clock after storage/asset awaits; a slow read must not
  // retain the earlier request-start freshness or key-window verdict.
  const now = typeof options.clock === "function" ? options.clock() : options.now;
  const verdict = await verifyPackage(bytes, registry, { ...options, now, expectedPublication: identity });
  const response = { schema: RESPONSE_SCHEMA, publication_sha256: identity, package_base64: base64(bytes) };
  return { body: encoder.encode(JSON.stringify(response)), verdict };
}
