"""Independent metadata binding of the stock frozen pretrained reader; no weight I/O."""
import re
from data_common import require,finite

WEIGHT_SHA='c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'
WEIGHT_BYTES=870182606
HEAD_SHAPES={'classifier.weight':[3,1024],'classifier.bias':[3],
             'pooler.dense.weight':[1024,1024],'pooler.dense.bias':[1024]}
STORED='Exact mmap source int64 arange512 checked against stock nonpersistent buffer'
DERIVED='Only deterministic nonpersistent stock position_ids constructed from source/config; no learned fallback'

def sha(value):
    return type(value)is str and re.fullmatch('[0-9a-f]{64}',value)is not None

def state_check(value,head):
    require(type(value)is dict and value['unchanged']is True and value['classifier_manifest']==head,
            'Frozen pretrained model/head state changed or missing')
    require(type(value['scope'])is str and bool(value['scope']),'Missing state-proof scope')
    return {'unchanged':True,'scope':value['scope']}

def audit_model(raw):
    r=raw['model_initialization']
    require(r['model_class']=='DebertaV2ForSequenceClassification' and r['learned_parameters']==435064835
            and r['loading_missing_keys']==[] and r['loading_unexpected_keys']==[]
            and r['CPU_FP32']is True and r['meta_tensors_remaining']==0
            and r['safe_mmap_meta_assign']is True,'Original exact stock FP32 learned state not established')
    require(r['weights_sha256']==WEIGHT_SHA and r['no_training_or_classifier_reinitialization']is True
            and r['actual_model_warmup_forwards']==0 and r['attention']=='eager','Wrong checkpoint/head/attention or unbudgeted warmup')
    require(r['source_parameter_dtype']=='F16'and r['compute_dtype']=='F32'
            and r['source_learned_tensor_count']==394
            and r['all_source_values_losslessly_converted_F16_to_F32']is True,
            'Exact source F16 to compute F32 conversion not established')
    require(r['tokenizer_class']=='DebertaV2TokenizerFast' and r['pair_special_tokens']==3
            and sha(r['backend_before_sha256'])and sha(r['backend_after_sha256']),
            'Original fast tokenizer/pair formatting proof missing')
    require(r['nonpersistent_buffers']==['deberta.embeddings.position_ids'] and r['position_ids_buffer_source']==STORED,
            'Unexplained or unmaterialized model buffer')
    learned_bytes=435064835*2
    require(r['data_bytes']==learned_bytes+4096
            and r['header_bytes']==48832
            and r['data_bytes']+r['header_bytes']+8==WEIGHT_BYTES
            and r['header_sha256']=='54177dcf30939971325ccfdda856523560a0457fa66e701d6206d27f96a7d9b4'
            and r['tensor_count']==395,'Original F16 safetensors header/data/count closure failed')
    require(finite(r['initialization_seconds'])and r['initialization_seconds']>=0,'Invalid initialization timing')
    head=r['classifier_manifest'];require(set(head)==set(HEAD_SHAPES),'Original classifier/pooler manifest incomplete')
    for name,shape in HEAD_SHAPES.items():
        require(head[name]['shape']==shape and head[name]['dtype']=='float32' and sha(head[name]['sha256']),
                'Wrong stock pretrained classifier/pooler tensor proof: '+name)
    final=state_check(raw['model_state_unchanged'],head)
    roles={}
    for name,receipt in raw['corpora'].items():
        if receipt is not None:roles[name]=state_check(receipt['model_state_unchanged'],head)
    return {'status':'PASS_ORIGINAL_FROZEN_STOCK_MORITZ_F16_SOURCE_FP32_COMPUTE_METADATA','weights_sha256':WEIGHT_SHA,
            'learned_parameters':435064835,'buffer_source':r['position_ids_buffer_source'],
            'classifier_manifest':head,'role_state_checks':roles,'final_state_check':final,
            'scope':'Byte-pinned original source plus actual strict loading metadata and storage/version/head-byte invariance. No independent full learned tensor decode, clone or hidden-forward claim.'}
