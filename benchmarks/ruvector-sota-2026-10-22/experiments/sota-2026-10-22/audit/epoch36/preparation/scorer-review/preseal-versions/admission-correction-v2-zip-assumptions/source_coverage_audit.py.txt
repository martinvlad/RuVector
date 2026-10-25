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
def full_context_check(source,hypothesis,units,catalogue,native,arm):
 c=arm['context'];ids=list(range(len(units)));spans=[[0,len(source)]]
 require(len(native['ids'])==len(ids)and all(type(i)is int for i in native['ids'])and set(native['ids'])==set(ids),'Full-source admission requires actual complete unique native unitset')
 require(c['policy']==FULL_POLICY and arm['premise']==source and c['selected_source_spans']==spans,
  'Full-source arm changed supplied text/span or policy')
 require(c['selected_chunk_ids_source_order']==ids and set(c['selected_chunk_ids_rank_order'])==set(ids)
  and len(c['selected_chunk_ids_rank_order'])==len(ids),'Full-source arm omitted or repeated source unit')
 require(c['source_sentence_groups']==catalogue and c['omitted_chunk_ids']==[]and c['omitted_source_spans']==[]
  and c['full_supplied_source_in_original_order']is True and c['native_complete_unique_unitset_verified']is True
  and c['all_selected_groups_complete']is True and c['selected_group_ids_admission_order']==[g['group_id']for g in catalogue],
  'Full-source group/omission catalogue changed')
 require(c['document_characters']==c['retained_source_characters']==len(source)and c['document_character_coverage']==1.0
  and c['total_document_chunks']==len(units),'Full supplied-source character coverage must be100percent')
 require(c['premise_sha256']==digest(source.encode())and c['hypothesis_sha256']==digest(hypothesis.encode()),'Full-source literal hashes changed')
 require(type(arm['joint_pair_tokens'])is int and 0<arm['joint_pair_tokens']<=512
  and c['joint_pair_tokens']==arm['joint_pair_tokens']and c['joint_pair_token_cap']==512,'Full pair must really fit512 without clipping')
 require(c['selected_evidence_truncated']is False and c['claim_truncated']is False and arm['semantic_decision_override']is False,
  'Full source/claim clipping or decision override forbidden')
 n=numeric_check(source,spans,c);require(n['numeric_omitted']==0,'Full-source numeric retention incomplete')
 return {'policy':FULL_POLICY,'full_source_exact_bytes':True,'native_coverage_admission':True,
  'complete_actual_native_unitset':native['ids'],'source_groups':len(catalogue),
  'original_document_character_coverage':1.0,'full_document_context':True,**n,
  'scope':'Native provides a full-unitset provenance admission; this full-source policy is not a causal native ranking-selection gain. True token count is a frozen worker observation, not independent retokenization.'}
