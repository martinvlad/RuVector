"""Epoch18 final-report skeleton: aggregate saved evidence, never run/score models.

Output is an exclusive new OUTSIDE-project directory. Root must independently
review these derived bytes before copying/publication. Case/evaluation/answer
fields are never inspected; wire JSON is projected only to status/elapsed/id.
"""
from __future__ import annotations
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path

PREFIX='experiments/sota-2026-10-22/'
PLAN_SHA='f2eb56b436bc499f4a63d724dc6055a5e1e69e82892cb41d1db4e023af49e7eb'
SOURCE='0eac156990f5a4ee0084af635eb3089913b437ff'
PHASES=('development','confirmation')
BINARY_ARMS=('ruvector_top2','native104_on_ruvector_evidence','same_nli_lexical_top2',
             'same_nli_positional_first2','previous_reader_native_same_premise')
TYPED_ARMS=tuple(a for a in BINARY_ARMS if a!='native104_on_ruvector_evidence')
BASE={'native_corpus_batches':16,'actual_HTTP_decisions':861,'paid_inference_calls':0,
      'new_GPU_rentals':0,'native_corpus_batches_completed':16,
      'native_corpus_attempts_including_failed_request':18,'actual_HTTP_successful_decisions':861,
      'actual_HTTP_failed_requests':2,'actual_HTTP_training_feature_requests':144,
      'actual_HTTP_evaluation_diagnostic_decisions':711,'actual_HTTP_training_sanity_diagnostic_requests':6}
RETAIN=(PREFIX+'epoch18/final-freeze-first-failure.json',
        PREFIX+'epoch18/publication-fixture-exact-restoration-v1.json',
        PREFIX+'audit/epoch18/exact-publication-fixture-restoration-review-v1.json',
        PREFIX+'epoch18/reviews/frozen-remote-readback-v1.json',PREFIX+'epoch18/NATIVE_ADMISSION.json')
COUNTERS=('requests_attempted','requests_completed','native104_requests_attempted','native104_requests_completed',
          'native_core_searches_attempted','native_core_searches_completed','bge_forward_batches_attempted',
          'bge_forward_batches_completed','bge_texts_attempted','bge_texts_completed',
          'nli_forward_pairs_attempted','nli_forward_pairs_completed','new_reader_forward_pairs_attempted',
          'new_reader_forward_pairs_completed','previous_reader_forward_pairs_attempted',
          'previous_reader_forward_pairs_completed','nli_input_tokens_attempted','nli_input_tokens_completed')


def regular(p):
    p=Path(p).absolute()
    if any(x.is_symlink()for x in (p,*p.parents))or not p.is_file():raise ValueError('Unsafe/missing file: '+str(p))
    return p


def sha(p):
    h=hashlib.sha256()
    with regular(p).open('rb')as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def read(p):return json.loads(regular(p).read_text())
def optional(p):return read(p)if p.exists()else None

def ident(p,root):
    p=regular(p);return {'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}


def linecount(p):
    if not p.exists():return 0
    with regular(p).open('rb')as f:return sum(bool(line.strip())for line in f)


def wire_metadata(p):
    values=[]
    if not p.exists():return values
    with regular(p).open()as f:
        for line in f:
            if not line.strip():continue
            # Deliberately never access request/response/evaluation/case/gold.
            row=json.loads(line)
            value={k:row[k]for k in ('id','status','elapsed_s')}
            if type(value['status'])is not int or type(value['elapsed_s'])not in (int,float)or not math.isfinite(value['elapsed_s'])or value['elapsed_s']<0:
                raise ValueError('Invalid saved HTTP timing/status metadata')
            values.append(value)
    return values


def percentile(values,q):
    if not values:return None
    ordered=sorted(values);x=(len(ordered)-1)*q;lo=math.floor(x);hi=math.ceil(x)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(x-lo)


def finite_number(value):return type(value)in (int,float)and math.isfinite(value)


def decision_check(decision):
    if decision.get('plan_sha256')!=PLAN_SHA or decision.get('checks_passed')is not True:
        raise ValueError('Exact independently completed plan-bound acceptance/rejection required')
    if type(decision.get('accepted'))is not bool or not isinstance(decision.get('status'),str)or not decision.get('next_priority'):
        raise ValueError('Explicit independent accepted/status/next_priority required')
    if decision['accepted']and any(decision.get(k)is not True for k in
        ('independent_replays_passed','DEV_gate_passed','CONF_gate_passed','actual_confirmation_completed')):
        raise ValueError('Acceptance requires all independent DEV/unused-CONF/replay gates')
    for key in ('champion_promoted','publisher_submission_allowed','official_sota_goal_met'):
        if decision.get(key)not in (None,False):raise ValueError('Reporting never promotes/submits/claims official SOTA')
    if decision.get('official_score')is not None or decision.get('official_rank')is not None:
        raise ValueError('Official result requires a separate verified publisher workflow')
    return decision['accepted']


def phase_evidence(root,phase):
    folder=root/PREFIX/'epoch18/runs'/phase
    popen=optional(folder/'popen-attempt.json');attempt=optional(folder/'attempt.json')
    completion=optional(folder/'completion.json');report=optional(folder/'report.json')
    runtime=optional(folder/'runtime.json');final=optional(folder/'final-engine.json')
    measured=optional(folder/'measured-execution.json');resources=optional(folder/'resources.json')
    cleanup=optional(folder/'cleanup.json');comparison=optional(folder/(phase+'-comparison.json'))
    wire=wire_metadata(folder/'wire.jsonl');started=linecount(folder/'started-requests.jsonl')
    records=linecount(folder/'records.jsonl');success=sum(row['status']==200 for row in wire)
    if success>started or records>success:raise ValueError('HTTP/started/saved-record counts inconsistent')
    reserved=popen is not None or attempt is not None
    for value in (popen,attempt,completion):
        if value and value.get('source_plan_sha256')not in (None,PLAN_SHA):raise ValueError('Phase uses a different plan')
    verified_start=attempt is not None or bool(completion and completion.get('native_process_started')is True)
    uncertain_start=reserved and not verified_start and not(completion and completion.get('native_process_started')is False)
    snapshots=[v for v in ((final or{}).get('execution_after_close'),(measured or{}).get('execution'))if isinstance(v,dict)]
    counters=snapshots[0].get('counters',{})if snapshots else None
    if counters is not None:
        if any(k in counters and(type(counters[k])is not int or counters[k]<0)for k in COUNTERS):
            raise ValueError('Execution counter is not a nonnegative actual integer')
    timings=[row['elapsed_s']for row in wire if row['status']==200]
    receipt=(runtime or{}).get('receipt');new=(receipt or{}).get('new_reader',{})
    count_known=bool(receipt)or bool(completion and completion.get('native_process_started')is False)or not reserved
    def observed(key):return (counters or{}).get(key)if counters is not None else(0 if not reserved or(completion and completion.get('native_process_started')is False)else None)
    metadata={'phase':phase,'reserved_attempt':reserved,'verified_worker_started':verified_start,
        'possible_worker_start_unresolved':uncertain_start,'attempt_receipt':attempt,'report':report,'completion':completion,
        'started_HTTP_requests':started,'successful_HTTP_status200':success,'failed_or_unanswered_HTTP_requests':started-success,
        'saved_decision_records':records,'corpus_completed':success==24 and records==24 and(report or{}).get(phase+'_completed')==24,
        'binary_metrics':(comparison or{}).get('metrics'),'typed_metrics':(comparison or{}).get('typed_metrics'),
        'typed_confusions':(comparison or{}).get('typed_confusions'),'comparison':comparison,
        'latency':{'n_observed_successful_requests':len(timings),'p50_seconds':percentile(timings,.5),'p95_seconds':percentile(timings,.95),
          'method':'Linear interpolation on q*(n-1) of sorted successful HTTP elapsed_s',
          'scope':'Whole request: all3 new-reader retrieval arms, previous-reader same-premise forward, native104 evidence control and native retrieval; primary-only latency unmeasured'},
        'phase_initialization_seconds':(runtime or{}).get('phase_initialization_seconds'),
        'engine_initialization_seconds':(receipt or{}).get('initialization_wall_seconds'),
        'model_initializations':new.get('model_initializations',0 if count_known and not receipt else None),
        'model_initialization_count_scope':'New primary reader only; previous/BGE native receipts separately retained',
        'quantization_initializations':new.get('quantization_initializations',0 if count_known and not receipt else None),
        'previous_reader_session_initialized':(receipt or{}).get('old_base_NLI_session_initialized'),
        'actual_runtime_receipt':receipt,'actual_terminal_execution':snapshots[0]if snapshots else None,
        'execution_counters':counters,'resources':resources,'cleanup':cleanup,
        'observed_execution':{key:observed(key)for key in COUNTERS}}
    refs=[]
    for name in ('popen-attempt.json','attempt.json','completion.json','report.json','runtime.json','final-engine.json',
                 'measured-execution.json','resources.json','cleanup.json',phase+'-comparison.json','wire.jsonl',
                 'records.jsonl','started-requests.jsonl','progress.json','worker.log'):
        p=folder/name
        if p.exists():refs.append(ident(p,root))
    metadata['evidence']=refs
    return metadata


def known_sum(values):return None if any(v is None for v in values)else sum(values)


def cumulative(actual,old):
    for key,value in BASE.items():
        if old.get(key)!=value:raise ValueError('Historical cumulative base changed: '+key)
    result=copy.deepcopy(old)
    for key,delta in [('native_corpus_attempts_including_failed_request',actual['native_process_attempts']),
        ('native_corpus_batches_completed',actual['completed_native_corpora']),
        ('actual_HTTP_successful_decisions',actual['successful_HTTP_decisions']),
        ('actual_HTTP_failed_requests',actual['failed_HTTP_requests']),
        ('actual_HTTP_evaluation_diagnostic_decisions',actual['successful_HTTP_decisions'])]:result[key]+=delta
    result['native_corpus_batches']=result['native_corpus_batches_completed'];result['actual_HTTP_decisions']=result['actual_HTTP_successful_decisions']
    if result['actual_HTTP_decisions']!=result['actual_HTTP_evaluation_diagnostic_decisions']+144+6:raise ValueError('Cumulative diagnostic accounting inconsistent')
    return result


def derive_final_roles(prenative,phases,projected,consumed,snapshot_ref):
    """Current nested roles replace pre-run facts; unknown inference use stays null."""
    used=copy.deepcopy(prenative)
    used['historical_pre_native_snapshot']=copy.deepcopy(snapshot_ref)
    for role in PHASES:
        phase=phases[role];counts=phase.get('observed_execution',{})
        activity=any(type(v)is int and v>0 for v in counts.values())
        if activity or phase.get('started_HTTP_requests',0)>0:model_attempted=True
        elif not phase['reserved_attempt']or (phase.get('completion')or{}).get('native_process_started')is False:model_attempted=False
        elif counts and all(type(v)is int and v==0 for v in counts.values()):model_attempted=False
        else:model_attempted=None
        facts=used.setdefault(role,{})
        facts.update(model_attempted=model_attempted,phase_attempts=int(phase['reserved_attempt']),
            verified_worker_starts=int(phase['verified_worker_started']),
            HTTP_requests_started=phase['started_HTTP_requests'],HTTP_successful_decisions=phase['successful_HTTP_status200'],
            annotation_choices_projected=(24 if role=='development'else projected),
            conservatively_retired=(True if role=='development'else consumed),
            model_use_uncertainty=(None if model_attempted is not None else 'Worker/process receipt is incomplete; no inference-use zero claimed'))
    used.update(status='FINAL_ROLES_AND_ACTUAL_CONSUMPTION',development_exposed_forever_DEV=True,
        confirmation_retired_forever_DEV=consumed,confirmation_annotation_choices_projected=projected,
        confirmation_phase_reservations=int(phases['confirmation']['reserved_attempt']),
        confirmation_successful_HTTP=phases['confirmation']['successful_HTTP_status200'],old48_model_unused=True,
        model_attempted_definition='Observed model request/forward/native activity; actual per-model forward counts retained separately',
        originaltrain_partition={'exposed':221+(8 if consumed else 0),'unreserved':178,'reserved_unused':16 if consumed else 24})
    return used


def build(root,decision_path):
    root=Path(root).absolute();study=root/PREFIX/'epoch18';plan=read(study/'plan.json')
    if sha(study/'plan.json')!=PLAN_SHA or len(plan['pins'])!=415 or len({r['path']for r in plan['pins']})!=415:
        raise ValueError('Immutable415-pin actual plan required')
    snapshot=read(study/'candidate-source-freeze.json')
    if snapshot['source_checkpoint']!=SOURCE or len(snapshot['files'])!=88:raise ValueError('Exact88-source snapshot required')
    for row in snapshot['files']:
        p=regular(root/row['path'])
        if ident(p,root)!=row:raise ValueError('Frozen scientific source changed: '+row['path'])
    decision=read(decision_path);accepted=decision_check(decision)
    retained=[ident(root/rel,root)for rel in RETAIN]
    admission=read(root/RETAIN[-1]);remote=read(root/RETAIN[-2])
    if admission.get('plan_sha256')!=PLAN_SHA or admission.get('checks_passed')is not True or remote.get('independent_remote_readback_passed')is not True:
        raise ValueError('Actual frozen publication/readback/native admission evidence required')
    if admission.get('independent_readback_sha256')!=sha(root/RETAIN[-2])or admission.get('source_commit')!=remote.get('commit'):
        raise ValueError('Native admission must bind exact independent published-source readback')
    summary=optional(study/'study-completion.json');phases={p:phase_evidence(root,p)for p in PHASES}
    admission_at=datetime.fromisoformat(admission['at'].replace('Z','+00:00')).timestamp()
    for phase in phases.values():
        receipt=phase['attempt_receipt']
        if receipt and(not finite_number(receipt.get('invocation_started_unix'))or receipt['invocation_started_unix']<admission_at):
            raise ValueError('Actual worker predates reviewed frozen-source admission')
    attempts=sum(p['reserved_attempt']for p in phases.values());starts=sum(p['verified_worker_started']for p in phases.values())
    if attempts>2 or decision.get('actual_native_process_reservations')!=attempts or decision.get('verified_worker_starts')!=starts:
        raise ValueError('Independent actual attempt/start counts disagree')
    if summary and(summary.get('actual_native_attempts')!=attempts or summary.get('allowed_further_attempts_in_closed_study')!=0):
        raise ValueError('Controller closure/attempt counts disagree')
    actual={'native_process_attempts':attempts,'native_processes_started_verified':starts,
        'native_process_start_uncertainties':sum(p['possible_worker_start_unresolved']for p in phases.values()),
        'attempt_count_scope':'Conservative pre-Popen durable reservations; reservation alone never proves a model or worker ran',
        'completed_native_corpora':sum(p['corpus_completed']for p in phases.values()),
        'successful_HTTP_decisions':sum(p['successful_HTTP_status200']for p in phases.values()),
        'failed_HTTP_requests':sum(p['failed_or_unanswered_HTTP_requests']for p in phases.values()),
        'decision_records_saved':sum(p['saved_decision_records']for p in phases.values()),
        'model_initializations':known_sum([p['model_initializations']for p in phases.values()]),
        'model_initialization_count_scope':'New primary reader only; complete previous/BGE receipt provenance retained per phase',
        'quantization_initializations':known_sum([p['quantization_initializations']for p in phases.values()]),
        'training_calibration_fits':0,'paid_API_calls':0,'GPU_calls':0,'unspent_phase_slots_closed':2-attempts,
        'allowed_further_epoch18_native_attempts':0}
    aliases={'NLI_forward_pairs_attempted':'nli_forward_pairs_attempted','NLI_forward_pairs_completed':'nli_forward_pairs_completed',
             'BGE_model_forwards':'bge_forward_batches_completed','BGE_texts':'bge_texts_completed',
             'native_core_searches':'native_core_searches_completed','native104_predictions':'native104_requests_completed',
             'new_reader_forwards':'new_reader_forward_pairs_completed','previous_reader_forwards':'previous_reader_forward_pairs_completed'}
    actual.update({key:known_sum([p['observed_execution'][field]for p in phases.values()])for key,field in aliases.items()})
    conf_receipt=optional(root/PREFIX/'legal-transfer/epoch18/confirmation-materialization.json')
    conf_file=root/PREFIX/'legal-transfer/epoch18/confirmation24.jsonl'
    projected=(conf_receipt or{}).get('annotation_choices_projected',0)
    if conf_file.exists()and not conf_receipt:raise ValueError('Partial CONF projection without receipt: exact annotation count unknown; require independent reconciliation, never infer zero')
    consumed=phases['confirmation']['reserved_attempt']or projected>0 or phases['confirmation']['started_HTTP_requests']>0
    if decision.get('confirmation_consumed')is not consumed:raise ValueError('Independent conservative confirmation retirement disagrees')
    if accepted and(not consumed or projected!=24 or not phases['confirmation']['corpus_completed']):raise ValueError('Accepted candidate lacks complete actual confirmation')
    used=derive_final_roles(read(study/'USED_IDENTITIES.pre-native.json'),phases,projected,consumed,
                            ident(study/'USED_IDENTITIES.pre-native.json',root))
    metrics={p:{k:phases[p][k]for k in ('binary_metrics','typed_metrics','typed_confusions','latency','phase_initialization_seconds',
        'engine_initialization_seconds','resources','execution_counters')}for p in PHASES}
    old=read(root/PREFIX/'epoch17/EPOCH_MANIFEST.json')['cumulative_execution'];total=cumulative(actual,old)
    results={'schema_version':1,'epoch':18,'status':decision['status'],'accepted':accepted,
        'scope':'Actual native original CC-BY4 ContractNLI three-predicate NDA diagnostic; not JevBench300/fullLegalBench/ClaimBench or official placement',
        'metrics_by_phase':metrics,'actual_execution':actual,'phases':phases,'study_completion':summary,
        'independent_decision':ident(decision_path,root),'frozen_plan':ident(study/'plan.json',root),
        'source_freeze':ident(study/'candidate-source-freeze.json',root),'preserved_pre_native_failures_and_recovery':retained,
        'pre_native_admission_errors':1,'inference_HTTP_errors':actual['failed_HTTP_requests'],
        'confirmation_choices_projected':projected,'confirmation_conservatively_retired':consumed,
        'champion_preserved':'SubmittedNative104/RRF10','official_score':None,'official_rank':None,'official_SOTA_verified':False}
    manifest={'schema_version':1,'epoch':18,'recorded_at':datetime.now(timezone.utc).isoformat(),'status':decision['status'],
        'source_epoch_closed':True,'accepted':accepted,'requested_native_measurement_completed':phases['development']['corpus_completed'],'resolved_source_commit':SOURCE,
        'exclusive_planning_lease_commit':'2e6aa4fca5acd9a5149c9f6b37aaf4360c035a45',
        'frozen_source_published_before_native_attempt':True,'published_source_commit':remote.get('commit'),
        'plan':ident(study/'plan.json',root),'source_freeze':ident(study/'candidate-source-freeze.json',root),
        'scientific_sources':88,'immutable_plan_pins':415,'actual_execution':actual,'benchmark_metrics':metrics,
        'confirmation':{'old48_model_unused':True,'exact_reused16CONF24_model_unused':not consumed,
            'CONF_annotations_projected':projected,'confirmation_attempts':int(phases['confirmation']['reserved_attempt'])},
        'originaltrain_partition':used['originaltrain_partition'],'cumulative_execution':total,
        'preserved_pre_native_failures_and_exact_recovery':retained,'independent_acceptance_rejection':ident(decision_path,root),
        'official_refresh':ident(root/PREFIX/'legal-transfer/epoch18/benchmark-refresh.json',root),
        'publisher_status':ident(root/PREFIX/'legal-transfer/epoch18/publisher-status.json',root),
        'publisher_scope':'Partial publisher-account search; additional account/broader search FORBIDDEN. No claim of official result absence; current result/rank unverified.',
        'champion':'SubmittedNative104/RRF10 unchanged','new_submission':False,'outbound_email':False,
        'paid_API_GPU_calls':0,'official_score':None,'official_rank':None,'official_SOTA_verified':False,
        'goal_met':False,'main_merge_release_packages_changed':False,'no_scheduled_work_claimed_executed':True,
        'automation_changed':False,'next_priority':decision['next_priority']}
    ledger=copy.deepcopy(read(root/PREFIX/'epoch17/REJECTION_LEDGER.json'))
    event={'epoch':18,'status':decision['status'],'accepted':accepted,'actual_execution':actual,
           'confirmation_consumed':consumed,'source_report':ident(decision_path,root),
           'scope':results['scope'],'champion_replaced':False}
    if not accepted:ledger['rejections'].append(event)
    ledger['epoch18_decision']=event;ledger.setdefault('preparation_blocks',[]).append({
        'epoch':18,'status':'ANCILLARY_FIXTURE_RACE_REJECTED_THEN_EXACT_REVIEWED_BYTES_RESTORED_NO_PLAN_REWRITE',
        'evidence':retained[:3],'scientific88_and_plan415_unchanged':True,'native_started_during_recovery':False})
    ledger['next_research_priority']=decision['next_priority'];ledger['epoch18_budget']={
        'this_epoch_native_attempts':attempts,'lifetime_native_attempts':18+attempts,'cap':2,
        'unspent_phase_slots_closed':2-attempts,'allowed_further_attempts':0,'CPU_threads':2,
        'max_seconds_each_including_initialization_cleanup':600,'paid_calls':0,'GPU_calls':0}
    def future(name,value):
        raw=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
        return {'path':PREFIX+'epoch18/'+name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    ledger['used_identity_manifest']=future('USED_IDENTITIES.json',used)
    manifest.update(results=future('RESULTS.json',results),used_identities=future('USED_IDENTITIES.json',used),
                    rejection_ledger=future('REJECTION_LEDGER.json',ledger))
    return {'RESULTS.json':results,'USED_IDENTITIES.json':used,'REJECTION_LEDGER.json':ledger,'EPOCH_MANIFEST.json':manifest}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True)
    p.add_argument('--acceptance',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    root=a.project.absolute();out=a.out.absolute()
    if out.exists()or out.is_symlink()or out.is_relative_to(root)or any(x.is_symlink()for x in out.parents):raise ValueError('Exclusive outside-project output required')
    objects=build(root,a.acceptance);out.mkdir(mode=0o700)
    for name,value in objects.items():(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':'DERIVED_FINAL_BYTES_REQUIRE_INDEPENDENT_REVIEW','files':list(objects),'Git_mutations':0,'inference_calls':0}))


if __name__=='__main__':main()
