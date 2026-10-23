// Structural prelaunch source closure. No filesystem, networking, or inference.
// Call only with independently reviewed, hash-verified manifest inputs.
// A PASS compares declared identities; it does NOT hash or reconstruct files.
export function sourceClosure(planPins, publishedFiles, externalRegistry) {
  const issues = [];
  const issue = (code, path, detail) => issues.push({ code, path: String(path ?? ""), detail });
  const validPath = p => typeof p === "string" && p.length > 0 && !p.startsWith("/") &&
    !/[\\:\u0000]/.test(p) && p.split("/").every(x => x !== "" && x !== "." && x !== "..");
  const validHash = s => typeof s === "string" && /^[0-9a-f]{64}$/.test(s);
  const validBytes = n => Number.isSafeInteger(n) && n >= 0;
  const validRecord = (r, label, withBytes) => {
    if (!r || !validPath(r.path) || !validHash(r.sha256) || (withBytes && !validBytes(r.bytes))) {
      issue("INVALID_RECORD", r?.path, label); return false;
    }
    return true;
  };
  if (![planPins, publishedFiles, externalRegistry].every(Array.isArray))
    return { status: "STRUCTURAL_CLOSURE_FAIL", checked_pins: 0, covered_public: 0,
      covered_external: 0, missing_count: 0,
      issues: [{code:"INVALID_INPUT",path:"",detail:"All inputs must be arrays"}],
      scope: "Declared metadata only; no actual file hashes, reconstruction, inference or benchmark result" };
  const publicMap = new Map();
  for (const r of publishedFiles) {
    if (!validRecord(r, "published", true)) continue;
    const prior = publicMap.get(r.path);
    if (prior && (prior.sha256 !== r.sha256 || prior.bytes !== r.bytes))
      issue("CONFLICTING_PUBLIC_IDENTITY", r.path, "Repeated path differs across public manifests");
    else publicMap.set(r.path, {path:r.path,sha256:r.sha256,bytes:r.bytes});
  }
  const registry = new Map();
  const isModelPath = p => p.startsWith("models/") ||
    /^experiments\/sota-[^/]+\/candidate\/[^/]+\/assets\//.test(p);
  const isNativePath = p => p.startsWith("node_modules/") || p.startsWith("retrieval/node_modules/");
  for (const r of externalRegistry) {
    if (!validRecord(r, "external", true)) continue;
    let ok = true;
    if (!((r.kind === "model_asset" && isModelPath(r.path)) ||
          (r.kind === "native_runtime" && isNativePath(r.path)))) {
      issue("UNSUPPORTED_EXTERNAL_KIND_OR_NAMESPACE", r.path, String(r.kind)); ok = false;
    }
    for (const name of ["provenance_manifest", "acquisition_helper"]) {
      const q = r[name];
      if (!validRecord(q, name, false)) { ok = false; continue; }
      const pub = publicMap.get(q.path);
      if (!pub || pub.sha256 !== q.sha256) {
        issue("UNPUBLISHED_OR_CHANGED_EXTERNAL_PROVENANCE", r.path, name + ":" + q.path); ok = false;
      }
    }
    const prior = registry.get(r.path);
    if (prior && (prior.sha256 !== r.sha256 || prior.bytes !== r.bytes || prior.kind !== r.kind)) {
      issue("CONFLICTING_EXTERNAL_IDENTITY", r.path, "Repeated external path differs"); ok = false;
    }
    const pub = publicMap.get(r.path);
    if (pub && (pub.sha256 !== r.sha256 || pub.bytes !== r.bytes)) {
      issue("PUBLIC_EXTERNAL_IDENTITY_MISMATCH", r.path, "Public and external declarations conflict"); ok = false;
    }
    if (ok) registry.set(r.path, {path:r.path,sha256:r.sha256,bytes:r.bytes,kind:r.kind});
  }
  const seen = new Set();
  let checked = 0, publicCount = 0, externalCount = 0, missing = 0;
  for (const r of planPins) {
    if (!validRecord(r, "plan", false)) continue;
    if (seen.has(r.path)) { issue("DUPLICATE_PLAN_PIN", r.path, "One identity per frozen pin required"); continue; }
    seen.add(r.path); checked++;
    const pub = publicMap.get(r.path);
    if (pub) {
      if (pub.sha256 !== r.sha256) issue("PUBLIC_PIN_HASH_MISMATCH", r.path, "Frozen/public SHA256 differ");
      else publicCount++;
      continue;
    }
    const ext = registry.get(r.path);
    if (ext) {
      if (ext.sha256 !== r.sha256) issue("EXTERNAL_PIN_HASH_MISMATCH", r.path, "Frozen/external SHA256 differ");
      else externalCount++;
      continue;
    }
    missing++; issue("UNDECLARED_FROZEN_SOURCE", r.path, "Neither public nor an explicit reviewed model/native restore identity");
  }
  const cmp = (a,b) => a < b ? -1 : a > b ? 1 : 0;
  issues.sort((a,b) => cmp(a.path,b.path) || cmp(a.code,b.code) || cmp(a.detail,b.detail));
  return {status:issues.length ? "STRUCTURAL_CLOSURE_FAIL" : "STRUCTURAL_CLOSURE_PASS",
    checked_pins:checked, covered_public:publicCount, covered_external:externalCount,
    missing_count:missing, issues,
    scope:"Declared metadata only; no actual file hashes, reconstruction, inference or benchmark result"};
}
