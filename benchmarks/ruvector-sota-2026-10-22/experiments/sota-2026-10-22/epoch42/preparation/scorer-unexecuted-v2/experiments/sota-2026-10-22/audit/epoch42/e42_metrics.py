"""Independent fixed two-window mixture and author-helper pilot metrology."""
import math
ARMS=['tasksource_native_two_windows','tasksource_lexical_two_windows','tasksource_source_order_two_windows'];PRIMARY=ARMS[0];CONTROLS=ARMS[1:];LABELS=['NotMentioned','Entailment','Contradiction'];MAP=[1,0,2];TOL=1e-12

def require(v,msg):
 if not v:raise ValueError(msg)
def finite(v):return type(v)in[int,float]and math.isfinite(v)
def forecast(logits):
 require(type(logits)is list and len(logits)==3 and all(finite(v)and abs(v)<=3.4028234663852886e38 for v in logits),'ACTUAL_FINITE_FP32_THREEWAY_LOGITS');peak=max(logits);s=[float(x)-peak for x in logits];z=math.log(math.fsum(math.exp(x)for x in s));nlp=[x-z for x in s];np=[math.exp(x)for x in nlp];lp=[nlp[i]for i in MAP];p=[np[i]for i in MAP];winner=max(range(3),key=lambda i:logits[MAP[i]]);return {'native_probabilities':np,'probabilities_N_E_C':p,'log_probabilities_N_E_C':lp,'canonical_argmax_index':winner,'primary_label':LABELS[winner]}
def mixture(two):
 require(type(two)is list and len(two)==2,'EXACT_TWO_ACTUAL_WINDOWS');lp=[]
 for i in range(3):
  x,y=[v['log_probabilities_N_E_C'][i]for v in two];require(finite(x)and finite(y),'FINITE_WINDOW_LOG_PROBABILITIES');m=max(x,y);lp.append(m+math.log(math.exp(x-m)+math.exp(y-m))-math.log(2))
 p=[math.exp(x)for x in lp];require(abs(math.fsum(p)-1)<=TOL,'NORMALIZED_TWO_WINDOW_MIXTURE');winner=max(range(3),key=lambda i:lp[i]);return {'probabilities_N_E_C':p,'log_probabilities_N_E_C':lp,'canonical_argmax_index':winner,'primary_label':LABELS[winner]}
def vector(got,want):return type(got)is list and len(got)==len(want)and all(finite(a)and abs(a-b)<=TOL for a,b in zip(got,want))
def check_case_arm(row,arm):
 physical=row['window_readouts'][arm];require(type(physical)is list and len(physical)==2,'TWO_PHYSICAL_WINDOWS_PER_ARM');values=[];refs=[]
 for i,r in enumerate(physical):
  rid=row['id']+'::'+arm+'::window:'+str(i);require(r['readout_id']==rid and r['model_tag']=='tasksource','EXACT_WINDOW_READOUT_ID_PROFILE');v=forecast(r['raw_native_logits']);require(vector(r['raw_native_probabilities'],v['native_probabilities'])and vector(r['probabilities_N_E_C'],v['probabilities_N_E_C'])and vector(r['log_probabilities_N_E_C'],v['log_probabilities_N_E_C']),'RAW_SOURCE_LOGIT_READOUT_REPLAY');require(type(r['canonical_argmax_index'])is int and r['canonical_argmax_index']==v['canonical_argmax_index']and r['primary_label']==v['primary_label']and r['argmax_label']==v['primary_label'],'WINDOW_CANONICAL_ARGMAX_REPLAY');values.append(v);refs.append(rid)
 want=mixture(values);r=row['readouts'][arm];require(r['model_tag']=='tasksource'and r['aggregation']=='EQUAL_WEIGHT_ARITHMETIC_PROBABILITY_MIXTURE_TWO_REAL_WINDOWS'and type(r['real_window_outputs_required'])is int and r['real_window_outputs_required']==2 and r['retrieval_miss_absence_inference']is False,'EXACT_FIXED_MIXTURE_NO_ABSENCE_OVERRIDE');require(r['forecast_id']==row['id']+'::'+arm and r['window_readout_ids']==refs,'EXACT_DERIVED_FORECAST_REFERENCES')
 for k in ['probabilities_N_E_C','log_probabilities_N_E_C']:require(vector(r[k],want[k]),'FIXED_TWO_WINDOW_MIXTURE_REPLAY')
 for k in ['canonical_argmax_index','primary_label']:require(type(r[k])is type(want[k])and r[k]==want[k],'CANONICAL_FIRST_MIXTURE_ARGMAX')
 return want,refs

def author(conf):
 n=sum(sum(r.values())for r in conf.values());require(n>0,'NONEMPTY_DENOMINATOR');v={'accuracy':sum(conf[x][x]for x in LABELS)/n};undefined={};support={}
 for label in LABELS[1:]:
  gold=sum(conf[label].values());pred=sum(conf[x][label]for x in LABELS);tp=conf[label][label];name=label.lower();support[label]={'support':gold,'predicted':pred,'TP':tp};parts={'precision':tp/pred if pred else 0.,'recall':tp/gold if gold else None,'f1':2*tp/(gold+pred)if gold else None}
  for key,value in parts.items():
   k=key+'_'+name;v[k]=value
   if value is None:undefined[k]={'status':'UNDEFINED_AUTHOR_NAN','reason':'No gold support for '+label}
 for key in ['precision','recall','f1']:
  x,y=v[key+'_entailment'],v[key+'_contradiction'];mean=None if x is None or y is None else(x+y)/2;harm=None if x is None or y is None else 0. if x==0 or y==0 else 2*x*y/(x+y)
  for tag,value in [('mean',mean),('hmean',harm)]:
   k=key+'_'+tag;v[k]=value
   if value is None:undefined[k]={'status':'UNDEFINED_AUTHOR_NAN','reason':'An author E/C component is undefined; no fill/drop.'}
 return v,undefined,support

def metrics(rows,arm,labels,expected_N=12):
 require(arm in ARMS and len(rows)==len({r['id']for r in rows})==expected_N and set(labels)=={r['id']for r in rows},'FULL_FIXED_DENOMINATOR');conf={g:{p:0 for p in LABELS}for g in LABELS};scores=[]
 for row in rows:
  gold=labels[row['id']];require(type(gold)is str and gold in LABELS,'EXACT_AUTHOR_RAW_CHOICE_NO_REMAP');v,refs=check_case_arm(row,arm);p=v['probabilities_N_E_C'];lp=v['log_probabilities_N_E_C'];i=LABELS.index(gold);pred=v['primary_label'];conf[gold][pred]+=1;scores.append({'id':row['id'],'document_id':row['document_id'],'hypothesis_id':row['hypothesis_id'],'gold':gold,'prediction':pred,'correct':int(gold==pred),'window_readout_ids':refs,'probabilities_N_E_C':p,'stable_log_probabilities_N_E_C':lp,'p_gold':p[i],'Brier':math.fsum((x-int(j==i))**2 for j,x in enumerate(p)),'NLL':-lp[i],'NLL_clipped_1e_12_diagnostic':-math.log(max(p[i],1e-12)),'display_probability_underflow':p[i]==0,'diagnostic_clipped':p[i]<1e-12})
 a,u,s=author(conf);return {'N':expected_N,'correct':sum(r['correct']for r in scores),'accuracy':a['accuracy'],'Brier':math.fsum(r['Brier']for r in scores)/expected_N,'NLL':math.fsum(r['NLL']for r in scores)/expected_N,'author_helper_metrics':a,'author_undefined_metrics':u,'author_EC_F1_mean':a['f1_mean'],'author_EC_F1_hmean':a['f1_hmean'],'E_C_support':s,'confusion':conf,'scores':scores,'NLL_clipped_1e_12_diagnostic':math.fsum(r['NLL_clipped_1e_12_diagnostic']for r in scores)/expected_N,'display_probability_underflow_count':sum(r['display_probability_underflow']for r in scores),'diagnostic_clip_count':sum(r['diagnostic_clipped']for r in scores)}
def gate_names():return ['integrity_complete_no_errors','all_three_full_N12']+[c+':'+g for c in CONTROLS for g in ['primary_gain_at_least_two_correct','Brier_nonincrease','stable_unclipped_NLL_nonincrease']]
def gates(all_metrics,integrity):
 require(set(all_metrics)==set(ARMS),'THREE_FIXED_MATCHED_ARMS');p=all_metrics[PRIMARY];out={'integrity_complete_no_errors':integrity is True,'all_three_full_N12':all(v['N']==12 for v in all_metrics.values())}
 for c in CONTROLS:
  v=all_metrics[c];out[c+':primary_gain_at_least_two_correct']=p['correct']>=v['correct']+2;out[c+':Brier_nonincrease']=p['Brier']<=v['Brier']+TOL;out[c+':stable_unclipped_NLL_nonincrease']=p['NLL']<=v['NLL']+TOL
 return out

def descriptive(rows,labels):
 docs=list(dict.fromkeys(r['document_id']for r in rows));hyps=list(dict.fromkeys(r['hypothesis_id']for r in rows));require(len(docs)==4 and len(hyps)==3,'FOUR_DOCUMENT_THREE_HYPOTHESIS_CLUSTER_SCOPE');by_doc={};by_hyp={};paired={}
 for k,ids,out,n in [('document_id',docs,by_doc,3),('hypothesis_id',hyps,by_hyp,4)]:
  for key in ids:
   selected=[r for r in rows if r[k]==key];out[str(key)]={a:metrics(selected,a,{r['id']:labels[r['id']]for r in selected},n)for a in ARMS}
 macro={a:{k:math.fsum(by_doc[str(d)][a][k]for d in docs)/4 for k in ['accuracy','Brier','NLL']}for a in ARMS}
 for a in CONTROLS:
  pairs=[]
  for r in rows:
   n,_=check_case_arm(r,PRIMARY);c,_=check_case_arm(r,a);gold=labels[r['id']];pairs.append({'id':r['id'],'native_prediction':n['primary_label'],'control_prediction':c['primary_label'],'gold':gold,'disagree':n['primary_label']!=c['primary_label'],'native_correct':n['primary_label']==gold,'control_correct':c['primary_label']==gold})
  paired[a]={'N':12,'native_only_correct':sum(r['native_correct']and not r['control_correct']for r in pairs),'control_only_correct':sum(r['control_correct']and not r['native_correct']for r in pairs),'disagreements':sum(r['disagree']for r in pairs),'pairs':pairs}
 return {'per_hypothesis':by_hyp,'per_document':by_doc,'macro_document':macro,'paired_control_disagreements':paired,'uncertainty_scope':'Only4documentclusters,3sharedhypotheses. DescriptiveDEV outcomes, no12independentdocument/CONF/publisher inference. AuthorundefinedF1 retainednull and not an E42 gate.'}
def quantile(v,q):
 require(v and all(finite(x)and x>=0 for x in v),'ACTUAL_FINITE_LATENCIES');a=sorted(v);x=(len(a)-1)*q;i=int(x);return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(x-i)
