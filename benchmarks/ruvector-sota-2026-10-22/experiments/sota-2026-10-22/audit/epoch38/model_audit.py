"""Independent metadata binding of the stock frozen pretrained reader; no weight I/O."""
import math,re,struct
from data_common import require,finite

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

def audit_models(root,raw,plan):
    from phase_audit import read,checked
    from nli_metrics import PROFILES
    require(set(raw['model_initializations'])==set(raw['model_states_unchanged'])=={'xxlarge'},'Single exact model initialization/state profile required')
    corpus=raw['corpora']['engineering'];require(corpus['model_states_unchanged']==raw['model_states_unchanged'],'Corpus/final model state aliases differ')
    profiles=read(root/plan['model_profiles_path'],plan['model_profiles_sha256'])
    require(profiles['epoch']==38 and set(profiles['profiles'])=={'xxlarge'},'Wrong frozen single-reader profile map')
    pins={p['path']:p for p in plan['pins']};sources={}
    for tag,key in [('xxlarge','pretrained_model_source')]:
        pin=plan[key];require(pins.get(pin['path'])==pin,'Unpinned exact model source');source=read(checked(root,pin));sources[tag]=source
        for field in ['metadata_admission','original_archive_metadata','legacy_original_load_plan']:
            reference=source[field];require(pins.get(reference['path'])==reference,'Unpinned pretrained model metadata reference: '+field);checked(root,reference)
        wanted=PROFILES[tag]
        require(source['epoch']==38 and source['kind']=='ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES'
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
    require(sources['xxlarge']['repository']=='microsoft/deberta-v2-xxlarge-mnli'and sources['xxlarge']['revision']=='8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06','Pretrained model identity differs')
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
    return {'status':'PASS_SINGLE_ORIGINAL_PRETRAINED_STOCK_READER',
        'xxlarge':{'status':'PASS_ORIGINAL_XXL_F16_SOURCE_F32_CPU_METADATA','weights_sha256':spec['sha'],'original_archive_metadata':meta_ref,
          'legacy_original_load_plan':legacy_ref,'source_metadata_audit':metadata_audit,
          'learned_parameters':parameters,'source_learned_tensors':len(floating),'classifier_manifest':head,'final_state_check':final,
          'buffer_source':r['position_ids_buffer_source']},
        'model_profiles':{'path':plan['model_profiles_path'],'sha256':plan['model_profiles_sha256']},
        'training_lineage_complete':False,'official_eligibility':'HOLD',
        'scope':'Frozen exact original asset/source metadata plus actual strict loading, dtype, no-warmup and state/head invariance receipts. Independent scorer does not decode any full learned tensor or execute the model. Source-frozen symbolic tensor metadata is not alone a proof of named-parameter identity; strict model-class loading/state checks supply that additional boundary.'}

EXPECTED_CATALOG={'path':'experiments/sota-2026-10-22/candidate/epoch38/MODEL_ASSETS.expected.json','bytes':2112,'sha256':'a65cda75fc67d2c935eac4b998fa5d3a6e375bbfbd7212dd19d998d15b016806'}
ASSET_FILENAMES={'config.json','tokenizer_config.json','LICENSE','spm.model','pytorch_model.bin'}

def independent_asset_identity(row):
    """Independent inert source-declaration interpretation; no payload reads."""
    import hashlib
    require(type(row)is dict,'Explicit source asset declaration required');fields={'path','bytes','source_url','upstream_git_blob_sha1'}
    typed=set(row)&{'metadata_body_sha256','upstream_sha256'}
    require(len(typed)==1 and set(row)==fields|typed,'Observed sha256 cannot replace typed source authority')
    filename=row['path'];size=row['bytes'];url=row['source_url'];upstream=row['upstream_git_blob_sha1'];key=next(iter(typed));payload=row[key]
    require(type(filename)is str and filename and '/'not in filename and '\\'not in filename and filename not in ['.','..']and type(size)is int and size>=0 and type(url)is str and url.startswith('https://')and type(upstream)is str and re.fullmatch('[0-9a-f]{40}',upstream)and sha(payload),'Malformed typed asset declaration')
    ordinary=key=='metadata_body_sha256';out={'path':filename,'bytes':size,'source_url':url,'payload_sha256':payload,'upstream_git_object_sha1':upstream,'representation':'RAW_GIT_BLOB_PAYLOAD'if ordinary else'CANONICAL_GIT_LFS_POINTER_WITH_SEPARATE_SHA256_PAYLOAD','raw_payload_git_blob_sha1_required':ordinary}
    if not ordinary:
        pointer=f'version https://git-lfs.github.com/spec/v1\noid sha256:{payload}\nsize {size}\n'.encode('ascii');git=hashlib.sha1(b'blob '+str(len(pointer)).encode()+b'\0'+pointer).hexdigest()
        require(git==upstream,'LFS upstream must be canonical pointer identity, not expanded payload Git hash')
        out.update(upstream_lfs_pointer_bytes=len(pointer),upstream_lfs_pointer_sha256=hashlib.sha256(pointer).hexdigest(),upstream_lfs_pointer_git_sha1=git)
    return out

def asset_guard_leaf_check(leaf,declarations,observed,refs,model_directory):
    """Replay source-bound actual full-scan metadata, without ML or rescanning GBs."""
    require(leaf['schema_version']==1 and leaf['epoch']==38 and leaf['kind']=='ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES'and leaf['source_checkpoint']=='7c50ba99848f6a13707eeec6c4947291a8478e5c'and leaf['status']=='ALL_FIVE_REAL_MODEL_ASSETS_VERIFIED_WITH_TYPED_SOURCE_IDENTITIES'and leaf['validator_function']=='model_assets_guard.validate_model_assets','Wrong real guard leaf scope')
    for key in ['common_source','validator_source','identity_helper_source','expected_catalog','public_model_assets_lock']:require(leaf[key]==refs[key],'Guard source identity changed: '+key)
    require(leaf['repository']=='microsoft/deberta-v2-xxlarge-mnli'and leaf['revision']=='8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06'and leaf['model_directory']==model_directory,'Real guard model source/directory changed')
    require(leaf['directory_inventory']==sorted(ASSET_FILENAMES|{'asset-lock.json'}),'Extra or missing external model asset')
    direct=leaf['external_direct_lock'];lock=refs['public_model_assets_lock'];require(direct=={'path':model_directory+'/asset-lock.json','bytes':lock['bytes'],'sha256':lock['sha256'],'byte_identical_to_public':True},'Direct observed lock must equal frozen public lock, not expected authority')
    require(leaf['stubs_used']is False and leaf['monkeypatches']==[]and all(type(leaf[k])is int and leaf[k]==0 for k in ['model_native_tokenizer_initializations_or_calls','case_oracle_reads','network_calls']),'Unstubbed asset-only guard required')
    require(type(declarations)is list and type(observed)is list and len(declarations)==len(observed)==5 and {r['path']for r in declarations}=={r['path']for r in observed}==ASSET_FILENAMES,'Exact five separately declared/observed assets required')
    by_observed={r['path']:r for r in observed};results=leaf['files'];require(type(results)is list and len(results)==5 and len({r['path']for r in results})==5 and {r['path']for r in results}==ASSET_FILENAMES,'All five actual full payload scans required');by_result={r['path']:r for r in results};total=ordinary=0
    for declaration in declarations:
        identity=independent_asset_identity(declaration);filename=identity['path'];o=by_observed[filename];r=by_result[filename];isordinary=identity['raw_payload_git_blob_sha1_required'];ordinary+=int(isordinary);total+=identity['bytes']
        require(type(o['bytes'])is int and o['bytes']==identity['bytes']and o['sha256']==identity['payload_sha256']and o['source_url']==identity['source_url']and o['upstream_git_blob_sha1']==identity['upstream_git_object_sha1'],'Observed public lock differs from independent source declaration')
        for k,v in identity.items():require(type(r[k])is type(v)and r[k]==v,'Real scan typed identity differs: '+filename+':'+k)
        require(r['payload_size_and_SHA256_verified']is True and r['raw_payload_git_sha1_verified']is isordinary and r['LFS_pointer_SHA1_compared_to_payload_SHA1']is False and type(r['actual_payload_bytes_hashed'])is int and r['actual_payload_bytes_hashed']==identity['bytes']and r['actual_payload_sha256']==identity['payload_sha256']and r['actual_full_payload_scan']is True and r['payload_git_SHA1_computed']is isordinary and r['LFS_payload_git_SHA1_not_required']is(not isordinary),'Unverified, partial, or pointer/payload-confused actual scan')
        require(r['actual_ordinary_payload_git_blob_sha1']==(identity['upstream_git_object_sha1']if isordinary else None),'Ordinary body Git SHA1 required only for ordinary source objects')
    require(leaf['actual_payload_files_verified']==5 and leaf['actual_payload_bytes_hashed']==total and leaf['ordinary_Git_payloads_verified']==ordinary==3 and leaf['canonical_LFS_pointers_verified']==2,'Actual five-file scan totals differ')
    require(finite(leaf['wall_seconds_hash_validation_only'])and leaf['wall_seconds_hash_validation_only']>=0,'Invalid real asset hash-scan timing')
    return {'status':'PASS_INDEPENDENT_TYPED_ASSET_GUARD_METADATA_REPLAY','actual_payload_files_verified':5,'ordinary_Git_payloads_verified':3,'canonical_LFS_pointers_verified':2,'actual_payload_bytes_hashed':total,'scope':'Actual root guard metadata bound to exact source/catalog/public/direct lock. Scorer imports no candidate helper and decodes/re-hashes no learned payload; source-frozen real full scan is retained evidence, not a fixture.'}

def premeasurement_asset_guard_check(root,plan):
    from phase_audit import read,checked
    from data_common import SOURCE_CHECKPOINT
    pins={r['path']:r for r in plan['pins']}
    for name in ['model_assets_expected','model_assets_validator','real_model_assets_guard_receipt']:
        reference=plan[name];require(reference==pins.get(reference['path'])and plan[name+'_path']==reference['path']and plan[name+'_sha256']==reference['sha256'],'Exact canonical asset admission ref/alias mismatch: '+name);checked(root,reference)
    require(plan['model_assets_expected']==EXPECTED_CATALOG,'Original separate expected catalog changed')
    catalog=read(checked(root,EXPECTED_CATALOG));lockref=pins[plan['model_assets_lock_path']];public=read(checked(root,lockref));require(public['epoch']==38 and public['kind']=='ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES'and public['model_directory']==plan['model_directory'],'Wrong public asset materialization lock')
    envelope=read(checked(root,plan['real_model_assets_guard_receipt']))
    asset_guard_envelope_check(envelope)
    base='experiments/sota-2026-10-22/candidate/epoch38/';refs={'common_source':pins[base+'runtime/common.py'],'validator_source':plan['model_assets_validator'],'identity_helper_source':pins[base+'asset_identity.py'],'expected_catalog':EXPECTED_CATALOG,'public_model_assets_lock':lockref}
    for key,value in refs.items():require(envelope[key]==value,'Envelope/source pin differs: '+key);checked(root,value)
    require(set(envelope['result'])=={'xxlarge'},'Exactly one original model asset guard result required')
    audit=asset_guard_leaf_check(envelope['result']['xxlarge'],catalog['files'],public['files'],refs,plan['model_directory'])
    return {'receipt':plan['real_model_assets_guard_receipt'],'separate_expected_catalog':EXPECTED_CATALOG,**audit}


def asset_guard_envelope_check(envelope):
    from data_common import SOURCE_CHECKPOINT
    required={'schema_version','epoch','source_checkpoint','status','function','function_calls','common_source','validator_source','identity_helper_source','expected_catalog','public_model_assets_lock','stubs_used','monkeypatches','model_native_tokenizer_initializations_or_calls','case_oracle_reads','result'}
    require(type(envelope)is dict and set(envelope)==required,'Exact full actual guard envelope schema required; no call-counter aliases')
    require(envelope['schema_version']==1 and envelope['epoch']==38 and envelope['source_checkpoint']==SOURCE_CHECKPOINT and envelope['status']=='PASS_UNSTUBBED_FULL_REAL_ASSET_GUARD_BEFORE_SOURCE_FREEZE'and envelope['function']=='C.verify_model_assets'and type(envelope['function_calls'])is int and envelope['function_calls']==1,'One full actual shared guard required before source freeze')
    require(envelope['stubs_used']is False and envelope['monkeypatches']==[]and type(envelope['case_oracle_reads'])is int and envelope['case_oracle_reads']==0 and type(envelope['model_native_tokenizer_initializations_or_calls'])is int and envelope['model_native_tokenizer_initializations_or_calls']==0,'Prefreeze asset guard cannot be mocked or execute cases/models')
    require(type(envelope['result'])is dict and set(envelope['result'])=={'xxlarge'},'Exactly one model asset result required')
    return True
