"""Independent label-free document identity qualification. Standard library only.

Reads sealed engineering outputs; never imports worker/model/tokenizer/native code
or reads source annotation choices. Original LoRA data-admission HOLD is immutable.
"""
import argparse
import base64
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
from identity_common import (KIND,require,read,identity,sha,canonical,model_text,
                             finite,cosine,quantile,write_new)
from audit_identity_inputs import audit as audit_inputs

# All scientific output JSON is strict: nonfinite unused fields are also errors.
_plain_read=read
def read(path,expected_sha=None,expected_bytes=None):
    value=_plain_read(path,expected_sha,expected_bytes)
    def check(item):
        if type(item)is float:require(math.isfinite(item),'Nonfinite JSON number')
        elif isinstance(item,dict):
            for child in item.values():check(child)
        elif isinstance(item,list):
            for child in item:check(child)
    check(value);return value

INPUT_SHA='ced6f3969f72f4f07da570f42ed62d439e5db1b440393688e8496acde731f4c3'
ORACLE_SHA='7085edc653ba4ad218260a4a2673f7b59e02e940157a83b3a906ec7b6a55d7d8'
CATALOG_SHA='11b6b56c6ab7540cc6d05b17f31178fc543e1417708eff9ca48ca1d07104bbdc'
PROTOCOL_SHA='d8bd0f3d271a5e5a0902d481886c3e9af858e36e62eb2b9c719218c6cb7aaef2'
SCHEMA_BINDING_SHA='c5da0e9703ce2c038f8d040bd2080510de65d2e81209918550f89aa191db4901'
NATIVE_K=16
PUBLICATION_HELPER_SHA='808026af97018b4b77c18ed15da91c8b713b667d9ea3ff38cf1cc44154b760ff'
PUBLICATION_COMMON_SHA='b44424f843588abc73b71fe639867c2ad4cab09ccae705ef918dc6a75269c1d2'

def project_ref(root,path):
    root,path=Path(root).resolve(),Path(path).resolve()
    require(path.is_relative_to(root),'Evidence must be within current project')
    result=identity(path);result['path']=str(path.relative_to(root));return result

def resolve_ref(root,pin):
    path=Path(pin['path'])
    if not path.is_absolute():path=Path(root)/path
    require(identity(path)['bytes']==pin['bytes']and identity(path)['sha256']==pin['sha256'],'Evidence identity mismatch')
    return path

def check_pin(path,pin):
    actual=identity(path)
    require(actual['bytes']==pin['bytes']and actual['sha256']==pin['sha256'],'Pinned artifact changed: '+str(path))

def load_context(root):
    here=Path(root)/'experiments/sota-2026-10-22/audit/epoch29/identity'
    paths={k:here/v for k,v in {'protocol':'protocol.json','inputs':'data/engineering-inputs.json',
          'oracle':'data/identity-oracle.json','catalog':'data/canonical-catalog.json',
          'schema_binding':'schema-bindings-v1.json'}.items()}
    fixed={'protocol':PROTOCOL_SHA,'inputs':INPUT_SHA,'oracle':ORACLE_SHA,'catalog':CATALOG_SHA,'schema_binding':SCHEMA_BINDING_SHA}
    data={k:read(p,fixed[k])for k,p in paths.items()}
    inp_audit=audit_inputs(paths['protocol'],paths['inputs'],paths['oracle'],paths['catalog'])
    require(inp_audit['corpus_count']==261 and inp_audit['query_count']==262,'Frozen corpus/query size changed')
    require(not inp_audit['protected_alias_exclusions'],'Frozen protected exclusion changed')
    return here,paths,data,inp_audit

def matrix_block(block):
    require(type(block)is dict,'Missing lossless vector block')
    require(block['encoding']=='base64'and block['dtype']=='float32le','Vector encoding mismatch')
    rows,cols=block['shape'];require(type(rows)is int and rows>0 and cols==384,'Vector shape mismatch')
    require(type(block['data_base64'])is str,'Missing base64 vectors')
    encoded=block['data_base64'];raw=base64.b64decode(encoded,validate=True)
    require(base64.b64encode(raw).decode()==encoded,'Noncanonical base64 vectors')
    require(len(raw)==block['bytes']==rows*cols*4 and sha(raw)==block['sha256'],'Vector byte/hash mismatch')
    values=struct.unpack('<'+'f'*(rows*cols),raw)
    require(all(math.isfinite(v)for v in values),'Nonfinite source float32 vectors')
    result=[list(values[i*cols:(i+1)*cols])for i in range(rows)]
    for row in result:
        norm=math.sqrt(math.fsum(v*v for v in row));require(abs(norm-1)<=1e-5,'Vector not normalized')
    receipts=[{'dimensions':cols,'dtype':'float32le','sha256':sha(raw[i*cols*4:(i+1)*cols*4])}for i in range(rows)]
    return result,receipts

def exact_dense(query_id,corpus_ids,vectors):
    return sorted([{'document_id':i,'cosine':cosine(vectors[query_id],vectors[i])}
                   for i in corpus_ids if i!=query_id],key=lambda r:(-r['cosine'],r['document_id']))

def metrics(rows,arm):
    positive=[r for r in rows if r['true_alias_document_ids']]
    hits=sum(bool(set(r['true_alias_document_ids'])&set(r[arm+'_top16_ids']))for r in positive)
    pairs=sum(len(r['true_alias_document_ids'])for r in rows)
    pair_hits=sum(len(set(r['true_alias_document_ids'])&set(r[arm+'_top16_ids']))for r in rows)
    confirmed=sum(bool(r[arm+'_confirmed_alias_ids'])for r in rows)
    return {'queries':len(rows),'positive_queries':len(positive),'positive_query_hits_at16':hits,
            'any_alias_query_recall_at16':hits/len(positive)if positive else None,
            'true_nonself_alias_pairs':pairs,'alias_pairs_found_at16':pair_hits,
            'paired_alias_target_recall_at16':pair_hits/pairs if pairs else None,
            'exact_hash_confirmed_queries':confirmed,'UNRESOLVED_queries':len(rows)-confirmed,
            'false_exact_hash_confirmations':0,'scope':'Finite frozen exposed261corpus+known548query;1positivequery, no generalization claim'}

def replay_queries(queries,oracle,corpus,vectors,receipts):
    require(type(queries)is list and len(queries)==262,'Complete262queries required')
    qids=corpus+[548];require([q['document_id']for q in queries]==qids,'Query identity/order mismatch')
    rows=[]
    for q,truth in zip(queries,oracle['query_records']):
        did=q['document_id'];require(q['normalized_document_sha256']==truth['normalized_document_sha256'],'Query source hash mismatch')
        require(q['query_id']=='document:'+str(did),'Query machine identity mismatch')
        require(q['exclude_document_id']==(did if did in corpus else None),'Self exclusion policy mismatch')
        require(q['authoritative_alias_document_ids']==truth['true_alias_document_ids'],'Worker oracle mismatch')
        native=q['native'];raw_ids=native['raw_ids'];k=min(17 if did in corpus else 16,len(corpus))
        require(native['requested_k']==k,'Native fetch depth changed')
        require(len(raw_ids)==len(set(raw_ids))==k,'Native raw hit count/uniqueness mismatch')
        # Native IDs and lossless compact receipt representation are checked by
        # the native-artifact adapter below before this replay is called.
        require(all(i in corpus for i in raw_ids),'Native unknown corpus ID')
        retained=[i for i in raw_ids if i!=did][:16]
        require(native['filtered_top16_ids']==retained and len(retained)==16,'Native filtering/order mismatch')
        require(finite(native['query_seconds'])and native['query_seconds']>=0,'Invalid native query timing')
        dense=q['dense'];expected=exact_dense(did,corpus,vectors);actual=dense['top16']
        require(dense['candidate_count']==len(expected)and len(actual)==16,'Brute corpus count mismatch')
        require([r['document_id']for r in actual]==[r['document_id']for r in expected[:16]],'Exact f32 cosine/numeric-ID-tie top16 mismatch')
        require(all(finite(a['cosine'])and abs(a['cosine']-e['cosine'])<=1e-12 for a,e in zip(actual,expected)),'Brute cosine replay mismatch')
        require(finite(dense['elapsed_seconds'])and dense['elapsed_seconds']>=0,'Invalid brute timing')
        aliases=truth['true_alias_document_ids'];dense_ids=[r['document_id']for r in actual]
        nconfirmed=[i for i in retained if i in aliases];dconfirmed=[i for i in dense_ids if i in aliases]
        require(q['native_confirmed_alias_ids']==nconfirmed and q['dense_confirmed_alias_ids']==dconfirmed,'Hash confirmation replay mismatch')
        require(q['native_status']==('CONFIRMED_NORMALIZED_ALIAS'if nconfirmed else'UNRESOLVED'),'Native status mismatch/CLEAN forbidden')
        require(q['dense_status']==('CONFIRMED_NORMALIZED_ALIAS'if dconfirmed else'UNRESOLVED'),'Brute status mismatch/CLEAN forbidden')
        require(not q.get('near_pairs',[]),'Near-duplicate threshold disabled')
        rows.append({'document_id':did,'true_alias_document_ids':aliases,'native_top16_ids':retained,
                     'dense_top16_ids':dense_ids,'native_confirmed_alias_ids':nconfirmed,'dense_confirmed_alias_ids':dconfirmed,
                     'top16_intersection':len(set(retained)&set(dense_ids)),
                     'native_query_seconds':native['query_seconds'],'dense_query_seconds':dense['elapsed_seconds'],
                     'brute_16th_cosine':expected[15]['cosine'],
                     'native_members_in_brute_tie_aware_top16':sum(cosine(vectors[did],vectors[i])>=expected[15]['cosine']-1e-12 for i in retained)})
    return rows

def replay_native_artifact(raw,native,corpus,qids,receipts,vector_pin):
    require(native['epoch']==29 and native['kind']==KIND,'Native artifact scope mismatch')
    require(native['package_version']=='0.1.33'and native['platform_package_version']=='0.1.31'
            and native['binary_version']=='2.3.0','Actual original RuVectorcore version mismatch')
    require(native['native_binary_sha256']=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e','Actual native binary identity mismatch')
    require(native['bundle_sha256']==vector_pin['sha256']and native['initialized_vectors']==261,'Native bundle/index closure mismatch')
    require(not native['errors']and native['original_nonvector_fields_preserved']is True
            and native['original_score_not_renamed']is True,'Native source receipts/errors invalid')
    require(len(native['queries'])==len(raw['queries'])==262,'Native query artifact incomplete')
    metadata_sha=sha(b'{"present":false}')
    index={did:i for i,did in enumerate(qids)}
    for q,n in zip(raw['queries'],native['queries']):
        require(q['native']==n,'Main raw/native literal query artifact mismatch')
        require(n['document_id']==q['document_id'],'Native query identity mismatch')
        require(n['native_order_used_without_replacement']is True,'Native source order not retained')
        require([int(h['id'])for h in n['raw_hits']]==n['raw_ids'],'Native ID/hit order mismatch')
        require(n['excluded_self_hit_ids']==[i for i in n['raw_ids']if i==q['document_id']],'Native self-hit receipt mismatch')
        for hit in n['raw_hits']:
            require(type(hit['id'])is str and str(int(hit['id']))==hit['id'],'Native ID must be canonical decimal string')
            did=int(hit['id']);require(did in corpus,'Native hit outside corpus')
            require(finite(hit['score']),'Nonfinite original native score')
            require(type(hit['raw_keys'])is list and len(hit['raw_keys'])==len(set(hit['raw_keys'])),'Missing raw native key receipt')
            require({'id','score','vector'}<=set(hit['raw_keys']),'Native source vector keys absent')
            v=hit['vector_receipt'];source=receipts[index[did]]
            require(v['source_vector_row']==index[did]and v['dimensions']==384 and v['dtype']=='float32le','Hit/source row/dtype mismatch')
            require(v['sha256']==v['source_sha256']==source['sha256']and v['source_equal_before_stripping']is True,'Native-returned vector/source byte receipt mismatch')
            m=hit['metadata_receipt']
            require(m=={'present':False,'canonical_json':'{"present":false}','sha256':metadata_sha,'source_equal_before_stripping':True},'Native absent-metadata receipt mismatch')

def counter_checks(counters):
    require(type(counters)is dict and counters,'Missing actual counters')
    expected={}
    for prefix,value in [('BGE_initializations',1),('ORT_sessions',1),('tokenizer_initializations',1),
        ('tokenizer_full_encoding_calls',33),('tokenizer_capped_encoding_calls',33),
        ('tokenizer_full_texts',262),('tokenizer_capped_texts',262),('BGE_forward_calls',33),('BGE_texts',262),
        ('native_helper_starts',1),('native_binary_loads',1),('native_index_initializations',1),
        ('native_insertions',261),('native_len_calls',2),('native_version_calls',1),('native_queries',262),
        ('dense_queries',262),('dense_cosines',68121)]:
        for suffix in ['attempted','completed']:expected[prefix+'_'+suffix]=value
    expected.update(document_records_completed=262,query_records_completed=262,
                    native_hits_retained=4192,dense_hits_retained=4192,native_hit_source_validations=4453)
    for key,value in expected.items():
        require(type(counters.get(key))is int and counters[key]==value,'Actual counter mismatch: '+key)
    return expected

def load_publication_helper(root):
    folder=Path(root)/'experiments/sota-2026-10-22/epoch29/publication'
    helper=folder/'stage_publication_v1.py';common=folder/'publication_common_v1.py'
    require(identity(helper)['sha256']==PUBLICATION_HELPER_SHA,'Frozen publication helper changed')
    require(identity(common)['sha256']==PUBLICATION_COMMON_SHA,'Frozen publication common changed')
    old_path=list(sys.path)
    try:
        sys.path.insert(0,str(folder))
        spec=importlib.util.spec_from_file_location('epoch29_publication_helper_independent',helper)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    finally:sys.path[:]=old_path
    return module,helper,common

def selected_raw(raw_path,execution):
    """Honor exact captured final/partial/UNKNOWN seals without hiding valid outputs."""
    raw_path=Path(raw_path).resolve();folder=raw_path.parent
    final=folder/'raw.json';partial=folder/'raw.partial.json'
    parsed={};parse_errors={};pins={}
    for name,path in [('raw.json',final),('raw.partial.json',partial)]:
        if path.exists():
            pins[name]=identity(path)
            try:parsed[name]=read(path)
            except (ValueError,UnicodeError)as error:parse_errors[name]={'type':type(error).__name__,'message':str(error)}
    source=execution['raw_operation_counters_source']
    require(source in ['raw.json','raw.partial.json','UNKNOWN'],'Unknown raw receipt discriminator')
    if 'raw.json'in parsed:require(source=='raw.json','Cannot hide parseable final raw')
    if source=='raw.json':
        require('raw.json'in parsed and type(parsed['raw.json'])is dict,'Final raw missing/malformed')
        pin=pins['raw.json'];require(pin['bytes']==execution['raw_bytes']and pin['sha256']==execution['raw_sha256'],'Final raw capture seal mismatch')
        require(execution['operation_counts_complete']is True and execution['backend_execution_since_checkpoint']=='NOT_APPLICABLE_FINAL_RAW','Final counter scope mismatch')
        return parsed['raw.json'],final,{'mode':'FINAL','parse_errors':parse_errors}
    require(execution['status']!='WORKER_COMPLETED'and execution['operation_counts_complete']is False and execution['backend_execution_since_checkpoint']=='UNKNOWN','Partial/absent failure scope invalid')
    if 'raw.json'in pins:
        require(pins['raw.json']['bytes']==execution['raw_bytes']and pins['raw.json']['sha256']==execution['raw_sha256'],'Malformed final capture seal mismatch')
        require('raw.json'in parse_errors,'Valid final cannot be hidden')
    else:require(execution['raw_bytes']is None and execution['raw_sha256']is None,'Missing final has fabricated seal')
    if source=='raw.partial.json':
        require('raw.partial.json'in parsed and type(parsed['raw.partial.json'])is dict,'Missing/malformed partial raw')
        pin=pins['raw.partial.json'];require(pin['bytes']==execution['partial_raw_bytes']and pin['sha256']==execution['partial_raw_sha256'],'Partial raw capture seal mismatch')
        require(parsed['raw.partial.json']['counters']==execution['raw_operation_counters'],'Partial captured counter mismatch')
        return parsed['raw.partial.json'],partial,{'mode':'PARTIAL','parse_errors':parse_errors,'unparsed_final_raw':pins.get('raw.json')}
    require('raw.partial.json'not in parsed or type(parsed['raw.partial.json'])is not dict
            or type(parsed['raw.partial.json'].get('counters'))is not dict,'Cannot hide valid partial counters')
    require(execution['raw_operation_counters']is None,'Absent raw operation counts must be UNKNOWN')
    # A known malformed final artifact still has a captured byte identity even
    # though its parsed operation evidence remains UNKNOWN. Preserve that ref;
    # only true artifact absence yields a null evidence.raw publication binding.
    return None,(final if 'raw.json'in pins else None),{'mode':'UNKNOWN','parse_errors':parse_errors,'unparsed_final_raw':pins.get('raw.json')}

def verify_plan_sources(root,plan_path,plan):
    require(plan['epoch']==29 and plan['kind']==KIND,'Wrong source plan')
    require(plan['source_checkpoint']=='07a2cbe78fdee78a8c9bca2aeb64bc9746481ba0'
            and plan['actual_project']==str(Path(root).resolve()),'Wrong current source/checkpoint root')
    require(plan['data_roles']=={'train':[],'dev':[],'calibration':[],'confirmation':[]},'Scientific roles must be empty')
    pins=plan['pins'];require(len(pins)==len({p['path']for p in pins}),'Duplicate source pins')
    by_path={p['path']:p for p in pins}
    for pin in pins:
        require(not Path(pin['path']).is_absolute()and '..'not in Path(pin['path']).parts,'Unsafe source pin')
        check_pin(Path(root)/pin['path'],pin)
    own=Path(__file__).resolve();ownrel=str(own.relative_to(Path(root).resolve()))
    require(ownrel in by_path,'Executed public scorer must be frozen in source plan')
    for name in ['identity_common.py','audit_identity_inputs.py','schema-bindings-v1.json']:
        relative=str((own.parent/name).relative_to(Path(root).resolve()))
        require(relative in by_path,'Scorer dependency unpinned')
    require(plan['engineering_inputs_sha256']==INPUT_SHA,'Plan input bank changed')
    freeze=read(Path(root)/plan['source_freeze_path'],plan['source_freeze_sha256'])
    require(freeze['epoch']==29 and freeze['kind']==KIND,'Wrong source freeze')
    for pin in freeze['entries']:require(by_path.get(pin['path'])==pin,'Source-freeze entry absent/different from plan')
    limits=plan['limits']
    for key,value in {'owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,
                      'native_corpus_batches':0,'engineering_batches':1,'paid_calls':0,'GPU_calls':0}.items():
        require(limits[key]==value,'Fixed limit changed: '+key)
    return {'pins_verified':len(pins),'source_freeze':identity(Path(root)/plan['source_freeze_path'])}

def closure(execution):
    require(execution['status']=='WORKER_COMPLETED'and execution['exit_code']==0,'Worker failed/partial: qualification unavailable')
    require(execution['worker_attempts_reserved']==execution['verified_worker_starts']==1,'Exactly one actual reserved worker required')
    require(execution['launcher_error']is None and not execution['cleanup_errors'],'Unexpected launcher/cleanup errors')
    require(execution['stdout_stderr_capture_completed']is True,'Output capture incomplete')
    require(execution['owned_live_processes_closed']is True and execution['owned_live_group_members']==[],'Owned process group not closed')
    require(execution['CPU_affinity']==[0,1]and finite(execution['wall_seconds_including_init_cleanup'])
            and 0<execution['wall_seconds_including_init_cleanup']<=600,'CPU/wall budget invalid')
    require(execution['source_plan_unchanged']is True,'Frozen source/plan changed')
    worker=execution['worker_identity'];pid=worker['pid'];ticks=worker.get('ticks',worker.get('startticks'))
    pgid=worker['pgid'];sid=worker['sid'];remaining=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            fields=(path/'stat').read_text().rsplit(')',1)[1].split()
            if int(fields[2])==pgid or int(fields[3])==sid:
                remaining.append({'pid':int(path.name),'state':fields[0],'pgid':int(fields[2]),'sid':int(fields[3]),'ticks':int(fields[19])})
        except (OSError,ValueError,IndexError):pass
    require(not remaining,'Physical owned group/session remains live')
    return {'worker_pid':pid,'worker_startticks':ticks,'owned_group':pgid,'owned_session':sid,'remaining_members':remaining}

def replay_documents(raw_documents,inputs,corpus,receipts):
    expected=inputs['documents']+[inputs['query']]
    require([d['document_id']for d in raw_documents]==corpus+[548],'Document provenance order changed')
    truncated=0
    for j,(d,inp)in enumerate(zip(raw_documents,expected)):
        for key in ['document_id','normalized_document_sha256','source_document_sha256','source_utf8_bytes','bge_input_sha256','bge_input_utf8_bytes']:
            require(d[key]==inp[key],'Document source/BGE-input provenance mismatch: '+key)
        require(d['vector_sha256']==receipts[j]['sha256'],'Document/source vector hash mismatch')
        raw_count,used=d['raw_tokens'],d['used_tokens'];ids=d['used_token_ids'];mask=d['used_attention_mask'];padded=d['padded_token_ids']
        require(type(raw_count)is int and type(used)is int and raw_count>=2 and used==min(raw_count,256),'Actual token count/cap mismatch')
        require(d['max_tokens']==256 and d['truncated']==(raw_count>256),'Truncation disclosure mismatch')
        require(len(ids)==used and ids[0]==101 and ids[-1]==102 and all(type(i)is int and i>=0 for i in ids),'Actual token IDs invalid')
        require(padded[:used]==ids and all(i==0 for i in padded[used:]),'Padding/source token receipt mismatch')
        require(mask==[1]*used+[0]*(len(padded)-used)and d['padded_tokens']==len(padded)-used,'Actual mask receipt mismatch')
        require(d['full_input_bytes_are_hashed_but_tokens_after256_are_not_attended']is True,'Fulltext attention overclaim')
        require(finite(d['actual_vector_norm'])and abs(d['actual_vector_norm']-1)<=1e-5,'Vector norm receipt invalid')
        truncated+=int(d['truncated'])
    return {'documents':len(expected),'truncated_texts':truncated,'max_BGE_tokens':256,
            'full_document_identity_does_not_establish_full_semantic_attention':True}

def cpu_checks(root,raw,execution):
    guard=raw['worker_cpu_guard_preexec']
    require(guard==execution['worker_cpu_guard_preexec'],'Worker/outer CPU guard receipt mismatch')
    require(raw['worker_cpu_guard_preexec_artifact']==execution['worker_cpu_guard_preexec_artifact'],'Worker/outer CPU guard artifact mismatch')
    guard_path=resolve_ref(root,execution['worker_cpu_guard_preexec_artifact'])
    require(read(guard_path)==guard,'Actual CPU guard artifact value mismatch')
    require(guard['status']=='CPU_GUARD_INSTALLED_BEFORE_EXEC'and guard['CPU_affinity']==[0,1],'Kernel CPU guard not installed')
    require(guard['denied_syscalls']==[203,1073742027]and guard['denial_errno']==1,'CPU guard policy changed')
    status=guard['actual_proc_status']
    require(status['NoNewPrivs']=='1'and status['Seccomp']=='2'and status['Cpus_allowed_list']=='0-1','Actual kernel guard/affinity receipt mismatch')
    require(guard['inherited_by_all_future_threads_and_exec']is True and guard['global_kernel_configuration_changed']is False,'CPU guard scope invalid')
    require(execution['actual_denied_affinity_syscalls']is None,'Unobserved real denied-call count must remain UNKNOWN')
    def visit(value):
        if isinstance(value,dict):
            if 'observed_thread_affinities'in value:
                for row in value['observed_thread_affinities']:
                    require(row['observed_affinity_within_CPU0_1']is True,'Observed thread outside CPU0,1')
            for item in value.values():visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(raw.get('progress',[]));visit(raw.get('resources',{}));visit(raw.get('initialization',{}))
    return {'kernel_worker_CPU_guard_verified':True,'scope':'Filter inherited by Python worker/all future threads/exec; observed task snapshots checked; real denied-call count UNKNOWN'}

def runtime_provenance(root,raw,plan,vector_pin):
    bge=raw['BGE']
    for key,value in {'repository':'Xenova/bge-small-en-v1.5','revision':'ea104dacec62c0de699686887e3f920caeb4f3e3',
        'model_sha256':'828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35',
        'tokenizer_sha256':'d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66',
        'numpy':'2.2.6','onnxruntime':'1.22.1','tokenizers':'0.21.4','providers':['CPUExecutionProvider'],
        'intra_op_threads':2,'inter_op_threads':1,'max_tokens':256,'pooling':'CLS','output_dimensions':384,
        'batch_size':8,'query_prefix':'','one_session':True,'one_tokenizer':True,'CPU_only':True,'no_warmup':True}.items():
        require(bge.get(key)==value,'Actual BGE runtime receipt mismatch: '+key)
    require(raw['engineering_input_bank_reads']==1,'Engineering source-bank read count mismatch')
    require(raw['data_roles']=={'train':[],'dev':[],'calibration':[],'confirmation':[]},'Raw scientific data roles changed')
    require(raw['benchmark_accuracy']is None and raw['benchmark_NLL']is None and raw['benchmark_Brier']is None
            and raw['proper_metric_computations']==0 and raw['champion_promoted']is False,'Raw invented benchmark/proper metric claim')
    require(raw['native_child_closed']is True and raw['native_child_exit_code']==0,'Native helper did not complete and close')
    require(raw['native_scratch']['removed_after_child_exit']is True,'Owned native storage scratch not removed')
    source=raw['source_bank'];require(source['sha256']==INPUT_SHA and source['path']==plan['engineering_inputs_path'],'Actual model source bank differs')
    events=raw['Node_guard_events'];require(events,'No native loader/policy evidence')
    require(all(e['Node_network_operations_attempted']==0 for e in events),'Persistent Node network violation')
    admission=[e for e in events if e['event']=='NODE_SOURCE_RUNTIME_ADMISSION_BEFORE_NATIVE_IMPORT']
    before=[e for e in events if e['event']=='NATIVE_BINARY_LOAD_BEFORE'];after=[e for e in events if e['event']=='NATIVE_BINARY_LOAD_AFTER']
    require(len(admission)==len(before)==len(after)==1,'Exactly one source-admitted actual addon load required')
    a=admission[0];require(a['full_vector_bundle']==vector_pin,'Node observed vector bundle differs')
    require(a['worker_sha256']==identity(Path(root)/plan['native_worker_path'])['sha256'],'Node observed helper source changed')
    status=a['CPU_guard_actual_proc_status'];require(status['NoNewPrivs']=='1'and status['Seccomp']=='2'and status['Cpus_allowed_list']=='0-1','Node did not inherit whole-worker kernel CPU guard')
    binary=Path(root)/'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node'
    require(before[0]['path']==after[0]['path']==str(binary)
            and before[0]['sha256']=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e','Actual loaded native binary path/hash mismatch')
    require(before[0]['native_binary_loads_attempted']==1 and after[0]['native_binary_loads_completed']==1,'Actual addon load not completed')
    lock=read(Path(root)/plan['runtime_assets_lock_path'],plan['runtime_assets_lock_sha256'])
    require(raw['runtime_assets']==lock,'Actual runtime lock differs')
    members=read(Path(root)/lock['wheel_members_reference_path'],lock['wheel_members_reference_sha256'])
    allowed={'retrieval/.venv/'+r['path']:r for r in members}
    loaded=raw['actual_loaded_BGE_runtime_libraries'];require(loaded and any('onnxruntime_pybind11_state'in r['path']for r in loaded),'Actual ONNX binding mapping not observed')
    for row in loaded:
        require(row['path']in allowed,'Unpinned actual BGE runtime shared library')
        require(row['bytes']==allowed[row['path']]['bytes']and row['sha256']==allowed[row['path']]['sha256'],'Loaded runtime library/source closure mismatch')
        check_pin(Path(root)/row['path'],row)
    return {'BGE_versions_and_source_receipt_verified':True,'native_addon_version':'2.3.0',
            'actual_native_addon_loads':1,'actual_loaded_BGE_shared_libraries':loaded,
            'opaque_native_internal_forward_or_thread_counts':'UNKNOWN; actual measured API calls and observed thread affinities only'}

def evaluate(args):
    root=Path(args.project).resolve();here,paths,context,input_audit=load_context(root)
    plan_path=Path(args.plan).resolve();execution_path=Path(args.execution).resolve()
    plan=read(plan_path);execution=read(execution_path)
    raw,selected,selection=selected_raw(args.raw,execution)
    helper,helper_path,helper_common=load_publication_helper(root)
    actual=helper.derive_actual(raw,execution)
    result={'schema_version':1,'epoch':29,'kind':KIND,'checks_passed':False,'engineering_qualified':False,
        'status':'REJECTED_ENGINEERING_QUALIFICATION','benchmark_accepted':False,'champion_promoted':False,
        'new_submission':False,'official_rank':None,'official_SOTA_verified':False,'roles':{'train':[],'dev':[],'calibration':[],'confirmation':[]},
        'LoRA_data_admission':'HOLD_RETAINED','held_parameter_adaptation':project_ref(root,here.parent/'data-projection-hold.json'),
        'actual_execution':actual,'raw_selection':selection,'input_identity_audit':input_audit,
        'metrics':None,'request_timing':None,'resource_scope':raw.get('resources')if raw is not None else None,
        'qualification_checks':{},'failed_integrity_checks':[],'failed_qualification_checks':[],
        'benchmark_metrics':{'accuracy':None,'NLL':None,'Brier':None,'reason':'Document integrity engineering only; no NLI/decision labels or forecasts','proper_metric_computations':0},
        'evidence':{'raw':project_ref(root,selected)if selected else None,'execution':project_ref(root,execution_path),
                    'plan':project_ref(root,plan_path),'scorer_source':project_ref(root,Path(__file__).resolve()),
                    'publication_helper':project_ref(root,helper_path),'publication_common':project_ref(root,helper_common),
                    **{k:project_ref(root,p)for k,p in paths.items()}},
        'source_annotation_choices_or_evidence_reads':0,'NLI_calls_by_scorer':0,'native_or_model_calls_by_scorer':0}
    try:
        source_checks=verify_plan_sources(root,plan_path,plan);physical=closure(execution)
        require(raw is not None and selection['mode']=='FINAL','Complete final worker raw required for qualification')
        require(raw['epoch']==29 and raw['kind']==KIND and raw['status']=='COMPLETED_NATIVE_DOCUMENT_IDENTITY_AWAITING_INDEPENDENT_REPLAY','Native identity worker incomplete')
        require(raw['plan_sha256']==identity(plan_path)['sha256'],'Raw/frozen plan digest mismatch')
        require(raw['source_freeze_sha256']==plan['source_freeze_sha256'],'Raw/source-freeze digest mismatch')
        require(not raw['errors'],'Unexpected worker errors')
        require(raw['counters']==execution['raw_operation_counters'],'Raw/outer operation counter mismatch')
        expected_counters=counter_checks(raw['counters'])
        for key in ['Python_network_operations_attempted','Node_network_operations_attempted','TRAIN_reads','DEV_reads','CONF_reads',
                    'benchmark_label_reads','fits','calibration_calls','training_steps','NLI_calls','Torch_imports','generation_calls','paid_calls','GPU_calls','HTTP_requests']:
            require(type(raw['counters'].get(key))is int and raw['counters'][key]==0,'Forbidden operation count: '+key)
        require(not raw.get('Python_network_violations',[]),'Python network violation')
        require(not raw.get('CPU_affinity_violation_snapshot'),'Observed CPU affinity violation')
        cpu=cpu_checks(root,raw,execution)
        vector_path=resolve_ref(root,raw['vector_bundle']);native_path=resolve_ref(root,raw['native_result'])
        bundle=read(vector_path);native=read(native_path);corpus=context['oracle']['corpus_document_ids'];qids=corpus+[548]
        require(native['source_sha256']==identity(root/plan['native_worker_path'])['sha256'],'Native helper source digest mismatch')
        require(bundle['schema_version']==3 and bundle['epoch']==29 and bundle['kind']==KIND
            and bundle['vector_encoding']=='base64_float32le_c_order','Wrong vector evidence schema')
        require(bundle['document_ids']==qids and bundle['corpus_document_ids']==corpus,'Vector matrix identity mismatch')
        matrix,receipts=matrix_block(bundle['vectors']);require(len(matrix)==262,'Complete262source vectors required')
        vectors=dict(zip(qids,matrix))
        expected_provenance=[{k:d[k]for k in ['document_id','source_document_sha256','normalized_document_sha256','bge_input_sha256']}
                             for d in context['inputs']['documents']+[context['inputs']['query']]]
        require(bundle['provenance']==expected_provenance,'Vector source provenance mismatch')
        docs=replay_documents(raw['documents'],context['inputs'],corpus,receipts)
        require(raw['counters']['BGE_truncated_texts']==docs['truncated_texts'],'Actual truncation counter mismatch')
        replay_native_artifact(raw,native,corpus,qids,receipts,raw['vector_bundle'])
        provenance=runtime_provenance(root,raw,plan,raw['vector_bundle'])
        for key,value in native.items():
            if key.startswith('native_')and type(value)is int:require(raw['counters'][key]==value,'Native artifact/raw counter mismatch: '+key)
        rows=replay_queries(raw['queries'],context['oracle'],corpus,vectors,receipts)
        scores={arm:metrics(rows,arm)for arm in ['native','dense']}
        checks={'native_known548_alias515':515 in rows[-1]['native_confirmed_alias_ids'],
                'dense_known548_alias515':515 in rows[-1]['dense_confirmed_alias_ids'],
                'native_all_positive_queries_recalled':scores['native']['any_alias_query_recall_at16']==1,
                'dense_all_positive_queries_recalled':scores['dense']['any_alias_query_recall_at16']==1,
                'zero_false_hash_confirmations':all(scores[a]['false_exact_hash_confirmations']==0 for a in scores)}
        result.update(checks_passed=True,engineering_qualified=all(checks.values()),qualification_checks=checks,
            failed_qualification_checks=[k for k,v in checks.items()if not v],source_checks=source_checks,
            physical_closure=physical,CPU_scope=cpu,runtime_provenance=provenance,tokenization=docs,metrics=scores,rows=rows,
            resource_scope=raw.get('resources'),expected_operation_counters=expected_counters,
            top16_overlap={'mean_count':math.fsum(r['top16_intersection']for r in rows)/len(rows),
                          'mean_tie_aware_brute_membership':math.fsum(r['native_members_in_brute_tie_aware_top16']for r in rows)/len(rows)},
            request_timing={arm:{'n':len(rows),'p50_seconds':quantile([r[arm+'_query_seconds']for r in rows],.5),
                                'p95_seconds':quantile([r[arm+'_query_seconds']for r in rows],.95)}for arm in ['native','dense']})
        if result['engineering_qualified']:result['status']='DATA_ADMISSION_HOLD_WITH_ENGINEERING_QUALIFIED'
        result['evidence']['vector_bundle']=project_ref(root,vector_path);result['evidence']['native_result']=project_ref(root,native_path)
    except (ValueError,KeyError,TypeError,IndexError,ZeroDivisionError,OSError)as error:
        result['failed_integrity_checks']=[{'type':type(error).__name__,'message':str(error)}]
        result['engineering_qualified']=False
    write_new(args.output,result)
    return result

def bind(args):
    root=Path(args.project).resolve();replay_path=Path(args.replay).resolve();results_path=Path(args.results).resolve()
    replay=read(replay_path);results=read(results_path)
    require(replay['epoch']==results['epoch']==29 and replay['kind']==results['kind']==KIND,'Wrong final engineering report scope')
    for key,pin in replay['evidence'].items():
        if pin is not None:resolve_ref(root,pin)
    plan_path=resolve_ref(root,replay['evidence']['plan']);plan=read(plan_path)
    verify_plan_sources(root,plan_path,plan)
    execution_path=resolve_ref(root,replay['evidence']['execution']);execution=read(execution_path)
    raw_arg=root/'experiments/sota-2026-10-22/epoch29/runs/engineering/raw.json'
    raw,selected,selection=selected_raw(raw_arg,execution)
    require((project_ref(root,selected)if selected else None)==replay['evidence']['raw'],'Selected raw receipt changed')
    helper,helper_path,helper_common=load_publication_helper(root)
    actual=helper.derive_actual(raw,execution)
    require(actual==replay['actual_execution']==results['actual_execution'],'Canonical RESULTS actual counters/resources mismatch')
    for key in ['engineering_qualified','status','metrics','request_timing','resource_scope','failed_integrity_checks',
                'failed_qualification_checks','held_parameter_adaptation','benchmark_metrics']:
        require(results.get(key)==replay.get(key),'Canonical RESULTS differs from frozen replay: '+key)
    for key in ['benchmark_accepted','champion_promoted','new_submission','official_SOTA_verified']:
        require(results[key]is False,'Forbidden benchmark/promotion claim')
    require(results['official_rank']is None,'No official rank exists')
    require(replay['roles']=={'train':[],'dev':[],'calibration':[],'confirmation':[]},'Engineering roles changed')
    if not replay['engineering_qualified']:
        require(replay['failed_integrity_checks']or replay['failed_qualification_checks'],'Rejection has no preserved failure')
    report=json.loads(canonical(replay))
    report['evaluated_integrity_checks_passed']=replay['checks_passed']
    report['publication_binding_checks_passed']=True
    report['checks_passed']=True
    report['checks_passed_scope']='Exact captured evidence, canonicalRESULTS and honest outcome binding; original evaluated integrity/qualification are preserved separately'
    report['evidence']['results']=project_ref(root,results_path)
    report['evidence']['qualification_replay']=project_ref(root,replay_path)
    report['original_qualification_failure_unchanged']=not replay['engineering_qualified']
    write_new(args.output,report)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='mode',required=True)
    evaluation=sub.add_parser('evaluate')
    for name in ['project','plan','raw','execution','output']:evaluation.add_argument('--'+name,required=True)
    binding=sub.add_parser('bind')
    for name in ['project','replay','results','output']:binding.add_argument('--'+name,required=True)
    args=parser.parse_args();result=evaluate(args)if args.mode=='evaluate'else bind(args)
    print(json.dumps({'status':result['status'],'checks_passed':result['checks_passed'],
                      'engineering_qualified':result['engineering_qualified'],'epoch':29}))
