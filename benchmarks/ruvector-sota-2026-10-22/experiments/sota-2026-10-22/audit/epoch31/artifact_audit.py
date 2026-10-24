"""Independent learned-parameter evidence replay using only the standard library.

No original weights/model import or TRAIN choice access. Parameter bytes are
decoded as fixed float32 evidence, never executable pickle or model objects.
"""
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from data_common import require, read, identity

# Archive validation retains the historical E30 identity and training order.
# Current E31 TRAIN is empty; this helper never opens a TRAIN source or bank.
HISTORICAL_TRAIN_IDS = [237,120,187,422,464,207,294,250]
def expected_cases(role):
    require(role == 'train', 'Only historical E30 TRAIN identity is defined')
    return [(f'original-contractnli:train:epoch30:train:{did}:{hid}',did,hid)
            for did in HISTORICAL_TRAIN_IDS for hid in ['nda-17','nda-7','nda-3']]

KIND = 'REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC'
BASE_SHA = 'ce253627f98f9db22af6a86efee6e905f001f7d8dc02dd14a8b4b4710c302b17'
MODULES = [f'model.decoder.layers.{i}.encoder_attn.{p}'
           for i in [10,11] for p in ['q_proj','v_proj']]
HEAD = [('classification_head.dense.weight',[1024,1024]),
        ('classification_head.dense.bias',[1024]),
        ('classification_head.out_proj.weight',[3,1024]),
        ('classification_head.out_proj.bias',[3])]
LEARNED = [(m+s,shape) for m in MODULES
           for s,shape in [('.lora_A',[4,1024]),('.lora_B',[1024,4])]] + HEAD

def sha(value):
    return hashlib.sha256(value).hexdigest()

def canonical_bytes(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def canonical_sha(value):
    return sha(canonical_bytes(value))

def hexsha(value):
    return type(value)is str and re.fullmatch('[0-9a-f]{64}',value)is not None

def frozen_shapes():
    result = {'model.shared.weight':[50265,1024],
              'model.encoder.embed_positions.weight':[1026,1024],
              'model.decoder.embed_positions.weight':[1026,1024]}
    for side in ['encoder','decoder']:
        for suffix in ['weight','bias']:
            result[f'model.{side}.layernorm_embedding.{suffix}']=[1024]
        for layer in range(12):
            prefix=f'model.{side}.layers.{layer}'
            for attention in (['self_attn']if side=='encoder'else['self_attn','encoder_attn']):
                for projection in ['k_proj','v_proj','q_proj','out_proj']:
                    result[f'{prefix}.{attention}.{projection}.weight']=[1024,1024]
                    result[f'{prefix}.{attention}.{projection}.bias']=[1024]
            norms=(['self_attn_layer_norm','final_layer_norm']if side=='encoder'
                   else['self_attn_layer_norm','encoder_attn_layer_norm','final_layer_norm'])
            for name in norms:
                for suffix in ['weight','bias']:result[f'{prefix}.{name}.{suffix}']=[1024]
            result[f'{prefix}.fc1.weight']=[4096,1024]
            result[f'{prefix}.fc1.bias']=[4096]
            result[f'{prefix}.fc2.weight']=[1024,4096]
            result[f'{prefix}.fc2.bias']=[1024]
    require(len(result)==511 and sum(math.prod(s)for s in result.values())==406291456,
            'Independent BART frozen architecture count changed')
    return result

def manifest(record,name,shape,sha_key='sha256'):
    require(record['name']==name and record['shape']==shape and record['dtype']=='float32le',
            'Parameter name/shape/dtype mismatch')
    require(type(record['numel'])is int and record['numel']==math.prod(shape)
            and type(record['bytes'])is int and record['bytes']==math.prod(shape)*4,
            'Parameter size mismatch')
    require(hexsha(record[sha_key]),'Invalid parameter digest')

def tensor(record,name,shape):
    require(set(record)=={'name','shape','dtype','numel','bytes','sha256','data_base64'},
            'Unexpected learned tensor fields')
    manifest(record,name,shape)
    require(type(record['data_base64'])is str,'Missing tensor base64')
    payload=base64.b64decode(record['data_base64'],validate=True)
    require(base64.b64encode(payload).decode()==record['data_base64'], 'Noncanonical tensor base64')
    require(len(payload)==record['bytes'] and sha(payload)==record['sha256'],'Learned tensor payload/hash mismatch')
    require(all(math.isfinite(v[0])for v in struct.iter_unpack('<f',payload)),'Nonfinite learned tensor')
    return payload

def algorithm_checks(a):
    require(a['seed']==30030 and a['module_order']==MODULES,'Fixed adapter seed/module order changed')
    for k,v in {'rank':4,'alpha':8,'scale':2.0,'dropout':0,
                'global_seed_reset_immediately_before_injection':True}.items():
        require(a['lora'][k]==v,'LoRA algorithm changed: '+k)
    expected={'name':'AdamW','learning_rate':1e-4,'weight_decay':0.01,'betas':[0.9,0.999],
              'epsilon':1e-8,'foreach':False,'fused':False,'amsgrad':False,'maximize':False,
              'capturable':False,'differentiable':False}
    require(a['optimizer']==expected,'Fixed AdamW configuration changed')
    require(a['train_case_order']==[r[0]for r in expected_cases('train')]
            and a['existing_pretrained_head_parameters']==[n for n,_ in HEAD],
            'Fixed TRAIN order or pretrained classifier parameter set changed')
    for k,v in {'trainable_parameters':1085443,'frozen_pretrained_parameters':406291456,
                'gradient_clip_global_norm':1.0,'attention':'sdpa','use_cache':False,
                'max_true_pair_tokens':512,'batch_size':1,'epochs':1,'training_steps':24,
                'temperature':1.0,'canonical_probability_permutation':[2,0,1],
                'no_early_stopping_checkpoint_selection_calibration_or_retry':True}.items():
        require(a[k]==v,'Fixed training algorithm changed: '+k)

def audit_artifact(path,plan_sha,inputs_sha):
    artifact=read(path)
    required={'schema_version','epoch','kind','codec','base_model','algorithm','source_plan_sha256',
              'training_inputs_sha256','training_steps','trainable_parameter_count','tensors',
              'original_head_manifest','initial_trainable_manifest','trainable_changes',
              'frozen_pretrained_proof','effective_lora_delta'}
    require(set(artifact)==required,'Unexpected learned artifact header fields')
    def finite_json(value):
        if type(value)is float:require(math.isfinite(value),'Nonfinite artifact JSON number')
        elif isinstance(value,dict):
            for child in value.values():finite_json(child)
        elif isinstance(value,list):
            for child in value:finite_json(child)
    finite_json(artifact)
    require(identity(path)['bytes']<=8*1024*1024,'Learned artifact exceeds transport cap')
    require(artifact['schema_version']==1 and artifact['epoch']==30 and artifact['kind']==KIND
            and artifact['codec']=='epoch30-bart-crossattn-r4-f32le-v1','Wrong learned artifact scope/codec')
    base=artifact['base_model']
    require(base=={'repository':'facebook/bart-large-mnli','revision':'d7645e127eaf1aefc7862fd59a17a5aa8558b8ce',
                  'weights_file':'pytorch_model.bin','weights_bytes':1629486723,
                  'weights_sha256':BASE_SHA,'pretrained_parameter_count':407344131},'Wrong original BART base')
    require(artifact['source_plan_sha256']==plan_sha and artifact['training_inputs_sha256']==inputs_sha,
            'Artifact source/input binding mismatch')
    require(artifact['training_steps']==24 and artifact['trainable_parameter_count']==1085443,
            'Partial or different training artifact')
    algorithm_checks(artifact['algorithm'])
    records=artifact['tensors'];require(len(records)==12,'Exactly12 learned tensors required')
    payloads={name:tensor(record,name,shape)for record,(name,shape)in zip(records,LEARNED)}
    require(sum(len(v)for v in payloads.values())==4341772,'Learned scalar byte closure failed')
    heads=artifact['original_head_manifest'];require(len(heads)==4,'Original head manifest incomplete')
    for record,(name,shape)in zip(heads,HEAD):manifest(record,name,shape)
    initial=artifact['initial_trainable_manifest'];changes=artifact['trainable_changes']
    require(len(initial)==len(changes)==12,'Initial/change manifest incomplete')
    for init,change,record,(name,shape)in zip(initial,changes,records,LEARNED):
        manifest(init,name,shape)
        require(change['name']==name and change['before_sha256']==init['sha256']
                and change['after_sha256']==record['sha256'] and change['changed']is True
                and init['sha256']!=record['sha256'],'Intended learned tensor did not change')
        if name.endswith('.lora_B'):
            require(init['sha256']==sha(bytes(math.prod(shape)*4)),'Initial B/effective delta not exactly zero')
        if name in dict(HEAD):
            old=heads[[n for n,_ in HEAD].index(name)]
            require(init['sha256']==old['sha256'],'Existing pretrained head reinitialized')
    proof=artifact['frozen_pretrained_proof'];expected=frozen_shapes();frozen=proof['before_after']
    require([r['name']for r in frozen]==sorted(expected),'Complete canonical511frozen parameter names required')
    require(proof['parameter_count']==406291456 and proof['tensor_count']==511
            and proof['all_bit_unchanged']is True,'Frozen backbone count/state changed')
    before,after=[],[]
    for r in frozen:
        manifest(r,r['name'],expected[r['name']],'sha256_before')
        require(r['sha256_before']==r['sha256_after'],'A frozen pretrained tensor changed')
        common={k:r[k]for k in ['name','shape','dtype','numel','bytes']}
        before.append({**common,'sha256':r['sha256_before']});after.append({**common,'sha256':r['sha256_after']})
    require(canonical_sha(before)==proof['aggregate_before_sha256']==proof['aggregate_after_sha256']
            ==canonical_sha(after),'Frozen proof aggregate byte hash mismatch')
    deltas=artifact['effective_lora_delta'];require(len(deltas)==4,'All four attention deltas required')
    mechanism=[]
    for d,module in zip(deltas,MODULES):
        require(d['module']==module and d['shape']==[1024,1024]and d['scale']==2.0
                and hexsha(d['sha256']),'Effective attention delta identity mismatch')
        a=list(struct.unpack('<4096f',payloads[module+'.lora_A']))
        b=list(struct.unpack('<4096f',payloads[module+'.lora_B']))
        # At least one nonzero mathematical BA entry is independently checked.
        # Torch FP32/FMA-derived delta SHA is a producer receipt, not falsely
        # represented as an exact float64 replay of matrix multiplication.
        nonzero=False
        for row in range(1024):
            for col in range(1024):
                if math.fsum(b[row*4+k]*a[k*1024+col]for k in range(4))!=0:
                    nonzero=True;break
            if nonzero:break
        require(nonzero and type(d['nonzero_entries'])is int and 0<d['nonzero_entries']<=1024*1024
                and math.isfinite(d['l2_norm'])and d['l2_norm']>0
                and math.isfinite(d['max_abs'])and d['max_abs']>0,'Effective attention adaptation absent/nonfinite')
        steps=d['B_nonzero_gradient_steps']
        require(type(steps)is list and steps and steps==sorted(set(steps))
                and all(type(i)is int and 1<=i<=24 for i in steps)
                and math.isfinite(d['max_B_gradient_l2'])and d['max_B_gradient_l2']>0,
                'Intended attention did not receive a finite nonzero TRAIN gradient')
        mechanism.append({'module':module,'independent_BA_nonzero':True,'B_nonzero_gradient_steps':steps,
                          'max_B_gradient_l2':d['max_B_gradient_l2']})
    return {'schema_version':1,'epoch':30,'kind':KIND,'status':'PASS_LEARNED_PARAMETER_AND_COMPLETE_FROZEN_BACKBONE_EVIDENCE',
            'artifact':identity(path),'trainable_tensors':12,'trainable_parameters':1085443,
            'frozen_original_tensors':511,'frozen_original_parameters':406291456,
            'frozen_aggregate_sha256':proof['aggregate_before_sha256'],'mechanism':mechanism,
            'original_head_manifest':heads,'algorithm':artifact['algorithm'],
            'mechanism_flags':{'original_head_preserved':True,'initial_B_zero':True,'all_base_unchanged':True,
                               'all12_changed':True,'all4_B_mechanisms_nonzero':True},
            'original_weights_or_models_loaded_by_auditor':0,'TRAIN_choice_or_example_reads':0,
            'delta_SHA_scope':'Producer TorchFP32 matmul receipt; factorbytes and mathematical nonzero independently replayed; no false exact-FMA-bit claim'}
