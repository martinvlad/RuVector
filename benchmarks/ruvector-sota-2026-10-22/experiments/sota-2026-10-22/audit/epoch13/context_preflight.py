"""Tokenizers and source invariants only: zero model/session/addon execution."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,itertools,json,random,re
from tokenizers import Tokenizer

OUT=Path(__file__).resolve().parent;S=OUT.parents[1];PROJECT=S/'epoch13/project'
CONTEXT=S/'candidate/epoch6/context.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
source_sha=sha(CONTEXT)
spec=importlib.util.spec_from_file_location('epoch6_pure_context',CONTEXT);C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
nli_path=PROJECT/'experiments/sota-2026-10-22/candidate/epoch13/assets/official-roberta-base/tokenizer.json'
bge_path=PROJECT/'models/bge-small-en-v1.5/tokenizer.json'
nli=Tokenizer.from_file(str(nli_path));bge=Tokenizer.from_file(str(bge_path));active=nli;active_path=nli_path
for token in [nli,bge]:token.no_padding();token.no_truncation()
assert sha(nli_path)=='2bb1a22cfbe25b8e5a232b7fc4d7fc5073923b45724a5f813b00811bb6620f66'
assert sha(bge_path)=='d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66'
tokenizer_json=json.loads(nli_path.read_text());assert tokenizer_json['model']['type']=='BPE'
assert tokenizer_json['truncation'] is None and tokenizer_json['padding'] is None
assert tokenizer_json['post_processor']=={'type':'RobertaProcessing','sep':['</s>',2],'cls':['<s>',0],'trim_offsets':True,'add_prefix_space':False}
serialization=nli.encode('The alpha agreement.','The beta claim.')
assert serialization.ids[0]==0 and serialization.ids[-1]==2 and all(v==0 for v in serialization.type_ids) and all(v==1 for v in serialization.attention_mask)
assert any(a==b==2 for a,b in zip(serialization.ids,serialization.ids[1:]))
config_path=S/'candidate/epoch6/config.json';config_sha=sha(config_path);config=json.loads(config_path.read_text());assert config['ranking_depth']==40 and config['joint_pair_token_cap']==512
D=S/'legal-transfer/epoch13'
phases={'development':D/'development24.jsonl','confirmation':S/'legal-transfer/epoch9/confirmation48.jsonl'}
# Reconstruct unused-CONF input-only rows from pinned source text/hypothesis and
# metadata hashes. Never parse the confirmation projection or its evaluation labels.
source_path=S/'legal-transfer/epoch3/sources/original-train.json'
assert sha(source_path)=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
source=json.loads(source_path.read_text());docs={d['id']:d['text'] for d in source['documents']}
allow_path=D/'confirmation-allowlist.json';assert sha(allow_path)=='65485b57d37a3341031cd4e125539e6c052f34844a60f93be7f1035db68c913e'
allow=json.loads(allow_path.read_text());assert not allow['contains_labels_or_inputs'] and len(allow['records'])==48
instruction='Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.'
confirmation_inputs=[]
for item in allow['records']:
    document_id=int(item['source_group'].rsplit(':',1)[1]);hypothesis=source['labels'][item['hypothesis_id']]['hypothesis']
    inp={'state':docs[document_id],'questions':{'decision':{'type':'choice','instructions':instruction,'criteria':{'Yes':hypothesis,'No':'The agreement does not establish the following: '+hypothesis}}}}
    encoded=json.dumps(inp,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    assert hashlib.sha256(encoded).hexdigest()==item['input_sha256']
    confirmation_inputs.append({'input':inp,'source_group':item['source_group']})
assert sha(phases['confirmation'])=='850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50'

maxactive=token_sequence_differences=active_admissions=0
maxb=maxn=maxbytes=maxunits=anchors=paths=0;stats={};cache={};trace_attempts=trace_rejections=0

def merge(units,ids):
    spans=[]
    for i in sorted(ids):
        a,b=units[i]['start'],units[i]['end']
        if spans and a==spans[-1][1]:spans[-1]=(spans[-1][0],b)
        else:spans.append((a,b))
    return spans

def verify(text,units,ranking,hyp):
    global maxn,maxbytes,trace_attempts,trace_rejections,maxactive,token_sequence_differences,active_admissions
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
        if step['accepted']:
            pa=nli.encode(candidate,hyp).ids;aa=active.encode(candidate,hyp).ids
            assert len(aa)<=512
            maxactive=max(maxactive,len(aa));token_sequence_differences+=pa!=aa;active_admissions+=1
            selected.append(i)
    spans=merge(units,selected)
    assert premise=='\n\n'.join(text[a:b] for a,b in spans)
    assert audit['selected_chunk_ids_rank_order']==selected and audit['selected_source_spans']==[list(x) for x in spans]
    assert audit['omitted_chunk_ids']==[i for i in range(len(units)) if i not in selected]
    count=len(nli.encode(premise,hyp).ids)
    assert count==audit['joint_pair_tokens']<=512 and not audit['selected_evidence_truncated'] and not audit['claim_truncated']
    assert audit['premise_sha256']==hashlib.sha256(premise.encode()).hexdigest() and audit['hypothesis_sha256']==hashlib.sha256(hyp.encode()).hexdigest()
    aa=active.encode(premise,hyp).ids;pa=nli.encode(premise,hyp).ids
    assert len(aa)<=512;maxactive=max(maxactive,len(aa));token_sequence_differences+=aa!=pa;active_admissions+=1
    assert len(premise.encode())<=16384
    maxn=max(maxn,count);maxbytes=max(maxbytes,len(premise.encode()))

for phase,path in phases.items():
    records=confirmation_inputs if phase=='confirmation' else rows(path);local_anchors=local_paths=0;fallback=0;phase_max_units=0
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
result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'context_source_sha256':source_sha,'config_sha256':config_sha,'DEV_sha256':sha(phases['development']),'confirmation_sha256':sha(phases['confirmation']),'phases':stats,'possible_anchors_tested':anchors,'bounded_full_ranking_paths_tested':paths,'admission_trace_attempts_retokenized':trace_attempts,'oversize_admissions_rejected':trace_rejections,'max_observed_complete_NLI_pair_tokens':maxn,'max_all72_BGE_sequence_tokens':maxb,'max_observed_native104_context_bytes':maxbytes,'max_source_units':maxunits,'budget_proof':'Sourcechecks before EVERY admission and final rendering imply allrankingpath contexts <=512; everyfrozenunit/query measured rawBGE<=256. Enumeratedall72singleanchors+neighbors plusfivefullorders/input; no exhaustive40!ranking claim. Runtime additionally requires16KiB nativeguard.','source_coverage':'Fullsourceexactcontiguouspartition includingwhitespace, nooffsetdrop/overlap. Oversizedatoms explicitlytokenfallback; allselectedstrings/hash/wholehypothesis/readmissioncounts replayed.','NLI_tokenizer_sha256':sha(nli_path),'BGE_tokenizer_sha256':sha(bge_path),'active_model_tokenizer_sha256':sha(active_path),'active_model_max_complete_pair_tokens':maxactive,'active_model_accepted_context_checks':active_admissions,'active_policy_token_sequence_differences':token_sequence_differences,'tokenizer_budget_adapter':{'algorithm_unchanged':True,'historical_policy_tokenizer_unchanged':False,'historical_context_strings_identical':False,'new_BPE_governs_partition_packing_decoding':True,'same_active_tokenizer_feed_and_packing':True,'raw_padding_truncation_disabled':True,'pair_format':'<s>premise</s></s>hypothesis</s>','class_mapping':'C0/E1/N2'},'no_confirmation_labels_accessed_for_checks':True,'unused_confirmation_projection_parsed':False,'confirmation_input_only_reconstruction_allowlist_sha256':sha(allow_path),'model_initializations_or_forwards_native_calls':0,'scope':'Tokenizers/sourcepolicy only; no predictions or qualityclaim.'}
p=OUT/'context-capacity-independent-v1.json'
with p.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(p),'stats':stats,'max_pair':maxn,'max_BGE':maxb,'max_bytes':maxbytes}))
