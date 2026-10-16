import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { RuGraph, RuGraphError } from '../index.mjs';

const base = new URL('../../../../crates/ruvector-language/examples/', import.meta.url);
const client = new RuGraph();
async function fixture() {
  const source = await readFile(new URL('incident.rvg', base), 'utf8');
  return { program: await client.compile(source), snapshot: JSON.parse(await readFile(new URL('snapshot.json', base))),
    context: JSON.parse(await readFile(new URL('context.json', base))) };
}
test('real binary compiles, executes, and replays the incident program', async () => {
  const request = await fixture(); const receipt = await client.run(request);
  assert.equal(receipt.output.kind, 'decisions');
  assert.ok(receipt.output.items.some(x => x.subject === 'database' && x.predicate === 'Degraded' && x.status === 'supported'));
  assert.deepEqual(await client.replay(request, receipt), receipt);
});
test('expired and deleted evidence cannot retain a supported diagnosis', async () => {
  const request = await fixture(); const initial = await client.run(request);
  request.context.now = 1100;
  const expired = await client.run(request);
  assert.ok(expired.output.items.every(x => x.status === 'unknown'));
  await assert.rejects(client.replay(request, initial), error => error.code === 'REPLAY_MISMATCH');
  request.context.now = 1000; request.snapshot.observations = [];
  const removed = await client.run(request);
  assert.ok(removed.output.items.every(x => x.status === 'unknown'));
});
test('program effects cannot grant host permissions', async () => {
  const request = await fixture(); request.context.capabilities = ['graph.read'];
  await assert.rejects(client.run(request), error => error instanceof RuGraphError && error.code === 'UNAUTHORIZED');
});
test('text and JSON frontends agree, duplicate keys and prediction laundering fail', async () => {
  const request = await fixture();
  assert.deepEqual(await client.compile(JSON.stringify(request.program)), request.program);
  await assert.rejects(client.compile('{"version":1,"version":2}'), RuGraphError);
  const source = 'program bad { effect graph.read; effect model.predict; effect decision.emit; budget 10000; let n = nodes "Service"; let p = predict n "Cause" model "v1" top 2; let a = assess p; emit a; }';
  await assert.rejects(client.compile(source), RuGraphError);
});
test('binding rejects nonfinite request numbers before invoking runtime', async () => {
  const request = await fixture(); request.context.now = NaN;
  assert.throws(() => client.run(request), error => error.code === 'INVALID_INPUT');
});
