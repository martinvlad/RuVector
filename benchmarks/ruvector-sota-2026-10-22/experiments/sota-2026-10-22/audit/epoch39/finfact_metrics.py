"""Independent official Fin-Fact decision/metrics and extra proper diagnostics."""
import math
ARMS=['b354_source_order','b354_native','b354_lexical','xxlarge_source_order'];PRIMARY='b354_native';REFERENCE='xxlarge_source_order';CONTROLS=['b354_source_order','b354_lexical','xxlarge_source_order'];LABELS=['true','false','neutral'];MAPS={'b354':[0,2,1],'xxlarge':[2,0,1]};NATIVE_LABELS={'b354':['true','neutral','false'],'xxlarge':['false','neutral','true']};TOL=1e-12

def require(v,message):
 if not v:raise ValueError(message)
def finite(x):return type(x)in(int,float)and math.isfinite(x)
def source_forecast(logits,tag):
 require(tag in MAPS and type(logits)is list and len(logits)==3 and all(finite(x)and abs(x)<=3.4028234663852886e38 for x in logits),'FINITE_FP32_RANGE_SOURCE_LOGITS_REQUIRED');peak=max(logits);shift=[float(x)-peak for x in logits];mass=[math.exp(x)for x in shift];z=math.fsum(mass);logz=math.log(z);lp=[x-logz for x in shift];p=[math.exp(x)for x in lp];mapping=MAPS[tag];canonical_p=[p[i]for i in mapping];canonical_lp=[lp[i]for i in mapping];winner=max(range(3),key=lambda i:logits[i])
 return {'native_probabilities':p,'probabilities':canonical_p,'log_probabilities':canonical_lp,'native_argmax_index':winner,'argmax_label':NATIVE_LABELS[tag][winner],'primary_label':ordered_label(canonical_p)}
def ordered_label(p):
 require(type(p)is list and len(p)==3 and all(finite(v)and 0<=v<=1 for v in p)and abs(math.fsum(p)-1)<=TOL,'COMPLETE_E_C_N_T1_REQUIRED')
 return 'true'if p[0]>.5 else'neutral'if p[2]>.5 else'false'
def readout_check(readout,caseid,arm):
 tag='xxlarge'if arm=='xxlarge_source_order'else'b354';require(arm in ARMS and readout['readout_id']==caseid+'::'+arm and readout['model_tag']==tag,'ACTUAL_READOUT_ID_PROFILE_MISMATCH');f=source_forecast(readout['raw_native_logits'],tag)
 for key,want in [('raw_native_probabilities',f['native_probabilities']),('probabilities_E_C_N',f['probabilities']),('log_probabilities_E_C_N',f['log_probabilities'])]:
  got=readout[key];require(type(got)is list and len(got)==3 and all(finite(x)and abs(x-y)<=TOL for x,y in zip(got,want)),'SOURCE_LOGIT_FORECAST_REPLAY_MISMATCH:'+key)
 for key in ['primary_label','argmax_label','native_argmax_index']:require(type(readout[key])is type(f[key])and readout[key]==f[key],'OFFICIAL_ORDERED_DECISION_OR_DIAGNOSTIC_ARGMAX_MISMATCH:'+key)
 return f

def metrics(rows,arm,labels):
 require(len(rows)==12 and len({r['id']for r in rows})==12 and set(labels)=={r['id']for r in rows},'FULL_FIXED_TWELVE_REQUIRED');conf={a:{b:0 for b in LABELS}for a in LABELS};scores=[];observed=set();fixed={l:{'support':0,'predicted':0,'TP':0}for l in LABELS}
 for row in rows:
  gold=labels[row['id']];require(gold in LABELS,'UNSUPPORTED_OFFICIAL_LABEL_NO_REMAP');r=row['readouts'][arm];f=readout_check(r,row['id'],arm);prediction=f['primary_label'];p=f['probabilities'];lp=f['log_probabilities'];i=LABELS.index(gold);pg=p[i];conf[gold][prediction]+=1;fixed[gold]['support']+=1;fixed[prediction]['predicted']+=1;fixed[gold]['TP']+=int(gold==prediction);observed.update([gold,prediction]);scores.append({'id':row['id'],'gold':gold,'prediction':prediction,'argmax_diagnostic_prediction':f['argmax_label'],'correct':int(gold==prediction),'argmax_diagnostic_correct':int(gold==f['argmax_label']),'probabilities_E_C_N':p,'stable_log_probabilities_E_C_N':lp,'p_gold':pg,'Brier':math.fsum((x-int(j==i))**2 for j,x in enumerate(p)),'NLL':-lp[i],'NLL_clipped_1e_12_diagnostic':-math.log(max(pg,1e-12)),'display_underflow':pg==0,'clipped_diagnostic':pg<1e-12})
 per={}
 for l,v in fixed.items():
  tp=v['TP'];pr=tp/v['predicted']if v['predicted']else 0;re=tp/v['support']if v['support']else 0;f1=2*tp/(v['support']+v['predicted'])if v['support']+v['predicted']else 0;per[l]={**v,'precision':pr,'recall':re,'F1':f1}
 observed=sorted(observed)
 return {'N':12,'correct':sum(s['correct']for s in scores),'accuracy':sum(s['correct']for s in scores)/12,'official_observed_union_labels':observed,'macro_precision':math.fsum(per[l]['precision']for l in observed)/len(observed),'macro_recall':math.fsum(per[l]['recall']for l in observed)/len(observed),'macro_F1':math.fsum(per[l]['F1']for l in observed)/len(observed),'fixed_three_class_macro_F1_diagnostic':math.fsum(per[l]['F1']for l in LABELS)/3,'by_class':per,'confusion':conf,'Brier':math.fsum(s['Brier']for s in scores)/12,'NLL':math.fsum(s['NLL']for s in scores)/12,'NLL_clipped_1e_12_diagnostic':math.fsum(s['NLL_clipped_1e_12_diagnostic']for s in scores)/12,'display_probability_underflow_count':sum(s['display_underflow']for s in scores),'diagnostic_clip_count':sum(s['clipped_diagnostic']for s in scores),'argmax_diagnostic_correct':sum(s['argmax_diagnostic_correct']for s in scores),'scores':scores,'macro_scope':'Official sklearn average=macro, labels=None, over observed gold/prediction union; undefined zero divisions contribute0. Fixedthree result is distinct diagnostic. No invalid/missing prediction drop is allowed.'}
def gates(results,integrity=True):
 require(set(results)==set(ARMS),'FOUR_REAL_ARMS_REQUIRED');p=results[PRIMARY];r=results[REFERENCE];checks={'integrity_complete_no_errors':bool(integrity),'all_four_full_N12':all(x['N']==12 for x in results.values()),'primary_gain_at_least_two_correct_vs_XXL':p['correct']>=r['correct']+2}
 for c in CONTROLS:
  checks[c+':accuracy_nondecrease']=p['accuracy']+TOL>=results[c]['accuracy'];checks[c+':official_macroF1_nondecrease']=p['macro_F1']+TOL>=results[c]['macro_F1'];checks[c+':Brier_nonincrease']=p['Brier']<=results[c]['Brier']+TOL;checks[c+':stable_unclipped_NLL_nonincrease']=p['NLL']<=results[c]['NLL']+TOL
 return checks

def quantile(v,q):
 require(v and all(finite(x)and x>=0 for x in v),'ACTUAL_FINITE_TIMINGS_REQUIRED');a=sorted(v);x=(len(a)-1)*q;i=int(x);j=min(i+1,len(a)-1);return a[i]+(a[j]-a[i])*(x-i)
