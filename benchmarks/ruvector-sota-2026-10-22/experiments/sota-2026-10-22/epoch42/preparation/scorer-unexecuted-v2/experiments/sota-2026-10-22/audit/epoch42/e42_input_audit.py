"""Independent replay of retained source/window/token receipts; no tokenizer."""
import hashlib,importlib.util,json,re
from pathlib import Path
p=Path(__file__).with_name('e42_features.py');b=p.read_bytes()
if hashlib.sha256(b).hexdigest()!='41327b58e30e789a5c03a795e8750d1e2f3b75db986661dc7b192b0fa3b765b3':raise ValueError('INPUT_AUDIT_FEATURE_SOURCE_DRIFT')
spec=importlib.util.spec_from_file_location('e42_input_features',p);F=importlib.util.module_from_spec(spec);exec(compile(b,str(p),'exec'),F.__dict__)
NUMBER=re.compile(r'(?<![\w])[-+\u2212]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?![\w])')
DATE=re.compile(r'\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2},?\s+\d{4})\b',re.I)
def same_fact(a,b):
 if type(a)is not type(b):return False
 if type(a)is dict:return set(a)==set(b)and all(same_fact(a[k],b[k])for k in a)
 if type(a)is list:return len(a)==len(b)and all(same_fact(x,y)for x,y in zip(a,b))
 return a==b
def digest(v):return F.sha(v.encode()if type(v)is str else json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def coverage(units,selected):
 text=''.join(u['sentence']for u in units);ranges=[(u['start'],u['end'])for u in units if u['unit_id']in set(selected)];out={}
 for name,p in [('numeric_literal',NUMBER),('date_pattern',DATE)]:
  matches=list(p.finditer(text));kept=sum(any(a<=m.start()and m.end()<=b for a,b in ranges)for m in matches);out.update({name+'_total':len(matches),name+'_retained':kept,name+'_omitted':len(matches)-kept,name+'_coverage':kept/len(matches)if matches else 1.})
 out['scope']='Frozen literal/date regex diagnostics; not exhaustive numeric semantics, evidence sufficiency, or arithmetic correctness.';return out

def validate_packing_journal(rows):
 seen={};policy='FULL_UNTRUNCATED_PAIR_COMPLETE_CLAIM_ADD_SPECIAL_TOKENS_NO_PADDING_NO_TOKEN_TYPE_IDS'
 for i,r in enumerate(rows):
  v=r['features'];F.require(type(r['ordinal'])is int and r['ordinal']==i+1 and r['tokenization_policy']==policy and type(r['joint_tokens'])is int and r['joint_tokens']==len(v['input_ids'])and r['features_sha256']==digest(v),'EXACT_ACTUAL_PACKING_FEATURE_COUNT_HASH_POLICY');key=(r['case_id'],r['arm'],r['premise_sha256'],r['claim_sha256']);value=(r['joint_tokens'],r['features_sha256']);F.require(key not in seen or seen[key]==value,'REPEATED_SAME_PAIR_TOKENIZATION_INCONSISTENT');seen[key]=value
 return {'records':len(rows),'unique_case_arm_input_pairs':len(seen),'fresh_tokenizer_or_model_calls':0}

def replay_packing(record,arm,ranking,public,audits,start):
 units=record['evidence'];claim=record['claim'];cursor=start;local=0;last_features_sha=None
 def count(ids):
  nonlocal cursor,local,last_features_sha
  F.require(cursor<len(audits),'MISSING_ACTUAL_PACKING_AUDIT');r=audits[cursor];premise='\n\n'.join(units[i]['sentence']for i in sorted(ids));F.require(r['case_id']==record['id']and r['arm']==arm and type(r['ordinal'])is int and r['ordinal']==cursor+1 and r['premise_sha256']==digest(premise)and r['claim_sha256']==digest(claim),'PACKING_SOURCE_INPUT_AND_GLOBAL_COUNTER');v=r['features'];F.require(set(v)=={'input_ids','attention_mask'}and type(v['input_ids'])is list and len(v['input_ids'])==len(v['attention_mask'])and v['input_ids']and all(type(i)is int and i>=0 for i in v['input_ids'])and all(type(i)is int and i==1 for i in v['attention_mask']),'ACTUAL_PACKING_TOKEN_FEATURES');last_features_sha=r['features_sha256'];cursor+=1;local+=1;return len(v['input_ids'])
 F.require(count([])<=512,'FULL_ORIGINAL_HYPOTHESIS_FIT');result=[];first=set()
 for number in range(2):
  chosen=set();anchors=[];receipt=[]
  for anchor in ranking:
   if number==1 and anchor in first:receipt.append({'anchor':anchor,'status':'ANCHOR_ALREADY_REPRESENTED_IN_FIRST'});continue
   group=set(range(max(0,anchor-1),min(len(units),anchor+2)))
   if group<=chosen:receipt.append({'anchor':anchor,'status':'GROUP_ALREADY_REPRESENTED'});continue
   proposal=chosen|group;n=count(proposal)
   if n>512:receipt.append({'anchor':anchor,'status':'WHOLE_GROUP_SKIPPED_TOKEN_OVERFLOW','group_unit_ids':sorted(group),'proposed_joint_tokens':n});continue
   chosen=proposal;anchors.append(anchor);receipt.append({'anchor':anchor,'status':'WHOLE_GROUP_ACCEPTED','group_unit_ids':sorted(group),'proposed_joint_tokens':n})
  duplicate=not chosen
  if duplicate:F.require(number==1,'NO_WHOLE_FIRST_WINDOW');chosen=set(first)
  ids=sorted(chosen);n=count(ids);F.require(ids and n<=512,'WHOLE_SOURCE_WINDOW_FITS');premise='\n\n'.join(units[i]['sentence']for i in ids);result.append({'window_index':number,'selected_unit_ids':ids,'accepted_anchor_ids':anchors,'source_spans':[{'unit_id':i,'start':units[i]['start'],'end':units[i]['end'],'sha256':digest(units[i]['sentence'])}for i in ids],'premise_sha256':digest(premise),'joint_tokens':n,'packing_features_sha256':last_features_sha,'duplicate_first_window':duplicate,'selection_receipts':receipt,'source_character_coverage':sum(len(units[i]['sentence'])for i in ids)/units[-1]['end'],'source_units_total':len(units),'selected_source_units':len(ids),'selection_is_not_a_proof_of_absence':True,'premise_truncated':False,'span_splits':0,'coverage_audit':coverage(units,ids)})
  if number==0:first=set(chosen)
 union=sorted(set(result[0]['selected_unit_ids'])|set(result[1]['selected_unit_ids']));want={'windows':result,'packing_pair_tokenizer_calls':local,'duplicate_window_count':sum(w['duplicate_first_window']for w in result),'union_selected_unit_ids':union,'union_coverage_audit':coverage(units,union)};F.require(set(public)==set(want)|{'packing_seconds'}and all(same_fact(public[k],v)for k,v in want.items()),'INDEPENDENT_WHOLE_GROUP_PACKING_REPLAY');return cursor,want

def saved_window(record,window,readout,saved):
 ids=window['selected_unit_ids'];premise='\n\n'.join(record['evidence'][i]['sentence']for i in ids);claim=record['claim'];F.assert_packed_input(claim,premise);F.require(readout['input_audit']['consumed_input_features_sha256']==window['packing_features_sha256'],'ACTUAL_NNI_FEATURES_EQUAL_MEASURED_PACKING_FEATURES');F.require(saved['readout_id']==readout['readout_id']and saved['model_tag']=='tasksource'and saved['raw_native_logits']==readout['raw_native_logits']and saved['premise']==premise and saved['claim']==claim,'SAVED_REAL_SOURCE_PAIR_PROVENANCE');full=saved['full_features'];got=saved['features'];seq=saved['sequence_ids'];fseq=saved['full_sequence_ids'];off=saved['offset_mapping'];foff=saved['full_offsets'];F.require(full==got and seq==fseq and off==foff and 0<len(got['input_ids'])<=512 and len(got['input_ids'])==window['joint_tokens'],'NO_WINDOW_OR_HYPOTHESIS_TRUNCATION')
 for features,sequences,offsets in [(full,fseq,foff),(got,seq,off)]:
  F.require(set(features)=={'input_ids','attention_mask'}and len(features['input_ids'])==len(features['attention_mask'])==len(sequences)==len(offsets)and all(type(x)is int and x>=0 for x in features['input_ids'])and all(type(x)is int and x==1 for x in features['attention_mask']),'SAVED_UNPADDED_FEATURE_SCHEMA')
  for s,o in zip(sequences,offsets):
   F.require((s is None or type(s)is int and s in[0,1])and type(o)in[list,tuple]and len(o)==2 and all(type(x)is int for x in o),'SAVED_SEQUENCE_OFFSET_SCHEMA');F.require(list(o)==[0,0]if s is None else 0<=o[0]<=o[1]<=len(premise if s==0 else claim),'SAVED_SEQUENCE_OFFSET_BOUNDS')
 pp=[i for i,s in zip(got['input_ids'],seq)if s==0];cp=[i for i,s in zip(got['input_ids'],seq)if s==1];intervals=[]
 for a,b in sorted(list(o)for o,s in zip(off,seq)if s==0):
  if a==b:continue
  if intervals and a<=intervals[-1][1]:intervals[-1][1]=max(b,intervals[-1][1])
  else:intervals.append([a,b])
 nums=list(NUMBER.finditer(premise));kept=sum(any(a<=m.start()and m.end()<=b for a,b in intervals)for m in nums);want={'full_premise_sha256':digest(premise),'claim_sha256':digest(claim),'ordered_unit_ids':ids,'full_joint_tokens':len(full['input_ids']),'joint_tokens':len(got['input_ids']),'full_premise_tokens':len(pp),'consumed_premise_tokens':len(pp),'full_claim_tokens':len(cp),'consumed_claim_tokens':len(cp),'claim_complete':True,'premise_truncated':False,'full_input_features_sha256':digest(full),'consumed_input_features_sha256':digest(got),'consumed_premise_tokens_sha256':digest(pp),'consumed_claim_tokens_sha256':digest(cp),'full_numeric_literal_count':len(nums),'retained_numeric_literal_count':kept,'omitted_numeric_literal_count':len(nums)-kept,'numeric_literal_coverage':kept/len(nums)if nums else 1.};F.require(same_fact(saved['input_audit'],want)and same_fact(readout['input_audit'],want),'INDEPENDENT_NO_TRUNCATION_INPUT_REPLAY');return want
