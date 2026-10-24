"""Independent epoch27 DEV diagnostics, standard library only.

Original choices are joined only after exact sealed24-case outputs and cleanup.
Never imports candidate, model, tokenizer, native library, or training code.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

DEV_IDS = [609, 380, 592, 454, 559, 515, 349, 223]
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
ARMS = ['actual_native', 'lexical', 'positional']
CLASSES = ['entailment', 'contradiction', 'not_mentioned']
NATIVE_ORDER = ['contradiction', 'not_mentioned', 'entailment']
SOURCE_MAP = {'Entailment': 'entailment', 'Contradiction': 'contradiction',
              'NotMentioned': 'not_mentioned'}
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
EPS = 1e-6
LOG_FLOOR = 1e-12


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, 'Duplicate JSON object key')
        out[key] = value
    return out


def identity(path):
    p = Path(path)
    raw = p.read_bytes()
    return {'path': str(p), 'bytes': len(raw), 'sha256': digest(raw)}


def read(path, expected_sha=None):
    p = Path(path)
    require(p.is_absolute() and p == p.resolve(), 'Absolute nonsymlink path required')
    raw = p.read_bytes()
    require(expected_sha is None or digest(raw) == expected_sha, 'File SHA mismatch')
    return json.loads(raw, object_pairs_hook=unique_object)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def quantile(values, q):
    if not values:
        return None
    a = sorted(values)
    rank = (len(a)-1)*q
    low, high = math.floor(rank), math.ceil(rank)
    return a[low] + (rank-low)*(a[high]-a[low])


def reader_check(arm):
    require(type(arm) is dict and type(arm.get('reader')) is dict, 'Missing reader result')
    reader = arm['reader']
    logits, p = reader['raw_logits'], reader['probabilities']
    require(type(logits) is list and len(logits) == 3 and all(finite(x) for x in logits),
            'Native [C,N,E] logits must be finite3-vector')
    require(type(p) is dict and set(p) == set(CLASSES), 'Exact three class probability keys required')
    require(all(finite(v) and 0 <= v <= 1 for v in p.values()), 'Probability must be finite in[0,1]')
    require(abs(math.fsum(p.values())-1) <= EPS, 'Probability mass outside tolerance')
    maximum = max(logits)
    exp = [math.exp(x-maximum) for x in logits]
    mass = math.fsum(exp)
    replay = {label: exp[j]/mass for j, label in enumerate(NATIVE_ORDER)}
    require(all(abs(p[k]-replay[k]) <= EPS for k in CLASSES), 'Unit-temperature softmax replay failed')
    prediction = NATIVE_ORDER[max(range(3), key=lambda j: logits[j])]
    require(reader['prediction'] == arm['decision'] == prediction, 'Native argmax/direct decision mismatch')
    tokens = arm['joint_pair_tokens']
    require(type(tokens) is int and 0 < tokens <= 512, 'True pair exceeds fixed512-token limit')
    # Floats from the same model can differ by ≤EPS from Python float replay.
    # Evaluate the frozen reported probability vector without renormalization.
    return p, prediction


def metrics(rows, arm):
    scores = []
    per_class = {label: {'n': 0, 'correct': 0} for label in CLASSES}
    confusion = {label: {pred: 0 for pred in CLASSES} for label in CLASSES}
    for row in rows:
        gold = row['gold']
        p, pred = row['arms'][arm]['probabilities'], row['arms'][arm]['prediction']
        correct = int(pred == gold)
        brier = math.fsum((p[k] - int(k == gold))**2 for k in CLASSES)
        clipped_nll = -math.log(max(p[gold], LOG_FLOOR))
        per_class[gold]['n'] += 1
        per_class[gold]['correct'] += correct
        confusion[gold][pred] += 1
        scores.append({'id': row['id'], 'document_id': row['document_id'], 'gold': gold,
            'prediction': pred, 'correct': bool(correct), 'Brier': brier,
            'NLL_clipped_1e-12': clipped_nll, 'gold_probability_clipped': p[gold] < LOG_FLOOR,
            'probabilities': p})
    n = len(scores)
    for item in per_class.values():
        item['accuracy'] = item['correct']/item['n'] if item['n'] else None
    document_scores = []
    for did in DEV_IDS:
        subset = [s for s in scores if s['document_id'] == did]
        document_scores.append({'document_id': did, 'n': len(subset),
            'accuracy': sum(s['correct'] for s in subset)/len(subset),
            'Brier': math.fsum(s['Brier'] for s in subset)/len(subset),
            'NLL_clipped_1e-12': math.fsum(s['NLL_clipped_1e-12'] for s in subset)/len(subset)})
    return {'n': n, 'correct': sum(s['correct'] for s in scores),
        'accuracy': sum(s['correct'] for s in scores)/n,
        'by_class': per_class, 'confusion_matrix': confusion,
        'Brier': math.fsum(s['Brier'] for s in scores)/n,
        'NLL_clipped_1e-12': math.fsum(s['NLL_clipped_1e-12'] for s in scores)/n,
        'NLL_clipped_case_count': sum(s['gold_probability_clipped'] for s in scores),
        'unclipped_NLL_finite': all(s['probabilities'][s['gold']] > 0 for s in scores),
        'per_document': document_scores, 'cases': scores}


def verify_seal(seal, raw_path, execution_path, inputs_path, source_freeze_path, freeze_sha):
    require(seal['epoch'] == 27 and seal['phase'] == 'dev', 'Wrong seal epoch/phase')
    for key, path in [('raw', raw_path), ('execution', execution_path), ('inputs', inputs_path)]:
        actual = identity(path)
        require(seal[key] == actual, 'Post-output sealed identity mismatch: ' + key)
    require(seal['owned_group_closed'] is True and seal['all24cases_complete'] is True,
            'No labels before complete sealed outputs and owned-group closure')
    require(seal['annotation_choices_accessed_before_seal'] == 0, 'Labels used before outputs sealed')
    require(seal['source_freeze_sha256'] == freeze_sha, 'Seal/sourcefreeze mismatch')
    freeze = read(source_freeze_path, freeze_sha)
    require(freeze['epoch'] == 27, 'Wrong source freeze')
    own = identity(Path(__file__).resolve())
    require(any(r == own for r in freeze['files']), 'Independent scorer must be frozen before source input')
    for row in freeze['files']:
        require(identity(row['path']) == row, 'Frozen source changed before gold projection')


def score(raw_path, execution_path, inputs_path, source_path, seal_path,
          source_freeze_path, freeze_sha):
    seal = read(seal_path)
    verify_seal(seal, raw_path, execution_path, inputs_path, source_freeze_path, freeze_sha)
    execution = read(execution_path)
    require(execution['status'] == 'WORKER_COMPLETED' and execution['exit_code'] == 0,
            'Worker not completed; preserve partial/error diagnostics without opening gold')
    require(execution['owned_live_processes_closed'] is True
            and execution['owned_live_group_members'] == [], 'Owned group not closed')
    raw, inputs = read(raw_path), read(inputs_path)
    require(raw['epoch'] == 27 and raw['phase'] == 'dev', 'Wrong raw epoch/phase')
    expected = [(f'original-contractnli:train:epoch27:dev:{did}:{hid}', did, hid)
                for did in DEV_IDS for hid in HYPOTHESES]
    cases, bank = raw['cases'], inputs['records']
    require(len(cases) == len(bank) == 24, 'All24 cases required before label join')
    triples = lambda rows: [(r['id'], r['document_id'], r['hypothesis_id']) for r in rows]
    require(triples(cases) == triples(bank) == expected, 'Fixed ordered case identity mismatch')
    for case, inp in zip(cases, bank):
        payload = {'document': inp['document'], 'hypothesis': inp['hypothesis']}
        sha = digest(canonical(payload).encode('utf-8'))
        require(case['input_sha256'] == inp['input_sha256'] == sha, 'Case/input identity mismatch')
        require(set(case['arms']) == set(ARMS), 'Matched3arms required')
        for arm in ARMS:
            reader_check(case['arms'][arm])
    for case in cases:
        for arm in ARMS:
            latency = case['arms'][arm]['reader'].get('latency_seconds')
            require(finite(latency) and latency >= 0, 'Invalid reader latency before gold')
    require(not raw.get('errors', []), 'Raw errors prevent complete pre-gold qualification')
    # FIRST source annotation choice access, after every pre-label gate above.
    source = read(source_path, SOURCE_SHA)
    docs = {d['id']: d for d in source['documents']}
    rows = []
    for case, inp in zip(cases, bank):
        doc = docs[case['document_id']]
        require(doc['text'] == inp['document'], 'Original document authenticity mismatch')
        hid = case['hypothesis_id']
        require(source['labels'][hid]['hypothesis'] == inp['hypothesis'], 'Original hypothesis authenticity mismatch')
        require(len(doc['annotation_sets']) == 1, 'Unique original annotation set required')
        original = doc['annotation_sets'][0]['annotations'][hid]['choice']
        require(type(original) is str and original in SOURCE_MAP, 'Unknown original threeway source choice')
        arms = {}
        for arm in ARMS:
            p, pred = reader_check(case['arms'][arm])
            arms[arm] = {'probabilities': p, 'prediction': pred}
        rows.append({'id': case['id'], 'document_id': case['document_id'],
                     'gold': SOURCE_MAP[original], 'arms': arms})
    result = {arm: metrics(rows, arm) for arm in ARMS}
    paired = {}
    for arm in ['lexical', 'positional']:
        a, b = result['actual_native'], result[arm]
        paired[arm] = {'native_minus_control_accuracy': a['accuracy']-b['accuracy'],
            'control_minus_native_Brier': b['Brier']-a['Brier'],
            'control_minus_native_NLL_clipped_1e-12': b['NLL_clipped_1e-12']-a['NLL_clipped_1e-12']}
    native = result['actual_native']
    gates = {'every_gold_class_present': all(native['by_class'][k]['n'] > 0 for k in CLASSES),
        'native_at_least_one_correct_per_class': all(native['by_class'][k]['correct'] > 0 for k in CLASSES),
        'raw_errors_empty': not raw.get('errors', [])}
    for arm in ['lexical', 'positional']:
        gates[arm+':native_at_least2more_correct'] = native['correct'] >= result[arm]['correct']+2
        gates[arm+':Brier_nonincrease'] = native['Brier'] <= result[arm]['Brier']+1e-12
        gates[arm+':NLL_nonincrease'] = native['NLL_clipped_1e-12'] <= result[arm]['NLL_clipped_1e-12']+1e-12
    latency = {}
    for arm in ARMS:
        observations = [case['arms'][arm]['reader'].get('latency_seconds') for case in cases]
        require(all(finite(x) and x >= 0 for x in observations), 'Missing/invalid reader latency')
        latency[arm] = {'n': len(observations), 'p50_seconds': quantile(observations, .5),
            'p95_seconds': quantile(observations, .95),
            'scope': 'Reader forward wall seconds only; context/retrieval/model initialization reported separately by raw worker and execution'}
    return {'schema_version': 1, 'epoch': 27, 'status': 'PROJECT_DEV_DIAGNOSTIC_ONLY',
        'benchmark_accepted': False, 'champion_promoted': False, 'official_SOTA_established': False,
        'confirmation': [], 'foundation_text_and_fuzzy_overlap_unknown': True,
        'reader_supervised_CNLI_exclusion': 'Determined by separate frozen exact-reader admission',
        'annotation_choices_accessed': 24, 'other_role_annotation_choices_accessed': 0,
        'metrics': result, 'paired_descriptive_differences': paired,
        'predeclared_descriptive_diagnostic_checks': gates,
        'descriptive_diagnostic_checks_pass': all(gates.values()),
        'runtime_qualification': 'Independent runtime/source/execution audit still required; CONF remains HOLD absent an exact full champion comparator and fresh accepted protocol; DEV cannot promote native104.',
        'reader_latency': latency,
        'raw_errors': raw.get('errors', []), 'execution': execution,
        'evidence': {k: identity(p) for k, p in [('raw',raw_path),('inputs',inputs_path),
            ('execution',execution_path),('seal',seal_path),('source_freeze',source_freeze_path)]},
        'metrics_definition': {'Brier': 'Mean sum of three squared class errors; range0..2',
            'NLL_clipped_1e-12': 'Mean -ln(max(p_gold,1e-12)); clipcount disclosed; reported probabilities never renormalized',
            'probability_mass_and_softmax_tolerance': EPS, 'class_order': CLASSES,
            'native_logit_order_and_tie_rule': NATIVE_ORDER,
            'sampling_unit': '8documents ×3fixed hypotheses;24 correlated cases, no IID24-case CI'},
        'scope': 'Original licensed ContractNLI TRAIN subset used as project DEV only. Fixed project DEV cannot establish independent heldout improvement or promote native104. Exact reader supervised lineage is reviewed separately. Foundation-text and fuzzy overlap remain unknown. Retrieval context output is a classifier diagnostic, not proof that a legal proposition is absent from the full agreement. No fresh confirmation, generalization, superiority, promotion, submission or official rank claim.'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    for name in ['raw', 'execution', 'inputs', 'source', 'seal', 'source-freeze',
                 'source-freeze-sha256', 'output']:
        ap.add_argument('--'+name, required=True)
    a = ap.parse_args()
    result = score(a.raw, a.execution, a.inputs, a.source, a.seal,
                   a.source_freeze, a.source_freeze_sha256)
    with Path(a.output).open('x') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({'status': result['status'], 'annotation_choices_accessed': 24,
                      'benchmark_accepted': False, 'champion_promoted': False}))
