"""Literal source/UTF8/numeric replay from existing E34 raw captures; no gold/tokenizer I/O."""
from pathlib import Path
import hashlib,json,math,os,re,statistics
W=Path('/workspace/ruvector-epoch34-047dbc740dc2'); A=Path('/workspace/ruvector-e34-independent-audit')
raw_path=W/'project/experiments/sota-2026-10-22/epoch34/runs/dev/raw.json'
NUMBER=re.compile(r'(?<![\w])[-+\u2212]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?![\w])')
def need(v,m):
    if not v:raise ValueError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(p):
    b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':sha(b)}
def main():
    b=raw_path.read_bytes();need(sha(b)=='86c31223fedcc0d1a83b12becc9bb70b8433db8391f65effe13e64860c0407bd','Raw differs');raw=json.loads(b)
    rows=[]; aggregates={}
    for role in ['engineering','dev']:
        for case in raw['corpora'][role]['cases']:
            source=case['document'];need(sha(source.encode())==case['document_sha256'],'Raw source hash differs')
            for arm,output in case['arms'].items():
                c=output['context'];spans=c['selected_source_spans'];p=c['source_provenance']
                need(all(type(a)is int and type(z)is int and 0<=a<z<=len(source) for a,z in spans),'Invalid spans')
                need(all(spans[i][1]<spans[i+1][0] for i in range(len(spans)-1)),'Spans overlap/noncanonical adjacency')
                premise='\n\n'.join(source[a:z]for a,z in spans)
                need(premise==output['premise'] and sha(premise.encode())==c['premise_sha256'],'Exact premise differs')
                provenance=[{'source_char_start':a,'source_char_end':z,'source_byte_start':len(source[:a].encode()),'source_byte_end':len(source[:z].encode()),'text':source[a:z],'text_sha256':sha(source[a:z].encode())}for a,z in spans]
                need(provenance==p['selected_source_provenance'],'UTF8 provenance differs')
                numbers=[]
                for m in NUMBER.finditer(source):
                    a,z=m.start(),m.end();text=m.group();numbers.append({'source_char_start':a,'source_char_end':z,'source_byte_start':len(source[:a].encode()),'source_byte_end':len(source[:z].encode()),'text':text,'text_sha256':sha(text.encode()),'retained':any(x<=a and z<=y for x,y in spans),'lexical_year_candidate':bool(re.fullmatch(r'\d{4}',text)and 1000<=int(text)<=2999)})
                need(numbers==p['numeric_literals'] and p['numeric_literal_pattern']==NUMBER.pattern,'Numeric literal replay differs')
                nr=sum(n['retained']for n in numbers);no=len(numbers)-nr
                need(nr==p['numeric_literals_retained'] and no==p['numeric_literals_omitted'],'Numeric count differs')
                need(p['source_text_normalized']is False and p['semantic_decision_override']is False,'Numeric/source semantic mutation')
                retained=sum(z-a for a,z in spans);coverage=retained/len(source)
                need(retained==c['retained_source_characters'] and len(source)==c['document_characters'] and abs(coverage-c['document_character_coverage'])<1e-14,'Source coverage differs')
                need(c['all_selected_groups_complete'] and c['additional_neighbor_unit_ids_inspected']==[] and c['selected_token_fallback_unit_ids']==[],'Unexpected context filler')
                rows.append({'role':role,'id':case['id'],'arm':arm,'document_id':case['document_id'],'document_characters':len(source),'selected_characters':retained,'source_character_coverage':coverage,'joint_pair_tokens_observed':output['joint_pair_tokens'],'selected_spans':spans,'mandatory_group_ids':c['mandatory_ranked_group_ids'],'optional_definition_group_ids':c['optional_definition_group_ids_admitted'],'single_group_degenerate':c['single_group_degenerate'],'numeric_literals':len(numbers),'numeric_retained':nr,'numeric_omitted':no,'lexical_year_candidates':sum(n['lexical_year_candidate']for n in numbers),'lexical_year_candidates_retained':sum(n['lexical_year_candidate']and n['retained']for n in numbers)})
    need(len(rows)==120,'Not 120 actual contexts')
    for role in ['engineering','dev']:
        aggregates[role]={}
        for arm in ['actual_native','native_original','lexical','positional']:
            rr=[r for r in rows if r['role']==role and r['arm']==arm];v=[r['source_character_coverage']for r in rr]
            aggregates[role][arm]={'contexts':len(rr),'coverage_min':min(v),'coverage_median':statistics.median(v),'coverage_max':max(v),'full_document_contexts':sum(x==1 for x in v),'observed_pair_tokens_min':min(r['joint_pair_tokens_observed']for r in rr),'observed_pair_tokens_max':max(r['joint_pair_tokens_observed']for r in rr),'single_group_degenerate_contexts':sum(r['single_group_degenerate']for r in rr),'numeric_literal_occurrences_across_contexts':sum(r['numeric_literals']for r in rr),'numeric_retained_occurrences_across_contexts':sum(r['numeric_retained']for r in rr),'numeric_omitted_occurrences_across_contexts':sum(r['numeric_omitted']for r in rr)}
    report={'schema_version':1,'epoch':34,'checks_passed':True,'status':'PASS_120_EXACT_LITERAL_SOURCE_UTF8_NUMERIC_CONTEXTS','evidence':{'raw':ref(raw_path),'audit_source':ref(Path(__file__))},'actual_contexts_checked':len(rows),'aggregate':aggregates,'observations':rows,'original_gold_source_reads':0,'model_native_tokenizer_calls':0,'used_confirmation_identities':[],'scope':'Literal selected source text, byte/character offsets, numeric/year identities and retained/omitted partitions independently recomputed from existing raw captures. No original annotations, labels, evidence lists or source bank read. True token counts recorded by actual worker, not independently retokenized. Numeric omission and retrieval misses never prove absence or insufficient evidence; this is provenance, not arithmetic or semantic numerical reasoning. Repeated numeric occurrences across per-hypothesis contexts are not unique-document totals.'}
    out=A/'context-numeric-actual-independent-v1.json';payload=(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False)as f:f.write(payload);f.flush();os.fsync(fd)
    finally:os.close(fd)
    d=os.open(A,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d);print(json.dumps(ref(out),sort_keys=True));print(json.dumps(aggregates['dev'],sort_keys=True))
if __name__=='__main__':main()
