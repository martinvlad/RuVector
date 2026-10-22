"""Conservative exact probability operations over explicit supplied facts.

No dataset, metadata, answer key, model, or external I/O is used here. Supported
grammars are deliberately finite. Any missing/ambiguous fact returns None.
"""
from fractions import Fraction
import re


def exact(value):
    return [value.numerator,value.denominator]


def span(state,match,role):
    return {'role':role,'span':[match.start(),match.end()],'text':match.group()}


def unique(pattern,text,flags=re.I):
    values=list(re.finditer(pattern,text,flags))
    return values[0] if len(values)==1 else None


def node(operation,inputs,value):
    return {'operation':operation,'inputs':inputs,'fraction':exact(value)}


def independent_connection(state,q):
    if q.get('type')!='noul':return None
    criteria=q.get('criteria',{})
    if set(criteria)!={'true','false'}:return None
    polarity={}
    for label,meaning in criteria.items():
        if len(re.findall(r'\b(?:make|makes|miss|misses)\b',meaning,re.I))!=1:return None
        makes=bool(re.search(r'\bmakes? the connection\b',meaning,re.I))
        misses=bool(re.search(r'\bmiss(?:es)? the connection\b',meaning,re.I))
        if makes==misses:return None
        polarity[label]='make' if makes else 'miss'
    if len(set(polarity.values()))!=2:return None
    instruction=q.get('instructions','')
    if len(re.findall(r'\b(?:make|miss)\b',instruction,re.I))!=1:return None
    asks_miss=bool(re.search(r'\bmiss the connection\b',instruction,re.I))
    asks_make=bool(re.search(r'\bmake the connection\b',instruction,re.I))
    if asks_miss==asks_make or polarity['true']!=('miss' if asks_miss else 'make'):return None
    rule=unique(r'Connection rule[^\n]*with the outbound on time, the passenger makes the connection if the inbound arrives no more than (\d+) minutes late\. If the outbound departs at least (\d+) minutes late, the passenger makes it if the inbound arrives no more than (\d+) minutes late\. The outbound never departs early\.',state)
    evidence=unique(r'Inbound ([^,\n]+), last (\d+) operations[^:\n]*: (\d+) arrived no more than (\d+) minutes late; (\d+) arrived between (\d+) and (\d+) minutes late; (\d+) arrived more than (\d+) minutes late\.',state)
    branch=unique(r'Outbound ([^:\n]+): departs at least (\d+) minutes late on (\d+(?:\.\d+)?)% of days, otherwise on time \(within (\d+) minutes\)\.',state)
    independence=unique(r'The two flights[’\'] delays are independent[^.]*\.',state)
    itinerary=unique(r'Itinerary: inbound flight (.+?) scheduled to arrive[^;\n]*; outbound flight (.+?) scheduled to depart[^.\n]*\.',state)
    if not all([rule,evidence,branch,independence,itinerary]):return None
    if re.search(r'\b(?:not independent|dependent delays|delays are dependent)\b',state,re.I):return None
    a,delay,b=map(int,rule.groups());in_id,n,nshort,ea,nmiddle,low,eb,nlong,ec=evidence.groups()
    out_id,out_delay,rate,otherwise=branch.groups()
    n,nshort,ea,nmiddle,low,eb,nlong,ec=map(int,[n,nshort,ea,nmiddle,low,eb,nlong,ec])
    if itinerary[1].strip()!=in_id.strip() or itinerary[2].strip()!=out_id.strip():return None
    if not (0<=a<b and a==ea and b==eb==ec and low==a+1 and int(out_delay)==delay and int(otherwise)<delay):return None
    if n<=0 or nshort+nmiddle+nlong!=n:return None
    late=Fraction(rate)/100
    if not 0<=late<=1:return None
    ontime=1-late;short=Fraction(nshort,n);extended=Fraction(nshort+nmiddle,n)
    first=ontime*short;second=late*extended;make=first+second;miss=1-make
    true=make if polarity['true']=='make' else miss
    return {'rule':'exact_explicit_independent_conditional_mixture','probabilities':{'yes':float(true),'no':float(1-true)},
        'exact_probability_fractions':{'yes':exact(true),'no':exact(1-true)},
        'source_spans':[span(state,m,r) for m,r in [(rule,'conditional success branches'),(evidence,'exhaustive inbound interval counts'),(branch,'exhaustive outbound branch probabilities'),(independence,'explicit independence'),(itinerary,'matching entities')]],
        'question_mapping':{'criteria':dict(criteria),'instructions':instruction,'polarity':polarity},
        'thresholds':{'on_time_success_max':a,'late_success_max':b,'late_branch_min':delay},
        'interval_counts':{'total':n,'short':nshort,'middle':nmiddle,'long':nlong},
        'tree':[node('complement',[exact(late)],ontime),node('conditional_frequency',[nshort,n],short),
            node('conditional_frequency',[nshort+nmiddle,n],extended),node('multiply',[exact(ontime),exact(short)],first),
            node('multiply',[exact(late),exact(extended)],second),node('add',[exact(first),exact(second)],make),
            node('complement',[exact(make)],miss)],'calibration_claim':False}


def percentage_rows(text):
    matches=list(re.finditer(r'(?<![\w-])([A-Za-z][\w-]*)\s+(\d+(?:\.\d+)?)\s*%',text))
    values={}
    for match in matches:
        name=match[1].casefold();value=Fraction(match[2])/100
        if name in values or not 0<=value<=1:return None
        values[name]=value
    remainder=re.sub(r'(?<![\w-])([A-Za-z][\w-]*)\s+(\d+(?:\.\d+)?)\s*%','',text)
    if re.sub(r'[\s·]','',remainder):return None
    return values if values else None


def scoped_bayes(state,q):
    if q.get('type')!='choice' or not isinstance(q.get('criteria'),dict) or len(q['criteria'])<2:return None
    part=unique(r'Failed part:[^\n]*\bpart number ([A-Za-z0-9-]+)[^\n]*\.',state)
    mode=unique(r'Failure mode determined by the lab:[^\n]*\(["“]([^"”]+)["”]\)\.',state)
    if part is None or mode is None:return None
    target=part[1]
    if not re.search(r'(?<![\w-])'+re.escape(target)+r'(?![\w-])',q.get('instructions','')):return None
    # A source scope starts at its typed heading and ends at the next paragraph.
    priors=unique(r'Supply data for '+re.escape(target)+r' \([^\n]*\):\n((?:[ \t]+[^\n]+\n)+)',state)
    failure=unique(r'Field failure rates of '+re.escape(target)+r' within (\d+) months[^\n]*all failure modes\):\n([^\n]+)',state)
    mix=unique(r'Failure-mode mix of those field failures \(share of each supplier[’\']s '+re.escape(target)+r' failures that were ([^;\n]+);[^\n]*\):\n([^\n]+)',state)
    sufficiency=unique(r'[^\n]*nothing else[^\n]*distinguishes the suppliers\.',state)
    if not all([priors,failure,mix,sufficiency]):return None
    age=re.search(r'after (\d+) months in service',part.group(),re.I)
    if age is None or not 0<int(age[1])<=int(failure[1]):return None
    if not re.search(r'stable across build years',sufficiency.group(),re.I):return None
    observed=mode[1].casefold().strip();condition=mix[1].casefold().strip()
    # Only the explicit observed name and its elementary plural are aliases.
    if condition not in [observed,observed+'s']:return None
    full={};prior={};source_rows=[]
    start=priors.start(1)
    for line in priors[1].splitlines(keepends=True):
        row=re.fullmatch(r'[ \t]+(.+?)\s*\.{2,}\s*(\d+(?:\.\d+)?)\s*%(?: of '+re.escape(target)+r' [A-Za-z -]+)?\s*\n?',line)
        if row is None:return None
        name=row[1].strip();alias=name.split()[0].casefold();value=Fraction(row[2])/100
        if alias in full or not 0<=value<=1:return None
        full[alias]=name;prior[alias]=value
        source_rows.append({'role':'scoped prior class','span':[start,start+len(line)],'text':line,'name':name,'alias':alias,'fraction':exact(value)})
        start+=len(line)
    likelihood=percentage_rows(failure[2]);mode_likelihood=percentage_rows(mix[2])
    if len(full)<2 or sum(prior.values())!=1 or likelihood is None or mode_likelihood is None:return None
    if set(prior)!=set(likelihood) or set(prior)!=set(mode_likelihood):return None
    if len(q['criteria'])!=len(full):return None
    mapping={}
    for label,meaning in q['criteria'].items():
        candidates=[alias for alias,name in full.items() if re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',meaning,re.I)]
        if len(candidates)!=1 or candidates[0] in mapping:return None
        if not re.search(r'\bsupplied by\b',meaning,re.I):return None
        mapping[candidates[0]]=label
    if set(mapping)!=set(full):return None
    weights={};tree=[]
    for alias in prior:
        first=prior[alias]*likelihood[alias];weight=first*mode_likelihood[alias];weights[alias]=weight
        tree.extend([{'class':alias,**node('multiply',[exact(prior[alias]),exact(likelihood[alias])],first)},
            {'class':alias,**node('multiply',[exact(first),exact(mode_likelihood[alias])],weight)}])
    denominator=sum(weights.values())
    if denominator<=0:return None
    posteriors={mapping[alias]:value/denominator for alias,value in weights.items()}
    tree.append(node('add',[exact(value) for value in weights.values()],denominator))
    tree.extend({'class':alias,'label':mapping[alias],**node('divide',[exact(value),exact(denominator)],value/denominator)} for alias,value in weights.items())
    return {'rule':'exact_scoped_prior_likelihood_observed_mode_bayes',
        'probabilities':{label:float(value) for label,value in posteriors.items()},
        'exact_probability_fractions':{label:exact(value) for label,value in posteriors.items()},
        'target':target,'observed_mode':observed,'class_aliases':full,'label_mapping':mapping,
        'source_spans':[span(state,m,r) for m,r in [(part,'observed target part'),(mode,'observed mode'),(priors,'target-specific prior scope'),(failure,'target-specific failure likelihood'),(mix,'target-specific conditional mode likelihood'),(sufficiency,'stated evidence sufficiency')]],
        'source_rows':source_rows,'priors':{name:exact(value) for name,value in prior.items()},
        'failure_likelihoods':{name:exact(value) for name,value in likelihood.items()},
        'mode_likelihoods':{name:exact(value) for name,value in mode_likelihood.items()},
        'normalization_denominator':exact(denominator),'tree':tree,'calibration_claim':False}


def solve(state,question):
    if not isinstance(state,str) or not isinstance(question,dict):return None
    try:
        candidates=[p for p in [independent_connection(state,question),scoped_bayes(state,question)] if p is not None]
        return candidates[0] if len(candidates)==1 else None
    except (ValueError,TypeError,KeyError,ZeroDivisionError,OverflowError):
        return None
