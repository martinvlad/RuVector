"""Disjoint metadata/transport/entrypoint fixtures; no real ContractNLI/text/labels."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ast,copy,hashlib,importlib.util,json,subprocess,tempfile,unittest
from unittest.mock import patch
import publication_common_v1 as c
import stage_publication_v1 as s
from phase_contract_v1 import *
HERE=Path(__file__).parent

def module(name,file):
 spec=importlib.util.spec_from_file_location(name,file);out=importlib.util.module_from_spec(spec);spec.loader.exec_module(out);return out
freeze=module('source_freeze_fixture',HERE.parent/'preparation/reviewed_build_plan.py')
finish=module('result_binding_fixture',HERE.parent/'preparation/reviewed_build_results.py')

def fields():return {'data_roles':{'train':[],'dev':['fixture-id-'+str(i)for i in range(12)],'calibration':[],'confirmation':[]},'arms':ARMS,'actual_NLI_forwards':48}
def replay():return {'epoch':40,'kind':KIND,'phase':'dev','status':'REJECTED_DEV_INTEGRITY','dev_passed':False,'checks_passed':False,'benchmark_accuracy':None,'used_confirmation_identities':[],**FLAGS,'actual_execution':{'worker_attempts':1,'corpus_batches_attempted':None,'completed_corpus_batches':None,'owned_live_processes_closed':True},'evaluation_executed':False,'metrics':None,'gate_checks':{'all_quality':'NOT_EVALUATED'},'label_custody':{'semantic_label_decodes':None,'decode_attempted_tokens':None,'semantic_decode_count_uncertain':True},'retained_fields':{'NLL':None,'raw_counter_scope':'UNKNOWN','errors':['fixture preworker failure']}}

class Publication(unittest.TestCase):
 def reject(self,fn,*args):
  with self.assertRaises((ValueError,KeyError,FileNotFoundError,FileExistsError)):fn(*args)
 def test_duplicate_nonfinite_JSON(self):
  for data in (b'{"a":1,"a":2}',b'{"n":NaN}',b'{"n":1e999}'):self.reject(c.loads,data)
 def test_scope_and_private_binary(self):
  for name in ('../a','/a','a/../b','a\\b'):self.reject(c.relative,name)
  self.reject(c.public_text,E+'bad.json',b'\x00');self.reject(c.public_text,E+'x.txt',('s'+'k-'+'x'*40).encode())
  self.reject(c.public_text,E+'new.patch',b'no new patch exception')
 def test_three_new_roots_no_legacy_patch_exception(self):
  self.assertEqual(c.ROOTS,(P+'candidate/epoch40',P+'audit/epoch40',P+'epoch40'));self.assertNotIn('.patch',c.EXTENSIONS)
 def test_exact_actual_base_owner_and_caps(self):
  self.assertEqual((c.OLD_CP_ROWS,s.BASE_GIT_LEAVES),(6517,6591));self.assertEqual(c.OWNER_PIN,(120232,27979422,13626));self.assertEqual(s.MAX_TREE_JSON,175904);self.assertEqual(s.MAX_BLOB_JSON,8384512)
 def test_DEV_role_only_and_four_physical_arms(self):
  self.assertEqual(freeze.roles_ready(fields())['dev'],fields()['data_roles']['dev'])
  for key,value in [('arms',['old_numeric_cert']),('actual_NLI_forwards',60),('actual_NLI_forwards',48.0)]:
   changed=fields();changed[key]=value;self.reject(freeze.roles_ready,changed)
  for role in ('train','calibration','confirmation'):
   changed=fields();changed['data_roles'][role]=['forbidden'];self.reject(freeze.roles_ready,changed)
 def test_no_case_replacement_duplicate_identity(self):
  changed=fields();changed['data_roles']['dev'][1]=changed['data_roles']['dev'][0];self.reject(freeze.roles_ready,changed)
 def test_external_feature_and_opaque_vault_hash_only(self):
  with tempfile.TemporaryDirectory()as temp:
   root=Path(temp);data=root/'data-source';data.mkdir();features=data/'features.json';vault=data/'vault.bin'
   # Deliberately INVALID JSON and binary; any parser would fail this test.
   features.write_bytes(b'not JSON; opaque feature bytes fixture');vault.write_bytes(b'\x00\xffopaque-token-vault-fixture')
   assets=[{'path':str(file),'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'role':role}for file,role in ((features,'dev_features'),(vault,'dev_oracle'))]
   with patch.object(freeze,'W',root):self.assertEqual(freeze.external_ready({'external_data_assets':assets}),assets)
   vault.write_bytes(b'changed')
   with patch.object(freeze,'W',root):self.reject(freeze.external_ready,{'external_data_assets':assets})
 def test_external_assets_must_not_be_public_or_alias_same_file(self):
  with tempfile.TemporaryDirectory()as temp:
   root=Path(temp);file=root/'project'/'data-source'/'x';file.parent.mkdir(parents=True);file.write_bytes(b'fixture')
   row={'path':str(file),'bytes':7,'sha256':hashlib.sha256(b'fixture').hexdigest(),'role':'dev_features'};other=dict(row,role='dev_oracle')
   with patch.object(freeze,'W',root):self.reject(freeze.external_ready,{'external_data_assets':[row,other]})
 def test_integrated_review_exact_files_and_actual_guard_privacy_flags(self):
  with tempfile.TemporaryDirectory()as temp:
   root=Path(temp);name=E+'source.py';(root/name).parent.mkdir(parents=True);(root/name).write_bytes(b'fixture\n');ref=c.ref(root,name);review=E+'review.json'
   value={'checks_passed':True,'data_source_license_scoring_access_verified':True,'label_blind_policy_frozen_before_materialization':True,'actual_full_model_assets_guard_verified':True,'no_raw_third_party_text_in_public_files':True,'scientific_measurements_started':False,'authoritative_label_codec_source_and_external_structure_verified':True,'private_input_publication_boundary_verified':True,'frozen_missing_or_partial_gold_failure_path_verified':True,'files':[ref]};(root/review).write_bytes(c.encoded(value));current={name:b'fixture\n',review:(root/review).read_bytes()}
   self.assertEqual(freeze.review_ready(root,review,current),c.ref(root,review))
   for key in ('actual_full_model_assets_guard_verified','no_raw_third_party_text_in_public_files','label_blind_policy_frozen_before_materialization'):
    wrong=copy.deepcopy(value);wrong[key]=False;(root/review).write_bytes(c.encoded(wrong));self.reject(freeze.review_ready,root,review,current)
 def test_history_champion_confirmation_not_mutable(self):
  old={'champion':{'id':'native104'},'used_confirmation_sets':['protected'],'exposed_development_sets':['DEV']};new=copy.deepcopy(old);s.preserve_history(old,new,s.FINAL_MUTABLE)
  for key,value in [('champion',{}),('used_confirmation_sets',[]),('exposed_development_sets',[])]:
   wrong=copy.deepcopy(new);wrong[key]=value;self.reject(s.preserve_history,old,wrong,s.FINAL_MUTABLE)
 def test_checkpoint_extends_all_old_rows_and_only_newroots(self):
  row={'path':'old.json','bytes':1,'sha256':'a'*64};old={'project_files':[row],'legacy':{'value':1}};current={E+'new.json':b'{}'};new=copy.deepcopy(old);new['project_files'].append({'path':E+'new.json','bytes':2,'sha256':c.sha(b'{}')});new['epoch40_source']={}
  self.assertEqual(len(s.checkpoint_extension(old,new,current)[1]),2);new['project_files'][0]['bytes']=2;self.reject(s.checkpoint_extension,old,new,current)
 def test_transport_strict_caps_and_dedup(self):
  body=b'['+b' '*70000+b']';blobs,groups=s.transport_groups({E+'a.json':body,E+'b.json':body,E+'small.txt':b'x'*60000});self.assertEqual(len(blobs),1);self.assertEqual(sum(len(g)for g in groups),3);self.assertTrue(all(len(c.encoded({'tree_elements':g}))<175904 for g in groups))
 def test_unequal_payload_git_collision_refused(self):
  with patch.object(s,'gitsha',return_value='a'*40):self.reject(s.transport_groups,{E+'a.txt':b'a'*70000,E+'b.txt':b'b'*70000})
 def test_scope_tree_identity_order_and_old_tuples(self):
  a=s.leaf('a.json',b'a');b=s.leaf('dir/b.json',b'b');self.assertEqual(s.scope_tree_sha({'a.json':a,'dir/b.json':b}),s.scope_tree_sha({'dir/b.json':b,'a.json':a}));b['sha']='0'*40;self.assertNotEqual(s.scope_tree_sha({'a.json':a}),s.scope_tree_sha({'a.json':a,'dir/b.json':b}))
 def test_every_evaluated_field_preserved_and_deepcopied(self):
  before=replay();out=finish.preserve_replay(before,{'scope':'DEV only'});self.assertTrue(all(out[k]==v for k,v in before.items()));out['retained_fields']['errors'].append('new');self.assertEqual(len(before['retained_fields']['errors']),1);self.reject(finish.preserve_replay,out,{})
 def test_DEVONLY_status_never_official_acceptance(self):
  self.assertEqual(finish.replay_ready(replay())['status'],'REJECTED_DEV_INTEGRITY')
  for key,value in [('status','ACCEPTED_ENGINEERING_ADMISSION_ONLY'),('benchmark_accepted',True),('benchmark_accuracy',1),('official_rank',1),('champion_promoted',True),('used_confirmation_identities',['fakeCONF']),('benchmark_generalization_claim',True)]:
   wrong=replay();wrong[key]=value;self.reject(finish.replay_ready,wrong)
 def test_positive_DEV_requires_integrity_and_consistent_status(self):
  value=replay();value.update(status='ACCEPTED_DEV_PILOT_ONLY',dev_passed=True,checks_passed=True,evaluation_executed=True,label_custody={'semantic_label_decodes':12,'decode_attempted_tokens':12,'semantic_decode_count_uncertain':False});finish.replay_ready(value);value['checks_passed']=False;self.reject(finish.replay_ready,value)
 def test_E37_unknown_cumulative_never_repaired(self):
  full={'worker_attempts':1,'corpus_batches_attempted':1,'completed_corpus_batches':1};counts=finish.cumulative(full);self.assertEqual((counts['verified_corpus_attempts_lower_bound'],counts['verified_completed_corpus_batches_lower_bound'],counts['bounded_native_process_attempts']),(36,34,41));self.assertIsNone(counts['corpus_attempts']);self.assertIsNone(counts['completed_corpus_batches']);self.assertEqual(counts['legacy_native_qualification_process_attempts'],6);self.assertEqual((counts['benchmark_HTTP_successes'],counts['benchmark_HTTP_failures']),(903,2))
  counts=finish.cumulative({'worker_attempts':1,'corpus_batches_attempted':None,'completed_corpus_batches':None});self.assertEqual((counts['verified_corpus_attempts_lower_bound'],counts['verified_completed_corpus_batches_lower_bound']),(35,33));self.assertIsNone(counts['corpus_attempts'])
 def test_no_source_oracle_parser_or_scientific_imports_in_helpers(self):
  for name in ('reviewed_build_plan.py','reviewed_build_results.py'):
   source=(HERE.parent/'preparation'/name).read_text();tree=ast.parse(source);imports=' '.join(ast.unparse(n)for n in ast.walk(tree)if isinstance(n,(ast.Import,ast.ImportFrom)))
   for word in ('torch','transformers','onnxruntime','tokenizers','requests','subprocess'):self.assertNotIn(word,imports)
  tree=ast.parse((HERE.parent/'preparation/reviewed_build_plan.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='external_ready');self.assertNotIn('parse(',ast.unparse(fn));self.assertNotIn('json.',ast.unparse(fn))
 def test_python_isolated_entrypoints_help_are_safe(self):
  for file in (HERE/'build_controls_v1.py',HERE/'stage_publication_v1.py',HERE.parent/'preparation/reviewed_build_plan.py',HERE.parent/'preparation/reviewed_build_results.py'):
   run=subprocess.run([sys.executable,'-I','-B',str(file),'--help'],text=True,capture_output=True,timeout=10);self.assertEqual(run.returncode,0,run.stderr);self.assertIn('usage:',run.stdout)
 def test_each_module_under500lines(self):
  for file in list(HERE.glob('*.py'))+list((HERE.parent/'preparation').glob('*.py'))+list((HERE.parent/'preparation').glob('*.js')):self.assertLess(len(file.read_text().splitlines()),500,file.name)
 def test_main_may_advance_readonly_and_actual_parent_conflict_fails(self):
  s.check_phase_main({'main':'a'*40},'b'*40);proof={'commit':'1'*40,'parent':'0'*40,'sole_parent':'0'*40,'checks_passed':True,'verified_actual_remote_readback':True,'root':'2'*40,'bench':'3'*40,'scope':'4'*40};s.check_readback(proof,'source','1'*40,('2'*40,'3'*40,'4'*40));proof['sole_parent']='5'*40;self.reject(s.check_readback,proof,'source','1'*40,('2'*40,'3'*40,'4'*40))
 def test_canonical_proof_flags_hold_zero_privileged_capabilities(self):
  self.assertTrue(all(v==0 for v in REMAINING.values()));self.assertEqual(LIMITS['CPU_affinity'],[0,1]);self.assertEqual(LIMITS['seconds_per_batch'],600);self.assertEqual(ARMS,['tasksource_source_order','tasksource_native','tasksource_lexical','b354_source_order'])

 def test_verify_flags_direct_success_and_false_integer_alias_refused(self):
  s.verify_flags(dict(s.FLAGS))
  for key,value in [('benchmark_accepted',0),('champion_promoted',0),('new_submission',0),('official_SOTA_verified',0),('official_rank',False)]:
   wrong=dict(s.FLAGS);wrong[key]=value;self.reject(s.verify_flags,wrong)
 def test_same_fact_nested_types_keys_and_lengths(self):
  self.assertTrue(c.same_fact({'a':[False,None,1,1.0]},{'a':[False,None,1,1.0]}))
  for left,right in [(False,0),(True,1),(1,1.0),({'a':False},{'a':0}),([1],[1,2]),({'a':1},{'b':1})]:self.assertFalse(c.same_fact(left,right))


 def test_missing_partial_join_is_frozen_integrity_failure_not_evaluation(self):
  for completed,attempted,uncertain in ((0,0,False),(2,2,False),(1,2,True),(None,None,True)):
   v=replay();v['label_custody']={'semantic_label_decodes':completed,'decode_attempted_tokens':attempted,'semantic_decode_count_uncertain':uncertain};out=finish.replay_ready(v);self.assertEqual(out['label_custody'],v['label_custody']);self.assertFalse(out['evaluation_executed']);self.assertIsNone(out['metrics'])
 def test_missing_gold_cannot_gain_scores_or_evaluation_claim(self):
  for key,value in [('metrics',{'fabricated':1}),('accuracy',1),('gate_checks',{'quality':False}),('evaluation_executed',0),('label_custody',{})]:
   v=replay();v[key]=value;self.reject(finish.replay_ready,v)
 def test_uncertain_partial_counts_cannot_be_replaced_or_coerced(self):
  for completed,attempted,uncertain in ((2,1,False),(False,2,False),(1.0,2,False),(None,0,False)):
   v=replay();v['label_custody']={'semantic_label_decodes':completed,'decode_attempted_tokens':attempted,'semantic_decode_count_uncertain':uncertain};self.reject(finish.replay_ready,v)
 def test_source_closure_includes_schema_and_failure_admission_roles(self):
  self.assertTrue({'data_schema_admission','failure_protocol'}<=REQUIRED_REFS)

if __name__=='__main__':unittest.main()
