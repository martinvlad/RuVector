"""Real512-only-first NLI, public hash/count receipts and private full features.

Definitions only. No model/tokenizer imports before the actual worker invokes
score. No text/tokenIDs/offset arrays leave this module through public receipt.
"""
import hashlib
import json
import math
import re
import time

NUMBER=re.compile(r'(?<![\w])[-+\u2212]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?![\w])')
LABELS=('NotMentioned','Entailment','Contradiction')
MAP={'b354':[1,0,2],'tasksource':[1,0,2]}
NATIVE={'b354':('Entailment','NotMentioned','Contradiction'),'tasksource':('Entailment','NotMentioned','Contradiction')}

def digest(value):
 raw=value.encode('utf-8')if isinstance(value,str)else json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 return hashlib.sha256(raw).hexdigest()

def decisions(logits,tag):
 if tag not in MAP or not isinstance(logits,list)or len(logits)!=3 or any(type(v)not in(int,float)or not math.isfinite(v)for v in logits):raise ValueError('INVALID_REAL_NATIVE_LOGITS')
 peak=max(logits);shift=[v-peak for v in logits];normalizer=math.log(math.fsum(math.exp(v)for v in shift))
 native_logp=[v-normalizer for v in shift];native_p=[math.exp(v)for v in native_logp];p=[native_p[i]for i in MAP[tag]];lp=[native_logp[i]for i in MAP[tag]]
 canonical_logits=[logits[i]for i in MAP[tag]];winner=max(range(3),key=lambda i:canonical_logits[i]);primary=LABELS[winner]
 return {'raw_native_logits':list(logits),'raw_native_probabilities':native_p,'probabilities_N_E_C':p,'log_probabilities_N_E_C':lp,
  'primary_label':primary,'argmax_label':primary,'canonical_argmax_index':winner}

def merged(spans):
 result=[]
 for a,b in sorted(spans):
  if a==b:continue
  if result and a<=result[-1][1]:result[-1][1]=max(result[-1][1],b)
  else:result.append([a,b])
 return result

def prepare(tokenizer,premise,claim,ordered_ids,counters=None):
 started=time.perf_counter()
 if counters is not None:counters['NLI_full_pair_tokenizer_calls_attempted']+=1
 full=tokenizer(premise,text_pair=claim,add_special_tokens=True,padding=False,truncation=False,
  return_attention_mask=True,return_token_type_ids=False,return_offsets_mapping=True)
 if counters is not None:counters['NLI_full_pair_tokenizer_calls_completed']+=1
 sequences=full.sequence_ids();full_claim=[i for i,s in zip(full['input_ids'],sequences)if s==1]
 if counters is not None:counters['NLI_claim_fit_tokenizer_calls_attempted']+=1
 alone=tokenizer('',text_pair=claim,add_special_tokens=True,padding=False,truncation=False,
  return_attention_mask=True,return_token_type_ids=False)
 if counters is not None:counters['NLI_claim_fit_tokenizer_calls_completed']+=1
 if len(alone['input_ids'])>512:raise ValueError('FULL_HYPOTHESIS_EXCEEDS512_STOP_NO_REPLACEMENT')
 if counters is not None:counters['NLI_capped_pair_tokenizer_calls_attempted']+=1
 capped=tokenizer(premise,text_pair=claim,add_special_tokens=True,padding=False,truncation='only_first',max_length=512,
  return_attention_mask=True,return_token_type_ids=False,return_offsets_mapping=True)
 if counters is not None:counters['NLI_capped_pair_tokenizer_calls_completed']+=1
 consumed_seq=capped.sequence_ids();consumed_claim=[i for i,s in zip(capped['input_ids'],consumed_seq)if s==1]
 if consumed_claim!=full_claim or not 0<len(capped['input_ids'])<=512:raise ValueError('WHOLE_CLAIM_OR512_PAIR_INTEGRITY_FAILED')
 full_premise=[i for i,s in zip(full['input_ids'],sequences)if s==0];consumed_premise=[i for i,s in zip(capped['input_ids'],consumed_seq)if s==0]
 spans=merged([list(offset)for offset,seq in zip(capped['offset_mapping'],consumed_seq)if seq==0])
 numbers=list(NUMBER.finditer(premise));retained=sum(any(a<=m.start()and m.end()<=b for a,b in spans)for m in numbers)
 features={k:list(capped[k])for k in ('input_ids','attention_mask')};full_features={k:list(full[k])for k in ('input_ids','attention_mask')}
 audit={'full_premise_sha256':digest(premise),'claim_sha256':digest(claim),'ordered_unit_ids':list(ordered_ids),
  'full_joint_tokens':len(full['input_ids']),'joint_tokens':len(capped['input_ids']),
  'full_premise_tokens':len(full_premise),'consumed_premise_tokens':len(consumed_premise),
  'full_claim_tokens':len(full_claim),'consumed_claim_tokens':len(consumed_claim),'claim_complete':True,
  'premise_truncated':len(consumed_premise)<len(full_premise),'full_input_features_sha256':digest(full_features),
  'consumed_input_features_sha256':digest(features),'consumed_premise_tokens_sha256':digest(consumed_premise),
  'consumed_claim_tokens_sha256':digest(consumed_claim),'full_numeric_literal_count':len(numbers),
  'retained_numeric_literal_count':retained,'omitted_numeric_literal_count':len(numbers)-retained,
  'numeric_literal_coverage':retained/len(numbers)if numbers else 1.0}
 private={'premise':premise,'claim':claim,'features':features,'full_features':full_features,'offset_mapping':list(capped['offset_mapping']),
  'sequence_ids':consumed_seq,'full_offsets':list(full['offset_mapping']),'full_sequence_ids':sequences,'input_audit':audit}
 return features,audit,private,time.perf_counter()-started

def score(reader,premise,claim,ordered_ids,tag,readout_id,counters,progress,private_writer):
 started=time.perf_counter();counters['pair_tokenizations_attempted']+=1
 features,audit,private,token_seconds=prepare(reader.tokenizer,premise,claim,ordered_ids,counters)
 counters['pair_tokenizations_completed']+=1
 torch=reader.torch;feed={k:torch.tensor([v],dtype=torch.long,device='cpu')for k,v in features.items()}
 counters['NLI_forward_calls_attempted']+=1;counters[tag+'_forward_calls_attempted']+=1;progress({'event':'NLI_FORWARD_BEFORE','readout_id':readout_id})
 forward=time.perf_counter()
 with torch.inference_mode():returned=reader.model(**feed,return_dict=True)
 output=returned.logits.detach().cpu();forward_seconds=time.perf_counter()-forward
 counters['NLI_forward_calls_completed']+=1;counters[tag+'_forward_calls_completed']+=1
 if list(output.shape)!=[1,3]or output.dtype!=torch.float32 or not bool(torch.isfinite(output).all()):raise ValueError('REAL_NLI_LOGITS_SHAPE_DTYPE_FINITE_FAILED')
 logits=[float(v)for v in output[0].tolist()];decision=decisions(logits,tag)
 private.update(readout_id=readout_id,model_tag=tag,raw_native_logits=logits);private_writer(private)
 receipt={'readout_id':readout_id,'model_tag':tag,**decision,'input_audit':audit,
  'timing':{'pair_tokenization_seconds':token_seconds,'NNI_forward_seconds':forward_seconds,'reader_total_seconds':time.perf_counter()-started}}
 counters['NLI_readouts_completed']+=1;counters['primary_decisions_completed']+=1;counters['canonical_argmax_decisions_completed']+=1
 progress({'event':'NLI_READOUT_AFTER','readout_id':readout_id});return receipt
