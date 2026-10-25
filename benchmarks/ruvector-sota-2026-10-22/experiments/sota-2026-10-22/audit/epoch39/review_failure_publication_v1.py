"""Read-only E39 public failure-record review; no project imports or gold reads."""
import collections
import datetime
import hashlib
import json
import math
import pathlib
import re

ROOT = pathlib.Path('/tmp/ruvector-sota-2026-10-22/epoch39-74dbbcb10508/project')
OWN = pathlib.Path('/workspace/ruvector-e39-acceptance-audit-new')
P = 'experiments/sota-2026-10-22/'
E = P+'epoch39/'
A = P+'audit/epoch39/'
K = P+'candidate/epoch39/'
ARMS = ['b354_source_order','b354_native','b354_lexical','xxlarge_source_order']


def same(a,b):
    if type(a) is not type(b): return False
    if isinstance(a,dict): return set(a)==set(b) and all(same(a[k],b[k]) for k in a)
    if isinstance(a,list): return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b


def loads(body):
    def unique(pairs):
        d={}
        for k,v in pairs:
            assert k not in d
            d[k]=v
        return d
    def bad(x): raise AssertionError('NONFINITE_JSON')
    value=json.loads(body,object_pairs_hook=unique,parse_constant=bad)
    def finite(v):
        if isinstance(v,float): assert math.isfinite(v)
        elif isinstance(v,dict):
            for x in v.values(): finite(x)
        elif isinstance(v,list):
            for x in v: finite(x)
    finite(value)
    return value


def ref(path):
    path=pathlib.Path(path)
    path=path if path.is_absolute() else ROOT/path
    b=path.read_bytes()
    try: name=path.relative_to(ROOT).as_posix()
    except ValueError: name=str(path)
    return {'path':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}


def load(path):
    path=pathlib.Path(path)
    return loads((path if path.is_absolute() else ROOT/path).read_bytes())


def checked(row):
    assert set(row)=={'path','bytes','sha256'} and not pathlib.PurePosixPath(row['path']).is_absolute()
    assert '..' not in pathlib.PurePosixPath(row['path']).parts
    assert same(ref(row['path']),row)
    return load(row['path'])


def q(v,f):
    v=sorted(v);x=(len(v)-1)*f;i=int(x)
    return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(x-i)


def main():
    plan=load(E+'plan.json'); result=load(E+'RESULTS.json')
    replay=load(A+'qualification-replay.json'); binding=load(A+'publication-binding.json')
    closure=load(A+'actual-physical-closure-independent-v1.json')
    assert ref(E+'plan.json')['sha256']=='d7942147b0b15d47ee220d19fb05f3a5c55b977f6140e8b1acba96dbe8ee8bcc'
    assert ref(A+'qualification-replay.json')['sha256']=='d9ee745f46ecfeadfc760fc802530eb72a7cd00be684eb5bf7505aa0f98731dd'
    assert ref(E+'RESULTS.json')['sha256']=='428f82713bc56d4cab6cd0a5f0e27cdcc38287f10667007bed8ee39dce88ef7e'
    assert ref(A+'publication-binding.json')['sha256']=='c8882a45a0c3a10a119a7a79f8b6aedaef9f4a84d39f9182c96741fecd2de8ca'
    assert ref(A+'actual-physical-closure-independent-v1.json')['sha256']=='c76f31e30635a551d1e6e6255cb51ffb4fc465dfd4398dd0f2c68834ee2ef172'
    assert set(result)==set(replay)|{'publication_checkpoint'}
    assert all(same(result[k],v) for k,v in replay.items())
    assert replay['status']=='REJECTED_DEV_INTEGRITY'
    assert all(replay[k] is False for k in ['checks_passed','dev_passed','evaluation_executed','frozen_full_input_quality_audit_executed','scoring_gates_evaluated'])
    assert type(replay['frozen_scorer_EVALUATE_invocations']) is int and replay['frozen_scorer_EVALUATE_invocations']==0
    assert replay['metrics'] is None and replay['paired_control_comparisons'] is None
    assert len(replay['gate_checks'])==15 and set(replay['gate_checks'].values())=={'NOT_EVALUATED'}
    assert set(replay['quality_metrics'])==set(ARMS)
    assert all(v is None for values in replay['quality_metrics'].values() for v in values.values())
    assert replay['benchmark_accuracy'] is None and replay['official_rank'] is None
    assert replay['official_eligibility']==replay['model_selection_lineage']=='HOLD'
    for k in ['benchmark_accepted','champion_promoted','new_submission','official_SOTA_verified','benchmark_generalization_claim']:
        assert replay[k] is False
    assert replay['used_confirmation_identities']==[]
    for row in plan['pins']:
        assert same(ref(row['path']),row)
    assert len(plan['pins'])==354
    evidence={k:checked(v) for k,v in replay['evidence'].items()}
    assert len(evidence)==14
    raw=evidence['raw'];execution=evidence['execution'];gold=evidence['gold_join_report']
    ids=plan['data_roles']['dev'];assert len(ids)==len(set(ids))==12
    assert [c['id'] for c in raw['cases']]==ids
    assert raw['status']=='DEV_FORECASTS_COMPLETE_NO_GOLD' and raw['errors']==[]
    expect={cid+'::'+arm for cid in ids for arm in ARMS}
    assert len(raw['completed_readout_ids'])==48 and set(raw['completed_readout_ids'])==expect
    assert len(raw['required_readout_ids'])==48 and set(raw['required_readout_ids'])==expect
    assert all(set(c['readouts'])==set(ARMS) for c in raw['cases'])
    assert all(same(raw['counters'][k],v) for k,v in plan['expected_operation_counters']['dev'].items())
    assert same(raw['counters'],execution['raw_operation_counters'])
    assert same(raw['counters'],replay['actual_execution']['raw_operation_counters'])
    assert execution['status']=='WORKER_COMPLETED' and execution['exit_code']==0
    assert execution['worker_popen_attempts']==execution['verified_worker_starts']==1
    assert execution['uncertain_start'] is False and execution['owned_live_processes_closed'] is True
    assert raw['closure_facts']['model_profiles_disposed']==['xxlarge','b354']
    assert raw['closure_facts']['native_child_closed'] is True
    assert len(raw['reader_lifecycle'])==10
    for model in ['xxlarge','b354']:
        last=[v for v in raw['reader_lifecycle'] if v['model_tag']==model][-1]
        assert last['event']=='MODEL_UNLOAD_AFTER_GC'
        assert all(last[k] is True for k in ['reader_weakref_dead','model_weakref_dead','tokenizer_weakref_dead'])
    assert closure['checks_passed'] is True and closure['physical_closure_passed'] is True
    assert closure['actual_supervisor_exit_wait_status']==0
    assert closure['live_known_owned_group_or_session_members']==[]
    assert closure['full_supervisor_observed_closed_by_bound_seconds']<=600
    assert same(closure['actual_counters'],raw['counters'])
    assert same(closure['raw'],ref(E+'runs/dev/raw.json'))
    assert gold['status']=='GOLD_JOIN_FAILED_FINAL_NO_RETRY'
    assert gold['semantic_labels_decoded']==gold['decode_attempted_tokens']==2
    assert gold['semantic_decode_count_uncertain'] is False and gold['label_reader_calls']==1
    assert gold['errors']==['ValueError:UNSUPPORTED_OFFICIAL_LABEL_NO_REMAP']
    assert 'joined_labels' not in gold
    assert not (ROOT/(A+'joined-labels.json')).exists()
    assert same(replay['label_custody'],{'semantic_label_decodes':2,'remaining_selected_tokens_opaque':10,'semantic_decode_count_uncertain':False,'join_reader_calls':1,'scorer_original_oracle_reads':0,'scorer_retained_join_reads':0,'additional_decode_retry_or_remap_authorized':False})
    assert {p.name for p in (ROOT/(E+'runs/dev')).glob('progress-*.json')}=={'progress-%02d-%s.json'%(i,s)for i in range(2)for s in ['before','after']}
    for i in range(2):
        before=evidence['progress_%02d_before'%i];after=evidence['progress_%02d_after'%i]
        assert before['caseid']==after['caseid']==ids[i]
        assert before['previous_semantic_decodes']==i and after['semantic_decodes_completed']==i+1
        assert after['supported_literal'] is (i==0)
        assert set(before)=={'schema_version','epoch','kind','phase','caseid','previous_semantic_decodes','token_sha256','decode_started','decode_completed'}
        assert set(after)=={'schema_version','epoch','kind','phase','caseid','semantic_decodes_completed','decode_completed','supported_literal'}
    assert binding['checks_passed'] is binding['publication_binding_checks_passed'] is True
    assert binding['evaluated_integrity_checks_passed'] is binding['dev_passed'] is False
    assert binding['no_scientific_measurements_or_oracle_reads_in_BIND'] is True
    assert same(binding['evidence'],{'results':ref(E+'RESULTS.json'),'qualification_replay':ref(A+'qualification-replay.json')})
    for arm in ARMS:
        for field in ['pair_tokenization_seconds','NNI_forward_seconds','reader_total_seconds','context_order_seconds','native_query_seconds']:
            values=[c['readouts'][arm]['timing'][field] for c in raw['cases']]
            got=replay['timing_metadata']['per_arm'][arm][field]
            assert got['N']==12
            assert abs(got['p50']-q(values,.5))<=1e-12 and abs(got['p95']-q(values,.95))<=1e-12
    assert same(replay['resource_metadata']['raw_worker'],raw['resources'])
    assert raw['resources']['cpu_affinity']==[0,1] and raw['resources']['torch_num_threads']==2
    assert same(result['publication_checkpoint']['qualification_replay'],ref(A+'qualification-replay.json'))
    assert same(result['publication_checkpoint']['independent_physical_closure'],ref(A+'actual-physical-closure-independent-v1.json'))
    cumul=result['publication_checkpoint']['cumulative_execution']
    assert cumul['corpus_attempts'] is cumul['completed_corpus_batches'] is None
    assert cumul['historical_E37_model_corpus_tail']=='UNKNOWN_PERMANENTLY'
    assert cumul['verified_corpus_attempts_lower_bound']==35 and cumul['verified_completed_corpus_batches_lower_bound']==33
    assert result['publication_checkpoint']['all_slots_closed'] is True
    assert all(type(v) is int and v==0 for v in result['publication_checkpoint']['remaining_slots'].values())
    continuation=load(ROOT.parent/'controls-source/CONTINUATION.json')
    oldledger=checked(continuation['rejection_ledger']);ledger=load(E+'REJECTION_LEDGER.json')
    assert same(ledger['rejections'][:-1],oldledger['rejections']) and len(ledger['rejections'])==len(oldledger['rejections'])+1
    assert ledger['rejections'][-1]['epoch']==39 and ledger['rejections'][-1]['status']=='REJECTED_DEV_INTEGRITY'
    used=load(E+'USED_CONFIRMATION_IDENTITIES.json');learnings=load(E+'LEARNINGS.json')
    assert used['new_source_exposed_DEV_identities_forever']==ids
    assert used['confirmation']==used['used_confirmation_identities']==used['train']==used['calibration']==[]
    assert used['prior_423_benchmark_partition_unchanged']=={'exposed':325,'unused':74,'protected':24}
    assert learnings['champion_native104_unchanged'] is True
    correction=load(A+'finfact-label-contract-correction-independent-v1.json')
    assert ref(A+'finfact-label-contract-correction-independent-v1.json')['sha256']=='50daa43b4860ca1a5767a13c3df24552636549be0dd227de2cde2c85afb689f3'
    assert correction['prior_report_preserved_byte_exact'] is True
    # Privacy: inspect the sanitized public schema, never dereference external_evidence.
    schema=load(K+'RAW_SCHEMA.v1.json')
    assert set(raw)==set(schema['top_level_keys'])
    for case in raw['cases']:
        assert set(case)==set(schema['case_public_keys'])|set(schema['extra_safe_case_keys'])
        for arm in ARMS:
            ro=case['readouts'][arm]
            assert set(ro)==set(schema['readout_public_keys'])
            assert set(ro['input_audit'])==set(schema['input_audit_public_keys'])
        embedding=case['embedding_audit']
        for unit in embedding['units']+[embedding['query']]:
            assert set(unit)=={'text_sha256','full_tokens','consumed_tokens','truncated','consumed_tokens_sha256'}
    forbidden_parts={'assets','__pycache__','.git','.cache','cache','venv','.venv','node_modules','site-packages','credentials','secrets','private','raw-pages','raw-email','inbox','mailbox','messages','models','weights'}
    extensions={'.py','.js','.mjs','.cjs','.json','.jsonl','.md','.txt','.log','.csv','.tsv','.yaml','.yml','.stdout','.stderr'}
    patterns=[r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',r'\bgh[pousr]_[A-Za-z0-9]{30,}\b',r'\bgithub_pat_[A-Za-z0-9_]{30,}\b',r'\bAKIA[0-9A-Z]{16}\b',r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b',r'\b(?:authorization|proxy-authorization)\s*[:=]\s*[\x22\x27]?(?:Bearer|Basic)\s+[A-Za-z0-9+/_.=-]{20,}',r'^[ \t]*(?:Received:|DKIM-Signature:|Return-Path:|MIME-Version:)',r'<(?:!DOCTYPE\s+html|html|head|body)(?:\s|>)']
    patterns=[re.compile(x,re.I|re.M) for x in patterns]
    inventory=[]
    for relative in [E,A,K]:
        for path in sorted((ROOT/relative).rglob('*')):
            assert not path.is_symlink()
            assert not any(part.lower() in forbidden_parts or '.private' in part.lower() or part.lower().startswith('.env') for part in path.relative_to(ROOT).parts)
            if path.is_dir(): continue
            row=ref(path);body=path.read_bytes();name=row['path']
            assert path.suffix in extensions or name==K+'reader/LICENSE.fairseq'
            text=body.decode('utf-8');assert '\0' not in text
            assert not any(ord(c)<32 and c not in '\t\r\n' for c in text)
            assert not any(pattern.search(text) for pattern in patterns),name
            if path.suffix=='.json': loads(body)
            inventory.append(row)
    inventory.sort(key=lambda r:r['path'])
    invbody=json.dumps(inventory,sort_keys=True,separators=(',',':')).encode()
    report={'schema_version':1,'epoch':39,'kind':'REAL_FINFACT_DEV_TRANSFER_PILOT','phase':'dev','checks_passed':True,'publication_allowed':True,'dev_passed':False,'no_raw_third_party_text_in_public_files':True,'status':'INDEPENDENT_APPROVAL_TO_PUBLISH_UNSCORED_DEV_INTEGRITY_REJECTION','scientific_status':'REJECTED_DEV_INTEGRITY','scientific_integrity_checks_passed':False,'evaluation_executed':False,'quality_metrics':None,'benchmark_accuracy':None,'official_rank':None,'official_eligibility':'HOLD','champion_promoted':False,'benchmark_generalization_claim':False,'used_confirmation_identities':[],'source_commit':'e06515a7dc493bfa9869d9e7a4b27c348bb32603','source_plan_sha256':ref(E+'plan.json')['sha256'],'results':ref(E+'RESULTS.json'),'binding':ref(A+'publication-binding.json'),'closure_report':ref(A+'actual-physical-closure-independent-v1.json'),'qualification_replay':ref(A+'qualification-replay.json'),'source_freeze':ref(E+'source-freeze.json'),'raw_forecasts':ref(E+'runs/dev/raw.json'),'execution':ref(E+'runs/dev/execution.json'),'custody_failure':ref(A+'actual-custody-failure-independent-v1.json'),'custody_report':ref(E+'runs/dev/GOLD_JOIN_REPORT.json'),'source_label_contract_correction':ref(A+'finfact-label-contract-correction-independent-v1.json'),'source_representation_finding':ref(A+'LABEL_REPRESENTATION_SOURCE_FINDING.v2.json'),'failure_assembler_review':ref(OWN/'FAILURE_ONLY_SOURCE_REVIEW_v1.json'),'reviewer_code':ref(pathlib.Path(__file__)),'independent_checks':{'exact_results_preserves_every_rejection_field_and_types':True,'BIND_is_metadata_identity_only_and_false_scientific_integrity_preserved':True,'all354_frozen_source_pins_exact':True,'all14_failure_record_public_evidence_refs_exact':True,'all48_readouts_four_arms_fixed12_retained':True,'all_expected_worker_counters_reconciled':True,'two_sequential_models_unloaded_and_native_closed':True,'one_worker_one_native_corpus12_queries53_inserts':True,'zero_worker_gold_TRAIN_calibration_CONF_paid_GPU_network':True,'actual2_semantic_decodes_known10_unattempted_no_label_values_accessed':True,'all15_scientific_gates_not_evaluated_quality_null':True,'forty_recorded_component_quantiles_independently_recomputed':True,'recorded_resource_and_total_scope_preserved':True,'prior_rejection_prefix_exact_and_one_new_integrity_rejection':True,'all_slots_permanently_closed_and_E37_unknowns_preserved':True,'all12_identities_DEV_forever_old423_partition_unchanged':True,'original_static_review_overclaim_corrected_append_only':True,'public_raw_schema_disallows_actual_text_tokenIDs_vectors':True,'public_progress_schema_contains_hashes_and_counts_only':True,'public_text_credentials_binary_privatepath_symlink_scan_pass':True},'actual_execution_summary':{'NLI_readouts':48,'XXL_readouts':12,'b354_readouts':36,'worker_attempts':1,'native_corpus_batches':1,'native_queries':12,'native_insertions':53,'BGE_texts':65,'BGE_forward_calls':26,'worker_semantic_gold_decodes':0,'postclosure_semantic_gold_decodes':2,'remaining_gold_tokens_opaque':10,'scorer_EVALUATE_invocations':0,'scorer_retained_join_reads':0,'frozen_full_input_quality_audit_executed':False,'supervisor_observed_exit_wait_status':0,'supervisor_whole_observed_closed_bound_seconds':closure['full_supervisor_observed_closed_by_bound_seconds'],'captured_supervisor_wall_seconds':execution['wall_seconds_including_init_cleanup'],'raw_worker_wall_seconds':raw['wall_seconds'],'largest_child_peak_RSS_bytes':execution['largest_child_peak_RSS_bytes'],'CPU_affinity':[0,1],'paid_GPU_calls':0},'privacy_inventory':{'current_roots':[K,A,E],'files_reviewed':len(inventory),'total_bytes':sum(v['bytes'] for v in inventory),'extensions':dict(collections.Counter(pathlib.Path(v['path']).suffix for v in inventory)),'ordered_path_byte_sha256_inventory_digest':hashlib.sha256(invbody).hexdigest(),'inventory_digest_encoding':'JSON sorted keys compact separators UTF8, sorted by path','symlinks_private_paths_credentials_controlbytes_generated_bytecode_or_model_payloads':0,'actual_selected_FinFact_text_feature_tokenID_vector_or_gold_value_payloads':0,'scope':'Read-only current three public E39 roots, including post-SOURCE execution history, corrections, failure helper and metadata. Actual selected FinFact claims/evidence/fullcase text, tokens, input audits, model/vector payloads, full private stdout/stderr and label tokens were not opened or followed. Retained official public licenses/README/scorer source and disjoint authored fixtures are authorized source provenance, not private selected corpus exports. Privacy conclusion combines exact public runtime schemas, frozen-source identity and bounded text/path scanning; no private-corpus matching scan was performed.','seal_limit':'Inventory predates this independent report copy and root final manifests. Main independent auditor must verify sealed manifest/stage/readback and release; this report does not claim a later commit or lock release.'},'interpretation':'The completed inference/retrieval runtime is evidenced, but the once-only custodian stopped on the second unsupported frozen gold representation. With no joined-label bank and no EVALUATE, no accuracy, macroF1, Brier, NLL, paired quality difference or acceptance gate can be inferred from these records or a supported prefix. This is a data/scorer-contract admission failure, not evidence of model performance gain or regression. Metadata publication checks pass while scientific integrity and DEV acceptance remain false.','next_direction':'Before a separately frozen new measurement, independently establish an authoritative version-bound source gold schema/codec and scorer agreement, or keep the mapping unverified and block scoring. Validate declared types/normalization with disjoint fixtures; synthetic fixtures cannot prove archive encoding. Do not remap, drop, replace, retry, reopen remaining10 labels or remeasure these12 exposed DEV identities. Any future codec investigation needs separately authorized non-confirmation scope, not a protected/confirmation/global label scan.','limitations':['No original private features/cases/vault/labels, external token audits or payloads were opened by this review; source/full-input semantic leakage and full context/quantity quality were not independently evaluated.','Guard/source evidence and sanitized counters are not proof of pretrained dataset independence. Foundation/model selection/official eligibility remain HOLD.','12 deterministic DEV examples are neither a population confidence estimate nor an unseen confirmation/full-benchmark placement. Existing native104 champion and protected/unused partitions are unchanged.','Known exact process/group closure relies on independently captured kernel/source evidence, not an assertion that the supervisor PID was absent or that unrelated global processes cannot exist.','Historic E37 actual model/corpus tail remains UNKNOWN;35/33 are known lower bounds only, not repaired exact totals.','Per-readout p50/p95 are component summaries with reused context/query work; they are not publisher latency or independent batch replicates. Sequential model RSS peaks are not summed.'],'auditor_calls':{'candidate_model_tokenizer_native_actual_guard_or_payload':0,'private_cases_features_or_original_oracle_gold_reader':0,'frozen_EVALUATE_BIND_or_failure_assembler_production_mode':0,'actual_quality_score_arithmetic':0,'Git_mutations_or_R_writes':0,'new_paid_or_network_calls':0},'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    out=OWN/'ACTUAL_FAILURE_ACCEPTANCE_PRIVACY_v1.json'
    assert not out.exists()
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(ref(out)))


if __name__=='__main__': main()
