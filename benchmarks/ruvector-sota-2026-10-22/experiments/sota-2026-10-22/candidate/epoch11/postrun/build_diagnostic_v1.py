"""Terminal DEV-only saved-logit/evidence/vector diagnostic; never infer or fit."""
import argparse,collections,hashlib,json,math,statistics
from pathlib import Path
PREFIX='experiments/sota-2026-10-22/'
ARMS=('ruvector_top2','same_nli_lexical_top2','same_nli_positional_first2','native104_on_ruvector_evidence')
SELECTORS=dict(zip(ARMS[:3],('ruvector_top2','lexical_top2','positional_first2')))
CLASSES=('Entailment','Contradiction','NotMentioned')
def obj(p):return json.loads(p.read_text())
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x] if p.exists() else []
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p,root):return {'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':digest(p)}
def decision(p):return min(p,key=lambda k:(-p[k],k))
def metrics(p,gold):
 if set(p)!={'Yes','No'} or gold not in p or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in p.values()) or abs(sum(p.values())-1)>1e-3:raise ValueError('Invalid cached probabilities')
 # Preserve the pinned scorer convention: float32 native104 distributions insideSUM_TOL are notrenormalized.
 choice=decision(p)
 return {'correct':choice==gold,'predicted':choice,'brier':sum((v-float(k==gold))**2 for k,v in p.items()),'nll':-math.log(max(p[gold],1e-15)),'confidence':max(p.values())}
def typed(raw,mapping):
 if mapping!={'entailment':0,'neutral':1,'contradiction':2} or len(raw)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in raw):raise ValueError('Invalid frozen typed logits')
 exps=[math.exp(v-max(raw)) for v in raw];p=[v/sum(exps) for v in exps]
 return {'Entailment':p[0],'Contradiction':p[2],'NotMentioned':p[1]}
def merge(spans,length):
 out=[]
 for pair in sorted(spans):
  if len(pair)!=2 or any(type(x) is not int for x in pair) or not 0<=pair[0]<pair[1]<=length:raise ValueError('Invalid source spans')
  a,b=pair
  if out and a<=out[-1][1]:out[-1][1]=max(b,out[-1][1])
  else:out.append([a,b])
 return out

def percentile(v,q):
 if not v:return None
 a=sorted(v);index=(len(a)-1)*q;low=math.floor(index);high=math.ceil(index)
 return a[low]+(a[high]-a[low])*(index-low)
def summarize(v):
 if not v:return {'n':0,'correct':0,'accuracy':None,'brier':None,'nll':None,'predicted_counts':{}}
 wrong=[x for x in v if not x['correct']]
 return {'n':len(v),'correct':sum(x['correct'] for x in v),'accuracy':sum(x['correct'] for x in v)/len(v),'brier':statistics.mean(x['brier'] for x in v),'nll':statistics.mean(x['nll'] for x in v),'predicted_counts':dict(collections.Counter(x['predicted'] for x in v)),'wrong_confidence_at_least_0_8':sum(x['confidence']>=.8 for x in wrong),'mean_wrong_confidence':statistics.mean(x['confidence'] for x in wrong) if wrong else None}
def validate_projection(projection,records,records_path):
 if projection.get('saved_DEV_records_sha256')!=digest(records_path) or projection.get('confirmation_records_or_labels_included') is not False:raise ValueError('Projection must bind exact consumedDEV only')
 a=projection['records'];identities={x['id'] for x in records}
 if len(a)!=len(records) or len({x['id'] for x in a})!=len(a) or {x['id'] for x in a}!=identities:raise ValueError('Unexpected/missing DEV projection identities')
 return {x['id']:x for x in a}
def native_proof(diag,run):
 r=diag['retrieval'];e=r['bundle_evidence'];path=run/'bundles'/e['relativefilename']
 if path.is_symlink() or path.name!=e['sha256']+'.json' or digest(path)!=e['sha256'] or path.stat().st_size!=e['bytes'] or r['native']['bundle_sha256']!=e['sha256']:raise ValueError('Cached native bundle identity changed')
 b=obj(path);v=b['vectors'];q=b['query_vectors']
 if len(v)!=diag['total_chunks'] or len(q)!=1 or any(len(x)!=384 or any(type(z) not in (int,float) or not math.isfinite(z) for z in x) for x in v+q):raise ValueError('Invalid saved native vectors')
 norms=[math.sqrt(sum(z*z for z in x)) for x in v];qn=math.sqrt(sum(z*z for z in q[0]))
 if abs(qn-1)>1e-5 or any(abs(n-1)>1e-5 for n in norms):raise ValueError('Unexpected saved vector normalization')
 cosine=[sum(a*b for a,b in zip(x,q[0]))/(n*qn) for x,n in zip(v,norms)];exact=sorted(range(len(v)),key=lambda i:(-cosine[i],i))[:min(40,len(v))];native=r['native'];ids=native['queries'][0]['ids']
 if not native['native'] or native['package_version']!='0.1.33' or len(ids)!=len(set(ids)) or len(ids)!=min(40,len(v)) or any(type(i) is not int or not 0<=i<len(v) for i in ids):raise ValueError('Invalid actual native ranking')
 return {'native_ids':ids,'saved_cosine_ids':exact,'top2_set_agreement':set(ids[:2])==set(exact[:2]),'candidate_set_agreement':set(ids)==set(exact),'full_order_agreement':ids==exact,'bundle':pin(path,run.parents[4])}

def build(root,annotation_path=None):
 root=Path(root).resolve();study=root/(PREFIX+'epoch11');run=study/'runs/development';terminal=study/'study-completion.json'
 summary=obj(terminal)
 if summary.get('allowed_further_attempts_in_closed_study')!=0 or summary.get('status') in ('PREPARED','STARTING','DEVELOPMENT'):raise ValueError('Require closed terminal study, never inspect activeoutputs')
 records_path=run/'records.jsonl';records=rows(records_path)
 if len(records)>24 or len({x['id'] for x in records})!=len(records) or any(x.get('measured_phase')!='development' or x.get('split')!='dev' for x in records):raise ValueError('Only exact successful saved DEV records accepted')
 proposal_path=root/(PREFIX+'candidate/epoch11/proposal-manifest.json');proposal=obj(proposal_path);plan=obj(study/'plan.json');wanted=next(x for x in plan['pins'] if x['path']==PREFIX+'candidate/epoch11/proposal-manifest.json')
 if digest(proposal_path)!=wanted['sha256']:raise ValueError('Frozen candidate manifest changed')
 for x in proposal['sources']:
  p=root/x['path']
  if p.stat().st_size!=x['bytes'] or digest(p)!=x['sha256']:raise ValueError('Frozen candidate source changed')
 annotations=validate_projection(obj(annotation_path),records,records_path) if annotation_path else {}
 results={a:[] for a in ARMS};confusion={a:collections.Counter() for a in ARMS[:3]};coverage={a:[] for a in ARMS[:3]};groups=collections.defaultdict(lambda:{a:0 for a in ARMS});cases=[];ann=[];seen_context={};max_drift=0.;token_counts=[]
 for row in records:
  gold=row['evaluation']['gold'];tg=row['evaluation']['original_threeway_label'];state=row['input']['state'];response=row['response'];d=response['diagnostics']['decision']
  if tg not in CLASSES or gold!=('Yes' if tg=='Entailment' else 'No') or d['source_state_sha256']!=hashlib.sha256(state.encode()).hexdigest() or d['source_state']!=state:raise ValueError('Cached source/gold identity changed')
  native=native_proof(d,run);ann.append(native);case={'id':row['id'],'source_group':row['source_group'],'gold_binary':gold,'gold_threeway':tg,'predictions':{},'typed_predictions':{}}
  answers={ARMS[0]:response['answers']['decision'],ARMS[1]:response['ablation_responses'][ARMS[1]]['answers']['decision'],ARMS[2]:response['ablation_responses'][ARMS[2]]['answers']['decision'],ARMS[3]:response['baseline104_response']['answers']['decision']}
  for arm,answer in answers.items():
   value=metrics(answer['probabilities'],gold)
   if answer['choice']!=value['predicted']:raise ValueError('Cachedchoice/probability disagreement')
   results[arm].append(value);groups[row['source_group']][arm]+=value['correct'];case['predictions'][arm]=value['predicted']
  for arm,selector in SELECTORS.items():
   x=d['arms'][selector];t=x['decoding'];probs=typed(t['logits'],t['raw_label_indices'])
   if t['model_repo']!=proposal['model_identity']['repo'] or t['model_revision']!=proposal['model_identity']['revision']:raise ValueError('Cached pretrainedmodel identity changed')
   if any(abs(probs[k]-t['raw_threeway_probabilities'][k])>1e-10 for k in probs):raise ValueError('Typedrawlogit replay mismatch')
   expected={'Yes':probs['Entailment'],'No':probs['Contradiction']+probs['NotMentioned']}
   if any(abs(expected[k]-answers[arm]['probabilities'][k])>1e-10 for k in expected):raise ValueError('Neutral-preserving readout changed')
   if t['truncated'] or t['padding_tokens'] or not 0<t['actual_model_pair_tokens']<=512 or not 0<t['frozen_epoch6_policy_pair_tokens']<=512:raise ValueError('Cached token guards changed')
   token_counts.append(t['actual_model_pair_tokens']);key=(x['premise'],x['hypothesis']);prior=seen_context.setdefault(key,t['logits']);max_drift=max(max_drift,max(abs(a-b) for a,b in zip(prior,t['logits'])))
   tp=decision(probs);confusion[arm][(tg,tp)]+=1;case['typed_predictions'][arm]=tp
   cov=x['coverage'];selected=merge(cov['selected_source_spans'],len(state))
   if x['premise']!='\n\n'.join(state[a:b] for a,b in selected):raise ValueError('Selected exactcontext changed')
   nums=cov['numeric_mentions']
   for n in nums:
    a,b=n['span']
    if state[a:b]!=n['text'] or n['retained']!=any(c<=a and b<=e for c,e in selected):raise ValueError('Numerical source retention changed')
   value={'numeric_total':len(nums),'numeric_retained':sum(n['retained'] for n in nums),'source_character_coverage':cov['document_character_coverage'],'binary_correct':results[arm][-1]['correct']}
   if annotations:
    g=annotations[row['id']]
    if g['gold_threeway']!=tg or g['source_group']!=row['source_group'] or g['hypothesis_id']!=row['provenance']['hypothesis_id']:raise ValueError('Consumed DEVannotation identity changed')
    gs=merge(g['annotation_spans'],len(state));total=sum(b-a for a,b in gs);retained=sum(max(0,min(b,y)-max(a,c)) for a,b in gs for c,y in selected)
    value.update(annotation_available=bool(total),any_gold_overlap=retained>0 if total else None,all_gold_characters=retained==total if total else None)
   coverage[arm].append(value)
  cases.append(case)
 metrics_by_arm={a:summarize(v) for a,v in results.items()};complete=len(records)==24
 if complete and len(groups)!=8:raise ValueError('CompleteDEV mustcontain8documentgroups')
 if complete and summary.get('development_metrics'):
  for a in ARMS:
   for k in ('n','correct','brier','nll'):
    if abs(metrics_by_arm[a][k]-summary['development_metrics'][a][k])>1e-10:raise ValueError('Parentmetrics changed')
 coverage_summaries={}
 for a,v in coverage.items():
  x={'numeric_total':sum(t['numeric_total'] for t in v),'numeric_retained':sum(t['numeric_retained'] for t in v),'mean_source_character_coverage':statistics.mean(t['source_character_coverage'] for t in v) if v else None}
  if annotations:
   av=[t for t in v if t['annotation_available']];x.update(annotated_cases=len(av),any_gold_overlap=sum(t['any_gold_overlap'] for t in av),all_gold_characters=sum(t['all_gold_characters'] for t in av),fully_retained_binary_wrong=sum(t['all_gold_characters'] and not t['binary_correct'] for t in av))
  coverage_summaries[a]=x
 lat=[x['elapsed_s'] for x in records];started=rows(run/'started-requests.jsonl');wire=rows(run/'wire.jsonl');paired={a:dict(collections.Counter('both_right' if x['correct'] and y['correct'] else 'native_only_right' if x['correct'] else 'other_only_right' if y['correct'] else 'both_wrong' for x,y in zip(results[ARMS[0]],results[a]))) for a in ARMS[1:]}
 inputs=[terminal,proposal_path,study/'plan.json',records_path,run/'wire.jsonl',run/'completion.json',run/'resources.json']
 if annotation_path:inputs.append(annotation_path)
 return {'schema_version':1,'status':'COMPLETE_DEV_DIAGNOSTIC' if complete else 'INCOMPLETE_DEV_DIAGNOSTIC_NO_FULL_SCORE','parent_terminal_status':summary['status'],'scope':'Pure cached DEVsuccesses only; no CONF text/labels/files opened, no models/native calls/fit/calibration/candidatevariants. Partialrows are not fullcorpus scores.','DEV_complete':complete,'successful_DEV_records':len(records),'document_groups':len(groups),'gold_binary_counts':dict(collections.Counter(x['evaluation']['gold'] for x in records)),'gold_threeway_counts':dict(collections.Counter(x['evaluation']['original_threeway_label'] for x in records)),'four_arm_metrics':metrics_by_arm,'threeway_confusions':{a:[{'gold':g,'predicted':p,'n':n} for (g,p),n in sorted(v.items())] for a,v in confusion.items()},'paired_disagreements':paired,'per_document_correct':dict(groups),'case_decisions_only':cases,'coverage':coverage_summaries,'gold_annotation_retention_available':bool(annotations),'coverage_scope':'Character/numerical retention is exposure, not sufficiency or numericaltruth. NotMentioned has no positiveannotation; noabsenceproof. Counts repeatdocumentsthreehypotheses.','saved_vector_native_audit':{'requests':len(ann),'top2_set_agreements':sum(x['top2_set_agreement'] for x in ann),'candidate_set_agreements':sum(x['candidate_set_agreement'] for x in ann),'full_order_agreements':sum(x['full_order_agreement'] for x in ann),'rows':ann,'scope':'Purecosine arithmetic on savedvectors; no newANN/native search. Disagreements retained.'},'same_context_max_logit_drift':max_drift,'max_actual_model_pair_tokens':max(token_counts) if token_counts else None,'whole_HTTP_latency_seconds':{'p50':statistics.median(lat) if lat else None,'p95':percentile(lat,.95),'max':max(lat) if lat else None,'scope':'All3NLIarms+Native104excerpt+BGE/nativeindex, not primary-onlydeployment'},'actual_request_counts':{'started':len(started),'wire':len(wire),'HTTP200':sum(x['status']==200 for x in wire),'failed_HTTP':sum(x['status']!=200 for x in wire),'parsed_successful_records':len(records),'started_without_wire':len(started)-len(wire)},'resource_receipt':obj(run/'resources.json') if (run/'resources.json').exists() else None,'statistical_unit':'Atmost8documentgroups,3correlatedhypotheses each; descriptive only, no cross-epochcausality or independentquery inference','source_result_pins':[pin(p,root) for p in inputs if p.is_file()],'new_model_calls':0,'new_native_calls':0,'new_optimizer_fits':0,'candidate_or_gate_changes':0,'official_score':None,'official_rank':None}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--annotations',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=build(a.root,a.annotations)
 with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({'status':result['status'],'output_sha256':digest(a.output),'model_native_fit_calls':0}))
