"""Postmeasurement cached DEV analysis only; never import model/native or open CONF.

Prepared before terminal notice. Execute only after parent confirms the single
counted corpus process has terminated and authorizes its saved DEV records.
"""
from pathlib import Path
from collections import Counter
import argparse, hashlib, json, math, statistics
ARMS = {'ruvector_top2': 'ruvector_top2',
        'same_nli_lexical_top2': 'lexical_top2',
        'same_nli_positional_first2': 'positional_first2',
        'native104_on_ruvector_evidence': None}
TYPED = ('Entailment', 'Contradiction', 'NotMentioned')
CANDIDATE_SHA = 'bf7426beaa2b0cc746cf38213d9d03216129398fe4d5d538300aa0af35118c76'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def avg(values):
    return statistics.mean(values) if values else None

def normalized(p):
    values = {str(k): float(v) for k, v in p.items()}
    if not values or any(not math.isfinite(v) or v < 0 for v in values.values()):
        raise ValueError('Invalid probability distribution')
    total = math.fsum(values.values())
    if total <= 0 or abs(total - 1) > 1e-3:
        raise ValueError('Invalid probability mass')
    return {k: float(v / total) for k, v in values.items()}

def decision(p):
    return min(p, key=lambda k: (-p[k], k))

def score(p, gold):
    p = normalized(p)
    if gold not in p:
        raise ValueError('Missing gold')
    return {'correct': decision(p) == gold,
            'brier': math.fsum((v - float(k == gold)) ** 2 for k, v in p.items()),
            'nll': -math.log(max(p[gold], 1e-15))}

def summary(scores):
    return {'n': len(scores), 'correct': sum(s['correct'] for s in scores),
            'brier': avg([s['brier'] for s in scores]),
            'nll': avg([s['nll'] for s in scores])}

def close(a, b):
    if not math.isclose(float(a), float(b), rel_tol=0, abs_tol=1e-10):
        raise ValueError('Saved probability/source coverage replay mismatch')

def analyze(records):
    if (len(records) != 24 or len({r['id'] for r in records}) != 24
            or any(r.get('measured_phase', 'development') != 'development' for r in records)):
        raise ValueError('Exactly24 distinct completed DEV records only; never TRAIN/CONF/partial')
    choices, typed_choices, confusion, scores, typed_scores = {}, {}, {}, {}, {}
    errors, cached, coverage, normalization = [], {}, {}, []
    for name in ARMS:
        choices[name], scores[name] = Counter(), []
        typed_choices[name], typed_scores[name] = Counter(), []
        confusion[name] = {gold: {pred: 0 for pred in TYPED} for gold in TYPED}
        coverage[name] = []
    for row in records:
        ident, response, gold = row['id'], row['response'], row['evaluation']
        cached[ident] = {}
        for name, alias in ARMS.items():
            res = response if name == 'ruvector_top2' else response['baseline104_response'] if alias is None else response['ablation_responses'][name]
            answer = res['answers']['decision']; raw = answer['probabilities']; p = normalized(raw)
            normalization.append(abs(math.fsum(float(v) for v in raw.values()) - 1))
            pred = decision(p)
            if pred != answer['choice']:
                raise ValueError('Saved binary decision mismatch after Python-float normalization')
            s = score(p, gold['gold']); scores[name].append(s); choices[name][pred] += 1
            item = {'id': ident, 'source_group': row['source_group'], 'binary_gold': gold['gold'],
                    'typed_gold': gold['original_threeway_label'], 'binary_prediction': pred,
                    'binary_correct': s['correct'], 'confidence': max(p.values()),
                    'binary_probabilities': p}
            if not s['correct']:
                errors.append({'arm': name, **item})
            cached[ident][name] = item
            if alias is None:
                continue
            a = response['diagnostics']['decision']['arms'][alias]; dec = a['decoding']; c = a['coverage']
            typed = normalized(dec['raw_threeway_probabilities']); tp = decision(typed)
            if tuple(typed) != TYPED and set(typed) != set(TYPED):
                raise ValueError('Missing canonical typed probabilities')
            indices = dec['raw_label_indices']; logits = [float(x) for x in dec['logits']]
            if indices != {'contradiction': 0, 'entailment': 1, 'neutral': 2}:
                raise ValueError('Frozen official C0/E1/N2 mapping changed')
            exps = [math.exp(x - max(logits)) for x in logits]; total = math.fsum(exps)
            mapped = {'Entailment': exps[1]/total, 'Contradiction': exps[0]/total, 'NotMentioned': exps[2]/total}
            for k in TYPED: close(typed[k], mapped[k])
            close(p['Yes'], typed['Entailment']); close(p['No'], typed['Contradiction']+typed['NotMentioned'])
            for x, idx in zip(dec['canonical_logits_E_C_N'], [1,0,2]): close(x,logits[idx])
            typed_choices[name][tp] += 1; confusion[name][gold['original_threeway_label']][tp] += 1
            typed_scores[name].append(score(typed, gold['original_threeway_label']))
            numbers = c['numeric_mentions']; retained = sum(bool(n['retained']) for n in numbers)
            if retained != c['numeric_mentions_retained'] or len(numbers)-retained != c['numeric_mentions_omitted']:
                raise ValueError('Numeric source-position counts changed')
            chars = sum(b-a for a,b in c['selected_source_spans'])
            if chars != c['retained_source_characters'] or len(row['input']['state']) != c['document_characters']:
                raise ValueError('Source character coverage changed')
            close(c['document_character_coverage'], chars / c['document_characters'])
            coverage[name].append({'id':ident, 'numeric_total':len(numbers), 'numeric_retained':retained,
                                   'character_fraction':c['document_character_coverage'],
                                   'selected_unit_count':len(c['selected_chunk_ids_rank_order']),
                                   'pair_tokens':dec['actual_model_pair_tokens']})
            item.update(typed_prediction=tp, typed_probabilities=typed,
                        typed_correct=tp==gold['original_threeway_label'],
                        premise=a['premise'], source_spans=c['selected_source_spans'], logits=logits)
    output = {}
    for name, alias in ARMS.items():
        wrong = [x['confidence'] for x in errors if x['arm'] == name]
        negatives = [d[name] for d in cached.values() if d[name]['binary_gold']=='No']
        output[name] = {'binary':summary(scores[name]), 'binary_predicted_counts':dict(choices[name]),
                        'binary_No_gold_correct':sum(x['binary_correct'] for x in negatives),
                        'binary_No_gold_n':len(negatives),
                        'wrong_confidence_mean':avg(wrong), 'wrong_confidence_at_least_0_8':sum(x>=.8 for x in wrong)}
        if alias is not None:
            contradictions = [d[name] for d in cached.values() if d[name]['typed_gold']=='Contradiction']
            c = coverage[name]; total = sum(x['numeric_total'] for x in c); kept = sum(x['numeric_retained'] for x in c)
            output[name].update(threeway=summary(typed_scores[name]), typed_predicted_counts=dict(typed_choices[name]),
                                typed_confusion_gold_to_prediction=confusion[name],
                                typed_Contradiction_gold_correct=sum(x['typed_correct'] for x in contradictions),
                                typed_Contradiction_gold_n=len(contradictions),
                                source_retention={'numeric_positions_per_query':total,'numeric_retained_per_query':kept,
                                                  'numeric_fraction':kept/total if total else None,
                                                  'mean_character_fraction':avg([x['character_fraction'] for x in c]),
                                                  'examples':c,'scope':'Repeated per-query source positions, not numeric truth or sufficiency'})
    comparisons = {}
    for name in list(ARMS)[1:]:
        rows=[]
        for ident, values in cached.items():
            a,b=values['ruvector_top2'],values[name]
            item={'id':ident,'source_group':a['source_group'],'native_correct':a['binary_correct'],'control_correct':b['binary_correct'],
                  'binary_disagreement':a['binary_prediction']!=b['binary_prediction']}
            if name != 'native104_on_ruvector_evidence':
                item.update(same_premise=a['premise']==b['premise'], same_source_spans=a['source_spans']==b['source_spans'],
                            typed_disagreement=a['typed_prediction']!=b['typed_prediction'])
                if item['same_premise']:
                    item['same_context_max_logit_drift']=max(abs(x-y) for x,y in zip(a['logits'],b['logits']))
            rows.append(item)
        comparisons[name]={'native_only_correct_ids':[x['id'] for x in rows if x['native_correct'] and not x['control_correct']],
                           'control_only_correct_ids':[x['id'] for x in rows if x['control_correct'] and not x['native_correct']],
                           'both_wrong_ids':[x['id'] for x in rows if not x['native_correct'] and not x['control_correct']],
                           'binary_disagreement_n':sum(x['binary_disagreement'] for x in rows),'examples':rows}
    return {'schema_version':1,'status':'COMPLETE_SAVED_DEV_DIAGNOSTIC','n':24,
            'document_groups':len({r['source_group'] for r in records}),
            'gold_binary_counts':dict(Counter(r['evaluation']['gold'] for r in records)),
            'gold_threeway_counts':dict(Counter(r['evaluation']['original_threeway_label'] for r in records)),
            'arms':output,'paired_comparisons':comparisons,'errors':errors,
            'normalization_max_raw_mass_deviation':max(normalization),
            'proper_score_scope':'Supplement normalizes Python float distributions before Brier/NLL. Frozen actual independent acceptance audit is authoritative if tiny normalization differences occur; no decision or gate changes.',
            'interpretation_limits':['Typed Contradiction recognition and binary No accuracy are different quantities.',
                                     'Same-model selectors share one fixed active BPE packing algorithm; they need not share contexts.',
                                     'Numeric/source retention cannot establish truth or insufficient evidence.',
                                     'Only8DEV document groups; newDEV is now exposed forever; no cross-epoch causal gain claim.',
                                     'No new inference, fit, confirmation, official rank or SOTA claim.'],
            'new_model_calls':0,'new_native_calls':0,'new_fits':0,'confirmation_labels_read':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--records',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    if args.out.exists():raise ValueError('Refuse output overwrite')
    records=[json.loads(x) for x in args.records.read_text().splitlines() if x]
    result=analyze(records);result.update(saved_records_sha256=sha(args.records),frozen_candidate_manifest_sha256=CANDIDATE_SHA,
                                         scope='Pure terminal saved DEV24 analysis only; no CONF/full-source/model/native access.')
    with args.out.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'diagnostic_sha256':sha(args.out),'new_inference':0}))
if __name__=='__main__':main()
