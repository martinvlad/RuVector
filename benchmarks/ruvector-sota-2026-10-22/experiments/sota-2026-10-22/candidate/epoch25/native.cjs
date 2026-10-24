'use strict';
// One admitted offline helper; separate actual native indexes over intact supplied source units.
const fs = require('node:fs');
const path = require('node:path');
const { performance } = require('node:perf_hooks');
const { createHash } = require('node:crypto');
const hash = p => createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const partial = {schema_version:1, cases:[], native_index_initializations_attempted:0,
  native_queries_attempted:0, native_queries_completed:0, Node_network_operations_attempted:0, stage:'HELPER_STARTED'};
let progressFd = null;
function progress(stage) {
  partial.stage=stage;
  if (progressFd !== null) {
    fs.writeSync(progressFd,JSON.stringify({stage,at_unix:Date.now()/1000,helper_pid:process.pid,
      native_index_initializations_attempted:partial.native_index_initializations_attempted,
      native_queries_attempted:partial.native_queries_attempted,
      native_queries_completed:partial.native_queries_completed,
      Node_network_operations_attempted:partial.Node_network_operations_attempted,
      active_case_id:partial.active_case_id || null})+'\n');
    fs.fsyncSync(progressFd);
  }
}
function refuseNetwork() {
  partial.Node_network_operations_attempted++;progress('OFFLINE_NETWORK_REFUSAL');
  throw new Error('Offline native helper refuses network access');
}
for (const [name, methods] of Object.entries({
  'node:net':['connect','createConnection'],
  'node:dns':['lookup','resolve','resolve4','resolve6'],
  'node:http':['request','get'], 'node:https':['request','get'],
  'node:dgram':['createSocket']})) {
  const module=require(name); for (const method of methods) module[method]=refuseNetwork;
}


(async () => {
  const root = fs.realpathSync(process.argv[2]);
  const source = fs.readFileSync(process.argv[3]);
  const bundle = JSON.parse(source);
  const output = process.argv[4];
  const planPath=process.argv[5],expectedPlanSha=process.argv[6],admissionPath=process.argv[7];
  if (planPath !== path.join(root,'experiments/sota-2026-10-22/epoch25/plan.json')
      || hash(planPath) !== expectedPlanSha) throw new Error('Native plan gate failed');
  const plan=JSON.parse(fs.readFileSync(planPath));
  const admission=JSON.parse(fs.readFileSync(admissionPath));
  const owner=JSON.parse(fs.readFileSync(path.join(root,'../owner.json')));
  const ownerStat=fs.readFileSync('/proc/70365/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
  if (admissionPath !== path.join(root,'experiments/sota-2026-10-22/epoch25/NATIVE_ADMISSION.json')
      || admission.epoch !== 25 || admission.phase !== 'engineering'
      || admission.verified_actual_remote_readback !== true || admission.plan_sha256 !== expectedPlanSha
      || admission.owner_pid !== 70365 || admission.owner_startticks !== 13868579
      || admission.source_freeze_sha256 !== plan.source_freeze_sha256
      || plan.epoch !== 25 || plan.actual_project !== root
      || plan.source_checkpoint.toLowerCase() !== 'a09506046843bc0c4e28e30865b610b283942e2d'
      || owner.pid !== 70365 || owner.startticks !== 13868579 || Date.now()/1000 >= owner.expires_unix
      || ['Z','X'].includes(ownerStat[0]) || Number(ownerStat[19]) !== 13868579)
    throw new Error('Native actual remote admission/exact owner gate failed');
  const ownPath='experiments/sota-2026-10-22/candidate/epoch25/native.cjs';
  const ownPin=plan.pins.find(row=>row.path === ownPath);
  if (!ownPin || hash(path.join(root,ownPath)) !== ownPin.sha256) throw new Error('Unfrozen native helper');
  progressFd=fs.openSync(process.argv[8],'wx',0o600);progress('ADMISSION_VERIFIED_BEFORE_NATIVE_IMPORT');
  const corePath = path.join(root, 'retrieval/node_modules/@ruvector/core');
  const binary = path.join(root, 'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node');
  if (hash(binary) !== 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e')
    throw new Error('Actual native binary changed');
  const core = require(corePath);
  const packageVersion = require(path.join(corePath, 'package.json')).version;
  const platformVersion = require(path.join(root,
    'retrieval/node_modules/ruvector-core-linux-x64-gnu/package.json')).version;
  const binaryVersion = core.version();
  if (packageVersion !== '0.1.33' || platformVersion !== '0.1.31' || binaryVersion !== '2.3.0')
    throw new Error('Exact native package/core versions changed');
  Object.assign(partial, {package_version:packageVersion,platform_package_version:platformVersion,
    binary_version:binaryVersion,native_binary_sha256:hash(binary),helper_pid:process.pid});
  const traces = [];
  partial.cases = traces;
  const workingRoot = process.cwd();
  for (let i = 0; i < bundle.cases.length; i++) {
    const item = bundle.cases[i];
    const vectors = item.vectors;
    const query = item.query_vector;
    if (!vectors.length || vectors.some(v => v.length !== 384 || v.some(x => !Number.isFinite(x)))
        || query.length !== 384 || query.some(x => !Number.isFinite(x)))
      throw new Error('Finite real BGE384 vectors required');
    const k = Math.min(Math.max(1, item.seed_limit), vectors.length);
    const storage = path.join(workingRoot, 'index-' + i);
    fs.mkdirSync(storage);
    process.chdir(storage);
    const started = performance.now();
    partial.stage = 'BEFORE_NATIVE_INDEX';
    partial.active_case_id = item.id;
    partial.native_index_initializations_attempted++;progress('BEFORE_NATIVE_INDEX');
    const db = new core.VectorDb({dimensions:384, distanceMetric:core.JsDistanceMetric.Cosine,
      storagePath:path.join(storage, 'ruvector.db')});
    if (await db.len() !== 0) throw new Error('Native index not initially empty');
    for (let j = 0; j < vectors.length; j++)
      await db.insert({id:String(j), vector:new Float32Array(vectors[j])});
    if (await db.len() !== vectors.length) throw new Error('Native index incomplete');
    const initialized = performance.now();
    partial.stage = 'BEFORE_NATIVE_SEARCH';
    partial.native_queries_attempted++;progress('BEFORE_NATIVE_SEARCH');
    const hits = await db.search({vector:new Float32Array(query), k});
    const queryMs = performance.now() - initialized;
    partial.native_queries_completed++;progress('AFTER_NATIVE_SEARCH');
    const ids = hits.map(hit => Number(hit.id));
    if (ids.length !== k || new Set(ids).size !== k
        || ids.some(id => !Number.isInteger(id) || id < 0 || id >= vectors.length))
      throw new Error('Native returned invalid observed IDs');
    const rawHits = hits.map(hit => {
      const row = {id:hit.id};
      for (const key of Object.keys(hit)) {
        const value = hit[key];
        if (typeof value === 'number' && !Number.isFinite(value))
          throw new Error('Nonfinite native hit field');
        row[key] = value;
      }
      for (const key of ['score', 'distance']) {
        if (key in hit) {
          if (typeof hit[key] !== 'number' || !Number.isFinite(hit[key]))
            throw new Error('Invalid raw native score/distance');
          row[key] = hit[key];
        }
      }
      return row;
    });
    traces.push({case_id:item.id, ids, raw_hits:rawHits, requested_k:k,
      initialized_vectors:await db.len(), initialization_ms:initialized-started,
      query_ms:queryMs, raw_hit_field_names:rawHits.length ? Object.keys(rawHits[0]) : [],
      score_semantics:'Raw native field(s) retained without reinterpretation or reranking.',
      effective_seed_limit:item.seed_limit});
    process.chdir(workingRoot);
    progress('CASE_COMPLETED');
  }
  fs.writeFileSync(output, JSON.stringify({schema_version:1,native:true,cases:traces,
    bundle_sha256:createHash('sha256').update(source).digest('hex'),
    native_binary_sha256:hash(binary),package_version:packageVersion,binary_version:binaryVersion,
    platform_package_version:platformVersion,
    helper_pid:process.pid,helper_cwd:process.cwd(),native_indexes:traces.length,
    native_index_initializations_attempted:partial.native_index_initializations_attempted,
    native_queries_attempted:partial.native_queries_attempted,
    native_queries_completed:partial.native_queries_completed,
    Node_network_operations_attempted:partial.Node_network_operations_attempted,
    helper_peak_RSS_bytes:process.resourceUsage().maxRSS*1024,
    helper_user_CPU_microseconds:process.resourceUsage().userCPUTime,
    helper_system_CPU_microseconds:process.resourceUsage().systemCPUTime})+'\n', {flag:'wx'});
  progress('HELPER_COMPLETED');
  if (progressFd !== null) fs.closeSync(progressFd);
})().catch(error => {
  partial.error = {name:error.name,message:String(error.message || error)};
  try {progress('HELPER_FAILED');} catch (ignored) {}
  try { fs.writeFileSync(process.argv[4]+'.failure.json',JSON.stringify(partial)+'\n',{flag:'wx'}); }
  catch (receiptError) { console.error('Failure receipt unavailable: '+receiptError.message); }
  console.error(error.stack || String(error)); process.exitCode = 1;
});
