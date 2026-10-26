"""Independent E47 post-DATA audit. No target source import or execution.

Prepare requires no current plan, DATA or private asset. Actual mode requires
root's exact input digest and exact frozen plan/SF/DATA descriptors. Public
SOURCE/Node/custody metadata is parsed; all private files, including the attempt
marker, remain opaque. The two new private containers are only
streamed into SHA256, never parsed or exposed. No Node/version/model/native call.
"""
import argparse,ast,hashlib,json,os,re,stat,time
from pathlib import Path
OWN=Path('/workspace/ruvector-e47-reader/postdata-review-v2')
W=Path('/tmp/ruvector-sota-2026-10-22/epoch47-143d1a78ea73');ROOT=W/'project'
BASE='143d1a78ea730e030ff5255a20b047d856f6305f';KIND='REAL_CONTRACTNLI_QWEN_COMPACT_EVIDENCE_DEV_PILOT'
ORIGIN_KIND='REAL_CONTRACTNLI_QWEN_JOINT_CONTEXT_DEV_PILOT'
P='experiments/sota-2026-10-22/epoch47/';A='experiments/sota-2026-10-22/audit/epoch47/'
OWNER_SHA='d2ce6bd948494ce0f2698b41b0658158584488bba5141324fdca150fbfe539fe';OWNER_BYTES=701;OWNER_PID=150294;OWNER_TICKS=36360851
FEATURE_SHA='73443811bc58206012d6abbb1d1e738418d99a691706f19e9e1966722abdd21f';VAULT_SHA='6c4a5f6d1683b8d4fdc934a7fcca40fb8c73dd1936705e06746fd78d009c4cd5'
NODE_PATH='/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node';NODE_BYTES=125989464;NODE_SHA='bc17c508ffeed0ec622934f9b7fa72f8e78da65350e63c3eceb56fa688aa5e12'
DOCS=[357,227,46,212];HYPS=['nda-1','nda-10','nda-16'];CASES=[f'contractnli:eced6528:test:{d}:{h}'for d in DOCS for h in HYPS];COUNTS={'357':25,'227':53,'46':56,'212':42}
CHECKS=[]
def need(v,code):
    if not v:raise ValueError(code)
    CHECKS.append(code)
def equal(a,b):
    if type(a)is not type(b):return False
    if type(a)is dict:return set(a)==set(b)and all(equal(a[k],b[k])for k in a)
    if type(a)is list:return len(a)==len(b)and all(equal(x,y)for x,y in zip(a,b))
    return a==b
def unique(rows):
    out={}
    for k,v in rows:need(k not in out,'DUPLICATE_PUBLIC_JSON_KEY');out[k]=v
    return out
def parse_public(b):return json.loads(b,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in()).throw(ValueError('NONFINITE_PUBLIC_JSON')))
def regular(path):
    p=Path(path);need(p.is_absolute()and p==p.resolve()and not any(x.is_symlink()for x in(p,*p.parents)),'CANONICAL_NONSYMLINK_REGULAR_PATH');return p
def read_file(path,max_bytes=16777216,parse=False,opaque=False):
    p=regular(path);need(not parse or 'private'not in p.parts,'NO_PRIVATE_JSON_PARSE_CAPABILITY');need(not p.is_relative_to(W/'private')or opaque and not parse,'PRIVATE_ONLY_OPAQUE_HASH_ACCESS');fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb')as f:
        before=os.fstat(f.fileno());need(stat.S_ISREG(before.st_mode)and 0<=before.st_size<=max_bytes,'BOUNDED_REGULAR_SOURCE')
        b=f.read(max_bytes+1)if parse else None;h=hashlib.sha256()
        if b is not None:h.update(b)
        else:
            for block in iter(lambda:f.read(1048576),b''):h.update(block)
        after=os.fstat(f.fileno())
    signature=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode,x.st_uid)
    need(signature(before)==signature(after),'STABLE_COMPLETE_FILE_READ');need(b is None or len(b)==after.st_size,'EXACT_PARSED_SOURCE_LENGTH')
    if opaque:need(stat.S_IMODE(after.st_mode)==0o600 and after.st_nlink==1,'OPAQUE_NEW_EXCLUSIVE_MODE600_SINGLE_LINK')
    row={'path':str(p.relative_to(ROOT))if p.is_relative_to(ROOT)else str(p),'bytes':after.st_size,'sha256':h.hexdigest()}
    return row,parse_public(b)if parse else None
def canonical(row):
    need(type(row)is dict and set(row)=={'path','bytes','sha256'}and type(row['path'])is str and type(row['bytes'])is int and row['bytes']>=0 and type(row['sha256'])is str and re.fullmatch('[0-9a-f]{64}',row['sha256'])is not None,'EXACT_CANONICAL_THREE_KEY_REFERENCE')
    return row
def checked(row,public=True,parse=True):
    canonical(row);p=Path(row['path']);p=p if p.is_absolute()else ROOT/p
    need(not public or p.is_relative_to(ROOT),'PUBLIC_SOURCE_WITHIN_PROJECT')
    actual,obj=read_file(p,max_bytes=max(1,row['bytes']),parse=parse)
    expected={**row,'path':str(p.relative_to(ROOT))if p.is_relative_to(ROOT)else str(p)}
    need(equal(actual,expected),'EXACT_REFERENCED_BODY_SIZE_SHA256');return obj
def envelope(x):need(type(x)is dict and type(x.get('schema_version'))is int and x['schema_version']==1 and type(x.get('epoch'))is int and x['epoch']==47 and x.get('kind')==KIND and x.get('phase')=='dev','EXACT_E47_DEV_ENVELOPE')
def emit(path,value):
    p=regular(path);need(p.is_relative_to(OWN)and not p.exists(),'FRESH_OUTSIDE_PROJECT_AUDIT_OUTPUT');raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
    d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
    return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def counters():
    # Independent arithmetic over immutable published metadata, not target calls.
    units=sum(COUNTS.values());batches=sum((x+7)//8 for x in COUNTS.values())+len(CASES);out={}
    for prefix,count in [('corpus_batches',1),('native_helper_starts',1),('native_binary_loads',1),('native_index_initializations',len(DOCS)),('native_insertions',units),('native_queries',len(CASES)),('native_len_calls',2*len(DOCS)),('native_version_calls',1),('BGE_initializations',1),('ORT_sessions',1),('BGE_forward_calls',batches),('BGE_texts',units+len(CASES)),('reader_server_starts',1),('reader_server_stops',1),('label_tokenize_requests',3),('metadata_requests',1),('completion_requests',36)]:
        out[prefix+'_attempted']=count;out[prefix+'_completed']=count
    out.update(native_hit_source_validations=3*units,Node_network_operations_attempted=0,feature_cases_admitted=12,feature_documents_admitted=4,first_answer_token_draws_observed=36,forecasts_completed=36)
    for k in ['semantic_gold_decodes','training_calls','calibration_calls','confirmation_calls','paid_API_calls','GPU_calls']:out[k]=0
    need(units==176 and batches==36 and out['BGE_texts_completed']==188,'INDEPENDENT_SOURCE_COUNTER_ARITHMETIC_176_188_36');return out
def prepare():
    proof={'schema_version':1,'epoch':47,'kind':KIND,'phase':'dev','status':'PREPARED_ONLY_NO_FROZEN_PLAN_SOURCE_COMMIT_DATA_OR_PRIVATE_ACCESS','source_checkpoint':BASE,'actual_plan_SF_bytes_hashes_or_source_commit_not_assumed':True,'checker':read_file(Path(__file__).absolute())[0],'required_actual_input_keys':['schema_version','epoch','source_plan','source_freeze','data_admission'],'input_reference_contract':'Root supplies exact canonical3 descriptors after freeze and one DATA call; actual function runs only after follow-up. Source commit is derived from actual SOURCE admission and independent readback, never a prior source commit.','required_source_role_count':'DERIVED_FROM_ACTUAL_ROOT_CONTRACT','required_integrated_review_flag_count':'DERIVED_FROM_ACTUAL_ROOT_CONTRACT','guardian12_owner':{'path':str(W/'owner.json'),'bytes':OWNER_BYTES,'sha256':OWNER_SHA,'pid':OWNER_PID,'startticks':OWNER_TICKS},'expected_source_units_per_document':COUNTS,'expected_source_units_total':176,'planned_not_executed_operation_counters':{'dev':counters()},'private_access_contract':'Only two new containers stream to SHA256/stat; no JSON/header/body/token/label parse. The once-attempt metadata marker is also streamed to SHA256 and compared with independently constructed canonical bytes; no private JSON is parsed.','actual_DATA_or_private_accesses':0,'actual_target_source_imports_or_calls':0,'Node_native_model_tokenizer_Gold_version_or_API_calls':0,'R_writes':0,'scientific_quality_or_ABI_evidence':False,'dispatch_authorized_by_checker':False}
    return emit(OWN/'POSTDATA_CHECKER_READY.v2.json',proof)
def raw_identity(plan):
    need(equal(plan['dev_document_ids'],DOCS)and equal(plan['dev_hypothesis_ids'],HYPS)and equal(plan['data_roles'],{'train':[],'dev':CASES,'calibration':[],'confirmation':[]}),'EXACT_FROZEN_DEV12_ROLE_AND_ORDER')
    need(all(type(d)is int for d in plan['dev_document_ids']),'STRICT_INTEGER_DOCUMENT_IDS')
    expected={str(d):[f'contractnli:eced6528:test:{d}:{h}'for h in HYPS]for d in DOCS}
    need(equal(plan['case_ids_by_document'],expected),'RAW_FROZEN_DOCUMENT_CASE_MAP_PRESENT_EXACT')
    need(plan['used_confirmation_identities']==[]and equal(plan['reserved_confirmation_document_ids'],[62,321,2]),'UNUSED_PROTECTED_CONFIRMATION_METADATA_ONLY')
    need(type(plan['full_prompt_token_cap'])is int and plan['full_prompt_token_cap']==320 and type(plan['server_context_size'])is int and plan['server_context_size']==512 and plan['packing_policy']=='TWO_DISJOINT_WHOLE_SOURCE_UNIT_ANCHORS'and type(plan['max_source_units_per_window'])is int and plan['max_source_units_per_window']==1 and plan['windows_per_case_arm']==2 and plan['allow_duplicate_windows']is False and plan['allow_source_truncation']is False,'EXACT_COMPACT320_CONTEXT512_DISJOINT_WHOLE_UNIT_POLICY')
def frozen(x):
    need(type(x)is dict and set(x)=={'schema_version','epoch','source_plan','source_freeze','data_admission'}and type(x['schema_version'])is int and x['schema_version']==1 and type(x['epoch'])is int and x['epoch']==47,'EXACT_ROOT_FOLLOWUP_INPUT_SCHEMA')
    pr=x['source_plan'];sf=x['source_freeze'];canonical(pr);canonical(sf);canonical(x['data_admission'])
    need(pr['path']==P+'plan.json'and sf['path']==P+'SOURCE_FREEZE.json'and x['data_admission']['path']==A+'DATA_ADMISSION.json','EXACT_CANONICAL_CURRENT_E47_OUTPUT_PATHS')
    plan=checked(pr);envelope(plan);need(plan['source_checkpoint']==BASE and plan['source_bindings_ready']is True and equal(plan['source_freeze'],sf),'ACTUAL_INPUT_BOUND_FROZEN_E47_PLAN_SF');raw_identity(plan)
    freeze=checked(sf);need(type(freeze)is dict and freeze['epoch']==47 and freeze['source_checkpoint']==BASE,'EXACT_FROZEN_SOURCE_ENVELOPE')
    files=freeze['files'];need(type(files)is list and files and len({r['path']for r in files})==len(files),'DERIVED_UNIQUE_FROZEN_SOURCE_CLOSURE_NO_ASSUMED_ROW_COUNT')
    table={r['path']:r for r in files}
    for row in files:checked(row,parse=False)
    for role in ['features_source','materialization_policy','predataseal','node_runtime_manifest','node_runtime_guard_source','counter_formula_source','native_plan_contract_source']:
        need(equal(plan[role],table[plan[role]['path']]),'CANONICAL_FROZEN_SOURCE_ROLE_'+role)
    root=checked(plan['root_contract']);need(root['epoch']==47 and root['base_commit']==BASE and root['workdir']==str(W),'ROOT_E47_SOURCE_BASE_WORKDIR')
    roles=root['source_admission_contract']['required_roles'];flags=root['source_admission_contract']['required_review_flags'];need(type(roles)is list and roles and all(type(v)is str for v in roles)and len(roles)==len(set(roles))and set(roles)==set(plan['required_refs']),'ACTUAL_ROOT_DERIVED_FROZEN_SOURCE_REQUIRED_ROLES');need(type(flags)is list and flags and all(type(v)is str for v in flags)and len(flags)==len(set(flags))and {'compact_whole_unit_evidence_and_prefill_budget_verified','opaque_E44_origin_kind_distinct_from_E47_report_kind_verified'}<=set(flags),'ACTUAL_ROOT_DERIVED_INTEGRATED_SOURCE_REVIEW_FLAGS')
    for role,row in plan['required_refs'].items():need(equal(row,table[row['path']]),'REQUIRED_ROLE_IN_FROZEN_HASH_CLOSURE_'+role)
    need(plan['data_custody_mode']=='REUSE_E44_EXPOSED_DEV_ASSETS'and type(plan['feature_vault_origin_epoch'])is int and plan['feature_vault_origin_epoch']==44 and plan['feature_vault_origin_kind']==ORIGIN_KIND,'EXACT_INHERITED_OPAQUE_DEV_ROUTE')
    need(P+'OPERATIONAL_BINDING.v1.json'in table,'SOURCE_FROZEN_CURRENT_OPERATIONAL_BINDING');op_ref=table[P+'OPERATIONAL_BINDING.v1.json'];need(equal(plan['operational_binding'],op_ref),'PLAN_EXACT_FROZEN_OPERATIONAL_BINDING');op=checked(op_ref)
    need(type(op['epoch'])is int and op['epoch']==47 and type(op['generation'])is int and op['generation']==12 and op['source_checkpoint']==BASE and op['workdir']==str(W)and equal(op['owner'],{'path':str(W/'owner.json'),'bytes':OWNER_BYTES,'sha256':OWNER_SHA}),'CURRENT_OPERATIONAL_BINDING_METADATA_OWNER')
    need(op['scope']=='NEW_EPOCH47_SOURCE_AND_FINAL_ONE_DEV_BATCH'and op['retired_epoch46_science_immutable']is True,'CURRENT_OPERATIONAL_BINDING_DISTINCT_EPOCH_SCOPE')
    need(equal(op['owner_review'],{'path':'/workspace/ruvector-e47-audit/GUARDIAN12_ACTUAL_HELD_INDEPENDENT.v1.json','bytes':7771,'sha256':'887c707506f3170d3f7f202d60717f00dc54c12da04f85b07c18914dd7d664df'}),'CURRENT_OPERATIONAL_BINDING_EXACT_HELD_OWNER_REVIEW')
    owner_review=checked(op['owner_review'],public=False)
    need(owner_review['checks_passed']is True and owner_review['decision']=='APPROVED_HELD_GUARDIAN12_CURRENT_OWNER_AND_EMPTY_OLD_SCOPES'and type(owner_review['epoch'])is int and owner_review['epoch']==47 and type(owner_review['generation'])is int and owner_review['generation']==12 and equal(owner_review['owner'],op['owner']),'INDEPENDENT_HELD_OWNER_REVIEW_EXACT_IDENTITY')
    need(all(owner_review[k]is True for k in ['all_old_owned_process_groups_have_no_live_members','independent_same_inode_nonblocking_FLOCK_denied','no_release_requested_or_recorded']),'INDEPENDENT_HELD_OWNER_REVIEW_REQUIRED_FLAGS')
    compact=checked(plan['compact_evidence_policy']);need(equal(plan['compact_evidence_policy'],table[plan['compact_evidence_policy']['path']])and compact['epoch']==47 and compact['kind']==KIND and compact['source_checkpoint']==BASE and compact['full_prompt_token_cap']==320 and compact['server_context_size']==512 and compact['packing_policy']==plan['packing_policy']and compact['allow_duplicate_windows']is False and compact['allow_source_truncation']is False,'SOURCE_FROZEN_COMPACT_POLICY_DOCUMENT')
    return plan,freeze,root,flags

def owner_fence(plan,slot):
    need(equal(plan['owner_ref'],{'path':'owner.json','bytes':OWNER_BYTES,'sha256':OWNER_SHA})and equal(slot['owner_ref'],{'path':str(W/'owner.json'),'bytes':OWNER_BYTES,'sha256':OWNER_SHA}),'CANONICAL_RELATIVE_OWNER_AND_ABSOLUTE_SLOT_REFERENCE')
    owner_ref={'path':str(W/'owner.json'),'bytes':OWNER_BYTES,'sha256':OWNER_SHA};owner=checked(owner_ref,public=False)
    need(owner['pid']==OWNER_PID and owner['startticks']==OWNER_TICKS and owner['generation']==12 and time.time()<owner['expires_unix']and not(W/'release.request').exists(),'CURRENT_GUARDIAN12_IDENTITY_UNEXPIRED_UNRELEASED')
    s=(Path('/proc')/str(OWNER_PID)/'stat').read_text().rsplit(')',1)[1].split();need(s[0]not in ['Z','X']and int(s[19])==OWNER_TICKS,'CURRENT_GUARDIAN12_STABLE_LIVE_STARTTICKS')
    lock=Path(f'/proc/{OWNER_PID}/fd/3').stat();need((lock.st_dev,lock.st_ino)==(owner['lock_device'],owner['lock_inode'])==(33,13626),'CURRENT_GUARDIAN12_SAME_ORIGINAL_LOCK_INODE')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==owner['kernel_boot_id']and os.readlink(f'/proc/{OWNER_PID}/ns/pid')==owner['PID_namespace'],'GUARDIAN12_CURRENT_BOOT_NAMESPACE')
    held=False
    for line in Path('/proc/locks').read_text().splitlines():
        f=line.split()
        if len(f)>=6 and f[1:5]==['FLOCK','ADVISORY','WRITE',str(OWNER_PID)]:
            major,minor,inode=f[5].split(':');held=(os.makedev(int(major,16),int(minor,16)),int(inode))==(33,13626)
    need(held,'CURRENT_GUARDIAN12_OS_FLOCK_HELD')
    return {'pid':OWNER_PID,'startticks':OWNER_TICKS,'generation':12,'state':s[0],'same_lock_inode_held':True,'unexpired':True}

def marker_from_source(plan,freeze):
    row=next(r for r in freeze['files']if r['path']==A+'e47_materialize.py');canonical(row);p=regular(ROOT/row['path']);need(p.is_relative_to(ROOT)and 'private'not in p.parts,'PUBLIC_CUSTODY_SOURCE_AST_ONLY')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb')as f:
        before=os.fstat(f.fileno());raw=f.read(row['bytes']+1);after=os.fstat(f.fileno())
    sig=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode)
    need(sig(before)==sig(after)and len(raw)==row['bytes']and hashlib.sha256(raw).hexdigest()==row['sha256'],'SOURCE_AUTHENTICATED_CUSTODY_AST_BYTES')
    tree=ast.parse(raw);func=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='materialize')
    calls=[n for n in ast.walk(func)if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and isinstance(n.func.value,ast.Name)and n.func.value.id=='F'and n.func.attr=='put'and len(n.args)==2 and isinstance(n.args[0],ast.Name)and n.args[0].id=='marker']
    need(len(calls)==1 and isinstance(calls[0].args[1],ast.Dict),'EXACT_ONCE_CUSTODY_MARKER_DICT_EMITTER')
    names={'policy_ref':plan['materialization_policy'],'seal_ref':plan['predataseal']}
    def value(node):
        if isinstance(node,ast.Constant)and type(node.value)in(str,int,bool,type(None)):return node.value
        if isinstance(node,ast.Dict):return {value(k):value(v)for k,v in zip(node.keys,node.values)}
        if isinstance(node,ast.Name)and node.id in names:return names[node.id]
        if isinstance(node,ast.Attribute)and isinstance(node.value,ast.Name)and node.value.id=='F'and node.attr in['KIND','ORIGIN_KIND']:return KIND if node.attr=='KIND'else ORIGIN_KIND
        raise ValueError('UNEXPECTED_SOURCE_MARKER_AST_NO_EXECUTION_FALLBACK')
    out=value(calls[0].args[1]);expected={'schema_version':1,'epoch':47,'kind':KIND,'phase':'dev','policy':plan['materialization_policy'],'source_seal':plan['predataseal'],'automatic_retry':False,'opaque_reuse_function_calls':1,'semantic_gold_values_decoded':0}
    need(set(expected)<=set(out)<=set(expected)|{'feature_vault_origin_epoch','feature_vault_origin_kind'}and all(equal(out[k],v)for k,v in expected.items()),'SOURCE_MARKER_CONTRACT_TYPE_EXACT')
    if 'feature_vault_origin_epoch'in out:need(type(out['feature_vault_origin_epoch'])is int and out['feature_vault_origin_epoch']==44,'SOURCE_MARKER_ORIGIN_EPOCH44')
    if 'feature_vault_origin_kind'in out:need(out['feature_vault_origin_kind']==ORIGIN_KIND,'SOURCE_MARKER_ORIGINAL_KIND')
    return out


def audit(x,input_ref):
    need(not(OWN/'ACTUAL_POSTDATA_AUDIT_ATTEMPT.v2.json').exists()and not(OWN/'ACTUAL_DATA_ADMISSION_INDEPENDENT.v2.json').exists(),'ONE_EXPLICIT_ACTUAL_POSTDATA_CHECKER_INVOCATION')
    emit(OWN/'ACTUAL_POSTDATA_AUDIT_ATTEMPT.v2.json',{'schema_version':1,'epoch':47,'input':input_ref,'actual_checker_invocations':1,'automatic_retry':False,'target_calls':0})
    plan,freeze,root,flags=frozen(x);pr=x['source_plan'];sf=x['source_freeze'];ps=pr['sha256'];fs=sf['sha256'];data_ref=x['data_admission'];data=checked(data_ref);envelope(data)
    need(data['status']=='READY_REUSED_EXPOSED_DEV_FEATURES_AND_OPAQUE_VAULT'and data['errors']==[]and equal(data['selected_ids'],CASES),'ACTUAL_SUCCESSFUL_ALL12_OPAQUE_DATA_REPORT')
    need(data['source_checkpoint']==BASE and data['source_plan_sha256']==ps and data['source_freeze_sha256']==fs and re.fullmatch('[0-9a-f]{40}',data['source_commit'])is not None and data['source_commit']!=BASE,'ACTUAL_DATA_NEW_SOURCE_PLAN_SF_BINDING')
    ev=data['evidence'];need(equal(ev['source_plan'],pr)and equal(ev['policy'],plan['materialization_policy'])and equal(ev['source_seal'],plan['predataseal']),'ACTUAL_DATA_EXACT_PLAN_POLICY_SEAL_EVIDENCE')
    source=checked(ev['source_admission']);envelope(source);need(ev['source_admission']['path']==plan['source_admission_path']==P+'SOURCE_ADMISSION.json'and source['checks_passed']is True and source['verified_actual_remote_readback']is True and source['actual_source_commit']==source['published_source_commit']==source['source_commit']==data['source_commit']and source['plan_sha256']==source['source_plan_sha256']==ps and source['source_freeze_sha256']==fs,'ACTUAL_NEW_SOURCE_ADMISSION_ALIAS_AND_HASH_CHAIN')
    ind=checked(source['independent_actual_source_readback']);envelope(ind);need(ind['checks_passed']is True and ind['verified_actual_remote_readback']is True and ind['commit']==data['source_commit']and ind['source_plan_sha256']==ps and ind['source_freeze_sha256']==fs and ind['tree_sha']==source['tree_sha'],'INDEPENDENT_ACTUAL_NEW_SOURCE_READBACK_CHAIN')
    approval=checked(ev['root_approval']);envelope(approval);slot=plan['worker_slot_reservation'];need(all(equal(slot,v['worker_slot_reservation'])for v in [source,ind,approval,data,root]),'TYPE_EXACT_PLAN_SOURCE_READBACK_ROOT_APPROVAL_DATA_SLOT_CHAIN')
    need(type(slot['epoch'])is int and slot['epoch']==47 and slot['kind']==KIND and slot['phase']=='dev'and type(slot['generation'])is int and slot['generation']==12 and slot['pid']==OWNER_PID and slot['startticks']==OWNER_TICKS and type(slot['reserved_worker_slots'])is int and slot['reserved_worker_slots']==1 and slot['permanently_burned_at_SOURCE_publication']is True and slot['owner_sha256']==OWNER_SHA and re.fullmatch('[0-9a-f]{64}',slot['reservation_token'])is not None,'GUARDIAN12_EXACT_ONE_PERMANENTLY_BURNED_WORKER_CAPABILITY')
    need(slot['currentepoch_new_invocations_after_owner_loss_forbidden']is True and slot['missing_receipt_after_owner_loss']=='UNKNOWN_PERMANENTLY_NO_RERUN','NO_OWNER_LOSS_REPLAY_OR_MISSING_RECEIPT_RETRY')
    owner=owner_fence(plan,slot)
    need(approval['source_checkpoint']==BASE and approval['source_commit']==data['source_commit']and approval['root_one_custodian_authorized']is True and approval['all_candidate_and_custody_source_frozen_before_data_access']is True and equal(approval['source_plan'],pr)and equal(approval['source_admission'],ev['source_admission'])and approval['policy_sha256']==plan['materialization_policy']['sha256']and approval['predataseal_sha256']==plan['predataseal']['sha256'],'ROOT_ONCE_DATA_APPROVAL_EXACT_FROZEN_SOURCE')
    review=checked(approval['independent_source_review']);need(review['checks_passed']is True and review['policy_sha256']==plan['materialization_policy']['sha256']and review['source_seal_sha256']==plan['predataseal']['sha256']and all(review.get(flag)is True for flag in flags),'INTEGRATED_SOURCE_REVIEW_ALL_ACTUAL_FLAGS_AND_DATA_SEAL')
    need(equal(approval['node_runtime_admission'],ev['node_runtime_admission']),'SAME_ROOT_DATA_NODE_METADATA_PROOF')
    node=checked(ev['node_runtime_admission']);envelope(node);manifest=checked(plan['node_runtime_manifest']);declaration={'path':NODE_PATH,'bytes':NODE_BYTES,'sha256':NODE_SHA};need(equal(manifest['executable'],declaration)and manifest['observed_local_version']=='v24.19.0'and plan['node_executable']==NODE_PATH,'PINNED_ABSOLUTE_NODE_DECLARATION_METADATA_ONLY')
    expected_node=dict(declaration,observed_local_version='v24.19.0',full_payload_hash_verified=True,ELF64_x86_64=True,native_helper_or_module_initialized=False,upstream_binary_reproducibility='NOT_ESTABLISHED_LOCAL_EXECUTABLE_PIN_ONLY')
    need(node['checks_passed']is True and node['source_commit']==data['source_commit']and node['source_plan_sha256']==ps and node['source_freeze_sha256']==fs and equal(node['node_runtime_receipt'],expected_node),'SOURCE_BOUND_NODE_HASH_ELF_METADATA_PROOF_BEFORE_DATA')
    policy=checked(plan['materialization_policy']);seal=checked(plan['predataseal']);need(policy['custody_mode']=='REUSE_E44_EXPOSED_DEV_ASSETS'and policy['feature_vault_origin_epoch']==44 and policy['feature_vault_origin_kind']==ORIGIN_KIND and policy['freshness']=='EXPOSED_DEV_FOREVER_NOT_FRESH'and seal['policy_sha256']==plan['materialization_policy']['sha256'],'FROZEN_SOURCE_OPAQUE_REUSE_POLICY_SEAL')
    need(equal(ev['prior_data_admission'],policy['prior_data_admission'])and equal(ev['prior_independent_data_review'],policy['prior_independent_data_review']),'AUTHENTICATED_ORIGIN44_PUBLIC_METADATA_REF_CHAIN')
    old=checked(policy['prior_data_admission']);oldreview=checked(policy['prior_independent_data_review']);need(old['epoch']==44 and old['status']=='READY_LABEL_BLIND_DEV_FEATURES_AND_OPAQUE_VAULT'and old['errors']==[]and old['semantic_gold_values_decoded']==0 and old['selected_raw_choice_tokens_copied']==12 and oldreview['checks_passed']is True and oldreview['semantic_gold_decodes']==0,'ORIGINAL_PUBLISHED_E44_DATA_AND_INDEPENDENT_ADMISSION')
    need(equal(old['private_features'],policy['reuse_source_features'])and equal(old['private_vault'],policy['reuse_source_vault'])and equal(oldreview['private_features_ref'],old['private_features'])and equal(oldreview['private_vault_ref'],old['private_vault'])and equal(oldreview['source_units_per_document'],COUNTS)and equal(policy['source_units_per_document'],COUNTS),'EXACT_OLD_OPAQUE_ASSET_PINS_AND_AUTHENTICATED_COUNTS_NOT_PRIVATE_PARSE')
    zero=['selected_raw_choice_tokens_copied','semantic_gold_values_decoded','feature_vault_JSON_parses','source_body_or_hypothesis_decodes','original_archive_reads','model_tokenizer_native_calls','protected_confirmation_body_or_choice_decodes'];need(all(type(data[k])is int and data[k]==0 for k in zero),'NEW_RAW_CHOICE_BODY_JSON_MODEL_GOLD_PROTECTED_COUNTS_ZERO')
    need(type(data['inherited_opaque_choice_tokens'])is int and data['inherited_opaque_choice_tokens']==12 and type(data['feature_vault_origin_epoch'])is int and data['feature_vault_origin_epoch']==44 and data['feature_vault_origin_kind']==ORIGIN_KIND and data['freshness']=='EXPOSED_DEV_FOREVER_NOT_FRESH'and data['used_confirmation_identities']==[]and equal(data['protected_confirmation_document_ids'],[62,321,2]),'INHERITED12_ORIGIN44_EXPOSED_DEV_NO_CONFIRMATION')
    stats=data['statistics'];want={'source_units_per_document':COUNTS,'unique_source_units':176,'expanded_pair_source_units':528,'expected_BGE_texts':188,'expected_BGE_forward_calls':36,'native_indexes':4,'native_queries':12};need(all(equal(stats[k],v)for k,v in want.items()),'EXACT_PUBLIC176_528_188_36_4_12_DESIGN_COUNTS_NOT_EXECUTION')
    forbidden=[W/'private/DEV_GOLD_JOINED.json',W/'private/DEV_GOLD.vault.json.DECODE_ATTEMPT.json',W/'private/GOLD_FUNCTION_ATTEMPT.json',ROOT/(A+'GOLD_JOIN_REPORT.json'),ROOT/(P+'DISPATCH_ATTEMPT.json'),ROOT/(P+'DISPATCH_RESERVATION.json'),ROOT/(P+'OUTER_RUNNER_ATTEMPT.json')]
    need(all(not p.exists()and not p.is_symlink()for p in forbidden),'NO_CURRENT_GOLD_OR_DISPATCH_BEFORE_INDEPENDENT_POSTDATA_ADMISSION')
    need({p.name for p in (W/'private').iterdir()}=={'DEV_FEATURES.json','DEV_GOLD.vault.json','DATA_MATERIALIZATION_ATTEMPT.json'},'EXACT_THREE_NEW_PRIVATE_OPAQUE_DATA_OUTPUTS_BEFORE_DISPATCH')
    output={}
    # FIRST private container access in the checker: full opaque SHA256 only.
    for role,name,size,digest in [('private_features','DEV_FEATURES.json',73969,FEATURE_SHA),('private_vault','DEV_GOLD.vault.json',1178,VAULT_SHA)]:
        expected={'path':str(W/'private'/name),'bytes':size,'sha256':digest};need(equal(data[role],expected),'NEW_OPAQUE_OUTPUT_DECLARATION_'+role);actual,_=read_file(expected['path'],max_bytes=size,parse=False,opaque=True);need(equal(actual,expected),'NEW_OPAQUE_STABLE_FULL_HASH_'+role);output[role]=actual
    # Compare exact canonical once-attempt metadata bytes without private JSON parsing.
    expected_marker=marker_from_source(plan,freeze)
    marker_bytes=json.dumps(expected_marker,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False).encode()+b'\n'
    marker_ref,_=read_file(W/'private/DATA_MATERIALIZATION_ATTEMPT.json',max_bytes=len(marker_bytes),parse=False,opaque=True)
    need(marker_ref['bytes']==len(marker_bytes)and marker_ref['sha256']==hashlib.sha256(marker_bytes).hexdigest(),'ACTUAL_EXCLUSIVE_ONCE_CUSTODY_ATTEMPT_OPAQUE_METADATA_HASH')
    need(all(not p.exists()and not p.is_symlink()for p in forbidden),'NO_STAGE_RACE_GOLD_OR_DISPATCH_AFTER_OPAQUE_HASHES');owner_fence(plan,slot)
    report={'schema_version':1,'epoch':47,'kind':KIND,'phase':'dev','checks_passed':True,'status':'READY_FOR_ONE_SOURCE_BOUND_DEV_DISPATCH_OPAQUE_REUSE_VERIFIED','source_checkpoint':BASE,'source_commit':data['source_commit'],'source_plan_sha256':ps,'source_freeze_sha256':fs,'worker_slot_reservation':slot,'data_admission':data_ref,'private_features_ref':output['private_features'],'private_vault_ref':output['private_vault'],'semantic_gold_decodes':0,'protected_unused_body_or_choice_decodes':0,'selected_raw_choice_tokens_copied':0,'inherited_opaque_choice_tokens':12,'feature_vault_origin_epoch':44,'feature_vault_origin_kind':ORIGIN_KIND,'freshness':'EXPOSED_DEV_FOREVER_NOT_FRESH','selected_ids':CASES,'protected_unused_document_ids':[62,321,2],'used_confirmation_identities':[],'source_units_per_document':COUNTS,'source_units_total':176,'unique_source_units':176,'expanded_pair_source_units':528,'expected_operation_counters':{'dev':counters()},'operation_counters_are_planned_design_not_actual_runtime_execution':True,'expected_variable_counter_keys':['local_HTTP_requests_attempted','local_HTTP_requests_completed','health_requests_attempted','health_requests_completed','prompt_tokenize_requests_attempted','prompt_tokenize_requests_completed'],'opaque_custody_attempt_markers_verified':1,'opaque_new_asset_full_hashes':2,'private_feature_vault_JSON_parses':0,'private_body_hypothesis_raw_choice_or_label_decodes':0,'private_attempt_metadata_parses':0,'private_attempt_metadata_opaque_full_hashes':1,'original_vault_or_archive_traversals':0,'model_tokenizer_native_Node_version_or_Gold_calls':0,'target_source_imports_or_functions':0,'API_calls':0,'R_writes':0,'frozen_source_rows_rehashed':len(freeze['files']),'frozen_required_source_roles':len(root['source_admission_contract']['required_roles']),'frozen_integrated_review_flags':len(flags),'raw_frozen_case_map_independently_verified':True,'guardian12_current_observation':owner,'evidence':dict(ev,source_freeze=sf,independent_actual_source_readback=source['independent_actual_source_readback'],attempt_marker=marker_ref,input=input_ref,checker=read_file(Path(__file__).absolute())[0]),'checks':list(dict.fromkeys(CHECKS)),'check_count_including_reference_metadata_checks':len(CHECKS),'dispatch_not_yet_executed':True,'scientific_quality_unmeasured':True,'native_addon_ABI_unmeasured':True,'scope':'Independent local public-evidence readback and stable opaque hashes of two new outputs. All corpus counts inherit immutable licensed E44 public metadata. No private JSON/container/header/label parse or target execution. This report creates no extra slot, retry, Gold, confirmation, model, promotion or publication authority.'}
    return emit(OWN/'ACTUAL_DATA_ADMISSION_INDEPENDENT.v2.json',report)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--input');p.add_argument('--expected-input-sha256');a=p.parse_args()
    if a.prepare:
        need(a.input is None and a.expected_input_sha256 is None,'PREPARATION_HAS_NO_ACTUAL_INPUT');print(json.dumps(prepare(),sort_keys=True));return
    need(a.input is not None and a.expected_input_sha256 is not None and re.fullmatch('[0-9a-f]{64}',a.expected_input_sha256)is not None,'ROOT_FOLLOWUP_EXACT_INPUT_REQUIRED');r,x=read_file(a.input,parse=True);need(r['sha256']==a.expected_input_sha256,'ROOT_EXACT_ACTUAL_INPUT_SHA256');print(json.dumps(audit(x,r),sort_keys=True))
if __name__=='__main__':main()
