'use strict';
const readline = require('node:readline');
const path = require('node:path');
const crypto = require('node:crypto');
const fs = require('node:fs');
const { nativeEngine, normalizeResponse } = require('../../optimization/baseline-server.cjs');
const root = path.resolve(__dirname, '../../..');
const engine = nativeEngine();
const manifest = fs.readFileSync(path.join(root, 'models/manifest.json'));
const binary = Object.keys(require.cache).find(p => p.endsWith('.node') && p.includes('typesafe'));
if (!binary) throw new Error('Actual loaded native binary path is required');
console.log(JSON.stringify({ status: 'ready', backend: engine.backend, binary_version: engine.version,
  package: '@ruvector/typesafe', package_version: require('@ruvector/typesafe/package.json').version,
  binary_sha256: crypto.createHash('sha256').update(fs.readFileSync(binary)).digest('hex'),
  model_manifest_sha256: crypto.createHash('sha256').update(manifest).digest('hex') }));
const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
(async () => {
  for await (const line of lines) {
    try {
      const request = JSON.parse(line);
      const result = await engine.systemOne(request);
      console.log(JSON.stringify({ ok: true, response: normalizeResponse(result, request.questions) }));
    } catch (error) {
      console.log(JSON.stringify({ ok: false, error: String(error.message || error) }));
    }
  }
})().catch(error => { console.error(String(error)); process.exitCode = 1; });
