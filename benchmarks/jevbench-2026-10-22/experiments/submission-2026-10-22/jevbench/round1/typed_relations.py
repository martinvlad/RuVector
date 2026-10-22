"""Finite source-linked joins over supplied current JSON records.

Inference has no dataset, metadata, filesystem, network, or answer-table access.
Unsupported, contradictory, incomplete or ambiguous inputs return None.
"""
import datetime as dt
import json
import math
import re


class Source:
    def __init__(self, text):
        self.text=text;self.spans={};self.used={};self.trace=[]
        decoder=json.JSONDecoder()
        def white(i):
            while i<len(text) and text[i].isspace():i+=1
            return i
        def parse(i,path):
            i=white(i);start=i
            if text[i]=='{':
                result={};i=white(i+1)
                while text[i]!='}':
                    key,j=decoder.raw_decode(text,i)
                    if not isinstance(key,str) or key in result:raise ValueError('Ambiguous key')
                    i=white(j)
                    if text[i]!=':':raise ValueError('Missing colon')
                    result[key],i=parse(i+1,path+(key,));i=white(i)
                    if text[i]=='}':break
                    if text[i]!=',':raise ValueError('Missing comma')
                    i=white(i+1)
                value=result;end=i+1
            elif text[i]=='[':
                value=[];i=white(i+1)
                while text[i]!=']':
                    part,i=parse(i,path+(len(value),));value.append(part);i=white(i)
                    if text[i]==']':break
                    if text[i]!=',':raise ValueError('Missing comma')
                    i=white(i+1)
                end=i+1
            else:value,end=decoder.raw_decode(text,i)
            self.spans[path]=(start,end);return value,end
        self.data,end=parse(0,())
        if white(end)!=len(text) or not isinstance(self.data,dict):raise ValueError('Object required')
    def get(self,*path):
        if not path or path[0]=='archive':raise ValueError('No archive facts')
        value=self.data
        for key in path:value=value[key]
        start,end=self.spans[path]
        self.used[path]={'path':list(path),'json_pointer':'/'+('/'.join(str(x).replace('~','~0').replace('/','~1') for x in path)),
            'span':[start,end],'text':self.text[start:end],'value':value}
        return value
    def step(self,operation,result,**inputs):
        self.trace.append({'operation':operation,'inputs':inputs,'result':result});return result
    def finish(self,grammar,label,question):
        return {'rule':'explicit_typed_relation_join','grammar':grammar,'decision':label,
            'source_facts':list(self.used.values()),'trace':self.trace,'criteria':dict(question['criteria']),
            'instructions':question.get('instructions',''),'archive_used':False,
            'source_span_unit':'Python Unicode character offsets in normalized supplied state',
            'calibration_claim':False}


def number(value):
    if type(value) not in [int,float] or not math.isfinite(value):raise ValueError('Finite number required')
    return value


def full(pattern,text):
    if not isinstance(text,str):raise ValueError('Text required')
    match=re.fullmatch(pattern,text,re.I)
    if match is None:raise ValueError('Unsupported grammar')
    return match


def label_for(question,pattern):
    matches=[key for key,value in question['criteria'].items() if isinstance(value,str) and re.fullmatch(pattern,value,re.I)]
    if len(matches)!=1:raise ValueError('Ambiguous or missing label')
    return matches[0]


def admission(source,q):
    required={'admission_table','application','catalog','equivalencies','footnotes','sequence','track_codes','transcript'}
    if not required<=source.data.keys() or not source.data.keys()<=required|{'archive'}:return None
    alias=source.get('application','course_alias');course=full(r'course ([\w-]+), ([\w -]+) section',source.get('catalog',alias))
    course_id,section=course.groups();source.step('exact_course_alias',course_id,alias=alias,section=section)
    track_name=source.get('application','applicant_track');track=source.get('track_codes',track_name)
    source.step('exact_track_alias',track,alias=track_name)
    row=full(r'score (\d+); prerequisite ([\w-]+) within (\d+) months\^([\w]+)',source.get('admission_table',course_id))
    score_min,required,months_max,marker=row.groups();score_min=int(score_min);months_max=int(months_max)
    pre=full(r'([\w-]+) completed (\d+) months ago',source.get('application','prerequisite'));code,months=pre[1],int(pre[2])
    equivalent=source.get('equivalencies',code);source.step('exact_prerequisite_equivalence',equivalent,code=code,required=required)
    foot=full(r'For ([\w-]+) applicants to an ([\w -]+) section, score threshold is (\d+) and prerequisite recency is (\d+) months if prior grade was ([ABCDF]) or higher\.',source.get('footnotes',marker))
    grade=source.get('transcript',code+' grade')
    if grade not in ['A','B','C','D','F']:raise ValueError('Unknown grade ordering')
    adjusted=(track==foot[1] and section.casefold()==foot[2].casefold() and 'ABCDF'.index(grade)<='ABCDF'.index(foot[5].upper()))
    if adjusted:score_min,months_max=int(foot[3]),int(foot[4])
    source.step('conditional_footnote_precedence',{'minimum_score':score_min,'maximum_age_months':months_max},applicable=adjusted,track=track,section=section,grade=grade)
    full(r'Resolve course and track aliases, equivalency, section qualifier, then footnote\.',source.get('sequence'))
    score=number(source.get('application','score'));assert 0<=score<=100
    score_ok=score>=score_min;pre_ok=equivalent==required and months<=months_max
    source.step('conjunction',score_ok and pre_ok,score_ok=score_ok,prerequisite_ok=pre_ok,score=score,months=months)
    if score_ok and pre_ok:pattern=r'All (?:adjusted )?requirements are met\.'
    elif score_ok and not pre_ok:pattern=r'Applicable prerequisite or recency fails\.'
    elif pre_ok and not score_ok:pattern=r'Applicable score threshold is missed\.'
    else:return None
    return source.finish('current_course_track_equivalence_footnote',label_for(q,pattern),q)


def calendar_date(text):
    try:return dt.date.fromisoformat(text)
    except ValueError:return dt.datetime.strptime(text,'%d %B %Y').date()


def incident(source,q):
    required={'asset_catalog','clock_rule','footnotes','incident','ownership','routing','severity_matrix','team_aliases'}
    if not required<=source.data.keys() or not source.data.keys()<=required|{'archive','memo'}:return None
    asset=source.get('incident','asset_name');asset_id=source.get('asset_catalog',asset);owner=source.get('ownership',asset_id)
    source.step('exact_asset_owner',owner,asset=asset,asset_id=asset_id)
    event=source.get('incident','event')
    keys=[key for key in source.get('severity_matrix') if re.match(r'^'+re.escape(key.replace('_',' '))+r'(?:\b|$)',event,re.I)]
    if len(keys)!=1:return None
    row=full(r'(S\d+) unless footnote ([\w]+)',source.get('severity_matrix',keys[0]));base,marker=row.groups()
    foot=full(r'For assets owned by a (Q\d+) team, exposure fully contained within (\d+) minutes with no observed access is (S\d+)\.',source.get('footnotes',marker))
    target_queue,maximum,alternate=foot[1],int(foot[2]),foot[3]
    rename=full(r'Team (.+?) beginning (\d{1,2} [A-Za-z]+ \d{4}); before then it is not a (Q\d+) team',source.get('team_aliases',owner))
    date=calendar_date(source.get('incident','date'));effective=calendar_date(rename[2])
    if rename[3]!=target_queue:return None
    queue_row=source.get('team_aliases',rename[1]);queue=full(r'.*\bqueue (Q\d+)',queue_row)[1]
    if queue!=target_queue:return None
    eligible_team=date>=effective
    source.step('effective_dated_alias',eligible_team,owner=owner,renamed_team=rename[1],incident_date=date.isoformat(),effective_date=effective.isoformat(),queue=queue)
    full(r'Elapsed minutes use detection to completed containment\.',source.get('clock_rule'))
    start=dt.datetime.strptime(source.get('incident','detected'),'%H:%M');end=dt.datetime.strptime(source.get('incident','containment'),'%H:%M')
    if end<start:return None
    minutes=int((end-start).total_seconds()/60)
    access=source.get('incident','data_access')
    if access not in ['none observed','access observed','observed access']:return None
    applicable=eligible_team and minutes<=maximum and access=='none observed'
    severity=alternate if applicable else base
    source.step('dated_conditional_severity',severity,team_eligible=eligible_team,elapsed_minutes=minutes,maximum_minutes=maximum,no_observed_access=access=='none observed')
    route=source.get('routing',severity);source.step('exact_severity_routing',route,severity=severity)
    label=label_for(q,r'Severity '+re.escape(severity)+r' (?:routing|owned by '+re.escape(rename[1])+r'/'+re.escape(queue)+r')\.')
    return source.finish('effective_dated_team_alias_clock_severity_routing',label,q)


def maintenance(source,q):
    required={'asset_map','bypass_log','calculation_rule','fault_map','footnotes','maintenance','response_table'}
    if not required<=source.data.keys() or not source.data.keys()<=required|{'archive'}:return None
    alias=source.get('maintenance','machine_alias');asset=full(r'press ([\w-]+), generation ([\w-]+)',source.get('asset_map',alias))
    code=source.get('maintenance','fault_code');fault=full(r'(.+), class ([\w-]+)',source.get('fault_map',code));category=fault[2]
    source.step('exact_asset_fault_joins',{'asset':asset[1],'generation':asset[2],'fault_class':category},machine_alias=alias,fault_code=code)
    row=full(r'local maintenance if under (\d+) minutes; central engineering otherwise([*])',source.get('response_table','class_'+category));threshold=int(row[1])
    foot=full(r'For ([\w-]+) presses on ([\w-]+) shift, approved bypass time is excluded from downtime when bypass restores safe operation\.',source.get('footnotes',row[2]))
    shift=source.get('maintenance','shift');temporary=source.get('maintenance','temporary_bypass');approved=source.get('bypass_log','approved');safe=source.get('bypass_log','restored_safe_operation')
    if any(type(value) is not bool for value in [temporary,approved,safe]):return None
    # A failed-safe bypass may trigger a separate safety rule outside this grammar.
    if temporary and not safe:return None
    downtime=number(source.get('maintenance','downtime_minutes'));duration=number(source.get('bypass_log','duration_minutes'))
    if downtime<0 or duration<0 or duration>downtime:return None
    qualifies=asset[2]==foot[1] and shift.casefold()==foot[2].casefold() and temporary and approved and safe
    adjusted=downtime-duration if qualifies else downtime
    calculation=full(r"Subtract only qualifying bypass duration before comparing 'under (\d+)'; exactly (\d+) is not under\.",source.get('calculation_rule'))
    if int(calculation[1])!=threshold or int(calculation[2])!=threshold:return None
    source.step('qualified_duration_subtraction',adjusted,qualifies=qualifies,downtime=downtime,bypass_duration=duration)
    below=adjusted<threshold;source.step('strict_numeric_threshold',below,adjusted_minutes=adjusted,threshold_minutes=threshold)
    qualifier='under' if below else 'at least'
    label=label_for(q,r'Adjusted downtime is '+qualifier+r' '+str(threshold)+r' minutes\.')
    return source.finish('machine_fault_qualifying_bypass_strict_threshold',label,q)


def solve(state,question):
    if not isinstance(state,str) or not isinstance(question,dict) or question.get('type')!='choice' or not isinstance(question.get('criteria'),dict):return None
    candidates=[]
    for grammar in [admission,incident,maintenance]:
        try:
            source=Source(state);answer=grammar(source,question)
            if answer is not None:candidates.append(answer)
        except (ValueError,TypeError,KeyError,IndexError,AssertionError,OverflowError,RecursionError):
            continue
    return candidates[0] if len(candidates)==1 else None
