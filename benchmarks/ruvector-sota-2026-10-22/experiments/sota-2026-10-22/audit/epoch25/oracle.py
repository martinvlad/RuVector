"""Frozen independent authored engineering oracle. Reads saved JSON; imports no candidate or model."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,math,re
LABELS=('entailment','contradiction','not_mentioned')
ARMS=('actual_native','lexical','positional')
CODES=('A','B','C')
INPUT_SHA='fd9654515677e013f01230c1ceaabc66f9d1375414abe58d3430a544276bb6cf'
GOLD_SHA='21cdac12b5e7bd91617f29836b556a934de1521e101462077269264f74a29c51'
CONTRACT_SHA='05635bce54142e8d0af99be01e8de24011625b4d41624fac5dc97ff32f50fcf9'
PROMPT_SHA='325c62adbfd4489de06297f84352183569b69a38690ee7953d475f24a6f90b6e'
BGE_PREFIX='Represent this sentence for searching relevant passages: '
EPS=1e-12
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def htext(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def ref(p):
 p=Path(p)
 return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def exactspan(t,q):
 st=t.index(q);en=st+len(q)
 return {'text':q,'start':st,'end':en,'source_byte_start':len(t[:st].encode()),'source_byte_end':len(t[:en].encode())}
def manualunit(source_id,text,literals,unknowns=()):
 rows=[]
 for item in literals:
  kind,q,*year=item
  r={'kind':kind,**exactspan(text,q)}
  if year:r['lexical_year_candidate']=year[0]
  rows.append(r)
 rows.sort(key=lambda x:(x['start'],x['end'],x['kind']))
 us=[{'reason':reason,**exactspan(text,q)} for reason,q in unknowns]
 us.sort(key=lambda x:(x['start'],x['end'],x['reason']))
 return {'source_id':source_id,'text':text,'source_sha256':htext(text),'whole_span':exactspan(text,text),'numeric_literals':rows,'structural_unknowns':us}
def owned_guard_expectations():
 return [
 manualunit('utf8_literals','In fiscal year 2024, café revenue was €12.5 million, up 8%.',
  [('period','fiscal year 2024'),('number','2024',True),('currency','€'),('number','12.5'),('scale','million'),('number','8'),('percent','%')]),
 manualunit('explicit_unit','For 2024 revenue was 42 million; currency unspecified.',
  [('number','2024',True),('number','42'),('scale','million')],[('explicit_unit_ambiguity','currency unspecified')]),
 manualunit('explicit_period','Revenue was USD 42 million; reporting period is unspecified.',
  [('currency','USD'),('number','42'),('scale','million')],[('explicit_period_ambiguity','reporting period is unspecified')]),
 manualunit('no_global_absence','The office uses blue folders.',[])
 ]
def main():
 ap=argparse.ArgumentParser()
 for key in ('inputs','gold','raw','execution','plan','native','bundle','prompt','out'):
  ap.add_argument('--'+key,type=Path,required=True)
 a=ap.parse_args()
 failures=[];checks=0
 def check(ok,label):
  nonlocal checks
  checks+=1
  if not ok:failures.append(label)
 check(sha(a.inputs)==INPUT_SHA,'exact independent input bytes')
 check(sha(a.gold)==GOLD_SHA,'exact sealed manual gold bytes')
 check(sha(a.prompt)==PROMPT_SHA,'exact fixed prompt bytes')
 inputs,gold,raw,execution,plan,prompt=map(read,(a.inputs,a.gold,a.raw,a.execution,a.plan,a.prompt))
 check(inputs['contract_sha256']==CONTRACT_SHA,'source contract binding')
 holds={'worker.py':'bb35e802349f44dced57b99047ca8d0cc1137063dc490586fb092bd38d63a820','native.cjs':'25acb96c37c2f2715f8dc0601a647672c004762eee98ee4b729c33d33b2afbfe','evidence.py':'ae3ed96266a9635fcf2bba9a5f7e01e6c7c8bb9c6abb911770d9bb3db66e72df','evidence-contract.json':CONTRACT_SHA,'reader.py':'a286dc987bc3fc0109f25534769f774835b3f49a9474af9206e622089063c783','prompt.json':PROMPT_SHA,'reader-contract.json':'7a27b98c5f99ed71a31552ab91642f32e83f0c4f03a9342653137577ee68ba79','MODEL_ASSETS.json':'1378b866db260787940c777badf949d8cc0da26da4f7cb54118877e66873d3bd'}
 pins={r['path']:r['sha256'] for r in plan.get('pins',[])}
 for name,expected in holds.items():
  check(pins.get('experiments/sota-2026-10-22/candidate/epoch25/'+name)==expected,'exact candidate HOLD preserved:'+name)
 check(raw.get('fixtures_sha256')==INPUT_SHA,'actual worker exact fixtures')
 check(raw.get('plan_sha256')==sha(a.plan),'actual worker exact plan')
 check(execution.get('raw_sha256')==sha(a.raw) and execution.get('raw_bytes')==a.raw.stat().st_size,'outer exact raw seal')
 check(raw.get('status')=='COMPLETED_ENGINEERING_AWAITING_INDEPENDENT_ORACLE' and raw.get('errors')==[],'worker completion and no errors')
 check(raw.get('roles_used')==dict.fromkeys(('train','dev','calibration','confirmation'),[]),'empty benchmark roles')
 check(raw.get('benchmark_results') is None and raw.get('accuracy') is None and raw.get('proper_scores') is None,'worker did not self-score')
 check(len(inputs['cases'])==6 and len(gold['cases'])==6,'six fixed manual cases')
 gm={x['id']:x for x in gold['cases']}
 check({l:sum(x['label']==l for x in gold['cases']) for l in LABELS}==dict.fromkeys(LABELS,2),'exact manual 2E2C2N')
 actual=raw.get('cases',[])
 check([r.get('id') for r in actual]==[c['id'] for c in inputs['cases']],'exact six output IDs/order')
 rm={r['id']:r for r in actual if isinstance(r,dict) and isinstance(r.get('id'),str)}
 native=read(a.native) if a.native.exists() else {}
 bundle=read(a.bundle) if a.bundle.exists() else {}
 check(native.get('native') is True and native.get('package_version')=='0.1.33' and native.get('platform_package_version')=='0.1.31' and native.get('binary_version')=='2.3.0','actual native implementation versions')
 check(a.bundle.exists() and native.get('bundle_sha256')==(sha(a.bundle) if a.bundle.exists() else None),'native exact saved BGE bundle')
 check(native.get('native_queries_completed')==6 and len(native.get('cases',[]))==6,'six actual native searches')
 nr={r.get('case_id'):r for r in native.get('cases',[])}
 br={r.get('id'):r for r in bundle.get('cases',[])}
 scored={arm:[] for arm in ARMS}
 seen_contexts=0
 for case in inputs['cases']:
  cid=case['id'];row=rm.get(cid)
  check(row is not None,'case present:'+cid)
  if row is None:continue
  check(row.get('hypothesis')==case['hypothesis'] and row.get('query')==case['query']==case['hypothesis'],'exact query and hypothesis:'+cid)
  expected_units=[dict(gold['manual_source_units'][s['source_id']],text=s['text']) for s in case['sources']]
  check(row.get('source_units')==expected_units,'manual full source literal/UTF8 provenance:'+cid)
  emb=row.get('embedding',{})
  check(emb.get('exact_query_text')==BGE_PREFIX+case['query'] and emb.get('source_ids')==[s['source_id'] for s in case['sources']],'actual BGE source/query provenance:'+cid)
  vectors=br.get(cid,{})
  allvectors=vectors.get('vectors',[])+[vectors.get('query_vector',[])]
  check(len(vectors.get('vectors',[]))==len(case['sources']) and all(len(v)==384 and all(finite(x) for x in v) and abs(math.sqrt(math.fsum(x*x for x in v))-1)<=1e-5 for v in allvectors),'finite normalized BGE384 saved vectors:'+cid)
  check(row.get('native')==nr.get(cid) and row.get('native') is not None,'native trace unchanged:'+cid)
  query_words=set(re.findall(r'\w+',case['query'].casefold()))
  texts=[s['text'] for s in case['sources']]
  scores=[]
  for text in texts:
   ws=set(re.findall(r'\w+',text.casefold()))
   scores.append(len(query_words&ws)/max(1,len(query_words|ws)))
  lexical=sorted(range(len(texts)),key=lambda i:(-scores[i],i))
  check(row.get('lexical_jaccard_scores')==scores,'independent lexical score replay:'+cid)
  observed_native=nr.get(cid,{}).get('ids',[])
  check(len(observed_native)==1 and type(observed_native[0]) is int and 0<=observed_native[0]<len(texts),'native observed top1 valid:'+cid)
  expected_rankings={'actual_native':observed_native,'lexical':lexical,'positional':list(range(len(texts)))}
  check(set(row.get('arms',{}))==set(ARMS),'exact three arm outputs:'+cid)
  for arm in ARMS:
   item=row.get('arms',{}).get(arm)
   check(item is not None,'arm present:'+cid+':'+arm)
   if item is None:continue
   try:
    ranking=expected_rankings[arm]
    check(item['observed_ranking']==ranking,'observed unmodified ranking:'+cid+':'+arm)
    idx=ranking[0];source=case['sources'][idx];unit=expected_units[idx];pack=item['pack']
    check(pack['top_k']==1 and pack['selected_indices']==[idx] and pack['selected_source_ids']==[source['source_id']],'same top1 pack:'+cid+':'+arm)
    check(pack['context']==source['text'] and pack['source_units']==[unit] and bool(source['text'].strip()),'entire nonempty exact source context:'+cid+':'+arm)
    guard=pack['guard']
    check(guard['decision'] is None and guard['status']=='SOURCE_PROVENANCE_VALID' and guard['structural_unknown'] is False and guard['unknowns']==[],'source-only guard no fabricated label:'+cid+':'+arm)
    result=item['reader'];p=[result['probabilities'][l] for l in LABELS]
    logits=[result['selected_logits'][code] for code in CODES]
    check(all(finite(x) for x in logits) and all(finite(x) and 0<=x<=1 for x in p) and abs(math.fsum(p)-1)<=1e-8,'finite normalized conditional scores:'+cid+':'+arm)
    peak=max(logits);den=math.fsum(math.exp(x-peak) for x in logits)
    expectedp=[math.exp(x-peak)/den for x in logits]
    expectedlog=[(x-peak)-math.log(den) for x in logits]
    check(all(abs(x-y)<=1e-12 for x,y in zip(p,expectedp)),'stable independent A/B/C softmax replay:'+cid+':'+arm)
    check(all(abs(result['log_probabilities'][l]-expectedlog[j])<=1e-12 for j,l in enumerate(LABELS)),'independent log probability replay:'+cid+':'+arm)
    check(result['conditional_valid_code_probabilities']==dict(zip(CODES,p)),'fixed code probability mapping:'+cid+':'+arm)
    best=max(range(3),key=lambda j:p[j])
    check(result['prediction']==LABELS[best] and result['prediction_code']==CODES[best] and item['decision']==LABELS[best],'fixed argmax and unchanged decision:'+cid+':'+arm)
    check(type(result['token_count']) is int and 0<result['token_count']<=512 and result['token_count']==item['validated_total_prompt_tokens'],'actual complete prompt token cap:'+cid+':'+arm)
    check(result['evidence_sha256']==htext(source['text']) and result['hypothesis_sha256']==htext(case['hypothesis']),'reader source/hypothesis hashes:'+cid+':'+arm)
    content=json.dumps({'evidence':source['text'],'hypothesis':case['hypothesis']},ensure_ascii=False,separators=(',',':'))
    rendered='<|im_start|>system\n'+prompt['system']+'<|im_end|>\n<|im_start|>user\n'+content+'<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
    check(result['prompt_sha256']==htext(rendered),'independent fixed Qwen no-thinking prompt reconstruction:'+cid+':'+arm)
    check(item['seed_origin']==('ACTUAL_NATIVE_OBSERVATION' if arm=='actual_native' else 'MATCHED_CONTROL'),'fixed source arm origin:'+cid+':'+arm)
    y=LABELS.index(gm[cid]['label'])
    scored[arm].append({'id':cid,'gold':LABELS[y],'prediction':LABELS[best],'correct':best==y,'Brier':math.fsum((v-(j==y))**2 for j,v in enumerate(p)),'NLL':-math.log(max(p[y],EPS)),'probabilities':dict(zip(LABELS,p)),'selected_source_id':source['source_id']})
    seen_contexts+=1
   except (KeyError,IndexError,TypeError,ValueError,OverflowError) as error:
    check(False,'incomplete/invalid arm:'+cid+':'+arm+':'+type(error).__name__+':'+str(error))
 owned=raw.get('source_only_guards',[])
 expected_owned=owned_guard_expectations()
 check(len(owned)==4,'four existing implementation-owned source guards')
 for i,unit in enumerate(expected_owned):
  if i>=len(owned):continue
  item=owned[i];unknown=bool(unit['structural_unknowns'])
  check(item.get('source')=={'source_id':unit['source_id'],'text':unit['text']} and item.get('unit')==unit,'manual owned guard literal and UTF8 spans:'+unit['source_id'])
  guard=item.get('guard',{})
  check(guard.get('structural_unknown') is unknown and guard.get('status')==('STRUCTURAL_UNKNOWN' if unknown else 'SOURCE_PROVENANCE_VALID') and guard.get('decision') is None and guard.get('unknowns')==unit['structural_unknowns'],'manual owned source guard unknown semantics:'+unit['source_id'])
 metrics={}
 for arm,rows in scored.items():
  n=len(rows)
  metrics[arm]={'n':n,'correct':sum(r['correct'] for r in rows),'accuracy':sum(r['correct'] for r in rows)/n if n else None,
    'Brier':math.fsum(r['Brier'] for r in rows)/n if n else None,'NLL':math.fsum(r['NLL'] for r in rows)/n if n else None,
    'by_class':{l:{'n':sum(r['gold']==l for r in rows),'correct':sum(r['gold']==l and r['correct'] for r in rows)} for l in LABELS}}
  check(n==6,'six scored cases:'+arm)
 primary=metrics['actual_native']
 check(primary['n']==6 and primary['correct']==6,'native six of six typed correctness')
 check(all(primary['by_class'][l]=={'n':2,'correct':2} for l in LABELS),'native every class two of two')
 for control in ARMS[1:]:
  other=metrics[control]
  check(primary['correct']>=other['correct'],'native accuracy nondecrease:'+control)
  for metric in ('Brier','NLL'):
   check(primary[metric] is not None and other[metric] is not None and primary[metric]<=other[metric]+1e-12,'native proper-score nonincrease:'+control+':'+metric)
 check(seen_contexts==18,'eighteen complete nonempty matched contexts')
 counts=raw.get('counters',{})
 for key,want in {'NLI_model_initializations':1,'NLI_model_initializations_completed':1,'NLI_forward_pairs_attempted':18,'NLI_forward_pairs_completed':18,'NLI_forwards':18,'engineering_pairs_completed':18,'engineering_cases_completed':6,'native_queries_completed':6}.items():
  check(type(counts.get(key)) is int and counts[key]==want,'exact execution count:'+key)
 for key in ('benchmark_corpora','benchmark_questions','benchmark_HTTP_requests','TRAIN_calibration_fits','CONF_worker_attempts','CONF_annotation_choices','CONF_NLI_pairs','paid_API_calls','GPU_calls','fits','paid_calls','Python_network_operations_attempted','Node_network_operations_attempted','confirmation_calls','generation_calls','generated_tokens','training_steps','optimizer_steps','external_API_calls','benchmark_corpus_reads','benchmark_label_reads','train_calls','dev_calls','calibration_calls'):
  check(type(counts.get(key)) is int and counts[key]==0,'forbidden zero:'+key)
 receipt=raw.get('reader',{})
 check(receipt.get('code_token_ids')==dict(zip(CODES,(32,33,34))) and receipt.get('code_to_label')==dict(zip(CODES,LABELS)),'actual fixed label token IDs')
 check(receipt.get('prompt_file_sha256')==PROMPT_SHA and receipt.get('enable_thinking') is False and receipt.get('truncation') is False and receipt.get('device')=='cpu','actual reader prompt and execution policy')
 check(execution.get('status')=='WORKER_COMPLETED' and execution.get('exit_code')==0 and execution.get('worker_attempts_reserved')==1 and execution.get('verified_worker_starts')==1 and execution.get('uncertain_start') is False,'one owned completed worker')
 check(execution.get('owned_live_processes_closed') is True and execution.get('owned_live_group_members')==[] and execution.get('cleanup_errors')==[] and execution.get('launcher_error') is None and execution.get('stdout_stderr_capture_completed') is True,'verified cleanup and complete output capture')
 check(finite(execution.get('wall_seconds_including_init_cleanup')) and execution['wall_seconds_including_init_cleanup']<=600 and execution.get('CPU_affinity')==[0,1],'outer complete CPU2/600 budget')
 check(raw.get('resources',{}).get('CPU_affinity')==[0,1] and finite(raw.get('wall_seconds_including_initialization_cleanup')) and raw['wall_seconds_including_initialization_cleanup']<=600,'inner CPU2/600 budget')
 check(execution.get('allowed_further_epoch25_workers')==0 and execution.get('confirmation_calls')==execution.get('paid_calls')==execution.get('GPU_calls')==0,'closed budget and outer forbidden actions')
 report={'schema_version':1,'epoch':25,'at':datetime.now(timezone.utc).isoformat(),'status':'ENGINEERING_QUALIFIED_BENCHMARK_NOT_EVALUATED' if not failures else 'REJECTED_AUTHORED_ENGINEERING_QUALIFICATION',
  'engineering_qualified':not failures,'benchmark_accepted':False,'champion_promoted':False,'checks':checks,'failures':failures,'metrics':metrics,'case_scores':scored,'raw_worker_errors':raw.get('errors'),
  'actual_execution':counts,'outer_execution':execution,'evidence':{k:ref(getattr(a,k)) for k in ('inputs','gold','raw','execution','plan','prompt')},
  'benchmark_roles':dict.fromkeys(('train','dev','calibration','confirmation'),[]),'global_insufficiency':'unknown',
  'scope':'Six newly authored CC0 engineering cases; conditional A/B/C token probabilities are uncalibrated. No semantic benchmark, generalization, genuine confirmation, ANN superiority, promotion or official rank claim.',
  'metrics_definition':{'Brier':'Mean sum-of-three squared class errors','NLL':'Mean -log(max(p_gold,1e-12))','numeric_tolerances':{'probability_mass':1e-8,'softmax_replay':1e-12,'proper_score_nonincrease':1e-12}},
  'source_guard_scope':'Four worker-owned exposed implementation guards checked from saved raw only; six extra private independent source guards unexecuted/excluded.',
  'activity':'Independent JSON/hash/string/arithmetic replay only; no candidate imports, tokenizer/model/native execution, generation, training, calibration, gold changes or label selection.'}
 with a.out.open('x') as f:
  f.write(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'status':report['status'],'checks':checks,'failures':failures,'metrics':metrics,'output':ref(a.out)},indent=2))
if __name__=='__main__':main()
