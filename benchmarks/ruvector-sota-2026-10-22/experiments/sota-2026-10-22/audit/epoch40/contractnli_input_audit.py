"""Independent replay of saved token/offset receipts; no tokenizer imports."""
import hashlib,json,re
import contractnli_io as I
import contractnli_metrics as M
import contractnli_data as D
# Frozen literal-coverage diagnostic, not arithmetic inference or a label rule.
NUMBER=re.compile(r'(?<![\w])[-+\u2212]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?![\w])')
def digest(v):return hashlib.sha256(v.encode()if type(v)is str else json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def merged(spans):
 result=[]
 for a,b in sorted(spans):
  if a==b:continue
  if result and a<=result[-1][1]:result[-1][1]=max(result[-1][1],b)
  else:result.append([a,b])
 return result

def check_saved_input(record,arm,readout,saved):
 units=record['evidence'];order=readout['input_audit']['ordered_unit_ids'];I.require(type(order)is list and len(order)==len(units)and set(order)==set(range(len(units)))and all(type(i)is int for i in order),'EVERY_SUPPLIED_UNIT_EXACTLY_ONCE_REQUIRED');premise='\n\n'.join(units[i]['sentence']for i in order);claim=record['claim'];D.assert_packed_input(claim,premise)
 I.require(saved['readout_id']==readout['readout_id']and saved['model_tag']==readout['model_tag']and saved['raw_native_logits']==readout['raw_native_logits']and saved['premise']==premise and saved['claim']==claim,'SAVED_SOURCE_PROVENANCE_MISMATCH');full=saved['full_features'];consumed=saved['features'];seq=saved['sequence_ids'];fseq=saved['full_sequence_ids'];offsets=saved['offset_mapping'];foffsets=saved['full_offsets']
 for features,sequences,spans in [(full,fseq,foffsets),(consumed,seq,offsets)]:
  I.require(set(features)=={'input_ids','attention_mask'}and type(features['input_ids'])is list and len(features['input_ids'])==len(features['attention_mask'])==len(sequences)==len(spans)and features['input_ids']and all(type(x)is int and x>=0 for x in features['input_ids'])and all(x==1 and type(x)is int for x in features['attention_mask']),'SAVED_UNPADDED_TOKEN_FEATURES_REQUIRED')
  for s,o in zip(sequences,spans):
   I.require((s is None or type(s)is int and s in [0,1])and type(o)in[list,tuple]and len(o)==2 and all(type(x)is int for x in o),'SAVED_TOKEN_OFFSET_SCHEMA_REQUIRED')
   I.require(0<=o[0]<=o[1]<=len(premise if s==0 else claim)if s is not None else list(o)==[0,0],'SAVED_TOKEN_OFFSET_BOUNDS_REQUIRED')
 fp=[i for i,s in zip(full['input_ids'],fseq)if s==0];fc=[i for i,s in zip(full['input_ids'],fseq)if s==1];cp=[i for i,s in zip(consumed['input_ids'],seq)if s==0];cc=[i for i,s in zip(consumed['input_ids'],seq)if s==1]
 I.require(fc==cc and cp==fp[:len(cp)]and 0<len(consumed['input_ids'])<=512,'ONLY_FIRST_PREMISE_PREFIX_WHOLE_CLAIM_REQUIRED');spans=merged([list(o)for o,s in zip(offsets,seq)if s==0]);numbers=list(NUMBER.finditer(premise));retained=sum(any(a<=m.start()and m.end()<=b for a,b in spans)for m in numbers)
 want={'full_premise_sha256':digest(premise),'claim_sha256':digest(claim),'ordered_unit_ids':order,'full_joint_tokens':len(full['input_ids']),'joint_tokens':len(consumed['input_ids']),'full_premise_tokens':len(fp),'consumed_premise_tokens':len(cp),'full_claim_tokens':len(fc),'consumed_claim_tokens':len(cc),'claim_complete':True,'premise_truncated':len(cp)<len(fp),'full_input_features_sha256':digest(full),'consumed_input_features_sha256':digest(consumed),'consumed_premise_tokens_sha256':digest(cp),'consumed_claim_tokens_sha256':digest(cc),'full_numeric_literal_count':len(numbers),'retained_numeric_literal_count':retained,'omitted_numeric_literal_count':len(numbers)-retained,'numeric_literal_coverage':retained/len(numbers)if numbers else 1.0}
 I.require(readout['input_audit']==want and saved['input_audit']==want,'INDEPENDENT_INPUT_COVERAGE_REPLAY_MISMATCH');return want
