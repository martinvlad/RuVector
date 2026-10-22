"""Extract minimal finite saved-output data. Requires the original local evidence.

This builder never invokes an embedding model, native search, reranker or API.
The published replay.py needs only Python's standard library and exported files.
"""
from pathlib import Path
import datetime
import hashlib
import json
import random
import shutil
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SW = ROOT / 'experiments/swarm'
CO = ROOT / 'experiments/compounding'
SOURCES = []


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(path):
    path = Path(path)
    SOURCES.append({'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
                    'sha256': sha(path)})
    return path


def read(path):
    return json.loads(source(path).read_text())


def write(name, value):
    path = HERE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    assert not path.exists(), 'Refuse overwrite: ' + name
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')


def archive_rows(path):
    source(path)
    with tarfile.open(path, 'r:*') as archive:
        raw = archive.extractfile('decisions.json').read()
    SOURCES.append({'archive': str(path.relative_to(ROOT)), 'member': 'decisions.json',
                    'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    return json.loads(raw)


def component_groups(queries):
    graph = {s['file_path']: set() for q in queries for s in q['snippets']}
    for q in queries:
        names = {s['file_path'] for s in q['snippets']}
        for name in names:
            graph[name].update(names - {name})
    groups = {}
    for name in sorted(graph):
        if name in groups:
            continue
        pending, members = [name], set()
        while pending:
            v = pending.pop()
            if v not in members:
                members.add(v)
                pending.extend(graph[v] - members)
        key = hashlib.sha256(json.dumps(sorted(members), separators=(',', ':')).encode()).hexdigest()
        for v in members:
            groups[v] = key
    return groups


def export_study(name, chunks, queries, parent, champion, candidate, historical=False):
    documents = sorted({c['file_path'] for c in chunks})
    docid = {v: i for i, v in enumerate(documents)}
    referenced = {int(j) for row in parent for j in row['native_ids'][:64] + row['reranked_ids']}
    geometry = [[j, docid[chunks[j]['file_path']], *chunks[j]['span']] for j in sorted(referenced)]
    component = component_groups(queries)
    rows = []
    for i, (q, raw, old, new) in enumerate(zip(queries, parent, champion, candidate)):
        assert raw['index'] == old['index'] == new['index'] == i
        assert q['source'] == raw['source'] == old['source'] == new['source']
        assert q['source_index'] == raw['source_index'] == old['source_index'] == new['source_index']
        group = q['snippets'][0]['file_path'] if historical else component[q['snippets'][0]['file_path']]
        row = {'index': i, 'source': q['source'], 'source_index': q['source_index'],
               'query_sha256': hashlib.sha256(q['query'].encode()).hexdigest(),
               'group': group,
               'gold': [[docid[g['file_path']], *g['span']] for g in q['snippets']],
               'native64': raw['native_ids'][:64], 'reranked64': raw['reranked_ids'],
               'champion_ids': old['champion_ids'] if historical else old['fused64'],
               'candidate_ids': new['candidate_ids'] if historical else new['ids'],
               'champion_metrics': old['champion'] if historical else old['metrics'],
               'candidate_metrics': new['candidate'] if historical else new['metrics']}
        if historical:
            assert q['query_id'] == raw['query_id'] == old['query_id'] == new['query_id']
            row['query_id'] = q['query_id']
        else:
            row['fold'] = new['fold']
        rows.append(row)
    assert len(rows) == len(queries) == len(parent) == len(champion) == len(candidate)
    packet = {'schema_version': 1, 'study': name, 'scope': 'historical_observed' if historical else 'custom_observed_development',
              'corpus_chunks': len(chunks), 'corpus_documents': len(documents),
              'geometry_records': len(geometry), 'documents': documents, 'chunks': geometry,
              'chunk_record_columns': ['original_chunk_id', 'document_index', 'character_start', 'character_end'],
              'gold_record_columns': ['document_index', 'character_start', 'character_end'],
              'query_text_included': False, 'query_text_binding': 'UTF8 query SHA256 and source index; original licensed source queries are not redistributed',
              'rows': rows}
    write('data/' + name + '.json', packet)
    return packet


def copy_evidence(src, target):
    src = source(src)
    dst = HERE / target
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copyfile(src, dst)


def main():
    devproof = read(CO / 'audit/retrieval-independent-verification.json')
    histproof = read(CO / 'audit/historical-replay-independent-verification.json')
    assert sha(CO / 'audit/retrieval-independent-verification.json') == '47944bcf76c89bcc52126d23bb1f49735adee203cca5d4e3c348356a1deac690'
    assert sha(CO / 'audit/historical-replay-independent-verification.json') == '9f95e00c58817b041737151fbfcea0b5a865d44c4d4c2a7327d42b1bf35d8080'
    chunks = read(SW / 'published-retrieval/chunks.json')
    queries = read(SW / 'published-retrieval/full-mini/queries.json')
    raw = archive_rows(SW / 'gpu-api-control/imported/split-complete/public-results.tgz')
    old = read(SW / 'api8b-fp32-rank-fusion/decisions.json')
    new = read(CO / 'retrieval/v2/selected/decisions.json')
    dev = export_study('development', chunks, queries, raw, old, new)
    assert len(dev['rows']) == 776 and dev['corpus_documents'] == 72 and dev['corpus_chunks'] == 17403
    hchunks = read(SW / 'api8b-fp32-rank-fusion-fresh/chunks.json')
    hqueries = read(SW / 'api8b-fp32-rank-fusion-fresh/queries.json')
    hraw = archive_rows(SW / 'api8b-fp32-rank-fusion-fresh-pipeline/output/imported-gpu/public-results.tgz')
    hrows = read(CO / 'retrieval/historical-replay/decisions.json')
    hist = export_study('historical64', hchunks, hqueries, hraw, hrows, hrows, historical=True)
    assert len(hist['rows']) == 64 and hist['corpus_documents'] == 80
    candidates = []
    for roundno in (1, 2):
        for p in sorted((CO / 'retrieval/v2' / ('round' + str(roundno))).glob('*/results.json')):
            candidates.append({'round': roundno, 'source': str(p.relative_to(ROOT)), 'source_sha256': sha(p), 'results': read(p)})
    assert len(candidates) == 37 and [sum(x['round'] == r for x in candidates) for r in (1, 2)] == [32, 5]
    write('search-history.json', {'scope': 'all37 adaptive observedDEV policies; selected verification replay is separate',
                                 'policies': candidates, 'policy_count': 37, 'selected_verification_replays': 1,
                                 'not_replayed_here': 'This minimal kit replays the two fixed selected64-list fusions; it records all37 original aggregate outcomes without rerunning the full128/diversity search.'})
    rng = random.Random(20261022)
    dev_indices = [[rng.randrange(72) for _ in range(72)] for _ in range(2000)]
    write('data/development-bootstrap.json', {'seed': 20261022, 'generator': 'Python random.Random.randrange, original independent audit', 'indices': dev_indices})
    import numpy as np
    generator = np.random.default_rng(20261022)
    hist_indices = [list(map(int, generator.integers(0, 8, 8))) for _ in range(2000)]
    write('data/historical64-bootstrap.json', {'seed': 20261022, 'generator': 'NumPy default_rng.integers, original producer and independently verified historical audit', 'indices': hist_indices})
    selected = read(CO / 'retrieval/v2/selected/results.json')
    hresult = read(CO / 'retrieval/historical-replay/results.json')
    write('expected.json', {'development': {'candidate_table': selected['table'], 'paired_document_diagnostics': devproof['paired_document_diagnostics']},
                            'historical64': {'table': hresult['table'], 'group_statistics': hresult['group_paired_sum_deltas'],
                                             'CI95': hresult['descriptive_2000_document_bootstrap_CI95'],
                                             'draw_distribution_sha256': histproof['descriptive_paired_document_bootstrap']['distribution_sha256']}})
    for src, dst in [
        (CO / 'audit/retrieval-independent-verification.json', 'evidence/development-independent-audit.json'),
        (CO / 'audit/historical-replay-independent-verification.json', 'evidence/historical-independent-audit.json'),
        (CO / 'retrieval/v2/selected-recipe.json', 'evidence/selected-recipe.json'),
        (CO / 'retrieval/v2/plan.json', 'evidence/development-plan.json'),
        (CO / 'retrieval/historical-replay/plan.json', 'evidence/historical-plan.json'),
        (CO / 'retrieval/aborted-pre-quality-runtime-inefficiency.json', 'evidence/pre-quality-abort.json'),
        (CO / 'confirmation-gpu/NOT_EXECUTED_WINDOW_EXPIRED.json', 'evidence/confirmation96-unscored.json'),
        (SW / 'api8b-fp32-rank-fusion-fresh-audit/independent-verification-v3.json', 'evidence/prior-confirmed-study-audit.json'),
        (SW / 'gpu-api-control/imported/split-complete/extracted/model-receipt.json', 'evidence/FP32-model-receipt.json'),
        (SW / 'api-qwen8b-recovery/live/extracted/output/embedding-receipt.json', 'evidence/hosted-embedding-receipt.json'),
        (SW / 'published-retrieval/source-receipts.json', 'evidence/corpus-source-receipts.json'),
        (SW / 'published-retrieval/source/run_benchmark.py', 'upstream/run_benchmark.py'),
        (SW / 'published-retrieval/source/benchmark_types.py', 'upstream/benchmark_types.py')]:
        copy_evidence(src, dst)
    assert sha(HERE / 'upstream/run_benchmark.py') == 'e4262263630f5fe70f074973b934808850dec8f92ce0d82bc2542fe172e316ef'
    assert sha(HERE / 'upstream/benchmark_types.py') == '91cce38bb48deb8941557f768d86911fd047515fdc4cf8eb250f0a6a6c52e4a2'
    license_response = json.loads((HERE / 'evidence/upstream-license-response.json').read_text())['structuredContent']
    (HERE / 'upstream/LICENSE').write_text(license_response['content'])
    write('extraction-provenance.json', {'schema_version': 1, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'source_files_and_archive_members': SOURCES, 'builder_sha256': sha(HERE / 'build_from_workspace.py'),
         'original_parent_ZIP_SHA256': 'da4f67550c39c0f668625e4f2cf484ce9badf2510d9100fc4a9f2984e40b5486',
         'original_compounding_delta_ZIP_SHA256': '9b29bec10491594c6c2ee8cbaceecf07b47cf97f13f6dd24bfe37b6252c2c45e',
         'transformations': ['Retain only saved native64/reranked64, both fixed fusion outputs and existing metrics', 'Prune unreferenced chunk geometry; retain original numeric IDs and document-index mapping', 'Omit all chunk text, gold answer text, raw query text, vectors, weights and logits', 'Materialize exactly the original seeded2000 bootstrap group-index draws for a stdlib replay'],
         'new_scientific_model_native_or_paid_API_calls': 0, 'bootstrap_indices_are_not_new_quality_search': True,
         'scope': 'Saved-output extraction only; not inference reproduction or external attestation'})
    print(json.dumps({'development_queries': 776, 'historical_queries': 64, 'development_geometry': dev['geometry_records'], 'historical_geometry': hist['geometry_records'], 'policies_recorded': 37}))


if __name__ == '__main__':
    main()
