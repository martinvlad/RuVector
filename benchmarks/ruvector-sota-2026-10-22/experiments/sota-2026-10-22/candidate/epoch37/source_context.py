"""Decimal-safe original source-line groups and matched coverage-prefix packing.

No model/data loading or label access. The caller provides actual tokenizers,
actual native/lexical rankings and a source/claim-derived dependency catalogue.
"""
import hashlib
import re

POLICY='rank-prefix-until-source-constraint-coverage-v1'


def _count(tokenizer,text,pair=None):
    return len(tokenizer.encode(text,pair).ids)if pair is not None else len(tokenizer.encode(text).ids)


def line_groups(state):
    if not isinstance(state,str)or not state:raise ValueError('Whole nonempty original source required')
    result=[];start=0;cursor=0
    for line_number,line in enumerate(state.splitlines(keepends=True)):
        cursor+=len(line)
        if line.strip():
            result.append({'group_id':len(result),'start':start,'end':cursor,
                           'line_number':line_number,'source_sha256':None})
            start=cursor
    if not result:raise ValueError('Source has no nonempty line group')
    result[-1]['end']=len(state)
    for row in result:row['source_sha256']=hashlib.sha256(state[row['start']:row['end']].encode()).hexdigest()
    return result


def partition(state,nli,bge,*,target=128,nli_cap=160,bge_cap=256,max_units=40):
    if(target,nli_cap,bge_cap,max_units)!=(128,160,256,40):raise ValueError('Exact frozen source-unit caps required')
    units=[]
    for group in line_groups(state):
        cursor,end=group['start'],group['end']
        stops=[cursor+m.end()for m in re.finditer(r'\S+\s*',state[cursor:end])]
        if not stops or stops[-1]!=end:stops.append(end)
        while cursor<end:
            chosen=None
            for stop in stops:
                if stop<=cursor:continue
                text=state[cursor:stop];nc=_count(nli,text);bc=_count(bge,text)
                if chosen is None:
                    if nc>nli_cap or bc>bge_cap:raise ValueError('An unsplittable source word exceeds unitcap; no clipping')
                    chosen=(stop,nc,bc)
                elif nc<=target and bc<=bge_cap:
                    chosen=(stop,nc,bc)
                else:break
            if chosen is None:raise ValueError('Source partition made no progress')
            stop,nc,bc=chosen
            units.append({'id':len(units),'start':cursor,'end':stop,'group_id':group['group_id'],
                          'line_number':group['line_number'],'source_line_span':[group['start'],group['end']],
                          'nli_tokens':nc,'bge_tokens':bc,'token_fallback':False})
            cursor=stop
    if len(units)>max_units:raise ValueError('Complete source exceeds40units; no dropped tail or fallback')
    groups(state,units)
    return units


def groups(state,units):
    catalogue=line_groups(state);cursor=0
    for row in catalogue:row['unit_ids']=[]
    for i,u in enumerate(units):
        if(type(u.get('group_id'))is not int or not 0<=u['group_id']<len(catalogue)):
            raise ValueError('Unknown source line group')
        g=catalogue[u['group_id']]
        if(u['id']!=i or u['start']!=cursor or not cursor<u['end']<=g['end']or u['start']<g['start']
                or u['source_line_span']!=[g['start'],g['end']]or u['line_number']!=g['line_number']
                or u.get('token_fallback')is not False):raise ValueError('Source-unit/group continuity changed')
        g['unit_ids'].append(i);cursor=u['end']
    if not units or cursor!=len(state)or any(not g['unit_ids']for g in catalogue):
        raise ValueError('Exact complete original source coverage required')
    return catalogue


def selected(state,catalogue,group_ids):
    chosen=[]
    for gid in sorted(group_ids):
        g=catalogue[gid]
        if chosen and chosen[-1][1]==g['start']:chosen[-1][1]=g['end']
        else:chosen.append([g['start'],g['end']])
    return '\n\n'.join(state[a:b]for a,b in chosen),chosen


def covers(spans,required):
    return all(any(a<=s and e<=b for a,b in spans)for s,e in required)


def pack(state,units,ranking,hypothesis,nli,analysis,*,pair_cap=512,rank_depth=None):
    n=len(units);ranking=list(ranking)
    if(rank_depth is None):rank_depth=n
    if(pair_cap!=512 or rank_depth!=n or n>40 or len(ranking)!=n or len(set(ranking))!=n
            or any(type(i)is not int for i in ranking)or set(ranking)!=set(range(n))):
        raise ValueError('Actual complete distinct bounded native/lexical unit ranking required')
    catalogue=groups(state,units);required=analysis['required_source_spans']
    if(analysis['document_sha256']!=hashlib.sha256(state.encode()).hexdigest()
            or analysis['hypothesis_sha256']!=hashlib.sha256(hypothesis.encode()).hexdigest()):
        raise ValueError('Source-only dependency analysis changed input')
    ordered=[];anchors={}
    for uid in ranking:
        gid=units[uid]['group_id']
        if gid not in anchors:ordered.append(gid);anchors[gid]=uid
    admitted=[];trace=[];premise='';spans=[]
    for gid in ordered:
        candidate,candidate_spans=selected(state,catalogue,admitted+[gid]);count=_count(nli,candidate,hypothesis)
        if count>pair_cap:raise ValueError('Required ranked whole source prefix exceeds512; no clipping/fallback')
        admitted.append(gid);premise,spans=candidate,candidate_spans
        trace.append({'group_id':gid,'unit_ids':catalogue[gid]['unit_ids'],'anchor_unit_id':anchors[gid],
                      'source_span':[catalogue[gid]['start'],catalogue[gid]['end']],
                      'candidate_pair_tokens':count,'required_quotes_covered':covers(spans,required)})
        if covers(spans,required):break
    if not admitted or not covers(spans,required):raise ValueError('Ranking failed exact required source coverage')
    chosen=sorted(uid for gid in admitted for uid in catalogue[gid]['unit_ids']);omitted=[i for i in range(n)if i not in set(chosen)]
    audit={'policy':POLICY,'source_line_groups':catalogue,'observed_complete_unit_ranking':ranking,
           'group_ranking_ids':ordered,'selected_group_ids_admission_order':admitted,
           'selected_chunk_ids_source_order':chosen,'selected_chunk_ids_rank_order':[i for i in ranking if i in set(chosen)],
           'selected_source_spans':spans,'omitted_chunk_ids':omitted,
           'omitted_source_spans':[[units[i]['start'],units[i]['end']]for i in omitted],
           'all_selected_groups_complete':True,'whole_group_prefix':True,'packing_attempts':trace,
           'dependency_analysis_sha256':analysis['analysis_sha256'],'required_source_spans':required,
           'all_required_source_quotes_covered':True,'all_source_clauses_parsed':analysis['status']=='CERTIFICATE_CANDIDATE',
           'neutral_catalog_requires_full_source':bool(analysis.get('proof')and analysis['proof']['neutral_requires_entire_source_catalog']),
           'source_text_normalized':False,'joint_pair_tokens':_count(nli,premise,hypothesis),'joint_pair_token_cap':512,
           'selected_evidence_truncated':False,'claim_truncated':False,'selected_token_fallback_unit_ids':[],
           'total_document_chunks':n,'retained_source_characters':sum(b-a for a,b in spans),'document_characters':len(state),
           'document_character_coverage':sum(b-a for a,b in spans)/len(state),
           'premise_sha256':hashlib.sha256(premise.encode()).hexdigest(),'hypothesis_sha256':hashlib.sha256(hypothesis.encode()).hexdigest(),
           'scope':'Identical dependency-complete whole-line-group prefix algorithm for real native and lexical orderings. No missing retrieval proves global source absence; unsupported source requires full supplied context and proof abstention.'}
    return premise,audit
