"""Saved-output-only terminal diagnostic; never loads/runs a model or fitter."""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import statistics

PREFIX = 'experiments/sota-2026-10-22/'
CLASSES = ('Entailment', 'Contradiction', 'NotMentioned')
SELECTORS = ('ruvector_top2', 'lexical_top2', 'positional_first2')
READOUTS = ('trained_head', 'fixed_raw_threeway', 'historical_discarded_neutral')


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def rows(path):
    return [json.loads(line) for line in path.open() if line.strip()]


def mean(values):
    values = [value for value in values if value is not None]
    return statistics.mean(values) if values else None


def decision(probs):
    return min(probs, key=lambda label: (-probs[label], label))


def score(probs, gold):
    if not all(math.isfinite(value) and value >= 0 for value in probs.values()) or abs(sum(probs.values()) - 1) > 1e-9:
        raise ValueError('Saved probabilities are invalid')
    predicted = decision(probs)
    return {'predicted': predicted, 'correct': predicted == gold, 'confidence': max(probs.values()),
            'brier': sum((value - float(label == gold)) ** 2 for label, value in probs.items()),
            'nll': -math.log(max(probs[gold], 1e-15))}


def summarize(observations):
    observations = list(observations)
    if not observations:
        return None
    return {'n': len(observations), 'correct': sum(row['correct'] for row in observations),
            'accuracy': mean(row['correct'] for row in observations),
            'predicted_counts': dict(collections.Counter(row['predicted'] for row in observations)),
            'mean_brier': mean(row['brier'] for row in observations), 'mean_nll': mean(row['nll'] for row in observations),
            'mean_confidence_correct': mean(row['confidence'] for row in observations if row['correct']),
            'mean_confidence_wrong': mean(row['confidence'] for row in observations if not row['correct']),
            'wrong_confidence_at_least_0_8': sum(not row['correct'] and row['confidence'] >= 0.8 for row in observations)}


def group_summaries(cases):
    """Descriptive units are document groups; no independent-query interval."""
    grouped = collections.defaultdict(list)
    for case in cases:
        grouped[case['group']].append(case)
    return {group: {'n': len(group_cases), 'gold_binary_counts': dict(collections.Counter(case['gold_binary'] for case in group_cases)),
                    'readouts': summaries(group_cases)} for group, group_cases in sorted(grouped.items())}


def paired_selector_summary(cases):
    output = {}
    for other in SELECTORS[1:]:
        both_right, primary_only, other_only, both_wrong = [], [], [], []
        for case in cases:
            p = case['selectors'][SELECTORS[0]].get('trained_head')
            q = case['selectors'][other].get('trained_head')
            if p is None or q is None:
                continue
            target = (both_right if p['binary']['correct'] and q['binary']['correct'] else
                      primary_only if p['binary']['correct'] else other_only if q['binary']['correct'] else both_wrong)
            target.append(case['id'])
        output[other] = {'both_right': both_right, 'primary_only_right': primary_only,
                         'other_only_right': other_only, 'both_wrong': both_wrong,
                         'scope': 'Descriptive matched cases only; queries within each document group are correlated.'}
    return output


def confusion_tables(cases):
    output = {}
    for selector in SELECTORS:
        output[selector] = {}
        for readout in READOUTS:
            tables = {}
            for domain, gold_key in (('binary', 'gold_binary'), ('threeway', 'gold_threeway')):
                observed = collections.Counter((case[gold_key], case['selectors'][selector][readout][domain]['predicted'])
                                               for case in cases if readout in case['selectors'][selector]
                                               and case['selectors'][selector][readout][domain] is not None)
                tables[domain] = [{'gold': gold, 'predicted': prediction, 'n': count}
                                  for (gold, prediction), count in sorted(observed.items())]
            output[selector][readout] = tables
    return output


def binary(threeway):
    return {'Yes': threeway['Entailment'], 'No': threeway['Contradiction'] + threeway['NotMentioned']}


def cases_for(records, cached_replay=None):
    replay = {(row['id'], row['arm']): row for row in (cached_replay or [])}
    output = []
    for row in records:
        label = row['evaluation']['original_threeway_label']
        gold = row['evaluation']['gold']
        if gold != ('Yes' if label == 'Entailment' else 'No'):
            raise ValueError('Saved binary and typed labels disagree')
        case = {'id': row['id'], 'group': row['source_group'], 'gold_binary': gold,
                'gold_threeway': label, 'hypothesis_id': row['provenance']['hypothesis_id'], 'selectors': {}}
        for selector in SELECTORS:
            trace = row['response']['diagnostics']['decision']['arms'][selector]['decoding']
            raw = trace['raw_threeway_probabilities']
            trained = (replay[(row['id'], selector)]['threeway_probabilities'] if cached_replay is not None
                       else trace['typed_threeway_probabilities'] if trace['typed_head_state'] == 'FROZEN' else None)
            e, c, n = trace['typed_head_canonical_logits']
            scale = max(e, c)
            p_yes = math.exp(e - scale) / (math.exp(e - scale) + math.exp(c - scale))
            views = {'fixed_raw_threeway': raw, 'trained_head': trained}
            scores = {}
            for readout, distribution in views.items():
                if distribution is None:
                    continue
                if set(distribution) != set(CLASSES):
                    raise ValueError('Three-way probability support changed')
                scores[readout] = {'binary': score(binary(distribution), gold),
                                   'threeway': score(distribution, label), 'probabilities': distribution}
            scores['historical_discarded_neutral'] = {
                'binary': score({'Yes': p_yes, 'No': 1 - p_yes}, gold), 'threeway': None,
                'scope': 'Predeclared offline same-logit historical reference; not measured candidate, fit/threshold choice or gate. Neutral intentionally absent only in this descriptive reference.'}
            case['selectors'][selector] = scores
        output.append(case)
    return output


def summaries(cases):
    result = {}
    for selector in SELECTORS:
        result[selector] = {}
        for readout in READOUTS:
            views = [case['selectors'][selector][readout] for case in cases if readout in case['selectors'][selector]]
            result[selector][readout] = {'binary': summarize(view['binary'] for view in views),
                                        'threeway': summarize(view['threeway'] for view in views if view['threeway'] is not None)} if views else None
    return result


def failures(value):
    if isinstance(value, dict):
        if 'fit_failure' in value:
            return value['fit_failure']
        for child in value.values():
            found = failures(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = failures(child)
            if found is not None:
                return found
    return None


def merge(spans):
    output = []
    for a, b in sorted(spans):
        if output and a <= output[-1][1]:
            output[-1] = (output[-1][0], max(output[-1][1], b))
        else:
            output.append((a, b))
    return output


def coverage(records, source_root):
    # Called only when all24 DEV records have actually been model-consumed.
    original_path = source_root / (PREFIX + 'legal-transfer/epoch3/sources/original-train.json')
    if not original_path.is_file():
        return {'available': False, 'reason': 'Original annotation source not restored; no other labels opened'}, None
    wanted = {str(row['provenance']['document_id']) for row in records}
    data = json.loads(original_path.read_text())
    docs = {str(doc['id']): doc for doc in data['documents'] if str(doc['id']) in wanted}
    result = []
    for row in records:
        doc = docs[str(row['provenance']['document_id'])]
        state = row['input']['state']
        if state != doc['text']:
            raise ValueError('Saved source and original annotation offsets differ')
        annotation = doc['annotation_sets'][0]['annotations'][row['provenance']['hypothesis_id']]
        if annotation['choice'] != row['evaluation']['original_threeway_label']:
            raise ValueError('Saved DEV and original annotation label differ')
        annotated = merge([tuple(doc['spans'][index]) for index in annotation['spans']])
        amount = sum(b - a for a, b in annotated)
        selectors = {}
        for selector in SELECTORS:
            observed = row['response']['diagnostics']['decision']['arms'][selector]['coverage']
            selected = merge([tuple(span) for span in observed['selected_source_spans']])
            overlap = [sum(max(0, min(b, y) - max(a, x)) for x, y in selected) for a, b in annotated]
            numbers = observed['numeric_mentions']
            for mention in numbers:
                a, b = mention['span']
                if state[a:b] != mention['text'] or mention['retained'] != any(x <= a and b <= y for x, y in selected):
                    raise ValueError('Numeric retention differs from exact saved source')
            selectors[selector] = {'annotation_available': bool(annotated),
                                    'any_annotation_overlap': any(value > 0 for value in overlap) if annotated else None,
                                    'all_annotation_characters_retained': sum(overlap) == amount if amount else None,
                                    'annotation_character_fraction': sum(overlap) / amount if amount else None,
                                    'numeric_total': len(numbers), 'numeric_retained': sum(item['retained'] for item in numbers),
                                    'source_character_coverage': observed['document_character_coverage']}
        result.append({'id': row['id'], 'group': row['source_group'], 'selectors': selectors})
    aggregate = {}
    for selector in SELECTORS:
        values = [row['selectors'][selector] for row in result]
        annotated = [row for row in values if row['annotation_available']]
        aggregate[selector] = {'annotated_cases': len(annotated),
                                'any_annotation_overlap': sum(row['any_annotation_overlap'] for row in annotated),
                                'all_annotation_characters_retained': sum(row['all_annotation_characters_retained'] for row in annotated),
                                'mean_annotation_fraction': mean(row['annotation_character_fraction'] for row in annotated),
                                'numeric_total': sum(row['numeric_total'] for row in values),
                                'numeric_retained': sum(row['numeric_retained'] for row in values),
                                'mean_source_character_coverage': mean(row['source_character_coverage'] for row in values)}
    return {'available': True, 'aggregate': aggregate, 'cases': result,
            'scope': 'Mechanical exposure only: coverage is not sufficiency. NotMentioned has no support annotations. Numeric occurrences are counted per query, repeating each document3times; no independent-fact count.'}, original_path


def build(project_root, source_root):
    study = project_root / (PREFIX + 'epoch8')
    completion_path = study / 'study-completion.json'
    completion = json.loads(completion_path.read_text())
    if not completion.get('finished_at') or completion.get('allowed_further_attempts_in_closed_study') != 0:
        raise ValueError('A terminal closed study is required')
    folder = study / 'runs/development'
    saved = rows(folder / 'records.jsonl') if (folder / 'records.jsonl').exists() else []
    train = [row for row in saved if row['measured_phase'] == 'train']
    dev = [row for row in saved if row['measured_phase'] == 'development']
    report = json.loads((folder / 'report.json').read_text()) if (folder / 'report.json').exists() else {}
    final_engine = json.loads((folder / 'final-engine.json').read_text()) if (folder / 'final-engine.json').exists() else {}
    fit_failure = failures(final_engine)
    fitted = json.loads((study / 'fitted-head.json').read_text()) if (study / 'fitted-head.json').exists() else None
    artifact_accepted = fitted is not None and (study / 'readout-fit-lock.json').is_file()
    full_dev = len(dev) == 24 and artifact_accepted
    cached_replay = fitted['cached_training_replay'] if artifact_accepted else None
    train_cases = cases_for(train, cached_replay) if train else []
    dev_cases = cases_for(dev) if full_dev else []
    cover, original = coverage(dev, source_root) if full_dev else ({'available': False, 'reason': 'No full24 fitted-head DEV results; original annotation corpus and unused DEV/CONF labels not opened'}, None)
    input_paths = [completion_path, study / 'plan.json', folder / 'report.json', folder / 'final-engine.json',
                   folder / 'records.jsonl', folder / 'training-cache.jsonl', study / 'fitted-head.json', study / 'readout-fit-lock.json']
    if full_dev:
        input_paths.append(folder / 'development-comparison.json')
    if original is not None:
        input_paths.append(original)
    input_paths += [source_root / (PREFIX + 'candidate/epoch8/' + name) for name in ('proposal-manifest.json', 'runtime.py', 'head.py', 'models.py', 'features.py', 'config.json')]
    input_paths.append(source_root / (PREFIX + 'audit/epoch8/offline-reference-analysis-contract-v2.json'))
    pins = [{'path': str(path.relative_to(project_root)) if path.is_relative_to(project_root) else str(path.relative_to(source_root)),
             'bytes': path.stat().st_size, 'sha256': sha(path)} for path in input_paths if path.is_file()]
    result = {'schema_version': 1, 'scope': 'One saved-output-only postrun diagnostic; no model/native calls, optimizer reruns, selection, source changes or extra queries',
              'study_status': completion['status'], 'confirmation_status': completion.get('confirmation_status'),
              'confirmation_consumed_or_attempted': completion.get('confirmation_consumed_or_attempted'),
              'unused_confirmation_labels_inspected': False, 'fit_artifact_accepted': artifact_accepted,
              'train_completed': len(train), 'train_document_groups': len({row['source_group'] for row in train}),
              'DEV_completed': len(dev), 'full_DEV_diagnostic_available': full_dev,
              'DEV_document_groups': len({row['source_group'] for row in dev}) if full_dev else None,
              'dependence_scope': 'TRAIN72 spans24 document groups; DEV24 spans8 other groups,3 correlated queries per group. In-sample TRAIN scores are not held-out accuracy; no24-independent-observation or cross-epoch causal model-gain claim.',
              'train_in_sample_summary': summaries(train_cases) if train_cases else None,
              'DEV_summary': summaries(dev_cases) if dev_cases else None,
              'train_in_sample_groups': group_summaries(train_cases) if train_cases else None,
              'DEV_groups': group_summaries(dev_cases) if dev_cases else None,
              'DEV_paired_selectors': paired_selector_summary(dev_cases) if dev_cases else None,
              'DEV_confusion': confusion_tables(dev_cases) if dev_cases else None,
              'train_cases': train_cases, 'DEV_cases': dev_cases,
              'fit_diagnostics': fitted.get('fit_diagnostics') if artifact_accepted else None,
              'fit_failure': fit_failure, 'worker_error': report.get('error'),
              'source_annotation_numeric_coverage': cover, 'source_and_result_pins': pins,
              'historical_reference_scope': 'Raw full-threeway and discarded-neutral readouts are predeclared offline same-logit references bound in the accepted plan. They are not accepted heads, tuned thresholds, candidate selection or confirmation gates; no rescue/promotion based on which wins. Main trained readout preserves all3classes.',
              'pilot_limits': ['Only this bounded project-level split, with24 train and8 DEV document groups; not an official leaderboard evaluation.',
                               'Training labels describe full agreements while each arm reads selected excerpts; coverage does not establish sufficiency.',
                               'Model pretraining/public-data contamination unknown; no causal gain claim comparing different historical epochs.',
                               'No unused DEV source/labels opened after fit failure and no unused confirmation labels opened.'],
              'new_model_calls': 0, 'new_native_calls': 0, 'new_optimizer_fits': 0,
              'frozen_sources_modified': False, 'official_score': None, 'official_rank': None}
    if full_dev:
        result['one_next_direction'] = {'status': 'Unimplemented/unmeasured; no automatic new run or tuning',
                                        'hypothesis': 'Use one predeclared evidence-sufficiency/deontic-scope training objective with document-group holdout, preserving all3classes and matched selectors; choose its source rule before any new held-out labels.',
                                        'separation': 'No fitting or threshold change on this consumed DEV or unused confirmation; preserve the frozen study and select no alternative from these outcomes.'}
    else:
        result['one_next_direction'] = {'status': 'Unimplemented/unmeasured; no retry or changed fitter in this closed study',
                                        'hypothesis': 'Diagnose the fixed fit boundary/objective/gradient from its saved cache and failure receipt, then predeclare a deterministic fail-closed convex optimization/source-interface repair in a future study before labels or model calls.',
                                        'separation': 'No held-out accuracy claimed and no unused DEV/confirmation inspection; no postfailure optimizer or acceptance-threshold selection.'}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.project_root, args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({'output': str(args.output), 'sha256': sha(args.output), 'status': result['study_status'],
                      'train_completed': result['train_completed'], 'DEV_completed': result['DEV_completed'],
                      'fit_artifact_accepted': result['fit_artifact_accepted'], 'model_native_optimizer_calls': 0}))


if __name__ == '__main__':
    main()
