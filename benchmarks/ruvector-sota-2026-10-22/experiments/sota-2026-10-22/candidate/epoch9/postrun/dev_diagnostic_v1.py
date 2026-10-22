"""One terminal DEV-only saved-output replay; standard library, no inference."""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path

PREFIX = 'experiments/sota-2026-10-22/'
ARMS = ('ruvector_top2', 'same_nli_lexical_top2', 'same_nli_positional_first2', 'native104_on_ruvector_evidence')
SELECTORS = dict(zip(ARMS[:3], ('ruvector_top2', 'lexical_top2', 'positional_first2')))


def pin(path, root):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(root)), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def decision(probs):
    return min(probs, key=lambda key: (-probs[key], key))


def metrics(probs, gold):
    # Pinned legacy scorer leaves distributions inside strict SUM_TOL=1e-3
    # unchanged, including Native104 float32 serialization roundoff.
    if set(probs) != {'Yes', 'No'} or not all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in probs.values()) or abs(sum(probs.values()) - 1) > 1e-3:
        raise ValueError('Invalid saved binary probabilities')
    predicted = decision(probs)
    return {'predicted': predicted, 'correct': predicted == gold, 'confidence': max(probs.values()),
            'brier': sum((p - float(label == gold)) ** 2 for label, p in probs.items()),
            'nll': -math.log(max(probs[gold], 1e-15))}


def merge(spans):
    output = []
    for a, b in sorted(spans):
        if output and a <= output[-1][1]: output[-1][1] = max(output[-1][1], b)
        else: output.append([a, b])
    return output


def build(root, annotation_path=None):
    study = root / (PREFIX + 'epoch9')
    folder = study / 'runs/development'
    completion_path = study / 'study-completion.json'
    completion = json.loads(completion_path.read_text())
    if completion['status'] != 'REJECTED_DEV_GATE' or completion['allowed_further_attempts_in_closed_study'] != 0 or completion['confirmation_consumed_or_attempted']:
        raise ValueError('Require closed rejected DEV study with unused confirmation')
    records_path = folder / 'records.jsonl'
    records = [json.loads(line) for line in records_path.open() if line.strip()]
    if len(records) != 24 or len({r['source_group'] for r in records}) != 8 or any(r['measured_phase'] != 'development' or r['split'] != 'dev' for r in records):
        raise ValueError('Require exact saved DEV24 / eight groups only')
    annotations = {}
    if annotation_path:
        projection = json.loads(annotation_path.read_text())
        if projection['saved_DEV_records_sha256'] != hashlib.sha256(records_path.read_bytes()).hexdigest() or projection['confirmation_records_or_labels_included']:
            raise ValueError('Projection must bind only the exact saved DEV records')
        annotations = {r['id']: r for r in projection['records']}
        if set(annotations) != {r['id'] for r in records}: raise ValueError('Annotation projection must be exact DEV24, without extra identities')
    results = {arm: [] for arm in ARMS}
    confusion = {arm: collections.Counter() for arm in ARMS[:3]}
    coverage = {arm: [] for arm in ARMS[:3]}
    groups = collections.defaultdict(lambda: {arm: 0 for arm in ARMS})
    cases = []
    validated = collections.Counter()
    for row in records:
        gold = row['evaluation']['gold']; typed_gold = row['evaluation']['original_threeway_label']
        if gold != ('Yes' if typed_gold == 'Entailment' else 'No'): raise ValueError('Saved gold mapping mismatch')
        response = row['response']; state = row['input']['state']; case = {'id': row['id'], 'group': row['source_group'], 'gold_binary': gold, 'gold_threeway': typed_gold, 'predictions': {}}
        answers = {ARMS[0]: response['answers']['decision'], ARMS[1]: response['ablation_responses'][ARMS[1]]['answers']['decision'], ARMS[2]: response['ablation_responses'][ARMS[2]]['answers']['decision'], ARMS[3]: response['baseline104_response']['answers']['decision']}
        for arm, answer in answers.items():
            scored = metrics(answer['probabilities'], gold)
            if answer['choice'] != scored['predicted']: raise ValueError('Saved answer/probability inconsistency')
            results[arm].append(scored); groups[row['source_group']][arm] += scored['correct']; case['predictions'][arm] = scored['predicted']; validated['binary_answers'] += 1
        for arm, selector in SELECTORS.items():
            observed = response['diagnostics']['decision']['arms'][selector]
            trace = observed['decoding']; raw = trace['logits']; mapping = trace['raw_label_indices']
            if mapping != {'entailment': 0, 'neutral': 1, 'contradiction': 2} or len(raw) != 3: raise ValueError('Frozen model label order changed')
            exps = [math.exp(v - max(raw)) for v in raw]; probs = [v / sum(exps) for v in exps]
            typed = {'Entailment': probs[0], 'Contradiction': probs[2], 'NotMentioned': probs[1]}
            if any(abs(typed[k] - trace['raw_threeway_probabilities'][k]) > 1e-12 for k in typed): raise ValueError('Raw-logit typed probability replay mismatch')
            expected = {'Yes': typed['Entailment'], 'No': typed['Contradiction'] + typed['NotMentioned']}
            if any(abs(expected[k] - answers[arm]['probabilities'][k]) > 1e-12 for k in expected): raise ValueError('Neutral-preserving binary replay mismatch')
            confusion[arm][(typed_gold, decision(typed))] += 1
            cov = observed['coverage']; selected = merge(cov['selected_source_spans'])
            numeric = cov['numeric_mentions']
            for item in numeric:
                a, b = item['span']
                if state[a:b] != item['text'] or item['retained'] != any(x <= a and b <= y for x, y in selected): raise ValueError('Numeric source retention mismatch')
            value = {'numeric_total': len(numeric), 'numeric_retained': sum(i['retained'] for i in numeric), 'source_character_coverage': cov['document_character_coverage'], 'binary_correct': results[arm][-1]['correct']}
            if annotations:
                annotation = annotations[row['id']]
                if annotation['gold_threeway'] != typed_gold or annotation['source_group'] != row['source_group'] or annotation['hypothesis_id'] != row['provenance']['hypothesis_id']: raise ValueError('DEV annotation identity mismatch')
                if any(type(a) is not int or type(b) is not int or not 0 <= a < b <= len(state) for a,b in annotation['annotation_spans']): raise ValueError('Gold annotation outside exact saved state')
                gold_spans = merge(annotation['annotation_spans']); size = sum(b-a for a,b in gold_spans)
                retained = sum(max(0,min(b,y)-max(a,x)) for a,b in gold_spans for x,y in selected)
                value.update(annotation_available=bool(size), any_gold_overlap=retained > 0 if size else None, all_gold_characters=retained == size if size else None)
            coverage[arm].append(value); validated['typed_logit_and_numeric_replays'] += 1
        cases.append(case)
    summaries = {}
    for arm, rows in results.items():
        summary = {'n': len(rows), 'correct': sum(r['correct'] for r in rows), 'accuracy': sum(r['correct'] for r in rows)/len(rows), 'brier': sum(r['brier'] for r in rows)/len(rows), 'nll': sum(r['nll'] for r in rows)/len(rows), 'predicted_counts': dict(collections.Counter(r['predicted'] for r in rows)), 'wrong_confidence_at_least_0_8': sum(not r['correct'] and r['confidence'] >= .8 for r in rows), 'mean_confidence_wrong': sum(r['confidence'] for r in rows if not r['correct']) / sum(not r['correct'] for r in rows)}
        for key in ('n','correct','accuracy','brier','nll'):
            if abs(summary[key] - completion['development_metrics'][arm][key]) > 1e-12: raise ValueError('Terminal saved-metric replay mismatch')
        summaries[arm] = summary
    coverage_summary = {}
    for arm, rows in coverage.items():
        value = {'numeric_total': sum(r['numeric_total'] for r in rows), 'numeric_retained': sum(r['numeric_retained'] for r in rows), 'mean_source_character_coverage': sum(r['source_character_coverage'] for r in rows)/len(rows)}
        if annotations:
            annotated = [r for r in rows if r['annotation_available']]
            value.update(annotated_cases=len(annotated), any_gold_overlap=sum(r['any_gold_overlap'] for r in annotated), all_gold_characters=sum(r['all_gold_characters'] for r in annotated), fully_retained_binary_wrong=sum(r['all_gold_characters'] and not r['binary_correct'] for r in annotated))
        coverage_summary[arm] = value
    paired = {}
    for arm in ARMS[1:]:
        paired[arm] = dict(collections.Counter('both_right' if a['correct'] and b['correct'] else 'native_only_right' if a['correct'] else 'other_only_right' if b['correct'] else 'both_wrong' for a,b in zip(results[ARMS[0]],results[arm])))
    inputs = [records_path, completion_path, folder/'development-comparison.json', folder/'wire.jsonl', root/(PREFIX+'candidate/epoch9/proposal-manifest.json')]
    if annotation_path: inputs.append(annotation_path)
    return {'schema_version':1,'scope':'One pure cached terminal DEV24 replay only; no confirmation text/labels/records opened, no model/native calls, fits, selection or frozen source changes','status':'REJECTED_DEV_GATE','confirmation_status':'NOT_MODEL_CONSUMED','statistical_unit':'8 document groups, three correlated hypotheses each; descriptive comparisons, no independent-query inference or causal cross-epoch model claim','gold_binary_counts':dict(collections.Counter(r['evaluation']['gold'] for r in records)),'gold_threeway_counts':dict(collections.Counter(r['evaluation']['original_threeway_label'] for r in records)),'four_arm_metrics':summaries,'threeway_confusions':{arm:[{'gold':g,'predicted':p,'n':n} for (g,p),n in sorted(counts.items())] for arm,counts in confusion.items()},'paired_disagreements':paired,'per_document_correct':dict(groups),'case_decisions_only':cases,'coverage':coverage_summary,'gold_annotation_retention_available':bool(annotations),'coverage_scope':'Coverage is mechanical source exposure, not sufficiency. NotMentioned has no positive evidence spans. Numeric counts repeat each document across three hypotheses. If no exact DEV-only annotation projection was supplied, no full original source was opened and gold retention is unavailable.','cached_validation':{'status':'PASS','checks':dict(validated),'terminal_metric_cells_compared':20,'source_result_pins':[pin(path,root) for path in inputs if path.is_file()]},'one_future_direction':{'status':'Unimplemented/unmeasured, no new selection, threshold, readout or optimizer','hypothesis':'Use TRAIN-only evidence-supervised clause-role, polarity and conditional-scope learning with separate Entailment/Contradiction/NotMentioned targets and one shared reader across matched retrieval controls. Freeze source rule and objective before a new document-group holdout.','separation':'Do not fit or tune on this consumed DEV; unused confirmation remains unused. No generic model grid or automatic execution.'},'new_model_calls':0,'new_native_calls':0,'new_optimizer_fits':0,'frozen_candidate_changes':0,'official_score':None,'official_rank':None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root',type=Path,required=True); parser.add_argument('--annotations',type=Path); parser.add_argument('--output',type=Path,required=True); args=parser.parse_args()
    result=build(args.root,args.annotations)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({'output':str(args.output),'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'cached_validation':result['cached_validation']['status'],'gold_annotation_retention_available':result['gold_annotation_retention_available']}))
