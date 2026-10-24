"""Numerical/structural regression probes. No real model or source choice access."""
import argparse
import base64
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import time
from unittest.mock import patch
import artifact_audit as A
import nli_metrics as N
import evidence_audit as E
import phase_audit as P
from data_common import expected,write_new

def run(output):
    tests=[];started=time.perf_counter()
    def eq(a,b):
        if a!=b:raise AssertionError((a,b))
    def reject(fn):
        try:fn()
        except (ValueError,KeyError,TypeError,IndexError):return
        raise AssertionError('Expected rejection')
    def test(name,fn):fn();tests.append({'name':name,'passed':True})
    test('independent complete stockBART frozenarchitecture',lambda:eq((len(A.frozen_shapes()),sum(math.prod(s)for s in A.frozen_shapes().values())),(511,406291456)))
    text,hyp='Numerical unit premise.','Numerical unit claim.'
    def reader(logits):
        exp=[math.exp(x-max(logits))for x in logits];p=[x/sum(exp)for x in exp];p=[p[2],p[0],p[1]]
        return {'raw_logits_C_N_E':logits,'probabilities_E_C_N':p,'actual_logits_shape':[1,3],
                'typed_prediction':N.NATIVE_TYPED[max(range(3),key=lambda i:logits[i])],
                'binary_yes_probability':p[0],'binary_no_probability':p[1]+p[2],
                'binary_prediction':'Yes'if p[0]>0.5 else'No','pair_tokens':8,'full_pair_tokens':8,'max_pair_tokens':512,
                'premise_truncated':False,'hypothesis_truncated':False,'native_pair_input_ids_sha256':'1'*64,
                'premise_sha256':hashlib.sha256(text.encode()).hexdigest(),'hypothesis_sha256':hashlib.sha256(hyp.encode()).hexdigest()}
    test('genuine neutral class retained',lambda:eq(N.reader_check(reader([0.,3.,0.]),text,hyp,8)['prediction'],'not_mentioned'))
    test('native threeway tie is Contradiction first',lambda:eq(N.reader_check(reader([0.,0.,0.]),text,hyp,8)['prediction'],'contradiction'))
    test('exact half binary forecast is No',lambda:eq(N.reader_check(reader([0.,0.,math.log(2)]),text,hyp,8)['binary_prediction'],'No'))
    wrong=reader([0.,3.,0.]);wrong['probabilities_E_C_N']=[0.5,0.5,0.0]
    test('neutral dropping renormalization rejected',lambda:reject(lambda:N.reader_check(wrong,text,hyp,8)))
    test('over512 true pair rejected',lambda:reject(lambda:N.reader_check(reader([0.,0.,0.]),text,hyp,513)))
    rows=[]
    for i in range(24):
        gold=N.CLASSES[i%3];p={c:0.01 for c in N.CLASSES};p[gold]=0.98
        good={'probabilities':p,'prediction':gold,'binary_yes_probability':p['entailment'],'binary_prediction':'Yes'if p['entailment']>0.5 else'No'}
        rows.append({'id':str(i),'document_id':i//3,'gold':gold,'readers':{n:copy.deepcopy(good)for n in ['adapted_native','original_native','adapted_lexical','adapted_positional']}})
    for name in ['original_native','adapted_lexical','adapted_positional']:
        for i in [0,1]:
            old=rows[i]['readers'][name];other=next(c for c in N.CLASSES if c!=rows[i]['gold']);old['probabilities']={c:(0.98 if c==other else 0.01)for c in N.CLASSES};old['prediction']=other
    result={name:N.metrics(rows,name)for name in rows[0]['readers']}
    test('independent threeclass Brier for confident correct forecasts',lambda:eq(round(result['adapted_native']['Brier'],6),0.0006))
    test('all frozen diagnostic gains require genuine control errors',lambda:eq(all(N.diagnostic_gates(result).values()),True))
    ceiling=copy.deepcopy(result);ceiling['original_native']=copy.deepcopy(ceiling['adapted_native'])
    test('C ceiling cannot silently relax strict gain',lambda:eq(N.diagnostic_gates(ceiling)['adaptation_C_correct_gain_at_least1'],False))
    rawvec=struct.pack('<384f',1.,*([0.]*383));block={'encoding':'base64','dtype':'float32le','shape':[1,384],
        'bytes':1536,'sha256':hashlib.sha256(rawvec).hexdigest(),'data_base64':base64.b64encode(rawvec).decode()}
    test('lossless native source vector digest replay',lambda:eq(E.block_digests(block),[hashlib.sha256(rawvec).hexdigest()]))
    changed=copy.deepcopy(block);changed['sha256']='0'*64
    test('native source-vector tamper rejected',lambda:reject(lambda:E.block_digests(changed)))
    bad=copy.deepcopy(block);v=struct.pack('<384f',float('nan'),*([0.]*383));bad.update(sha256=hashlib.sha256(v).hexdigest(),data_base64=base64.b64encode(v).decode())
    test('nonfinite native source-vector rejected',lambda:reject(lambda:E.block_digests(bad)))
    root=Path('/tmp/ruvector-sota-2026-10-22/epoch30-9f13c9bb6e47/project')
    row={'event':'socket.bind','allowed':True,'family':10,'socket_type':1,'protocol':0,'address':"('::1', 0)",
         'source_provenance':{'path':str(root/'retrieval/.venv/lib/python3.12/site-packages/urllib3/util/connection.py'),
           'sha256':'2633bbdb69731e5ccb5cf4e4afd65605d86c7979cc5633126f50c92d5ad74a74','function':'_has_ipv6','line':127},
         'stack':['synthetic-source-only-stack'],'bind_outcome':'SUCCESS','close_outcome':'SUCCESS',
         'file_descriptor_after_close':-1,'monotonic_seconds':1.,'close_monotonic_seconds':2.}
    policy={'counters':{'Python_literal_loopback_capability_binds_allowed':1},'Python_network_events':[row],
            'Python_network_violations':[],'Node_guard_events':[{'Node_network_operations_attempted':0}]}
    test('capabilitybind source-wire outcome accepted with no actualsocketprobe',lambda:eq(P.network_checks(root,policy)['allowed_capability_binds'],1))
    unclosed=copy.deepcopy(policy);unclosed['Python_network_events'][0]['close_outcome']='PENDING'
    test('capabilitybind unclosedreceipt rejected',lambda:reject(lambda:P.network_checks(root,unclosed)))
    extra=copy.deepcopy(policy);extra['counters']['Python_literal_loopback_capability_binds_allowed']=2
    test('capabilitybind allowance cannot expand',lambda:reject(lambda:P.network_checks(root,extra)))
    # Synthetic learned bytes and hash-only backbone manifests: no original
    # weights are read and no ML library is imported to construct this fixture.
    tensors=[];initial=[];changes=[];heads=[]
    for name,shape in A.LEARNED:
        count=math.prod(shape);payload=struct.pack('<f',0.01)*count
        r={'name':name,'shape':shape,'dtype':'float32le','numel':count,'bytes':count*4,'sha256':A.sha(payload)}
        tensors.append({**r,'data_base64':base64.b64encode(payload).decode()})
        old={**r,'sha256':A.sha(bytes(count*4))if name.endswith('.lora_B')or name in dict(A.HEAD)else A.sha(('initial'+name).encode())}
        initial.append(old);changes.append({'name':name,'before_sha256':old['sha256'],'after_sha256':r['sha256'],'changed':True})
        if name in dict(A.HEAD):heads.append(old)
    frozen=[]
    for name,shape in sorted(A.frozen_shapes().items()):
        h=A.sha(name.encode());frozen.append({'name':name,'shape':shape,'dtype':'float32le','numel':math.prod(shape),
            'bytes':math.prod(shape)*4,'sha256_before':h,'sha256_after':h})
    fman=[{**{k:r[k]for k in ['name','shape','dtype','numel','bytes']},'sha256':r['sha256_before']}for r in frozen]
    algorithm={'seed':30030,'module_order':A.MODULES,'lora':{'rank':4,'alpha':8,'scale':2.,'dropout':0,'global_seed_reset_immediately_before_injection':True},
        'optimizer':{'name':'AdamW','learning_rate':1e-4,'weight_decay':0.01,'betas':[0.9,0.999],'epsilon':1e-8,'foreach':False,'fused':False,'amsgrad':False,'maximize':False,'capturable':False,'differentiable':False},
        'train_case_order':[r[0]for r in expected('train')],'existing_pretrained_head_parameters':[n for n,_ in A.HEAD],
        'trainable_parameters':1085443,'frozen_pretrained_parameters':406291456,'gradient_clip_global_norm':1.,'attention':'sdpa',
        'use_cache':False,'max_true_pair_tokens':512,'batch_size':1,'epochs':1,'training_steps':24,'temperature':1.,'canonical_probability_permutation':[2,0,1],
        'no_early_stopping_checkpoint_selection_calibration_or_retry':True}
    value={'schema_version':1,'epoch':30,'kind':A.KIND,'codec':'epoch30-bart-crossattn-r4-f32le-v1',
        'base_model':{'repository':'facebook/bart-large-mnli','revision':'d7645e127eaf1aefc7862fd59a17a5aa8558b8ce','weights_file':'pytorch_model.bin',
          'weights_bytes':1629486723,'weights_sha256':A.BASE_SHA,'pretrained_parameter_count':407344131},
        'algorithm':algorithm,'source_plan_sha256':'a'*64,'training_inputs_sha256':'b'*64,'training_steps':24,'trainable_parameter_count':1085443,
        'tensors':tensors,'original_head_manifest':heads,'initial_trainable_manifest':initial,'trainable_changes':changes,
        'frozen_pretrained_proof':{'parameter_count':406291456,'tensor_count':511,'before_after':frozen,'all_bit_unchanged':True,
           'aggregate_before_sha256':A.canonical_sha(fman),'aggregate_after_sha256':A.canonical_sha(fman)},
        'effective_lora_delta':[{'module':m,'shape':[1024,1024],'scale':2.,'sha256':'c'*64,'l2_norm':1.,'max_abs':0.1,
            'nonzero_entries':1048576,'B_nonzero_gradient_steps':[1],'max_B_gradient_l2':0.1}for m in A.MODULES]}
    def audit(v):
        with patch.object(A,'read',return_value=v),patch.object(A,'identity',return_value={'path':'synthetic','bytes':6000000,'sha256':'d'*64}):
            return A.audit_artifact(Path('/synthetic'),'a'*64,'b'*64)
    test('full12tensor511frozen source-free positive artifact audit',lambda:eq(all(audit(value)['mechanism_flags'].values()),True))
    tamper=copy.deepcopy(value);tamper['tensors'][0]['sha256']='0'*64
    test('learned payload hash tamper rejected',lambda:reject(lambda:audit(tamper)))
    missing=copy.deepcopy(value);missing['frozen_pretrained_proof']['before_after'].pop()
    test('missing frozen backbone tensor rejected',lambda:reject(lambda:audit(missing)))
    mutate=copy.deepcopy(value);mutate['frozen_pretrained_proof']['before_after'][0]['sha256_after']='0'*64
    test('changed frozen pretrained tensor rejected',lambda:reject(lambda:audit(mutate)))
    wronghead=copy.deepcopy(value);wronghead['original_head_manifest'][0]={**wronghead['original_head_manifest'][0],'sha256':'f'*64}
    test('classifier reinitialization rejected',lambda:reject(lambda:audit(wronghead)))
    nograd=copy.deepcopy(value);nograd['effective_lora_delta'][0]['B_nonzero_gradient_steps']=[]
    test('missing actual B gradient mechanism rejected',lambda:reject(lambda:audit(nograd)))
    seed=copy.deepcopy(value);seed['algorithm']['seed']=30031
    test('unfrozen optimizer seed rejected',lambda:reject(lambda:audit(seed)))
    report={'schema_version':1,'epoch':30,'kind':A.KIND,'status':'PASS_STDLIB_SCORER_PROOF_AND_NUMERICAL_PREFLIGHT',
        'check_count':len(tests),'checks':tests,'seconds':time.perf_counter()-started,
        'real_model_native_tokenizer_or_original_weights_loads':0,'real_source_choice_or_evidence_reads':0,
        'synthetic_scope':'Only numerical/unit parameter bytes and hash manifests, never authored benchmark inference',
        'scorer_sources':{n:hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest()for n in ['artifact_audit.py','nli_metrics.py','phase_audit.py','evidence_audit.py','score_train.py','score_dev.py']}}
    write_new(output,report);print(json.dumps({'status':report['status'],'checks':len(tests)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
