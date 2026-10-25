"""E40 authorized post-join public math only; no project/scorer imports or modes."""
from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction
import datetime
import hashlib
import json
import math
from pathlib import Path
import struct

W=Path('/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05')
R=W/'project'
OWN=Path('/workspace/ruvector-e40-acceptance-audit')
P='experiments/sota-2026-10-22/'
E=P+'epoch40/'
A=P+'audit/epoch40/'
ARMS=['tasksource_source_order','tasksource_native','tasksource_lexical','b354_source_order']
LABELS=['NotMentioned','Entailment','Contradiction']
PRIMARY='tasksource_native'
REFERENCE='b354_source_order'
TOL=1e-12

def loads(b):
    def pairs(items):
        out={}
        for k,v in items:
            assert k not in out;out[k]=v
        return out
    def bad(x):raise ValueError('NONFINITE_JSON')
    d=json.loads(b,object_pairs_hook=pairs,parse_constant=bad)
    def walk(v):
        if isinstance(v,float):assert math.isfinite(v)
        elif isinstance(v,dict):
            for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    walk(d);return d

def resolve(path):
    p=Path(path);return p if p.is_absolute()else R/p

def load(path):return loads(resolve(path).read_bytes())

def ref(path):
    p=resolve(path);b=p.read_bytes()
    try:name=p.relative_to(R).as_posix()
    except ValueError:name=str(p)
    return {'path':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def exact(row):
    assert row==ref(row['path']);return load(row['path'])

def near(a,b):
    assert type(a)in(int,float)and type(b)in(int,float)
    assert math.isfinite(a)and math.isfinite(b)and abs(a-b)<=TOL,(a,b)

def compare(a,b):
    if isinstance(a,dict):
        assert isinstance(b,dict)and set(a)==set(b)
        for k in a:compare(a[k],b[k])
    elif isinstance(a,list):
        assert isinstance(b,list)and len(a)==len(b)
        for x,y in zip(a,b):compare(x,y)
    elif type(a)is float:near(a,b)
    else:assert type(a)is type(b)and a==b,(a,b)

def forecast(z):
    assert isinstance(z,list)and len(z)==3
    assert all(type(v)is float and math.isfinite(v)and struct.unpack('<f',struct.pack('<f',v))[0]==v for v in z)
    with localcontext()as ctx:
        ctx.prec=90
        d=[Decimal.from_float(v)for v in z];shifts=[v-max(d)for v in d]
        den=sum(v.exp()for v in shifts).ln();native_lp=[v-den for v in shifts]
        native_p=[v.exp()for v in native_lp]
        p=[float(native_p[i])for i in [1,0,2]];lp=[float(native_lp[i])for i in [1,0,2]]
    ordered=[z[i]for i in [1,0,2]];winner=max(range(3),key=lambda i:ordered[i])
    return [float(v)for v in native_p],p,lp,winner

def metric(rows,arm,gold):
    scores=[];conf={g:{p:0 for p in LABELS}for g in LABELS}
    for row in rows:
        r=row['readouts'][arm];assert r['readout_id']==row['id']+'::'+arm
        assert r['model_tag']==('b354'if arm==REFERENCE else'tasksource')
        native,p,lp,winner=forecast(r['raw_native_logits'])
        compare(native,r['raw_native_probabilities']);compare(p,r['probabilities_N_E_C']);compare(lp,r['log_probabilities_N_E_C'])
        assert r['primary_label']==r['argmax_label']==LABELS[winner]and r['canonical_argmax_index']==winner
        g=gold[row['id']];pred=LABELS[winner];gi=LABELS.index(g);conf[g][pred]+=1
        brier=math.fsum((prob-(i==gi))**2 for i,prob in enumerate(p));pg=p[gi]
        scores.append({'id':row['id'],'gold':g,'prediction':pred,'correct':int(g==pred),'probabilities_N_E_C':p,
                       'stable_log_probabilities_N_E_C':lp,'p_gold':pg,'Brier':brier,'NLL':-lp[gi],
                       'NLL_clipped_1e_12_diagnostic':-math.log(max(pg,1e-12)),
                       'display_underflow':pg==0,'clipped_diagnostic':pg<1e-12})
    correct=sum(s['correct']for s in scores);author={'accuracy':correct/12};support={}
    for label in ['Entailment','Contradiction']:
        n=sum(conf[label].values());predicted=sum(conf[g][label]for g in LABELS);tp=conf[label][label]
        support[label]={'support':n,'predicted':predicted,'TP':tp};suffix=label.lower()
        author['precision_'+suffix]=float(Fraction(tp,predicted))if predicted else 0.
        author['recall_'+suffix]=float(Fraction(tp,n))if n else None
        author['f1_'+suffix]=float(Fraction(2*tp,n+predicted))if n else None
    for name in ['precision','recall','f1']:
        x,y=author[name+'_entailment'],author[name+'_contradiction']
        author[name+'_mean']=None if x is None or y is None else(x+y)/2
        author[name+'_hmean']=None if x is None or y is None else 0. if not x or not y else 2*x*y/(x+y)
    return {'N':12,'correct':correct,'accuracy':correct/12,'confusion':conf,'E_C_support':support,
            'author_helper_metrics':author,'author_EC_F1_mean':author['f1_mean'],'author_EC_F1_hmean':author['f1_hmean'],
            'Brier':math.fsum(s['Brier']for s in scores)/12,'NLL':math.fsum(s['NLL']for s in scores)/12,
            'NLL_clipped_1e_12_diagnostic':math.fsum(s['NLL_clipped_1e_12_diagnostic']for s in scores)/12,
            'display_probability_underflow_count':sum(s['display_underflow']for s in scores),
            'diagnostic_clip_count':sum(s['clipped_diagnostic']for s in scores),'scores':scores}

def gates(m):
    p=m[PRIMARY];out={'all_four_full_N12':True,'integrity_complete_no_errors':True,
                     'primary_gain_at_least_two_correct_vs_b354':p['correct']>=m[REFERENCE]['correct']+2}
    for arm in [x for x in ARMS if x!=PRIMARY]:
        other=m[arm];out[arm+':accuracy_nondecrease']=p['accuracy']+TOL>=other['accuracy']
        x,y=p['author_EC_F1_mean'],other['author_EC_F1_mean']
        out[arm+':author_EC_F1_mean_defined_nondecrease']=x is not None and y is not None and x+TOL>=y
        out[arm+':Brier_nonincrease']=p['Brier']<=other['Brier']+TOL
        out[arm+':stable_unclipped_NLL_nonincrease']=p['NLL']<=other['NLL']+TOL
    return out

def quantile(values,q):
    a=sorted(values);x=(len(a)-1)*q;i=int(x);return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(x-i)

def main():
    expected={E+'plan.json':'3083581ef07d43a4e64d635de87f9dc78cfcd444746b15215b2791340301ba31',
              E+'runs/dev/raw.json':'f74ae28579c55d125f6cdf36f07886a33265a37ca009860dfbb5d363ed871c39',
              A+'qualification-replay.json':'fa5a547ca6de559eda0c82eff538f6dbbc84b5cbb85d370831ab7a20df4470f9',
              A+'actual-physical-closure-independent-v1.json':'46efb9b6319153d2979e4f1a2f637fe3acfd399243063903aed49ba444798704',
              str(W/'gold-custody-once/joined_labels.json'):'2fb073dfd1c56cfea73e8418fa072e567a894da29774410fef68ea2db3ef3b64'}
    for p,sha in expected.items():assert ref(p)['sha256']==sha
    plan=load(E+'plan.json');raw=load(E+'runs/dev/raw.json');replay=load(A+'qualification-replay.json')
    closed=load(A+'actual-physical-closure-independent-v1.json');joined=load(W/'gold-custody-once/joined_labels.json')
    assert replay['evaluation_executed']is True and replay['checks_passed']is True and replay['dev_passed']is False
    assert replay['status']=='REJECTED_DEV_PILOT'and replay['command_execution']['evaluate_function_calls']==1
    assert replay['command_execution']['capture_failure_function_calls']==0
    assert raw['status']=='DEV_FORECASTS_COMPLETE_NO_GOLD'and raw['errors']==[]
    ids=plan['data_roles']['dev'];assert [r['id']for r in raw['cases']]==ids and len(ids)==len(set(ids))==12
    assert joined['selected_ids']==ids and set(joined['labels'])==set(ids)
    assert joined['semantic_labels_decoded']==12 and joined['label_reader_calls']==1
    assert joined['all_labels_decoded_after_forecasts_and_physical_closure']is True
    gold=joined['labels'];assert all(type(v)is str and v in LABELS for v in gold.values())
    for row in plan['pins']:assert ref(row['path'])==row
    assert len(plan['pins'])==221
    assert raw['counters']==replay['actual_execution']['actual_counters']
    for k,v in plan['expected_operation_counters']['dev'].items():assert type(raw['counters'][k])is int and raw['counters'][k]==v
    assert raw['counters']['BGE_forward_calls_attempted']==raw['counters']['BGE_forward_calls_completed']==158
    assert closed['checks_passed']is closed['qualified_supervisor_passed']is closed['physical_closure_passed']is True
    required={cid+'::'+arm for cid in ids for arm in ARMS}
    assert len(raw['completed_readout_ids'])==48 and set(raw['completed_readout_ids'])==required
    assert len(raw['required_readout_ids'])==48 and set(raw['required_readout_ids'])==required
    computed={arm:metric(raw['cases'],arm,gold)for arm in ARMS}
    for arm,metrics in computed.items():
        for key,value in metrics.items():compare(value,replay['metrics'][arm][key])
        undefined={k for k,v in metrics['author_helper_metrics'].items()if v is None}
        assert set(replay['metrics'][arm]['author_undefined_metrics'])==undefined
        assert all(v['status']=='UNDEFINED_AUTHOR_NAN'for v in replay['metrics'][arm]['author_undefined_metrics'].values())
    checks=gates(computed);compare(checks,replay['gate_checks']);assert not all(checks.values())
    paired={}
    for arm in [x for x in ARMS if x!=PRIMARY]:
        pairs=list(zip(computed[PRIMARY]['scores'],computed[arm]['scores']))
        paired[arm]={'both_correct':sum(a['correct']and b['correct']for a,b in pairs),
                     'native_gained':sum(a['correct']and not b['correct']for a,b in pairs),
                     'native_lost':sum(not a['correct']and b['correct']for a,b in pairs),
                     'both_wrong':sum(not a['correct']and not b['correct']for a,b in pairs),
                     'accuracy_gain_pp':100*(computed[PRIMARY]['accuracy']-computed[arm]['accuracy']),
                     'Brier_delta_native_minus_control':computed[PRIMARY]['Brier']-computed[arm]['Brier'],
                     'NLL_delta_native_minus_control':computed[PRIMARY]['NLL']-computed[arm]['NLL']}
    timing={};coverage={};pipeline=[]
    for arm in ARMS:
        rows=[r['readouts'][arm]for r in raw['cases']]
        timing[arm]={key:{'N':12,'p50':quantile([r['timing'][key]for r in rows],.5),'p95':quantile([r['timing'][key]for r in rows],.95)}for key in ['pair_tokenization_seconds','NNI_forward_seconds','reader_total_seconds','context_order_seconds','native_query_seconds']}
        coverage[arm]={'N':12,'claim_complete':sum(r['input_audit']['claim_complete']is True for r in rows),'premise_truncated':sum(r['input_audit']['premise_truncated']is True for r in rows),'maximum_joint_tokens':max(r['input_audit']['joint_tokens']for r in rows),'minimum_numeric_literal_coverage':min(r['input_audit']['numeric_literal_coverage']for r in rows),'total_full_numeric_literal_count':sum(r['input_audit']['full_numeric_literal_count']for r in rows),'total_retained_numeric_literal_count':sum(r['input_audit']['retained_numeric_literal_count']for r in rows)}
        assert coverage[arm]['claim_complete']==12 and coverage[arm]['maximum_joint_tokens']<=512
    for case in raw['cases']:
        p=case['pipeline_timing'];near(p['batch_case_span_seconds'],p['all_readouts_completed_monotonic_seconds']-p['source_preparation_started_monotonic_seconds']);pipeline.append(p['batch_case_span_seconds'])
    assert [v['model_tag']for v in raw['reader_lifecycle']if v['event']=='MODEL_UNLOAD_AFTER_GC']==['b354','tasksource']
    for v in raw['reader_lifecycle']:
        if v['event']=='MODEL_UNLOAD_AFTER_GC':assert all(v[k]is True for k in ['reader_weakref_dead','model_weakref_dead','tokenizer_weakref_dead'])
    report={'schema_version':1,'epoch':40,'kind':'REAL_CONTRACTNLI_HELDOUT_DEV_TRANSFER_PILOT','phase':'dev','checks_passed':True,'scientific_integrity_checks_passed':True,'evaluation_executed':True,'dev_passed':False,'status':'INDEPENDENTLY_VERIFIED_REJECTED_DEV_PILOT','source_commit':'57138c4423ce8c83d7965a5b00ea5338d24b002d','inputs':{p:ref(p)for p in expected},'model_assets_admission':plan['model_assets_admission'],'metrics_policy':plan['metrics_policy'],'ROOT_contract':plan['root_contract'],'independent_method':'No project imports/helper/scorer execution. Decimal90 independently reconstructs softmax/logsoftmax from exactly FP32-representable raw ENC logits; canonical NE C ordering [1,0,2] and first maximum. Fraction confusion counts reproduce author evaluate_class E/C metrics and undefined rules; all per-case proper scores recomputed in Python double from independent probabilities.','actual_NLI_readouts':48,'canonical_label_distribution':{v:Counter(gold.values())[v]for v in LABELS},'fixed_denominator':12,'same_shared_hypothesis':'nda-7','computed_metrics':computed,'frozen_gates_recomputed':checks,'failed_gate_names':[k for k,v in checks.items()if not v],'paired_control_comparisons_descriptive':paired,'latency_components_recomputed':timing,'public_input_coverage_summary':coverage,'batch_case_span_descriptive':{'p50':quantile(pipeline,.5),'p95':quantile(pipeline,.95),'scope':'Actual spans include other-case queue/model initialization and batch waits, exclude initial sharedBGEinit; not independent isolated request or publisher latency.'},'resources':raw['resources'],'raw_worker_wall_seconds':raw['wall_seconds'],'label_custody':replay['label_custody'],'operation_counters':raw['counters'],'all221_source_pins_exact':True,'verification_counts':{'actual_raw_FP32_logits':144,'actual_readouts':48,'source_logit_probability_logprob_triplets':144,'per_case_Brier_NLL_pairs':48,'author_metric_arms':4,'frozen_gate_checks':15,'actual_helper_EVALUATE_or_BIND_calls_by_auditor':0,'original_archive_case_features_vault_private_inputaudit_or_goldtoken_reads':0},'interpretation':'The pilot completed with valid captured execution and valid12-label custody, but fails its frozen quality gates. Native4/12 equals B3544/12 and is below lexical6/12; it does not obtain the required+2 correct gain. Native Brier/NLL improve relative to all three controls, but those proper-score gains do not override failed accuracy/F1 requirements. GoldContradiction support0 makes author C recall/F1 and E/C recall/F1 mean/hmean undefined; null+source status is correct, never zero or a reduced denominator. This is a quality rejection with integrity pass, distinct from E39 unsupported-label integrity rejection.','limitations':['Only12 label-blind-selected held-out DEV documents share one known nda-7 hypothesis; no class balancing/resampling/drop. Missing C support is an observed limitation, not permission to replace cases.','No population significance, fresh confirmation, full17-hypothesis/evidence task, official paper score or benchmark rank is established. Both model lineage/ContractNLI training overlap and official eligibility remain HOLD.','B354 source-order is the direct reader reference, not the submitted native104 champion. Native104/champion,74unused/24protected and all prior histories remain unchanged.','Private full input/token audits and original source text were not re-opened here. The frozen EVALUATE independently checked them; this audit verifies public numeric/count metadata and authorized postjoin labels only. Numeric literal coverage remains a substring/offset diagnostic and does not establish numerical correctness.','The allowed512 ONLY_FIRST budget preserves full claim and intentionally truncates premises; source-order does not mean full untruncated document. No retrieval miss proves NotMentioned.','No new model/tokenizer/native/scorer/observer/guard/payload/network calls were made. Final RESULTS/BIND/publication inventory and import-adapter chronology still require their exact public references before final publication approval.'],'future_direction':'Preserve the failed cohort and every arm. Do not change thresholds, rank policy, precision, class coverage or labels using these outcomes and call it confirmation. A separately preregistered broader multi-hypothesis/unused-document study or a new fixed context-coverage hypothesis may be evaluated only under a new source/data admission; report author-undefined metrics transparently. First compare native ordering against the stronger lexical control at matched budgets; proper-score improvement alone is insufficient for this gate.','benchmark_accuracy':None,'official_rank':None,'benchmark_accepted':False,'champion_promoted':False,'used_confirmation_identities':[],'publication_final_binding_pending':True,'reviewer_code':ref(Path(__file__)),'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    output=OWN/'ACTUAL_METRIC_REJECTION_v1.json'
    assert not output.exists();output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(ref(output)))

if __name__=='__main__':main()
