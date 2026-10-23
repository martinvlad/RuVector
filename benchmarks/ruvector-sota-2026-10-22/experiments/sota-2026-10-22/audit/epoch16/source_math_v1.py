"""Independent exact-source context reconstruction; tokenization only."""
import hashlib,re
DEFINITION=re.compile(r'(?:\bhereinafter\b|\breferred\s+to\s+as\b|\bdefined\s+as\b|["“][^"”\r\n]{1,80}["”]\s*(?:shall\s+)?(?:means?|includes?)\b)',re.I)
NAMED=re.compile(r'''\([^()\r\n]{0,96}["“‘']\s*(?:(?:confidential|proprietary|non[\s\-\u2010-\u2015]*public)[\s\-\u2010-\u2015]+information|data[\s\-\u2010-\u2015]+recipient|receiving[\s\-\u2010-\u2015]+party|disclosing[\s\-\u2010-\u2015]+party|vendor|recipient)\s*["”’'][^()\r\n]{0,32}\)''',re.I)
BETWEEN=re.compile(r'\bbetween\b',re.I)
PARTY=re.compile(r'\b(?:agreement|parties|party|recipient|disclosing|receiving)\b',re.I)
NUMBER=re.compile(r'(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:\s*%|\b)')
def merged(units,ids):
 out=[]
 for a,b in sorted((units[i]['start'],units[i]['end']) for i in ids):
  if out and a<=out[-1][1]:out[-1][1]=max(out[-1][1],b)
  else:out.append([a,b])
 return out

def text_for(state,units,ids):
 spans=merged(units,ids);return '\n\n'.join(state[a:b] for a,b in spans),spans

def priority(state,units,tok):
 selected=[];attempts=[]
 for i,u in enumerate(units):
  assert u['id']==i and 0<=u['start']<u['end']<=len(state)
  text=state[u['start']:u['end']];triggers=[]
  if DEFINITION.search(text):triggers.append('explicit-definition-marker')
  if NAMED.search(text):triggers.append('explicit-quoted-named-term-parenthetical')
  initial=state[u['start']:min(u['end'],2048)]
  if u['start']<2048 and BETWEEN.search(initial) and PARTY.search(initial):triggers.append('initial-party-declaration')
  if not triggers:continue
  candidate,_=text_for(state,units,selected+[i]);count=len(tok.encode(candidate,add_special_tokens=False).ids);accepted=not u['token_fallback'] and count<=160
  reason='admitted-whole-source-unit' if accepted else 'token-fallback-not-whole-original-atom' if u['token_fallback'] else 'whole-unit-exceeds-remaining160-token-priority-budget'
  attempts.append({'unit_id':i,'span':[u['start'],u['end']],'source_sha256':hashlib.sha256(text.encode()).hexdigest(),'triggers':triggers,'candidate_priority_tokens':count,'accepted':accepted,'reason':reason})
  if accepted:selected.append(i)
 text,spans=text_for(state,units,selected);count=len(tok.encode(text,add_special_tokens=False).ids);assert count<=160
 return {'selected_unit_ids':selected,'selected_source_spans':spans,'priority_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'priority_tokens':count,'priority_token_cap':160,'initial_party_character_cap':2048,'candidate_attempts':attempts,'whole_units_only':True,'token_fallback_admitted':False,'literal_first_text_guaranteed':False,'claim_dependent':False}

def check_priority(actual,expected):
 for key,value in expected.items():assert actual[key]==value,('priority',key,actual.get(key),value)
 assert actual['definition_regex']==DEFINITION.pattern and actual['named_parenthetical_regex']==NAMED.pattern and actual['between_regex']==BETWEEN.pattern and actual['party_regex']==PARTY.pattern

def pack(state,units,order,hyp,tok,priority_ids):
 selected=list(priority_ids);trace=[];order=list(order)[:40]
 assert len(order)==len(set(order)) and all(type(i) is int and 0<=i<len(units) for i in order)
 pre,_=text_for(state,units,selected);assert len(tok.encode(pre,hyp).ids)<=512 and len(tok.encode('',hyp).ids)<=512
 def admit(i,role,anchor):
  if i in selected:return True
  text,_=text_for(state,units,selected+[i]);count=len(tok.encode(text,hyp).ids);ok=count<=512;trace.append({'unit_id':i,'role':role,'anchor':anchor,'candidate_pair_tokens':count,'accepted':ok})
  if ok:selected.append(i)
  return ok
 for i in order:
  if i in selected:continue
  if admit(i,'ranked-anchor',i):
   for j in [i-1,i+1]:
    if 0<=j<len(units) and units[j]['paragraph_id']==units[i]['paragraph_id']:admit(j,'same-paragraph-neighbor',i)
 assert selected
 text,spans=text_for(state,units,selected);count=len(tok.encode(text,hyp).ids);assert count<=512
 numbers=[{'span':[m.start(),m.end()],'text':m.group(),'retained':any(a<=m.start() and m.end()<=b for a,b in spans)} for m in NUMBER.finditer(state)]
 return {'selected':selected,'spans':spans,'premise':text,'tokens':count,'trace':trace,'numbers':numbers,'chars':sum(b-a for a,b in spans),'neighbors':sorted({x['unit_id'] for x in trace if x['role']=='same-paragraph-neighbor' and x['unit_id'] not in order})}

def check_pack(actual,result,state,units,order,hyp,tok,pre):
 cov=actual['coverage'];assert actual['chunk_ids']==result['selected'] and actual['chunk_spans']==[[units[i]['start'],units[i]['end']] for i in result['selected']]
 assert actual['premise']==result['premise'] and actual['hypothesis']==hyp and actual['ranking_ids']==order
 check_priority(cov['definition_priority'],pre)
 assert cov['selected_chunk_ids_rank_order']==result['selected'] and cov['selected_chunk_ids_source_order']==sorted(result['selected']) and cov['selected_source_spans']==result['spans']
 assert cov['packing_attempts']==result['trace'] and cov['joint_pair_tokens']==result['tokens'] and cov['joint_pair_token_cap']==512 and cov['additional_neighbor_unit_ids_inspected']==result['neighbors']
 assert cov['omitted_chunk_ids']==[i for i in range(len(units)) if i not in result['selected']] and cov['omitted_source_spans']==[[u['start'],u['end']] for u in units if u['id'] not in result['selected']]
 assert cov['retained_source_characters']==result['chars'] and cov['document_characters']==len(state) and abs(cov['document_character_coverage']-result['chars']/len(state))<1e-12
 assert cov['numeric_mentions']==result['numbers'] and cov['numeric_mentions_retained']==sum(x['retained'] for x in result['numbers']) and cov['numeric_mentions_omitted']==sum(not x['retained'] for x in result['numbers'])
 assert not cov['selected_evidence_truncated'] and not cov['claim_truncated']
 assert cov['premise_sha256']==hashlib.sha256(result['premise'].encode()).hexdigest() and cov['hypothesis_sha256']==hashlib.sha256(hyp.encode()).hexdigest()
 old=pack(state,units,order,hyp,tok,[]);counter=cov['no_priority_counterfactual'];assert counter['status']=='TOKENIZATION_ONLY' and counter['model_forwards']==0
 expected={'selected_chunk_ids_source_order':sorted(old['selected']),'selected_source_spans':old['spans'],'joint_pair_tokens':old['tokens'],'retained_source_characters':old['chars'],'numeric_mentions_retained':sum(x['retained'] for x in old['numbers']),'displaced_unit_ids':sorted(set(old['selected'])-set(result['selected'])),'introduced_unit_ids':sorted(set(result['selected'])-set(old['selected'])),'source_characters_delta':result['chars']-old['chars'],'pair_tokens_delta':result['tokens']-old['tokens'],'numeric_retained_delta':sum(x['retained'] for x in result['numbers'])-sum(x['retained'] for x in old['numbers'])}
 for key,value in expected.items():assert counter[key]==value,('counterfactual',key)
 return expected
