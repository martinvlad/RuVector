"""Independent stdlib three-class observed-probability metrics; no model imports."""
import math,random
LABELS=('NotMentioned','Entailment','Contradiction');TOKENS=('N','E','C')
ARMS=('qwen_native_joint_context','qwen_lexical_joint_context','qwen_source_order_joint_context');PRIMARY=ARMS[0];CONTROLS=ARMS[1:]
GATE_EPS=1e-12;PROB_SUM_EPS=1e-6;BOOTSTRAP_SEED=43;BOOTSTRAP_REPLICATES=256
GATE_NAMES=('integrity_complete_no_errors','all_three_full_N12','all_three_gold_classes_represented','native_at_least_one_correct_per_gold_class',*(a+':'+s for a in CONTROLS for s in ['primary_gain_at_least_two_correct','Brier_nonincrease','observed_probability_NLL_nonincrease']))
def require(v,code):
 if not v:raise ValueError(code)
def finite(x):return type(x)in(int,float)and math.isfinite(x)
def observed_probabilities(values):
 require(type(values)is list and len(values)==3 and all(finite(p)and 0<p<=1 for p in values),'EXACT_THREE_POSITIVE_FINITE_OBSERVED_PROBABILITIES');require(abs(math.fsum(values)-1)<=PROB_SUM_EPS,'OBSERVED_F32_PROBABILITY_MASS_OUTSIDE_FROZEN_TOLERANCE');return values

def winner(values):
 observed_probabilities(values);return max(range(3),key=lambda i:values[i])
def q(values,f):
 require(type(values)is list and values and all(finite(x)for x in values),'FINITE_OBSERVATIONS');s=sorted(values);x=(len(s)-1)*f;i=int(x);return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(x-i)
def interval(values):return {'lower_2_5_percentile':q(values,.025),'upper_97_5_percentile':q(values,.975)}
def row_score(probabilities,gold):
 observed_probabilities(probabilities);require(type(gold)is str and gold in LABELS,'AUTHORITATIVE_CASE_SENSITIVE_GOLD_ENUM');g=LABELS.index(gold);pred=winner(probabilities);return {'prediction':LABELS[pred],'correct':int(pred==g),'Brier':math.fsum((p-int(i==g))**2 for i,p in enumerate(probabilities)),'NLL':-math.log(probabilities[g]),'observed_p_gold':probabilities[g]}
def author_metrics(gold,predictions):
 require(len(gold)==len(predictions)>0,'FULL_AUTHOR_HELPER_DENOMINATOR');out={'accuracy':sum(a==b for a,b in zip(gold,predictions))/len(gold)};undefined={}
 for cls,suffix in [('Entailment','entailment'),('Contradiction','contradiction')]:
  tp=sum(a==b==cls for a,b in zip(gold,predictions));np=sum(p==cls for p in predictions);ng=sum(g==cls for g in gold)
  parts={'precision':tp/np if np else 0.,'recall':tp/ng if ng else None,'f1':2*tp/(np+ng)if ng else None}
  for metric,value in parts.items():
   key=metric+'_'+suffix;out[key]=value
   if value is None:undefined[key]='UNDEFINED_AUTHOR_NAN'
 for metric in ['precision','recall','f1']:
  a,b=out[metric+'_entailment'],out[metric+'_contradiction'];mean=None if a is None or b is None else(a+b)/2;hmean=None if a is None or b is None else(0. if a*b==0 else 2/(1/a+1/b));out[metric+'_mean']=mean;out[metric+'_hmean']=hmean
  if mean is None:undefined[metric+'_mean']=undefined[metric+'_hmean']='UNDEFINED_AUTHOR_NAN'
 return out,undefined

def evaluate_rows(cases,labels):
 require(type(cases)is list and len(cases)==12 and len({r['id']for r in cases})==12,'ALL_TWELVE_CASES_NO_DROP');require(type(labels)is dict and set(labels)=={r['id']for r in cases}and all(type(v)is str and v in LABELS for v in labels.values()),'EXACT_TWELVE_RETAINED_AUTHOR_LABELS');metrics={};per_rows={};support={cls:sum(v==cls for v in labels.values())for cls in LABELS}
 for arm in ARMS:
  scored=[];gold=[];pred=[]
  for case in cases:
   readout=case['forecasts'][arm];require(readout['forecast_id']==case['id']+'::'+arm,'EXACT_FORECAST_ID');p=observed_probabilities(readout['probabilities']);s=row_score(p,labels[case['id']]);require(readout['forecast']==TOKENS[LABELS.index(s['prediction'])],'CANONICAL_OBSERVED_PROBABILITY_ARGMAX');gold.append(labels[case['id']]);pred.append(s['prediction']);scored.append(dict(id=case['id'],document_id=case['document_id'],hypothesis_id=case['hypothesis_id'],**s))
  author,undefined=author_metrics(gold,pred);by_class={cls:{'support':support[cls],'correct':sum(r['correct']for r in scored if labels[r['id']]==cls)}for cls in LABELS};metrics[arm]={'N':12,'correct':sum(r['correct']for r in scored),'accuracy':sum(r['correct']for r in scored)/12,'Brier':math.fsum(r['Brier']for r in scored)/12,'NLL':math.fsum(r['NLL']for r in scored)/12,'NLL_scope':'Unclipped -log(observed positive F32 server class probability); no rawlogit/unrounded-stable NLL claim.','class_results':by_class,'author_helper_metrics':author,'author_undefined_metrics':undefined,'rows':scored};per_rows[arm]=scored
 checks={GATE_NAMES[0]:True,GATE_NAMES[1]:True,GATE_NAMES[2]:all(support[c]>0 for c in LABELS),GATE_NAMES[3]:all(metrics[PRIMARY]['class_results'][c]['correct']>=1 for c in LABELS)}
 for arm in CONTROLS:
  checks[arm+':primary_gain_at_least_two_correct']=metrics[PRIMARY]['correct']>=metrics[arm]['correct']+2;checks[arm+':Brier_nonincrease']=metrics[PRIMARY]['Brier']<=metrics[arm]['Brier']+GATE_EPS;checks[arm+':observed_probability_NLL_nonincrease']=metrics[PRIMARY]['NLL']<=metrics[arm]['NLL']+GATE_EPS
 return {'metrics':metrics,'gate_checks':checks,'dev_passed':all(checks.values()),'descriptive':descriptive(cases,labels,per_rows)}

def descriptive(cases,labels,rows):
 docs=list(dict.fromkeys(r['document_id']for r in cases));hyps=list(dict.fromkeys(r['hypothesis_id']for r in cases));require(len(docs)==4 and len(hyps)==3 and all(sum(c['document_id']==d for c in cases)==3 for d in docs),'FOUR_SHARED_DOCUMENT_CLUSTERS');out={'independent_document_clusters':4,'shared_hypothesis_templates':3,'per_document':{},'per_hypothesis':{},'paired_controls':{},'four_document_bootstrap':{'replicates':BOOTSTRAP_REPLICATES,'seed':BOOTSTRAP_SEED,'unit':'Source document cluster, four with replacement per replicate; three fixed hypotheses stay together.','descriptive_only_not_gate':True,'intervals':{}}}
 for role,key,values in [('per_document','document_id',docs),('per_hypothesis','hypothesis_id',hyps)]:
  for value in values:
   out[role][str(value)]={}
   for arm in ARMS:
    rr=[r for r in rows[arm]if r[key]==value];out[role][str(value)][arm]={'N':len(rr),'correct':sum(r['correct']for r in rr),'Brier':math.fsum(r['Brier']for r in rr)/len(rr),'NLL':math.fsum(r['NLL']for r in rr)/len(rr)}
 rng=random.Random(BOOTSTRAP_SEED);draws=[[rng.randrange(4)for _ in range(4)]for _ in range(BOOTSTRAP_REPLICATES)]
 for arm in CONTROLS:
  pairs=list(zip(rows[PRIMARY],rows[arm]));out['paired_controls'][arm]={'native_only_correct':sum(a['correct']and not b['correct']for a,b in pairs),'control_only_correct':sum(b['correct']and not a['correct']for a,b in pairs),'prediction_disagreements':[a['id']for a,b in pairs if a['prediction']!=b['prediction']]};dist={metric:[]for metric in ['accuracy_gain_native_minus_control','Brier_gain_control_minus_native','NLL_gain_control_minus_native']}
  for selected in draws:
   rr=[(a,b)for i in selected for a,b in pairs if a['document_id']==docs[i]];dist['accuracy_gain_native_minus_control'].append(sum(a['correct']-b['correct']for a,b in rr)/12);dist['Brier_gain_control_minus_native'].append(math.fsum(b['Brier']-a['Brier']for a,b in rr)/12);dist['NLL_gain_control_minus_native'].append(math.fsum(b['NLL']-a['NLL']for a,b in rr)/12)
  out['four_document_bootstrap']['intervals'][arm]={k:interval(v)for k,v in dist.items()}
 return out

def numeric_diagnostic(numerator,denominator):
 require(type(numerator)is int and type(denominator)is int and 0<=numerator<=denominator,'NUMERIC_DIAGNOSTIC_COUNTS');return {'numerator':numerator,'denominator':denominator,'applicable':denominator>0,'fraction':numerator/denominator if denominator else None,'not_a_correctness_or_insufficiency_proof':True}
