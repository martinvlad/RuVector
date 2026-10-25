"""Independent exact source group and fixed mandatory/definition packing replay.

No candidate implementation or tokenizer is imported. Source boundaries,
qualifier groups, lexical/native group selection, admitted full groups, and
numeric provenance are rederived. Token-budget branch arithmetic is replayed
from observed token-count receipts; actual tokenizer counts are source-bound
worker observations, not independently retokenized by this stdlib auditor.
"""
import re
from data_common import require,digest
POLICY='mandatory-two-groups-before-optional-definitions-v1'
PARAGRAPH=re.compile(r'(?:\r?\n)[ \t]*(?:\r?\n)+')
SENTENCE=re.compile(r'[.!?;][\"\'\)\]]*(?:\s+|$)')
BULLET=re.compile(r'^\s*(?:(?:\([a-zA-Z0-9]+\)|[a-zA-Z0-9]+[.)])\s+)?')
QUALIFIER=re.compile(r'^(?:provided\b|however\b|except\b|unless\b|notwithstanding\b|subject\s+to\b|in\s+(?:such|that)\s+(?:case|event)\b|in\s+(?:the\s+)?event\b|such\s+(?:disclosure|information|copies|copy)\b|any\s+such\b|only\b|to\s+the\s+extent\b|upon\b|at\s+(?:the\s+|a\s+)?request\b|and\s+(?:only|provided)\b|but\b)',re.IGNORECASE)
DEFINITION=re.compile(r'(?:\bhereinafter\b|\breferred\s+to\s+as\b|\bdefined\s+as\b|["“][^"”\r\n]{1,80}["”]\s*(?:shall\s+)?(?:means?|includes?)\b)',re.IGNORECASE)
NAMED=re.compile(r'''\([^()\r\n]{0,96}["“‘']\s*(?:(?:confidential|proprietary|non[\s\-\u2010-\u2015]*public)[\s\-\u2010-\u2015]+information|data[\s\-\u2010-\u2015]+recipient|receiving[\s\-\u2010-\u2015]+party|disclosing[\s\-\u2010-\u2015]+party|vendor|recipient)\s*["”’'][^()\r\n]{0,32}\)''',re.IGNORECASE)
BETWEEN=re.compile(r'\bbetween\b',re.IGNORECASE)
PARTY=re.compile(r'\b(?:agreement|parties|party|recipient|disclosing|receiving)\b',re.IGNORECASE)
def merged(units,ids):
    spans=[]
    for i in sorted(set(ids)):
        a,b=units[i]['start'],units[i]['end']
        if spans and a==spans[-1][1]:spans[-1][1]=b
        else:spans.append([a,b])
    return spans
def source_groups(source,units):
    # Independently scan paragraph/sentence terminators and prefix qualifier
    # attachment. Boundaries are whole original character spans.
    paras=[m.end()for m in PARAGRAPH.finditer(source)]
    if not paras or paras[-1]!=len(source):paras.append(len(source))
    atoms=[];start=0;gid=-1
    for paragraph,end in enumerate(paras):
        stops=[start+m.end()for m in SENTENCE.finditer(source[start:end])]
        if not stops or stops[-1]!=end:stops.append(end)
        cursor=start
        for stop in stops:
            if stop<=cursor:continue
            prefix=BULLET.sub('',source[cursor:stop],count=1)
            attached=bool(atoms and atoms[-1]['paragraph_id']==paragraph and QUALIFIER.search(prefix))
            if not attached:gid+=1
            atoms.append({'sentence_id':len(atoms),'start':cursor,'end':stop,'paragraph_id':paragraph,'group_id':gid,'qualifier_attached':attached});cursor=stop
        start=end
    require(bool(units)and len(units)<=192,'Complete bounded source-unit partition required')
    catalogue=[];cursor=0;seen_sentences=set()
    for i,u in enumerate(units):
        sid=u.get('sentence_id');require(type(sid)is int and 0<=sid<len(atoms),'Source unit unknown sentence')
        atom=atoms[sid]
        require(u['id']==i and u['start']==cursor and type(u['end'])is int and cursor<u['end']<=atom['end']
                and atom['start']<=u['start'] and u['sentence_span']==[atom['start'],atom['end']]
                and all(u[k]==atom[k]for k in('paragraph_id','group_id','qualifier_attached')),'Independent source atom/unit/group metadata differs')
        require(type(u['token_fallback'])is bool,'Missing source split fallback observation')
        if not catalogue or catalogue[-1]['group_id']!=atom['group_id']:
            require(atom['group_id']==len(catalogue),'Dense contiguous source groups required')
            catalogue.append({'group_id':atom['group_id'],'start':u['start'],'end':u['end'],'paragraph_id':atom['paragraph_id'],'unit_ids':[],'sentence_ids':[],'qualifier_sentence_ids':[],'token_fallback':False})
        group=catalogue[-1];group['end']=u['end'];group['unit_ids'].append(i)
        if sid not in group['sentence_ids']:group['sentence_ids'].append(sid)
        if atom['qualifier_attached']and sid not in group['qualifier_sentence_ids']:group['qualifier_sentence_ids'].append(sid)
        group['token_fallback']|=u['token_fallback'];seen_sentences.add(sid);cursor=u['end']
    require(cursor==len(source)and seen_sentences==set(range(len(atoms))),'Source group catalogue tail or sentence coverage lost')
    return catalogue

def prelude_check(source,units,catalogue,prelude):
    selected=[];group_ids=[];attempts=prelude['candidate_attempts'];seen=0
    for group in catalogue:
        a,b=group['start'],group['end'];text=source[a:b];triggers=[]
        if DEFINITION.search(text):triggers.append('explicit-definition-marker')
        if NAMED.search(text):triggers.append('explicit-quoted-named-term-parenthetical')
        initial=source[a:min(b,2048)]
        if a<2048 and BETWEEN.search(initial)and PARTY.search(initial):triggers.append('initial-party-declaration')
        if not triggers:continue
        require(seen<len(attempts),'Missing source definition candidate observation')
        row=attempts[seen];seen+=1;count=row['candidate_priority_tokens']
        require(type(count)is int and count>=0,'Invalid recorded definition token count')
        accepted=not group['token_fallback']and count<=160
        expect={'group_id':group['group_id'],'unit_ids':group['unit_ids'],'span':[a,b],'source_sha256':digest(text.encode()),'triggers':triggers,'candidate_priority_tokens':count,'accepted':accepted,'reason':'admitted-whole-source-group'if accepted else'fallback-or-whole-group-exceeds160'}
        require(row==expect,'Independent source definition trigger or count-decision replay differs')
        if accepted:selected.extend(group['unit_ids']);group_ids.append(group['group_id'])
    require(seen==len(attempts),'Extra definition candidate attempt')
    spans=merged(units,selected);premise='\n\n'.join(source[a:b]for a,b in spans)
    count=prelude['priority_tokens'];require(type(count)is int and 0<=count<=160,'Shared definition prelude token cap differs')
    expected={'policy':POLICY+':claim-independent-whole-group-definition-priority','selected_unit_ids':selected,'selected_group_ids':group_ids,'selected_source_spans':spans,'priority_tokens':count,'priority_token_cap':160,'priority_text_sha256':digest(premise.encode()),'candidate_attempts':attempts,'whole_groups_only':True,'token_fallback_admitted':False,'claim_dependent':False,'literal_first_text_guaranteed':False}
    require(prelude==expected,'Independent shared source definition prelude differs')
    return group_ids

def context_check(source,units,catalogue,ranking,context,prelude):
    require(context['policy']==POLICY and context['source_sentence_groups']==catalogue
            and context['qualifier_regex']==QUALIFIER.pattern and context['bullet_regex']==BULLET.pattern,
            'Frozen shared source-group policy/catalogue differs')
    require(context['definition_priority']==prelude and context['definition_admission_priority']=='after-both-mandatory-ranked-groups','Definitions must follow mandatory evidence under identical shared prelude')
    order=[];anchors={}
    for unit in ranking:
        gid=units[unit]['group_id']
        if gid not in anchors:order.append(gid);anchors[gid]=unit
    mandatory=order[:2];require(len(mandatory)==min(2,len(catalogue)),'Actual ranking lacks mandatory distinct groups')
    require(context['group_ranking_ids']==order and context['group_ranking_anchor_unit_ids']==[anchors[g]for g in order]
            and context['mandatory_ranked_group_ids']==mandatory and context['mandatory_ranked_anchor_unit_ids']==[anchors[g]for g in mandatory]
            and context['mandatory_ranked_group_cap']==2 and context['single_group_degenerate']is(len(catalogue)==1),
            'First2 distinct complete source groups changed')
    selected=[];selected_groups=[];optional=[];trace=context['packing_attempts'];at=0
    for gid in mandatory:
        group=catalogue[gid];require(at<len(trace),'Mandatory group trace missing');row=trace[at];at+=1;count=row['candidate_pair_tokens']
        require(type(count)is int and 0<count<=512,'Mandatory complete groups must fit512truejointtokens')
        require(row=={'group_id':gid,'unit_ids':group['unit_ids'],'role':'mandatory-ranked-group','anchor':anchors[gid],'source_span':[group['start'],group['end']],'candidate_pair_tokens':count,'accepted':True,'all_group_units_admitted_together':True},'Mandatory group trace differs')
        selected.extend(group['unit_ids']);selected_groups.append(gid)
    for gid in prelude['selected_group_ids']:
        if gid in selected_groups:continue
        group=catalogue[gid];require(at<len(trace),'Optional definition trace missing');row=trace[at];at+=1;count=row['candidate_pair_tokens']
        require(type(count)is int and count>0,'Invalid optional observed pairtoken count');accepted=count<=512
        require(row=={'group_id':gid,'unit_ids':group['unit_ids'],'role':'optional-definition-after-mandatory','anchor':None,'source_span':[group['start'],group['end']],'candidate_pair_tokens':count,'accepted':accepted,'all_group_units_admitted_together':accepted},'Optional definition count-decision trace differs')
        if accepted:selected.extend(group['unit_ids']);selected_groups.append(gid);optional.append(gid)
    require(at==len(trace),'Extra/filler/neighbor admission forbidden')
    spans=merged(units,selected);omitted=[u['id']for u in units if u['id']not in set(selected)];covered=sum(b-a for a,b in spans)
    require(context['optional_definition_group_ids_admitted']==optional and context['selected_group_ids_admission_order']==selected_groups
            and context['all_selected_groups_complete']is True and context['selected_chunk_ids_rank_order']==selected
            and context['selected_chunk_ids_source_order']==sorted(selected)and context['selected_source_spans']==spans
            and context['additional_neighbor_unit_ids_inspected']==[]and context['omitted_chunk_ids']==omitted
            and context['omitted_source_spans']==[[units[i]['start'],units[i]['end']]for i in omitted]
            and context['total_document_chunks']==len(units)and context['retained_source_characters']==covered
            and context['document_characters']==len(source)and context['document_character_coverage']==covered/len(source),
            'Whole mandatory/optional-only context coverage or omission replay differs')
    require(context['ranking_depth']==context['ranked_anchor_candidate_cap']==len(ranking)==min(40,len(units))
            and context['joint_pair_token_cap']==512 and context['selected_token_fallback_unit_ids']==[i for i in selected if units[i]['token_fallback']],
            'Frozen source group/rank/token budget differs')
    return {'mandatory_group_ids':mandatory,'optional_definition_group_ids':optional,'source_groups':len(catalogue),'original_document_character_coverage':covered/len(source),'full_document_context':covered==len(source),'token_budget_replay_scope':'Observed source-bound token count decisions; no independent retokenization/model calls'}
