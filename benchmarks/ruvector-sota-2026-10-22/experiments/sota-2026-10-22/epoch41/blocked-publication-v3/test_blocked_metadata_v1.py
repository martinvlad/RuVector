"""Unrelated metadata fixtures only; never production setup/results/manifest/stage."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import copy,tempfile,unittest
import blocked_common_v1 as c
import blocked_transport_v1 as t
import build_blocked_checkpoint_v1 as b

class Metadata(unittest.TestCase):
 def sample(self):
  value=dict(epoch=41,kind=b.KIND,status=b.STATUS,metrics=None,benchmark_accuracy=None,experiment_executed=False,evaluation_executed=False,dev_passed=False,used_confirmation_identities=[],phase_remaining=copy.deepcopy(b.REMAINING),cumulative_execution=copy.deepcopy(b.CUMULATIVE));value.update(b.FLAGS);return value
 def failure(self):
  counts={k:0 for k in ('new_selected_document_decodes','new_selected_hypothesis_decodes','selected_raw_choice_tokens_copied','semantic_gold_values_decoded','model_tokenizer_native_calls','actual_NLI_readouts','derived_forecasts','semantic_gold_join_calls','scorer_EVALUATE_calls','scorer_BIND_calls','feature_or_vault_or_selected_identity_outputs')};counts.update(root_custodian_calls=1,already_exposed_Legal96_input_state_decodes=96)
  return ({'checks_passed':True,'data_admission_passed':False,'candidate_execution_qualified':False,'metrics':None,'actual_counts':counts},{'checks_passed':True,'physical_closure_passed':True,'actual_materializer_calls':1,'actual_materializer_status':'DATA_ADMISSION_FAILED'},{'status':'DATA_ADMISSION_FAILED','errors':[{'code':'EXACT_GLOBAL_HYPOTHESIS_KEYSET'}]},{'child_reaped':True,'automatic_retry':False,'signals':[],'wall_seconds':0.6887229919666424})
 def test_positive_block(self):b.facts(self.sample())
 def test_no_bool_integer_flags(self):
  for key in b.FLAGS:
   v=self.sample();v[key]=0
   with self.subTest(key=key),self.assertRaises(ValueError):b.facts(v)
 def test_no_metrics(self):
  v=self.sample();v['metrics']={'accuracy':0.0}
  with self.assertRaises(ValueError):b.facts(v)
 def test_no_evaluation(self):
  v=self.sample();v['evaluation_executed']=True
  with self.assertRaises(ValueError):b.facts(v)
 def test_no_experiment(self):
  v=self.sample();v['experiment_executed']=True
  with self.assertRaises(ValueError):b.facts(v)
 def test_no_confirmation(self):
  v=self.sample();v['used_confirmation_identities']=['synthetic-unused-id']
  with self.assertRaises(ValueError):b.facts(v)
 def test_unknown_tail_retained(self):
  v=self.sample();v['cumulative_execution']['corpus_attempts']=36
  with self.assertRaises(ValueError):b.facts(v)
 def test_no_process_increment(self):
  v=self.sample();v['cumulative_execution']['bounded_native_process_attempts']=42
  with self.assertRaises(ValueError):b.facts(v)
 def test_no_slot_reopen(self):
  v=self.sample();v['phase_remaining']['native_corpus']=1
  with self.assertRaises(ValueError):b.facts(v)
 def test_failure_positive(self):b.verify_failure(*self.failure())
 def test_nonzero_new_access_refused(self):
  f,p,r,x=self.failure();f['actual_counts']['new_selected_hypothesis_decodes']=1
  with self.assertRaises(ValueError):b.verify_failure(f,p,r,x)
 def test_bool_count_refused(self):
  f,p,r,x=self.failure();f['actual_counts']['actual_NLI_readouts']=False
  with self.assertRaises(ValueError):b.verify_failure(f,p,r,x)
 def test_legacy_reads_separate(self):
  f,p,r,x=self.failure();f['actual_counts']['already_exposed_Legal96_input_state_decodes']=0
  with self.assertRaises(ValueError):b.verify_failure(f,p,r,x)
 def test_not_exit0_admission(self):
  f,p,r,x=self.failure();r['status']='SUCCESS'
  with self.assertRaises(ValueError):b.verify_failure(f,p,r,x)
 def test_no_retries(self):
  f,p,r,x=self.failure();x['automatic_retry']=True
  with self.assertRaises(ValueError):b.verify_failure(f,p,r,x)
 def test_no_unknown_closure(self):
  f,p,r,x=self.failure();p['physical_closure_passed']=False
  with self.assertRaises(ValueError):b.verify_failure(f,p,r,x)
 def test_public_relative_only(self):
  for path in ('/tmp/secret.json','a/../b.json','a\\b.json'):
   with self.subTest(path=path),self.assertRaises(ValueError):c.relative(path)
 def test_hashonly_ref_regular(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'fixture.json').write_text('{"fixture":true}')
   row=c.ref(p,'fixture.json');self.assertEqual(row['bytes'],16);self.assertEqual(len(row['sha256']),64)
 def test_public_private_paths(self):
  for path in ('private/a.json','models/a.json','secrets/a.txt'):
   with self.subTest(path=path),self.assertRaises(ValueError):c.public_text(path,b'{}')
 def test_raw_page_refused(self):
  with self.assertRaises(ValueError):c.public_text('a.json',bytes([60])+b'html>not a public artifact</html>')
 def test_same_fact_types(self):self.assertFalse(c.same_fact({'n':False},{'n':0}));self.assertFalse(c.same_fact(1,1.0))
 def test_transport_caps(self):
  blobs,groups=t.transport_groups({'x.json':b'{}'});self.assertEqual(blobs,[]);self.assertEqual(len(groups),1);self.assertLess(len(c.encoded({'tree_elements':groups[0]})),t.MAX_TREE_JSON)
 def test_tree_sha_independent_order(self):
  rows={'z.json':t.leaf('z.json',b'{}'),'a/b.json':t.leaf('a/b.json',b'[]')};self.assertEqual(t.scope_tree_sha(rows),t.scope_tree_sha(dict(reversed(list(rows.items())))))
 def test_history_prefix(self):
  before={'champion':'fixture','used_confirmation_sets':[]};after={**before,'epoch41_fixture':True};t.preserve_history(before,after,set())
  with self.assertRaises(ValueError):t.preserve_history(before,{**after,'champion':'changed'},set())

if __name__=='__main__':unittest.main()
