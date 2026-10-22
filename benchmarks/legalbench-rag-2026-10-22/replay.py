#!/usr/bin/env python3
"""Offline saved-output LegalBench-RAG replay; Python standard library only.

No embedding, native search, model, network, API or original corpus execution.
"""
from collections import Counter
from fractions import Fraction
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import math
import random

HERE = Path(__file__).resolve().parent
KS = [1, 2, 4, 8, 16, 32, 64]
METRICS = ['precision', 'recall', 'f1']


def read(path):
    def bad(value):
        raise ValueError('Nonfinite JSON number: ' + value)
    return json.loads(Path(path).read_text(), parse_constant=bad)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def close(actual, expected):
    assert type(actual) in (int, float) and math.isfinite(actual)
    assert math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12), (actual, expected)


def verify_manifest():
    records = read(HERE / 'manifest.json')['files']
    seen = set()
    for record in records:
        rel = PurePosixPath(record['path'])
        assert not rel.is_absolute() and '..' not in rel.parts and str(rel) not in seen
        seen.add(str(rel))
        path = HERE / str(rel)
        assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(HERE.resolve())
        raw = path.read_bytes()
        assert len(raw) == record['bytes'] and hashlib.sha256(raw).hexdigest() == record['sha256'], str(rel)
    return len(records)


def fuse(native, reranked, constant):
    assert len(native) == len(set(native)) == len(reranked) == len(set(reranked)) == 64
    scores = {}
    for ids in (native, reranked):
        for rank, chunk in enumerate(ids, 1):
            assert type(chunk) is int and chunk >= 0
            scores[chunk] = scores.get(chunk, Fraction(0)) + Fraction(1, 2 * (constant + rank))
    return sorted(scores, key=lambda chunk: (-scores[chunk], chunk))[:64]


def metric(chunks, gold):
    # Pinned author QAResult pairwise overlap; no union merging of retrieved spans.
    retrieved_length = sum(end - start for _, start, end in chunks)
    gold_length = sum(end - start for _, start, end in gold)
    overlap = sum(max(0, min(aend, bend) - max(astart, bstart))
                  for adoc, astart, aend in chunks for bdoc, bstart, bend in gold if adoc == bdoc)
    precision = overlap / retrieved_length if retrieved_length else 0
    recall = overlap / gold_length if gold_length else 0
    return {'precision': precision, 'recall': recall,
            'f1': 2 * precision * recall / (precision + recall) if precision + recall else 0}


def mean_table(rows, arm, source=None):
    selected = [r for r in rows if source is None or r['source'] == source]
    assert selected
    return [{'k': k, 'n': len(selected), **{m: math.fsum(r[arm + '_metrics'][str(k)][m] for r in selected) / len(selected)
             for m in METRICS}} for k in KS]


def groups_from_gold(packet):
    graph = {}
    for row in packet['rows']:
        names = {packet['documents'][g[0]] for g in row['gold']}
        for name in names:
            graph.setdefault(name, set()).update(names - {name})
    output = {}
    for first in sorted(graph):
        if first in output:
            continue
        pending, members = [first], set()
        while pending:
            name = pending.pop()
            if name not in members:
                members.add(name)
                pending.extend(graph[name] - members)
        # The original component identity used ASCII-escaped sorted JSON.
        group = hashlib.sha256(json.dumps(sorted(members), separators=(',', ':')).encode()).hexdigest()
        for name in members:
            output[name] = group
    return output


def replay_study(name, expected):
    packet = read(HERE / 'data' / (name + '.json'))
    rows = packet['rows']
    n = 776 if name == 'development' else 64
    assert len(rows) == n and packet['query_text_included'] is False
    assert len(packet['documents']) == packet['corpus_documents'] and len(set(packet['documents'])) == len(packet['documents'])
    chunks = {}
    for chunk_id, document, start, end in packet['chunks']:
        assert all(type(v) is int for v in [chunk_id, document, start, end])
        assert 0 <= chunk_id < packet['corpus_chunks'] and 0 <= document < len(packet['documents']) and 0 <= start < end
        assert chunk_id not in chunks
        chunks[chunk_id] = (document, start, end)
    assert len(chunks) == packet['geometry_records']
    component = groups_from_gold(packet)
    checks = 0
    for i, row in enumerate(rows):
        assert row['index'] == i
        assert len(row['query_sha256']) == 64 and all(c in '0123456789abcdef' for c in row['query_sha256'])
        for document, start, end in row['gold']:
            assert all(type(v) is int for v in [document, start, end]) and 0 <= start < end and 0 <= document < len(packet['documents'])
            assert packet['documents'][document].split('/')[0] == row['source']
        names = [packet['documents'][g[0]] for g in row['gold']]
        if name == 'development':
            assert {component[v] for v in names} == {row['group']} and row['fold'] == int(row['group'], 16) % 4
        else:
            assert {v for v in names} == {row['group']}
        for arm, constant in [('champion', 10), ('candidate', 20)]:
            ids = fuse(row['native64'], row['reranked64'], constant)
            assert ids == row[arm + '_ids'], (name, i, arm)
            for k in KS:
                actual = metric([chunks[j] for j in ids[:k]], row['gold'])
                for measure, value in actual.items():
                    close(value, row[arm + '_metrics'][str(k)][measure])
                    checks += 1
    tables = {arm: {source: mean_table(rows, arm, None if source == 'equal_weight_ALL' else source)
              for source in sorted({r['source'] for r in rows}) + ['equal_weight_ALL']}
              for arm in ['champion', 'candidate']}
    if name == 'development':
        assert Counter(r['source'] for r in rows) == {s: 194 for s in ['privacy_qa', 'contractnli', 'maud', 'cuad']}
        history = read(HERE / 'search-history.json')
        assert history['policy_count'] == len(history['policies']) == 37
        baseline = next(x['results']['table'] for x in history['policies'] if x['results']['policy']['id'] == 'rrf10-w2of4-n64')
        expected_tables = {'champion': baseline, 'candidate': expected['candidate_table']}
        for arm in ['champion', 'candidate']:
            for source, table in expected_tables[arm].items():
                for actual, want in zip(tables[arm][source], table):
                    assert actual['k'] == want['k'] and actual['n'] == want['n']
                    for measure in METRICS:
                        close(actual[measure], want[measure])
    else:
        assert Counter(r['source'] for r in rows) == {'maud': 64}
        for arm, table in expected['table'].items():
            for actual, want in zip(tables[arm]['equal_weight_ALL'], table):
                assert actual['k'] == want['k'] and actual['n'] == want['n']
                for measure in METRICS:
                    close(actual[measure], want[measure])
    return packet, tables, checks


def percentile(values, p):
    values = sorted(values)
    location = (len(values) - 1) * p
    lo = int(location)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (location - lo)


def bootstrap(packet, expected):
    rows = packet['rows']
    names = sorted({r['group'] for r in rows})
    stats = []
    for group in names:
        ix = [r for r in rows if r['group'] == group]
        stats.append({'group': group, 'n': len(ix), **{m: math.fsum(r['candidate_metrics']['8'][m] - r['champion_metrics']['8'][m] for r in ix) for m in ['recall', 'precision']}})
    data = read(HERE / 'data' / (packet['study'] + '-bootstrap.json'))
    indices = data['indices']
    assert data['seed'] == 20261022 and len(indices) == 2000
    metric_order = ['recall', 'precision'] if packet['study'] == 'development' else ['precision', 'recall']
    draws = []
    for ix in indices:
        assert len(ix) == len(names) and all(type(j) is int and 0 <= j < len(names) for j in ix)
        sample = [stats[j] for j in ix]
        denominator = sum(s['n'] for s in sample)
        draws.append([sum(s[measure] for s in sample) / denominator for measure in metric_order])
    if packet['study'] == 'development':
        rng = random.Random(20261022)
        assert indices == [[rng.randrange(len(names)) for _ in names] for _ in range(2000)]
        diagnostic = expected['paired_document_diagnostics']
        assert len(names) == diagnostic['groups'] == 72
        for actual, want in zip(stats, diagnostic['group_statistics']):
            assert actual['group'] == want['group_sha256'] and actual['n'] == want['n']
            for measure in ['recall', 'precision']:
                close(actual[measure], want[measure + '_gain_sum'])
        expected_ci = diagnostic['CI95']
        expected_digest = diagnostic['draw_distribution_sha256']
    else:
        assert len(names) == 8
        for actual, want in zip(stats, expected['group_statistics']):
            assert actual['group'] == want['group'] and actual['n'] == want['n']
            for measure in ['recall', 'precision']:
                close(actual[measure], want[measure])
        expected_ci = expected['CI95']
        expected_digest = expected['draw_distribution_sha256']
    assert digest(draws) == expected_digest
    ci = {measure: [percentile([d[i] for d in draws], p) for p in [.025, .975]] for i, measure in enumerate(metric_order)}
    for measure, bounds in ci.items():
        for actual, want in zip(bounds, expected_ci[measure]):
            close(actual, want)
        assert bounds[0] < 0 < bounds[1]
    return {'groups': len(names), 'draws': len(indices), 'CI95': ci,
            'both_intervals_include_zero': True, 'scope': 'post-selection observed/historical diagnostics, not unused confirmation',
            'draw_distribution_sha256': digest(draws)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    verified = verify_manifest()
    expected = read(HERE / 'expected.json')
    studies = {}
    checks = 0
    for name in ['development', 'historical64']:
        packet, table, count = replay_study(name, expected[name])
        checks += count
        studies[name] = {'n': len(packet['rows']), 'tables': table, 'bootstrap': bootstrap(packet, expected[name])}
    assert checks == 35280
    result = {'schema_version': 1, 'status': 'passed', 'manifest_files_rehashed': verified,
              'fixed_Fraction_rank_reconstructions': 1680, 'author_metric_scalar_checks': checks,
              'all_cutoffs': KS, 'studies': studies, 'search_policies_recorded': 37,
              'search_scope': 'These37 are the latest cached-ranking continuation; earlier embedding/reranker/native experiments also occurred.',
              'execution': 'Saved-output ranks, geometry, metrics and original bootstrap-draw replay only',
              'new_model_native_API_HTTP_or_paid_calls': 0, 'native_or_model_execution_reproduced': False,
              'hosted_embedding_weight_revision_verified': False, 'new96_quality_result': None,
              'confirmed_champion_changed': False, 'official_rank': None, 'full162task_LegalBench_result': False}
    if args.out:
        args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': 'passed', 'files': verified, 'ranks': 1680, 'scalar_checks': checks,
                      'development_recall_at8': studies['development']['tables']['candidate']['equal_weight_ALL'][3]['recall'],
                      'historical_recall_at8': studies['historical64']['tables']['candidate']['equal_weight_ALL'][3]['recall']}))


if __name__ == '__main__':
    main()
