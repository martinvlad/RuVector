"""Independent numerical/runtime replay of saved complete benchmark phases.

No inference, native process, ONNX/session, network or fit. Exact source/context
coverage is verified separately. Archived self-check is engineering validation,
not a new benchmark observation. The active epoch15 replay must bind plan SHA.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,math,random,statistics
ARMS={'ruvector_top2':None,'same_nli_lexical_top2':'lexical_top2','same_nli_positional_first2':'positional_first2','native104_on_ruvector_evidence':'baseline'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def obj(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x]
def close(a,b):assert math.isclose(float(a),float(b),rel_tol=0,abs_tol=1e-10),(a,b)
def distribution(p,labels):
 assert set(p)==set(labels) and all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=1 for x in p.values())
 assert abs(sum(p.values())-1)<=1e-3
 return p
def scores(p,gold,labels):
 distribution(p,labels);assert gold in labels
 return {'brier':sum((p[x]-float(x==gold))**2 for x in labels),'nll':-math.log(max(p[gold],1e-15))}
def predicted(p):return min(p,key=lambda x:(-p[x],x))
def percentile(xs,q):
 v=sorted(xs);i=(len(v)-1)*q;l=int(i);h=min(l+1,len(v)-1);return v[l]+(v[h]-v[l])*(i-l)
def interval(ds):
 assert ds and all(math.isfinite(x) for x in ds);rng=random.Random(20261022);n=len(ds)
 v=sorted(statistics.mean(ds[rng.randrange(n)] for _ in range(n)) for _ in range(2000))
 return {'mean_improvement':statistics.mean(ds),'ci95':[v[int(.025*1999)],v[int(.975*1999)]],'draws':2000,'seed':20261022}
def gate(m,dev):
 n=24 if dev else 48
 if set(m)!=set(ARMS) or any(x['n']!=n or x['strict_valid']!=n or x['errors'] or not all(math.isfinite(x[k]) for k in ['brier','nll']) for x in m.values()):return False
 p=m['ruvector_top2'];gain=2 if dev else 0
 return all(p['correct']>=v['correct']+gain and p['brier']<=v['brier']+1e-12 and p['nll']<=v['nll']+1e-12 for k,v in m.items() if k!='ruvector_top2') and all(p['brier']<m[k]['brier']-1e-12 or p['nll']<m[k]['nll']-1e-12 for k in ['same_nli_lexical_top2','same_nli_positional_first2'])
def audit(project,epoch,expected_plan_sha,prior,archived_numerical_only=False):
 s=project/'experiments/sota-2026-10-22';study=s/('epoch'+str(epoch));plan=obj(study/'plan.json');assert sha(study/'plan.json')==expected_plan_sha
 skipped_archived_asset_pins=[]
 assert not archived_numerical_only or (epoch==13 and prior==15)
 for pin in plan['pins']:
  p=project/pin['path']
  if archived_numerical_only and not p.is_file():skipped_archived_asset_pins.append(pin['path']);continue
  assert p.is_file() and not any(x.is_symlink() for x in [p,*p.parents]) and sha(p)==pin['sha256'],pin['path']
 summary=obj(study/'study-completion.json');all_scores={};typed_scores={};confusions={};phase_rows={};phase_ev={};per_record=[];counter={'NLI_pairs':0,'NLI_tokens':0,'BGE_texts':0,'BGE_batches':0,'native_searches':0};same_input_logits={};max_drift=0
 for phase,n,attempt_number in [('development',24,1),('confirmation',48,2)]:
  run=study/'runs'/phase
  if not (run/'attempt.json').exists():continue
  ev={k:obj(run/(k+'.json')) for k in ['completion','runtime','resources','attempt','report','cleanup','final-engine']};phase_ev[phase]=ev
  invocation=obj(run/'popen-attempt.json');completion=ev['completion'];attempt=ev['attempt'];runtime=ev['runtime'];clean=ev['cleanup'];resources=ev['resources']
  assert completion['exit_code']==0 and completion['error'] is None and completion['source_plan_unchanged']
  assert completion['popen_invocation_reserved'] and completion['native_process_started'] and completion['wall_seconds_including_model_load']<=600
  assert completion['prior_closed_attempts']==prior and completion['lifetime_native_attempt']==prior+attempt_number
  assert invocation['new_study_native_attempt']==attempt_number and invocation['source_plan_sha256']==expected_plan_sha
  assert invocation['at']<=attempt['at']<=runtime['at']
  assert not completion['owned_group_cleanup']['live_members_after'] and completion['owned_group_cleanup']['finished_within_deadline']
  assert clean['engine_close_called'] and not clean['cleanup_errors'] and clean['native_child_pids_absent']
  if not archived_numerical_only:assert not any(Path('/proc',str(pid)).exists() for pid in [attempt['pid'],*runtime['native_child_pids']])
  assert len(resources['allowed_CPU_ids'])<=2 and resources['configured_ORT_threads']==2
  assert runtime['receipt']['nli']['revision']==plan['expected_nli_revision'] and runtime['receipt']['nli']['model_sha256']==plan['expected_nli_sha256']
  for k,v in plan['expected_native_receipt'].items():assert runtime['receipt'][k]==v
  assert runtime['receipt']['nli']['batch_size']==1 and not runtime['receipt']['nli']['padding'] and not runtime['receipt']['nli']['truncation']
  expected=rows(project/plan['datasets'][phase]);actual=rows(run/'records.jsonl');wire=rows(run/'wire.jsonl');events=rows(run/'server-audit.jsonl');started=rows(run/'started-requests.jsonl')
  assert len(expected)==len(actual)==len(wire)==len(events)==len(started)==n
  assert sha(run/'records.jsonl')==ev['report']['records_sha256'] and sha(run/'wire.jsonl')==ev['report']['wire_sha256']
  byarm={name:[] for name in ARMS};typed={name:[] for name in ARMS if name!='native104_on_ruvector_evidence'};confusion={name:{} for name in typed}
  for e,r,w,se,st in zip(expected,actual,wire,events,started):
   assert e['id']==r['id']==w['id']==st['id'] and r['input']==e['input'] and r['evaluation']==e['evaluation']
   assert w['phase']==st['phase']==r['measured_phase']==phase
   assert json.loads(w['request'])==r['input'] and json.loads(w['response'])==r['response'] and w['status']==se['status']==200 and se['ok']
   for side in ['request','response']:assert hashlib.sha256(w[side].encode()).hexdigest()==w[side+'_sha256']==se[side+'_sha256']
   assert st['request']==w['request'] and st['request_sha256']==w['request_sha256']
   response=r['response'];d=response['diagnostics']['decision'];usage=response['usage'];assert usage['paid_calls']==0 and usage['native_requests']==usage['native_core_searches']==1 and usage['nli_singleton_pairs']==3
   gold=r['evaluation']['gold'];typed_gold=r['evaluation']['original_threeway_label'];assert gold==('Yes' if typed_gold=='Entailment' else 'No')
   proof={'id':r['id'],'phase':phase,'source_group':r['source_group'],'gold_binary':gold,'gold_typed':typed_gold,'arms':{}}
   for name,key in ARMS.items():
    answer_response=response if key is None else response['baseline104_response'] if key=='baseline' else response['ablation_responses'][name]
    answer=answer_response['answers']['decision'];p=distribution(answer['probabilities'],['Yes','No']);assert answer['choice']==predicted(p)
    row={'correct':predicted(p)==gold,**scores(p,gold,['Yes','No'])};byarm[name].append(row);proof['arms'][name]={'probabilities':p,**row}
    if key=='baseline':continue
    arm=d['arms'][key or name];dec=arm['decoding'];z=dec['logits'];assert len(z)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in z)
    indices=dec['raw_label_indices'];assert set(indices)=={'entailment','contradiction','neutral'} and set(indices.values())=={0,1,2}
    ez=[math.exp(v-max(z)) for v in z];q=[v/sum(ez) for v in ez];typed_p={'Entailment':q[indices['entailment']],'Contradiction':q[indices['contradiction']],'NotMentioned':q[indices['neutral']]}
    close(p['Yes'],typed_p['Entailment']);close(p['No'],typed_p['Contradiction']+typed_p['NotMentioned'])
    for label,value in typed_p.items():close(dec['raw_threeway_probabilities'][label],value)
    assert dec['model_revision']==plan['expected_nli_revision'] and dec['onnx_sha256']==plan['expected_nli_sha256'] and dec['temperature']==1 and dec['batch_size']==1 and not dec['truncated'] and not dec['padding_tokens']
    assert dec['raw_tokens']==dec['used_tokens']==dec['input_tokens']==dec['actual_model_pair_tokens']<=512
    assert len(dec['input_ids'])==len(dec['attention_mask'])==len(dec['token_type_ids'])==dec['input_tokens'] and all(v==1 for v in dec['attention_mask'])
    assert arm['hypothesis']==r['input']['questions']['decision']['criteria']['Yes']
    actual_input=json.dumps({'premise':arm['premise'],'hypothesis':arm['hypothesis']},ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();assert hashlib.sha256(actual_input).hexdigest()==dec['input_text_sha256']
    fingerprint=dec['input_text_sha256']
    if fingerprint in same_input_logits:max_drift=max(max_drift,max(abs(a-b) for a,b in zip(z,same_input_logits[fingerprint])))
    else:same_input_logits[fingerprint]=z
    tr={'correct':predicted(typed_p)==typed_gold,**scores(typed_p,typed_gold,list(typed_p))};typed[name].append(tr);label=typed_gold+'->'+predicted(typed_p);confusion[name][label]=confusion[name].get(label,0)+1
    proof['arms'][name].update(typed_probabilities=typed_p,typed_prediction=predicted(typed_p),typed_correct=tr['correct'])
    counter['NLI_pairs']+=1;counter['NLI_tokens']+=dec['input_tokens']
   embedding=d['retrieval']['embedding'];counter['BGE_texts']+=embedding['actual_embedded_texts'];counter['BGE_batches']+=embedding['chunks']['model_batches']+embedding['query']['model_batches'];counter['native_searches']+=1
   per_record.append(proof)
  all_scores[phase]=byarm;typed_scores[phase]=typed;confusions[phase]=confusion;phase_rows[phase]=actual
 assert list(phase_ev) in [['development'],['development','confirmation']]
 assert summary['native_processes_started']==summary['actual_native_attempts']==len(phase_ev) and summary['lifetime_native_attempts']==prior+len(phase_ev) and summary['allowed_further_attempts_in_closed_study']==0
 metrics={phase:{name:{'n':len(xs),'correct':sum(x['correct'] for x in xs),'brier':statistics.mean(x['brier'] for x in xs),'nll':statistics.mean(x['nll'] for x in xs),'strict_valid':len(xs),'errors':0} for name,xs in arms.items()} for phase,arms in all_scores.items()}
 for phase,m in metrics.items():
  published=obj(study/'runs'/phase/(phase+'-comparison.json'))['metrics']
  for name,v in m.items():
   for key,value in v.items():close(published[name][key],value)
 uncertainty={}
 for phase,rs in phase_rows.items():
  groups=sorted({r['source_group'] for r in rs});assert len(groups)==(8 if phase=='development' else 16) and all(sum(r['source_group']==g for r in rs)==3 for g in groups);uncertainty[phase]={}
  for name in ARMS:
   if name=='ruvector_top2':continue
   diffs={key:[] for key in ['accuracy','brier','nll']}
   for g in groups:
    ix=[i for i,r in enumerate(rs) if r['source_group']==g]
    diffs['accuracy'].append(statistics.mean(int(all_scores[phase]['ruvector_top2'][i]['correct'])-int(all_scores[phase][name][i]['correct']) for i in ix))
    for key in ['brier','nll']:diffs[key].append(statistics.mean(all_scores[phase][name][i][key]-all_scores[phase]['ruvector_top2'][i][key] for i in ix))
   uncertainty[phase][name]={key:interval(v) for key,v in diffs.items()}
 devgate=gate(metrics['development'],True);holdout=False
 if 'confirmation' in phase_ev:
  assert devgate
  holdout=gate(metrics['confirmation'],False) and all(x['accuracy']['ci95'][0]>0 and all(x[k]['ci95'][0]>=-1e-12 for k in ['brier','nll']) for x in uncertainty['confirmation'].values())
 else:
  assert not (study/'confirmation-selection-lock.json').exists() and not (study/'runs/confirmation/attempt.json').exists() and not (study/'runs/confirmation/popen-attempt.json').exists()
 assert max_drift<1e-5
 result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'status':summary['status'],'scope':'Independent saved-output numerical/wire/process/resource replay only; exact source-context/native-vector execution requires separate bound verifier. No new inference.','checks_passed':True,'epoch':epoch,'plan_SHA256':expected_plan_sha,'metrics':metrics,'multiclass_metrics':{phase:{name:{'n':len(xs),'correct':sum(x['correct'] for x in xs),'brier':statistics.mean(x['brier'] for x in xs),'nll':statistics.mean(x['nll'] for x in xs)} for name,xs in arms.items()} for phase,arms in typed_scores.items()},'typed_confusions':confusions,'DEV_gate_passed':devgate,'internal_confirmation_gate_passed':holdout,'confirmation_consumed':'confirmation' in phase_ev,'paired_doc_bootstrap':uncertainty,'nominal_intervals_not_familywise':True,'counts':counter,'maximum_same_input_logit_drift':max_drift,'latency_by_phase_seconds':{phase:{'p50':statistics.median(r['elapsed_s'] for r in rs),'p95':percentile([r['elapsed_s'] for r in rs],.95),'max':max(r['elapsed_s'] for r in rs),'scope':'Whole all-arm request; not primary-only deployment'} for phase,rs in phase_rows.items()},'resources':{phase:ev['resources'] for phase,ev in phase_ev.items()},'completions':{phase:ev['completion'] for phase,ev in phase_ev.items()},'rows':per_record,'official_score':None,'official_rank':None,'SOTA_established':False,'auditor_model_native_session_fit_paid_GPU_calls':0,'archived_numerical_selfcheck_only':archived_numerical_only,'archived_missing_asset_pins_not_verified':skipped_archived_asset_pins,'current_native_admission_proof':False}
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--expected-plan-sha',required=True);ap.add_argument('--epoch',type=int,default=15);ap.add_argument('--prior-closed',type=int,default=16);ap.add_argument('--archived-numerical-only',action='store_true');a=ap.parse_args();assert not a.out.exists();result=audit(a.project,a.epoch,a.expected_plan_sha,a.prior_closed,a.archived_numerical_only);raw=(json.dumps(result,indent=2)+'\n').encode()
 with a.out.open('xb') as f:f.write(raw)
 print(json.dumps({'checks_passed':True,'sha256':hashlib.sha256(raw).hexdigest(),'metrics':result['metrics'],'DEV_gate_passed':result['DEV_gate_passed'],'confirmation_consumed':result['confirmation_consumed']}))
if __name__=='__main__':main()
