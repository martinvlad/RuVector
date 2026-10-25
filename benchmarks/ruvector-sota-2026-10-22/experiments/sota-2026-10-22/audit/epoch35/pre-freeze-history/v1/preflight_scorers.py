"""Pure authored fixtures only; never evaluate/bind, corpus or model execution."""
import ast,base64,copy,hashlib,json,math,struct,tempfile
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import data_common as D
import evidence_audit as E
import group_audit as G
import model_audit as A
import nli_metrics as M
import phase_audit as P
import query_audit as Q
import decision_proof_audit as F
import score_engineering as S
import policy_lineage_audit as L
checks=[]
def req(value):
    if not value:raise AssertionError('Authored fixture expectation failed')
def rejects(call):
    try:call()
    except (ValueError,KeyError,TypeError,AssertionError):return
    raise AssertionError('Invalid authored fixture accepted')
def test(name,call):call();checks.append({'name':name,'passed':True})
def reader(logits):
    z=[math.exp(v-max(logits))for v in logits];p=[v/math.fsum(z)for v in z];w=max(range(3),key=lambda i:logits[i])
    return {'raw_logits_E_N_C':logits,'probabilities_E_N_C':p,'probabilities_E_C_N':[p[0],p[2],p[1]],
        'actual_logits_shape':[1,3],'native_label_index':w,'native_typed_argmax':['Entailment','NotMentioned','Contradiction'][w],
        'native_binary_probabilities_Yes_No':{'Yes':p[0],'No':p[1]+p[2]},'native_binary_decision':'Yes'if p[0]>.5 else'No',
        'temperature':1.,'calibrated':False,'semantic_decision_override':False,'model_weights_sha256':A.WEIGHT_SHA,
        'pair_tokens':8,'full_pair_tokens':8,'max_pair_tokens':512,'hidden_truncation':False,
        'premise_sha256':D.digest('unit premise'.encode()),'hypothesis_sha256':D.digest('unit claim'.encode()),
        'native_pair_input_ids_sha256':'a'*64,'forward_seconds':.01,'reader_seconds':.02}
def rcheck(r):return M.reader_check(r,'unit premise','unit claim',8)
for index,label in enumerate(['entailment','not_mentioned','contradiction']):
    def f(index=index,label=label):
        logits=[-10.]*3;logits[index]=10.;req(rcheck(reader(logits))['prediction']==label)
    test('native_ENC_'+label,f)
test('stable_large_logits',lambda:req(rcheck(reader([10000.,9999.,9998.]))['prediction']=='entailment'))
test('tie_E_first',lambda:req(rcheck(reader([1.,1.,1.]))['prediction']=='entailment'))
test('tie_N_before_C',lambda:req(rcheck(reader([0.,1.,1.]))['prediction']=='not_mentioned'))
test('binary_half_is_No',lambda:req(rcheck(reader([0.,-math.log(2),-math.log(2)]))['binary_prediction']=='No'))
def mutate_reader(key,value):
    r=reader([2.,1.,0.]);r[key]=value;rejects(lambda:rcheck(r))
for key,value in [('probabilities_E_C_N',[.2,.3,.5]),('hidden_truncation',True),('model_weights_sha256','0'*64),
                  ('semantic_decision_override',True),('raw_logits_E_N_C',[float('nan'),0.,0.]),('native_label_index',2),
                  ('temperature',2.),('reader_seconds',-.1),('full_pair_tokens',9)]:
    test('reject_reader_'+key,lambda key=key,value=value:mutate_reader(key,value))
def fixture(native_wrong=False):
    rows=[];labels={}
    for i,(case_id,did,hid)in enumerate(D.expected('engineering')):
        label=D.CLASSES[i//4];p={c:.8 if c==label else.1 for c in D.CLASSES}
        readers={n:{'probabilities':dict(p),'prediction':label}for n in S.ARMS.values()}
        if native_wrong and i==0:readers['native']['prediction']='contradiction'
        rows.append({'id':case_id,'document_id':did,'readers':readers});labels[case_id]={v:k for k,v in D.GOLD_NAMES.items()}[label]
    return rows,{'expected_labels':labels}
def good_metrics():
    passed,scores,gates=S.engineering_replay(*fixture());req(passed and all(gates.values()))
    for value in scores.values():
        req(value['n']==value['correct']==12 and abs(value['Brier']-.06)<1e-12
            and abs(value['NLL_clipped_1e-12']+math.log(.8))<1e-12
            and value['NLL_clip_count']==0 and value['unclipped_NLL_finite']
            and all(v=={'n':4,'correct':4}for v in value['by_class'].values()))
test('manual_12way_threeclass_proper_scores',good_metrics)
test('native11_refuses_engineering',lambda:req(S.engineering_replay(*fixture(True))[0]is False))
def worse_proper(key):
    _,scores,_=S.engineering_replay(*fixture());scores['lexical'][key]-=1e-4
    req(not M.engineering_gates(scores)['lexical:'+('Brier_nonincrease'if key=='Brier'else'NLL_nonincrease')])
test('perfect_accuracy_but_Brier_worse_rejected',lambda:worse_proper('Brier'))
test('perfect_accuracy_but_NLL_worse_rejected',lambda:worse_proper('NLL_clipped_1e-12'))
def missingclass():
    rows,gate=fixture();first=next(iter(gate['expected_labels']));gate['expected_labels'][first]='Contradiction';rejects(lambda:S.engineering_replay(rows,gate))
test('unbalanced_authored_label_rejected',missingclass)
def unknownid():
    rows,gate=fixture();gate['expected_labels']['foreign-case']='Entailment';rejects(lambda:S.engineering_replay(rows,gate))
test('extra_foreign_or_exposed_identity_rejected',unknownid)
def balanced_permutation():
    rows,gate=fixture();ids=list(gate['expected_labels']);gate['expected_labels'][ids[0]],gate['expected_labels'][ids[4]]=gate['expected_labels'][ids[4]],gate['expected_labels'][ids[0]]
    rejects(lambda:S.engineering_replay(rows,gate))
test('balanced_permutation_of_joined_labels_rejected',balanced_permutation)
def clipping():
    rows,_=fixture()
    for row in rows:
        row['gold']='entailment';row['readers']['native']={'probabilities':{'entailment':0.,'contradiction':1.,'not_mentioned':0.},'prediction':'contradiction'}
    m=M.metrics(rows,'native',12);req(m['NLL_clip_count']==12 and m['unclipped_NLL_finite']is False
        and abs(m['NLL_clipped_1e-12']+math.log(1e-12))<1e-12 and m['Brier']==2.)
test('zero_probability_clipping_retains_unclipped_nonfiniteness',clipping)
test('matched12_authored_source_clusters',lambda:req(M.paired_differences(S.engineering_replay(*fixture())[1])['lexical']['authored_source_clusters']==12))
def block(value=1.):
    b=struct.pack('<384f',value,*([0.]*383));return {'encoding':'base64','dtype':'float32le','shape':[1,384],'bytes':1536,'sha256':D.digest(b),'data_base64':base64.b64encode(b).decode()}
test('lossless_normalized_f32',lambda:req(E.block_digests(block())==[block()['sha256']]))
for name,value in [('nonfinite',float('nan')),('unnormalized',2.)]:test(name+'_vector_rejected',lambda value=value:rejects(lambda:E.block_digests(block(value))))
def badbase64():
    b=block();b['data_base64']+='\n';rejects(lambda:E.block_digests(b))
test('noncanonical_base64_rejected',badbase64)
test('unsafe_absolute_pin_rejected',lambda:rejects(lambda:P.checked(Path('/tmp'),{'path':'/etc/passwd','bytes':0,'sha256':'0'*64})))
test('unsafe_parent_pin_rejected',lambda:rejects(lambda:P.checked(Path('/tmp'),{'path':'../etc/passwd','bytes':0,'sha256':'0'*64})))
test('duplicate_json_rejected',lambda:rejects(lambda:D.unique_object([('x',1),('x',2)])))
def hybrid(lexical,native,units):
    anchor=lexical[0];different=[i for i in native if units[i]['group_id']!=units[anchor]['group_id']]
    complement=different[0]if different else None;prefix=[anchor]+([]if complement is None else[complement]);ranking=(prefix+[i for i in native if i not in prefix])[:min(40,len(units))]
    receipt={'policy':Q.POLICY,'lexical_anchor_unit_id':anchor,'lexical_anchor_group_id':units[anchor]['group_id'],
        'native_complement_unit_id':complement,'native_complement_group_id':None if complement is None else units[complement]['group_id'],
        'single_group_degenerate':len({u['group_id']for u in units})==1,'hybrid_ranking':ranking}
    return Q.hybrid_check(lexical,native,units,receipt)
test('same_original_native_distinct_group_complement',lambda:req(hybrid([0,1,2],[1,0,2],[{'group_id':0},{'group_id':0},{'group_id':1}])[0]==[0,2,1]))
test('single_group_degenerate_permitted',lambda:req(hybrid([0,1],[1,0],[{'group_id':0},{'group_id':0}])[1]['single_group_degenerate']))
test('multigroup_missing_native_complement_fails_closed',lambda:rejects(lambda:hybrid(list(range(41)),list(range(40)),[{'group_id':0}for i in range(40)]+[{'group_id':1}])))
def disabled_decision(override=False):
    r=reader([2.,1.,0.]);p=r['probabilities_E_C_N'];decision={'schema_version':1,'epoch':35,'raw_probabilities_E_C_N':p,
        'raw_typed_argmax':'Entailment','final_probabilities_E_C_N':p,'final_typed_argmax':'Entailment','policy':F.POLICY,
        'certificate':None,'fallback_reason':'proof_disabled_for_ALL_ROLES','semantic_decision_override':override}
    return F.decision_check(decision,r,rcheck(r),'unit premise','unit premise','unit claim',[[0,12]],False,'engineering')
test('final_forecasts_equal_rawT1',lambda:req(disabled_decision()[1]['prediction_changed']is False))
test('semantic_override_rejected_even_authored',lambda:rejects(lambda:disabled_decision(True)))
test('benchmark_role_identity_forbidden',lambda:rejects(lambda:D.expected('dev')))
test('p50_p95_interpolation',lambda:req(S.quantile([0.,1.,2.,3.],.5)==1.5 and abs(S.quantile([0.,1.,2.,3.],.95)-2.85)<1e-12))
test('nonfinite_timing_rejected',lambda:rejects(lambda:S.quantile([float('nan')],.5)))
test('Decimal_cash_threshold',lambda:req(Decimal('2.75')>=Decimal('2.50')))
test('Fraction_one_quarter',lambda:req(Fraction(18,72)==Fraction(1,4)))
test('Decimal_unit_inclusive_boundary',lambda:req(Decimal('.075')*Decimal('1000')==Decimal('75')))
test('exact_signed_cash_flow',lambda:req(Fraction(210)-Fraction(335)==Fraction(-125)))
test('strict_ratio_equality_breach',lambda:req(not(Fraction(30,50)<Fraction(3,5))))
test('missing_denominator_two_models',lambda:req(Fraction(8,400)==Fraction(2,100)and Fraction(8,800)!=Fraction(2,100)))
test('metadata_epoch_normalization_only_named_dictkey',lambda:req(ast.dump(L.MetadataEpoch().visit(ast.parse("{'epoch':35,'threshold':35}")),include_attributes=False)==ast.dump(ast.parse("{'epoch':0,'threshold':35}"),include_attributes=False)))
report={'schema_version':1,'epoch':35,'checks_passed':True,'checks':checks,
    'counts':{'tests':len(checks),'benchmark_records_or_labels_read':0,'authored_oracle_file_traversals':0,
        'model_native_tokenizer_imports_or_calls':0,'actual_scientific_evaluate_or_bind':0},
    'scope':'Pure authored unit probabilities, vectors, source contracts and rational arithmetic. Does not exercise a model, native library, current48 outputs, closure or actual engineering admission.'}
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args();D.write_new(args.output,report)
    print(json.dumps({'checks_passed':True,'tests':len(checks)}))
