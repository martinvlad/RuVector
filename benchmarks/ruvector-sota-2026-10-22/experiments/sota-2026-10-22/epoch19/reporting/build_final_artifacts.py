"""Append final reporting from immutable real receipts; never score or run models."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os
from datetime import datetime,timezone
P='experiments/sota-2026-10-22/'
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def ref(root,name):
    path=root/name
    return {'path':name,'bytes':path.stat().st_size,'sha256':sha(path)}
def put(path,value):
    with path.open('x') as f:
        json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def build(args):
    root=args.project.resolve();s=root/P;out=s/'epoch19';kit=args.kit.resolve()
    a_path=P+'audit/epoch19/acceptance-rejection-independent-v1.json'
    post_path=P+'audit/epoch19/postrun-source-process-independent-v1.json'
    id_path=P+'legal-transfer/epoch19/postrun-identity-retirement-v1.json'
    raw_path=P+'epoch19/runs/qualification/raw.json';ex_path=P+'epoch19/runs/qualification/execution.json'
    a=read(root/a_path);post=read(root/post_path);ids=read(root/id_path)
    v=read(root/raw_path);e=read(root/ex_path);plan=read(out/'plan.json')
    assert all(z['checks_passed'] is True for z in (a,post,ids))
    assert a['engineering_qualified'] is False and a['accepted'] is False and a['status']=='REJECTED_ENGINEERING_QUALIFICATION'
    assert a['plan_sha256']==sha(out/'plan.json')==e['plan_sha256']==v['plan_sha256']
    assert a['raw_receipt_identity']['sha256']==sha(root/raw_path)==e['raw_sha256']
    assert a['outer_execution_identity']['sha256']==sha(root/ex_path)
    assert e['qualification_worker_attempts']==e['verified_worker_starts']==1 and e['worker_exit_code']==0 and e['error'] is None
    assert e['elapsed_seconds']<=600 and len(e['CPU_affinity'])<=2
    assert all(e['cleanup'][k] is True for k in ('worker_exited','native_helper_exited','process_group_empty'))
    assert e['cleanup']['owned_live_pids']==[] and post['actual_OS_owned_process_group_live_members']==[]
    assert v['counters']['nli_forward_pairs_completed']==6 and v['counters']['native_queries_completed']==3
    now=datetime.now(timezone.utc).isoformat()
    refs={'independent_acceptance':ref(root,a_path),'postrun_source_process':ref(root,post_path),
        'postrun_identities':ref(root,id_path),'raw':ref(root,raw_path),'execution':ref(root,ex_path),
        'plan':ref(root,P+'epoch19/plan.json'),'source_freeze':ref(root,P+'epoch19/candidate-source-freeze.json'),
        'precision_provenance_cross_epoch':ref(root,P+'audit/epoch19/precision-provenance-cross-epoch-v1.json')}
    uncertainty=[
        'Exactly three publicly authored exposed CC0 engineering examples, not a random or benchmark sample; no legal/generalization/official placement estimate.',
        'FP32 inference got the neutral fixture wrong; dynamic INT8 changed one prediction and distributions. These fixed-pair observations do not identify the cause of epoch18 legal errors.',
        'Three short direct-pair timings per precision and three tiny deterministic-vector searches; no full serving, legal-context, embedding or benchmark deployment performance claim.',
        'One CPU configuration and one process; no precision/model/ANN grid, confidence/calibration fitting or confirmation selection.',
        'Official publisher score/rank and complete ClaimBench dataset/scorer/license/submission access remain unverified.']
    actual={'qualification_worker_attempts':e['qualification_worker_attempts'],'verified_worker_starts':e['verified_worker_starts'],
        'completed_qualification_workers':1,'NLI_forward_pairs_attempted':v['counters']['nli_forward_pairs_attempted'],
        'NLI_forward_pairs_completed':v['counters']['nli_forward_pairs_completed'],
        'FP32_forwards':3,'INT8_forwards':3,'native_index_initializations':1,'native_searches_completed':v['counters']['native_queries_completed'],
        'model_initializations':v['counters']['model_initializations'],'quantization_initializations':v['counters']['quantization_initializations'],
        'converted_Linear_modules':v['int8_state']['quantized_linear_count'],'benchmark_corpora':0,'benchmark_HTTP_requests':0,
        'TRAIN_calibration_fits':0,'CONF_calls':0,'new_legal_inputs_or_labels':0,'paid_API_calls':0,'GPU_calls':0,
        'CPU_affinity':e['CPU_affinity'],'torch_interop_threads':1,'wall_seconds_including_init_cleanup':e['elapsed_seconds'],
        'user_seconds':e['user_seconds'],'system_seconds':e['system_seconds'],'peak_RSS_bytes':e['peak_RSS_bytes'],
        'memory_scope':e['resource_scope'],'errors':0,'owned_live_processes_closed':True,
        'all_unused_slots_closed':True,'allowed_further_epoch19_attempts':0}
    metrics={'FP32_correct':a['FP32_correct'],'INT8_correct':a['INT8_correct'],'n_per_precision':3,
        'FP32_predictions':a['FP32_predictions'],'INT8_predictions':a['INT8_predictions'],
        'labels_matching':a['labels_matching'],'maximum_absolute_per_class_probability_delta':a['maximum_absolute_per_class_probability_delta'],
        'FP32_proper_scores':a['FP32_proper_scores'],'INT8_proper_scores':a['INT8_proper_scores'],
        'FP32_latency':a['FP32_latency'],'INT8_latency':a['INT8_latency'],
        'native_search_latency':post['native_search_latency'],'scope':'Engineering-only; no benchmark accuracy or generalization.'}
    results={'schema_version':1,'epoch':19,'at':now,'status':a['status'],'checks_passed':True,
        'engineering_qualified':False,'benchmark_accepted':False,'evidence':refs,'actual_execution':actual,
        'engineering_metrics':metrics,'frozen_gates':a['gates'],'raw_forward_predictions_and_probabilities':v['forwards'],
        'model_provenance':v['model_provenance'],'loaded_parameter_count':v['fp32_state']['parameter_count'],
        'FP32_state_sha256':v['fp32_state']['sha256'],'INT8_state_sha256':v['int8_state']['sha256'],
        'uncertainty':uncertainty,'official_score':None,'official_rank':None,'champion_promoted':False}
    put(out/'RESULTS.json',results)
    old_cont=read(kit/'CONTINUATION.json')
    used={'schema_version':1,'epoch':19,'kind':'USED_ENGINEERING_IDENTITIES_NO_BENCHMARK_CONFIRMATION',
        'actual_worker_attempts':1,'engineering_canary_manifest':ref(root,P+'legal-transfer/epoch19/canaries.json'),
        'engineering_fixture_ids':[r['id'] for r in read(root/(P+'legal-transfer/epoch19/canaries.json'))['fixtures']],
        'engineering_pair_records':6,'these_are_public_exposed_engineering_fixtures_not_fresh_confirmation':True,
        'TRAIN':[],'DEV':[],'calibration':[],'fresh_confirmation':[],'used_confirmation_identities_this_epoch':[],
        'prior_used_confirmation_sets_remain_DEV_forever':old_cont['used_confirmation_sets'],
        'prior_unused_confirmation_bank_metadata':old_cont['unused_confirmation_sets'],
        'originaltrain_partition_preserved':{'exposed':221,'unreserved':178,'reserved':24},
        'all_prior_DEV_exposed_forever':True,'confirmation_labels_or_model_inputs_consumed':0,
        'identity_audit':refs['postrun_identities'],'no_train_calibrate_or_select_on_confirmation_labels':True}
    put(out/'USED_IDENTITIES.json',used)
    ledger=read(s/'epoch18/REJECTION_LEDGER.json')
    rejection={'epoch':19,'kind':'ENGINEERING_QUALIFICATION_ONLY','status':a['status'],'accepted':False,
        'FP32_correct':a['FP32_correct'],'INT8_correct':a['INT8_correct'],'n_per_precision':3,'max_probability_drift':a['maximum_absolute_per_class_probability_delta'],
        'frozen_drift_limit':0.05,'frozen_semantic_requirement':'3/3 each precision',
        'reason':'Both semantic readiness gates fail and dynamic-int8 fidelity fails; no benchmark/confirmation measurement or promotion.',
        'independent_report':refs['independent_acceptance'],'actual_execution':actual,
        'cause_of_epoch18_legal_failure':'UNPROVEN','champion_replaced':False}
    ledger['rejections'].append(rejection);ledger['epoch19_decision']=rejection
    next_priority='Reject this exact xlarge dynamic-qint8 recipe for promotion. Before another legal draw, freeze a materially different licensed pretrained typed-NLI model/precision hypothesis with credible Neutral handling and semantic/fidelity qualification. Any later native-vs-matched-same-model retrieval benchmark needs a new frozen fresh DEV and genuinely unused CONF gate plus proper-score/runtime checks. Do not infer epoch18 causation, repeat this unchanged recipe, or treat engineering canaries/exposed DEV as benchmark confirmation.'
    ledger['next_research_priority']=next_priority
    put(out/'REJECTION_LEDGER.json',ledger)
    manifest={'schema_version':1,'epoch':19,'kind':'REAL_NATIVE_ENGINEERING_SEMANTIC_PRECISION_QUALIFICATION',
        'created_at':now,'finished_at':e['at'],'status':a['status'],'checks_passed':True,
        'engineering_qualified':False,'accepted':False,'source_checkpoint':'6eb624feef9ea93c3b1a8f76c20e8442c6bece50',
        'published_premeasurement_commit':'b4f32720a212f1735ba71cbfee539152715c883a',
        'evidence':refs,'actual_execution':actual,'engineering_metrics':metrics,'uncertainty':uncertainty,
        'actual_checkpoint_storage_precision':post['observed_serialized_checkpoint_precision'],
        'loaded_inference_precisions':['Explicit FP32 from original FP16 tensors','Same loaded model dynamic-qint8 Linear, FP32 remainder, fbgemm'],
        'model_repository':'microsoft/deberta-v2-xlarge-mnli','model_revision':'2b65bccdedcead4bc685988bcc30153d4922a789',
        'source_licenses':{'fixtures':'CC0-1.0','model_card':'MIT','source_code_native_package':'Original notices preserved'},
        'frozen_scorer':{'path':P+'audit/epoch19/scorer.py','sha256':a['scorer_source_sha256']},
        'roles':{'TRAIN':[],'DEV':[],'calibration':[],'fresh_confirmation':[]},
        'budget':{'user_process_slot_maximum':2,'frozen_qualification_attempt_cap':1,'used':1,
            'all_remaining_slots_closed':True,'CPU_threads':2,'seconds_limit_including_init_cleanup':600,'new_paid_GPU_cost_USD':0},
        'cumulative':{'prior_corpus_attempts':19,'prior_completed_corpora':17,'prior_successful_HTTP':885,
            'prior_failed_HTTP':2,'new_qualification_attempts':1,'bounded_worker_attempts_total':20,
            'new_benchmark_corpora':0,'new_benchmark_HTTP':0,'scope':'Engineering and corpus counts are deliberately distinct.'},
        'results':ref(root,P+'epoch19/RESULTS.json'),'used_identities':ref(root,P+'epoch19/USED_IDENTITIES.json'),
        'rejection_ledger':ref(root,P+'epoch19/REJECTION_LEDGER.json'),'next_research_priority':next_priority,
        'champion':'SubmittedNative104/RRF10 unchanged','champion_promoted':False,'publisher_submission_allowed':False,
        'new_submission_or_author_email':False,'official_score':None,'official_rank':None,'official_SOTA_verified':False,
        'publisher_status':ref(root,P+'legal-transfer/epoch19/publisher-status.json'),
        'benchmark_refresh':ref(root,P+'legal-transfer/epoch19/benchmark-refresh.json'),
        'host_work_lock_release':'Pending exact final checkpoint publication/readback; all owned native processes are already closed.'}
    put(out/'EPOCH_MANIFEST.json',manifest)
    helper_path=out/'publication/prepare_publication.py'
    spec=importlib.util.spec_from_file_location('report19inventory',helper_path)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    current=helper.walk_current(root)
    files=[{'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(current.items())]
    source={'schema_version':1,'epoch':19,'at':now,'status':a['status'],'source_checkpoint':manifest['source_checkpoint'],
        'published_premeasurement_commit':manifest['published_premeasurement_commit'],'files':files,
        'scientific_snapshot':refs['source_freeze'],'immutable_plan':refs['plan'],
        'actual_independent_decision':refs['independent_acceptance'],'actual_identity_retirement':refs['postrun_identities'],
        'actual_execution':actual,'accepted':False,'engineering_qualified':False,'champion_unchanged':True,
        'official_score':None,'official_rank':None,
        'scope':'All new19 files existing at this reporting snapshot, excluding this self-referential manifest and later appended final publication reviews/transport receipts. Full final CP and exact Git leaf readback separately cover every published file. No frozen source, role, scorer, budget or gate was changed after measurement.'}
    put(out/'SOURCE_MANIFEST.json',source)
    return {'status':a['status'],'new_final_artifacts':5,'reporting_snapshot_files':len(files),'model_native_calls':0}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--kit',type=Path,required=True)
    print(json.dumps(build(ap.parse_args())))
