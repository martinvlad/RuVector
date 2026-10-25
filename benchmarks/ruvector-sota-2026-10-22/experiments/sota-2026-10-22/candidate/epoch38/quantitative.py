"""Closed source-bound rational quantities and two-set cardinality certificates.

No labels, case identities, files, model calls or learned parameters enter this
module. Every nonblank source line must parse. Unsupported or inconsistent
supplied context abstains; missing retrieval never proves insufficiency.
"""
from fractions import Fraction
import hashlib
import json
import re

POLICY = 'typed-financial-affine-cardinality-v1'
MAX_CHARS = 8192
MAX_CLAUSES = 24
Q = r'"([A-Za-z0-9][A-Za-z0-9 _/.-]{0,63})"'
NUM = r'(-?(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,6})?)'
UNIT = r'(million USD|thousand USD|USD|items|percent)'
PREFIX = r'For ' + Q + r' in ' + Q + r', '
COMPARISON = r'(exactly|at least|at most|more than|less than)'
PATTERNS = [
 ('exact', re.compile(PREFIX + Q + r' is exactly ' + NUM + r' ' + UNIT + r'\.', re.ASCII)),
 ('interval', re.compile(PREFIX + Q + r' is between ' + NUM + r' and ' + NUM + r' ' + UNIT + r' inclusive\.', re.ASCII)),
 ('binary', re.compile(PREFIX + Q + r' equals ' + Q + r' (plus|minus) ' + Q + r'\.', re.ASCII)),
 ('scale', re.compile(PREFIX + Q + r' equals ' + NUM + r' times ' + Q + r'\.', re.ASCII)),
 ('divide', re.compile(PREFIX + Q + r' equals ' + Q + r' divided by ' + NUM + r'\.', re.ASCII)),
 ('universe', re.compile(PREFIX + r'the universe has exactly ' + NUM + r' items\.', re.ASCII)),
 ('set', re.compile(PREFIX + Q + r' contains exactly ' + NUM + r' items\.', re.ASCII)),
 ('overlap', re.compile(PREFIX + r'the overlap of ' + Q + r' and ' + Q + r' contains exactly ' + NUM + r' items\.', re.ASCII)),
]
AMOUNT_CLAIM = re.compile(PREFIX + Q + r' is ' + COMPARISON + r' ' + NUM + r' ' + UNIT + r'\.', re.ASCII)
SET_CLAIM = re.compile(PREFIX + r'the (overlap|union) of ' + Q + r' and ' + Q + r' contains ' + COMPARISON + r' ' + NUM + r' items\.', re.ASCII)
UNITS = {'USD': ('USD', Fraction(1)), 'thousand USD': ('USD', Fraction(1000)),
         'million USD': ('USD', Fraction(1000000)), 'items': ('items', Fraction(1)),
         'percent': ('ratio', Fraction(1,100))}


class Unsupported(ValueError):
    pass


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def rational(value):
    return [value.numerator, value.denominator]


def freeze(value):
    if isinstance(value, Fraction):
        return rational(value)
    if isinstance(value, dict):
        return {str(k): freeze(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [freeze(v) for v in value]
    if isinstance(value, set):
        return sorted(value)
    return value


def canonical_sha(value):
    return sha(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False))


def parse_atom(text):
    for kind,pattern in PATTERNS:
        m=pattern.fullmatch(text)
        if not m:
            continue
        a=list(m.groups());entity,period=a[:2];a=a[2:]
        result={'kind':kind,'entity':entity,'period':period}
        if kind in ('exact','interval'):
            metric=a[0];unit=a[-1];dimension,multiplier=UNITS[unit]
            lo=Fraction(a[1])*multiplier
            hi=lo if kind=='exact'else Fraction(a[2])*multiplier
            if lo>hi:
                raise Unsupported('inconsistent_source_interval')
            if dimension=='items'and(lo.denominator!=1 or hi.denominator!=1):
                raise Unsupported('nonintegral_item_source_domain')
            result.update(metric=metric,lower=lo,upper=hi,unit=unit,dimension=dimension)
        elif kind=='binary':
            result.update(metric=a[0],left=a[1],operator=a[2],right=a[3])
        elif kind=='scale':
            result.update(metric=a[0],scalar=Fraction(a[1]),operand=a[2])
        elif kind=='divide':
            scalar=Fraction(a[2])
            if not scalar:
                raise Unsupported('zero_divisor')
            result.update(metric=a[0],scalar=scalar,operand=a[1])
        else:
            value=Fraction(a[-1])
            if value.denominator!=1 or not 0<=value<=1000000:
                raise Unsupported('cardinality_not_bounded_nonnegative_integer')
            result['value']=int(value)
            if kind=='set':result['set_name']=a[0]
            if kind=='overlap':result['sets']=sorted(a[:2])
        return result
    raise Unsupported('unparsed_source_clause')


def parse_document(document):
    if not isinstance(document,str)or not document.isascii()or not 0<len(document)<=MAX_CHARS or '\x00'in document:
        raise Unsupported('unsupported_source_encoding_or_size')
    rows=[];cursor=0
    for line in document.splitlines(keepends=True):
        left=len(line)-len(line.lstrip());right=len(line.rstrip())
        if right>left:
            text=line[left:right];atom=parse_atom(text)
            rows.append({'clause_id':len(rows),'span':[cursor+left,cursor+right],
                         'text':text,'text_sha256':sha(text),'atom':atom})
            if len(rows)>MAX_CLAUSES:raise Unsupported('source_clause_cap')
        cursor+=len(line)
    if not rows:raise Unsupported('no_source_clause')
    return rows


def parse_claim(hypothesis):
    if not isinstance(hypothesis,str)or not hypothesis.isascii()or len(hypothesis)>1024:
        raise Unsupported('unsupported_claim')
    m=AMOUNT_CLAIM.fullmatch(hypothesis)
    if m:
        entity,period,metric,op,value,unit=m.groups();dimension,multiplier=UNITS[unit]
        return {'kind':'amount','entity':entity,'period':period,'metric':metric,
                'comparison':op,'value':Fraction(value)*multiplier,'unit':unit,'dimension':dimension}
    m=SET_CLAIM.fullmatch(hypothesis)
    if m:
        entity,period,operation,a,b,op,value=m.groups()
        if a==b:raise Unsupported('set_pair_not_distinct')
        number=Fraction(value)
        if number.denominator!=1:raise Unsupported('nonintegral_cardinality_claim')
        return {'kind':'cardinality','entity':entity,'period':period,'operation':operation,
                'sets':sorted([a,b]),'comparison':op,'value':number,'dimension':'items'}
    raise Unsupported('unparsed_claim')


def compare(value,op,target):
    if op=='exactly':return value==target
    if op=='at least':return value>=target
    if op=='at most':return value<=target
    if op=='more than':return value>target
    if op=='less than':return value<target
    raise Unsupported('unknown_comparison')


def conclusion_from_extrema(lo,hi,op,target):
    if op=='exactly':
        return 'Entailment'if lo==hi==target else 'Contradiction'if target<lo or target>hi else 'NotMentioned'
    if op=='at least':return 'Entailment'if lo>=target else'Contradiction'if hi<target else'NotMentioned'
    if op=='at most':return 'Entailment'if hi<=target else'Contradiction'if lo>target else'NotMentioned'
    if op=='more than':return 'Entailment'if lo>target else'Contradiction'if hi<=target else'NotMentioned'
    if op=='less than':return 'Entailment'if hi<target else'Contradiction'if lo>=target else'NotMentioned'
    raise Unsupported('unknown_comparison')


class Model:
    def __init__(self,rows):
        self.rows=rows;self.domains={};self.definitions={};self.forms={};self.visiting=set();self.set_frames={}
        facts={}
        for row in rows:
            atom=row['atom'];frame=(atom['entity'],atom['period']);kind=atom['kind'];i=row['clause_id']
            if kind in('exact','interval'):
                key=(*frame,atom['metric']);facts.setdefault(key,[]).append(row)
            elif kind in('binary','scale','divide'):
                key=(*frame,atom['metric'])
                if key in self.definitions and self.definitions[key]['atom']!=atom:
                    raise Unsupported('conflicting_derived_metric_definitions')
                self.definitions.setdefault(key,{'atom':atom,'clause_ids':[]})['clause_ids'].append(i)
            else:
                self.set_frames.setdefault(frame,[]).append(row)
        if set(facts)&set(self.definitions):raise Unsupported('coupled_fact_and_definition_not_supported')
        for key,rr in facts.items():
            dims={r['atom']['dimension']for r in rr}
            if len(dims)!=1:raise Unsupported('conflicting_metric_dimensions')
            lo=max(r['atom']['lower']for r in rr);hi=min(r['atom']['upper']for r in rr)
            if lo>hi:raise Unsupported('inconsistent_source_metric_bounds')
            self.domains[key]={'lower':lo,'upper':hi,'dimension':next(iter(dims)),
                               'integer_domain':next(iter(dims))=='items','clause_ids':[r['clause_id']for r in rr]}
        if len(self.domains)>16:raise Unsupported('primitive_quantity_cap')
        for key in [*self.domains,*self.definitions]:self.resolve(key)
        self.set_frames={key:self.check_set_frame(key,rr)for key,rr in self.set_frames.items()}

    def resolve(self,key):
        if key in self.forms:return self.forms[key]
        if key in self.visiting:raise Unsupported('cyclic_metric_definition')
        self.visiting.add(key)
        if key in self.domains:
            d=self.domains[key];fixed=d['lower']==d['upper']
            form={'constant':d['lower']if fixed else Fraction(0),
                  'coefficients':{}if fixed else{key:Fraction(1)},
                  'dimension':d['dimension'],'dependencies':set(d['clause_ids'])}
        elif key in self.definitions:
            data=self.definitions[key];a=data['atom'];frame=key[:2]
            if a['kind']=='binary':
                l=self.resolve((*frame,a['left']));r=self.resolve((*frame,a['right']))
                if l['dimension']!=r['dimension']:raise Unsupported('invalid_affine_unit_arithmetic')
                s=Fraction(1)if a['operator']=='plus'else Fraction(-1);coeff=dict(l['coefficients'])
                for variable,c in r['coefficients'].items():coeff[variable]=coeff.get(variable,Fraction(0))+s*c
                form={'constant':l['constant']+s*r['constant'],
                      'coefficients':{v:c for v,c in coeff.items()if c},'dimension':l['dimension'],
                      'dependencies':l['dependencies']|r['dependencies']|set(data['clause_ids'])}
            else:
                child=self.resolve((*frame,a['operand']));s=a['scalar']if a['kind']=='scale'else Fraction(1)/a['scalar']
                form={'constant':child['constant']*s,'coefficients':{v:c*s for v,c in child['coefficients'].items()if c*s},
                      'dimension':child['dimension'],'dependencies':child['dependencies']|set(data['clause_ids'])}
        else:raise Unsupported('unbound_formula_or_claim_metric')
        self.visiting.remove(key);self.forms[key]=form;return form

    def check_set_frame(self,key,rr):
        totals=[r for r in rr if r['atom']['kind']=='universe'];sets={};overlaps=[]
        if not totals or len({r['atom']['value']for r in totals})!=1:
            raise Unsupported('missing_or_conflicting_universe')
        total=totals[0]['atom']['value']
        for row in rr:
            a=row['atom']
            if a['kind']=='set':
                name=a['set_name']
                if name in sets and sets[name]['count']!=a['value']:raise Unsupported('conflicting_set_size')
                sets.setdefault(name,{'count':a['value'],'clause_ids':[]})['clause_ids'].append(row['clause_id'])
            elif a['kind']=='overlap':overlaps.append(row)
        if len(sets)!=2:raise Unsupported('exactly_two_named_sets_required')
        names=sorted(sets);a,b=[sets[n]['count']for n in names]
        if a>total or b>total:raise Unsupported('set_exceeds_declared_universe')
        lo=max(0,a+b-total);hi=min(a,b)
        for row in overlaps:
            atom=row['atom']
            if atom['sets']!=names:raise Unsupported('overlap_set_identity_mismatch')
            lo=max(lo,atom['value']);hi=min(hi,atom['value'])
        if lo>hi:raise Unsupported('inconsistent_cardinality_constraints')
        return {'entity':key[0],'period':key[1],'universe':total,'set_names':names,'set_counts':[a,b],
                'overlap_lower':lo,'overlap_upper':hi,'dependencies':{r['clause_id']for r in rr}}

    def minimum_world(self):
        return ({k:d['lower']for k,d in self.domains.items()},
                {k:f['overlap_lower']for k,f in self.set_frames.items()})

    def affine_value(self,form,values):
        return form['constant']+sum((c*values[v]for v,c in form['coefficients'].items()),Fraction(0))

    def valid_world(self,values,set_values):
        if set(values)!=set(self.domains)or set(set_values)!=set(self.set_frames):return False
        for key,d in self.domains.items():
            value=values[key]
            if not isinstance(value,Fraction)or not d['lower']<=value<=d['upper']or(d['integer_domain']and value.denominator!=1):return False
        # Derived item quantities are counts too. A fractional derived count is
        # not a feasible model, even if each primitive count was integral.
        for key,form in self.forms.items():
            if form['dimension']=='items'and self.affine_value(form,values).denominator!=1:return False
        for key,f in self.set_frames.items():
            x=set_values[key]
            if type(x)is not int or not f['overlap_lower']<=x<=f['overlap_upper']:return False
            a,b=f['set_counts'];cells=[x,a-x,b-x,f['universe']-a-b+x]
            if min(cells)<0 or sum(cells)!=f['universe']:return False
        return True

    def world(self,values,set_values,claim):
        if not self.valid_world(values,set_values):raise Unsupported('invalid_compatible_world')
        if claim['kind']=='amount':value=self.affine_value(self.resolve((claim['entity'],claim['period'],claim['metric'])),values)
        else:
            frame=(claim['entity'],claim['period']);f=self.set_frames[frame];x=set_values[frame]
            value=Fraction(x if claim['operation']=='overlap'else sum(f['set_counts'])-x)
        return {'claim_truth':compare(value,claim['comparison'],claim['value']),'claim_value':rational(value),
                'amount_variables':[{'binding':list(k),'value':rational(values[k]),'dimension':self.domains[k]['dimension'],
                                     'integer_domain':self.domains[k]['integer_domain']}for k in sorted(values)],
                'derived_values':[{'binding':list(k),'value':rational(self.affine_value(self.forms[k],values)),
                                   'dimension':self.forms[k]['dimension']}for k in sorted(self.definitions)],
                'set_tables':[self.set_table(k,set_values[k])for k in sorted(set_values)],
                'all_source_constraints_satisfied':True}

    def set_table(self,key,x):
        f=self.set_frames[key];a,b=f['set_counts']
        return {'binding':list(key),'universe':f['universe'],'sets':f['set_names'],'marginals':[a,b],
                'both':x,'only_first':a-x,'only_second':b-x,'neither':f['universe']-a-b+x,
                'overlap_bounds':[f['overlap_lower'],f['overlap_upper']]}

    def analyze_claim(self,claim):
        baseline,base_sets=self.minimum_world();low_values=dict(baseline);high_values=dict(baseline)
        low_sets=dict(base_sets);high_sets=dict(base_sets)
        if claim['kind']=='amount':
            key=(claim['entity'],claim['period'],claim['metric']);form=self.resolve(key)
            if form['dimension']!=claim['dimension']:raise Unsupported('claim_metric_dimension_mismatch')
            for variable,c in form['coefficients'].items():
                d=self.domains[variable];low_values[variable]=d['lower']if c>0 else d['upper'];high_values[variable]=d['upper']if c>0 else d['lower']
            lo=self.affine_value(form,low_values);hi=self.affine_value(form,high_values);deps=form['dependencies']
            primitive={'kind':'AFFINE_QUANTITY','binding':list(key),'dimension':form['dimension'],
                       'constant':rational(form['constant']),
                       'coefficients':[{'binding':list(k),'coefficient':rational(c)}for k,c in sorted(form['coefficients'].items())],
                       'independent_root_domains':[{'binding':list(k),'lower':rational(d['lower']),'upper':rational(d['upper']),
                                                   'integer_domain':d['integer_domain']}for k,d in sorted(self.domains.items())]}
        else:
            frame=(claim['entity'],claim['period']);f=self.set_frames.get(frame)
            if f is None or f['set_names']!=claim['sets']:raise Unsupported('unbound_claim_set_family')
            if claim['operation']=='overlap':low_sets[frame]=f['overlap_lower'];high_sets[frame]=f['overlap_upper']
            else:low_sets[frame]=f['overlap_upper'];high_sets[frame]=f['overlap_lower']
            lo=Fraction(low_sets[frame]if claim['operation']=='overlap'else sum(f['set_counts'])-low_sets[frame])
            hi=Fraction(high_sets[frame]if claim['operation']=='overlap'else sum(f['set_counts'])-high_sets[frame]);deps=f['dependencies']
            primitive={'kind':'INTEGER_TWO_SET_CARDINALITY','binding':list(frame),'family':freeze(f),'operation':claim['operation']}
        conclusion=conclusion_from_extrema(lo,hi,claim['comparison'],claim['value'])
        worlds=[self.world(low_values,low_sets,claim),self.world(high_values,high_sets,claim)]
        if conclusion=='NotMentioned'and not any(w['claim_truth']for w in worlds):
            if claim['comparison']!='exactly' or lo==hi:raise Unsupported('no_explicit_true_false_worlds')
            if claim['kind']=='cardinality':
                frame=(claim['entity'],claim['period']);f=self.set_frames[frame]
                x=claim['value']if claim['operation']=='overlap'else Fraction(sum(f['set_counts']))-claim['value']
                if x.denominator!=1:raise Unsupported('no_integral_true_cardinality_world')
                ss=dict(base_sets);ss[frame]=int(x);worlds.append(self.world(baseline,ss,claim))
            else:
                t=(claim['value']-lo)/(hi-lo)
                values={k:low_values[k]+t*(high_values[k]-low_values[k])for k in baseline}
                candidates=[values]
                # Exact single-root adjustments can establish integer witnesses
                # when continuous interpolation gives fractional item counts.
                form=self.resolve((claim['entity'],claim['period'],claim['metric']))
                for variable,c in form['coefficients'].items():
                    vv=dict(low_values);vv[variable]+=(claim['value']-lo)/c;candidates.append(vv)
                for vv in candidates:
                    if self.valid_world(vv,base_sets):
                        w=self.world(vv,base_sets,claim)
                        if w['claim_truth']:worlds.append(w);break
        if conclusion=='NotMentioned':
            yes=next((w for w in worlds if w['claim_truth']),None);no=next((w for w in worlds if not w['claim_truth']),None)
            if yes is None or no is None:raise Unsupported('no_explicit_true_false_compatible_worlds')
            worlds=[yes,no];deps={r['clause_id']for r in self.rows}
        elif conclusion=='Entailment'and not all(w['claim_truth']for w in worlds):raise Unsupported('extremum_certificate_truth_mismatch')
        elif conclusion=='Contradiction'and any(w['claim_truth']for w in worlds):raise Unsupported('extremum_certificate_false_mismatch')
        return {'conclusion':conclusion,'rule':'AFFINE_EXTREMA_OR_EXPLICIT_COMPATIBLE_WORLDS'if claim['kind']=='amount'else'FINITE_TWO_SET_EXTREMA_OR_EXPLICIT_COMPATIBLE_WORLDS',
                'claim':freeze(claim),'lower':rational(lo),'upper':rational(hi),'derivation':primitive,
                'required_clause_ids':sorted(deps),'compatible_worlds':worlds,
                'neutral_requires_entire_source_catalog':conclusion=='NotMentioned'}


def analyze(document,hypothesis):
    common={'schema_version':1,'epoch':38,'policy':POLICY,'document_sha256':sha(document)if isinstance(document,str)else None,
            'hypothesis_sha256':sha(hypothesis)if isinstance(hypothesis,str)else None}
    parsed_all=False
    try:
        rows=parse_document(document);parsed_all=True;claim=parse_claim(hypothesis);model=Model(rows);proof=model.analyze_claim(claim)
        result={**common,'status':'CERTIFICATE_CANDIDATE','all_supplied_clauses_parsed':True,
                'source_model_consistent':True,'source_clauses':freeze(rows),'proof':proof,
                'required_source_spans':[rows[i]['span']for i in proof['required_clause_ids']]}
    except Unsupported as error:
        result={**common,'status':'ABSTAIN','reason':str(error),'all_supplied_clauses_parsed':parsed_all,
                'source_model_consistent':None,'required_source_spans':[[0,len(document)]]if isinstance(document,str)else[],'proof':None}
    result['analysis_sha256']=canonical_sha(result)
    return result
