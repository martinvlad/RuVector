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


# The complete frozen round1 source is preserved above. The final round adds
# only a counterexample validator for one explicitly ordered money operation.
import json
from decimal import Decimal,localcontext,ROUND_HALF_UP

round1_solve=solve


def monetary_rounding_counterexample(state,q):
    if q.get('type')!='noul' or set(q.get('criteria',{}))!={'true','false'}:return None
    if not re.search(r'fully correct',q['criteria']['true'],re.I) or not re.search(r'\berror\b',q['criteria']['false'],re.I):return None
    if not re.search(r'response.*(?:satisf|correct)',q.get('instructions',''),re.I):return None
    try:fields=json.loads(state)
    except (ValueError,TypeError):return None
    if not isinstance(fields,dict) or set(fields)!={'request','response'} or not all(isinstance(x,str) for x in fields.values()):return None
    request,response=fields['request'],fields['response']
    primary=request.split('\n\n',1)[0]
    amount=r'(\d{1,12}(?:\.\d{1,2})?)';rate=r'(\d{1,3}(?:\.\d{1,6})?)'
    rule=re.fullmatch(r'An invoice subtotal is ([$€£])'+amount+r'\. Apply a '+rate+r'% discount, then '+rate+r'% tax to the discounted amount\. Do not round the intermediate discounted amount\. Round the final charge to cents using half-up, and show the derivation\.',primary,re.I)
    if rule is None:return None
    extra=request[len(primary):]
    if extra and (not extra.startswith('\n\nAdditional evaluation context:') or re.search(r'[$€£%]|\b(?:instead|unless|except|override|additional (?:fee|charge))\b',extra,re.I)):return None
    currency,subtotal_s,discount_s,tax_s=rule.groups()
    claim=unique(r'final charge is\s*(?:\*\*)?'+re.escape(currency)+r'(\d{1,14}\.\d{2})(?!\d)',response)
    if claim is None:return None
    with localcontext() as context:
        context.prec=80
        subtotal=Decimal(subtotal_s);discount=Decimal(discount_s)/100;tax=Decimal(tax_s)/100
        if subtotal<0 or not 0<=discount<=1 or not 0<=tax<=1:return None
        retained=1-discount;discounted=subtotal*retained;tax_multiplier=1+tax;raw=discounted*tax_multiplier
        rounded=raw.quantize(Decimal('.01'),rounding=ROUND_HALF_UP);claimed=Decimal(claim[1])
    # One independently established error is sufficient to disprove full
    # correctness. Agreement does not prove all deliverables: abstain to97.
    if claimed==rounded:return None
    return {'rule':'exact_ordered_money_half_up_counterexample','decision':False,
        'input_encoding':'official normalized state JSON fields',
        'source_spans':[{'role':'complete explicit ordered arithmetic rule','source_field':'request','span':[0,len(primary)],'text':primary},
            {'role':'claimed final monetary charge','source_field':'response','span':[claim.start(),claim.end()],'text':claim.group()}],
        'currency':currency,'subtotal':subtotal_s,'discount_rate':discount_s,'tax_rate':tax_s,
        'exact_decimal_operations':[{'operation':'subtract','inputs':['1',str(discount)],'result':str(retained)},
            {'operation':'multiply','inputs':[str(subtotal),str(retained)],'result':str(discounted)},
            {'operation':'add','inputs':['1',str(tax)],'result':str(tax_multiplier)},
            {'operation':'multiply','inputs':[str(discounted),str(tax_multiplier)],'result':str(raw)},
            {'operation':'quantize','input':str(raw),'quantum':'.01','rounding':'ROUND_HALF_UP','result':str(rounded)}],
        'correct_rounded_charge':str(rounded),'claimed_charge':str(claimed),'counterexample':'The unique claimed final charge differs from exact ordered arithmetic and required rounding.',
        'positive_correctness_claim':False,'calibration_claim':False}


def solve(state,question):
    prior=round1_solve(state,question)
    if prior is not None:return prior
    try:return monetary_rounding_counterexample(state,question)
    except (ValueError,TypeError,KeyError,ArithmeticError):return None
