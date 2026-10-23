"""Independent saved-output epoch10 replay; no ORT/native/model calls.

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
def gate(metrics,development=False):
 if set(metrics)!=set(ARMS):return False
 expected=24 if development else 48
 if any(v['n']!=expected or v['strict_valid']!=expected or v['errors']!=0 or not all(math.isfinite(v[k]) for k in ['brier','nll']) for v in metrics.values()):return False
 p=metrics['ruvector_top2'];gain=2 if development else 0
 return all(p['correct']>=b['correct']+gain and p['brier']<=b['brier']+1e-12 and p['nll']<=b['nll']+1e-12 for n,b in metrics.items() if n!='ruvector_top2') and all(p['brier']<metrics[n]['brier']-1e-12 or p['nll']<metrics[n]['nll']-1e-12 for n in ['same_nli_lexical_top2','same_nli_positional_first2'])

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
 project=args.project;s=project/'experiments/sota-2026-10-22';study=s/'epoch10';plan=obj(study/'plan.json');assert sha(study/'plan.json')==args.expected_plan_sha
 for item in plan['pins']:assert sha(project/item['path'])==item['sha256'],item['path']
 summary=obj(study/'study-completion.json');phase_evidence={};actual=[];wire=[];server=[];started=[]
 for phase in ['development','confirmation']:
  run=study/'runs'/phase
  if not (run/'attempt.json').exists():continue
  ev={k:obj(run/(k+'.json')) for k in ['report','completion','runtime','cleanup','final-engine','resources','attempt']};phase_evidence[phase]=ev
  report=ev['report'];completion=ev['completion'];runtime=ev['runtime'];cleanup=ev['cleanup'];attempt=ev['attempt']
  assert completion['source_plan_unchanged'] and not completion['owned_group_cleanup']['live_members_after'] and completion['owned_group_cleanup']['finished_within_deadline']
  expected_number=1 if phase=='development' else 2
  assert completion['prior_closed_attempts']==12 and completion['lifetime_native_attempt']==12+expected_number
  assert attempt['new_study_native_attempt']==expected_number and attempt['lifetime_native_attempt']==12+expected_number and attempt['source_plan_sha256']==args.expected_plan_sha
  assert cleanup['engine_close_called'] and not cleanup['cleanup_errors'] and cleanup['native_child_pids_absent'];assert not any(Path('/proc',str(p)).exists() for p in [attempt['pid'],*runtime['native_child_pids']])
  assert len(ev['resources']['allowed_CPU_ids'])<=2 and runtime['receipt']['nli']['batch_size']==1 and not runtime['receipt']['nli']['padding'] and not runtime['receipt']['nli']['truncation']
  for k,v in plan['expected_native_receipt'].items():assert runtime['receipt'][k]==v
  assert runtime['receipt']['nli']['revision']==plan['expected_nli_revision'] and runtime['receipt']['nli']['model_sha256']==plan['expected_nli_sha256']
  assert runtime['receipt']['old_base_NLI_session_initialized'] is False and runtime['receipt']['unchanged_epoch6_context_policy'] is True
  assert runtime['receipt']['nli']['classes']==3 and runtime['receipt']['nli']['label_indices']=={'entailment':0,'neutral':1,'contradiction':2}
  assert attempt['model_deadline_unix']==runtime['deadline_unix'] and attempt['hard_cleanup_deadline_unix']-attempt['model_deadline_unix']>=4.9
  assert completion['wall_seconds_including_model_load']<=plan['limits']['seconds_per_batch']
  a,w,se,st=[rows(run/f) for f in ['records.jsonl','wire.jsonl','server-audit.jsonl','started-requests.jsonl']]
  assert len(a)==len(w)==len(se)==len(st)==({'development':96,'confirmation':48}[phase] if completion['exit_code']==0 else len(a))
  
  if completion['exit_code']==0:assert sha(run/'records.jsonl')==report['records_sha256'] and sha(run/'wire.jsonl')==report['wire_sha256']
  assert sum(report[k+'_completed'] for k in ['train','development','confirmation'])==len(a)
  actual+=a;wire+=w;server+=se;started+=st
 assert list(phase_evidence) in [['development'],['development','confirmation']]
 assert summary['actual_native_attempts']==len(phase_evidence) and summary['lifetime_native_attempts']==12+len(phase_evidence) and summary['allowed_further_attempts_in_closed_study']==0
 expected={phase:rows(project/path) if phase!='confirmation' or 'confirmation' in phase_evidence else [] for phase,path in plan['datasets'].items()};byphase={phase:[x for x in actual if x['measured_phase']==phase] for phase in expected}
 assert len(byphase['train'])==72 and len(byphase['development']) in [0,24] and len(byphase['confirmation']) in [0,48]
 ordered=expected['train']+(expected['development'] if byphase['development'] else [])+(expected['confirmation'] if byphase['confirmation'] else []);assert [r['id'] for r in actual]==[r['id'] for r in ordered]
 bge=Tokenizer.from_file(str(project/'models/bge-small-en-v1.5/tokenizer.json'));nli=Tokenizer.from_file(str(s/'candidate/epoch4/assets/nli-base/tokenizer.json'))
 for t in [bge,nli]:t.no_padding();t.no_truncation()
 model_tokenizer=Tokenizer.from_file(str(s/'candidate/epoch9/assets/nli-broader/tokenizer.json'));model_tokenizer.no_padding();model_tokenizer.no_truncation()
 config=obj(s/'candidate/epoch9/assets/nli-broader/config.json');assert config['id2label']=={'0':'entailment','1':'neutral','2':'contradiction'}
 feature_module=module(s/'candidate/epoch10/features.py','epoch10_saved_features');fitted_artifact=obj(study/'fitted-head.json') if (study/'fitted-head.json').exists() else None
 context=module(s/'candidate/epoch6/context.py','epoch6_source_partition');scorer=module(s/'benchmark/sources/jevbench_scoring.py','epoch6_independent_scorer');docs={split:{d['id']:d for d in obj(s/('legal-transfer/epoch3/sources/original-'+split+'.json'))['documents']} for split in ['train','dev']}
 threeway_scores={phase:{name:[] for name in ARMS if name!='native104_on_ruvector_evidence'} for phase in expected};scores={phase:{name:[] for name in ARMS} for phase in expected};proofs=[];sameinputs={};repeatdrift=0.;text_count=bge_batches=nli_tokens=0;phase_counts={phase:{'BGE_texts':0,'BGE_batches':0,'NLI_tokens':0} for phase in expected}
 for exp,rec,pair,event,begin in zip(ordered,actual,wire,server,started):
  assert rec['id']==exp['id']==pair['id']==begin['id'];phase=rec['measured_phase'];process_phase='development' if phase=='train' else phase;run=study/'runs'/process_phase;ev=phase_evidence[process_phase];runtime=ev['runtime'];attempt=ev['attempt'];assert phase==pair['phase']==begin['phase'];assert rec['evaluation']==exp['evaluation'] and rec['input']==exp['input'];assert hashlib.sha256(canonical(rec['input'])).hexdigest()==exp['input_sha256']
  assert set(json.loads(pair['request']))=={'state','questions'} and json.loads(pair['request'])==rec['input'];assert pair['status']==event['status']==200 and event['ok']
  for side in ['request','response']:assert hashlib.sha256(pair[side].encode()).hexdigest()==pair[side+'_sha256']==event[side+'_sha256']
  assert begin['request']==pair['request'] and begin['request_sha256']==pair['request_sha256'];response=rec['response'];assert json.loads(pair['response'])==response;usage=response['usage'];assert usage['native_requests']==usage['native_core_searches']==event['usage']['native_requests']==1 and usage['nli_singleton_pairs']==3 and usage['paid_calls']==0
  assert 0<=rec['elapsed_s']<=plan['limits']['seconds_per_decision'];assert datetime.fromisoformat(event['at']).timestamp()<=attempt['model_deadline_unix']
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
  text_count+=len(texts);bge_batches+=embedding['chunks']['model_batches']+embedding['query']['model_batches'];phase_counts[phase]['BGE_texts']+=len(texts);phase_counts[phase]['BGE_batches']+=embedding['chunks']['model_batches']+embedding['query']['model_batches']
  rankings={'ruvector_top2':ids,'lexical_top2':lexical(chunks,hyp),'positional_first2':list(range(min(40,len(chunks))))};doc=docs[exp['provenance']['source_split']][exp['provenance']['document_id']];assert doc['text']==state;ann=doc['annotation_sets'][0]['annotations'][exp['provenance']['hypothesis_id']];goldspans=[doc['spans'][j] for j in ann['spans']];row={'id':rec['id'],'phase':phase,'group':rec['source_group'],'native_ranking_ids':ids,'primary_selected_unit_ids':chosen,'exact_cosine_ranking_ids':exact,'exact_top2_set_agreement':set(ids[:2])==set(exact[:2]),'exact_candidate_set_agreement':set(ids)==set(exact),'gold':rec['evaluation']['gold'],'arms':{}}
  for name,alias in ARMS.items():
   answer_response=response if alias is None else response['baseline104_response'] if alias=='baseline' else response['ablation_responses'][name];answer=answer_response['answers']['decision'];p=answer['probabilities'];canonical_score=scorer.score_task(p,SimpleNamespace(labels=['Yes','No'],expected=rec['evaluation']['gold'],question={'type':'choice'}));assert canonical_score['valid'] and canonical_score['strict_valid'] and answer['choice']==canonical_score['predicted'];scores[phase][name].append({'correct':bool(canonical_score['correct']),**proper_scores(canonical_score['probs'],rec['evaluation']['gold'],['Yes','No'])})
   if alias=='baseline':continue
   key=alias or name;ad=d['arms'][key];ranking=rankings[key];assert ad['ranking_ids']==ranking;sel,expected_trace=independent_pack(state,units,ranking,hyp,nli);assert ad['coverage']['packing_attempts']==expected_trace and ad['chunk_ids']==sel and ad['chunk_spans']==[spans[i] for i in sel];merged=merged_spans(spans,sel);premise='\n\n'.join(state[a:b] for a,b in merged);assert ad['premise']==premise and ad['hypothesis']==hyp
   coverage=ad['coverage'];assert coverage['ranking_ids_considered']==ranking and coverage['ranking_depth']==len(ranking) and coverage['ranked_anchor_candidate_cap']==min(40,len(units)) and coverage['joint_pair_token_cap']==512;assert coverage['additional_neighbor_unit_ids_inspected']==sorted({step['unit_id'] for step in expected_trace if step['role']=='same-paragraph-neighbor' and step['unit_id'] not in ranking});assert coverage['selected_source_spans']==merged and coverage['omitted_chunk_ids']==[i for i in range(len(spans)) if i not in sel] and not coverage['selected_evidence_truncated'] and not coverage['claim_truncated'];assert coverage['premise_sha256']==hashlib.sha256(premise.encode()).hexdigest();close(coverage['document_character_coverage'],sum(b-a for a,b in merged)/len(state))
   numbers=[{'span':[m.start(),m.end()],'text':m.group(),'retained':any(a<=m.start() and m.end()<=b for a,b in merged)} for m in re.finditer(r'(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:\s*%|\b)',state)];assert coverage['numeric_mentions']==numbers
   policy_enc=nli.encode(premise,hyp);enc=model_tokenizer.encode(premise,hyp);dec=ad['decoding'];assert dec['frozen_epoch6_policy_pair_tokens']==len(policy_enc.ids)==coverage['joint_pair_tokens']<=512;assert dec['actual_model_pair_tokens']==len(enc.ids)<=512;assert dec['input_ids']==enc.ids and dec['attention_mask']==enc.attention_mask and dec['token_type_ids']==enc.type_ids and all(i==1 for i in enc.attention_mask);assert dec['raw_tokens']==dec['used_tokens']==dec['input_tokens']==len(enc.ids)<=512 and dec['batch_size']==1 and dec['padding_tokens']==0 and not dec['truncated'];assert dec['input_text_sha256']==hashlib.sha256(raw({'premise':premise,'hypothesis':hyp})).hexdigest()
   logits=np.asarray(dec['logits'],dtype=np.float64);assert logits.shape==(3,) and np.isfinite(logits).all();prob=np.exp(logits-logits.max());prob/=prob.sum();rawtyped={'Entailment':float(prob[0]),'Contradiction':float(prob[2]),'NotMentioned':float(prob[1])};canonical_logits=[float(logits[i]) for i in (0,2,1)];assert dec['canonical_logits_E_C_N']==canonical_logits and dec['typed_head_canonical_logits']==canonical_logits
   for label,value in rawtyped.items():close(value,dec['raw_threeway_probabilities'][label])
   features=feature_module.extract(premise,hyp,canonical_logits);assert features==dec['typed_head_features'] and dec['typed_head_feature_names']==list(feature_module.FEATURE_NAMES)
   if phase=='train':
    typed=rawtyped;assert dec['typed_head_state']=='TRAIN_COLLECTION' and dec['annotation_overlap_probability'] is None
   else:
    assert fitted_artifact is not None and dec['typed_head_state']=='FROZEN';af=fitted_artifact['auxiliary_final'];r=np.asarray(features);az=((r-np.asarray(af['mean']))/np.asarray(af['scale']))@np.asarray(af['weights']);aux=float(np.exp(-np.logaddexp(0.,-az)));close(aux,dec['annotation_overlap_probability']);b=np.asarray(canonical_logits);z=b-b.mean()+((np.r_[r,aux]-np.asarray(fitted_artifact['mean']))/np.asarray(fitted_artifact['scale']))@np.asarray(fitted_artifact['weights']);t=np.exp(z-z.max());t/=t.sum();typed=dict(zip(['Entailment','Contradiction','NotMentioned'],map(float,t)))
   for k,v in typed.items():close(v,dec['typed_threeway_probabilities'][k])
   close(p['Yes'],typed['Entailment']);close(p['No'],typed['Contradiction']+typed['NotMentioned'])
   typedgold=exp['evaluation']['original_threeway_label'];assert typedgold==ann['choice'] and rec['evaluation']['gold']==('Yes' if typedgold=='Entailment' else 'No')
   typedpred=min(typed,key=lambda k:(-typed[k],k));threeway_scores[phase][name].append({'correct':typedpred==typedgold,**proper_scores(typed,typedgold,list(typed))})
   for j,label in config['id2label'].items():close(dec['nli_probabilities'][label],prob[int(j)])
   h=dec['input_text_sha256']
   if h in sameinputs:repeatdrift=max(repeatdrift,float(np.max(np.abs(logits-sameinputs[h]))))
   else:sameinputs[h]=logits
   nli_tokens+=len(enc.ids);phase_counts[phase]['NLI_tokens']+=len(enc.ids);overlap=[any(max(0,min(g[1],b)-max(g[0],a)) for a,b in merged) for g in goldspans];row['arms'][name]={'selected':sel,'gold_span_count':len(goldspans),'any_gold_overlap':any(overlap),'all_gold_spans_overlap':bool(goldspans) and all(overlap),'decode_ms':dec['elapsed_ms'],'ranking':ranking,'selected_spans':merged,'additional_neighbor_units_inspected':coverage['additional_neighbor_unit_ids_inspected'],'fallback_selected_unit_ids':coverage['selected_token_fallback_unit_ids'],'context_character_coverage':coverage['document_character_coverage'],'joint_tokens':len(enc.ids),'correct':bool(canonical_score['correct'])}
  control=d['baseline_control_input'];premise=d['arms']['ruvector_top2']['premise'];assert control=={'state':premise,'questions':rec['input']['questions']} and hashlib.sha256(raw(control)).hexdigest()==d['baseline_control_input_sha256'] and d['baseline_control_source_chunk_ids']==chosen and d['baseline_control_label']=='native104_on_ruvector_evidence' and len(premise.encode())==d['baseline_control_state_bytes']<=16384
  proofs.append(row)
 N=len(actual)
 for phase,ev in phase_evidence.items():
  counters=ev['final-engine']['execution_after_close']['counters'];count=len(byphase[phase])+(len(byphase['train']) if phase=='development' else 0);pc={k:phase_counts[phase][k]+(phase_counts['train'][k] if phase=='development' else 0) for k in phase_counts[phase]}
  for key in ['requests','native104_requests','native_core_searches','context_partitions']:assert counters[key+'_attempted']==counters[key+'_completed']==count
  assert counters['context_packs_attempted']==counters['context_packs_completed']==count*3
  assert counters['bge_texts_attempted']==counters['bge_texts_completed']==pc['BGE_texts'] and counters['bge_forward_batches_attempted']==counters['bge_forward_batches_completed']==pc['BGE_batches']
  assert counters['nli_forward_pairs_attempted']==counters['nli_forward_pairs_completed']==count*3 and counters['nli_input_tokens_attempted']==counters['nli_input_tokens_completed']==pc['NLI_tokens']

 allmetrics={phase:{name:{'n':len(vals),'correct':sum(x['correct'] for x in vals),'brier':statistics.mean(x['brier'] for x in vals),'nll':statistics.mean(x['nll'] for x in vals),'errors':0,'strict_valid':len(vals)} for name,vals in arm.items()} for phase,arm in scores.items() if byphase[phase]}
 metrics={k:v for k,v in allmetrics.items() if k!='train'};trainmetrics=allmetrics.get('train');devgate=gate(metrics['development'],development=True) if 'development' in metrics else False
 for phase,phase_metrics in metrics.items():
  official=obj(study/'runs'/phase/(phase+'-comparison.json'))['metrics']
  for name,values in phase_metrics.items():
   for key,value in values.items():close(official[name][key],value)
 if byphase['development']:
  assert devgate==phase_evidence['development']['report']['development_gate_passed']==obj(study/'runs/development/development-comparison.json')['frozen_development_gate_passed']
 uncertainty={};holdout_pass=False
 for phase,rs in byphase.items():
  if not rs or phase=='train':continue
  groups=sorted({x['source_group'] for x in rs});assert len(groups)==(8 if phase=='development' else 16);assert all(sum(x['source_group']==g for x in rs)==3 for g in groups);uncertainty[phase]={}
  for name in ARMS:
   if name=='ruvector_top2':continue
   gains={key:[] for key in ['accuracy','brier','nll']}
   for g in groups:
    ix=[i for i,x in enumerate(rs) if x['source_group']==g]
    gains['accuracy'].append(statistics.mean(int(scores[phase]['ruvector_top2'][i]['correct'])-int(scores[phase][name][i]['correct']) for i in ix))
    for key in ['brier','nll']:gains[key].append(statistics.mean(scores[phase][name][i][key]-scores[phase]['ruvector_top2'][i][key] for i in ix))
   uncertainty[phase][name]={key:paired_bootstrap_interval(v) for key,v in gains.items()}
 admission=obj(study/'runtime-admission.json') if (study/'runtime-admission.json').exists() else None
 if admission:
  initialization=phase_evidence['development']['runtime']['receipt']['initialization_wall_seconds'];devmax=max(r['elapsed_s'] for r in byphase['development']);devunits=max(len(context.partition(r['input']['state'],nli,bge,target=128,nli_cap=160,bge_cap=256,max_units=192)) for r in expected['development']);assert devunits==plan['runtime_admission']['max_DEV_units']==admission['max_DEV_units']==23 and plan['runtime_admission']['max_confirmation_units']==admission['max_confirmation_units']==57
  projected=48*devmax*max(1,57/23)+2*initialization+60;close(projected,admission['projected_confirmation_seconds']);close(initialization,admission['DEV_initialization_seconds']);close(devmax,admission['max_DEV_HTTP_seconds']);remaining=plan['lease_expires_unix']-datetime.fromisoformat(admission['at']).timestamp();assert admission['allowed']==(projected<=600 and remaining>=projected+30)
 if byphase['confirmation']:
  assert devgate and admission['allowed'];lock=obj(study/'confirmation-selection-lock.json');assert lock['plan_sha256']==sha(study/'plan.json') and lock['development_comparison_sha256']==sha(study/'runs/development/development-comparison.json') and lock['runtime_admission_sha256']==sha(study/'runtime-admission.json') and lock['fitted_head_sha256']==sha(study/'fitted-head.json') and lock['fit_lock_sha256']==sha(study/'readout-fit-lock.json');assert lock['at']<=phase_evidence['confirmation']['attempt']['at']<=next(r['at'] for r in started if r['phase']=='confirmation')
  holdout_pass=gate(metrics['confirmation']) and all(uncertainty['confirmation'][name]['accuracy']['ci95'][0]>0 for name in uncertainty['confirmation']) and all(uncertainty['confirmation'][name][key]['ci95'][0]>=-1e-12 for name in uncertainty['confirmation'] for key in ['brier','nll'])
 else:
  assert not (study/'confirmation-selection-lock.json').exists() and not (study/'runs/confirmation/attempt.json').exists() and not any(r['phase']=='confirmation' for r in started)
  if byphase['development']:assert not devgate or not admission['allowed'];assert summary['status']==('REJECTED_DEV_GATE' if not devgate else 'BLOCKED_CONFIRMATION_RUNTIME_BUDGET')
  else:assert summary['status']=='FAILED_PRESERVED_EVIDENCE' and not phase_evidence['development']['report']['fit_complete']
 resources={phase:ev['resources'] for phase,ev in phase_evidence.items()};completion={phase:ev['completion'] for phase,ev in phase_evidence.items()}
 assert repeatdrift<1e-5
 fit_verifier=module(HERE/'verify_fit.py','epoch10_independent_saved_fits');fitproof=fit_verifier.run(project)
 result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'status':summary['status'],'plan_SHA256':sha(study/'plan.json'),'source_pins_verified':len(plan['pins']),'metrics':{'development':metrics.get('development'),'confirmation':metrics.get('confirmation')},'train_prefit_metrics':trainmetrics,'multiclass_metrics':{phase:{name:{'n':len(vals),'correct':sum(x['correct'] for x in vals),'brier':statistics.mean(x['brier'] for x in vals),'nll':statistics.mean(x['nll'] for x in vals)} for name,vals in arms.items()} for phase,arms in threeway_scores.items() if byphase[phase]},'actual_successful_HTTP_by_corpus':{phase:len(rs) for phase,rs in byphase.items()},'training_feature_HTTP_requests':len(byphase['train']),'DEV_gate_passed':devgate,'internal_confirmation_gate_passed':holdout_pass,'confirmation_consumed':'confirmation' in phase_evidence,'confirmation_now_permanently_exposed_DEV':'confirmation' in phase_evidence,'paired_doc_bootstrap':uncertainty,'bootstrap_scope':'2000paired doc-group draws seed20261022, nominal unadjusted intervals; gainsaccuracy primary-control, properlosscontrol-primary','headfitdiagnostics':fitproof,'max_same_context_singleton_logit_drift':repeatdrift,'ANN_exact_top2_set_agreement_count':sum(x['exact_top2_set_agreement'] for x in proofs),'ANN_exact_candidate_set_agreement_count':sum(x['exact_candidate_set_agreement'] for x in proofs),'ANN_full_order_agreement_count':sum(x['native_ranking_ids']==x['exact_cosine_ranking_ids'] for x in proofs),'arm_name_scope':'Legacytop2names alias40rankedanchors+neighbors under512; allsamehead/model; excerpt104differentreader.','actual_requests':N,'actual_NLI_singleton_pairs':N*3,'actual_NLI_input_tokens':nli_tokens,'actual_BGE_texts':text_count,'actual_BGE_batches':bge_batches,'resources':resources,'completion':completion,'phase_counts':phase_counts,'runtime_admission':admission,'study_completion':summary,'latency_by_phase_seconds':{phase:{'p50':statistics.median(x['elapsed_s'] for x in rs),'p95':float(np.percentile([x['elapsed_s'] for x in rs],95)),'max':max(x['elapsed_s'] for x in rs),'scope':'WholeHTTPall3NLIarms+native104excerpt+embedding/index, notprimarydeployment'} for phase,rs in byphase.items() if rs},'rows':proofs,'official_rank':None,'official_score':None,'SOTA_established':False,'generic_submitted_Jev104_RRF10_champions_unchanged':True,'auditor_native_calls':0,'auditor_ONNX_calls':0,'artifact_pins':[{'path':str(p.relative_to(project)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(study.rglob('*')) if 'runs' in p.parts or p.name in ['fitted-head.json','readout-fit-lock.json','runtime-admission.json','study-completion.json','confirmation-selection-lock.json'] if p.is_file()]}
 args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks_passed':True,'sha256':sha(args.out),'metrics':metrics,'DEV_gate':devgate,'confirmation_gate':holdout_pass,'confirmation_consumed':'confirmation' in phase_evidence}))

if __name__=='__main__':main()
