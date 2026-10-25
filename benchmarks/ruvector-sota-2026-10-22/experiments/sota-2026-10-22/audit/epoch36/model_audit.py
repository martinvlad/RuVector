"""Independent metadata binding of the stock frozen pretrained reader; no weight I/O."""
import math,re,struct
from data_common import require,finite

WEIGHT_SHA='c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'
WEIGHT_BYTES=870182606
HEAD_SHAPES={'classifier.weight':[3,1024],'classifier.bias':[3],
             'pooler.dense.weight':[1024,1024],'pooler.dense.bias':[1024]}
STORED='Exact mmap source int64 arange512 checked against stock nonpersistent buffer'
DERIVED='Only deterministic nonpersistent stock position_ids constructed from source/config; no learned fallback'
XXL_STORED='Exact original source I64 arange512 validated, sole permitted legacy nonpersistent buffer'
XXL_DERIVED='Only deterministic config-derived stock arange512 nonpersistent buffer; no learned fallback'
XXL_METADATA_SHA='05e21f2e52be254c09c7cf715cd36afd1bd6f4a58b9a0710c9f1589506a07fc0'
LEGACY_PLAN_SHA='98daf4e1807375fa785f72b8014cbd067c58bc8d1232c0a1c237c86479113fdd'
LEGACY_FORMAT='PYTORCH_LEGACY_CONCATENATED_PICKLE_RAW_STORAGES'
LEGACY_STATUS='ORIGINAL_TORCH_LEGACY_PICKLETOOLS_METADATA_VERIFIED_NO_UNPICKLE'

def sha(value):
    return type(value)is str and re.fullmatch('[0-9a-f]{64}',value)is not None

def state_check(value,head):
    require(type(value)is dict and value['unchanged']is True and value['classifier_manifest']==head,
            'Frozen pretrained model/head state changed or missing')
    require(type(value['scope'])is str and bool(value['scope']),'Missing state-proof scope')
    return {'unchanged':True,'scope':value['scope']}

def legacy_metadata_check(meta):
    """Replay root-approved primitive metadata; no tensor payload or pickle I/O."""
    from nli_metrics import PROFILES
    spec=PROFILES['xxlarge']
    require(meta['schema_version']==3 and meta['epoch']==36 and meta['status']==LEGACY_STATUS
        and meta['format']==LEGACY_FORMAT and meta['weights']=={'bytes':spec['bytes'],'sha256':spec['sha']},'Wrong exact original legacy metadata')
    require(all(meta[k]==0 for k in ['unsafe_unpickling_calls','checkpoint_functions_invoked','ML_imports','model_tokenizer_native_calls','storage_payloads_decoded'])
        and meta['storage_data_ends_at_filelength']is True,'Unsafe or payload-decoding legacy metadata')
    require(meta['magic_number_hex']=='0x1950a86a20f9469cfc6c'and meta['protocol_version']==1001
        and meta['sys_info']=={'protocol_version':1001,'little_endian':True,'type_sizes':{'short':2,'int':4,'long':4}},'Different original legacy protocol/platform')
    cursor=0;objects=meta['metadata_objects']
    require(meta['metadata_pickle_count']==len(objects)==5
        and[r['name']for r in objects]==['magic','protocol','sys_info','state_dict','serialized_storage_keys'],'Five original metadata streams required')
    allowed={'collections.OrderedDict','torch.HalfStorage','torch._utils._rebuild_tensor_v2'}
    for row in objects:
        require(row['offset']==cursor and type(row['bytes'])is int and 0<row['bytes']<=8388608
            and sha(row['sha256'])and type(row['opcode_count'])is int and 0<row['opcode_count']<=2000000
            and set(row['checkpoint_globals_as_inert_symbols'])<=allowed,'Invalid inert bounded metadata range')
        cursor+=row['bytes']
    require(cursor==meta['combined_metadata_bytes']==127876 and cursor<=8388608,'Original metadata byte closure differs')
    roots=meta['storages'];keys=meta['serialized_storage_keys_in_physical_order']
    require(type(roots)is dict and len(roots)==meta['unique_storage_count']==9 and len(keys)==9
        and len(set(keys))==9 and set(keys)==set(roots),'Nine exact shared root storages required')
    for key in keys:
        row=roots[key]
        require(row['dtype']=='F16'and row['location_tag']=='cuda:0'and type(row['elements'])is int and row['elements']>0
            and row['bytes']==row['data_bytes']==row['elements']*2 and row['header_bytes']==8
            and row['header_offset']==cursor and row['header_element_count']==row['elements']
            and type(row['header_hex'])is str and re.fullmatch('[0-9a-f]{16}',row['header_hex'])is not None
            and struct.unpack('<Q',bytes.fromhex(row['header_hex']))[0]==row['elements']
            and row['data_offset']==cursor+8 and row['data_end_offset']==cursor+8+row['bytes']
            and row['raw_payload_decoded']is False,'Original legacy storage count/range/format differs')
        cursor=row['data_end_offset']
    require(cursor==spec['bytes']and meta['storage_header_bytes']==72
        and meta['unique_storage_bytes']==sum(r['bytes']for r in roots.values())
        and meta['combined_metadata_bytes']+meta['storage_header_bytes']+meta['unique_storage_bytes']==spec['bytes'],'Legacy metadata/header/payload exact EOF closure failed')
    tensors=meta['tensors'];require(type(tensors)is list and len(tensors)==meta['state_tensor_count']==782
        and len({t['name']for t in tensors})==782,'Exact original782 state tensors required')
    intervals={k:[]for k in roots};shared={k:[]for k in roots}
    for t in tensors:
        shape=t['shape'];stride=[];extent=1
        require(type(shape)is list and 0<len(shape)<=8 and all(type(d)is int and d>0 for d in shape),'Invalid original tensor shape')
        for d in reversed(shape):stride.insert(0,extent);extent*=d
        key=t['storage_key'];require(key in roots and t['dtype']=='F16'and t['stride']==stride and t['numel']==extent
            and type(t['storage_offset'])is int and t['storage_offset']>=0 and t['root_storage_offset']==t['storage_offset']
            and t['legacy_view_key']is None and t['legacy_view_offset']==0 and t['legacy_view_elements']==roots[key]['elements']
            and t['requires_grad_tag']is False,'Different original contiguous F16 state descriptor')
        intervals[key].append((t['root_storage_offset'],t['root_storage_offset']+extent));shared[key].append(t['name'])
    for key,rr in intervals.items():
        end=0
        for a,b in sorted(rr):require(a==end and b>a,'Original tensor ranges overlap or leave storage gap');end=b
        require(end==roots[key]['elements'],'Original tensor ranges do not completely cover shared root')
    total=sum(t['numel']for t in tensors)
    require(total==1566915075==meta['floating_state_tensor_elements']==meta['unique_floating_storage_elements']
        and meta['source_parameter_dtype']=='F16'and meta['dtype_summaries']=={'F16':{'tensor_count':782,'tensor_elements':total}}
        and meta['shared_storage_keys']=={k:v for k,v in shared.items()if len(v)>1},'Original source F16 dtype/count/shared-view closure differs')
    require(all(t['name']!='deberta.embeddings.position_ids'for t in tensors),'Original source has no position_ids or I64 buffer')
    return {'status':'PASS_EXACT_ORIGINAL_LEGACY_PRIMITIVE_METADATA','format':LEGACY_FORMAT,'state_tensor_count':782,
        'source_state_elements':total,'shared_root_storages':9,'source_I64_tensors':0,'source_position_ids_present':False,
        'source_storage_location_tags':['cuda:0'],'actual_loader_required_map_location':'cpu',
        'scope':'Source location tags are retained provenance, not actual GPU work. State elements are not called named parameters until actual strict model-class receipt agrees.'}

def audit_b354_metadata(raw):
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

def audit_models(root,raw,plan):
    from phase_audit import read,checked
    from nli_metrics import PROFILES
    require(set(raw['model_initializations'])==set(raw['model_states_unchanged'])=={'b354','xxlarge'},'Both exact model initialization/state profiles required')
    corpus=raw['corpora']['engineering'];require(corpus['model_states_unchanged']==raw['model_states_unchanged'],'Corpus/final model state aliases differ')
    profiles=read(root/plan['model_profiles_path'],plan['model_profiles_sha256'])
    require(profiles['epoch']==36 and set(profiles['profiles'])=={'b354','xxlarge'},'Wrong frozen two-reader profile map')
    pins={p['path']:p for p in plan['pins']};sources={}
    for tag,key in [('xxlarge','pretrained_model_source'),('b354','baseline_model_source')]:
        pin=plan[key];require(pins.get(pin['path'])==pin,'Unpinned exact model source');source=read(checked(root,pin));sources[tag]=source
        wanted=PROFILES[tag]
        require(source['epoch']==36 and source['kind']=='ENGINEERING_PAIRED_READER_SOURCE_COVERAGE'
            and source['weights_sha256']==wanted['sha']and source['weights_bytes']==wanted['bytes']
            and source['source_parameter_dtype']=='F16'and source['compute_dtype']=='F32'
            and source['training_lineage_complete']is False and source['promotion_allowed']is False
            and source['official_eligibility']=='HOLD'and source['confirmation']==[],'Wrong model source/weights/dtype or overstated eligibility')
        native={str(i):name.lower().replace('notmentioned','neutral')for i,name in enumerate(wanted['order'])}
        require({str(k):v.lower().replace('notmentioned','neutral')for k,v in source['native_id2label'].items()}==native,'Source label-index map changed')
        entry=profiles['profiles'][tag];assetkey='model_assets_lock'if tag=='xxlarge'else'baseline_model_assets_lock'
        assetref=next((p for p in plan['pins']if p['path']==plan[assetkey+'_path']),None)
        require(entry['model_source']==pin and entry['model_assets_lock']==assetref and entry['native_label_order']==wanted['order']
            and entry['canonical_E_C_N_from_raw']==wanted['canonical'],'Model profile source/asset/order binding differs')
        require(entry['model_directory']==plan['model_directory'if tag=='xxlarge'else'baseline_model_directory'],'Model directory scope differs')
    require(sources['b354']['repository']=='MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
        and sources['b354']['revision']=='b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7'
        and sources['xxlarge']['repository']=='microsoft/deberta-v2-xxlarge-mnli'
        and sources['xxlarge']['revision']=='8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06','Pretrained model identity differs')
    b354=audit_b354_metadata({'model_initialization':raw['model_initializations']['b354'],
        'model_state_unchanged':raw['model_states_unchanged']['b354'],
        'corpora':{'engineering':{'model_state_unchanged':corpus['model_states_unchanged']['b354']}}})
    source=sources['xxlarge'];entry=profiles['profiles']['xxlarge'];meta_ref=source['original_archive_metadata']
    require(entry['original_archive_metadata']==meta_ref and pins.get(meta_ref['path'])==meta_ref
        and meta_ref['path']==plan['xxlarge_weight_metadata_path']and meta_ref['sha256']==plan['xxlarge_weight_metadata_sha256']==XXL_METADATA_SHA
        and meta_ref['bytes']==408186,
        'Original symbolic archive metadata must match exact explicit frozen plan')
    meta=read(checked(root,meta_ref));spec=PROFILES['xxlarge']
    metadata_audit=legacy_metadata_check(meta);tensors=floating=meta['tensors']
    legacy_ref=source['legacy_original_load_plan']
    require(entry['legacy_original_load_plan']==legacy_ref and pins.get(legacy_ref['path'])==legacy_ref
        and legacy_ref['path']==plan['legacy_original_load_plan_path']
        and legacy_ref['sha256']==plan['legacy_original_load_plan_sha256']==LEGACY_PLAN_SHA,'Exact approved legacy load-plan binding differs')
    legacy=read(checked(root,legacy_ref));policy=legacy['future_frozen_loader_policy']
    require(legacy['schema_version']==3 and legacy['epoch']==36 and policy['serialization_format']==LEGACY_FORMAT
        and policy['weights_only']is True and policy['mmap']is False and policy['map_location']=='cpu'
        and policy['unrestricted_pickle_allowed']is False and policy['extra_pickle_safe_globals_added']==0
        and policy['ZIP_fallback_allowed']is False and policy['alternate_checkpoint_allowed']is False
        and policy['dynamic_quantization_allowed']is False,'Approved restricted legacy loader policy differs')
    parameters=sum(t['numel']for t in floating);r=raw['model_initializations']['xxlarge']
    require(r['model_class']=='DebertaV2ForSequenceClassification'and r['learned_parameters']==parameters
        and r['source_state_tensor_count']==len(tensors)and r['source_learned_tensor_count']==len(floating)and r['source_parameter_dtype']=='F16'and r['compute_dtype']=='F32'
        and r['loading_missing_keys']==[]and r['loading_unexpected_keys']==[]and r['CPU_FP32']is True
        and r['meta_tensors_remaining']==0 and r['safe_weights_only_legacy_meta_assign']is True
        and r['weights_only']is True and r['mmap']is False and r['map_location']=='cpu'and r['strict_assign']is True
        and r['original_serialization_format']==LEGACY_FORMAT and r['legacy_original_load_plan']==legacy_ref
        and r['unrestricted_pickle_allowed']is False and r['extra_pickle_safe_globals_added']==0
        and r['source_storage_offsets_verified_before_F32']is True and r['source_state_references_disposed_before_F32']is True
        and type(r['preconversion_gc_collected_objects'])is int and r['preconversion_gc_collected_objects']>=0,
        'Exact original xxlarge strict loaded FP32 state not established')
    require(r['original_archive_metadata']==meta_ref and r['weights_sha256']==spec['sha']
        and r['no_training_or_classifier_reinitialization']is True and r['actual_model_warmup_forwards']==0
        and r['attention']=='eager'and r['all_source_values_losslessly_converted_F16_to_F32']is True,'Wrong xxlarge source, warmup, head, attention or cast')
    require(r['tokenizer_class']=='DebertaV2TokenizerFast'and r['pair_special_tokens']==3
        and sha(r['backend_before_sha256'])and sha(r['backend_after_sha256']),'Source-pinned xxlarge fast tokenizer formatting missing')
    require(r['nonpersistent_buffers']==['deberta.embeddings.position_ids']and r['position_ids_buffer_source']==XXL_DERIVED,
        'Original legacy source has no I64/position_ids; sole buffer must be deterministic config-derived')
    require(finite(r['initialization_seconds'])and r['initialization_seconds']>=0,'Invalid xxlarge initialization timing')
    shapes={'classifier.weight':[3,1536],'classifier.bias':[3],'pooler.dense.weight':[1536,1536],'pooler.dense.bias':[1536]}
    by={t['name']:t for t in tensors};head=r['classifier_manifest'];require(set(head)==set(shapes),'Incomplete original xxlarge head/pooler proof')
    for name,shape in shapes.items():
        require(name in by and by[name]['shape']==shape and head[name]['shape']==shape and head[name]['dtype']=='float32'and sha(head[name]['sha256']),'Wrong original xxlarge classifier/pooler state: '+name)
    final=state_check(raw['model_states_unchanged']['xxlarge'],head)
    return {'status':'PASS_TWO_ORIGINAL_PRETRAINED_STOCK_READERS','b354':b354,
        'xxlarge':{'status':'PASS_ORIGINAL_XXL_F16_SOURCE_F32_CPU_METADATA','weights_sha256':spec['sha'],'original_archive_metadata':meta_ref,
          'legacy_original_load_plan':legacy_ref,'source_metadata_audit':metadata_audit,
          'learned_parameters':parameters,'source_learned_tensors':len(floating),'classifier_manifest':head,'final_state_check':final,
          'buffer_source':r['position_ids_buffer_source']},
        'model_profiles':{'path':plan['model_profiles_path'],'sha256':plan['model_profiles_sha256']},
        'training_lineage_complete':False,'official_eligibility':'HOLD',
        'scope':'Frozen exact original asset/source metadata plus actual strict loading, dtype, no-warmup and state/head invariance receipts. Independent scorer does not decode any full learned tensor or execute either model. Source-frozen symbolic tensor metadata is not alone a proof of named-parameter identity; strict model-class loading/state checks supply that additional boundary.'}
