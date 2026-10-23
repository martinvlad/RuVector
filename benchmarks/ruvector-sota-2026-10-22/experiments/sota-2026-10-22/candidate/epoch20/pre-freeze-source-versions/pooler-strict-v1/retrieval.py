"""Late BGE inference and actual pinned native index per supplied corpus."""
from __future__ import annotations
import hashlib
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import common as C

BGE_SOURCE = C.PREFIX + 'candidate/epoch3/models.py'
BGE_SOURCE_SHA = 'c5cf3500a89837e71adc754f0dc96d090e172068031545fc55ee349e80210716'
CONTEXT_SOURCE = C.PREFIX + 'candidate/epoch15/context.py'
CONTEXT_SOURCE_SHA = '9bf168e90511708c2aa5e6248d1806c57e5fc48ffa1c97ceab218c757e5f76fb'
QUERY_PREFIX = 'Represent this sentence for searching relevant passages: '


def remaining(deadline):
    n = deadline - time.time()
    if n <= 0: raise TimeoutError('Bounded worker deadline reached')
    return n


def reference(vectors, queries):
    rows = []
    for q in queries:
        qn = math.sqrt(math.fsum(x * x for x in q))
        scores = [math.fsum(x * y for x, y in zip(v, q)) /
                  (math.sqrt(math.fsum(x * x for x in v)) * qn) for v in vectors]
        rows.append({'cosine_similarities': scores,
            'full_cosine_order': sorted(range(len(vectors)), key=lambda i: (-scores[i], i))})
    return rows


def engineering_bundle(rows):
    vocab = ['lamp', 'on', 'not', 'box', 'blue']
    def vector(text):
        tokens = re.findall('[a-z]+', text.lower())
        return [tokens.count(x) for x in vocab] + [0] * 379
    return {'vectors': [vector(r['premise']) for r in rows],
            'query_vectors': [vector(r['hypothesis']) for r in rows]}


def lexical_ids(chunks, hypothesis, k):
    query = set(re.findall(r'\w+', hypothesis.casefold()))
    words = [set(re.findall(r'\w+', text.casefold())) for text in chunks]
    scores = [len(query & w) / max(1, len(query | w)) for w in words]
    return sorted(range(len(chunks)), key=lambda i: (-scores[i], i))[:k]


def native(bundle, folder, tag, deadline, counters, progress):
    if (not bundle['vectors'] or any(len(v) != 384 for v in bundle['vectors'] + bundle['query_vectors'])
            or any(not math.isfinite(x) for v in bundle['vectors'] + bundle['query_vectors'] for x in v)):
        raise ValueError('Finite actual384-dimensional vectors required')
    counters['native_index_initializations_attempted'] += 1
    counters['native_queries_attempted'] += len(bundle['query_vectors']); progress()
    with tempfile.TemporaryDirectory(prefix='ruvector-e20-' + tag + '-') as tmp:
        work = Path(tmp); source = work / 'bundle.json'; target = work / 'native.json'
        C.write_new(source, bundle)
        p = subprocess.Popen(['node', str(C.checked(C.NATIVE_SCRIPT)), str(source), str(target)],
            cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        attempt = {'pid': p.pid, 'pgid': os.getpgid(p.pid), 'worker_pid': os.getpid(),
                   'source_script_sha256': C.NATIVE_SCRIPT_SHA, 'tag': tag}
        C.write_new(folder / ('native-attempt-' + tag + '.json'), attempt)
        try: stdout, stderr = p.communicate(timeout=min(30, remaining(deadline)))
        finally:
            if p.poll() is None: p.kill(); p.wait()
        if p.returncode != 0: raise RuntimeError('Pinned native helper failed: ' + stderr[-1000:])
        result = C.read(target); count = min(40, len(bundle['vectors']))
        if (result.get('native') is not True or result.get('native_binary_sha256') != C.NATIVE_BINARY_SHA
                or result.get('package_version') != '0.1.33' or result.get('vectors') != len(bundle['vectors'])
                or len(result.get('queries', [])) != len(bundle['query_vectors'])
                or result.get('bundle_sha256') != C.sha(source)):
            raise ValueError('Actual native index/package/bundle receipt changed')
        for q in result['queries']:
            if (len(q['ids']) != count or len(set(q['ids'])) != count
                    or any(type(i) is not int or i < 0 or i >= len(bundle['vectors']) for i in q['ids'])):
                raise ValueError('Invalid observed native candidate IDs')
        counters['native_index_initializations_completed'] += 1
        counters['native_queries_completed'] += len(result['queries'])
        trace = {'bundle': bundle, 'bundle_sha256': C.sha(source), 'raw_native_output': result,
            'reference': reference(bundle['vectors'], bundle['query_vectors']),
            'initial_length': 0, 'final_length': result['vectors'], 'source_script_sha256': C.NATIVE_SCRIPT_SHA,
            'native_helper_pid': p.pid, 'native_helper_pgid': attempt['pgid'],
            'helper_exit_code': p.returncode, 'helper_exited': True, 'candidate_depth': count,
            'raw_scores_available': False, 'native_order_used_without_replacement': True,
            'scope': 'Native order is observed; saved-vector cosine is an independent numerical reference, never substituted.'}
        C.write_new(folder / ('native-result-' + tag + '.json'), trace)
    progress()
    return trace


class CountedSession:
    def __init__(self, session, counters): self.session, self.counters = session, counters
    def run(self, names, feed):
        n = len(feed['input_ids']); start = time.perf_counter()
        self.counters['BGE_forwards_attempted'] += 1; self.counters['BGE_texts_attempted'] += n
        y = self.session.run(names, feed)
        self.counters['BGE_forwards_completed'] += 1; self.counters['BGE_texts_completed'] += n
        self.counters['BGE_forward_seconds'] += time.perf_counter() - start
        return y


class Evidence:
    def __init__(self, reader, counters):
        models = C.load_module('epoch20_exact_original_bge', BGE_SOURCE, BGE_SOURCE_SHA)
        self.context = C.load_module('epoch20_exact_source_context15', CONTEXT_SOURCE, CONTEXT_SOURCE_SHA)
        counters['BGE_initializations_attempted'] += 1
        counters['ORT_sessions_attempted'] += 1
        self.bge = models.BgeEncoder(C.ROOT)
        counters['ORT_sessions_completed'] += 1
        self.bge.session = CountedSession(self.bge.session, counters)
        counters['BGE_initializations_completed'] += 1
        self.reader, self.counters = reader, counters
        self.receipt = dict(self.bge.receipt, wrapper_source_sha256=BGE_SOURCE_SHA,
                            context_source_sha256=CONTEXT_SOURCE_SHA,
                            query_prefix=QUERY_PREFIX, batch_size=8, no_warmup=True)

    def prepare(self, state, hypotheses):
        units = self.context.partition(state, self.reader.tokenizer, self.bge.raw_tokenizer,
            target=128, nli_cap=160, bge_cap=256, max_units=192)
        prelude = self.context.select_prelude(state, units, self.reader.tokenizer)
        chunks = [state[u['start']:u['end']] for u in units]
        queries = [QUERY_PREFIX + h for h in hypotheses]
        if any(len(self.bge.raw_tokenizer.encode(q).ids) > 256 for q in queries):
            raise ValueError('Exact retrieval query over256; no clipping')
        if any(len(self.reader.tokenizer.encode('', h).ids) > 512 for h in hypotheses):
            raise ValueError('Exact whole hypothesis over512; no clipping')
        vectors, doc_diagnostics = self.bge.encode(chunks)
        query_vectors, query_diagnostics = self.bge.encode(queries)
        return units, prelude, chunks, {'vectors': vectors.tolist(), 'query_vectors': query_vectors.tolist()}, {
            'document_embedding': doc_diagnostics, 'query_embedding': query_diagnostics,
            'exact_document_texts': chunks, 'exact_query_texts': queries}

    def pack(self, state, units, ranking, hypothesis, prelude):
        return self.context.pack(state, units, ranking, hypothesis, self.reader.tokenizer,
            pair_cap=512, rank_depth=min(40, len(units)), prelude=prelude)
