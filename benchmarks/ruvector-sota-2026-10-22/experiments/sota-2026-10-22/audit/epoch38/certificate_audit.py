"""Independent certificate verifier: lexical tokens, exact constraints, witnesses.

Never imports the candidate prover. It validates retained certificates only
after the real worker has closed; pure tests use unrelated authored fixtures.
"""
from fractions import Fraction as F
import hashlib,json,re
from data_common import require,canonical,CANONICAL_LABELS

GRAMMAR='typed-financial-affine-cardinality-v1'
NUMBER=r'-?(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,6})?'
IDENTIFIER=r'[A-Za-z0-9][A-Za-z0-9 _/.-]{0,63}'
TOKEN=re.compile(r'\s*(?:"('+IDENTIFIER+r')"|('+NUMBER+r')|([A-Za-z]+)|([,.]))',re.ASCII)
UNIT={'USD':('USD',F(1)),'thousand USD':('USD',F(1000)),'million USD':('USD',F(1000000)),'items':('items',F(1)),'percent':('ratio',F(1,100))}

def sha(text):return hashlib.sha256(text.encode()).hexdigest()
def pair(q):return[q.numerator,q.denominator]
def rat(v):
 require(type(v)is list and len(v)==2 and all(type(x)is int for x in v)and v[1]>0 and max(abs(x).bit_length()for x in v)<=4096,'Invalid bounded rational pair')
 q=F(*v);require(pair(q)==v,'Noncanonical rational pair');return q
def freeze(v):
 if isinstance(v,F):return pair(v)
 if isinstance(v,dict):return{k:freeze(x)for k,x in v.items()}
 if isinstance(v,(list,tuple)):return[freeze(x)for x in v]
 if isinstance(v,set):return sorted(v)
 return v
def tokens(text):
 require(type(text)is str and text.isascii()and '\x00'not in text,'Non-ASCII or null source clause')
 out=[];p=0
 while p<len(text):
  m=TOKEN.match(text,p);require(m is not None,'Unsupported source token')
  if m.group(1)is not None:out.append(('q',m.group(1)))
  elif m.group(2)is not None:out.append(('n',F(m.group(2))))
  elif m.group(3)is not None:out.append(('w',m.group(3)))
  else:out.append(('p',m.group(4)))
  p=m.end()
 return out
class Cursor:
 def __init__(self,text):self.a=tokens(text);self.i=0
 def take(self,kind,value=None):
  require(self.i<len(self.a),'Incomplete typed clause');k,v=self.a[self.i];self.i+=1
  require(k==kind and(value is None or v==value),'Typed source grammar mismatch');return v
 def words(self,*a):
  for x in a:self.take('w',x)
 def peek(self,kind=None,value=None):
  return self.i<len(self.a)and(kind is None or self.a[self.i][0]==kind)and(value is None or self.a[self.i][1]==value)
 def binding(self):
  self.words('For');e=self.take('q');self.words('in');p=self.take('q');self.take('p',',');return e,p
 def unit(self):
  first=self.take('w');u=first+' '+self.take('w','USD')if first in ['million','thousand']else first
  require(u in UNIT,'Unsupported source unit');return u
 def end(self):self.take('p','.');require(self.i==len(self.a),'Trailing unparsed source content')

def parse_statement(text):
 c=Cursor(text);e,p=c.binding();r={'entity':e,'period':p}
 if c.peek('w','the'):
  c.words('the')
  if c.peek('w','universe'):
   c.words('universe','has','exactly');v=c.take('n');c.words('items');r.update(kind='universe',value=v)
  else:
   c.words('overlap','of');a=c.take('q');c.words('and');b=c.take('q');c.words('contains','exactly');v=c.take('n');c.words('items');r.update(kind='overlap',sets=sorted([a,b]),value=v)
 elif c.peek('q'):
  metric=c.take('q')
  if c.peek('w','contains'):
   c.words('contains','exactly');v=c.take('n');c.words('items');r.update(kind='set',set_name=metric,value=v)
  elif c.peek('w','is'):
   c.words('is');exact=c.peek('w','exactly');c.words('exactly'if exact else'between');lo=c.take('n')
   if exact:hi=lo
   else:c.words('and');hi=c.take('n')
   u=c.unit()
   if not exact:c.words('inclusive')
   dim,mult=UNIT[u];lo*=mult;hi*=mult
   require(lo<=hi,'Inconsistent primitive bounds');require(dim!='items'or lo.denominator==hi.denominator==1,'Fractional primitive item domain')
   r.update(kind='exact'if exact else'interval',metric=metric,lower=lo,upper=hi,unit=u,dimension=dim)
  else:
   c.words('equals')
   if c.peek('n'):
    s=c.take('n');c.words('times');operand=c.take('q');r.update(kind='scale',metric=metric,scalar=s,operand=operand)
   else:
    left=c.take('q')
    if c.peek('w','divided'):
     c.words('divided','by');s=c.take('n');require(s!=0,'Zero source divisor');r.update(kind='divide',metric=metric,scalar=s,operand=left)
    else:
     op=c.take('w');require(op in ['plus','minus'],'Unsupported binary source operator');right=c.take('q');r.update(kind='binary',metric=metric,left=left,operator=op,right=right)
 else:raise ValueError('Missing typed source subject')
 c.end()
 if r['kind']in ['universe','set','overlap']:
  require(r['value'].denominator==1 and 0<=r['value']<=1000000,'Cardinality count not bounded nonnegative integer');r['value']=int(r['value'])
 return r

def comparison(c):
 w=c.take('w')
 if w=='exactly':return w
 if w=='at':v=c.take('w');require(v in ['least','most'],'Unsupported inclusive comparison');return w+' '+v
 require(w in ['more','less'],'Unsupported strict comparison');c.words('than');return w+' than'
def parse_claim(text):
 require(len(text)<=1024,'Oversized typed claim');c=Cursor(text);e,p=c.binding();r={'entity':e,'period':p}
 if c.peek('q'):
  metric=c.take('q');c.words('is');op=comparison(c);v=c.take('n');u=c.unit();dim,m=UNIT[u];r.update(kind='amount',metric=metric,comparison=op,value=v*m,unit=u,dimension=dim)
 else:
  c.words('the');opn=c.take('w');require(opn in ['overlap','union'],'Unsupported set operator');c.words('of');a=c.take('q');c.words('and');b=c.take('q');require(a!=b,'Identical set names');c.words('contains');op=comparison(c);v=c.take('n');c.words('items');require(v.denominator==1,'Nonintegral set claim');r.update(kind='cardinality',operation=opn,sets=sorted([a,b]),comparison=op,value=v,dimension='items')
 c.end();return r
def source_rows(document):
 require(type(document)is str and document.isascii()and 0<len(document)<=8192,'Unsupported source encoding or size');rows=[];offset=0
 for line in document.splitlines(keepends=True):
  left=len(line)-len(line.lstrip());right=len(line.rstrip())
  if right>left:
   text=line[left:right];rows.append({'clause_id':len(rows),'span':[offset+left,offset+right],'text':text,'text_sha256':sha(text),'atom':parse_statement(text)})
  offset+=len(line)
 require(0<len(rows)<=24,'Typed source clause cap');return rows
def truth(x,op,t):
 return {'exactly':lambda:x==t,'at least':lambda:x>=t,'at most':lambda:x<=t,'more than':lambda:x>t,'less than':lambda:x<t}[op]()
def all_or_none(lo,hi,op,t):
 # Bounds are source-wide affine box bounds (or exact finite set extrema).
 if op=='exactly':yes=lo==hi==t;no=t<lo or t>hi
 elif op=='at least':yes=lo>=t;no=hi<t
 elif op=='at most':yes=hi<=t;no=lo>t
 elif op=='more than':yes=lo>t;no=hi<=t
 else:yes=hi<t;no=lo>=t
 return 'Entailment'if yes else'Contradiction'if no else'NotMentioned'

class IndependentCatalog:
 """Build affine equations independently, preserving repeated-variable identity."""
 def __init__(self,rows):
  self.rows=rows;self.roots={};self.defs={};self.forms={};self.frames={};facts={};defs={};cards={}
  for r in rows:
   a=r['atom'];k=(a['entity'],a['period']);typ=a['kind']
   if typ in ['exact','interval']:facts.setdefault(k+(a['metric'],),[]).append(r)
   elif typ in ['binary','scale','divide']:defs.setdefault(k+(a['metric'],),[]).append(r)
   else:cards.setdefault(k,[]).append(r)
  require(not(set(facts)&set(defs)),'Coupled fact and equation source refused');require(len(facts)<=16,'Primitive quantity cap')
  for k,rr in facts.items():
   require(len({r['atom']['dimension']for r in rr})==1,'Conflicting units');lo=max(r['atom']['lower']for r in rr);hi=min(r['atom']['upper']for r in rr);require(lo<=hi,'Empty primitive source domain');dim=rr[0]['atom']['dimension']
   self.roots[k]={'lo':lo,'hi':hi,'dim':dim,'integer':dim=='items','deps':{r['clause_id']for r in rr}}
  for k,rr in defs.items():
   require(all(r['atom']==rr[0]['atom']for r in rr),'Conflicting source equations');self.defs[k]=(rr[0]['atom'],{r['clause_id']for r in rr})
  for k in [*self.roots,*self.defs]:self.form(k,set())
  for k,rr in cards.items():
   universes={r['atom']['value']for r in rr if r['atom']['kind']=='universe'};require(len(universes)==1,'Missing/conflicting universe');n=next(iter(universes));named={}
   for r in rr:
    a=r['atom']
    if a['kind']=='set':
     require(a['set_name']not in named or named[a['set_name']]==a['value'],'Conflicting set count');named[a['set_name']]=a['value']
   require(len(named)==2,'Exactly two named subsets required');names=sorted(named);aa,bb=[named[x]for x in names];require(max(aa,bb)<=n,'Set exceeds scope universe');lo=max(0,aa+bb-n);hi=min(aa,bb)
   for r in rr:
    a=r['atom']
    if a['kind']=='overlap':require(a['sets']==names,'Overlap names do not bind universe');lo=max(lo,a['value']);hi=min(hi,a['value'])
   require(lo<=hi,'Empty integral set family');self.frames[k]={'n':n,'names':names,'a':aa,'b':bb,'lo':lo,'hi':hi,'deps':{r['clause_id']for r in rr}}
 def form(self,key,visiting):
  if key in self.forms:return self.forms[key]
  require(key not in visiting,'Cyclic source equation');visiting=visiting|{key}
  if key in self.roots:
   d=self.roots[key];fixed=d['lo']==d['hi'];f=(d['lo']if fixed else F(0),{}if fixed else{key:F(1)},d['dim'],set(d['deps']))
  else:
   require(key in self.defs,'Unbound source metric');a,deps=self.defs[key];scope=key[:2]
   if a['kind']=='binary':
    lc,lv,ld,lp=self.form(scope+(a['left'],),visiting);rc,rv,rd,rp=self.form(scope+(a['right'],),visiting);require(ld==rd,'Dimensionally invalid equation');sgn=1 if a['operator']=='plus'else-1;co=dict(lv)
    for v,z in rv.items():co[v]=co.get(v,F(0))+sgn*z
    f=(lc+sgn*rc,{v:z for v,z in co.items()if z},ld,lp|rp|deps)
   else:
    c,coeff,d,p=self.form(scope+(a['operand'],),visiting);s=a['scalar']if a['kind']=='scale'else 1/a['scalar'];f=(c*s,{v:z*s for v,z in coeff.items()if z*s},d,p|deps)
  self.forms[key]=f;return f
 def value(self,key,values):
  c,coeff,_,_=self.forms[key];return c+sum((v*values[k]for k,v in coeff.items()),F(0))
 def claim_info(self,claim):
  if claim['kind']=='amount':
   k=(claim['entity'],claim['period'],claim['metric']);c,coeff,d,deps=self.form(k,set());require(d==claim['dimension'],'Claim/source unit mismatch');lo=c;hi=c
   for v,z in coeff.items():
    q=self.roots[v];lo+=z*(q['lo']if z>0 else q['hi']);hi+=z*(q['hi']if z>0 else q['lo'])
   deriv={'kind':'AFFINE_QUANTITY','binding':list(k),'dimension':d,'constant':pair(c),'coefficients':[{'binding':list(v),'coefficient':pair(z)}for v,z in sorted(coeff.items())],'independent_root_domains':[{'binding':list(v),'lower':pair(q['lo']),'upper':pair(q['hi']),'integer_domain':q['integer']}for v,q in sorted(self.roots.items())]}
  else:
   k=(claim['entity'],claim['period']);require(k in self.frames,'Unknown set universe');q=self.frames[k];require(q['names']==claim['sets'],'Claim named sets mismatch');deps=q['deps']
   lo,hi=(F(q['lo']),F(q['hi']))if claim['operation']=='overlap'else(F(q['a']+q['b']-q['hi']),F(q['a']+q['b']-q['lo']))
   family={'entity':k[0],'period':k[1],'universe':q['n'],'set_names':q['names'],'set_counts':[q['a'],q['b']],'overlap_lower':q['lo'],'overlap_upper':q['hi'],'dependencies':sorted(q['deps'])}
   deriv={'kind':'INTEGER_TWO_SET_CARDINALITY','binding':list(k),'family':family,'operation':claim['operation']}
  return lo,hi,deps,deriv
 def witness(self,w,claim):
  require(isinstance(w,dict)and w.get('all_source_constraints_satisfied')is True,'Missing source-wide feasible witness assertion');roots={}
  for r in w['amount_variables']:
   k=tuple(r['binding']);require(k in self.roots and k not in roots,'Unknown/duplicate primitive witness binding');q=self.roots[k];v=rat(r['value']);require(q['lo']<=v<=q['hi']and(not q['integer']or v.denominator==1),'Primitive witness violates stated bound/domain');require(r['dimension']==q['dim']and r['integer_domain']is q['integer'],'Witness primitive type mismatch');roots[k]=v
  require(set(roots)==set(self.roots),'Witness omits full-source primitive constraint')
  actual={}
  for r in w['derived_values']:
   k=tuple(r['binding']);require(k in self.defs and k not in actual,'Unknown/duplicate derived witness binding');v=rat(r['value']);require(v==self.value(k,roots)and r['dimension']==self.forms[k][2],'Derived witness violates source equation');require(self.forms[k][2]!='items'or v.denominator==1,'Fractional derived item witness');actual[k]=v
  require(set(actual)==set(self.defs),'Witness omits full-source derived equation');tables={}
  for r in w['set_tables']:
   k=tuple(r['binding']);require(k in self.frames and k not in tables,'Unknown/duplicate set witness scope');require(all(type(r[z])is int for z in ['universe','both','only_first','only_second','neither'])and type(r['marginals'])is list and len(r['marginals'])==2 and all(type(x)is int for x in r['marginals'])and type(r['overlap_bounds'])is list and len(r['overlap_bounds'])==2 and all(type(x)is int for x in r['overlap_bounds']),'Set witness integer metadata required');q=self.frames[k];x=r['both'];require(type(x)is int and q['lo']<=x<=q['hi'],'Set witness overlap outside constraints');cells=[x,q['a']-x,q['b']-x,q['n']-q['a']-q['b']+x]
   require(min(cells)>=0 and sum(cells)==q['n'],'Invalid full2x2 population witness');expected={'binding':list(k),'universe':q['n'],'sets':q['names'],'marginals':[q['a'],q['b']],'both':cells[0],'only_first':cells[1],'only_second':cells[2],'neither':cells[3],'overlap_bounds':[q['lo'],q['hi']]};require(r==expected,'Set witness table metadata differs');tables[k]=x
  require(set(tables)==set(self.frames),'Witness omits full-source set family')
  if claim['kind']=='amount':value=self.value((claim['entity'],claim['period'],claim['metric']),roots)
  else:
   k=(claim['entity'],claim['period']);q=self.frames[k];value=F(tables[k]if claim['operation']=='overlap'else q['a']+q['b']-tables[k])
  yes=truth(value,claim['comparison'],claim['value']);require(rat(w['claim_value'])==value and type(w['claim_truth'])is bool and w['claim_truth']==yes,'Witness claim truth/value mismatch');return value,yes

def audit_analysis(analysis,document,hypothesis):
 require(isinstance(analysis,dict)and analysis.get('schema_version')==1 and analysis.get('epoch')==38 and analysis.get('policy')==GRAMMAR,'Wrong typed source analysis')
 require(analysis['document_sha256']==sha(document)and analysis['hypothesis_sha256']==sha(hypothesis),'Analysis source hashes differ')
 unhashed={k:v for k,v in analysis.items()if k!='analysis_sha256'};body=json.dumps(unhashed,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
 require(analysis.get('analysis_sha256')==sha(body),'Full typed analysis content hash differs')
 require(analysis.get('status')=='CERTIFICATE_CANDIDATE'and analysis.get('all_supplied_clauses_parsed')is True and analysis.get('source_model_consistent')is True,'Applied certificate lacks parsed consistent source')
 rows=source_rows(document);require(analysis['source_clauses']==freeze(rows),'Independent full-source lexical/quote/atom parse differs');claim=parse_claim(hypothesis);cat=IndependentCatalog(rows);lo,hi,deps,deriv=cat.claim_info(claim);proof=analysis['proof'];rat(proof['lower']);rat(proof['upper']);label=all_or_none(lo,hi,claim['comparison'],claim['value'])
 require(proof['conclusion']==label and proof['claim']==freeze(claim)and proof['lower']==pair(lo)and proof['upper']==pair(hi)and proof['derivation']==deriv,'Independent source binding/affine or set bounds differ')
 rule='AFFINE_EXTREMA_OR_EXPLICIT_COMPATIBLE_WORLDS'if claim['kind']=='amount'else'FINITE_TWO_SET_EXTREMA_OR_EXPLICIT_COMPATIBLE_WORLDS';require(proof['rule']==rule,'Unsupported source proof rule')
 worlds=proof['compatible_worlds'];require(type(worlds)is list and len(worlds)==2,'Two explicit feasible source worlds required');vv=[cat.witness(w,claim)for w in worlds]
 if label=='NotMentioned':require({yes for _,yes in vv}=={True,False},'Neutral lacks actual full-source true/false compatible worlds');needed=set(range(len(rows)))
 else:
  require([v for v,_ in vv]==[lo,hi],'Universal proof lacks source-feasible extrema');require(all(yes==(label=='Entailment')for _,yes in vv),'Extrema predicate inconsistent with universal conclusion');needed=deps
 require(proof['neutral_requires_entire_source_catalog']is(label=='NotMentioned')and proof['required_clause_ids']==sorted(needed),'Required full-source constraints changed');spans=[rows[i]['span']for i in sorted(needed)];require(analysis['required_source_spans']==spans,'Required source quote coverage differs')
 return {'conclusion':label,'required_spans':spans,'worlds_independently_validated':2,'source_clauses':len(rows),'source_consistency_proven_by_actual_worlds':True,'source_scope':'All supplied typed clauses parsed; named sets are subsets of their same entity/period universe. No retrieval omission is a proof.'}

def audit_certificate(cert,document,premise,hypothesis,selected_spans):
 require(isinstance(cert,dict)and cert.get('schema_version')==1 and cert.get('epoch')==38 and cert.get('grammar')==GRAMMAR,'Wrong source certificate schema')
 require(cert['document_sha256']==sha(document)and cert['hypothesis_sha256']==sha(hypothesis)and cert['premise_sha256']==sha(premise),'Certificate literal evidence changed');require(cert['selected_source_spans']==selected_spans and cert['all_required_source_quotes_covered']is True,'Certificate measured span admission changed')
 info=audit_analysis(cert['full_source_analysis'],document,hypothesis)
 for a,b in info['required_spans']:require(any(x<=a and b<=y for x,y in selected_spans),'Required source constraint absent from measured context')
 require(cert['conclusion']==info['conclusion'],'Certificate conclusion changed');return info

def audit_catalog(analysis,document,hypothesis):
 if analysis.get('status')=='CERTIFICATE_CANDIDATE':return audit_analysis(analysis,document,hypothesis)
 require(analysis.get('schema_version')==1 and analysis.get('epoch')==38 and analysis.get('policy')==GRAMMAR and analysis.get('status')=='ABSTAIN','Unknown source catalogue status')
 require(analysis.get('document_sha256')==sha(document)and analysis.get('hypothesis_sha256')==sha(hypothesis),'Abstaining source catalogue has changed input')
 body=json.dumps({k:v for k,v in analysis.items()if k!='analysis_sha256'},sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
 require(analysis.get('analysis_sha256')==sha(body)and analysis.get('source_model_consistent')is None and analysis.get('proof')is None and analysis.get('required_source_spans')==[[0,len(document)]]and type(analysis.get('all_supplied_clauses_parsed'))is bool and type(analysis.get('reason'))is str and analysis['reason'],'Abstention must preserve full source and provide no conclusion')
 return {'conclusion':None,'required_spans':[[0,len(document)]],'worlds_independently_validated':0,'certificate_applied':False,'safe_abstention':True,'reason':analysis['reason']}
