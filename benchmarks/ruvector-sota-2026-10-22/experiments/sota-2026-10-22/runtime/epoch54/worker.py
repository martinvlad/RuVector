"""E54 real tokenizer/BGE/native source-fragment engineering qualification.

No semantic labels, typed model construction, weights, NLI inference, training,
calibration or benchmark evaluation. All authored fixtures are CC0 engineering data.
"""
import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import resource
import sys
import time
import traceback
import unicodedata
from collections import Counter
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import support
from support import require,verify_file,put,proc
from inherited_guards import NetworkAudit,memory_snapshot,require_headroom
import inherited_packing as packing
from inherited_reader import Reader,validate_encoding
KIND='REAL_NATIVE_SOURCE_FRAGMENT_CAPACITY_QUALIFICATION'
ARMS=('native','lexical','source_order','whole_source')
SLOTS=('nda-1','nda-10','nda-16')


def validate_fixture(value):
    require(value['schema_version']==1 and value['epoch']==54 and value['kind']==KIND
            and value['license']=='CC0-1.0' and value['semantic_labels'] is None
            and value['classification_benchmark'] is False,'AUTHORED_ENGINEERING_ONLY_FIXTURES')
    require(len(value['documents'])==4 and len(value['cases'])==12,'FOUR_DOCUMENT_TWELVE_QUERY_FIXTURES')
    require(all(value['roles'][x]==[] for x in ('train','development','calibration','fresh_confirmation')),
            'NO_BENCHMARK_DATA_ROLES')
    documents={}
    for d in value['documents']:
        require(type(d['document_id']) is str and d['document_id'].startswith('authored:e54:')
                and d['document_id'] not in documents,'AUTHORSHIP_DOCUMENT_IDENTITY')
        end=0
        for i,u in enumerate(d['evidence']):
            require(set(u)=={'unit_id','start','end','sentence'} and u['unit_id']==i
                    and type(u['sentence']) is str and u['sentence']
                    and u['start']==end and u['end']==end+len(u['sentence']), 'EXACT_AUTHORITATIVE_UNITS')
            end=u['end']
        text=''.join(u['sentence'] for u in d['evidence'])
        require(0<len(text.encode())<=1048576 and packing.digest(text)==d['source_document_sha256'],
                'AUTHORED_SOURCE_TEXT_HASH')
        documents[d['document_id']]=(d,text)
    cases=[]
    for doc in value['documents']:
        rows=[r for r in value['cases'] if r['document_id']==doc['document_id']]
        require([r['query_slot'] for r in rows]==[1,2,3],'FIXED_THREE_AUTHORED_QUERY_SLOTS')
        for i,row in enumerate(rows):
            require(row['id']==doc['document_id']+':query-'+str(i+1)
                    and type(row['claim']) is str and row['claim'].strip(),'NEW_AUTHOR_QUERY_IDENTITY')
            cases.append(dict(row,hypothesis_id=SLOTS[i]))
    require([c['id'] for c in cases]==value['roles']['engineering']
            and len({c['id'] for c in cases})==12,'FROZEN_ENGINEERING_ROLE_ORDER')
    return {'schema_version':1,'epoch':54,'kind':KIND,'role':'engineering',
            'documents':value['documents'],'cases':cases},documents


class TokenizerOnlyCapture:
    """Explicit composition: original tokenizer calls, no Reader constructor/model.

    E53 Reader methods operate only on tokenizer, counters, stage and deadline.
    Bind those exact methods without constructing Reader or loading any model.
    """
    tokenize=Reader.tokenize
    hypothesis_pair_capacity=Reader.hypothesis_pair_capacity
    set_tokenization_stage=Reader.set_tokenization_stage
    def __init__(self,plan,counters,deadline,network):
        self.counters=counters;self.check_deadline=deadline;self.tokenization_stage='fragmentation'
        expected={'README.md','config.json','special_tokens_map.json','tokenizer.json','tokenizer_config.json','vocab.txt'}
        require({r['file'] for r in plan['tokenizer_assets']}==expected and len(plan['tokenizer_assets'])==6,
                'SIX_FROZEN_TOKENIZER_METADATA_ASSETS_NO_WEIGHTS')
        folder=Path(plan['tokenizer_directory'])
        for r in plan['tokenizer_assets']:
            require(Path(r['path'])==folder/r['file'],'TOKENIZER_FROZEN_LOCATION');verify_file(r)
        require(plan['tokenizer_revision']=='ac92b6b512d7a4bad7abe356750c3b916fe18649',
                'EXACT_EXISTING_BERT_TOKENIZER_REVISION')
        network.set_stage('reader_transformers_import')
        from transformers import BertTokenizerFast
        network.set_stage('tokenizer_initialization')
        counters['tokenizer_initializations_attempted']+=1
        self.tokenizer=BertTokenizerFast.from_pretrained(str(folder),local_files_only=True)
        require(self.tokenizer.vocab_size==30522,'TOKENIZER_VOCABULARY')
        counters['tokenizer_initializations_completed']+=1
        deadline()
    def close(self):
        self.tokenizer=None;gc.collect()
        return {'tokenizer_reference_released':True,'typed_model_ever_created':False,
                'scope':'Outer supervisor verifies worker/native physical process closure.'}


def branch_and_integrity_gates(original,bank,audit):
    require(audit['complete'] and len(audit['documents'])==4,'CATALOG_COMPLETE')
    checks={};over=coalesced=combining=zwj=protected=blank=fitting=0
    for old,new,record in zip(original['documents'],bank['documents'],audit['documents']):
        text=''.join(u['sentence'] for u in old['evidence'])
        require(new['document_id']==record['document_id']==old['document_id'],'CATALOG_DOCUMENT_ORDER')
        require(''.join(u['sentence'] for u in new['evidence'])==text
                and record['all_source_characters_once'] and record['complete'],'EXACT_FRAGMENT_SOURCE_COVERAGE')
        document_over=sum(g['over_capacity'] for g in record['coalesced_groups'])
        require(document_over>=1,'EVERY_AUTHORED_DOCUMENT_EXERCISES_OVERSIZED_BRANCH')
        over+=document_over
        fitting+=sum(not g['over_capacity'] for g in record['coalesced_groups'])
        for g in record['coalesced_groups']:
            require((max(g['original_pair_token_counts'].values())>512)==g['over_capacity'],
                    'ACTUAL_OVERSIZED_PAIR_COUNTS')
            require((len(g['fragment_ids'])>1) if g['over_capacity'] else (len(g['fragment_ids'])==1),
                    'ACTUAL_BRANCH_FRAGMENT_COUNTS')
        expected_boundaries=set()
        matches=list(packing.PROTECTED.finditer(text))
        for u in old['evidence'][:-1]:
            at=u['end']
            if any(m.start()<at<m.end() for m in matches):expected_boundaries.add(at);protected+=1
            if unicodedata.combining(text[at]):expected_boundaries.add(at);combining+=1
            if '\u200d' in text[at-1:at+1]:expected_boundaries.add(at);zwj+=1
        for i,u in enumerate(old['evidence']):
            if not u['sentence'].strip():
                if i:expected_boundaries.add(old['evidence'][i-1]['end']);blank+=1
                elif len(old['evidence'])>1:expected_boundaries.add(u['end']);blank+=1
        require(set(record['coalesced_boundary_offsets'])==expected_boundaries,
                'EXACT_EXPECTED_COALESCED_BOUNDARIES')
        coalesced+=len(expected_boundaries)
        for f,u in zip(record['fragments'],new['evidence']):
            require(f['unit_id']==u['unit_id'] and f['start']==u['start'] and f['end']==u['end']
                    and f['sha256']==packing.digest(text[u['start']:u['end']])
                    and set(f['checked_pair_token_counts'])==set(SLOTS)
                    and max(f['checked_pair_token_counts'].values())<=512,
                    'ORIGINAL_REAL_PAIR_FRAGMENT_CAPACITY')
            for at in (u['start'],u['end']):
                require(not any(m.start()<at<m.end() for m in matches),'NO_PROTECTED_SUBSTRING_CUT')
                require(not (0<at<len(text) and (unicodedata.combining(text[at]) or '\u200d' in text[at-1:at+1])),
                        'NO_COMBINING_OR_ZWJ_CUT')
        require(record['numeric_date_currency_negation_partition_audit']['source_and_premise_occurrence_counts_match'],
                'EXACT_PROTECTED_OCCURRENCE_MULTISET')
        checks[old['document_id']]={'all_characters_once':True,'parent_offsets_hashes_valid':True,
            'all_three_queries_real_pair_capacity_at_most512':True,
            'protected_numeric_date_currency_negation_multiset_preserved':True,
            'unsafe_Unicode_boundaries_not_used':True,'expected_coalesced_offsets':sorted(expected_boundaries),
            'source_characters':len(text),'original_source_units':len(old['evidence']),
            'final_fragments':len(new['evidence']),'over_capacity_groups':document_over,
            'coalesced_group_original_real_pair_counts':[{'over_capacity':g['over_capacity'],'counts':g['original_pair_token_counts']} for g in record['coalesced_groups']]}
    require(over>=4 and coalesced>=4 and combining>=1 and zwj>=1 and protected>=2 and blank>=1 and fitting>=1,
            'ALL_FROZEN_REAL_ENGINEERING_BRANCHES_EXERCISED')
    require(audit['fragment_count']<=256,'FROZEN_ENGINEERING_FRAGMENT_CAP256')
    return {'checks_passed':True,'documents':checks,'actual_branch_counts':{'over_capacity_groups':over,
        'coalesced_boundaries':coalesced,'combining_boundary_crossings':combining,'ZWJ_boundary_crossings':zwj,
        'protected_regex_boundary_crossings':protected,'blank_boundaries':blank,'capacity_fitting_groups':fitting},
        'scope':'Source/capacity/substrings only; no semantic arithmetic, absence, classification or generalization proof.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--expected-plan-sha256',required=True)
    p.add_argument('--admission',required=True);p.add_argument('--expected-admission-sha256',required=True)
    p.add_argument('--out-dir',required=True);p.add_argument('--deadline',required=True,type=float);a=p.parse_args()
    started=time.monotonic();require(math.isfinite(a.deadline) and 0<a.deadline-started<=570,'ABSOLUTE_DEADLINE')
    require(sorted(os.sched_getaffinity(0))==[0,1],'CPU_AFFINITY_0_1')
    external=Path(a.out_dir);require(external.is_absolute() and external.is_dir() and not external.is_symlink(),'PRIVATE_RUN_DIRECTORY')
    counters=Counter();network=NetworkAudit(counters);sys.addaudithook(network);network.install_socket_guards()
    def no_weight_read(event,args):
        if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            path=os.fsdecode(args[0])
            if path.endswith(('.safetensors','.bin','.pt','.pth','.zip')):
                counters['forbidden_model_or_archive_file_access_attempts']+=1
                raise RuntimeError('ENGINEERING_MODEL_WEIGHTS_AND_CORPUS_ARCHIVES_FORBIDDEN')
    sys.addaudithook(no_weight_read)
    def deadline():
        left=a.deadline-time.monotonic();require(left>0,'ENGINEERING_WORKER_DEADLINE');return left
    progress_fd=os.open(external/'worker-progress.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    def progress(stage):
        deadline();row={'stage':stage,'monotonic_seconds':time.monotonic(),'counters':dict(counters)}
        os.write(progress_fd,(json.dumps(row,allow_nan=False)+'\n').encode());os.fsync(progress_fd)
    raw={'schema_version':1,'epoch':54,'kind':KIND,'phase':'engineering','status':'PARTIAL_ENGINEERING_NOT_SCORED',
         'plan_sha256':a.expected_plan_sha256,'rows':[],'counters':counters,'errors':[],
         'typed_model_initializations':0,'NLI_forwards':0,'semantic_labels':None,
         'quality_metrics':{'accuracy':None,'Brier':None,'NLL':None},'benchmark_generalization_claim':False,
         'fragment_catalog_audit':{},'native_state':{},'shared_memory_snapshots':[]}
    reader=None;rc=2
    try:
        plan_bytes=Path(a.plan).read_bytes();require(hashlib.sha256(plan_bytes).hexdigest()==a.expected_plan_sha256,'FROZEN_PLAN_SHA256')
        plan=json.loads(plan_bytes);plan['_sha256']=a.expected_plan_sha256
        require(plan['epoch']==54 and plan['kind']==KIND and plan['maximum_native_batches']==1
                and plan['typed_model_initializations_authorized']==plan['NLI_forwards_authorized']==0,'ENGINEERING_ONLY_PLAN')
        ab=Path(a.admission).read_bytes();require(hashlib.sha256(ab).hexdigest()==a.expected_admission_sha256,'ADMISSION_SHA256')
        ad=json.loads(ab);require(ad['allowed'] is True and ad['epoch']==54 and ad['kind']==KIND
                and ad['plan_sha256']==a.expected_plan_sha256 and ad['source_publication_independently_verified'] is True,
                'ROOT_EXACT_SOURCE_ADMISSION')
        # Supervisor has already validated owner and the same exact source/asset refs.
        for row in ad['source_files']:verify_file(row)
        for package,version in plan['runtime_versions'].items():
            require(importlib.metadata.version(package)==version,'EXACT_RUNTIME_VERSION')
        baseline=memory_snapshot();raw['shared_memory_snapshots'].append({'stage':'before_assets',**baseline});require_headroom(baseline)
        fixture=json.loads(verify_file(plan['fixtures']).read_bytes());bank,documents=validate_fixture(fixture)
        raw['fixture_ref']=plan['fixtures'];raw['source_commit']=ad['source_commit'];raw['source_freeze_sha256']=ad['source_freeze_sha256']
        raw['inherited_source_files']=plan['inherited_source_files'];raw['worker_identity']=proc(os.getpid())
        progress('TOKENIZER_INITIALIZE_BEFORE');reader=TokenizerOnlyCapture(plan,counters,deadline,network)
        progress('REAL_FRAGMENT_CATALOG_BEFORE_ANY_BGE_NATIVE')
        before=time.monotonic();original=bank
        bank=packing.build_fragment_catalog(bank,reader.tokenize,deadline,raw['fragment_catalog_audit'])
        raw['fragmentation_seconds']=time.monotonic()-before
        raw['engineering_branch_gates']=branch_and_integrity_gates(original,bank,raw['fragment_catalog_audit'])
        require(counters['BGE_initializations_attempted']==counters['native_corpus_batches_attempted']==0,
                'CATALOG_BEFORE_BGE_NATIVE')
        reader.set_tokenization_stage('packing');network.set_stage('bge_initialization_and_embedding')
        progress('BGE_BEFORE');bundle,raw['BGE_runtime'],raw['embedding_audit']=support.embed_documents(plan,bank,counters,progress,deadline)
        network.set_stage('native_retrieval');native,_=support.run_native(plan,bundle,external,counters,progress,deadline,raw['native_state'])
        raw['native_result']=native;observed={q['case_id']:q for d in native['documents'] for q in d['queries']}
        network.set_stage('engineering_packet_integrity')
        for case in bank['cases']:
            units=next(d['evidence'] for d in bank['documents'] if d['document_id']==case['document_id'])
            orders={'native':observed[case['id']]['ids'],'lexical':packing.bm25_order(units,case['claim']),
                    'source_order':list(range(len(units)))}
            for arm in ARMS:
                before=time.monotonic()
                if arm=='whole_source':
                    windows=packing.pack_whole_source(units,case['claim'],reader.tokenize,reader.hypothesis_pair_capacity)
                    for w in windows:validate_encoding(w['tokens'],pair=True)
                    evidence=[w['evidence'] for w in windows]
                    count=len(windows);coverage=1.0
                else:
                    tokens,e=packing.pack(units,case['claim'],orders[arm],reader.tokenize,reader.hypothesis_pair_capacity)
                    validate_encoding(tokens,pair=True);evidence=[e];count=1
                    coverage=e['selected_source_characters']/e['source_characters_total']
                require(all(e['pair_token_count']<=512 and e['numeric_date_currency_negation_audit']['source_and_premise_occurrence_counts_match'] for e in evidence),
                        'ENGINEERING_ALL_PACKETS_REAL_PAIR_CAP_AND_SUBSTRINGS')
                raw['rows'].append({'case_id':case['id'],'document_id':case['document_id'],'arm':arm,
                    'packet_count':count,'evidence':evidence,'source_character_coverage_fraction':coverage,
                    'context_preparation_seconds':time.monotonic()-before,
                    'native_query_and_hit_validation_seconds':observed[case['id']]['elapsed_seconds'],
                    'semantic_prediction':None,'probabilities':None,'engineering_integrity_checks_passed':True})
                counters['engineering_contexts_completed']+=1;progress('ENGINEERING_CONTEXT_COMPLETE')
        require(len(raw['rows'])==counters['engineering_contexts_completed']==48
                and counters['reader_capacity_tokenizations']==48 and counters['native_corpus_batches']==1,
                'ONE_COMPLETE_ENGINEERING_NATIVE_BATCH')
        require(counters['reader_pair_tokenizations']==counters['reader_pair_tokenizations_completed']
                ==counters['reader_fragmentation_pair_tokenizations']+counters['reader_packing_pair_tokenizations'],
                'REAL_PAIR_ATTEMPT_COMPLETION_ACCOUNTING')
        require(network.receipt()['admissible'] and counters['Node_network_operations_attempted']==0
                and counters['forbidden_model_or_archive_file_access_attempts']==0,'NO_EXTERNAL_IO_OR_MODEL_WEIGHT_ACCESS')
        raw['status']='ENGINEERING_QUALIFIED_NOT_BENCHMARK_SCORED';rc=0
    except BaseException as e:
        code=str(e);raw['errors'].append({'type':type(e).__name__,'code':code if re.fullmatch('[A-Z0-9_]{1,120}',code) else 'ENGINEERING_WORKER_FAILURE_PRIVATE_TRACE_RETAINED'})
        (external/'worker.exception.txt').write_text(traceback.format_exc())
    finally:
        if reader is not None:raw['tokenizer_cleanup']=reader.close()
        raw['network_audit']=network.receipt();raw['counters']=dict(counters)
        for key in ('typed_model_initializations','NLI_forwards_attempted','NLI_forwards_completed','semantic_gold_decodes','training_calls','calibration_calls','paid_API_calls','GPU_calls','forbidden_model_or_archive_file_access_attempts'):
            raw['counters'].setdefault(key,0)
        usage=resource.getrusage(resource.RUSAGE_SELF);child=resource.getrusage(resource.RUSAGE_CHILDREN)
        raw['timing']={'worker_wall_seconds_including_init_cleanup':time.monotonic()-started,
                       'started_monotonic_seconds':started,'completed_monotonic_seconds':time.monotonic()}
        raw['resources']={'CPU_affinity':sorted(os.sched_getaffinity(0)),'compute_threads':2,
          'worker_max_RSS_KiB':usage.ru_maxrss,'worker_user_seconds':usage.ru_utime,'worker_system_seconds':usage.ru_stime,
          'children_max_RSS_KiB':child.ru_maxrss,'children_user_seconds':child.ru_utime,'children_system_seconds':child.ru_stime,
          'RSS_scope':'SELF versus CHILDREN high-water recorded separately, never summed.',
          'shared_cgroup':memory_snapshot()}
        raw['latency_scope']='Context preparation includes packing and real pair tokenizations; common catalog/BGE/index/init/cleanup excluded and reported separately. Native query includes returned-hit validation. Inclusive outer clock is authoritative whole-batch bound.'
        os.close(progress_fd);put(external/'raw.json',raw)
    return rc

if __name__=='__main__':raise SystemExit(main())
