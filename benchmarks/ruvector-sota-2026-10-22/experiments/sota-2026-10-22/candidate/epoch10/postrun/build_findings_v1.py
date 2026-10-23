"""Derive concise findings from the immutable cached diagnostic only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIAGNOSTIC_SHA256 = '3d3d723a40f9cfc85aeee57a86798f20bc1772c5e792d5f8287dcfb79e231cd4'
spec = importlib.util.spec_from_file_location('epoch10_cached_diagnostic', HERE/'build_diagnostic_v1.py')
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)


def build(path):
    literal = path.read_bytes()
    if hashlib.sha256(literal).hexdigest() != DIAGNOSTIC_SHA256:
        raise ValueError('Immutable diagnostic identity differs')
    value = json.loads(literal)
    if value['study_status'] != 'REJECTED_DEV_GATE' or value['TRAIN_completed'] != 72 or value['DEV_completed'] != 24:
        raise ValueError('Expected exact terminal epoch10 result')
    paired = {}
    for selector, views in value['DEV_summary'].items():
        raw, fitted = views['fixed_raw9_threeway'], views['trained_head']
        paired[selector] = {'raw9_binary_correct':raw['binary']['correct'],'trained_binary_correct':fitted['binary']['correct'],
            'raw9_binary_brier':raw['binary']['brier'],'trained_binary_brier':fitted['binary']['brier'],
            'raw9_binary_nll':raw['binary']['nll'],'trained_binary_nll':fitted['binary']['nll'],
            'raw9_threeway_correct':raw['threeway']['correct'],'trained_threeway_correct':fitted['threeway']['correct'],
            'trained_threeway_confusion':fitted['threeway_confusion']}
    retention = value['DEV_retention']; retained = {(row['id'],row['selector']):row for row in retention['cases']}
    dev_aux = {}
    for selector in D.SELECTORS:
        probabilities,targets=[],[]
        for case in value['DEV_cases']:
            row=retained[(case['id'],selector)];p=case['selectors'][selector]['auxiliary_runtime_probability']
            if p is None:raise ValueError('Missing deployed auxiliary probability')
            probabilities.append(p);targets.append(float(bool(row['any_annotation_overlap'])) if row['positive_annotation_spans_available'] else 0.)
        dev_aux[selector]=D.probability_metrics(probabilities,targets)
    primary=paired['ruvector_top2'];positional=paired['positional_first2']
    return {'schema_version':1,'diagnostic_sha256':DIAGNOSTIC_SHA256,'status':'REJECTED_DEV_GATE','champion_promoted':False,
        'submitted_native104_champion_preserved':True,'confirmation48_consumed_or_attempted':False,
        'official_score':None,'official_rank':None,'matched_saved_input_readouts':paired,
        'trained_native_vs_positional':{'correct_difference':primary['trained_binary_correct']-positional['trained_binary_correct'],
            'brier_difference':primary['trained_binary_brier']-positional['trained_binary_brier'],
            'nll_difference':primary['trained_binary_nll']-positional['trained_binary_nll'],
            'interpretation':'Native ties positional17/24 and same-excerpt10417/24; positional has better proper scores. Strict development acceptance fails; confirmation remains unused.'},
        'auxiliary_TRAIN_all_views':value['auxiliary_TRAIN_OOF_and_runtime_shift']['all_views'],
        'auxiliary_consumed_DEV':dev_aux,'DEV_annotation_numeric_retention':retention['aggregate'],
        'DEV_ANN':{k:v for k,v in value['DEV_ANN_drift'].items() if k!='cases'},
        'learning':['The fixed TRAIN-only head reduces raw pretrained positive bias on the same saved DEV inputs across all three selectors; this is descriptive within this split, not an official result or cross-epoch causal gain.',
            'Native retains more annotated characters than positional but does not beat its binary accuracy/proper scores. Retained annotation does not establish correct actor/scope interpretation or sufficiency.',
            'The native typed head distinguishes only one of five contradictions as Contradiction; two become Entailment and two NotMentioned. Weak coverage discrimination cannot replace typed decision quality.',
            'TRAIN OOF and final allTRAIN auxiliary probabilities differ substantially; final TRAIN discrimination is in-sample and cannot establish deployment generalization.',
            'All24 saved native rankings match offline cosine ordering, so these observations provide no ANN-ranking defect to repair in this epoch.'],
        'one_next_direction':{'status':'Unimplemented/unmeasured; no further attempt in closed epoch10',
            'hypothesis':'A single pretrained typed clause decision pipeline with explicit actor/scope contradiction supervision and a deployment-matched evidence-proxy interface, frozen before a genuinely unused document split, may turn better native evidence retention into a measured decision advantage.',
            'conditions':'Use only permitted training data and exact licensed model/source revisions; preserve E/C/N and matched same-model selectors. Do not fit/select/calibrate on any consumed DEV or unused confirmation. Any paid work requires a new actually authorized remaining cap and frozen price/time/cleanup plan.'},
        'dependence':'DEV24 contains eight documents with three correlated queries each. Auxiliary views also share queries/documents. No independent24-case significance or full-benchmark placement is claimed.',
        'new_model_calls':0,'new_native_calls':0,'new_optimizer_fits':0,'frozen_candidate_sources_modified':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--diagnostic',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=build(args.diagnostic)
    with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'output':str(args.output),'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'new_calls':0}))


if __name__=='__main__':main()
