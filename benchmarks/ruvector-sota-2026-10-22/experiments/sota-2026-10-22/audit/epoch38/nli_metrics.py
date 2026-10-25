"""Independent source-order rawT1/derived forecast metrics; stdlib only."""
import math,re,struct
from data_common import require,finite,CLASSES,CANONICAL_LABELS,GOLD_NAMES,NATIVE_LABELS
ARMS=['full_raw','native_raw','native_verified','lexical_verified','full_verified']
CONTEXTS=['full_source','native_coverage','lexical_coverage']
REUSE={'full_raw':'full_source','full_verified':'full_source','native_raw':'native_coverage','native_verified':'native_coverage','lexical_verified':'lexical_coverage'}
PRIMARY='native_verified'
GATE_CONTROLS=['full_raw','native_raw','lexical_verified','full_verified']
MODEL={'repository':'microsoft/deberta-v2-xxlarge-mnli','revision':'8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06','weights_sha256':'5b2d8ddf6c80e4e6105b27cdb9fa346a8ba1f0c0dfd410b0007be894567cb4db','weights_bytes':3133958098}
PROFILES={'xxlarge':{'bytes':MODEL['weights_bytes'],'sha':MODEL['weights_sha256'],'order':NATIVE_LABELS,'canonical':[2,0,1]}}
EPS=1e-12
def log_softmax_source(logits):
 require(type(logits)is list and len(logits)==3 and all(finite(x)and abs(x)<=3.4028234663852886e38 for x in logits),'Three finite FP32-range source logits required')
 m=max(logits);shifted=[float(x)-m for x in logits];logz=math.log(math.fsum(math.exp(x)for x in shifted));native=[x-logz for x in shifted]
 return [native[2],native[0],native[1]]
def permuted_logp(raw_logp,provided_native_label,certified_label):
 require(type(raw_logp)is list and len(raw_logp)==3 and all(finite(x)and x<=0 for x in raw_logp),'Complete finite stable canonical log probabilities required')
 out=list(raw_logp)
 if certified_label is not None:
  require(provided_native_label in CANONICAL_LABELS and certified_label in CANONICAL_LABELS,'Typed permutation labels required');i=CANONICAL_LABELS.index(provided_native_label);j=CANONICAL_LABELS.index(certified_label);out[i],out[j]=out[j],out[i]
 return out
def distribution(p):
 require(type(p)is list and len(p)==3 and all(finite(x)and 0<=x<=1 for x in p)and abs(math.fsum(p)-1)<=EPS,'Three complete finite canonical probabilities required');return p
def reader_check(r,premise,hypothesis,pair_tokens):
 require(isinstance(r,dict)and r.get('model_tag')=='xxlarge','Single original XXL profile required')
 logits=r['raw_logits'];require(type(logits)is list and len(logits)==3 and all(finite(x)for x in logits)and logits==r['raw_logits_C_N_E'],'Three finite source C,N,E logits required')
 require(r['native_label_order']==NATIVE_LABELS and r['canonical_E_C_N_from_raw']==[2,0,1],'Source label order changed')
 require(r['actual_logits_shape']==[1,3]and r['actual_logits_dtype']=='torch.float32'and r['actual_logits_device']=='cpu','Original CPU FP32 head output required')
 lp=log_softmax_source(logits);e=[math.exp(x-max(logits))for x in logits];z=math.fsum(e);native=[x/z for x in e];p=distribution(r['probabilities_E_C_N']);replayed=[native[2],native[0],native[1]]
 require(all(abs(a-b)<=EPS for a,b in zip(p,replayed)),'Canonical rawT1 softmax replay differs')
 require(type(r['probabilities_native_order'])is list and len(r['probabilities_native_order'])==3 and r['probabilities_native_order']==r['probabilities_C_N_E']and all(finite(x)and abs(x-native[i])<=EPS for i,x in enumerate(r['probabilities_native_order'])),'Source-order rawT1 forecast differs')
 winner=max(range(3),key=lambda i:logits[i]);label=NATIVE_LABELS[winner]
 require(type(r['native_label_index'])is int and r['native_label_index']==winner and r['native_typed_argmax']==label,'Provided original raw-logit winner/tie differs')
 require(r['temperature']==1.0 and r['calibrated']is False and r['semantic_decision_override']is False,'Raw readout was calibrated or overridden')
 for key,want in [('model_weights_sha256',MODEL['weights_sha256']),('model_repository',MODEL['repository']),('model_revision',MODEL['revision'])]:require(r[key]==want,'Original reader source identity changed')
 require(type(pair_tokens)is int and 0<pair_tokens<=512 and r['pair_tokens']==r['full_pair_tokens']==pair_tokens and r['max_pair_tokens']==512 and r['hidden_truncation']is False,'True complete pair cap/truncation changed')
 from hashlib import sha256
 require(r['premise_sha256']==sha256(premise.encode()).hexdigest()and r['hypothesis_sha256']==sha256(hypothesis.encode()).hexdigest(),'Literal model pair changed')
 require(type(r['native_pair_input_ids_sha256'])is str and re.fullmatch('[0-9a-f]{64}',r['native_pair_input_ids_sha256']),'Actual tokenizer input identity absent')
 require(all(finite(r[k])and r[k]>=0 for k in ['forward_seconds','reader_seconds'])and r['reader_seconds']+1e-9>=r['forward_seconds'],'Actual timing invalid')
 return {'probabilities':dict(zip(CLASSES,p)),'prediction':GOLD_NAMES[label],'native_label':label,'native_label_index':winner,'raw_logits':list(logits),'canonical':list(p),'log_probabilities':dict(zip(CLASSES,lp)),'canonical_log_probabilities':lp}
def transposed(raw,provided_native_label,certified_label):
 p=list(distribution(raw));require(provided_native_label in NATIVE_LABELS,'Original provided source winner required')
 if certified_label is None:return p,provided_native_label
 require(certified_label in CANONICAL_LABELS,'Unknown certificate class')
 old=CANONICAL_LABELS.index(provided_native_label);new=CANONICAL_LABELS.index(certified_label)
 p[old],p[new]=p[new],p[old]
 require(p[new]==max(p),'Certificate target is not a final maximum')
 return p,certified_label
def metrics(rows,arm):
 counts={c:{'n':0,'correct':0}for c in CLASSES};confusion={c:{p:0 for p in CLASSES}for c in CLASSES};out=[]
 for row in rows:
  gold=row['gold'];require(gold in CLASSES,'Unknown retained authored label');r=row['readers'][arm];p=r['probabilities'];lp=r['log_probabilities'];pred=r['prediction']
  require(set(p)==set(CLASSES)and pred in CLASSES and all(finite(v)and 0<=v<=1 for v in p.values())and abs(math.fsum(p.values())-1)<=EPS,'Invalid complete forecast')
  require(set(lp)==set(CLASSES)and all(finite(v)and v<=0 for v in lp.values()),'Unclipped stable complete log probabilities required')
  require(all(abs(math.exp(lp[c])-p[c])<=EPS for c in CLASSES),'Displayed probability and stable log probability differ')
  correct=int(pred==gold);counts[gold]['n']+=1;counts[gold]['correct']+=correct;confusion[gold][pred]+=1;pg=p[gold]
  out.append({'id':row['id'],'document_id':row['document_id'],'gold':gold,'prediction':pred,'correct':correct,'Brier':math.fsum((p[c]-int(c==gold))**2 for c in CLASSES),'NLL':-lp[gold],'p_gold':pg,'NLL_clipped_1e-12':-math.log(max(pg,1e-12)),'NLL_clipped':pg<1e-12,'unclipped_NLL_finite':math.isfinite(-lp[gold]),'display_probability_underflow':pg==0,'probabilities':p})
 require(len(out)==12,'Twelve retained authored cases required')
 return {'n':12,'correct':sum(r['correct']for r in out),'accuracy':sum(r['correct']for r in out)/12,'Brier':math.fsum(r['Brier']for r in out)/12,'NLL':math.fsum(r['NLL']for r in out)/12,'display_probability_underflow_count':sum(r['display_probability_underflow']for r in out),'NLL_clipped_1e-12':math.fsum(r['NLL_clipped_1e-12']for r in out)/12,'NLL_clip_count':sum(r['NLL_clipped']for r in out),'unclipped_NLL_finite':all(r['unclipped_NLL_finite']for r in out),'by_class':counts,'confusion':confusion,'scores':out}
def engineering_gates(results):
 require(set(results)==set(ARMS),'All five arms required');p=results[PRIMARY]
 checks={'primary_all12_correct':p['correct']==12,'authored_class_balance4each':all(p['by_class'][c]['n']==4 for c in CLASSES),'primary_all4_per_class_correct':all(p['by_class'][c]['correct']==4 for c in CLASSES),'accuracy_gain_at_least2_vs_full_raw':p['correct']-results['full_raw']['correct']>=2,'prospective_full_raw_ceiling':results['full_raw']['correct']<=10}
 for c in GATE_CONTROLS:
  checks[c+':Brier_nonincrease']=p['Brier']<=results[c]['Brier']+1e-12;checks[c+':NLL_nonincrease']=p['NLL']<=results[c]['NLL']+1e-12
 return checks
def paired_differences(results):
 p=results[PRIMARY];out={}
 for a in ARMS:
  if a==PRIMARY:continue
  b=results[a];pairs=[]
  for x,y in zip(p['scores'],b['scores']):
   require((x['id'],x['document_id'],x['gold'])==(y['id'],y['document_id'],y['gold']),'Unmatched source case')
   pairs.append({'id':x['id'],'document_id':x['document_id'],'primary_minus_correct':x['correct']-y['correct'],'primary_minus_Brier':x['Brier']-y['Brier'],'primary_minus_NLL':x['NLL']-y['NLL']})
  require(len(pairs)==12,'Twelve source clusters required')
  out[a]={'primary_minus_correct':p['correct']-b['correct'],'primary_minus_accuracy':p['accuracy']-b['accuracy'],'primary_minus_Brier':p['Brier']-b['Brier'],'primary_minus_NLL':p['NLL']-b['NLL'],'authored_source_clusters':12,'authored_case_differences':pairs,'uncertainty':'Restricted authored formal-source engineering, not representative benchmark accuracy or generalization. Native/lexical null results establish no causal ranking benefit. Fixed serial order and reused readouts are explicit.'}
 return out
