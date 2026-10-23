"""Independent byte-level BPE/feed replay: tokenizers only, never neural code.

Preflight touches only the three public engineering strings. Postrun mode first
requires immutable completed owned-process evidence, then re-encodes saved pairs.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import sys
import replay_pooler_v1 as R


def build_tokenizer():
    R.demand(importlib.metadata.version('tokenizers') == '0.21.4', 'exact pinned tokenizers distribution required')
    from tokenizers import AddedToken, Tokenizer, models, pre_tokenizers, processors, decoders
    protocol=R.read(R.PROTOCOL);assets={r['remote_path']:r for r in protocol['model']['assets']}
    files={}
    for name in ('vocab.json','merges.txt','special_tokens_map.json'):
        row=assets[name];p=R.member(row['path']);actual=R.identity(p,row['path'])
        R.demand(actual=={k:row[k]for k in('path','bytes','sha256')},'independent tokenizer source asset changed')
        files[name]=p
    vocab=R.read(files['vocab.json'])
    R.demand(len(vocab)==50265 and len(set(vocab.values()))==50265
             and all(type(k)is str and type(v)is int and 0<=v<50265 for k,v in vocab.items()),'exact literal source BPE vocabulary required')
    lines=files['merges.txt'].read_text().splitlines();R.demand(lines[0]=='#version: 0.2','exact source BPE merge format required')
    merges=[tuple(line.split())for line in lines[1:]if line]
    R.demand(all(len(pair)==2 for pair in merges),'literal source BPE pair ranks required')
    tokenizer=Tokenizer(models.BPE(vocab=vocab,merges=merges,dropout=None,continuing_subword_prefix='',end_of_word_suffix='',fuse_unk=False))
    tokenizer.pre_tokenizer=pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder=decoders.ByteLevel()
    tokenizer.post_processor=processors.RobertaProcessing(sep=('</s>',2),cls=('<s>',0),add_prefix_space=False,trim_offsets=True)
    special=R.read(files['special_tokens_map.json']);added=[];seen=set()
    for name in ('bos_token','eos_token','unk_token','sep_token','pad_token','cls_token','mask_token'):
        spec=special[name];R.demand(type(spec)is dict and type(spec['content'])is str,'exact official added-token metadata required')
        if spec['content']in seen:continue
        seen.add(spec['content']);added.append(AddedToken(spec['content'],single_word=spec['single_word'],lstrip=spec['lstrip'],rstrip=spec['rstrip'],normalized=spec['normalized'],special=True))
    tokenizer.add_special_tokens(added);tokenizer.no_padding();tokenizer.no_truncation()
    R.demand(not any(name in sys.modules for name in('torch','transformers','onnxruntime')),'tokenizer replay must never import neural frameworks')
    return tokenizer,vocab,[R.identity(files[name],assets[name]['path'])for name in files]


def preflight():
    tokenizer,vocab,assets=build_tokenizer();protocol=R.read(R.PROTOCOL);rows=[]
    for fixture in protocol['engineering']['fixtures']:
        encoded=tokenizer.encode(fixture['premise'],fixture['hypothesis'])
        def words(text):
            pieces=text.removesuffix('.').split(' ')
            return [pieces[0]]+['Ġ'+p for p in pieces[1:]]+['.']
        expected=[vocab[x]for x in['<s>',*words(fixture['premise']),'</s>','</s>',*words(fixture['hypothesis']),'</s>']]
        R.demand(encoded.ids==expected and encoded.attention_mask==[1]*len(expected)and encoded.type_ids==[0]*len(expected),'public parser/format fixture token IDs do not match exact BPE vocabulary contract')
        rows.append({'fixture_id':fixture['id'],'input_ids':encoded.ids,'attention_mask':encoded.attention_mask,'token_type_ids_not_fed':encoded.type_ids})
    return {'schema_version':1,'epoch':20,'at':datetime.now(timezone.utc).isoformat(),
            'kind':'TOKENIZER_ONLY_PUBLIC_ENGINEERING_FORMAT_PREFLIGHT','checks_passed':True,
            'tokenizers_version':'0.21.4','independent_backend_sha256':R.digest(tokenizer.to_str().encode()),
            'assets':assets,'fixtures':rows,'neural_framework_imports':[],
            'model_native_forwards':0,'legal_DEV_or_CONF_texts_read':0,'original_annotations_read':0,
            'scope':'Parser and pair-format verification on3public exposed engineering strings; no semantic predictions or benchmark measurement.'}


def replay(plan_path,raw_path,execution_path):
    plan,protocol=R.plan_replay(plan_path);raw=R.read(raw_path);execution=R.read(execution_path)
    state,instance=R.model_replay(raw,protocol);engineering=R.engineering_replay(raw,protocol,state,instance)
    R.assets_replay(raw,plan)
    complete=raw['status']=='COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE'
    R.demand(complete or(raw['status']=='REJECTED_ENGINEERING_QUALIFICATION_NO_LEGAL_INPUTS'and not engineering['passed']),'only completed immutable phase evidence may enter tokenizer replay')
    R.resources_replay(raw,execution,raw_path,raw['phase'],complete);R.counters_replay(raw,complete)
    pairs=[row['forward']for row in raw['canary_forwards']]
    if complete:
        for document in raw['documents']:
            for question in document['questions']:
                pairs.extend(question['arms'][arm]['forward']for arm in R.M.ARMS)
    R.demand(len(pairs)==(75 if complete else 3),'exact saved phase feed count required')
    tokenizer,_,assets=build_tokenizer();rows=[]
    for i,row in enumerate(pairs):
        encoded=tokenizer.encode(row['premise'],row['hypothesis'])
        feed={'input_ids':[encoded.ids],'attention_mask':[encoded.attention_mask]}
        R.demand(feed==row['feed']and row['feed_sha256']==R.digest(R.canonical(feed))
                 and row['token_type_ids_not_fed']==[encoded.type_ids],'actual tensor feed differs from independently reconstructed source BPE tokenizer')
        R.demand(len(encoded.ids)<=512 and all(x==1 for x in encoded.attention_mask)and all(x==0 for x in encoded.type_ids),'complete source tokenizer feed budget/format changed')
        rows.append({'forward_index':i,'input_text_sha256':row['input_text_sha256'],'feed_sha256':row['feed_sha256'],'tokens':len(encoded.ids)})
    return {'schema_version':1,'epoch':20,'phase':raw['phase'],'at':datetime.now(timezone.utc).isoformat(),
            'kind':'INDEPENDENT_POSTRUN_SOURCE_BPE_FEED_REPLAY','checks_passed':True,
            'plan_sha256':R.identity(plan_path)['sha256'],'raw_receipt_sha256':R.identity(raw_path)['sha256'],
            'execution_receipt':R.identity(execution_path,str(Path(execution_path).relative_to(R.ROOT))),
            'tokenizers_version':'0.21.4','actual_worker_backend_sha256':raw['tokenizer']['backend_sha256'],
            'independent_reconstructed_backend_sha256':R.digest(tokenizer.to_str().encode()),
            'reconstructed_backend_identity_comparison_scope':'Actual feed IDs are compared exactly. Independent constructor serialization metadata need not equal worker backend serialization.',
            'actual_feed_pairs_replayed':len(rows),'feeds':rows,'assets':assets,
            'model_native_forwards':0,'neural_framework_imports':[],
            'gold_labels_read':0,'scope':'Postrun exact source BPE/feed verification only; no new semantic predictions or corpus measurement.'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--preflight',action='store_true')
    for key in('plan','raw','execution'):ap.add_argument('--'+key,type=Path)
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    if a.preflight:
        R.demand(not any((a.plan,a.raw,a.execution)),'preflight cannot read legal/model receipts');v=preflight()
    else:
        R.demand(all((a.plan,a.raw,a.execution)),'postrun replay requires exact sealed plan/raw/execution');v=replay(a.plan,a.raw,a.execution)
    R.write_new(a.out,v);print({'checks_passed':True,'model_native_forwards':0,'scope':v['kind']})


if __name__=='__main__':main()
