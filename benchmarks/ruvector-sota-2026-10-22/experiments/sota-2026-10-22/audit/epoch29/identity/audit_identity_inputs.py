"""Independent hash-only/source-bank replay; never parses annotated source."""
import argparse
import json
from pathlib import Path
from identity_common import KIND,require,read,identity,sha,normalize,model_text,write_new

def audit(protocol_path,inputs_path,oracle_path,catalog_path):
    p,b,o,c=map(read,[protocol_path,inputs_path,oracle_path,catalog_path])
    require(all(d['epoch']==29 and d['kind']==KIND for d in [p,b,o,c]),'Wrong engineering identity scope')
    old=set(p['old_exposed_index_document_ids_before_protection']);protected=set(p['protected_document_ids'])
    require(len(old)==261 and len(protected)==24 and not(old&protected),'Historical roleIDs changed')
    records=c['records'];catalog={r['document_id']:r for r in records}
    require(len(records)==len(catalog)==423,'Complete unique hash-only catalog required')
    remaining=set(p['remaining_unreserved_document_ids']);retired=set(p['retired_LoRA_fixed_document_ids'])
    require(len(remaining)==122 and len(retired)==16 and len(old|protected|remaining|retired)==423,'Fixed partition changed')
    require(set(catalog)==old|protected|remaining|retired,'Catalog ID universe changed')
    for did,row in catalog.items():
        role='old_exposed'if did in old else 'protected_confirmation'if did in protected else 'retired_LoRA'if did in retired else 'remaining_unreserved'
        require(row['role']==role,'Catalog role changed')
    protected_hashes={catalog[i]['normalized_document_sha256'] for i in protected}
    exclusions=sorted(i for i in old if catalog[i]['normalized_document_sha256']in protected_hashes)
    corpus=sorted(old-set(exclusions));qid=548
    require(b['excluded_protected_alias_document_ids']==exclusions,'Protected exclusion changed')
    require([r['document_id']for r in b['documents']]==corpus and b['query']['document_id']==qid,'Model bank identity/order changed')
    require(b['protected_document_ids']==sorted(protected),'Protected IDs changed')
    require(b['roles']=={'train':[],'dev':[],'calibration':[],'confirmation':[]},'Engineering has scientific data roles')
    for row in b['documents']+[b['query']]:
        did=row['document_id'];txt=row['normalized_text'];h=sha(txt.encode())
        require(type(txt)is str and txt==normalize(txt),'Noncanonical model-bank normalized text')
        require(h==row['normalized_document_sha256']==catalog[did]['normalized_document_sha256'],'Normalized document hash mismatch')
        require(h not in protected_hashes and did not in protected|remaining,'Protected/unreserved model text')
        require(row['source_document_sha256']==catalog[did]['source_document_sha256']and row['source_utf8_bytes']==catalog[did]['source_utf8_bytes'],'Source identity mismatch')
        bge=model_text(txt);require(sha(bge.encode())==row['bge_input_sha256']and len(bge.encode())==row['bge_input_utf8_bytes'],'Separate BGE input hash mismatch')
    groups={}
    for did,row in catalog.items():groups.setdefault(row['normalized_document_sha256'],[]).append(did)
    expected_groups=[{'normalized_document_sha256':h,'document_ids':sorted(ids)}for h,ids in sorted(groups.items())]
    require(c['canonical_groups']==expected_groups,'Canonical fulltext group oracle mismatch')
    require(o['inputs']==identity(inputs_path)and o['corpus_document_ids']==corpus,'Oracle input binding mismatch')
    require([q['document_id']for q in o['query_records']]==corpus+[qid],'Oracle query order mismatch')
    for q in o['query_records']:
        did=q['document_id'];h=catalog[did]['normalized_document_sha256']
        targets=[i for i in corpus if i!=did and catalog[i]['normalized_document_sha256']==h]
        require(q['true_alias_document_ids']==targets and q['normalized_document_sha256']==h,'Exact nonself alias oracle mismatch')
    require(515 in o['query_records'][-1]['true_alias_document_ids'],'Known548→515 missing')
    require(o['positive_query_count']==sum(bool(q['true_alias_document_ids'])for q in o['query_records']),'Positive query count mismatch')
    require(o['true_nonself_alias_pairs']==sum(len(q['true_alias_document_ids'])for q in o['query_records']),'Positive alias pair count mismatch')
    require(o['corpus_count']==len(corpus)and o['query_count']==len(corpus)+1,'Counts mismatch')
    return {'schema_version':1,'epoch':29,'kind':KIND,'status':'PASS_PROTECTED_SAFE_DOCUMENT_IDENTITY_INPUTS_AND_ORACLE',
            'corpus_count':len(corpus),'query_count':len(corpus)+1,'protected_alias_exclusions':exclusions,
            'positive_query_count':o['positive_query_count'],'true_nonself_alias_pairs':o['true_nonself_alias_pairs'],
            'known548_aliases':o['query_records'][-1]['true_alias_document_ids'],
            'protected_prior_exposed_aliases':o['protected_prior_exposed_aliases'],
            'source_annotation_choices_or_evidence_accessed':0,'annotated_source_JSON_parses_by_auditor':0,
            'model_tokenizer_native_calls':0,'remaining122_or_reserved24_text_encoded':0,
            'source_builder_text_hash_traversals':{'all':423,'protected':24,'remaining_unreserved':122},
            'evidence':{'protocol':identity(protocol_path),'inputs':identity(inputs_path),'oracle':identity(oracle_path),'catalog':identity(catalog_path)},
            'LoRA_HOLD_retained':True,'benchmark_accepted':False,'champion_promoted':False,'roles':b['roles']}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['protocol','inputs','oracle','catalog','output']:p.add_argument('--'+n,required=True)
    a=p.parse_args();r=audit(a.protocol,a.inputs,a.oracle,a.catalog);write_new(a.output,r)
    print(json.dumps({'status':r['status'],'corpus_count':r['corpus_count'],'query_count':r['query_count']}))
