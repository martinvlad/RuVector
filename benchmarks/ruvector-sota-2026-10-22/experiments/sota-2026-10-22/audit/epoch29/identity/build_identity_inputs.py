"""Document id/text-only canonical inventory and protected engineering inputs.

No annotation/evidence access. Full public annotated source is parsed in RAM.
Protected and nonexposed texts are hashed by stdlib only, never emitted to model bank.
"""
import argparse
import json
from pathlib import Path
from identity_common import (KIND,SOURCE_SHA,SOURCE_BYTES,require,read,identity,
                             sha,normalize,model_text,write_new)

def build(source_path,protocol_path,output_dir,source_freeze_path,source_freeze_sha):
    freeze=read(source_freeze_path,source_freeze_sha)
    require(freeze['epoch']==29 and freeze['kind']==KIND,'Wrong identity source freeze')
    for pin in freeze['files']:require(identity(pin['path'])==pin,'Frozen identity source changed')
    require(any(pin==identity(Path(__file__).resolve()) for pin in freeze['files']),'Identity builder not frozen')
    require(any(pin==identity(protocol_path) for pin in freeze['files']),'Protocol not frozen')
    protocol=read(protocol_path)
    old=set(protocol['old_exposed_index_document_ids_before_protection'])
    protected=set(protocol['protected_document_ids'])
    retired=set(protocol['retired_LoRA_fixed_document_ids'])
    remaining=set(protocol['remaining_unreserved_document_ids'])
    require((len(old),len(protected),len(retired),len(remaining))==(261,24,16,122),'Fixed role counts changed')
    require(len(old|protected|retired|remaining)==423,'Role partition overlaps')
    out=Path(output_dir).resolve();require(out.is_dir() and not any(out.iterdir()),'Empty identity output directory required')
    source=read(source_path,SOURCE_SHA,SOURCE_BYTES)
    docs={d['id']:d for d in source['documents']}
    require(len(docs)==len(source['documents'])==423 and set(docs)==old|protected|retired|remaining,'Official source universe changed')
    hashes={};groups={};records=[]
    # Exactly423 intentional source text-field traversals. Hash-only metadata for
    # protected24 and remaining122; no tokenizer/model call or text output for them.
    for did in sorted(docs):
        text=docs[did]['text'];require(type(text)is str and text,'Source document must be nonempty string')
        normalized=normalize(text);require(normalized,'Empty normalized source')
        h=sha(normalized.encode());hashes[did]=h;groups.setdefault(h,[]).append(did)
        role='old_exposed' if did in old else 'protected_confirmation' if did in protected else 'retired_LoRA' if did in retired else 'remaining_unreserved'
        records.append({'document_id':did,'role':role,'normalized_document_sha256':h,'source_document_sha256':sha(text.encode()),'source_utf8_bytes':len(text.encode())})
    protected_hashes={hashes[i] for i in protected}
    excluded=sorted(i for i in old if hashes[i] in protected_hashes)
    corpus=sorted(old-set(excluded));qid=protocol['known_alias_query_document_id']
    require(qid==548 and hashes[qid]==protocol['known_alias_normalized_sha256'],'Known548 identity changed')
    protected_aliases=[{'protected_document_id':i,'normalized_document_sha256':hashes[i],
                       'old_exposed_alias_ids':[j for j in groups[hashes[i]] if j in old],
                       'status':'CONF_IDENTITY_INELIGIBLE_HOLD_PRIOR_EXPOSED_ALIAS'}
                      for i in sorted(protected) if any(j in old for j in groups[hashes[i]])]
    catalog={'schema_version':1,'epoch':29,'kind':KIND,'source':identity(source_path),'records':records,
             'canonical_groups':[{'normalized_document_sha256':h,'document_ids':ids} for h,ids in sorted(groups.items())],
             'protected_prior_exposed_aliases':protected_aliases,'protected_ids_unchanged':sorted(protected),
             'remaining_unreserved_future_inventory':[{'document_id':i,'normalized_document_sha256':hashes[i],
                 'same_canonical_group_document_ids':groups[hashes[i]],'future_review_only_no_current_allocation':True}
                for i in sorted(remaining)],'source_document_text_fields_hashed':423,'protected_text_fields_hashed_without_encoding':24,
             'remaining_unreserved_text_fields_hashed_without_encoding':122,'annotation_choices_accessed':0,'evidence_lists_accessed':0,
             'model_calls':0,'partition':{'exposed':277,'unreserved':122,'reserved_confirmation':24,'total':423},
             'isolation':'Full annotated publicJSON parsed; id/text field traversal only; logical field isolation, not OS secrecy'}
    write_new(out/'canonical-catalog.json',catalog)
    require(hashes[qid] not in protected_hashes,'Protected548 normalized alias: HOLD,0modelcalls')
    def row(did):
        text=docs[did]['text'];normalized=normalize(text);bge=model_text(normalized)
        return {'document_id':did,'normalized_text':normalized,'normalized_document_sha256':hashes[did],
                'source_document_sha256':sha(text.encode()),'source_utf8_bytes':len(text.encode()),
                'bge_input_sha256':sha(bge.encode()),'bge_input_utf8_bytes':len(bge.encode())}
    bank={'schema_version':1,'epoch':29,'kind':KIND,'normalization':'casefold+split/join whitespace',
          'documents':[row(i) for i in corpus],'query':row(qid),'protected_document_ids':sorted(protected),
          'excluded_protected_alias_document_ids':excluded,'source_sha256':SOURCE_SHA,
          'roles':{'train':[],'dev':[],'calibration':[],'confirmation':[]}}
    write_new(out/'engineering-inputs.json',bank)
    queries=[]
    for did in corpus+[qid]:
        aliases=[i for i in corpus if i!=did and hashes[i]==hashes[did]]
        queries.append({'document_id':did,'is_corpus_query':did in old,'normalized_document_sha256':hashes[did],
                        'true_alias_document_ids':aliases})
    require(515 in queries[-1]['true_alias_document_ids'],'Known548→515 not in protected-safe corpus: HOLD')
    oracle={'schema_version':1,'epoch':29,'kind':KIND,'inputs':identity(out/'engineering-inputs.json'),
            'corpus_document_ids':corpus,'query_records':queries,'query_count':len(queries),'corpus_count':len(corpus),
            'positive_query_count':sum(bool(q['true_alias_document_ids'])for q in queries),
            'true_nonself_alias_pairs':sum(len(q['true_alias_document_ids'])for q in queries),
            'known_query_document_id':qid,'known_alias_document_id':515,'protected_alias_exclusions':excluded,
            'protected_prior_exposed_aliases':protected_aliases,'source_annotation_choices_accessed':0,'source_evidence_lists_accessed':0,
            'no_CLEAN_or_fresh_eligibility_decision':True}
    write_new(out/'identity-oracle.json',oracle)
    report={'schema_version':1,'epoch':29,'kind':KIND,'status':'PROTECTED_SAFE_FIXED_EXPOSED_DOCUMENT_IDENTITY_INPUTS_PROJECTED',
            'source':identity(source_path),'source_freeze_sha256':source_freeze_sha,'inputs':identity(out/'engineering-inputs.json'),
            'catalog':identity(out/'canonical-catalog.json'),'oracle':identity(out/'identity-oracle.json'),
            'corpus_count':len(corpus),'query_count':len(queries),'excluded_protected_alias_ids':excluded,
            'protected_prior_exposed_aliases':protected_aliases,'model_calls':0,'annotation_choices_accessed':0,'evidence_lists_accessed':0,
            'source_document_text_fields_hashed':423,'protected_text_fields_hashed_without_encoding':24,
            'remaining_unreserved_text_fields_hashed_without_encoding':122,'models_receive_remaining_or_protected_texts':False,
            'LoRA_HOLD_unchanged':True,'roles':bank['roles'],'benchmark_accepted':False,'champion_promoted':False}
    write_new(out/'projection.json',report)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['source','protocol','output-dir','source-freeze','source-freeze-sha256']:p.add_argument('--'+n,required=True)
    a=p.parse_args();r=build(a.source,a.protocol,a.output_dir,a.source_freeze,a.source_freeze_sha256)
    print(json.dumps({'status':r['status'],'corpus_count':r['corpus_count'],'query_count':r['query_count'],'protected_exclusions':r['excluded_protected_alias_ids'],'annotation_choices_accessed':0}))
