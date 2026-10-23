"""Closed-study saved-output diagnostics; no model/native/fitter imports or calls."""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import statistics
import numpy as np

PREFIX = 'experiments/sota-2026-10-22/'
CLASSES = ('Entailment', 'Contradiction', 'NotMentioned')
SELECTORS = ('ruvector_top2', 'lexical_top2', 'positional_first2')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.open() if line.strip()] if path.is_file() else []


def mean(values):
    values = [value for value in values if value is not None]
    return statistics.mean(values) if values else None


def decision(probs):
    return min(probs, key=lambda label: (-probs[label], label))


def binary(typed):
    return {'Yes': typed['Entailment'], 'No': typed['Contradiction'] + typed['NotMentioned']}


def score(probs, gold):
    if not probs or not all(math.isfinite(p) and p >= 0 for p in probs.values()) or abs(sum(probs.values()) - 1) > 1e-9:
        raise ValueError('Saved probability distribution invalid')
    prediction = decision(probs)
    return {'predicted': prediction, 'correct': prediction == gold,
            'brier': sum((p - float(k == gold)) ** 2 for k, p in probs.items()),
            'nll': -math.log(max(probs[gold], 1e-15)), 'confidence': max(probs.values())}


def summarize(items):
    values = list(items)
    if not values:
        return None
    return {'n': len(values), 'correct': sum(x['correct'] for x in values), 'accuracy': mean(x['correct'] for x in values),
            'brier': mean(x['brier'] for x in values), 'nll': mean(x['nll'] for x in values),
            'predicted_counts': dict(collections.Counter(x['predicted'] for x in values)),
            'wrong_confidence_at_least_0_8': sum(not x['correct'] and x['confidence'] >= .8 for x in values)}


def probability_metrics(predicted, targets):
    p, y = list(predicted), list(targets)
    if len(p) != len(y) or not p:
        return None
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in p) or any(v not in (0, 1) for v in y):
        raise ValueError('Invalid saved auxiliary prediction/target')
    pos = [a for a, b in zip(p, y) if b == 1]; neg = [a for a, b in zip(p, y) if b == 0]
    auc = sum(float(a > b) + .5 * float(a == b) for a in pos for b in neg) / (len(pos) * len(neg)) if pos and neg else None
    return {'views': len(p), 'positive_annotation_overlap_targets': sum(y), 'mean_probability': mean(p),
            'mean_probability_positive': mean(pos), 'mean_probability_negative': mean(neg), 'auc_pairwise_tie_half': auc,
            'brier': mean((a - b) ** 2 for a, b in zip(p, y)),
            'nll': mean(-math.log(max(a if b else 1 - a, 1e-15)) for a, b in zip(p, y)),
            'scope': 'Annotation-overlap discrimination only; correlated selector/query/document views, not sufficiency or benchmark generalization.'}


def aux_probability(model, features):
    x = (np.asarray(features, dtype=np.float64) - np.asarray(model['mean'])) / np.asarray(model['scale'])
    value = float(x @ np.asarray(model['weights']))
    return math.exp(-float(np.logaddexp(0., -value)))


def auxiliary_diagnostic(artifact):
    examples = artifact['training_examples']; oof = artifact['oof_probabilities']
    if len(examples) != 216 or len(oof) != 216:
        raise ValueError('Expected exact216 saved TRAIN views')
    final = [aux_probability(artifact['auxiliary_final'], x['features']) for x in examples]
    result = {}
    for selector in (None,) + SELECTORS:
        indices = [i for i, x in enumerate(examples) if selector is None or x['arm'] == selector]
        delta = [final[i] - oof[i] for i in indices]
        result['all_views' if selector is None else selector] = {
            'OOF': probability_metrics([oof[i] for i in indices], [examples[i]['annotation_overlap_target'] for i in indices]),
            'final_allTRAIN_in_sample': probability_metrics([final[i] for i in indices], [examples[i]['annotation_overlap_target'] for i in indices]),
            'final_minus_OOF_mean': mean(delta), 'final_minus_OOF_mean_absolute': mean(abs(x) for x in delta),
            'final_minus_OOF_max_absolute': max(abs(x) for x in delta)}
    result['folds'] = [{'fold': model['fold'], 'training_groups': model['training_groups'], 'heldout_groups': model['heldout_groups'],
                        'training_examples': model['training_examples'], 'heldout_examples': model['heldout_examples'],
                        'fit_diagnostics': model['fit_diagnostics']} for model in artifact['auxiliary_folds']]
    result['allTRAIN_auxiliary_fit_diagnostics'] = artifact['auxiliary_final']['fit_diagnostics']
    result['scope'] = 'Saved weight dot products only; no refit. Decisionhead trained on OOF coverage; deployed auxiliary is finalallTRAIN. AllTRAIN discrimination is in-sample, not held-out. No alternative or calibration is selected.'
    return result


def cases_for(records, replay=None):
    cache = {(x['id'], x['arm']): x for x in replay or []}; output = []
    for row in records:
        if hashlib.sha256(canonical(row['input'])).hexdigest() != row['input_sha256']:
            raise ValueError('Saved input identity differs')
        label = row['evaluation']['original_threeway_label']; gold = row['evaluation']['gold']
        if label not in CLASSES or gold != ('Yes' if label == 'Entailment' else 'No'):
            raise ValueError('Saved labels inconsistent')
        case = {'id': row['id'], 'group': row['source_group'], 'gold_threeway': label, 'gold_binary': gold, 'selectors': {}}
        for selector in SELECTORS:
            observed = row['response']['diagnostics']['decision']['arms'][selector]; trace = observed['decoding']
            raw = trace['raw_threeway_probabilities']
            fitted = (cache[(row['id'], selector)]['threeway_probabilities'] if replay is not None
                      else trace['typed_threeway_probabilities'] if trace['typed_head_state'] == 'FROZEN' else None)
            feature = dict(zip(trace['typed_head_feature_names'], trace['typed_head_features']))
            values = {'generic_role_match_present': feature.get('role_match_fraction', 0) > 0,
                      'generic_role_mismatch_present': feature.get('role_mismatch_fraction', 0) > 0,
                      'generic_negation_before_action_present': feature.get('negation_before_action_fraction', 0) > 0,
                      'generic_condition_present': feature.get('condition_fraction', 0) > 0,
                      'generic_exception_present': feature.get('exception_fraction', 0) > 0,
                      'auxiliary_runtime_probability': trace.get('annotation_overlap_probability'), 'readouts': {}}
            for name, p in (('fixed_raw9_threeway', raw), ('trained_head', fitted)):
                if p is not None:
                    if set(p) != set(CLASSES): raise ValueError('Threeway support changed')
                    values['readouts'][name] = {'binary': score(binary(p), gold), 'threeway': score(p, label), 'probabilities': p}
            case['selectors'][selector] = values
        output.append(case)
    return output


def cases_summary(cases):
    out = {}
    for selector in SELECTORS:
        out[selector] = {}
        for readout in ('fixed_raw9_threeway', 'trained_head'):
            values = [(c, c['selectors'][selector]['readouts'][readout]) for c in cases if readout in c['selectors'][selector]['readouts']]
            if not values:
                out[selector][readout] = None; continue
            strata = {}
            for feature in ('generic_role_match_present', 'generic_role_mismatch_present', 'generic_negation_before_action_present', 'generic_condition_present', 'generic_exception_present'):
                strata[feature] = {str(present): summarize(v['binary'] for c, v in values if c['selectors'][selector][feature] == present) for present in (True, False)}
            out[selector][readout] = {'binary': summarize(v['binary'] for c, v in values), 'threeway': summarize(v['threeway'] for c, v in values),
                'threeway_confusion': [{'gold': a, 'predicted': b, 'n': n} for (a, b), n in sorted(collections.Counter((c['gold_threeway'], v['threeway']['predicted']) for c, v in values).items())],
                'generic_text_feature_strata': strata}
    return out


def merged(spans):
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]: out[-1] = (out[-1][0], max(out[-1][1], b))
        else: out.append((a, b))
    return out


def normalize_dev_projection(projection, records, records_sha256):
    """Accept the auditor's consumed-output-bound projection without original-corpus reads."""
    if projection.get('role') in ('development', 'dev'):
        return projection
    if (projection.get('only_consumed_DEV_hypotheses') is not True
            or projection.get('confirmation_records_or_labels_included') is not False
            or projection.get('saved_DEV_records_sha256') != records_sha256
            or projection.get('queries') != 24 or projection.get('document_groups') != 8):
        raise ValueError('Auditor DEV projection boundary/records binding invalid')
    by_id = {r['id']: r for r in records}; projected = projection['records']
    if len(projected) != 24 or len({r['id'] for r in projected}) != 24 or {r['id'] for r in projected} != set(by_id):
        raise ValueError('Auditor DEV projection identity set differs')
    normalized = []
    for annotation in projected:
        row = by_id[annotation['id']]
        if (annotation['source_group'] != row['source_group'] or annotation['hypothesis_id'] != row['provenance']['hypothesis_id']
                or annotation['gold_threeway'] != row['evaluation']['original_threeway_label']):
            raise ValueError('Auditor DEV projection source/hypothesis/label differs')
        normalized.append({'id': row['id'], 'source_group': row['source_group'], 'input_sha256': row['input_sha256'],
            'source_document_sha256': hashlib.sha256(row['input']['state'].encode()).hexdigest(),
            'original_threeway_label': annotation['gold_threeway'], 'evidence_spans': annotation['annotation_spans']})
    return {'role': 'development', 'queries': 24, 'document_groups': 8, 'records': normalized}


def retention(records, annotations):
    annotation_rows = None
    if annotations is not None:
        if annotations.get('role') not in ('development', 'dev') or annotations.get('queries') != len(records):
            raise ValueError('Only exact consumed DEV annotation projection allowed')
        annotation_rows = {x['id']: x for x in annotations['records']}
        if set(annotation_rows) != {x['id'] for x in records}: raise ValueError('DEV annotation identity set differs')
    observations = []
    for row in records:
        state = row['input']['state']; diag = row['response']['diagnostics']['decision']; annotation = annotation_rows[row['id']] if annotation_rows is not None else None
        if annotation is not None:
            if (annotation['input_sha256'] != row['input_sha256'] or annotation['source_group'] != row['source_group']
                    or annotation['source_document_sha256'] != hashlib.sha256(state.encode()).hexdigest()
                    or annotation['original_threeway_label'] != row['evaluation']['original_threeway_label']):
                raise ValueError('DEV annotation projection provenance differs')
            if any(len(pair) != 2 or any(type(v) is not int for v in pair) or not 0 <= pair[0] < pair[1] <= len(state) for pair in annotation['evidence_spans']):
                raise ValueError('DEV annotation offsets invalid')
            gold = merged(annotation['evidence_spans']); total = sum(b - a for a, b in gold)
        for selector in SELECTORS:
            observed = diag['arms'][selector]['coverage']; spans = merged(observed['selected_source_spans']); numbers = observed['numeric_mentions']
            for mention in numbers:
                a, b = mention['span']
                if state[a:b] != mention['text'] or mention['retained'] != any(c <= a and b <= d for c, d in spans):
                    raise ValueError('Saved numeric mention/source identity differs')
            item = {'id': row['id'], 'group': row['source_group'], 'selector': selector,
                    'numeric_total': len(numbers), 'numeric_retained': sum(n['retained'] for n in numbers),
                    'source_character_coverage': observed['document_character_coverage'], 'positive_annotation_spans_available': bool(total) if annotation is not None else None}
            if annotation is not None:
                overlap = sum(max(0, min(b, d) - max(a, c)) for a, b in gold for c, d in spans)
                item.update(any_annotation_overlap=bool(overlap) if total else None, full_annotation_retained=overlap == total if total else None,
                            annotation_character_fraction=overlap / total if total else None)
            observations.append(item)
    aggregate = {}
    for selector in SELECTORS:
        all_rows = [x for x in observations if x['selector'] == selector]; annotated = [x for x in all_rows if x['positive_annotation_spans_available']]
        aggregate[selector] = {'numeric_total': sum(x['numeric_total'] for x in all_rows), 'numeric_retained': sum(x['numeric_retained'] for x in all_rows),
            'mean_source_character_coverage': mean(x['source_character_coverage'] for x in all_rows),
            'positive_annotation_cases': len(annotated) if annotation_rows is not None else None,
            'any_annotation_overlap': sum(x['any_annotation_overlap'] for x in annotated) if annotation_rows is not None else None,
            'full_annotation_retained': sum(x['full_annotation_retained'] for x in annotated) if annotation_rows is not None else None,
            'mean_annotation_character_fraction': mean(x['annotation_character_fraction'] for x in annotated)}
    return {'aggregate': aggregate, 'cases': observations, 'DEV_annotation_projection_available': annotation_rows is not None,
            'scope': 'Mechanical retained characters/numbers, not evidence sufficiency. Missing annotation/overlap never proves absence. Document numeric occurrences repeat across its three queries.'}


def ann_diagnostic(records, folder):
    output = []
    for row in records:
        retrieval = row['response']['diagnostics']['decision']['retrieval']; evidence = retrieval['bundle_evidence']; path = folder / 'bundles' / evidence['relativefilename']
        if not path.is_file() or path.stat().st_size != evidence['bytes'] or sha(path) != evidence['sha256']:
            raise ValueError('Exact saved native bundle missing or changed')
        bundle = json.loads(path.read_text()); vectors = np.asarray(bundle['vectors'], dtype=np.float64); query = np.asarray(bundle['query_vectors'][0], dtype=np.float64)
        distances = 1 - (vectors @ query) / (np.linalg.norm(vectors, axis=1) * np.linalg.norm(query))
        if not np.isfinite(distances).all(): raise ValueError('Invalid cached cosine input')
        native = retrieval['native']['queries'][0]['ids']; k = len(native); exact = sorted(range(len(vectors)), key=lambda i: (float(distances[i]), i))[:k]
        output.append({'id': row['id'], 'bundle_sha256': evidence['sha256'], 'vectors': len(vectors), 'k': k,
                       'topk_set_overlap_fraction': len(set(native) & set(exact)) / k,
                       'rank_position_differences': sum(a != b for a, b in zip(native, exact)),
                       'native_top1_exact_top1': native[0] == exact[0],
                       'top1_cosine_distance_regret': float(distances[native[0]] - distances[exact[0]]),
                       'native_ids': native, 'offline_exact_ids': exact})
    return {'queries': len(output), 'cases': output, 'mean_topk_set_overlap_fraction': mean(x['topk_set_overlap_fraction'] for x in output),
            'queries_with_rank_position_difference': sum(x['rank_position_differences'] > 0 for x in output),
            'max_top1_cosine_distance_regret': max((x['top1_cosine_distance_regret'] for x in output), default=None),
            'scope': 'Saved vector arithmetic only, no native/model calls. Float64 cosine and ascending index tie rule can differ from native float32/ties. No evidence is reselected or decoder rerun.'}


def find_failure(value):
    if isinstance(value, dict):
        if 'fit_failure' in value: return value['fit_failure']
        for child in value.values():
            found = find_failure(child)
            if found is not None: return found
    elif isinstance(value, list):
        for child in value:
            found = find_failure(child)
            if found is not None: return found
    return None


def build(project_root, source_root, dev_annotations_path=None):
    study = project_root / (PREFIX + 'epoch10'); completion_path = study / 'study-completion.json'
    completion = json.loads(completion_path.read_text())
    if not completion.get('finished_at') or completion.get('allowed_further_attempts_in_closed_study') != 0:
        raise ValueError('Terminal closed epoch10 study required before any outputs are read')
    manifest_path = source_root / (PREFIX + 'candidate/epoch10/proposal-manifest.json'); manifest = json.loads(manifest_path.read_text())
    for entry in manifest['sources'] + manifest['read_only_code_dependencies']:
        path = source_root / entry['path']
        if path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']: raise ValueError('Frozen source identity changed')
    folder = study / 'runs/development'; saved = rows(folder / 'records.jsonl')
    train = [x for x in saved if x['measured_phase'] == 'train']; dev = [x for x in saved if x['measured_phase'] == 'development']
    artifact_path = study / 'fitted-head.json'; lock_path = study / 'readout-fit-lock.json'; artifact = None
    if artifact_path.is_file() and lock_path.is_file():
        artifact = json.loads(artifact_path.read_text()); lock = json.loads(lock_path.read_text())
        if (lock.get('fitted_head_sha256') != sha(artifact_path) or lock.get('training_cache_sha256') != sha(folder / 'training-cache.jsonl')
                or lock.get('DEV_requests_before_fit_lock') != 0 or lock.get('confirmation_requests_before_fit_lock') != 0):
            raise ValueError('Fitted artifact/cache/boundary lock differs')
        if artifact.get('state') != 'FROZEN': raise ValueError('Nonfrozen artifact cannot be analyzed as acceptedfit')
    full_dev = len(dev) == 24 and artifact is not None
    if dev_annotations_path is not None and not full_dev: raise ValueError('Cannot open any DEV annotation projection before all24DEV consumed and artifact frozen')
    annotations = normalize_dev_projection(json.loads(dev_annotations_path.read_text()), dev, sha(folder / 'records.jsonl')) if dev_annotations_path is not None else None
    train_cases = cases_for(train, artifact['cached_training_replay'] if artifact is not None else None) if train else []
    dev_cases = cases_for(dev) if full_dev else []
    engine_path = folder / 'final-engine.json'; engine = json.loads(engine_path.read_text()) if engine_path.is_file() else {}
    inputs = [completion_path, manifest_path, folder / 'records.jsonl', folder / 'report.json', engine_path, artifact_path, lock_path]
    if dev_annotations_path is not None: inputs.append(dev_annotations_path)
    return {'schema_version':1,'scope':'Saved-output-only postrun diagnostic; no model/native/fit execution, source changes, selection, rescue or promotion',
            'study_status':completion['status'],'confirmation_status':completion.get('confirmation_status'),
            'confirmation_files_or_labels_opened':False,'unused_DEV_labels_opened':False,'fit_artifact_available':artifact is not None,
            'TRAIN_completed':len(train),'DEV_completed':len(dev),'full_DEV_available':full_dev,
            'TRAIN_in_sample_summary':cases_summary(train_cases) if train_cases else None,
            'DEV_summary':cases_summary(dev_cases) if dev_cases else None,'DEV_cases':dev_cases,
            'auxiliary_TRAIN_OOF_and_runtime_shift':auxiliary_diagnostic(artifact) if artifact is not None else None,
            'decision_fit_diagnostics':artifact['fit_diagnostics'] if artifact is not None else None,
            'fit_failure':find_failure(engine),'DEV_retention':retention(dev, annotations) if full_dev else None,
            'DEV_ANN_drift':ann_diagnostic(dev, folder) if full_dev else None,
            'inputs':[{'path':str(p.relative_to(project_root)) if p.is_relative_to(project_root) else str(p.relative_to(source_root)),
                       'bytes':p.stat().st_size,'sha256':sha(p)} for p in inputs if p.is_file()],
            'limits':['TRAIN is already exposed and replay is in-sample; no TRAIN generalization claim.',
                      'DEV has eight correlated document groups, not24 independent samples.',
                      'Feature strata observe generic text cues, not gold actor/scope correctness annotations.',
                      'OOF predicts weak annotation overlap, not truth/sufficiency; allTRAIN auxiliary scores are in-sample.',
                      'Raw9 readout over saved logits is descriptive only; it is not a new candidate or acceptance rescue.',
                      'Public pretraining contamination is unknown; official benchmark rank/score is not established.'],
            'new_model_calls':0,'new_native_calls':0,'new_optimizer_fits':0,'frozen_sources_modified':False,'official_rank':None,'official_score':None}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--project-root',type=Path,required=True); parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--dev-annotations',type=Path); parser.add_argument('--output',type=Path,required=True); args = parser.parse_args()
    result = build(args.project_root,args.source_root,args.dev_annotations)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2,allow_nan=False); stream.write('\n')
    print(json.dumps({'output':str(args.output),'sha256':sha(args.output),'status':result['study_status'],'TRAIN_completed':result['TRAIN_completed'],'DEV_completed':result['DEV_completed'],'new_calls':0}))


if __name__ == '__main__': main()
