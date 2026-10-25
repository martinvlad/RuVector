"""Disjoint invented source/protocol fixtures; no real data, model or tokenizers."""
import importlib.util
import itertools
import json
import math
from pathlib import Path
import unittest
HERE=Path(__file__).resolve().parent

def load(name):
 s=importlib.util.spec_from_file_location('e38_fixture_'+name,HERE/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
Q=load('quantitative');P=load('proof');S=load('source_context')
PREFIX='For "Fixture Cedar" in "Q4", '
def doc(*clauses):return '\n'.join(PREFIX+x for x in clauses)
def claim(x):return PREFIX+x

def certify(d,h,label):
 a=Q.analyze(d,h)
 assert a['status']=='CERTIFICATE_CANDIDATE',a
 assert a['proof']['conclusion']==label,a
 assert a['all_supplied_clauses_parsed']and a['source_model_consistent']
 assert all(d[r['span'][0]:r['span'][1]]==r['text']for r in a['source_clauses'])
 if label=='NotMentioned':assert {w['claim_truth']for w in a['proof']['compatible_worlds']}=={False,True}
 return a
class Stub:
 """Invented word count, not a tokenizer or empirical token estimate."""
 def encode(self,text,pair=None):
  return type('Encoded',(),{'ids':list(range(len((text+' '+(pair or '')).split())+3)),
   'offsets':[(m.start(),m.end())for m in __import__('re').finditer(r'\S+',text)]})()
class SourceTests(unittest.TestCase):
 def test_affine_units_signed_and_binding(self):
  d=doc('"base" is exactly 1.25 thousand USD.','"charge" is exactly 300 USD.','"net" equals "base" minus "charge".',
    '"scaled" equals -2 times "net".')+'\nFor "Fixture Cedar" in "Q3", "base" is exactly 99 USD.'
  certify(d,claim('"net" is exactly 950 USD.'),'Entailment')
  certify(d,claim('"scaled" is exactly -1900 USD.'),'Entailment')
  certify(d,claim('"net" is less than 950 USD.'),'Contradiction')
  self.assertEqual(Q.analyze(d,claim('"net" is exactly 950 percent.'))['status'],'ABSTAIN')
 def test_shared_dependency_cancellation(self):
  d=doc('"x" is between -4 and 9 USD inclusive.','"zero" equals "x" minus "x".')
  a=certify(d,claim('"zero" is exactly 0 USD.'),'Entailment');self.assertEqual(a['proof']['derivation']['coefficients'],[])
 def test_all_comparison_boundaries(self):
  d=doc('"r" is between 2 and 8 USD inclusive.')
  for op,t,l in [('at least',2,'Entailment'),('at most',8,'Entailment'),('more than',8,'Contradiction'),
   ('less than',2,'Contradiction'),('exactly',5,'NotMentioned'),('more than',2,'NotMentioned'),('less than',8,'NotMentioned')]:
   certify(d,claim(f'"r" is {op} {t} USD.'),l)
 def test_duplicate_intersection_and_division(self):
  d=doc('"r" is between 2 and 8 USD inclusive.','"r" is between 4 and 6 USD inclusive.','"z" equals "r" divided by 2.')
  certify(d,claim('"z" is exactly 2.5 USD.'),'NotMentioned')
 def test_refuse_unparsed_conflicting_cyclic_unbound_units(self):
  sources=[doc('"r" is exactly 1 USD.')+'\nManagement may override this.',
   doc('"r" is exactly 1 USD.','"r" is exactly 2 USD.'),doc('"r" equals "s" plus "s".','"s" equals "r" plus "r".'),
   doc('"r" equals "s" divided by 0.'),doc('"r" equals "missing" divided by 2.'),
   doc('"r" is exactly 1 USD.','"s" is exactly 1 percent.','"t" equals "r" plus "s".'),
   doc('"r" is exactly 1 items.','"half" equals "r" divided by 2.'),
   doc('"r" is exactly 1 USD.','"r" equals 2 times "r".')]
  for d in sources:self.assertEqual(Q.analyze(d,claim('"r" is exactly 1 USD.'))['status'],'ABSTAIN')
  self.assertEqual(Q.analyze(doc('"r" is exactly 1 USD.'),claim('"unknown" is exactly 1 USD.'))['status'],'ABSTAIN')
 def test_global_inconsistency_not_vacuous_proof(self):
  d=doc('"r" is exactly 1 USD.','"other" is exactly 5 USD.','"other" is exactly 6 USD.')
  self.assertEqual(Q.analyze(d,claim('"r" is exactly 1 USD.'))['status'],'ABSTAIN')
 def test_sets_integer_worlds_and_universe(self):
  d=doc('the universe has exactly 11 items.','"red" contains exactly 7 items.','"blue" contains exactly 6 items.')
  a=certify(d,claim('the overlap of "blue" and "red" contains exactly 4 items.'),'NotMentioned')
  self.assertEqual(len(a['proof']['required_clause_ids']),3)
  for w in a['proof']['compatible_worlds']:
   t=w['set_tables'][0];self.assertEqual(sum(t[k]for k in ['both','only_first','only_second','neither']),11)
  certify(d,claim('the overlap of "red" and "blue" contains at least 2 items.'),'Entailment')
  certify(d,claim('the union of "red" and "blue" contains less than 7 items.'),'Contradiction')
  fixed=d+'\n'+PREFIX+'the overlap of "red" and "blue" contains exactly 3 items.'
  certify(fixed,claim('the union of "red" and "blue" contains exactly 10 items.'),'Entailment')
  for extra in ['the overlap of "red" and "blue" contains exactly 0 items.','"red" contains exactly 12 items.']:
   self.assertEqual(Q.analyze(d+'\n'+PREFIX+extra,claim('the overlap of "red" and "blue" contains exactly 4 items.'))['status'],'ABSTAIN')
 def test_proof_quote_coverage_and_abstention(self):
  d=doc('"x" is between 2 and 8 USD inclusive.','"other" is exactly 3 USD.');h=claim('"x" is exactly 5 USD.')
  r={'probabilities_E_C_N':[.2,.7,.1],'native_typed_argmax':'Contradiction'}
  first=d.splitlines()[0];v=P.decide(d,first,h,[[0,len(first)]],r)
  self.assertIsNone(v['certificate']);self.assertEqual(v['final_probabilities_E_C_N'],r['probabilities_E_C_N'])
  v=P.decide(d,d,h,[[0,len(d)]],r);self.assertEqual(v['final_typed_argmax'],'NotMentioned');self.assertEqual(v['final_probabilities_E_C_N'],[.2,.1,.7])
 def test_provided_raw_tie_winner_preserved(self):
  # These equal probabilities may arise from distinct source logits rounded by softmax.
  r={'probabilities_E_C_N':[1/3]*3,'native_typed_argmax':'NotMentioned'}
  self.assertEqual(P.raw_decision(r)['final_typed_argmax'],'NotMentioned')
  d=doc('"r" is exactly 1 USD.');h=claim('"r" is exactly 1 USD.')
  self.assertEqual(P.decide(d,d,h,[[0,len(d)]],r)['final_typed_argmax'],'Entailment')
 def test_proper_score_conditional_monotonicity_and_wrong_cert(self):
  for ints in itertools.product(range(5),repeat=3):
   if sum(ints)!=4:continue
   raw=[x/4 for x in ints];w=max(range(3),key=raw.__getitem__)
   for c in range(3):
    perm=[0,1,2];perm[w],perm[c]=perm[c],perm[w];final=[raw[i]for i in perm]
    b=lambda p,g:sum((v-(i==g))**2 for i,v in enumerate(p))
    self.assertLessEqual(b(final,c),b(raw,c)+1e-14);self.assertGreaterEqual(final[c],raw[c])
  self.assertEqual(sum((v-(i==2))**2 for i,v in enumerate([.7,.2,.1])),sum((v-(i==2))**2 for i,v in enumerate([.2,.7,.1])))
 def test_source_coverage_prefix_and_no_omission_absence(self):
  d=doc('"x" is between 2 and 8 USD inclusive.','"other" is exactly 3 USD.');h=claim('"x" is exactly 5 USD.')
  a=Q.analyze(d,h);t=Stub();u=S.partition(d,t,t,target=128,nli_cap=160,bge_cap=256,max_units=40)
  p,c=S.pack(d,u,list(reversed(range(len(u)))),h,t,a,pair_cap=512)
  self.assertEqual(p,d);self.assertTrue(c['all_required_source_quotes_covered']);self.assertEqual(c['document_character_coverage'],1)
  with self.assertRaises(ValueError):S.pack(d,u,[0,0],h,t,a)
class WorkerWireFixtures(unittest.TestCase):
 def test_stub_three_readouts_reused_as_five_forecasts(self):
  # Pure invented reader; no model/tokenizer imports or actual-data calls.
  w=load('worker');m=load('xxlarge_model');d=doc('"w" is exactly 13 USD.');h=claim('"w" is exactly 14 USD.')
  record={'id':'pure-fixture:wire-only','document':d,'hypothesis':h,'readouts':{},'arms':{}}
  counters={k:0 for k in w.expected_counters()};calls=[]
  for name in w.A.RAW_CONTEXTS:
   record['readouts'][name]={'readout_id':'pure-fixture:'+name,'premise':d,'context':{'selected_source_spans':[[0,len(d)]]},
    'joint_pair_tokens':1,'context_seconds':.1,'native_query_seconds':.01}
  class Reader:
   def score(self,premise,hyp,receipt,role):
    calls.append((premise,hyp,role));receipt.update(m.decisions([-1000,0,1]),pair_tokens=1,
     model_weights_sha256=w.A.MODEL_WEIGHT_SHA['xxlarge'],forward_seconds=.2)
  class Offline:
   def assert_clean(self):pass
  args=type('Args',(),{'deadline':__import__('time').time()+30})()
  w.score_model_role({'counters':counters},{'cases':[record]},Reader(),args,lambda event:None,Offline(),'xxlarge')
  self.assertEqual(len(calls),3);self.assertEqual(counters['derived_forecasts_completed'],5)
  self.assertEqual(counters['certificate_decisions_completed'],3)
  self.assertEqual(counters['source_analysis_calls_completed'],3)
  for name,a in record['arms'].items():
   self.assertIs(a['reader'],record['readouts'][w.A.READOUT_REUSE_MAP[name]]['reader'])
   v=a['decision'];self.assertEqual(v['final_log_probabilities_E_C_N'],[v['raw_log_probabilities_E_C_N'][i]for i in v['permutation']])
   self.assertTrue(all(math.isfinite(x)for x in v['final_log_probabilities_E_C_N']))
   self.assertEqual(v['raw_probabilities_E_C_N'][1],0)
  self.assertEqual(record['arms']['native_verified']['decision']['final_typed_argmax'],'Contradiction')
 def test_resource_headroom_excludes_shmem(self):
  path=HERE.parents[1]/'epoch38/preparation/dispatch_once.py'
  spec=importlib.util.spec_from_file_location('pure_resource_reducer',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  policy=dict(mod.RESOURCE_POLICY);g=1024**3;mem={'MemTotal':16*g,'MemAvailable':16*g}
  stats={'anon':4*g,'kernel':0,'file':6*g,'shmem':6*g,'active_file':0,'inactive_file':6*g,'file_dirty':0,'file_writeback':0}
  with self.assertRaises(RuntimeError):mod.evaluate_host_memory(mem,16*g,10*g,stats,20*1024**2,policy)
  stats['shmem']=0;yes=mod.evaluate_host_memory(mem,16*g,10*g,stats,20*1024**2,policy)
  self.assertTrue(yes['passed']);self.assertEqual(yes['minimum_required_reclaim_adjusted_headroom_bytes'],11549357942)
  stats['file_dirty']=4*g
  with self.assertRaises(RuntimeError):mod.evaluate_host_memory(mem,16*g,10*g,stats,20*1024**2,policy)

if __name__=='__main__':unittest.main()
