'use strict';
const fs = require('node:fs');
const { performance } = require('node:perf_hooks');
const { createHash } = require('node:crypto');
const core = require('@ruvector/core');

(async () => {
  const bytes = fs.readFileSync(process.argv[2]);
  const bundle = JSON.parse(bytes);
  const db = new core.VectorDb({ dimensions: 384, distanceMetric: core.JsDistanceMetric.Cosine });
  if (await db.len() !== 0) throw new Error('Native working directory is not empty');
  for (let i=0;i<bundle.vectors.length;i++)
    await db.insert({id:String(i),vector:new Float32Array(bundle.vectors[i])});
  if (await db.len() !== bundle.vectors.length) throw new Error('Native index is incomplete');
  const queries = [];
  for (const q of bundle.query_vectors) {
    const t = performance.now();
    const hits = await db.search({vector:new Float32Array(q),k:Math.min(40,bundle.vectors.length)});
    const ids = hits.map(x=>Number(x.id));
    if (ids.length !== new Set(ids).size) throw new Error('Duplicate nearest neighbors');
    queries.push({ids,latency_ms:performance.now()-t});
  }
  const binary = require.resolve('ruvector-core-linux-x64-gnu/ruvector.node');
  fs.writeFileSync(process.argv[3],JSON.stringify({
    queries,bundle_sha256:createHash('sha256').update(bytes).digest('hex'),
    native_binary_sha256:createHash('sha256').update(fs.readFileSync(binary)).digest('hex'),
    binary_version:core.version(),package_version:require('@ruvector/core/package.json').version,
    vectors:await db.len(),native:true
  }));
})().catch(e=>{console.error(e);process.exitCode=1;});
