"""Independent author-helper metrics; all12 three-class cases, no binary drop.

This is a declared helper-based pilot adaptation, not full evaluate_all/paper
reproduction. Official E/C undefined means remain null+UNDEFINED_AUTHOR_NAN.
"""
import math
ARMS=['tasksource_source_order','tasksource_native','tasksource_lexical','b354_source_order']
PRIMARY='tasksource_native';REFERENCE='b354_source_order'
CONTROLS=['tasksource_source_order','tasksource_lexical','b354_source_order']
LABELS=['NotMentioned','Entailment','Contradiction']
MAPS={'tasksource':[1,0,2],'b354':[1,0,2]};TOL=1e-12

def require(v,message):
 if not v:raise ValueError(message)
def finite(x):return type(x)in(int,float)and math.isfinite(x)
def source_forecast(logits,tag):
 require(tag in MAPS and type(logits)is list and len(logits)==3 and all(finite(x)and abs(x)<=3.4028234663852886e38 for x in logits),'FINITE_FP32_SOURCE_LOGITS_REQUIRED');peak=max(logits);shift=[float(x)-peak for x in logits];z=math.log(math.fsum(math.exp(x)for x in shift));native_lp=[x-z for x in shift];native_p=[math.exp(x)for x in native_lp];p=[native_p[i]for i in MAPS[tag]];lp=[native_lp[i]for i in MAPS[tag]];canonical_logits=[logits[i]for i in MAPS[tag]];winner=max(range(3),key=lambda i:canonical_logits[i])
 return {'native_probabilities':native_p,'probabilities':p,'log_probabilities':lp,'canonical_argmax_index':winner,'primary_label':LABELS[winner]}
def readout_check(readout,caseid,arm):
 tag='b354'if arm==REFERENCE else'tasksource';require(arm in ARMS and readout['readout_id']==caseid+'::'+arm and readout['model_tag']==tag,'ACTUAL_READOUT_ID_PROFILE_MISMATCH');f=source_forecast(readout['raw_native_logits'],tag)
 for key,want in [('raw_native_probabilities',f['native_probabilities']),('probabilities_N_E_C',f['probabilities']),('log_probabilities_N_E_C',f['log_probabilities'])]:
  got=readout[key];require(type(got)is list and len(got)==3 and all(finite(x)and abs(x-y)<=TOL for x,y in zip(got,want)),'SOURCE_LOGIT_FORECAST_REPLAY_MISMATCH:'+key)
 for key in ['primary_label','canonical_argmax_index']:require(type(readout[key])is type(f[key])and readout[key]==f[key],'AUTHOR_CANONICAL_ARGMAX_MISMATCH:'+key)
 return f

def author_classification_metrics(conf):
 n=sum(sum(r.values())for r in conf.values());require(n>0,'NONEMPTY_FULL_DENOMINATOR');m={'accuracy':sum(conf[l][l]for l in LABELS)/n};undefined={};by_class={}
 for label in ['Entailment','Contradiction']:
  key=label.lower();support=sum(conf[label].values());predicted=sum(conf[g][label]for g in LABELS);tp=conf[label][label];precision=tp/predicted if predicted else 0.;recall=tp/support if support else None;f1=2*tp/(support+predicted)if support else None;by_class[label]={'support':support,'predicted':predicted,'TP':tp}
  for name,value in [('precision',precision),('recall',recall),('f1',f1)]:
   field=name+'_'+key;m[field]=value
   if value is None:undefined[field]={'status':'UNDEFINED_AUTHOR_NAN','reason':'No gold support for '+label+'; author explicitly returns NaN for recall/F1.'}
 for name in ['precision','recall','f1']:
  a,b=m[name+'_entailment'],m[name+'_contradiction'];mean=None if a is None or b is None else(a+b)/2;hmean=None if a is None or b is None else 0. if a==0 or b==0 else 2*a*b/(a+b)
  for suffix,value in [('mean',mean),('hmean',hmean)]:
   key=name+'_'+suffix;m[key]=value
   if value is None:undefined[key]={'status':'UNDEFINED_AUTHOR_NAN','reason':'An author E/C component is undefined; no zero imputation or omission.'}
 return m,undefined,by_class

def metrics(rows,arm,labels):
 require(len(rows)==12 and len({r['id']for r in rows})==12 and set(labels)=={r['id']for r in rows},'ALL_FIXED_TWELVE_CASES_REQUIRED');conf={a:{b:0 for b in LABELS}for a in LABELS};scores=[]
 for row in rows:
  gold=labels[row['id']];require(type(gold)is str and gold in LABELS,'UNSUPPORTED_OFFICIAL_RAW_CHOICE_NO_REMAP');f=readout_check(row['readouts'][arm],row['id'],arm);pred=f['primary_label'];p=f['probabilities'];lp=f['log_probabilities'];i=LABELS.index(gold);pg=p[i];conf[gold][pred]+=1;scores.append({'id':row['id'],'gold':gold,'prediction':pred,'correct':int(gold==pred),'probabilities_N_E_C':p,'stable_log_probabilities_N_E_C':lp,'p_gold':pg,'Brier':math.fsum((x-int(j==i))**2 for j,x in enumerate(p)),'NLL':-lp[i],'NLL_clipped_1e_12_diagnostic':-math.log(max(pg,1e-12)),'display_underflow':pg==0,'clipped_diagnostic':pg<1e-12})
 author,undefined,by_class=author_classification_metrics(conf)
 return {'N':12,'correct':sum(s['correct']for s in scores),'accuracy':author['accuracy'],'author_helper_metrics':author,'author_undefined_metrics':undefined,'author_EC_F1_mean':author['f1_mean'],'author_EC_F1_hmean':author['f1_hmean'],'E_C_support':by_class,'confusion':conf,'Brier':math.fsum(s['Brier']for s in scores)/12,'NLL':math.fsum(s['NLL']for s in scores)/12,'NLL_clipped_1e_12_diagnostic':math.fsum(s['NLL_clipped_1e_12_diagnostic']for s in scores)/12,'display_probability_underflow_count':sum(s['display_underflow']for s in scores),'diagnostic_clip_count':sum(s['clipped_diagnostic']for s in scores),'scores':scores,'scope':'All12 unfiltered three-class evaluate_class helper formulas. Full evaluate_all classification entrypoint has binary-filtered diagnostics; no full-entrypoint/paper reproduction claim.'}

def gate_names():
 out=['integrity_complete_no_errors','all_four_full_N12','primary_gain_at_least_two_correct_vs_b354']
 for c in CONTROLS:
  out += [c+':accuracy_nondecrease',c+':author_EC_F1_mean_defined_nondecrease',c+':Brier_nonincrease',c+':stable_unclipped_NLL_nonincrease']
 return out
def gates(results,integrity=True):
 require(set(results)==set(ARMS),'FOUR_REAL_ARMS_REQUIRED');p=results[PRIMARY];r=results[REFERENCE];checks={'integrity_complete_no_errors':bool(integrity),'all_four_full_N12':all(x['N']==12 for x in results.values()),'primary_gain_at_least_two_correct_vs_b354':p['correct']>=r['correct']+2}
 for c in CONTROLS:
  checks[c+':accuracy_nondecrease']=p['accuracy']+TOL>=results[c]['accuracy'];a=p['author_EC_F1_mean'];b=results[c]['author_EC_F1_mean'];checks[c+':author_EC_F1_mean_defined_nondecrease']=a is not None and b is not None and a+TOL>=b;checks[c+':Brier_nonincrease']=p['Brier']<=results[c]['Brier']+TOL;checks[c+':stable_unclipped_NLL_nonincrease']=p['NLL']<=results[c]['NLL']+TOL
 return checks

def quantile(values,q):
 require(values and all(finite(x)and x>=0 for x in values),'FINITE_ACTUAL_TIMINGS_REQUIRED');a=sorted(values);x=(len(a)-1)*q;i=int(x);j=min(i+1,len(a)-1);return a[i]+(a[j]-a[i])*(x-i)
