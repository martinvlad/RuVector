"""Exact full supplied-source policy replay, without candidate/tokenizer imports."""
import re
from data_common import require,digest
FULL_POLICY='native-complete-source-when-pair-fits512-v1'
NUMBER=re.compile(r'(?<![\w])[-+\u2212]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?![\w])')
def numeric_check(source,spans,context):
 provenance=[{'source_char_start':a,'source_char_end':b,'source_byte_start':len(source[:a].encode()),
  'source_byte_end':len(source[:b].encode()),'text':source[a:b],'text_sha256':digest(source[a:b].encode())}for a,b in spans]
 numeric=context['source_provenance']
 require(numeric['selected_source_provenance']==provenance,'Exact original source UTF8 offsets/text changed')
 literals=[]
 for m in NUMBER.finditer(source):
  a,b=m.span();literals.append({'source_char_start':a,'source_char_end':b,'source_byte_start':len(source[:a].encode()),
   'source_byte_end':len(source[:b].encode()),'text':source[a:b],'text_sha256':digest(source[a:b].encode()),
   'retained':any(x<=a and b<=y for x,y in spans),
   'lexical_year_candidate':bool(re.fullmatch(r'\d{4}',m.group())and 1000<=int(m.group())<=2999)})
 require(numeric['numeric_literals']==literals and numeric['numeric_literal_pattern']==NUMBER.pattern
  and numeric['numeric_literals_retained']==sum(r['retained']for r in literals)
  and numeric['numeric_literals_omitted']==sum(not r['retained']for r in literals)
  and numeric['source_text_normalized']is False and numeric['semantic_decision_override']is False,'Exact numeric/source provenance changed')
 return {'numeric_occurrences':len(literals),'numeric_retained':sum(r['retained']for r in literals),
  'numeric_omitted':sum(not r['retained']for r in literals),'selected_source_spans':spans}

def source_groups(source,units):
 # Independent original-line catalogue: blank separators belong to following line.
 lines=source.splitlines(keepends=True);catalogue=[];cursor=start=0
 for number,line in enumerate(lines):
  cursor+=len(line)
  if line.strip():catalogue.append({'group_id':len(catalogue),'start':start,'end':cursor,'line_number':number,'source_sha256':None,'unit_ids':[]});start=cursor
 require(bool(catalogue),'Source line groups missing');catalogue[-1]['end']=len(source)
 for g in catalogue:g['source_sha256']=digest(source[g['start']:g['end']].encode())
 cursor=0
 require(type(units)is list and 0<len(units)<=40,'Native source unit cap')
 for i,u in enumerate(units):
  gid=u['group_id'];require(type(gid)is int and 0<=gid<len(catalogue),'Unknown original line group');g=catalogue[gid]
  require(type(u['id'])is int and u['id']==i and u['start']==cursor and type(u['end'])is int and cursor<u['end']<=g['end']and g['start']<=cursor,'Original source units have gaps/overlaps')
  require(u['source_line_span']==[g['start'],g['end']]and u['line_number']==g['line_number']and u['token_fallback']is False,'Source unit line identity differs')
  require(type(u['nli_tokens'])is int and 0<u['nli_tokens']<=160 and type(u['bge_tokens'])is int and 0<u['bge_tokens']<=256,'Actual whole-unit token caps changed')
  # Splits must land after a complete source whitespace-delimited word.
  require(u['end']==g['end']or source[u['end']-1].isspace(),'Source unit split within a word')
  g['unit_ids'].append(i);cursor=u['end']
 require(cursor==len(source)and all(g['unit_ids']for g in catalogue),'Complete source coverage missing')
 return catalogue

def selected_spans(catalogue,groups):
 spans=[]
 for i in sorted(groups):
  g=catalogue[i]
  if spans and spans[-1][1]==g['start']:spans[-1][1]=g['end']
  else:spans.append([g['start'],g['end']])
 return spans

def covers(spans,required):return all(any(a<=s and e<=b for a,b in spans)for s,e in required)

def context_check(source,hypothesis,units,catalogue,ranking,physical,analysis,name):
 c=physical['context'];spans=c['selected_source_spans'];required=analysis['required_source_spans'];n=len(units)
 require(type(ranking)is list and len(ranking)==n and set(ranking)==set(range(n))and all(type(x)is int for x in ranking),'Complete actual ranking missing')
 require(physical['observed_ranking']==ranking,'Physical measured ranking changed')
 require(c['dependency_analysis_sha256']==analysis['analysis_sha256']and c['all_required_source_quotes_covered']is True,'Source dependency admission differs')
 require(c['selected_evidence_truncated']is False and c['claim_truncated']is False and c['joint_pair_token_cap']==512 and type(physical['joint_pair_tokens'])is int and 0<physical['joint_pair_tokens']==c['joint_pair_tokens']<=512,'Complete source pair budget or truncation differs')
 if name=='full_source':
  require(c['policy']==FULL_POLICY and spans==[[0,len(source)]]and physical['premise']==source and c['selected_chunk_ids_source_order']==list(range(n))and c['selected_group_ids_admission_order']==list(range(len(catalogue)))and c['full_supplied_source_in_original_order']is True and c['document_character_coverage']==1.0,'Full original supplied source changed')
 else:
  require(c['policy']=='rank-prefix-until-source-constraint-coverage-v1'and c['source_line_groups']==catalogue and c['observed_complete_unit_ranking']==ranking,'Whole source line group policy differs')
  order=[];anchors={}
  for uid in ranking:
   gid=units[uid]['group_id']
   if gid not in anchors:order.append(gid);anchors[gid]=uid
  admitted=[]
  for gid in order:
   admitted.append(gid)
   if covers(selected_spans(catalogue,admitted),required):break
  expected_spans=selected_spans(catalogue,admitted);chosen=sorted(uid for gid in admitted for uid in catalogue[gid]['unit_ids']);omitted=[i for i in range(n)if i not in chosen]
  require(c['group_ranking_ids']==order and c['selected_group_ids_admission_order']==admitted and c['selected_chunk_ids_source_order']==chosen and c['selected_chunk_ids_rank_order']==[i for i in ranking if i in chosen],'Fixed identical prefix algorithm changed or skipped rank')
  require(c['omitted_chunk_ids']==omitted and c['omitted_source_spans']==[[units[i]['start'],units[i]['end']]for i in omitted]and spans==expected_spans and physical['premise']=='\n\n'.join(source[a:b]for a,b in spans),'Exact selected/omitted original source changed')
  trace=c['packing_attempts'];require(type(trace)is list and len(trace)==len(admitted),'Complete actual packing tokenization trace required')
  for j,(r,gid)in enumerate(zip(trace,admitted)):
   g=catalogue[gid];partial=selected_spans(catalogue,admitted[:j+1]);require(r['group_id']==gid and r['unit_ids']==g['unit_ids']and r['anchor_unit_id']==anchors[gid]and r['source_span']==[g['start'],g['end']]and type(r['candidate_pair_tokens'])is int and 0<r['candidate_pair_tokens']<=512 and r['required_quotes_covered']is covers(partial,required),'Prefix packing trace differs')
  require(trace[-1]['candidate_pair_tokens']==physical['joint_pair_tokens'],'Final observed packing pair token count differs')
  require(c['required_source_spans']==required and c['all_selected_groups_complete']is True and c['whole_group_prefix']is True and c['all_source_clauses_parsed']is(analysis['status']=='CERTIFICATE_CANDIDATE') and c['source_text_normalized']is False and c['selected_token_fallback_unit_ids']==[],'Source proof admission or line-group integrity differs')
  neutral=bool(analysis.get('proof')and analysis['proof']['neutral_requires_entire_source_catalog']);require(c['neutral_catalog_requires_full_source']is neutral,'Neutral full source admission differs')
  if neutral:require(spans==[[0,len(source)]],'Neutral proof lost full supplied catalogue')
  retained=sum(b-a for a,b in spans)
  require(c['total_document_chunks']==n and c['document_characters']==len(source)and c['retained_source_characters']==retained and c['document_character_coverage']==retained/len(source),'Exact source character coverage differs')
  require(c['premise_sha256']==digest(physical['premise'].encode())and c['hypothesis_sha256']==digest(hypothesis.encode()),'Source pair hash differs')
 require(covers(spans,required),'Required source quote omitted')
 numeric=numeric_check(source,spans,c)
 return {'measured_context':name,'selected_source_spans':spans,'selected_groups':len(c['selected_group_ids_admission_order']),'source_groups':len(catalogue),'document_character_coverage':sum(b-a for a,b in spans)/len(source),'joint_pair_tokens_observed':physical['joint_pair_tokens'],**numeric}
