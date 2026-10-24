'use strict';
// One owned helper, separate literal native indexes over supplied fixture excerpts.
const fs = require('node:fs');
const path = require('node:path');
const { performance } = require('node:perf_hooks');
const { createHash } = require('node:crypto');
const hash = p => createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const partial = {schema_version:1, cases:[], native_index_initializations_attempted:0,
  native_queries_attempted:0, stage:'HELPER_STARTED'};

(async () => {
  const root = fs.realpathSync(process.argv[2]);
  const source = fs.readFileSync(process.argv[3]);
  const bundle = JSON.parse(source);
  const output = process.argv[4];
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
    partial.native_index_initializations_attempted++;
    const db = new core.VectorDb({dimensions:384, distanceMetric:core.JsDistanceMetric.Cosine,
      storagePath:path.join(storage, 'ruvector.db')});
    if (await db.len() !== 0) throw new Error('Native index not initially empty');
    for (let j = 0; j < vectors.length; j++)
      await db.insert({id:String(j), vector:new Float32Array(vectors[j])});
    if (await db.len() !== vectors.length) throw new Error('Native index incomplete');
    const initialized = performance.now();
    partial.stage = 'BEFORE_NATIVE_SEARCH';
    partial.native_queries_attempted++;
    const hits = await db.search({vector:new Float32Array(query), k});
    const queryMs = performance.now() - initialized;
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
    partial.stage = 'CASE_COMPLETED';
  }
  fs.writeFileSync(output, JSON.stringify({schema_version:1,native:true,cases:traces,
    bundle_sha256:createHash('sha256').update(source).digest('hex'),
    native_binary_sha256:hash(binary),package_version:packageVersion,binary_version:binaryVersion,
    platform_package_version:platformVersion,
    helper_pid:process.pid,helper_cwd:process.cwd(),native_indexes:traces.length})+'\n', {flag:'wx'});
})().catch(error => {
  partial.error = {name:error.name,message:String(error.message || error)};
  try { fs.writeFileSync(process.argv[4]+'.failure.json',JSON.stringify(partial)+'\n',{flag:'wx'}); }
  catch (receiptError) { console.error('Failure receipt unavailable: '+receiptError.message); }
  console.error(error.stack || String(error)); process.exitCode = 1;
});
