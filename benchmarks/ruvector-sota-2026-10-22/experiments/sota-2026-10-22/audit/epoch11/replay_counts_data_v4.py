"""Independent saved-count/resource/identity audit; no model/native imports or fits."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,math,statistics
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x]
def digest(raw):return hashlib.sha256(raw).hexdigest()
def close(a,b):assert math.isclose(a,b,abs_tol=1e-12,rel_tol=0),(a,b)
def percentile(v,p):
 x=sorted(v);t=(len(x)-1)*p;l=math.floor(t);u=math.ceil(t);return x[l]+(x[u]-x[l])*(t-l)
def answer(response,name):
 if name=='native104_on_ruvector_evidence':response=response['baseline104_response']
 elif name!='ruvector_top2':response=response['ablation_responses'][name]
 return response['answers']['decision']
def run(root,frozen_project=None):
 s=root/'experiments/sota-2026-10-22';e=s/'epoch11';run=e/'runs/development';contract=load(s/'legal-transfer/epoch11/data-contract.json');plan=load(e/'plan.json');original=rows(s/'legal-transfer/epoch11/development24.jsonl');meta=load(s/'legal-transfer/epoch11/confirmation-allowlist.json')
 assert contract['train']==contract['calibration']==[] and plan['train']==plan['calibration']=='none'
 assert len(original)==24 and len({x['source_group'] for x in original})==8 and len(meta['records'])==48 and len({x['source_group'] for x in meta['records']})==16
 assert digest((s/'legal-transfer/epoch11/development24.jsonl').read_bytes())==contract['development']['sha256']
 assert not {x['source_group'] for x in original}&{x['source_group'] for x in meta['records']}
 start,wire,record,server=[rows(run/n) for n in ('started-requests.jsonl','wire.jsonl','records.jsonl','server-audit.jsonl')];assert len(start)==len(wire)==len(record)==len(server)==24
 assert [x['id'] for x in original]==[x['id'] for x in record]==[x['id'] for x in wire]==[x['id'] for x in start]
 metrics={};names=['ruvector_top2','same_nli_lexical_top2','same_nli_positional_first2','native104_on_ruvector_evidence'];scores={n:[] for n in names};bundle_paths=set();BGE_texts=BGE_batches=NLI_tokens=0
 for source,st,w,rec,sv in zip(original,start,wire,record,server):
  assert rec['measured_phase']=='development' and st['phase']==w['phase']=='development'
  request=w['request'].encode();reply=w['response'].encode();inp=json.loads(w['request']);response=json.loads(w['response'])
  assert set(inp)=={'state','questions'} and inp==source['input']==rec['input'] and response==rec['response']
  assert st['request']==w['request'] and digest(request)==st['request_sha256']==w['request_sha256']==sv['request_sha256'];assert digest(reply)==w['response_sha256']==sv['response_sha256'];assert w['status']==sv['status']==200 and sv['ok'] and sv['error'] is None and sv['cost_per_decision_usd'] is None and sv['usage']['paid_calls']==0
  close(w['elapsed_s'],rec['elapsed_s']);assert rec['evaluation']==source['evaluation'] and rec['input_sha256']==source['input_sha256'] and rec['source_group']==source['source_group']
  d=response['diagnostics']['decision'];assert d['source_state']==inp['state'] and digest(inp['state'].encode())==d['source_state_sha256']
  desc=d['retrieval']['bundle_evidence'];p=run/'bundles'/desc['relativefilename'];assert p.name==desc['sha256']+'.json' and p.stat().st_size==desc['bytes'] and sha(p)==desc['sha256']==d['retrieval']['native']['bundle_sha256'];bundle_paths.add(p.name)
  bundle=load(p);assert len(bundle['vectors'])==d['total_chunks'] and len(bundle['query_vectors'])==1;dims={len(v) for v in bundle['vectors']+bundle['query_vectors']};assert dims=={384};assert all(math.isfinite(v) for line in bundle['vectors']+bundle['query_vectors'] for v in line)
  native=d['retrieval']['native'];assert native['native'] is True and native['native_binary_sha256']=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
  em=d['retrieval']['embedding'];BGE_batches+=sum(em[k]['model_batches'] for k in ('chunks','query'));BGE_texts+=len(em['query']['examples'])+(0 if em['chunks']['cache_hit'] else len(em['chunks']['examples']))
  for k in ('chunks','query'):
   for x in em[k]['examples']:assert not x['truncated'] and x['raw_tokens']==x['used_tokens']<=256
  for arm in d['arms'].values():
   dc=arm['decoding'];assert not dc['truncated'] and dc['padding_tokens']==0 and dc['batch_size']==1 and dc['used_tokens']==dc['raw_tokens']==dc['actual_model_pair_tokens']<=512;NLI_tokens+=dc['input_tokens']
  gold=source['evaluation']['gold']
  for n in names:
   a=answer(response,n);probs=a['probabilities'];assert a['type']=='choice' and a['choice'] in ('Yes','No') and set(probs)=={'Yes','No'} and all(math.isfinite(p) and 0<=p<=1 for p in probs.values());assert abs(sum(probs.values())-1.)<=1e-3;assert a['choice']==max(sorted(probs),key=lambda label:probs[label])
   correct=int(a['choice']==gold);brier=sum((probs[l]-float(l==gold))**2 for l in ('Yes','No'));nll=-math.log(max(1e-15,probs[gold]));scores[n].append((correct,brier,nll))
 assert len(bundle_paths)==len(list((run/'bundles').glob('*.json')))==24
 for name,vals in scores.items():metrics[name]={'n':24,'correct':sum(x[0] for x in vals),'brier':statistics.mean(x[1] for x in vals),'nll':statistics.mean(x[2] for x in vals)}
 report=load(run/'development-comparison.json');summary=load(e/'study-completion.json');completion=load(run/'completion.json');resources=load(run/'resources.json');runtime=load(run/'runtime.json');attempt=load(run/'attempt.json');marker=load(run/'popen-attempt.json');counters=load(run/'final-engine.json')['execution_after_close']['counters'];independent=load(s/'audit/epoch11/actual-independent-v1.json')
 for n,m in metrics.items():
  target=report['metrics'][n];assert target['n']==m['n'] and target['correct']==m['correct'] and target['strict_valid']==24 and target['errors']==0;close(target['brier'],m['brier']);close(target['nll'],m['nll'])
 assert [metrics[n]['correct'] for n in names]==[12,12,12,13];assert not report['frozen_development_gate_passed'] and not summary['development_gate_passed'] and summary['status']=='REJECTED_DEV_GATE'
 assert summary['actual_native_attempts']==summary['native_processes_started']==sum((e/'runs'/p/'popen-attempt.json').exists() for p in ('development','confirmation'))==1 and summary['lifetime_native_attempts']==14 and summary['unspent_phase_slots']==1 and summary['allowed_further_attempts_in_closed_study']==0
 assert summary['confirmation_consumed_or_attempted'] is False and summary['confirmation_phase_attempted'] is False and not (e/'runs/confirmation').exists()
 assert completion['native_process_started'] and completion['popen_invocation_reserved'] and completion['exit_code']==0 and completion['error'] is None and completion['source_plan_unchanged'] and completion['wall_seconds_including_model_load']<=600 and not completion['owned_group_cleanup']['live_members_after'] and completion['owned_group_cleanup']['finished_within_deadline']
 assert marker['source_plan_sha256']==attempt['source_plan_sha256']==sha(e/'plan.json') and marker['at']<=attempt['at'] and attempt['pid']==runtime['pid'] and marker['lifetime_native_attempt']==attempt['lifetime_native_attempt']==14
 assert counters['requests_completed']==counters['native104_requests_completed']==counters['native_core_searches_completed']==24 and counters['nli_forward_pairs_completed']==72 and counters['nli_input_tokens_completed']==NLI_tokens==35119 and counters['bge_texts_completed']==BGE_texts==179 and counters['bge_forward_batches_completed']==BGE_batches==46
 assert resources['allowed_CPU_ids']==[0,1] and resources['configured_ORT_threads']==2
 CPU=sum(resources[k] for k in ('worker_cpu_user_seconds','worker_cpu_system_seconds','terminated_children_cpu_user_seconds','terminated_children_cpu_system_seconds'));assert CPU<=2*completion['wall_seconds_including_model_load']+2
 elapsed=[x['elapsed_s'] for x in wire];latency={'p50':statistics.median(elapsed),'p95':percentile(elapsed,.95),'max':max(elapsed)}
 for k,v in latency.items():close(v,independent['latency_by_phase_seconds']['development'][k])
 frozen=frozen_project if frozen_project else e/'project';excluded=contract['confirmation']['path'];pins=[]
 for x in plan['pins']:
  if x['path']==excluded:continue
  p=frozen/x['path'];assert p.is_file() and sha(p)==x['sha256'],x['path'];pins.append(x['path'])
 assert len(pins)==172 and independent['source_pins_verified']==173 and independent['checks_passed']
 base=load(e/'durable-kit/CONTINUATION.json')['execution_observed'];totals={'attempts':base['native_corpus_attempts_including_failed_request']+1,'completed_batches':base['native_corpus_batches_completed']+1,'success_HTTP':base['actual_HTTP_successful_decisions']+24,'TRAIN_HTTP':base['actual_HTTP_training_feature_requests'],'evaluation_HTTP':base['actual_HTTP_evaluation_diagnostic_decisions']+24,'historic_failed_HTTP':base['actual_HTTP_failed_requests']};assert totals=={'attempts':14,'completed_batches':12,'success_HTTP':759,'TRAIN_HTTP':144,'evaluation_HTTP':615,'historic_failed_HTTP':2}
 return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'audit_source':Path(__file__).name,'audit_source_sha256':sha(Path(__file__)),'server_USD_cost_reported':None,'paid_API_calls_verified':0,'scope':'Saved actual count/resource/identity/probability arithmetic only; no model/native imports, new fit, inference, or CONF label parse. This data worker directly hashes172/173pins, excluding unused fullCONF and referring to mainauditor all173proof.','plan_sha256':sha(e/'plan.json'),'direct_frozen_pins_checked':172,'excluded_full_confirmation_pin':excluded,'main_auditor_all173pin_reference_sha256':sha(s/'audit/epoch11/actual-independent-v1.json'),'matched_started_wire_records_server':24,'TRAIN_requests':0,'DEV_requests':24,'CONF_requests':0,'errors':0,'finite_hash_valid_native_vectorbundles':24,'metrics':metrics,'latency_whole_HTTP_seconds':latency,'wall_seconds':completion['wall_seconds_including_model_load'],'CPU_seconds_worker_plus_terminated_children':CPU,'resource_scopes':resources,'execution_counters':counters,'process_attempts':{'conservative_Popen_invocations':1,'PID_confirmed_native_process_starts':1,'closed_cap':2,'unspent_slots':1,'allowed_further':0},'cumulative':totals,'identities':{'prior_exposed':165,'new_DEV_groups_retired':8,'exposed_now':173,'unreserved_after_fixed_draw':234,'CONF_reserved_groups':16,'CONF_reserved_queries':48,'confirmation_model_unused':True},'source_data_raw_unchanged':True,'confirmation_labels_inspected':False,'auditor_models_native_fits_paid_calls':0}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=HERE.parents[3]);p.add_argument('--frozen-project',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();result=run(a.root,a.frozen_project);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks_passed':True,'out_sha256':sha(a.out),'DEV_n':result['DEV_requests'],'errors':result['errors'],'cumulative':result['cumulative']}))
