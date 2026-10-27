"""E56 one-shot real SciFact retrieval DEV forecasts; qrels forbidden in this process.

No scoring, training, calibration, NLI model, confirmation, or publisher action.
All rankings are sealed before independent physical closure and separate scoring.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from inherited_guards import NetworkAudit,memory_snapshot,require_headroom
from io_guard import DeniedOpenAudit
from search_policy import apply_exact_absent_interpreter_zip_policy
import retrieval_support as s
KIND=s.KIND
PHASE=s.PHASE


def main():
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--expected-plan-sha256',required=True);p.add_argument('--admission',required=True);p.add_argument('--expected-admission-sha256',required=True);p.add_argument('--out-dir',required=True);p.add_argument('--deadline',required=True,type=float);a=p.parse_args()
 started=time.monotonic();s.need(math.isfinite(a.deadline)and 0<a.deadline-started<=570,'ABSOLUTE_RETRIEVAL_DEADLINE');s.need(sorted(os.sched_getaffinity(0))==[0,1],'CPU_AFFINITY_0_1')
 out=Path(a.out_dir);s.need(out.is_absolute()and out.is_dir()and not out.is_symlink(),'PRIVATE_RUN_DIRECTORY')
 counters=Counter();network=NetworkAudit(counters);sys.addaudithook(network);network.install_socket_guards();denied=DeniedOpenAudit(counters,maximum_events=64)
 def guarded(event,args):
  denied.set_stage(network.stage);denied(event,args)
 sys.addaudithook(guarded)
 def deadline():
  left=a.deadline-time.monotonic();s.need(left>0,'RETRIEVAL_WORKER_DEADLINE');return left
 fd=os.open(out/'worker-progress.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 def progress(stage):
  deadline();row={'stage':stage,'monotonic_seconds':time.monotonic(),'counters':dict(counters)};b=(json.dumps(row,sort_keys=True,allow_nan=False)+'\n').encode();s.need(os.write(fd,b)==len(b),'COMPLETE_PROGRESS_WRITE');os.fsync(fd)
 raw={'schema_version':1,'epoch':56,'kind':KIND,'phase':PHASE,'status':'PARTIAL_RETRIEVAL_DEVELOPMENT_NOT_SCORED','plan_sha256':a.expected_plan_sha256,'counters':{},'errors':[],'typed_model_initializations':0,'NLI_forwards':0,'quality_metrics':{'accuracy':None,'Brier':None,'NLL':None},'benchmark_generalization_claim':False,'candidate_promoted':False,'used_confirmation_identities':[],'native_state':{},'semantic_gold_decodes':0,'rows':[],'actual_pilot_attempted':True,'attempt_evidence_scope':'Actual worker entry; RootCLI/outer receipts separately bind invocation and physical closure.','actual_feature_query_ids':[],'actual_feature_query_ids_uncertain':False,'actual_scored_query_ids':[],'reserved_development_query_ids':[],'identity_namespace':None}
 rc=2
 try:
  pb=Path(a.plan).read_bytes();s.need(hashlib.sha256(pb).hexdigest()==a.expected_plan_sha256,'FROZEN_PLAN_SHA256');plan=json.loads(pb);plan['_sha256']=a.expected_plan_sha256;plan['path']=a.plan
  ab=Path(a.admission).read_bytes();s.need(hashlib.sha256(ab).hexdigest()==a.expected_admission_sha256,'ADMISSION_SHA256');ad=json.loads(ab)
  s.need(plan['epoch']==ad['epoch']==56 and plan['kind']==ad['kind']==KIND and plan['phase']==PHASE and ad['allowed']is True and ad['plan_sha256']==a.expected_plan_sha256 and ad['source_publication_independently_verified']is True,'ROOT_EXACT_SOURCE_ADMISSION')
  raw['reserved_development_query_ids']=plan['selected_query_ids'];raw['identity_namespace']=plan['identity_namespace']
  goldpaths={os.path.abspath(x)for x in plan['gold_paths_forbidden_to_worker']};s.need(goldpaths,'EXACT_QRELS_DENY_PATHS_REQUIRED')
  def no_gold(event,args):
   if event=='open'and args and isinstance(args[0],(str,bytes,os.PathLike)):
    path=os.fsdecode(args[0]);base=Path(path).name.lower()
    if os.path.abspath(path)in goldpaths or ('qrels'in base and Path(path).suffix.lower()in {'.tsv','.csv','.jsonl','.parquet','.gz','.zip'}):
     counters['qrels_or_label_file_access_attempts']+=1;raise RuntimeError('RETRIEVAL_QRELS_LABEL_PAYLOAD_FORBIDDEN')
  sys.addaudithook(no_gold)
  for row in ad['source_files']:s.verify(row)
  baseline=memory_snapshot();raw['pre_assets_shared_cgroup']=baseline;require_headroom(baseline)
  network.set_stage('exact_absent_interpreter_zip_search_policy');raw['metadata_search_policy']=apply_exact_absent_interpreter_zip_policy(plan['metadata_search_policy'])
  s.need(plan['maximum_native_batches']==1 and plan['maximum_outer_seconds']==600 and plan['typed_model_initializations_authorized']==plan['NLI_forwards_authorized']==0,'DEV_RETRIEVAL_RESOURCE_SCOPE')
  corpus,queries=s.features(plan,raw);ids=[d['_id']for d in corpus];qids=[d['_id']for d in queries]
  texts=[d['title']+' '+d['text']for d in corpus];input_texts=texts+[s.BGE_PREFIX+d['text']for d in queries]
  raw['corpus_features_ref']=plan['corpus_features'];raw['query_features_ref']=plan['query_features'];raw['source_commit']=ad['source_commit'];raw['selected_query_ids']=qids
  progress('BGE_BEFORE');before=time.monotonic();matrix,embedding,receipt=s.embed(plan,input_texts,counters,deadline,progress,network)
  raw['BGE_runtime']=receipt;raw['embedding_audit']=embedding;raw['BGE_total_seconds']=time.monotonic()-before
  vectors=matrix[:5183];qvectors=matrix[5183:];bundle={'schema_version':1,'epoch':56,'kind':KIND,'phase':PHASE,'plan_sha256':a.expected_plan_sha256,'corpus':{'ids':ids,'vectors':s.block(vectors)},'queries':{'ids':qids,'vectors':s.block(qvectors)}}
  network.set_stage('native_retrieval');native=s.native(plan,bundle,out,counters,deadline,progress,raw['native_state']);raw['native_result']=native
  s.need([r['query_id']for r in native['queries']]==qids,'NATIVE_QUERY_ID_ORDER')
  before=time.monotonic();index=s.bm25_index(texts);raw['BM25_corpus_index_seconds']=time.monotonic()-before;progress('MATCHED_BASELINES_BEFORE')
  ranks={'native':{},'exact_cosine':{},'bm25':{}};native_ids=set(ids)
  for i,q in enumerate(queries):
   deadline();n=native['queries'][i]
   s.need(len(n['ids'])==len(set(n['ids']))==10 and set(n['ids'])<=native_ids and len(n['scores'])==10 and all(type(x)in(int,float)and math.isfinite(x)for x in n['scores']),'COMPLETE_NATIVE_TOP10')
   rows=[('native',n['ids'],n['scores'],n['elapsed_seconds'])]
   for arm,method in [('exact_cosine',lambda:s.cosine_query(qvectors[i],vectors,ids)),('bm25',lambda:s.bm25_query(q['text'],index,ids))]:
    before=time.monotonic();order,scores=method();elapsed=time.monotonic()-before;rows.append((arm,[ids[j]for j in order],scores,elapsed))
   for arm,docids,scores,elapsed in rows:
    s.need(len(docids)==10 and len(set(docids))==10 and all(d in native_ids for d in docids)and len(scores)==10 and math.isfinite(elapsed)and elapsed>=0,'MATCHED_TOP10_FORECAST')
    rank_scores={docid:10-rank for rank,docid in enumerate(docids)};ranks[arm][q['_id']]=rank_scores
    raw['rows'].append({'query_id':q['_id'],'arm':arm,'ids':docids,'raw_method_scores':scores,'rank_scores':rank_scores,'query_search_seconds':elapsed,'predictions_are_retrieval_ranks_not_semantic_probabilities':True})
   counters['matched_query_forecasts_completed']+=1;progress('MATCHED_QUERY_FORECAST_COMPLETE')
  s.need(counters['matched_query_forecasts_completed']==16 and len(raw['rows'])==48,'ALL48_MATCHED_QUERY_FORECASTS')
  s.need(raw['native_state']['accounting']['qualified']and counters['native_index_initializations_completed']==1 and counters['native_insertions_completed']==5183 and counters['native_queries_completed']==16,'ACTUAL_NATIVE_CAPS_AND_ACCOUNTING')
  s.need(network.receipt()['admissible']and counters['Node_network_operations_attempted']==0 and counters['forbidden_model_or_archive_file_access_attempts']==0 and counters['qrels_or_label_file_access_attempts']==0,'NO_EXTERNAL_IO_WEIGHTS_OR_QRELS')
  forecasts={'schema_version':1,'epoch':56,'kind':KIND,'phase':PHASE,'role':'PROJECT_DEVELOPMENT_SOURCE_OFFICIAL_TEST_SUBSET','selected_query_ids':qids,'corpus_document_count':5183,'plan_sha256':a.expected_plan_sha256,'source_commit':ad['source_commit'],'corpus_features_ref':plan['corpus_features'],'query_features_ref':plan['query_features'],'rankings':ranks,'rows':raw['rows'],'metric_score_encoding':'Strict descending rankcodes10..1; not calibrated probabilities or native distance reinterpretation.','tie_policy':'exactcosine/BM25 allcorpus equal scores doc-ID lexical; native only returned adjacent equal-score tie groups canonicalized, global boundary ties unverified.','quality_metrics':None,'semantic_gold_decodes_before_seal':0,'used_confirmation_identities':[],'benchmark_generalization_claim':False,'candidate_promoted':False,'identity_namespace':plan['identity_namespace'],'actual_feature_query_ids':qids,'actual_scored_query_ids':[]}
  raw['forecast_seal']=s.put(out/'forecasts.json',forecasts);raw['status']='RETRIEVAL_DEVELOPMENT_FORECASTS_SEALED_NOT_SCORED';rc=0
 except BaseException as e:
  code=str(e);raw['errors'].append({'type':type(e).__name__,'code':code if code.replace('_','').isalnum()and len(code)<=120 else 'RETRIEVAL_WORKER_FAILURE_PRIVATE_TRACE_RETAINED'});(out/'worker.exception.txt').write_text(traceback.format_exc())
 finally:
  raw['network_audit']=network.receipt();raw['denied_open_audit']=denied.receipt()
  for k in ['typed_model_initializations','NLI_forwards_attempted','NLI_forwards_completed','semantic_gold_decodes','training_calls','calibration_calls','paid_API_calls','GPU_calls','qrels_or_label_file_access_attempts','forbidden_model_or_archive_file_access_attempts']:counters.setdefault(k,0)
  raw['counters']=dict(counters);raw['timing']={'worker_wall_seconds_including_init_and_capture':time.monotonic()-started,'started_monotonic_seconds':started,'completed_monotonic_seconds':time.monotonic()}
  u=resource.getrusage(resource.RUSAGE_SELF);c=resource.getrusage(resource.RUSAGE_CHILDREN)
  raw['resources']={'CPU_affinity':sorted(os.sched_getaffinity(0)),'compute_threads':2,'worker_max_RSS_KiB':u.ru_maxrss,'worker_user_seconds':u.ru_utime,'worker_system_seconds':u.ru_stime,'children_max_RSS_KiB':c.ru_maxrss,'children_user_seconds':c.ru_utime,'children_system_seconds':c.ru_stime,'RSS_scope':'SELF and CHILDREN highwater separately, never summed.','shared_cgroup':memory_snapshot()}
  raw['latency_scope']='Per-querysearch excludes shared BGE/corpus/index/init/capture/cleanup, recorded separately; inclusive outerclock is batchbound. Native queryincludes F32hitvalidation; exactcosine/BM25 includes exact rank sort.'
  os.close(fd);s.put(out/'raw.json',raw)
 return rc

if __name__=='__main__':raise SystemExit(main())
