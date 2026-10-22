'use strict';
// Local baseline endpoint for evaluator-contract checks. This is not a winning-model claim.
const http = require('node:http');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');

function normalizeResponse(response, questions) {
  const answers = Object.create(null);
  for (const [id, question] of Object.entries(questions)) {
    const answer = response.answers[id];
    if (!answer) throw new Error('Missing answer for ' + id);
    answers[id] = { ...answer, type: question.type };
    if (question.type === 'score' && Array.isArray(answer.probabilities)) {
      answers[id].probabilities = Object.fromEntries(answer.probabilities.map((p, i) => [String(i), p]));
    }
  }
  return { model: 'ruvector-native-baseline', answers, usage: response.usage };
}

function nativeEngine() {
  const { createTypesafe } = require('@ruvector/typesafe');
  const engine = createTypesafe({
    embedder: { kind: 'onnx', modelDir: path.join(root, 'models'), manifest: path.join(root, 'models/manifest.json') },
    engine: { choiceInstructions: true },
  });
  if (engine.backend !== 'native') throw new Error('Native ONNX baseline is required');
  return engine;
}

function createServer(engine) {
  return http.createServer(async (request, response) => {
    const send = (status, value) => {
      response.writeHead(status, { 'content-type': 'application/json' });
      response.end(JSON.stringify(value));
    };
    if (request.method === 'GET' && request.url === '/health') {
      return send(200, { model: 'ruvector-native-baseline', backend: engine.backend, binary_version: engine.version });
    }
    if (request.method !== 'POST' || request.url !== '/v1/systemone') return send(404, { error: 'Unknown route' });
    try {
      let bytes = 0;
      const chunks = [];
      for await (const chunk of request) {
        bytes += chunk.length;
        if (bytes > 128 * 1024) {
          send(413, { error: 'Request is too large' });
          request.resume();
          return;
        }
        chunks.push(chunk);
      }
      const body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
      if (!body.questions || typeof body.questions !== 'object' || Array.isArray(body.questions))
        return send(400, { error: 'questions must be a question map' });
      for (const question of Object.values(body.questions))
        if (!question || !['choice', 'score', 'noul'].includes(question.type))
          return send(400, { error: 'Unknown question type' });
      const state = typeof body.state === 'string' ? body.state : JSON.stringify(body.state);
      if (typeof state !== 'string') return send(400, { error: 'state is required' });
      const result = await engine.systemOne({ state, questions: body.questions });
      return send(200, normalizeResponse(result, body.questions));
    } catch (error) {
      return send(error.kind === 'limit' ? 413 : 400, { error: String(error.message || error) });
    }
  });
}

if (require.main === module) {
  const port = Number(process.argv[2] || 8787);
  const server = createServer(nativeEngine());
  server.listen(port, '127.0.0.1', () => console.log('Local evaluator baseline: http://127.0.0.1:' + port + '/v1/systemone'));
}
module.exports = { normalizeResponse, nativeEngine, createServer };
