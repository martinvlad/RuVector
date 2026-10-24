"""Focused standard-library numerical and no-gold-on-failure source tests.

Authored unit values only. No corpus parse, real choices, model/tokenizer/native
imports, weight payload I/O, or scientific evaluate/bind invocation.
"""
import base64,copy,hashlib,importlib.util,json,math,struct,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import nli_metrics as M
import model_audit as A
import evidence_audit as E
import phase_audit as P
import score_dev as S
from data_common import CLASSES,require
checks=[]
def test(name,func):
    func();checks.append({'name':name,'passed':True})
def req(value):
    if not value:raise AssertionError('Unit fixture expectation failed')
def rejects(func):
    try:func()
    except (ValueError,KeyError,TypeError,AssertionError):return
    raise AssertionError('Invalid fixture accepted')
def reader(logits):
    z=[math.exp(v-max(logits))for v in logits];p=[v/math.fsum(z)for v in z];w=max(range(3),key=lambda i:logits[i])
    return {'raw_logits_E_N_C':logits,'probabilities_E_N_C':p,'probabilities_E_C_N':[p[0],p[2],p[1]],
      'actual_logits_shape':[1,3],'native_label_index':w,'native_typed_argmax':['Entailment','NotMentioned','Contradiction'][w],
      'native_binary_probabilities_Yes_No':{'Yes':p[0],'No':p[1]+p[2]},'native_binary_decision':'Yes'if p[0]>.5 else'No',
      'temperature':1.0,'calibrated':False,'semantic_decision_override':False,'model_weights_sha256':A.WEIGHT_SHA,
      'pair_tokens':8,'full_pair_tokens':8,'max_pair_tokens':512,'hidden_truncation':False,
      'premise_sha256':hashlib.sha256('unit premise'.encode()).hexdigest(),'hypothesis_sha256':hashlib.sha256('unit claim'.encode()).hexdigest(),
      'native_pair_input_ids_sha256':'a'*64,'forward_seconds':.01,'reader_seconds':.02}
def rcheck(r):return M.reader_check(r,'unit premise','unit claim',8)
for i,c in enumerate(['entailment','not_mentioned','contradiction']):
    def f(i=i,c=c):
        x=[-10.,-10.,-10.];x[i]=10.;req(rcheck(reader(x))['prediction']==c)
    test('native_ENC_class_'+c,f)
test('stable_huge_logits',lambda:req(rcheck(reader([10000.,9999.,9998.]))['prediction']=='entailment'))
test('native_tie_first_E',lambda:req(rcheck(reader([1.,1.,1.]))['prediction']=='entailment'))
test('native_N_C_tie_first_N',lambda:req(rcheck(reader([0.,1.,1.]))['prediction']=='not_mentioned'))
test('binary_exact_half_No',lambda:req(rcheck(reader([0.,-math.log(2),-math.log(2)]))['binary_prediction']=='No'))
def mutation(name,value):
    r=reader([2.,1.,0.]);r[name]=value;rejects(lambda:rcheck(r))
test('wrong_ECN_permutation_rejected',lambda:mutation('probabilities_E_C_N',[.2,.3,.5]))
test('hidden_truncation_rejected',lambda:mutation('hidden_truncation',True))
test('head_checkpoint_substitution_rejected',lambda:mutation('model_weights_sha256','0'*64))
test('semantic_override_rejected',lambda:mutation('semantic_decision_override',True))
test('nonfinite_native_logit_rejected',lambda:mutation('raw_logits_E_N_C',[float('nan'),0.,0.]))
test('wrong_native_argmax_rejected',lambda:mutation('native_label_index',2))
def row(i,gold,wrong=False):
    p={c:(.8 if c==gold else .1)for c in CLASSES};pred=CLASSES[(CLASSES.index(gold)+1)%3]if wrong else gold
    r={'probabilities':p,'prediction':pred};return {'id':'unit:'+str(i),'document_id':i//3,'gold':gold,'readers':{k:dict(r)for k in ['native','lexical','positional']}}
rows=[row(i,CLASSES[i%3])for i in range(24)]
def proper():
    m=M.metrics(rows,'native');req(m['correct']==24 and abs(m['Brier']-.06)<1e-12 and abs(m['NLL_clipped_1e-12']+math.log(.8))<1e-12 and all(x['n']==8 for x in m['by_class'].values()))
test('manual_threeway_proper_scores',proper)
def missing():
    rr=[row(i,'entailment')for i in range(24)];m=M.metrics(rr,'native');req(m['by_class']['contradiction']['n']==0);req(M.diagnostic_gates({k:copy.deepcopy(m)for k in ['native','lexical','positional']})['every_gold_class_present']is False)
test('missing_class_rejects_without_fake_denominator',missing)
def gate_fixture():
    m=M.metrics(rows,'native');a={k:copy.deepcopy(m)for k in ['native','lexical','positional']}
    for c in ['lexical','positional']:a[c]['correct']=22;a[c]['Brier']+=.1;a[c]['NLL_clipped_1e-12']+=.1
    return a
test('strict_plus2_and_proper_gate_pass',lambda:req(all(M.diagnostic_gates(gate_fixture()).values())))
def plus1():
    a=gate_fixture();a['lexical']['correct']=23;req(M.diagnostic_gates(a)['lexical:correct_gain_at_least2']is False)
test('plus1_gain_rejected',plus1)
def worse():
    a=gate_fixture();a['lexical']['NLL_clipped_1e-12']=a['native']['NLL_clipped_1e-12']-1e-4;req(M.diagnostic_gates(a)['lexical:NLL_nonincrease']is False)
test('proper_worsening_rejected',worse)
def cfail():
    a=gate_fixture();a['native']['by_class']['contradiction']['correct']=0;req(M.diagnostic_gates(a)['native_one_correct_per_class']is False)
test('contradiction_zero_rejected',cfail)
test('eight_cluster_pairing_retained',lambda:req(M.paired_differences({k:M.metrics(rows,k)for k in ['native','lexical','positional']})['lexical']['n_document_clusters']==8))
def eng_fixture(native_wrong=False,control_wrong=False):
    rs=[];labels={}
    for i,g in enumerate(['entailment']*2+['contradiction']*2+['not_mentioned']*2,1):
        rr=row(i,g);rr['id']=f'epoch32:cc0:engineering:{i}';rr['document_id']=-32000-i
        for n in rr['readers']:
            if(n=='native'and native_wrong and i==1)or(n!='native'and control_wrong):rr['readers'][n]['prediction']=CLASSES[(CLASSES.index(g)+1)%3]
        rs.append(rr);labels[rr['id']]={'entailment':'Entailment','contradiction':'Contradiction','not_mentioned':'NotMentioned'}[g]
    return rs,{'schema_version':1,'epoch':32,'role':'engineering','expected_labels':labels}
test('engineering_native6_controls_descriptive',lambda:req(S.engineering_replay(*eng_fixture(control_wrong=True))[0]is True))
test('engineering_native5_refuses',lambda:req(S.engineering_replay(*eng_fixture(native_wrong=True))[0]is False))
def block():
    b=struct.pack('<384f',1.,*([0.]*383));return {'encoding':'base64','dtype':'float32le','shape':[1,384],'bytes':1536,'sha256':hashlib.sha256(b).hexdigest(),'data_base64':base64.b64encode(b).decode()}
test('lossless_f32_vector_digest',lambda:req(E.block_digests(block())==[block()['sha256']]))
def badblock():
    x=block();x['data_base64']+='\n';rejects(lambda:E.block_digests(x))
test('noncanonical_base64_rejected',badblock)
def nanblock():
    x=block();b=struct.pack('<384f',float('nan'),*([0.]*383));x.update(sha256=hashlib.sha256(b).hexdigest(),data_base64=base64.b64encode(b).decode());rejects(lambda:E.block_digests(x))
test('nonfinite_source_vector_rejected',nanblock)
test('unsafe_absolute_evidence_rejected',lambda:rejects(lambda:P.checked(HERE,{'path':'/etc/passwd','bytes':0,'sha256':'0'*64})))
test('evidence_parent_escape_rejected',lambda:rejects(lambda:P.checked(HERE,{'path':'../outside','bytes':0,'sha256':'0'*64})))
def not_closed_no_gold():
    old={name:getattr(S,name)for name in ['source_checks','publisher','pretrained_source','read']};opens=[]
    class Pub:
        @staticmethod
        def phase_evidence(*args):return {'raw':None,'execution':None,'raw_value':None}
        @staticmethod
        def aggregate_actual(value):return {'worker_attempts':1,'operation_counts_complete':False,'native_corpus_batches':None}
        @staticmethod
        def phase_completed(value):return False
    plan={'source_freeze_path':'data-source-freeze-v2.json','pretrained_model_source':P.ref(HERE,HERE/'selection.json')}
    try:
        S.source_checks=lambda *args:(plan,{'unit_fixture':True});S.publisher=lambda *args:Pub;S.pretrained_source=lambda *args:{}
        S.read=lambda *args:(_ for _ in ()).throw(AssertionError('Unclosed output attempted source/gold read'))
        with tempfile.TemporaryDirectory(prefix='unit-failure-',dir=HERE)as td:
            result=S.evaluate(SimpleNamespace(project=str(HERE),plan=str(HERE/'protocol.json'),source='/ABSENT_ORIGINAL_SOURCE_SENTINEL',output=str(Path(td)/'report.json')))
            req(result['checks_passed']is False and result['metrics']is None and result['annotation_choices_accessed']==0 and result['original_annotated_source_json_parsed']is False)
    finally:
        for name,value in old.items():setattr(S,name,value)
test('uncaptured_unclosed_worker_never_reads_gold',not_closed_no_gold)
def refusal_fixture():
    return {'execution_value':{'status':'WORKER_ENGINEERING_REJECTED','exit_code':2,'source_plan_unchanged':True,'raw_closure_invariants':{'unit':True}},
        'actual':{'verified_worker_starts':1,'uncertain_start':False,'owned_live_processes_closed':True,'operation_counts_complete':True,'errors':0,'wall_seconds_including_init_cleanup':20.},
        'dispatch_attempt_value':{'verified_launcher_start':True,'uncertain_launcher_start':False}}
test('closed_expected_engineering_exit2_integrity',lambda:req(S.refusal_closed_integrity(refusal_fixture())is True))
def refusal_mutate(part,key,value):
    x=refusal_fixture();x[part][key]=value;rejects(lambda:S.refusal_closed_integrity(x))
test('engineering_refusal_uncertain_start_rejected',lambda:refusal_mutate('actual','uncertain_start',True))
test('engineering_refusal_checkpoint_incomplete_rejected',lambda:refusal_mutate('actual','operation_counts_complete',False))
test('engineering_refusal_wrong_exit_rejected',lambda:refusal_mutate('execution_value','exit_code',0))
def model_fixture(stored=True):
    data=435064835*4+(4096 if stored else 0);head={k:{'shape':v,'dtype':'float32','sha256':'a'*64}for k,v in A.HEAD_SHAPES.items()}
    state={'unchanged':True,'classifier_manifest':head,'scope':'Unit storage/version+head hash fixture'}
    r={'model_class':'DebertaV2ForSequenceClassification','learned_parameters':435064835,'loading_missing_keys':[],'loading_unexpected_keys':[],'CPU_FP32':True,'meta_tensors_remaining':0,'safe_mmap_meta_assign':True,'weights_sha256':A.WEIGHT_SHA,'no_training_or_classifier_reinitialization':True,'actual_model_warmup_forwards':0,'attention':'eager','tokenizer_class':'DebertaV2TokenizerFast','pair_special_tokens':3,'backend_before_sha256':'a'*64,'backend_after_sha256':'b'*64,'nonpersistent_buffers':['deberta.embeddings.position_ids'],'position_ids_buffer_source':A.STORED if stored else A.DERIVED,'data_bytes':data,'header_bytes':A.WEIGHT_BYTES-data-8,'header_sha256':'c'*64,'tensor_count':400,'initialization_seconds':1.,'classifier_manifest':head}
    return {'model_initialization':r,'model_state_unchanged':state,'corpora':{'engineering':{'model_state_unchanged':state},'dev':None}}
test('strict_model_stored_position_buffer_metadata',lambda:req(A.audit_model(model_fixture())['learned_parameters']==435064835))
test('only_deterministic_stock_buffer_conditional',lambda:req(A.audit_model(model_fixture(False))['buffer_source']==A.DERIVED))
def model_bad(key,value):
    r=model_fixture();r['model_initialization'][key]=value;rejects(lambda:A.audit_model(r))
test('model_missing_learned_keys_rejected',lambda:model_bad('loading_missing_keys',['classifier.weight']))
test('model_remaining_meta_rejected',lambda:model_bad('meta_tensors_remaining',1))
test('model_unexplained_buffer_rejected',lambda:model_bad('nonpersistent_buffers',['other']))
result={'schema_version':1,'epoch':32,'checks_passed':True,'checks':checks,'counts':{'tests':len(checks),'original_corpus_parses':0,'actual_annotation_choices_or_evidence':0,'model_tokenizer_native_imports_or_calls':0,'weight_payload_decodes':0,'actual_science_evaluate_or_bind':0},'scope':'Pure authored unit logits/probabilities/vectors and one mocked unclosed-worker control-flow fixture. No measured outputs or source choices used.'}
p=HERE/'scorer-preflight-v3.json'
with p.open('x')as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps({'checks_passed':True,'tests':len(checks)}))
