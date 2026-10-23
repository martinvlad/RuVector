"""Tokenizers and source invariants only: zero model/session/addon execution."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,itertools,json,random,re
from tokenizers import Tokenizer

OUT=Path(__file__).resolve().parent;S=OUT.parents[1];PROJECT=S/'epoch10/project'
CONTEXT=S/'candidate/epoch6/context.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
source_sha=sha(CONTEXT)
spec=importlib.util.spec_from_file_location('epoch6_pure_context',CONTEXT);C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
nli_path=PROJECT/'experiments/sota-2026-10-22/candidate/epoch4/assets/nli-base/tokenizer.json'
bge_path=PROJECT/'models/bge-small-en-v1.5/tokenizer.json'
nli=Tokenizer.from_file(str(nli_path));bge=Tokenizer.from_file(str(bge_path))
for t in [nli,bge]:t.no_padding();t.no_truncation()
assert sha(nli_path)=='a86f883318afa11c8c10466f1bf4efaeb6ded28a52cbe57217a8fa0d0a2a87df'
assert sha(bge_path)=='d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66'
config_path=S/'candidate/epoch6/config.json';config_sha=sha(config_path);config=json.loads(config_path.read_text());assert config['ranking_depth']==40 and config['joint_pair_token_cap']==512
phases={'train':S/'legal-transfer/epoch10/train72.jsonl','development':S/'legal-transfer/epoch10/development24.jsonl','confirmation':S/'legal-transfer/epoch9/confirmation48.jsonl'}
maxb=maxn=maxbytes=maxunits=anchors=paths=0;stats={};cache={};trace_attempts=trace_rejections=0

def merge(units,ids):
    spans=[]
    for i in sorted(ids):
        a,b=units[i]['start'],units[i]['end']
        if spans and a==spans[-1][1]:spans[-1]=(spans[-1][0],b)
        else:spans.append((a,b))
    return spans

def verify(text,units,ranking,hyp):
    global maxn,maxbytes,trace_attempts,trace_rejections
    premise,audit=C.pack(text,units,ranking,hyp,nli,pair_cap=512,rank_depth=40)
    assert audit['ranking_ids_considered']==ranking[:40] and audit['ranking_depth']==min(40,len(ranking))
    assert audit['ranked_anchor_candidate_cap']==40 and audit['joint_pair_token_cap']==512
    assert audit['additional_neighbor_unit_ids_inspected']==sorted({step['unit_id'] for step in audit['packing_attempts'] if step['role']=='same-paragraph-neighbor' and step['unit_id'] not in ranking[:40]})
    selected=[]
    for step in audit['packing_attempts']:
        i=step['unit_id'];assert i not in selected
        spans=merge(units,selected+[i]);candidate='\n\n'.join(text[a:b] for a,b in spans)
        count=len(nli.encode(candidate,hyp).ids)
        assert count==step['candidate_pair_tokens'] and step['accepted']==(count<=512)
        trace_attempts+=1;trace_rejections+=not step['accepted']
        if step['accepted']:selected.append(i)
    spans=merge(units,selected)
    assert premise=='\n\n'.join(text[a:b] for a,b in spans)
    assert audit['selected_chunk_ids_rank_order']==selected and audit['selected_source_spans']==[list(x) for x in spans]
    assert audit['omitted_chunk_ids']==[i for i in range(len(units)) if i not in selected]
    count=len(nli.encode(premise,hyp).ids)
    assert count==audit['joint_pair_tokens']<=512 and not audit['selected_evidence_truncated'] and not audit['claim_truncated']
    assert audit['premise_sha256']==hashlib.sha256(premise.encode()).hexdigest() and audit['hypothesis_sha256']==hashlib.sha256(hyp.encode()).hexdigest()
    assert len(premise.encode())<=16384
    maxn=max(maxn,count);maxbytes=max(maxbytes,len(premise.encode()))

for phase,path in phases.items():
    records=rows(path);local_anchors=local_paths=0;fallback=0;phase_max_units=0
    for r in records:
        text=r['input']['state'];hyp=r['input']['questions']['decision']['criteria']['Yes']
        if text not in cache:
            units=C.partition(text,nli,bge,target=128,nli_cap=160,bge_cap=256,max_units=192)
            assert units[0]['start']==0 and units[-1]['end']==len(text) and all(a['end']==b['start'] for a,b in zip(units,units[1:]))
            assert ''.join(text[u['start']:u['end']] for u in units)==text
            for i,u in enumerate(units):
                assert u['id']==i and u['start']<u['end'] and u['nli_tokens']==len(nli.encode(text[u['start']:u['end']],add_special_tokens=False).ids)<=160
                count=len(bge.encode(text[u['start']:u['end']]).ids);assert count==u['bge_tokens']<=256;maxb=max(maxb,count)
            cache[text]=units
        units=cache[text];phase_max_units=max(phase_max_units,len(units));maxunits=max(maxunits,len(units));fallback+=sum(u['token_fallback'] for u in units)
        maxb=max(maxb,len(bge.encode(config['query_prefix']+hyp).ids))
        assert len(nli.encode('',hyp).ids)<=512
        # Every potential anchor with its coherent neighbors is tested directly.
        for i,u in enumerate(units):
            assert len(nli.encode(text[u['start']:u['end']],hyp).ids)<=512
            verify(text,units,[i],hyp);local_anchors+=1
        ids=list(range(len(units)));words=set(re.findall(r'\w+',hyp.casefold()))
        lex=sorted(ids,key=lambda i:(-len(words&set(re.findall(r'\w+',text[units[i]['start']:units[i]['end']].casefold())))/max(1,len(words|set(re.findall(r'\w+',text[units[i]['start']:units[i]['end']].casefold())))),i))
        shuffle=ids.copy();random.Random(20261022).shuffle(shuffle)
        orders=[ids,list(reversed(ids)),lex,shuffle,ids[::2]+ids[1::2]]
        for ranking in orders:verify(text,units,ranking,hyp);local_paths+=1
    anchors+=local_anchors;paths+=local_paths
    stats[phase]={'requests':len(records),'max_units':phase_max_units,'source_document_groups':len({r['source_group'] for r in records}),'all_possible_single_anchors_plus_neighbors_tested':local_anchors,'full_ranking_paths_tested':local_paths,'fallback_units_across_queries':fallback}
assert maxb<=256 and sha(CONTEXT)==source_sha and sha(config_path)==config_sha
result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'context_source_sha256':source_sha,'config_sha256':config_sha,'TRAIN_sha256':sha(phases['train']),'DEV_sha256':sha(phases['development']),'confirmation_sha256':sha(phases['confirmation']),'phases':stats,'possible_anchors_tested':anchors,'bounded_full_ranking_paths_tested':paths,'admission_trace_attempts_retokenized':trace_attempts,'oversize_admissions_rejected':trace_rejections,'max_observed_complete_NLI_pair_tokens':maxn,'max_all144_BGE_sequence_tokens':maxb,'max_observed_native104_context_bytes':maxbytes,'max_source_units':maxunits,'budget_proof':'Sourcechecks before EVERY admission and final rendering imply allrankingpath contexts <=512; everyfrozenunit/query measured rawBGE<=256. Enumeratedall144singleanchors+neighbors plusfivefullorders/input; no exhaustive40!ranking claim. Runtime additionally requires16KiB nativeguard.','source_coverage':'Fullsourceexactcontiguouspartition includingwhitespace, nooffsetdrop/overlap. Oversizedatoms explicitlytokenfallback; allselectedstrings/hash/wholehypothesis/readmissioncounts replayed.','NLI_tokenizer_sha256':sha(nli_path),'BGE_tokenizer_sha256':sha(bge_path),'model_initializations_or_forwards_native_calls':0,'scope':'Tokenizers/sourcepolicy only; no predictions or qualityclaim.'}
p=OUT/'context-capacity-independent-v1.json'
with p.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(p),'stats':stats,'max_pair':maxn,'max_BGE':maxb,'max_bytes':maxbytes}))
