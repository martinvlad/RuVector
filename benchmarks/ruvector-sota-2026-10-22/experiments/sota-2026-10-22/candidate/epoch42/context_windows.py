"""Prospective exact-source context heuristic; no claim of semantic completeness.

Catalog spans partition every source character. Punctuation boundaries are
heuristic; no clause is certified and no missing selected span implies absence.
The caller supplies an actual no-truncation pair-token count, never gold/model
predictions. Packing is identical for all three frozen ranking arms.
"""
import hashlib
import re

MAX_UNITS=1024
MAX_DOCUMENT_BYTES=1048576
MAX_UNIT_BYTES=262144
MAX_CLAIM_BYTES=65536
MAX_JOINT_TOKENS=512
SEPARATOR='\n\n'
ABBREVIATIONS=frozenset(('mr.','mrs.','ms.','dr.','prof.','inc.','ltd.','corp.',
    'co.','vs.','no.','sec.','art.','e.g.','i.e.','u.s.','u.k.'))


def sha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()


def sentence_catalog(document):
    if type(document)is not str or not document.strip():raise ValueError('SOURCE_DOCUMENT_EMPTY_OR_TYPE')
    if len(document.encode('utf-8'))>MAX_DOCUMENT_BYTES:raise ValueError('SOURCE_DOCUMENT_CAP')
    boundaries=[];length=len(document)
    for match in re.finditer(r'[.!?]',document):
        at=match.start();mark=document[at]
        if mark=='.':
            if at>0 and at+1<length and document[at-1].isdigit()and document[at+1].isdigit():continue
            token=re.search(r'[A-Za-z.]+\.$',document[:at+1])
            word=token.group().lower()if token else ''
            if word in ABBREVIATIONS or re.fullmatch(r'[a-z]\.',word):continue
        end=at+1
        while end<length and document[end]in '\"\'”’)]}':end+=1
        if end<length and not document[end].isspace():continue
        while end<length and document[end].isspace():end+=1
        if end<length:boundaries.append(end)
    boundaries=sorted(set([0,*boundaries,length]));spans=[]
    for start,end in zip(boundaries,boundaries[1:]):
        text=document[start:end]
        if not text:continue
        if len(text.encode('utf-8'))>MAX_UNIT_BYTES:raise ValueError('SOURCE_UNIT_CAP_NO_SPLITTING')
        spans.append({'unit_id':len(spans),'start':start,'end':end,'sentence':text})
    if len(spans)>MAX_UNITS:raise ValueError('SOURCE_UNIT_COUNT_CAP')
    if ''.join(row['sentence']for row in spans)!=document:raise AssertionError('SOURCE_PARTITION')
    return spans


def validate_spans(spans):
    if type(spans)is not list or not 1<=len(spans)<=MAX_UNITS:raise ValueError('SOURCE_UNIT_COUNT_CAP')
    end=0
    for index,row in enumerate(spans):
        if (set(row)!={'unit_id','start','end','sentence'}or type(row['unit_id'])is not int
            or row['unit_id']!=index or type(row['start'])is not int or type(row['end'])is not int
            or row['start']!=end or type(row['sentence'])is not str or not row['sentence']
            or row['end']!=row['start']+len(row['sentence'])):raise ValueError('NONCONTIGUOUS_SOURCE_CATALOG')
        if len(row['sentence'].encode('utf-8'))>MAX_UNIT_BYTES:raise ValueError('SOURCE_UNIT_CAP_NO_SPLITTING')
        end=row['end']
    if len(''.join(row['sentence']for row in spans).encode('utf-8'))>MAX_DOCUMENT_BYTES:raise ValueError('SOURCE_DOCUMENT_CAP')


def lexical_order(spans,claim):
    query=set(re.findall(r'\w+',claim.lower()))
    def key(row):
        terms=set(re.findall(r'\w+',row['sentence'].lower()));union=query|terms
        return (-(len(query&terms)/len(union)if union else 0),row['unit_id'])
    return [row['unit_id']for row in sorted(spans,key=key)]


def build_windows(spans,ranking,claim,pair_token_count):
    """Two deterministic packets; all token-count invocations are caller-audited."""
    validate_spans(spans)
    if type(claim)is not str or not claim.strip()or len(claim.encode('utf-8'))>MAX_CLAIM_BYTES:
        raise ValueError('CLAIM_CAP_OR_EMPTY')
    if type(ranking)is not list or any(type(i)is not int for i in ranking)or sorted(ranking)!=list(range(len(spans))):
        raise ValueError('RANKING_NOT_EXACT_FULL_SOURCE_PERMUTATION')
    calls=0
    def count(ids):
        nonlocal calls
        calls+=1;value=pair_token_count(SEPARATOR.join(spans[i]['sentence']for i in sorted(ids)),claim)
        if type(value)is not int or value<1:raise ValueError('PAIR_TOKEN_COUNT_NOT_POSITIVE_INTEGER')
        return value
    if count([])>MAX_JOINT_TOKENS:raise ValueError('CLAIM_CANNOT_FIT_WITH_SPECIAL_TOKENS')
    windows=[];first=set()
    for number in range(2):
        selected=set();accepted=[];receipts=[]
        for anchor in ranking:
            if number==1 and anchor in first:
                receipts.append({'anchor':anchor,'status':'ANCHOR_ALREADY_REPRESENTED_IN_FIRST'});continue
            group=set(range(max(0,anchor-1),min(len(spans),anchor+2)))
            if group<=selected:
                receipts.append({'anchor':anchor,'status':'GROUP_ALREADY_REPRESENTED'});continue
            proposed=selected|group;tokens=count(proposed)
            if tokens>MAX_JOINT_TOKENS:
                receipts.append({'anchor':anchor,'status':'WHOLE_GROUP_SKIPPED_TOKEN_OVERFLOW',
                    'group_unit_ids':sorted(group),'proposed_joint_tokens':tokens});continue
            selected=proposed;accepted.append(anchor)
            receipts.append({'anchor':anchor,'status':'WHOLE_GROUP_ACCEPTED','group_unit_ids':sorted(group),
                'proposed_joint_tokens':tokens})
        duplicate=False
        if not selected:
            if number==0:raise ValueError('NO_COMPLETE_NEIGHBOR_GROUP_FITS_NO_REPLACEMENT')
            selected=set(first);duplicate=True
        ids=sorted(selected);text=SEPARATOR.join(spans[i]['sentence']for i in ids);tokens=count(ids)
        if not ids or tokens>MAX_JOINT_TOKENS:raise AssertionError('PACKED_WINDOW_INTEGRITY')
        windows.append({'window_index':number,'selected_unit_ids':ids,'accepted_anchor_ids':accepted,
            'source_spans':[{'unit_id':i,'start':spans[i]['start'],'end':spans[i]['end'],
                'sha256':sha(spans[i]['sentence'])}for i in ids],
            'premise':text,'premise_sha256':sha(text),'joint_tokens':tokens,
            'duplicate_first_window':duplicate,'selection_receipts':receipts,
            'source_character_coverage':sum(len(spans[i]['sentence'])for i in ids)/spans[-1]['end'],
            'source_units_total':len(spans),'selected_source_units':len(ids),
            'selection_is_not_a_proof_of_absence':True,'premise_truncated':False,'span_splits':0})
        if number==0:first=set(selected)
    return {'windows':windows,'packing_pair_tokenizer_calls':calls,
        'duplicate_window_count':sum(w['duplicate_first_window']for w in windows),
        'union_selected_unit_ids':sorted(set(windows[0]['selected_unit_ids'])|set(windows[1]['selected_unit_ids']))}
