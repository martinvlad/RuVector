"""Independent six-arm source-order NLI replay; standard library only."""
import hashlib,math,re
from data_common import require,finite,CLASSES
ARMS=['xxlarge_full_source','xxlarge_native_two','xxlarge_lexical_two','xxlarge_positional_two','b354_full_source','b354_native_two']
PRIMARY='xxlarge_full_source'
GATE_CONTROLS=['b354_full_source','xxlarge_native_two','xxlarge_lexical_two','xxlarge_positional_two']
PROFILES={
 'b354':{'order':['Entailment','NotMentioned','Contradiction'],'canonical':[0,2,1],
 'sha':'c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b',
 'bytes':870182606,'logit_alias':'raw_logits_E_N_C','probability_alias':'probabilities_E_N_C',
 'repository':'MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli','revision':'b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7'},
 'xxlarge':{'order':['Contradiction','NotMentioned','Entailment'],'canonical':[2,0,1],
 'sha':'5b2d8ddf6c80e4e6105b27cdb9fa346a8ba1f0c0dfd410b0007be894567cb4db',
 'bytes':3133958098,'logit_alias':'raw_logits_C_N_E','probability_alias':'probabilities_C_N_E',
 'repository':'microsoft/deberta-v2-xxlarge-mnli','revision':'8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06'}}
CANON={'Entailment':'entailment','Contradiction':'contradiction','NotMentioned':'not_mentioned'}
EPS=1e-6
FLOOR=1e-12
def model_for_arm(arm):
 require(arm in ARMS,'Unknown frozen arm')
 return 'b354'if arm.startswith('b354_')else'xxlarge'
def reader_check(r,premise,hypothesis,pair_tokens,model_tag):
 require(type(r)is dict and model_tag in PROFILES and r['model_tag']==model_tag,'Wrong/missing model profile')
 spec=PROFILES[model_tag];logits=r['raw_logits'];p=r['probabilities_E_C_N']
 require(r['native_label_order']==spec['order']and r['canonical_E_C_N_from_raw']==spec['canonical'],'Source-derived label order changed')
 require(logits==r[spec['logit_alias']]and type(logits)is list and len(logits)==3 and all(finite(v)for v in logits),'Three finite source-order logits required')
 require(r['actual_logits_shape']==[1,3]and r['actual_logits_dtype']=='torch.float32'
  and r['actual_logits_device']=='cpu','Original CPU FP32 pretrained head output changed')
 require(type(p)is list and len(p)==3 and all(finite(v)and 0<=v<=1 for v in p),'Complete canonical probabilities required')
 shifted=[math.exp(v-max(logits))for v in logits];mass=math.fsum(shifted);raw=[v/mass for v in shifted]
 replayed=[raw[i]for i in spec['canonical']]
 require(abs(math.fsum(p)-1)<=EPS and all(abs(x-y)<=EPS for x,y in zip(p,replayed)),'Source-order unit-temperature softmax replay failed')
 original=r['probabilities_native_order']
 require(original==r[spec['probability_alias']]and type(original)is list and len(original)==3
  and all(finite(v)and abs(v-raw[i])<=EPS for i,v in enumerate(original)),'Original source-order probabilities changed')
 require(finite(r['temperature'])and r['temperature']==1 and r['calibrated']is False
  and r['semantic_decision_override']is False and r['model_weights_sha256']==spec['sha']
  and r['model_repository']==spec['repository']and r['model_revision']==spec['revision'],'RawT1 checkpoint/readout changed')
 winner=max(range(3),key=lambda i:logits[i]);label=spec['order'][winner]
 require(type(r['native_label_index'])is int and r['native_label_index']==winner and r['native_typed_argmax']==label,'Source-specific native argmax/tie rule changed')
 binary=r['native_binary_probabilities_Yes_No']
 require(set(binary)=={'Yes','No'}and all(finite(v)for v in binary.values())and abs(binary['Yes']-p[0])<=EPS
  and abs(binary['No']-(p[1]+p[2]))<=EPS and r['native_binary_decision']==('Yes'if p[0]>.5 else'No'),'Binary entailment collapse/tie changed')
 require(type(pair_tokens)is int and 0<pair_tokens<=512 and r['pair_tokens']==r['full_pair_tokens']==pair_tokens
  and r['max_pair_tokens']==512 and r['hidden_truncation']is False,'True source pair length/cap mismatch')
 require(r['premise_sha256']==hashlib.sha256(premise.encode()).hexdigest()
  and r['hypothesis_sha256']==hashlib.sha256(hypothesis.encode()).hexdigest(),'Reader literal source changed')
 require(type(r['native_pair_input_ids_sha256'])is str and re.fullmatch('[0-9a-f]{64}',r['native_pair_input_ids_sha256']),'Missing true pair token ID receipt')
 require(all(finite(r[k])and r[k]>=0 for k in ['forward_seconds','reader_seconds'])and r['reader_seconds']+1e-9>=r['forward_seconds'],'Invalid reader/forward timing')
 return {'probabilities':dict(zip(CLASSES,p)),'prediction':CANON[label],'binary_yes_probability':p[0],'binary_prediction':r['native_binary_decision']}
def metrics(rows,reader,expected_n=9):
 counts={c:{'n':0,'correct':0}for c in CLASSES};confusion={c:{p:0 for p in CLASSES}for c in CLASSES};scores=[]
 for row in rows:
  gold=row['gold'];require(gold in CLASSES,'Unknown source gold');r=row['readers'][reader];p=r['probabilities'];pred=r['prediction'];pg=p[gold]
  require(set(p)==set(CLASSES)and pred in CLASSES and all(finite(v)and 0<=v<=1 for v in p.values())and abs(math.fsum(p.values())-1)<=EPS,'Invalid complete forecast')
  correct=int(pred==gold);counts[gold]['n']+=1;counts[gold]['correct']+=correct;confusion[gold][pred]+=1
  scores.append({'id':row['id'],'document_id':row['document_id'],'gold':gold,'prediction':pred,'correct':correct,
   'Brier':math.fsum((p[c]-int(c==gold))**2 for c in CLASSES),'NLL_clipped_1e-12':-math.log(max(pg,FLOOR)),
   'NLL_clipped':pg<FLOOR,'unclipped_NLL_finite':pg>0,'probabilities':p})
 n=len(scores);require(n==expected_n,'Fixed case count required')
 return {'n':n,'correct':sum(r['correct']for r in scores),'accuracy':sum(r['correct']for r in scores)/n,
  'Brier':math.fsum(r['Brier']for r in scores)/n,'NLL_clipped_1e-12':math.fsum(r['NLL_clipped_1e-12']for r in scores)/n,
  'NLL_clip_count':sum(r['NLL_clipped']for r in scores),'unclipped_NLL_finite':all(r['unclipped_NLL_finite']for r in scores),
  'by_class':counts,'confusion':confusion,'scores':scores}
def engineering_gates(results):
 require(set(results)==set(ARMS),'All six arms required');candidate=results[PRIMARY]
 checks={'primary_all9_correct':candidate['correct']==9,'authored_class_balance3each':all(candidate['by_class'][c]['n']==3 for c in CLASSES),
  'primary_all3_per_class_correct':all(candidate['by_class'][c]['correct']==3 for c in CLASSES),
  'full_source_model_accuracy_gain_at_least2':candidate['correct']-results['b354_full_source']['correct']>=2}
 for name in GATE_CONTROLS:
  checks[name+':Brier_nonincrease']=candidate['Brier']<=results[name]['Brier']+1e-12
  checks[name+':NLL_nonincrease']=candidate['NLL_clipped_1e-12']<=results[name]['NLL_clipped_1e-12']+1e-12
 return checks
def paired_differences(results):
 candidate=results[PRIMARY];answer={}
 for name in ARMS:
  if name==PRIMARY:continue
  other=results[name];rows=[]
  for a,b in zip(candidate['scores'],other['scores']):
   require(a['id']==b['id']and a['document_id']==b['document_id']and a['gold']==b['gold'],'Unmatched paired engineering cases')
   rows.append({'id':a['id'],'document_id':a['document_id'],'primary_minus_correct':a['correct']-b['correct'],
    'primary_minus_Brier':a['Brier']-b['Brier'],'primary_minus_NLL':a['NLL_clipped_1e-12']-b['NLL_clipped_1e-12']})
  require(len(rows)==9 and len({r['document_id']for r in rows})==9,'Nine authored source clusters required')
  answer[name]={'primary_minus_correct':candidate['correct']-other['correct'],'primary_minus_accuracy':candidate['accuracy']-other['accuracy'],
   'primary_minus_Brier':candidate['Brier']-other['Brier'],'primary_minus_NLL':candidate['NLL_clipped_1e-12']-other['NLL_clipped_1e-12'],
   'authored_case_differences':rows,'authored_source_clusters':9,'uncertainty':'Nine source-authored, intentionally balanced CC0 engineering cases; descriptive paired model/context comparison only, not benchmark or population generalization. Full-source native is coverage admission, not a causal ranking-gain claim.'}
 return answer
