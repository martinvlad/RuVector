"""Complete selected source evidence and a mechanical coverage audit."""
from __future__ import annotations
import hashlib
import re


def spans_from_offsets(offsets,text_length,window=192,overlap=32,max_chunks=64):
    if not offsets:return [(0,text_length)]
    spans=[]
    for start in range(0,len(offsets),window-overlap):
        end=min(start+window,len(offsets));spans.append((offsets[start][0],offsets[end-1][1]))
        if end==len(offsets):break
    if len(spans)>max_chunks:raise ValueError("More than64 complete source chunks; no hidden clipping")
    return spans


def merge_spans(spans,ids):
    if not ids or len(ids)!=len(set(ids)) or any(type(i) is not int or i<0 or i>=len(spans) for i in ids):raise ValueError("Invalid selected source chunk ids")
    selected=sorted((spans[i] for i in ids),key=lambda x:(x[0],x[1]))
    merged=[]
    for start,end in selected:
        if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
        else:merged.append((start,end))
    return merged


def joint_context(state,spans,ids,hypothesis,tokenizer):
    merged=merge_spans(spans,ids)
    premise="\n\n".join(state[a:b] for a,b in merged)
    encoded=tokenizer.encode(premise,hypothesis)
    if len(encoded.ids)>512:raise ValueError("Complete selected source evidence plus claim exceeds512 tokens; no clipping")
    selected_set=set(ids)
    omitted=[i for i in range(len(spans)) if i not in selected_set]
    numbers=[]
    for match in re.finditer(r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:\s*%|\b)",state):
        retained=any(a<=match.start() and match.end()<=b for a,b in merged)
        numbers.append({"span":[match.start(),match.end()],"text":match.group(),"retained":retained})
    covered=sum(b-a for a,b in merged)
    audit={"selected_chunk_ids_rank_order":list(ids),"selected_chunk_ids_source_order":sorted(ids,key=lambda i:spans[i]),"selected_source_spans":[list(x) for x in merged],"omitted_chunk_ids":omitted,"omitted_chunk_ids_scope":"Not selected as top2; these source chunks may partially overlap retained spans.","total_document_chunks":len(spans),"retained_source_characters":covered,"document_characters":len(state),"document_character_coverage":covered/max(1,len(state)),"selected_evidence_truncated":False,"claim_truncated":False,"joint_pair_tokens":len(encoded.ids),"premise_sha256":hashlib.sha256(premise.encode()).hexdigest(),"hypothesis_sha256":hashlib.sha256(hypothesis.encode()).hexdigest(),"numeric_mentions":numbers,"numeric_mentions_retained":sum(n["retained"] for n in numbers),"numeric_mentions_omitted":sum(not n["retained"] for n in numbers),"scope":"Mechanical source coverage only; omitted text/numbers do not establish insufficient evidence or correctness."}
    return premise,audit
