"""Independent saved-output epoch6 replay; no ORT/native/model calls.

Acceptance, data/model/source pins and gates were frozen before measurement.
This numerical replay is adapted before launch from the preserved epoch4 auditor; only saved evidence is evaluated.
"""
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
import argparse, hashlib, importlib.util, json, math, re, statistics, sys
import numpy as np
from tokenizers import Tokenizer

HERE=Path(__file__).resolve().parent
OUTER=HERE.parents[1]
sys.path.insert(0,str(OUTER/'audit'))
from verify_epoch_v2 import proper_scores,paired_bootstrap_interval
ARMS={'ruvector_top2':None,'same_nli_lexical_top2':'lexical_top2','same_nli_positional_first2':'positional_first2','native104_on_ruvector_evidence':'baseline'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def obj(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x]
def raw(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def close(a,b):assert math.isclose(float(a),float(b),rel_tol=0,abs_tol=1e-10),(a,b)
def module(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def lexical(chunks,hyp):
 q=set(re.findall(r'\w+',hyp.casefold()));v=[]
 for i,t in enumerate(chunks):
  w=set(re.findall(r'\w+',t.casefold()));v.append((-len(q&w)/max(1,len(q|w)),i))
 return [i for _,i in sorted(v)[:40]]
def merged_spans(spans,ids):
 result=[]
 for a,b in sorted(spans[i] for i in ids):
  if result and a<=result[-1][1]:result[-1]=[result[-1][0],max(b,result[-1][1])]
  else:result.append([a,b])
 return result
def gate(metrics):
 p=metrics['ruvector_top2']
 return all(p['correct']>=b['correct'] and p['brier']<=b['brier']+1e-12 and p['nll']<=b['nll']+1e-12 for n,b in metrics.items() if n!='ruvector_top2') and all(p['brier']<metrics[n]['brier']-1e-12 or p['nll']<metrics[n]['nll']-1e-12 for n in ['same_nli_lexical_top2','same_nli_positional_first2'])

def independent_pack(state,units,ranking,hyp,nli):
 chosen=[];trace=[]
 def admit(i,role,anchor):
  if i in chosen:return True
  spans=merged_spans([[u['start'],u['end']] for u in units],chosen+[i]);text='\n\n'.join(state[a:b] for a,b in spans);count=len(nli.encode(text,hyp).ids);accept=count<=512
  trace.append({'unit_id':i,'role':role,'anchor':anchor,'candidate_pair_tokens':count,'accepted':accept})
  if accept:chosen.append(i)
  return accept
 for i in ranking:
  if i in chosen:continue
  if admit(i,'ranked-anchor',i):
   for j in (i-1,i+1):
    if 0<=j<len(units) and units[j]['paragraph_id']==units[i]['paragraph_id']:admit(j,'same-paragraph-neighbor',i)
 assert chosen
 return chosen,trace

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--expected-plan-sha',required=True);args=ap.parse_args();assert not args.out.exists()
 project=args.project;s=project/'experiments/sota-2026-10-22';run=s/'epoch6/runs/composite';plan=obj(s/'epoch6/plan.json');assert sha(s/'epoch6/plan.json')==args.expected_plan_sha
 for x in plan['pins']:assert sha(project/x['path'])==x['sha256'],x['path']
 report=obj(run/'report.json');completion=obj(run/'completion.json');runtime=obj(run/'runtime.json');cleanup=obj(run/'cleanup.json');engine=obj(run/'final-engine.json');resources=obj(run/'resources.json');attempt=obj(run/'attempt.json')
 assert completion['exit_code']==0 and completion['error'] is None and completion['source_plan_unchanged'];assert not completion['owned_group_cleanup']['live_members_after'];assert completion['prior_study_native_attempts_used']==7 and completion['original_study_native_attempts_used']==6 and completion['epoch5_study_native_attempts_used']==1 and completion['prior_study_attempts_remaining']==0 and completion['new_study_native_attempts_used']==1 and completion['new_study_attempts_remaining']==0 and completion['lifetime_native_attempts_used']==8
 assert cleanup['engine_close_called'] and not cleanup['cleanup_errors'] and cleanup['native_child_pids_absent'];assert not any(Path('/proc',str(p)).exists() for p in [attempt['pid'],*runtime['native_child_pids']])
 assert resources['allowed_CPU_ids']==[0,1] and runtime['receipt']['nli']['batch_size']==1 and not runtime['receipt']['nli']['padding'] and not runtime['receipt']['nli']['truncation']
 for k,v in plan['expected_native_receipt'].items():assert runtime['receipt'][k]==v
 assert runtime['receipt']['nli']['revision']==plan['expected_nli_revision'] and runtime['receipt']['nli']['model_sha256']==plan['expected_nli_sha256']
 assert attempt['deadline_unix']==runtime['deadline_unix'];assert completion['wall_seconds_including_model_load']<=plan['limits']['seconds_per_batch']+10
 actual,wire,server,started=[rows(run/f) for f in ['records.jsonl','wire.jsonl','server-audit.jsonl','started-requests.jsonl']]
 assert len(actual)==len(wire)==len(server)==len(started);assert sha(run/'records.jsonl')==report['records_sha256'] and sha(run/'wire.jsonl')==report['wire_sha256']
 expected={phase:rows(project/path) for phase,path in plan['datasets'].items()};byphase={phase:[x for x in actual if x['measured_phase']==phase] for phase in expected}
 assert len(byphase['development'])==report['development_completed']==24;assert len(byphase['confirmation'])==report['confirmation_completed'] in [0,96]
 ordered=expected['development']+(expected['confirmation'] if byphase['confirmation'] else []);assert [x['id'] for x in actual]==[x['id'] for x in ordered]
 bge=Tokenizer.from_file(str(project/'models/bge-small-en-v1.5/tokenizer.json'));nli=Tokenizer.from_file(str(s/'candidate/epoch4/assets/nli-base/tokenizer.json'))
 for t in [bge,nli]:t.no_padding();t.no_truncation()
 config=obj(s/'candidate/epoch4/assets/nli-base/config.json');assert config['id2label']=={'0':'contradiction','1':'entailment','2':'neutral'}
 context=module(s/'candidate/epoch6/context.py','epoch6_source_partition');scorer=module(s/'benchmark/sources/jevbench_scoring.py','epoch6_independent_scorer');docs={split:{d['id']:d for d in obj(s/('legal-transfer/epoch3/sources/original-'+split+'.json'))['documents']} for split in ['train','dev']}
 scores={phase:{name:[] for name in ARMS} for phase in expected};proofs=[];sameinputs={};repeatdrift=0.;text_count=bge_batches=nli_tokens=0
 for exp,rec,pair,event,begin in zip(ordered,actual,wire,server,started):
  assert rec['id']==exp['id']==pair['id']==begin['id'];phase=rec['measured_phase'];assert phase==pair['phase']==begin['phase'];assert rec['evaluation']==exp['evaluation'] and rec['input']==exp['input'];assert hashlib.sha256(canonical(rec['input'])).hexdigest()==exp['input_sha256']
  assert set(json.loads(pair['request']))=={'state','questions'} and json.loads(pair['request'])==rec['input'];assert pair['status']==event['status']==200 and event['ok']
  for side in ['request','response']:assert hashlib.sha256(pair[side].encode()).hexdigest()==pair[side+'_sha256']==event[side+'_sha256']
  assert begin['request']==pair['request'] and begin['request_sha256']==pair['request_sha256'];response=rec['response'];assert json.loads(pair['response'])==response;usage=response['usage'];assert usage['native_requests']==usage['native_core_searches']==event['usage']['native_requests']==1 and usage['nli_singleton_pairs']==3 and usage['paid_calls']==0
  assert 0<=rec['elapsed_s']<=plan['limits']['seconds_per_decision'];assert datetime.fromisoformat(event['at']).timestamp()<=attempt['deadline_unix']
  state=rec['input']['state'];hyp=rec['input']['questions']['decision']['criteria']['Yes'];d=response['diagnostics']['decision'];units=context.partition(state,nli,bge,target=128,nli_cap=160,bge_cap=256,max_units=192);spans=[[u['start'],u['end']] for u in units]
  assert d['source_state']==state and d['source_state_sha256']==hashlib.sha256(state.encode()).hexdigest();assert d['source_units']==units and d['full_source_partition'] and not d['source_partition_has_overlap'];assert spans[0][0]==0 and spans[-1][1]==len(state) and all(a[1]==b[0] for a,b in zip(spans,spans[1:]));assert ''.join(state[a:b] for a,b in spans)==state
  chunks=[state[a:b] for a,b in spans];assert len(chunks)==d['total_chunks']<=192 and d['chunk_spans']==spans and d['ranking_candidate_depth']==min(40,len(chunks))
  retrieval=d['retrieval'];e=retrieval['bundle_evidence'];bundlepath=run/'bundles'/e['relativefilename'];assert not bundlepath.is_symlink() and bundlepath.name==e['sha256']+'.json' and sha(bundlepath)==e['sha256']==retrieval['native']['bundle_sha256'] and bundlepath.stat().st_size==e['bytes']
  bundle=obj(bundlepath);v=np.asarray(bundle['vectors'],dtype=np.float64);q=np.asarray(bundle['query_vectors'],dtype=np.float64);assert v.shape==(len(chunks),384) and q.shape==(1,384) and np.isfinite(v).all() and np.isfinite(q).all();assert np.max(np.abs(np.linalg.norm(v,axis=1)-1))<1e-5 and abs(np.linalg.norm(q)-1)<1e-5
  native=retrieval['native'];assert native['native'] and native['package_version']=='0.1.33' and native['native_binary_sha256']==runtime['receipt']['native_core_binary_sha256'] and native['vectors']==len(chunks);ids=native['queries'][0]['ids'];assert len(ids)==len(set(ids))==min(40,len(chunks)) and all(type(i) is int and 0<=i<len(chunks) for i in ids);chosen=d['arms']['ruvector_top2']['coverage']['selected_chunk_ids_rank_order']
  cosine=(v@q[0])/(np.linalg.norm(v,axis=1)*np.linalg.norm(q[0]));exact=sorted(range(len(chunks)),key=lambda i:(-cosine[i],i))[:min(40,len(chunks))];assert retrieval['ranking_scope']['actual_returned_ids']==ids and retrieval['ranking_scope']['requested']==min(40,len(chunks))
  embedding=retrieval['embedding'];assert embedding['actual_embedded_texts']==1+(0 if embedding['chunks']['cache_hit'] else len(chunks));assert embedding['cached_chunk_vectors']==(len(chunks) if embedding['chunks']['cache_hit'] else 0)
  texts=([] if embedding['chunks']['cache_hit'] else chunks)+['Represent this sentence for searching relevant passages: '+hyp];examples=embedding['chunks']['examples']+embedding['query']['examples'];assert len(texts)==len(examples)
  for txt,tok in zip(texts,examples):
   count=len(bge.encode(txt).ids);assert tok=={'raw_tokens':count,'used_tokens':count,'truncated':False} and count<=256
  text_count+=len(texts);bge_batches+=embedding['chunks']['model_batches']+embedding['query']['model_batches']
  rankings={'ruvector_top2':ids,'lexical_top2':lexical(chunks,hyp),'positional_first2':list(range(min(40,len(chunks))))};doc=docs[exp['provenance']['source_split']][exp['provenance']['document_id']];assert doc['text']==state;ann=doc['annotation_sets'][0]['annotations'][exp['provenance']['hypothesis_id']];goldspans=[doc['spans'][j] for j in ann['spans']];row={'id':rec['id'],'phase':phase,'group':rec['source_group'],'native_ranking_ids':ids,'primary_selected_unit_ids':chosen,'exact_cosine_ranking_ids':exact,'exact_top2_set_agreement':set(ids[:2])==set(exact[:2]),'exact_candidate_set_agreement':set(ids)==set(exact),'gold':rec['evaluation']['gold'],'arms':{}}
  for name,alias in ARMS.items():
   answer_response=response if alias is None else response['baseline104_response'] if alias=='baseline' else response['ablation_responses'][name];answer=answer_response['answers']['decision'];p=answer['probabilities'];canonical_score=scorer.score_task(p,SimpleNamespace(labels=['Yes','No'],expected=rec['evaluation']['gold'],question={'type':'choice'}));assert canonical_score['valid'] and canonical_score['strict_valid'] and answer['choice']==canonical_score['predicted'];scores[phase][name].append({'correct':bool(canonical_score['correct']),**proper_scores(canonical_score['probs'],rec['evaluation']['gold'],['Yes','No'])})
   if alias=='baseline':continue
   key=alias or name;ad=d['arms'][key];ranking=rankings[key];assert ad['ranking_ids']==ranking;sel,expected_trace=independent_pack(state,units,ranking,hyp,nli);assert ad['coverage']['packing_attempts']==expected_trace and ad['chunk_ids']==sel and ad['chunk_spans']==[spans[i] for i in sel];merged=merged_spans(spans,sel);premise='\n\n'.join(state[a:b] for a,b in merged);assert ad['premise']==premise and ad['hypothesis']==hyp
   coverage=ad['coverage'];assert coverage['ranking_ids_considered']==ranking and coverage['ranking_depth']==len(ranking) and coverage['ranked_anchor_candidate_cap']==min(40,len(units)) and coverage['joint_pair_token_cap']==512;assert coverage['additional_neighbor_unit_ids_inspected']==sorted({step['unit_id'] for step in expected_trace if step['role']=='same-paragraph-neighbor' and step['unit_id'] not in ranking});assert coverage['selected_source_spans']==merged and coverage['omitted_chunk_ids']==[i for i in range(len(spans)) if i not in sel] and not coverage['selected_evidence_truncated'] and not coverage['claim_truncated'];assert coverage['premise_sha256']==hashlib.sha256(premise.encode()).hexdigest();close(coverage['document_character_coverage'],sum(b-a for a,b in merged)/len(state))
   numbers=[{'span':[m.start(),m.end()],'text':m.group(),'retained':any(a<=m.start() and m.end()<=b for a,b in merged)} for m in re.finditer(r'(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:\s*%|\b)',state)];assert coverage['numeric_mentions']==numbers
   enc=nli.encode(premise,hyp);dec=ad['decoding'];assert dec['input_ids']==enc.ids and dec['attention_mask']==enc.attention_mask and dec['token_type_ids']==enc.type_ids and all(i==1 for i in enc.attention_mask);assert dec['raw_tokens']==dec['used_tokens']==dec['input_tokens']==coverage['joint_pair_tokens']==len(enc.ids)<=512 and dec['batch_size']==1 and dec['padding_tokens']==0 and not dec['truncated'];assert dec['input_text_sha256']==hashlib.sha256(raw({'premise':premise,'hypothesis':hyp})).hexdigest()
   logits=np.asarray(dec['logits'],dtype=np.float64);assert logits.shape==(3,) and np.isfinite(logits).all();prob=np.exp(logits-logits.max());prob/=prob.sum();close(p['Yes'],prob[1]);close(p['No'],prob[0]+prob[2]);assert dec['pool']=='One joint evidence premise; no per-chunk maximum'
   for j,label in config['id2label'].items():close(dec['nli_probabilities'][label],prob[int(j)])
   h=dec['input_text_sha256']
   if h in sameinputs:repeatdrift=max(repeatdrift,float(np.max(np.abs(logits-sameinputs[h]))))
   else:sameinputs[h]=logits
   nli_tokens+=len(enc.ids);overlap=[any(max(0,min(g[1],b)-max(g[0],a)) for a,b in merged) for g in goldspans];row['arms'][name]={'selected':sel,'gold_span_count':len(goldspans),'any_gold_overlap':any(overlap),'all_gold_spans_overlap':bool(goldspans) and all(overlap),'decode_ms':dec['elapsed_ms'],'ranking':ranking,'selected_spans':merged,'additional_neighbor_units_inspected':coverage['additional_neighbor_unit_ids_inspected'],'fallback_selected_unit_ids':coverage['selected_token_fallback_unit_ids'],'context_character_coverage':coverage['document_character_coverage'],'joint_tokens':len(enc.ids),'correct':bool(canonical_score['correct'])}
  control=d['baseline_control_input'];premise=d['arms']['ruvector_top2']['premise'];assert control=={'state':premise,'questions':rec['input']['questions']} and hashlib.sha256(raw(control)).hexdigest()==d['baseline_control_input_sha256'] and d['baseline_control_source_chunk_ids']==chosen and d['baseline_control_label']=='native104_on_ruvector_evidence' and len(premise.encode())==d['baseline_control_state_bytes']<=16384
  proofs.append(row)
 counters=engine['execution_after_close']['counters'];N=len(actual)
 for key in ['requests','native104_requests','native_core_searches','context_partitions']:
  assert counters[key+'_attempted']==counters[key+'_completed']==N
 assert counters['context_packs_attempted']==counters['context_packs_completed']==N*3
 assert counters['bge_texts_attempted']==counters['bge_texts_completed']==text_count and counters['bge_forward_batches_attempted']==counters['bge_forward_batches_completed']==bge_batches and counters['nli_forward_pairs_attempted']==counters['nli_forward_pairs_completed']==N*3 and counters['nli_input_tokens_attempted']==counters['nli_input_tokens_completed']==nli_tokens
 metrics={phase:{name:{'n':len(vals),'correct':sum(x['correct'] for x in vals),'brier':statistics.mean(x['brier'] for x in vals),'nll':statistics.mean(x['nll'] for x in vals),'errors':0,'strict_valid':len(vals)} for name,vals in arm.items()} for phase,arm in scores.items() if byphase[phase]}
 dev=obj(run/'development-comparison.json');devgate=gate(metrics['development']);assert devgate==dev['frozen_development_gate_passed']==report['development_gate_passed']
 for phase,summary in metrics.items():
  official=obj(run/('development-comparison.json' if phase=='development' else 'confirmation-comparison.json'))['metrics']
  for name,values in summary.items():
   for key,value in values.items():close(official[name][key],value)
 uncertainty={};holdout_pass=False
 for phase,rs in byphase.items():
  if not rs:continue
  groups=sorted({x['source_group'] for x in rs});assert len(groups)==(8 if phase=='development' else 32);assert all(sum(x['source_group']==g for x in rs)==3 for g in groups);uncertainty[phase]={}
  for name in ARMS:
   if name=='ruvector_top2':continue
   gains={key:[] for key in ['accuracy','brier','nll']}
   for g in groups:
    ix=[i for i,x in enumerate(rs) if x['source_group']==g]
    gains['accuracy'].append(statistics.mean(int(scores[phase]['ruvector_top2'][i]['correct'])-int(scores[phase][name][i]['correct']) for i in ix))
    for key in ['brier','nll']:gains[key].append(statistics.mean(scores[phase][name][i][key]-scores[phase]['ruvector_top2'][i][key] for i in ix))
   uncertainty[phase][name]={key:paired_bootstrap_interval(v) for key,v in gains.items()}
 if byphase['confirmation']:
  assert devgate;lock=obj(run/'confirmation-selection-lock.json');assert lock['plan_sha256']==sha(s/'epoch6/plan.json') and lock['development_comparison_sha256']==sha(run/'development-comparison.json') and lock['shared_deadline_unix']==attempt['deadline_unix'];assert lock['at']<=next(x['at'] for x in started if x['phase']=='confirmation');assert report['confirmation_status']=='USED_NOW_EXPOSED_DEV'
  holdout_pass=gate(metrics['confirmation']) and all(uncertainty['confirmation'][name]['accuracy']['ci95'][0]>0 for name in ['same_nli_lexical_top2','same_nli_positional_first2']) and all(uncertainty['confirmation'][name][key]['ci95'][0]>=-1e-12 for name in uncertainty['confirmation'] for key in ['brier','nll'])
 else:assert not devgate and not (run/'confirmation-selection-lock.json').exists() and not any(x['phase']=='confirmation' for x in started)
 assert repeatdrift<1e-5
 result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'plan_SHA256':sha(s/'epoch6/plan.json'),'source_pins_verified':len(plan['pins']),'metrics':metrics,'DEV_gate_passed':devgate,'internal_confirmation_gate_passed':holdout_pass,'confirmation_consumed':bool(byphase['confirmation']),'confirmation_now_permanently_exposed_DEV':bool(byphase['confirmation']),'paired_doc_bootstrap':uncertainty,'bootstrap_scope':'2000paired doc-group draws seed20261022, nearest empirical 2.5/97.5percentiles inherited frozen verifier; nominal unadjusted intervals.','max_same_context_singleton_logit_drift':repeatdrift,'ANN_exact_top2_set_agreement_count':sum(x['exact_top2_set_agreement'] for x in proofs),'ANN_exact_candidate_set_agreement_count':sum(x['exact_candidate_set_agreement'] for x in proofs),'arm_name_scope':'Legacytop2names are aliases: actual40rankedanchor candidates plusneighbor expansion under shared512budget, variableunitcount. No causalold-vs-newcontextclaim.','actual_requests':N,'actual_NLI_singleton_pairs':N*3,'actual_NLI_input_tokens':nli_tokens,'actual_BGE_texts':text_count,'actual_BGE_batches':bge_batches,'resources':resources,'completion':completion,'latency_by_phase_seconds':{phase:{'p50':statistics.median(x['elapsed_s'] for x in rs),'p95':float(np.percentile([x['elapsed_s'] for x in rs],95)),'max':max(x['elapsed_s'] for x in rs),'scope':'Whole HTTP request includesall3NLIcontrols+native104excerpt+evidenceencoding/index; not primary-only deployment'} for phase,rs in byphase.items() if rs},'rows':proofs,'official_rank':None,'official_score':None,'SOTA_established':False,'generic_submitted_Jev104_RRF10_champions_unchanged':True,'auditor_native_calls':0,'auditor_ONNX_calls':0,'artifact_pins':[{'path':str(p.relative_to(project)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(run.rglob('*')) if p.is_file()]}
 args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks_passed':True,'sha256':sha(args.out),'metrics':metrics,'DEV_gate':devgate,'confirmation_gate':holdout_pass,'confirmation_consumed':bool(byphase['confirmation'])}))

if __name__=='__main__':main()
