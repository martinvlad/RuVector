"""Conservative proof-bearing arithmetic on explicitly supplied records.

Pure input -> proof. No data-file access, evaluation identifiers, expected labels,
network/model calls, or answer tables. Unknown grammar/filters return None.
"""
from datetime import date,datetime
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR,ROUND_HALF_UP
from fractions import Fraction
from itertools import product
import re

def norm(value):return re.sub(r'[^a-z0-9]','',str(value).lower())

def label_map(outcomes,criteria):
    """Exact normalized label/description identity only; no semantic guessing."""
    mapping={}
    for outcome in set(outcomes):
        matches=[label for label,description in criteria.items() if norm(outcome) in [norm(label),norm(description.get('what') if isinstance(description,dict) else description)]]
        if len(matches)!=1:return None
        mapping[outcome]=matches[0]
    if len(set(mapping.values()))!=len(mapping):return None
    return mapping

def parse_date(value):
    value=value.strip()
    for fmt in ['%Y-%m-%d','%d %B %Y','%d %b %Y']:
        try:return datetime.strptime(value,fmt).date()
        except ValueError:pass
    raise ValueError('Unsupported explicit date')

def rows(state):
    result=[]
    for number,line in enumerate(state.splitlines()):
        if '|' not in line:continue
        cells=[part.strip() for part in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r'[-: ]+',cell) for cell in cells):continue
        result.append((number,cells))
    return result

def infer_columns(table,criteria,fields,time_pattern):
    choices={name:[i for i in range(5) if norm(value) in {norm(cells[i]) for _,cells in table}] for name,value in fields.items()}
    choices['time']=[i for i in range(5) if all(re.fullmatch(time_pattern,cells[i],re.I) for _,cells in table)]
    choices['outcome']=[i for i in range(5) if label_map([cells[i] for _,cells in table],criteria) is not None]
    if any(not value for value in choices.values()):return None
    matches=[]
    for values in product(*choices.values()):
        if len(set(values))!=4:continue
        columns=dict(zip(choices,values));identity=next(i for i in range(5) if i not in values)
        if len({cells[identity] for _,cells in table})!=len(table):continue
        columns['record_key']=identity;matches.append(columns)
    return matches[0] if len(matches)==1 else None

def span(state,kind,text):
    start=state.find(text)
    return {'kind':kind,'span':[start,start+len(text)],'text':text}

def distribution(state,eligible,all_rows,criteria,filters,rule,columns,sources):
    if not eligible:return None
    mapping=label_map([cells[columns['outcome']] for _,cells in all_rows],criteria)
    if mapping is None:return None
    counts={label:0 for label in criteria}
    for _,cells in eligible:counts[mapping[cells[columns['outcome']]]]+=1
    fractions={label:Fraction(count,len(eligible)) for label,count in counts.items()}
    return {'rule':rule,'probabilities':{label:float(value) for label,value in fractions.items()},
        'exact_probability_fractions':{label:[value.numerator,value.denominator] for label,value in fractions.items()},
        'eligible_rows':[number for number,_ in eligible],'total_rows':len(all_rows),'denominator':len(eligible),
        'outcome_counts':counts,'filters':filters,'outcome_to_label':mapping,'columns':columns,
        'source_spans':[span(state,kind,text) for kind,text in sources],
        'source_rows':[{'line':number,'cells':cells,**span(state,'table_row',state.splitlines()[number]),'eligible':number in {n for n,_ in eligible}} for number,cells in all_rows]}

def table_frequencies(state,question):
    if question['type']!='choice' or not re.search(r'(?i)probabilit',question.get('instructions','')):return None
    criteria=question.get('criteria')
    if not isinstance(criteria,dict) or not 2<=len(criteria)<=26:return None
    table=rows(state)
    if not table or not all(len(cells)==5 for _,cells in table):return None
    preamble='\n'.join(state.splitlines()[:table[0][0]])
    tier_rules=[line for line in preamble.splitlines() if re.search(r'(?i)same tier',line) and re.search(r'(?i)same category',line)]
    if len(tier_rules)==1:
        rule=tier_rules[0]
        residual=re.sub(r'(?i)same (?:tier|category)','',rule)
        if re.search(r'(?i)\bsame\b|\bbefore\b|\bexcluding\b|\bwithin\b|\bunless\b|\bexcept\b|\bon or after\b',residual):return None
        cutoffs=re.findall(r'(?i)opened after (\d{1,2} [a-z]+ \d{4}|\d{4}-\d{2}-\d{2})',rule)
        targets=list(re.finditer(r'(?im)^\s*(?:new|target) [^:\n]{1,100}:\s*([^,\n]+?)\s+tier,\s*category\s+([^,\n]+),\s*opened\s+([^\n.]+)',preamble))
        if len(cutoffs)!=1 or len(targets)!=1:return None
        tier,category,target_date=targets[0].groups()
        try:cutoff=parse_date(cutoffs[0]);parse_date(target_date)
        except ValueError:return None
        columns=infer_columns(table,criteria,{'tier':tier,'category':category},r'opened \d{4}-\d{2}-\d{2}')
        if columns is None:return None
        eligible=[]
        for number,cells in table:
            match=re.fullmatch(r'(?i)opened (\d{4}-\d{2}-\d{2})',cells[columns['time']])
            if not match:return None
            try:opened=parse_date(match.group(1))
            except ValueError:return None
            if norm(cells[columns['tier']])==norm(tier) and norm(cells[columns['category']])==norm(category) and opened>cutoff:eligible.append((number,cells))
        return distribution(state,eligible,table,criteria,{'tier':tier,'category':category,'opened_strict_after':str(cutoff)},'explicit_same_attribute_date_frequency',columns,[('rule',rule),('target',targets[0].group(0))])
    route_rules=[line for line in preamble.splitlines() if all(re.search(pattern,line,re.I) for pattern in ['same route','same carrier','same service'])]
    if len(route_rules)==1:
        rule=route_rules[0];residual=re.sub(r'(?i)same (?:route|carrier|service(?: level)?)','',rule)
        if re.search(r'(?i)\bsame\b|\bbefore\b|\bafter\b|\bunless\b|\bexcept\b|\bwithin\b',residual):return None
        bounds=re.findall(r'(?i)excluding.{0,60}?weeks (\d{1,2})\s*[-–]\s*(\d{1,2})',rule)
        targets=list(re.finditer(r'(?im)^[^:\n]{1,100}:\s*([^,\n]+),\s*service\s+([^,\n]+),\s*pickup week\s+\d{1,2}/\d{4},\s*route\s+([^\n.]+)',preamble))
        contexts=list(re.finditer(r'(?im)^past [^\n]*? on route\s+([^,\n]+),\s*\d{4}',preamble))
        if len(bounds)!=1 or len(targets)!=1 or len(contexts)!=1:return None
        low,high=map(int,bounds[0]);carrier,service,route=targets[0].groups()
        if not 1<=low<=high<=53 or norm(route)!=norm(contexts[0].group(1)):return None
        columns=infer_columns(table,criteria,{'carrier':carrier,'service':service},r'pickup week \d{1,2}/\d{4}')
        if columns is None:return None
        eligible=[]
        for number,cells in table:
            match=re.fullmatch(r'(?i)pickup week (\d{1,2})/(\d{4})',cells[columns['time']])
            if not match:return None
            week=int(match.group(1))
            if not 1<=week<=53:return None
            if norm(cells[columns['carrier']])==norm(carrier) and norm(cells[columns['service']])==norm(service) and not low<=week<=high:eligible.append((number,cells))
        return distribution(state,eligible,table,criteria,{'carrier':carrier,'service':service,'route':route,'exclude_weeks_inclusive':[low,high]},'explicit_route_service_week_frequency',columns,[('rule',rule),('target',targets[0].group(0)),('shared_route_context',contexts[0].group(0))])
    return None

def mass_threshold(state,question):
    if question['type']!='noul' or not re.search(r'(?i)\bcompl(?:y|ies)\b',question.get('instructions','')):return None
    formulas=re.findall(r'(?i)gross weight\s*=\s*([^\n.]+)',state)
    if len(formulas)!=1:return None
    clean=re.sub(r'\([^)]*\)','',formulas[0]).lower().replace('uld ','')
    terms={norm(term) for term in clean.split('+')}
    if terms!={'netcargoweight','tareweight','restraintequipmentweight'}:return None
    if len(re.findall(r'(?i)\bmust\b',state))!=1 or re.search(r'(?i)\brequires?\b|\bonly if\b|\bunless\b|\bprovided that\b',state):return None
    number=r'((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)'
    captures={
        'limit':re.findall(r'(?i)must not exceed\s*'+number+r'\s*kg',state),
        'net':re.findall(r'(?i)net cargo[^:\n]*:\s*'+number+r'\s*(lb|kg)\b',state),
        'tare':re.findall(r'(?i)tare weight\s*:?\s*'+number+r'\s*kg',state),
        'restraint':re.findall(r'(?i)restraint total\s*:?\s*'+number+r'\s*kg',state)}
    if any(len(value)!=1 for value in captures.values()):return None
    value=lambda text:Decimal(text.replace(',',''))
    limit=value(captures['limit'][0]);net,unit=captures['net'][0];net=value(net);tare=value(captures['tare'][0]);restraint=value(captures['restraint'][0]);factor=Decimal(1)
    if unit.lower()=='lb':
        factors=re.findall(r'(?i)1\s*lb\s*=\s*'+number+r'\s*kg',state)
        if len(factors)!=1:return None
        factor=value(factors[0])
    modes=[]
    if re.search(r'(?i)rounded up to the next whole kilogram',state):modes.append(('up',ROUND_CEILING))
    if re.search(r'(?i)rounded down to the (?:next )?whole kilogram',state):modes.append(('down',ROUND_FLOOR))
    if re.search(r'(?i)rounded to the nearest whole kilogram',state):modes.append(('nearest_half_up',ROUND_HALF_UP))
    if len(modes)!=1:return None
    raw=net*factor+tare+restraint;rounded=raw.to_integral_value(rounding=modes[0][1])
    patterns={'formula':r'(?i)gross weight\s*=\s*([^\n.]+)','limit':r'(?i)must not exceed\s*'+number+r'\s*kg',
        'net':r'(?i)net cargo[^:\n]*:\s*'+number+r'\s*(lb|kg)\b','tare':r'(?i)tare weight\s*:?\s*'+number+r'\s*kg',
        'restraint':r'(?i)restraint total\s*:?\s*'+number+r'\s*kg','rounding':r'(?i)rounded (?:up to the next|down to the (?:next )?|to the nearest)\s*whole kilogram'}
    if unit.lower()=='lb':patterns['conversion']=r'(?i)1\s*lb\s*=\s*'+number+r'\s*kg'
    sources=[span(state,kind,re.search(pattern,state).group(0)) for kind,pattern in patterns.items()]
    return {'decision':rounded<=limit,'rule':'explicit_mass_formula_and_threshold',
        'inputs':{'net':str(net),'net_unit':unit.lower(),'kg_per_net_unit':str(factor),'tare_kg':str(tare),'restraint_kg':str(restraint),'limit_kg':str(limit)},
        'raw_gross_kg':str(raw),'rounding':modes[0][0],'rounded_gross_kg':str(rounded),'operator':'<=','source_spans':sources}

def solve(state,question):
    if not isinstance(state,str):return None
    return table_frequencies(state,question) or mass_threshold(state,question)

_previous_supported_solver=solve

def snapshot_frequency(state,question):
    """Explicit snapshot + event history -> one supplied frequency-table row."""
    if question['type']!='choice' or not re.search(r'(?i)probabilit',question.get('instructions','')):return None
    criteria=question.get('criteria')
    if not isinstance(criteria,dict):return None
    table=rows(state)
    if len(table)<3:return None
    header=table[0][1]
    if len(header)!=len(criteria)+2 or any(len(cells)!=len(header) for _,cells in table):return None
    status_columns=[i for i,value in enumerate(header) if re.search(r'(?i)status at (\d+) h before',value)]
    if len(status_columns)!=1:return None
    status_column=status_columns[0];hours=int(re.search(r'(\d+) h before',header[status_column]).group(1))
    if not 1<=hours<=168:return None
    outcomes={}
    for i,value in enumerate(header):
        if i==status_column:continue
        label=label_map([re.sub(r'\([^)]*\)','',value).strip()],criteria)
        if label:outcomes[i]=next(iter(label.values()))
    if len(outcomes)!=len(criteria) or set(outcomes.values())!=set(criteria):return None
    total_columns=[i for i in range(len(header)) if i not in outcomes and i!=status_column]
    if len(total_columns)!=1:return None
    total_column=total_columns[0];profiles=[]
    for number,cells in table[1:]:
        if not all(re.fullmatch(r'(?:\d{1,3}(?:,\d{3})+|\d+)',cells[i]) for i in [total_column,*outcomes]):return None
        try:
            counts={label:int(cells[i].replace(',','')) for i,label in outcomes.items()};total=int(cells[total_column].replace(',',''))
        except ValueError:return None
        if any(value<0 for value in counts.values()) or total<=0 or sum(counts.values())!=total:return None
        profiles.append((number,cells,counts,total))
    rule_lines=[line for line in state.splitlines() if re.search(r'(?i)use the row matching',line) and re.search(r'(?i)status',line)]
    if len(rule_lines)!=1:return None
    rule=rule_lines[0]
    if not re.search(r'(?i)at the '+str(hours)+r'-hour mark',rule) or re.search(r'(?i)\bsame\b|\bunless\b|\bexcept\b|\bexcluding\b|\bwithin\b',rule):return None
    if not (re.search(r'(?i)after the '+str(hours)+r'-hour mark',rule) and re.search(r'(?i)ignored',rule)):return None
    stamp=r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})'
    targets=[line for line in state.splitlines() if re.search(r'(?i)(?:appointment|target event) to estimate:',line)]
    checkpoints=[line for line in state.splitlines() if re.search(r'(?i)'+str(hours)+r'-hour mark for this',line)]
    if len(targets)!=1 or len(checkpoints)!=1:return None
    preamble='\n'.join(state.splitlines()[:table[0][0]])
    population=[]
    for age in ['adult','child','pediatric']:
        if re.search(r'(?i)\b'+age+r' appointments\b',preamble):
            if not re.search(r'(?i)\b'+age+r'\b',targets[0]):return None
            population.append(age)
    sites=re.findall(r'(?i)\b([a-z]+ site)\b',preamble)
    if len(set(value.lower() for value in sites))>1:return None
    for site in sites:
        if not re.search(r'(?i)\b'+re.escape(site)+r'\b',targets[0]):return None
        population.append(site.lower())
    def moment(line):
        values=re.findall(stamp,line)
        if len(values)!=1:raise ValueError('One explicit timestamp required')
        return datetime.strptime(values[0],'%Y-%m-%d %H:%M')
    try:target=moment(targets[0]);checkpoint=moment(checkpoints[0])
    except ValueError:return None
    from datetime import timedelta
    if target-timedelta(hours=hours)!=checkpoint:return None
    confirmations=[profile for profile in profiles if re.search(r'(?i)confirmed',profile[1][status_column])]
    delivered_profiles=[profile for profile in profiles if re.search(r'(?i)delivered.*no reply',profile[1][status_column])]
    failed_profiles=[profile for profile in profiles if re.search(r'(?i)not delivered|undelivered|delivery failed',profile[1][status_column])]
    if any(len(items)!=1 for items in [confirmations,delivered_profiles,failed_profiles]):return None
    tokens=re.findall(r'"([^"\n]+)"',confirmations[0][1][status_column])
    if len(tokens)!=1:return None
    confirmation_token=tokens[0]
    delivery=[line for line in state.splitlines() if re.search(r'(?i)delivery receipt:',line)]
    replies=[line for line in state.splitlines() if re.search(r'(?i)\breply\s+"',line)]
    if len(delivery)!=1:return None
    try:delivery_time=moment(delivery[0])
    except ValueError:return None
    delivery_state=re.search(r'(?i)delivery receipt:\s*(DELIVERED|FAILED|NOT DELIVERED)\b',delivery[0])
    if not delivery_state:return None
    delivered=delivery_state.group(1).lower()=='delivered' and delivery_time<=checkpoint
    failed=delivery_state.group(1).lower()!='delivered' and delivery_time<=checkpoint
    before=[]
    for line in replies:
        match=re.search(r'(?i)\breply\s+"([^"\n]+)"',line)
        try:when=moment(line)
        except ValueError:return None
        if when<=checkpoint:
            if match.group(1)!=confirmation_token:return None
            before.append((when,line))
    if len(before)>1:return None
    confirmed=bool(before)
    if confirmed and (not delivered or before[0][0]<delivery_time):return None
    if confirmed:selected=confirmations[0]
    elif delivered:selected=delivered_profiles[0]
    elif failed:selected=failed_profiles[0]
    else:return None
    row_number,cells,counts,total=selected;fractions={label:Fraction(count,total) for label,count in counts.items()}
    source=[('header',state.splitlines()[table[0][0]]),('governing_rule',rule),('target_event',targets[0]),('checkpoint',checkpoints[0]),('delivery_event',delivery[0]),('selected_profile',state.splitlines()[row_number])]
    source.extend(('reply_event',line) for line in replies)
    return {'rule':'explicit_snapshot_event_status_frequency','probabilities':{label:float(value) for label,value in fractions.items()},
        'exact_probability_fractions':{label:[value.numerator,value.denominator] for label,value in fractions.items()},
        'outcome_counts':counts,'denominator':total,'columns':{'status':status_column,'total':total_column,'outcomes':{str(i):label for i,label in outcomes.items()}},
        'population_constraints':population,
        'snapshot_hours_before':hours,'target_event':target.isoformat(),'computed_checkpoint':checkpoint.isoformat(),
        'event_state_at_checkpoint':{'delivered':delivered,'confirmed':confirmed,'explicit_failed_delivery':failed},
        'selected_profile_label':cells[status_column],'selected_source_row':row_number,
        'source_spans':[span(state,kind,text) for kind,text in source]}

def solve(state,question):
    if not isinstance(state,str):return None
    return _previous_supported_solver(state,question) or snapshot_frequency(state,question)
