"""Pure saved-record analysis. Never import a model runtime or open confirmation/full-source data."""
from pathlib import Path
from collections import Counter
import argparse,hashlib,json,math,statistics
ARMS={'ruvector_top2':None,'same_nli_lexical_top2':'lexical_top2','same_nli_positional_first2':'positional_first2','native104_on_ruvector_evidence':'baseline'}
TYPED=('Entailment','Contradiction','NotMentioned')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def mean(v):return statistics.mean(v) if v else None
def close(a,b):
 if not math.isclose(float(a),float(b),rel_tol=0,abs_tol=1e-10):raise ValueError('Cached scalar mismatch')
def normalized(p):
 if not p or any(not math.isfinite(float(v)) or float(v)<0 for v in p.values()):raise ValueError('Invalid probability')
 total=sum(p.values())
 if total<=0 or abs(total-1)>1e-3:raise ValueError('Invalid normalized probability')
 return {k:float(v)/total for k,v in p.items()}
def decision(p):return min(p,key=lambda k:(-p[k],k))
def scores(p,gold):
 p=normalized(p)
 if gold not in p:raise ValueError('Missing gold class')
 return {'correct':decision(p)==gold,'brier':sum((v-float(k==gold))**2 for k,v in p.items()),'nll':-math.log(max(p[gold],1e-15))}
def summarize(items):
 if not items:return {'n':0,'correct':0,'brier':None,'nll':None}
 return {'n':len(items),'correct':sum(x['correct'] for x in items),'brier':mean([x['brier'] for x in items]),'nll':mean([x['nll'] for x in items])}
def softmax(v):
 if len(v)!=3 or not all(math.isfinite(float(x)) for x in v):raise ValueError('Invalid triple')
 e=[math.exp(x-max(v)) for x in v];z=sum(e);return [x/z for x in e]
def pair(fp,quant):
 for key in ('input_ids','attention_mask','token_type_ids','input_text_sha256','raw_label_indices'):
  if fp[key]!=quant[key]:raise ValueError('Different paired input/feed')
 if fp['precision']!='FP32' or quant['precision']!='INT8_TRAIN_DIAGNOSTIC':raise ValueError('Different precision contract')
 a=fp['canonical_logits_E_C_N'];b=quant['canonical_logits_E_C_N'];pa=softmax(a);pb=softmax(b)
 for i,k in enumerate(TYPED):close(pa[i],fp['raw_threeway_probabilities'][k]);close(pb[i],quant['raw_threeway_probabilities'][k])
 raw=[x-y for x,y in zip(a,b)];center=[(x-mean(a))-(y-mean(b)) for x,y in zip(a,b)];m=[.5*(x+y) for x,y in zip(pa,pb)]
 def kl(p,q):return sum(x*(math.log(x)-math.log(y)) for x,y in zip(p,q) if x>0)
 ba={'Yes':pa[0],'No':pa[1]+pa[2]};bb={'Yes':pb[0],'No':pb[1]+pb[2]}
 ta=dict(zip(TYPED,pa));tb=dict(zip(TYPED,pb))
 return {'raw_logits_max_absolute_difference':max(map(abs,raw)),'raw_logits_RMS_difference':math.sqrt(mean([x*x for x in raw])),'centered_logits_max_absolute_difference':max(map(abs,center)),'typed_probability_max_absolute_difference':max(abs(x-y) for x,y in zip(pa,pb)),'posterior_total_variation':.5*sum(abs(x-y) for x,y in zip(pa,pb)),'Jensen_Shannon_divergence_nats':.5*(kl(pa,m)+kl(pb,m)),'typed_decision_agrees':decision(ta)==decision(tb),'binary_decision_agrees':decision(ba)==decision(bb),'FP32_binary_probabilities':ba,'INT8_binary_probabilities':bb,'FP32_typed_probabilities':ta,'INT8_typed_probabilities':tb,'identical_feed_tokens':len(fp['input_ids'])}
def analyze(records):
 train=[x for x in records if x['measured_phase']=='train'];dev=[x for x in records if x['measured_phase']=='development']
 if len(train)!=6 or len(dev)!=24 or len(records)!=30 or len({x['id'] for x in records})!=30:raise ValueError('Expected exactly6TRAIN+24DEV unique saved outputs')
 paired=[];train_scores={p:{'binary':[],'threeway':[]} for p in ('FP32','INT8')}
 for row in train:
  d=row['response']['diagnostics']['decision'];fp=d['arms']['ruvector_top2']['decoding'];q=d['TRAIN_only_precision_pair']['quantized_decoding'];out=pair(fp,q);gold=row['evaluation'];out.update(id=row['id'],source_group=row['source_group'],gold_binary=gold['gold'],gold_threeway=gold['original_threeway_label'])
  saved=row['response']['precision_fidelity']['decision']
  for key in ('raw_logits_max_absolute_difference','raw_logits_RMS_difference','centered_logits_max_absolute_difference','typed_probability_max_absolute_difference','Jensen_Shannon_divergence_nats'):close(out[key],saved[key])
  close(2*out['posterior_total_variation'],saved['typed_probability_L1_difference'])
  if out['typed_decision_agrees']!=saved['typed_decision_agrees'] or out['binary_decision_agrees']!=saved['binary_decision_agrees']:raise ValueError('Cached decision agreement mismatch')
  for p in train_scores:
   train_scores[p]['binary'].append(scores(out[p+'_binary_probabilities'],gold['gold']))
   train_scores[p]['threeway'].append(scores(out[p+'_typed_probabilities'],gold['original_threeway_label']))
  paired.append(out)
 train_summary={p:{role:summarize(v) for role,v in roles.items()} for p,roles in train_scores.items()}
 ranges={}
 for k in ('raw_logits_max_absolute_difference','raw_logits_RMS_difference','centered_logits_max_absolute_difference','typed_probability_max_absolute_difference','posterior_total_variation','Jensen_Shannon_divergence_nats'):
  v=[x[k] for x in paired];ranges[k]={'mean':mean(v),'max':max(v),'min':min(v)}
 output={};errors=[]
 for arm,alias in ARMS.items():
  binary_scores=[];typed_scores=[];choices=Counter();typed_choices=Counter();confusion={gold:{pred:0 for pred in TYPED} for gold in TYPED};wrongconf=[];coverage=[];total_numbers=retained_numbers=0
  for row in dev:
   response=row['response'];res=response if alias is None else response['baseline104_response'] if alias=='baseline' else response['ablation_responses'][arm]
   answer=res['answers']['decision'];p=normalized(answer['probabilities']);pred=decision(p);gold=row['evaluation'];score=scores(p,gold['gold']);binary_scores.append(score);choices[pred]+=1
   if pred!=answer['choice']:raise ValueError('Saved binary decision mismatch')
   if not score['correct']:
    wrongconf.append(max(p.values()));errors.append({'id':row['id'],'arm':arm,'gold_binary':gold['gold'],'prediction':pred,'confidence':max(p.values())})
   if alias=='baseline':continue
   d=response['diagnostics']['decision']['arms'][alias or arm];dec=d['decoding'];typed=normalized(dec['raw_threeway_probabilities']);tp=decision(typed);typed_choices[tp]+=1;confusion[gold['original_threeway_label']][tp]+=1;typed_scores.append(scores(typed,gold['original_threeway_label']))
   c=d['coverage'];n=sum(bool(x['retained']) for x in c['numeric_mentions']);total=len(c['numeric_mentions']);assert n==c['numeric_mentions_retained'] and total-n==c['numeric_mentions_omitted']
   retained=sum(b-a for a,b in c['selected_source_spans']);assert retained==c['retained_source_characters'] and c['document_characters']==len(row['input']['state']);close(c['document_character_coverage'],retained/len(row['input']['state']))
   total_numbers+=total;retained_numbers+=n;coverage.append(c['document_character_coverage'])
  output[arm]={'binary':summarize(binary_scores),'binary_predicted_counts':dict(sorted(choices.items())),'wrong_confidence_mean':mean(wrongconf),'wrong_confidence_at_least_0_8':sum(x>=.8 for x in wrongconf)}
  if alias!='baseline':output[arm].update(threeway=summarize(typed_scores),typed_predicted_counts=dict(sorted(typed_choices.items())),typed_confusion_gold_to_prediction=confusion,source_retention={'numeric_mentions_total_per_query':total_numbers,'numeric_mentions_retained_per_query':retained_numbers,'numeric_retention_fraction':retained_numbers/total_numbers if total_numbers else None,'mean_document_character_coverage_per_query':mean(coverage),'scope':'Repeated per-query source-position exposure counts, not unique document totals, numeric truth, annotation coverage or evidence sufficiency.'})
 return {'TRAIN_paired':{'n':6,'document_groups':2,'binary_agreement_count':sum(x['binary_decision_agrees'] for x in paired),'typed_agreement_count':sum(x['typed_decision_agrees'] for x in paired),'differences':ranges,'precision_scores':train_summary,'examples':paired,'scope':'Paired co-located published FP32/INT8 exports on identical native packed contexts from already exposed TRAIN documents; descriptive, no fit/selection or benchmark generalization.'},'DEV':{'n':24,'document_groups':len({x['source_group'] for x in dev}),'gold_binary_counts':dict(Counter(x['evaluation']['gold'] for x in dev)),'gold_threeway_counts':dict(Counter(x['evaluation']['original_threeway_label'] for x in dev)),'arms':output,'errors':errors,'latency_seconds':{'p50':statistics.median(x['elapsed_s'] for x in dev),'scope':'Whole saved HTTP request; three FP32 arms plus Native104/evidence, not primary-only deployment.'}},'new_model_calls':0,'new_native_calls':0,'new_fits':0,'confirmation_labels_read':False,'source_original_fidelity_established':False}
def findings(diag):
 t=diag['TRAIN_paired'];d=diag['DEV'];a=d['arms'];n=a['ruvector_top2'];p=a['same_nli_positional_first2'];q=a['native104_on_ruvector_evidence']
 return {'schema_version':1,'status':'REJECTED_DEV_GATE','TRAIN_fidelity':{'binary_agreement':str(t['binary_agreement_count'])+'/6','threeway_agreement':str(t['typed_agreement_count'])+'/6','max_posterior_total_variation':t['differences']['posterior_total_variation']['max'],'mean_posterior_total_variation':t['differences']['posterior_total_variation']['mean'],'max_centered_logit_difference':t['differences']['centered_logits_max_absolute_difference']['max'],'binary_proper_scores':{k:v['binary'] for k,v in t['precision_scores'].items()},'interpretation':'Exact same-input variant differences are measured on six exposed TRAIN inputs; they do not establish source-original fidelity, a pure quantization causal effect or held-out accuracy superiority. No precision was selected from these outputs.'},'DEV':{'native':n,'positional':p,'excerpt104':q,'all_arms_binary_correct':{k:v['binary']['correct'] for k,v in a.items()},'interpretation':'The fixed FP32 native arm must pass every frozen control/proper-score condition; a gain against one retrieval selector cannot override another failed gate. New DEV documents differ from e11, so cross-epoch13vs12 is not a causal accuracy gain.'},'next_direction':'Use the saved paired variant evidence and legal contradiction/neutral errors to prioritize a separately frozen source-verifiable legal decision model. Do not rescue or select a precision, threshold, context or fallback on this exposed DEV. Any new study needs its own checkpoint lock and frozen source/data/budget gates within the existing authorization.','limits':['Only two TRAIN and eight DEV document groups','Unknown pretraining overlap and exact upstream weight/conversion provenance','Numeric and character retention are source-position exposure, not evidence sufficiency','No confirmation attempt, champion promotion, official score/rank or SOTA established'],'new_model_calls':0,'new_native_calls':0,'new_fits':0}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--records',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--findings-out',type=Path,required=True);args=ap.parse_args()
 if args.out.exists() or args.findings_out.exists():raise ValueError('Refuse output overwrite')
 records=[json.loads(x) for x in args.records.read_text().splitlines() if x];diag=analyze(records);diag.update(schema_version=1,saved_records_sha256=sha(args.records),frozen_candidate_manifest_sha256='e026244f921171860a8cb9a9b9ce0c03de61bd2330d6521653b16db9455b9aaf',scope='Pure postmeasurement analysis of already consumed30saved outputs only; no CONF/full-source/model access.')
 for path,value in ((args.out,diag),(args.findings_out,findings(diag))):
  with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
 print(json.dumps({'diagnostic_sha256':sha(args.out),'findings_sha256':sha(args.findings_out),'new_inference':0}))
if __name__=='__main__':main()
