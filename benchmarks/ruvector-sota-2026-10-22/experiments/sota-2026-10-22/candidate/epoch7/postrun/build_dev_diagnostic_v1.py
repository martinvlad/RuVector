"""One saved-DEV diagnostic; no model/native imports, reruns or selection."""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import statistics

PREFIX = 'experiments/sota-2026-10-22/'
ARMS = {'ruvector_top2': None, 'same_nli_lexical_top2': 'lexical_top2',
        'same_nli_positional_first2': 'positional_first2'}


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def pin(root, relative, role):
    path = root / relative
    return {'role': role, 'path': relative, 'bytes': path.stat().st_size, 'sha256': sha(path)}


def mean(values):
    values = [value for value in values if value is not None]
    return statistics.mean(values) if values else None


def merge(ranges):
    result = []
    for start, end in sorted(ranges):
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def overlap(start, end, ranges):
    return sum(max(0, min(end, b) - max(start, a)) for a, b in ranges)


def run(project, source):
    study_dir = project / (PREFIX + 'epoch7')
    completion_path = study_dir / 'study-completion.json'
    completion = json.loads(completion_path.read_text())
    if (completion['status'] != 'REJECTED_DEV_GATE'
            or completion['confirmation_status'] != 'NOT_MODEL_CONSUMED'
            or completion['confirmation_consumed_or_attempted']
            or completion['started_phases'] != ['development']):
        raise ValueError('This diagnostic is fixed to the terminal DEV-only study')
    records_path = study_dir / 'runs/development/records.jsonl'
    records = [json.loads(line) for line in records_path.open()]
    groups = sorted({row['source_group'] for row in records})
    if len(records) != 24 or len(groups) != 8 or any(row['measured_phase'] != 'development' or row['provenance']['source_split'] != 'train' for row in records):
        raise ValueError('Expected24 saved DEV queries from8 original-train groups')
    original_path = source / (PREFIX + 'legal-transfer/epoch3/sources/original-train.json')
    wanted = {str(row['provenance']['document_id']) for row in records}
    original = json.loads(original_path.read_text())
    documents = {str(doc['id']): doc for doc in original['documents'] if str(doc['id']) in wanted}
    # Only the three saved DEV hypotheses are consulted; sibling annotations are
    # never aggregated or used as evidence here.
    cases = []
    for row in records:
        doc = documents[str(row['provenance']['document_id'])]
        state = row['input']['state']
        if state != doc['text']:
            raise ValueError('Original source and measured state differ')
        label = row['evaluation']['gold']
        hypothesis_id = row['provenance']['hypothesis_id']
        annotation = doc['annotation_sets'][0]['annotations'][hypothesis_id]
        if annotation['choice'] != row['evaluation']['original_threeway_label']:
            raise ValueError('Saved DEV and original annotation disagree')
        annotated = merge([tuple(doc['spans'][index]) for index in annotation['spans']])
        annotated_chars = sum(end - start for start, end in annotated)
        diagnostic = row['response']['diagnostics']['decision']
        case = {'id': row['id'], 'group': row['source_group'], 'hypothesis_id': hypothesis_id,
                'gold': label, 'original_threeway_label': annotation['choice'],
                'source_state_sha256': hashlib.sha256(state.encode()).hexdigest(),
                'annotated_spans': [list(span) for span in annotated],
                'annotated_characters': annotated_chars, 'arms': {}}
        if case['source_state_sha256'] != diagnostic['source_state_sha256']:
            raise ValueError('Saved diagnostic source hash mismatch')
        for arm, diag_name in ARMS.items():
            response = row['response'] if diag_name is None else row['response']['ablation_responses'][arm]
            probs = response['answers']['decision']['probabilities']
            prediction = max(probs, key=lambda key: (probs[key], key))
            arm_diag = diagnostic['arms']['ruvector_top2' if diag_name is None else diag_name]
            coverage = arm_diag['coverage']
            selected = merge([tuple(span) for span in coverage['selected_source_spans']])
            if arm_diag['premise'] != '\n\n'.join(state[a:b] for a, b in selected):
                raise ValueError('Saved premise is not exact selected source')
            overlaps = [overlap(a, b, selected) for a, b in annotated]
            retained = sum(overlaps)
            numbers = coverage['numeric_mentions']
            for mention in numbers:
                a, b = mention['span']
                if state[a:b] != mention['text'] or mention['retained'] != (overlap(a, b, selected) == b - a):
                    raise ValueError('Numeric retention trace does not match source')
            case['arms'][arm] = {'predicted': prediction, 'p_yes': probs['Yes'],
                                 'confidence': max(probs.values()), 'correct': prediction == label,
                                 'nll': -math.log(max(probs[label], 1e-15)),
                                 'brier': sum((probs[key] - float(key == label)) ** 2 for key in probs),
                                 'selected_source_spans': [list(span) for span in selected],
                                 'source_character_coverage': coverage['document_character_coverage'],
                                 'annotation_coverage': None if not annotated else {
                                     'any_character_overlap': any(value > 0 for value in overlaps),
                                     'all_annotated_spans_have_overlap': all(value > 0 for value in overlaps),
                                     'every_annotated_character_retained': retained == annotated_chars,
                                     'retained_characters': retained, 'total_characters': annotated_chars,
                                     'retained_fraction': retained / annotated_chars},
                                 'numeric_mentions': len(numbers),
                                 'numeric_mentions_retained': sum(item['retained'] for item in numbers),
                                 'numeric_retention_fraction': (sum(item['retained'] for item in numbers) / len(numbers)) if numbers else None}
        cases.append(case)
    summaries = {}
    for arm in ARMS:
        values = [case['arms'][arm] for case in cases]
        annotated = [value['annotation_coverage'] for value in values if value['annotation_coverage'] is not None]
        summaries[arm] = {'n': 24, 'correct': sum(value['correct'] for value in values),
                          'predicted': dict(collections.Counter(value['predicted'] for value in values)),
                          'false_yes': sum(value['predicted'] == 'Yes' and case['gold'] == 'No' for value, case in zip(values, cases)),
                          'false_no': sum(value['predicted'] == 'No' and case['gold'] == 'Yes' for value, case in zip(values, cases)),
                          'mean_confidence_correct': mean(value['confidence'] for value in values if value['correct']),
                          'mean_confidence_wrong': mean(value['confidence'] for value in values if not value['correct']),
                          'wrong_confidence_at_least_0_8': sum(not value['correct'] and value['confidence'] >= 0.8 for value in values),
                          'mean_nll': mean(value['nll'] for value in values), 'mean_brier': mean(value['brier'] for value in values),
                          'annotation_cases': len(annotated),
                          'any_annotation_overlap': sum(item['any_character_overlap'] for item in annotated),
                          'all_annotations_overlap': sum(item['all_annotated_spans_have_overlap'] for item in annotated),
                          'all_annotation_characters_retained': sum(item['every_annotated_character_retained'] for item in annotated),
                          'mean_annotation_character_fraction': mean(item['retained_fraction'] for item in annotated),
                          'mean_source_character_coverage': mean(value['source_character_coverage'] for value in values),
                          'numeric_mentions_retained': sum(value['numeric_mentions_retained'] for value in values),
                          'numeric_mentions_total': sum(value['numeric_mentions'] for value in values),
                          'mean_numeric_retention_correct': mean(value['numeric_retention_fraction'] for value in values if value['correct']),
                          'mean_numeric_retention_wrong': mean(value['numeric_retention_fraction'] for value in values if not value['correct'])}
    paired = {}
    for arm in list(ARMS)[1:]:
        paired[arm] = {key: [] for key in ('both_correct', 'primary_only_correct', 'other_only_correct', 'both_wrong', 'different_decisions')}
        for case in cases:
            primary = case['arms']['ruvector_top2']; other = case['arms'][arm]
            key = ('both_correct' if primary['correct'] and other['correct'] else 'primary_only_correct' if primary['correct']
                   else 'other_only_correct' if other['correct'] else 'both_wrong')
            paired[arm][key].append(case['id'])
            if primary['predicted'] != other['predicted']:
                paired[arm]['different_decisions'].append(case['id'])
    group_metrics = [{'group': group, 'n': sum(case['group'] == group for case in cases),
                      'correct': {arm: sum(case['arms'][arm]['correct'] for case in cases if case['group'] == group) for arm in ARMS}}
                     for group in groups]
    gold = dict(collections.Counter(case['gold'] for case in cases))
    inputs = [pin(project, PREFIX + 'epoch7/' + name, role) for name, role in (
        ('study-completion.json', 'terminal status and saved aggregate results'),
        ('runs/development/records.jsonl', 'all saved DEV responses and24 labels'),
        ('runs/development/development-comparison.json', 'frozen DEV comparison'),
        ('plan.json', 'accepted plan'))]
    inputs += [pin(source, PREFIX + name, role) for name, role in (
        ('legal-transfer/epoch3/sources/original-train.json', 'original source annotations; filtered to8DEV groups/3hypotheses'),
        ('candidate/epoch7/proposal-manifest.json', 'frozen candidate source identity'),
        ('candidate/epoch7/runtime.py', 'reader runtime'), ('candidate/epoch7/models.py', 'binary decoder'),
        ('candidate/epoch7/config.json', 'fixed config'), ('candidate/epoch7/model-assets.lock.json', 'immutable selected model hashes'),
        ('candidate/epoch6/context.py', 'unchanged source partition/packer'))]
    return {'schema_version': 1, 'scope': 'One posthoc saved-DEV-only descriptive diagnostic; no reruns, tuning, candidate selection or causal cross-epoch model comparison',
            'status': completion['status'], 'confirmation_status': completion['confirmation_status'],
            'n': 24, 'independent_source_groups': 8, 'queries_per_group': 3,
            'numeric_retention_scope': 'Mentions counted per query; the same source document appears in3 queries. Totals are descriptive exposure counts, not independent numeric facts or evidence of sufficiency.',
            'group_dependence': '24 correlated queries from8 document groups; no24-independent-observation significance claim',
            'gold': gold, 'original_threeway_labels': dict(collections.Counter(case['original_threeway_label'] for case in cases)),
            'same_new_model_arm_summary': summaries, 'paired_same_model_case_partitions': paired,
            'group_metrics': group_metrics, 'cases': cases, 'source_and_result_pins': inputs,
            'findings': ['Native-selected reader predictsYes23/24 against goldYes7/24; all17 gold-No cases are false positives. Lexical and positional controls share a strong positive bias.',
                         'Matched same-new-model retrieval-arm disagreements are listed by saved case ID; they do not identify a causal model gain across epochs.',
                         'Annotation overlap and numeric retention are mechanical exposure measurements. Coverage is not sufficiency; NotMentioned cases have no annotated support and are excluded from annotation-coverage denominators.',
                         'Confidence errors and proper scores are descriptive DEV diagnostics, not official Capability, calibration against a gold distribution or proof of rank.'],
            'posthoc_majority_reference': {'scope': 'Posthoc DEV-only reference computed after observing gold; not a candidate, tuned threshold, selection rule or confirmation gate',
                                           'constant_label': 'No', 'correct': gold['No'], 'n': 24},
            'one_next_hypothesis': {'status': 'Unimplemented and unmeasured; no automatic execution or generic model grid',
                                    'hypothesis': 'A domain-specific three-way legal decision head that explicitly distinguishes entailment, contradiction and not-mentioned, with permission/prohibition/exception scope, will reduce broad positive bias under the same frozen RuVector context policy.',
                                    'training_separation': 'If later authorized, use only original official training documents after excluding all8 exposed DEV groups; exclude all official dev/test documents and original-dev confirmation96 f018 from fitting, calibration and selection.',
                                    'typed_readout': 'Yes=P(entailment);No=P(contradiction)+P(not-mentioned); no posthoc threshold fitted to these24 outcomes',
                                    'test_design': 'Freeze one legal/deontic hypothesis and unchanged matched retrieval arms before any future unused confirmation, with document-group uncertainty.'},
            'exposure_note': 'A preliminary schema probe displayed sibling annotation labels for one already-consumed DEV training document. These siblings were excluded from every metric/hypothesis; all8groups remain permanent DEV. No unused confirmation source/labels were opened.',
            'new_model_calls': 0, 'new_native_calls': 0, 'new_paid_calls': 0,
            'frozen_candidate_modified': False, 'unused_confirmation_labels_inspected': False,
            'official_score': None, 'official_rank': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.project_root, args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({'output': str(args.output), 'sha256': sha(args.output), 'n': result['n'],
                      'groups': result['independent_source_groups'], 'summary': result['same_new_model_arm_summary'],
                      'model_native_calls': 0}))


if __name__ == '__main__':
    main()
