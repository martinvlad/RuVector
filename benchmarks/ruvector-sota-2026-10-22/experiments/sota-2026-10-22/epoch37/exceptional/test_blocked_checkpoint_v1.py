"""Disjoint metadata/transport fixtures only; never invoke exceptional CLI modes."""
import sys
sys.dont_write_bytecode=True
import ast,copy,hashlib,importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('blocked_metadata_fixture',HERE/'blocked_checkpoint_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
PUB=HERE.parent/'publication'
if not PUB.exists():PUB=Path(__file__).parents[6]/'experiments/sota-2026-10-22/epoch37/publication'
sys.path.insert(0,str(PUB));import publication_common_v1 as c;import stage_publication_v1 as p

def replay():
 return {'epoch':37,'kind':m.KIND,'status':'REJECTED_ENGINEERING_INTEGRITY','checks_passed':False,'engineering_passed':False,'readiness_qualified':False,'actual_NLI_forwards':None,'final_derived_forecasts':None,'engineering_metrics':None,'confirmation':[],'used_confirmation_identities':[],'benchmark_accuracy':None,**m.FLAGS,'evidence':{'raw':None,'execution':None,'supervisor_observed_closure':m.FROZEN['frozen_observer']},'retained_arbitrary_field':{'errors':['fixture failure'],'partial':None,'counts':'UNKNOWN'}}
def supplement():
 return {'schema_version':1,'epoch':37,'kind':m.KIND,'status':'SOURCE_BOUND_PREWORKER_FAILURE_WITH_KERNEL_ZOMBIE_RESOLUTION','checks_passed':True,'exceptional_preworker_resolution_passed':True,'retained_frozen_observer_physical_closure_passed':False,'retained_frozen_observer_unknown_physical_ownership':True,'frozen_evaluation_checks_passed':False,'logical_dispatch_slot_burned':1,'all_remaining_slots':0,'internal_operation_counts':'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT','published_source_commit':m.SOURCE,'source_trees':m.TREES,'evidence':{'fixture':'disjoint metadata; not an observation'},'physical_kernel_observation':{'supervisor_pid':112597,'supervisor_startticks':25316871,'supervisor_state':'Z','kernel_boot_id':'4632fb06-b0ef-4df5-b72b-0e875bbad810','current_PID_namespace_inode':4026532200,'statm_all_zero':True,'kernel_FDSize_zero':True,'status_fields':{'FDSize':'0'},'observed_fd_entries':None,'fd_directory_observation':'DENIED_EACCES','same_identity_before_and_after_scan':True,'live_scoped_PGID_or_SID_members':[],'current_direct_children':[]},'source_failure_boundary':{'frozen_source_and_stderr_consistent':True,'runtime_guard_top_level_before_worker_try':True,'worker_reservation_line':220,'worker_Popen_line':263,'frozen_launch_statement_order':[{'call':'C.verify_runtime','line':212},{'call':'reserve','line':220},{'call':'subprocess.Popen','line':263}]}}

class BlockedMetadata(unittest.TestCase):
 def reject(self,fn,*args):
  with self.assertRaises((ValueError,KeyError,FileNotFoundError,FileExistsError)):fn(*args)
 def test_rejected_evaluation_every_field_preserved(self):
  before=replay();saved=copy.deepcopy(before);out=m.add_results(before,{'status':m.STATUS,'counts':'UNKNOWN'})
  self.assertEqual(before,saved)
  for key,value in before.items():self.assertEqual(out[key],value)
  out['retained_arbitrary_field']['errors'].append('new');self.assertEqual(before,saved)
 def test_cannot_convert_evaluation_into_success(self):
  for key,value in [('checks_passed',True),('engineering_passed',True),('readiness_qualified',True),('actual_NLI_forwards',0),('final_derived_forecasts',0),('engineering_metrics',{}),('status','ACCEPTED_ENGINEERING_ADMISSION_ONLY'),('benchmark_accuracy',1),('used_confirmation_identities',['new']),('champion_promoted',True)]:
   changed=replay();changed[key]=value;self.reject(m.validate_replay,changed)
 def test_no_fabricated_execution_or_raw(self):
  for key in ('execution','raw'):
   changed=replay();changed['evidence'][key]={'fake':'receipt'};self.reject(m.validate_replay,changed)
 def test_existing_exception_cannot_replay(self):
  changed=replay();changed['exceptional_blocked_checkpoint']={};self.reject(m.add_results,changed,{})
 def test_supplement_preserves_false_frozen_and_unknown_counters(self):
  value=supplement();self.assertEqual(m.validate_supplement(value),value)
  for key,wrong in [('retained_frozen_observer_physical_closure_passed',True),('retained_frozen_observer_unknown_physical_ownership',False),('frozen_evaluation_checks_passed',True),('all_remaining_slots',1),('internal_operation_counts',0),('logical_dispatch_slot_burned',0),('checks_passed',False)]:
   changed=supplement();changed[key]=wrong;self.reject(m.validate_supplement,changed)
 def test_EACCES_must_not_be_relabelled_empty_FD_enumeration(self):
  for key,value in [('observed_fd_entries',[]),('fd_directory_observation','EMPTY'),('kernel_FDSize_zero',False),('supervisor_state','S'),('supervisor_startticks',1),('live_scoped_PGID_or_SID_members',[1])]:
   changed=supplement();changed['physical_kernel_observation'][key]=value;self.reject(m.validate_supplement,changed)
 def test_source_failure_must_precede_reserve_and_only_worker_Popen(self):
  for key,value in [('worker_reservation_line',211),('worker_Popen_line',210),('runtime_guard_top_level_before_worker_try',False),('frozen_source_and_stderr_consistent',False)]:
   changed=supplement();changed['source_failure_boundary'][key]=value;self.reject(m.validate_supplement,changed)
 def test_source_parent_tree_substitution_refused(self):
  changed=supplement();changed['published_source_commit']='0'*40;self.reject(m.validate_supplement,changed)
  changed=supplement();changed['source_trees']={'root':'0'*40};self.reject(m.validate_supplement,changed)
 def test_prospective_metadata_uses_UNKNOWN_not_zero_actual_counts(self):
  value=m.metadata({}, {},m.SUPPLEMENT_REF,m.FUTURE_REF)
  for key in ('actual_NLI_forwards','final_derived_forecasts','corpus_batches_attempted','corpus_batches_completed','model_initializations','actual_resources'):self.assertIsNone(value[key])
  self.assertEqual(value['logical_dispatch_slots_burned'],1);self.assertEqual(value['cumulative_scope']['known_prior_corpus_attempts'],33);self.assertEqual(value['cumulative_scope']['known_prior_completed_corpus_batches'],31);self.assertEqual(value['cumulative_scope']['bounded_outer_process_attempts'],38)
  self.assertEqual((value['cumulative_scope']['official_benchmark_HTTP_successes'],value['cumulative_scope']['official_benchmark_HTTP_failures']),(894,2));self.assertEqual(value['cumulative_scope']['legacy_dedicated_qualification_attempts'],6)
  self.assertTrue(all(type(v)is int and v==0 for v in value['remaining_slots'].values()))
 def test_exact_patch_only_and_frozen_scanner_still_applies(self):
  data=b'--- fixture/a\n+++ fixture/b\n';ref={'path':m.PATCH_REF['path'],'bytes':len(data),'sha256':m.sha(data)}
  with patch.object(m,'PATCH_REF',ref):
   self.assertEqual(m.public_metadata_text(c,ref['path'],data),data.decode())
   self.reject(m.public_metadata_text,c,ref['path'],data+b'x')
   self.reject(m.public_metadata_text,c,ref['path'].replace('FUTURE_ONLY','OTHER'),data)
  secret=('s'+'k-'+'x'*40).encode();secretref=dict(ref,bytes=len(secret),sha256=m.sha(secret))
  with patch.object(m,'PATCH_REF',secretref):self.reject(m.public_metadata_text,c,secretref['path'],secret)
 def test_exception_collector_and_transport_share_one_patch_gate(self):
  data=b'fixture patch\n';ref={'path':m.PATCH_REF['path'],'bytes':len(data),'sha256':m.sha(data)}
  with tempfile.TemporaryDirectory()as temp,patch.object(m,'PATCH_REF',ref):
   root=Path(temp);file=root/ref['path'];file.parent.mkdir(parents=True);file.write_bytes(data)
   found=m.collect_current(root,c);self.assertEqual(found,{ref['path']:data})
   blobs,groups=m.blocked_transport_groups(found,c,p);self.assertEqual(blobs,[]);self.assertEqual(groups[0][0]['path'],c.SCOPE+ref['path']);self.assertEqual(groups[0][0]['content'],data.decode())
   file.write_bytes(data+b'changed');self.reject(m.collect_current,root,c)
 def test_metadata_output_exclusive_and_nonfinite_refused(self):
  with tempfile.TemporaryDirectory()as temp:
   path=Path(temp)/'new.json';m.write_new(path,{'fixture':None});self.reject(m.write_new,path,{})
   bad=Path(temp)/'nan.json'
   with self.assertRaises(ValueError):m.write_new(bad,{'bad':float('nan')})
 def test_reference_path_and_byte_substitution_refused(self):
  with tempfile.TemporaryDirectory()as temp:
   root=Path(temp);path=root/'file.json';path.write_text('{}');row=m.reference(root,'file.json');self.assertEqual(m.checked(root,row),row)
   path.write_text('{"changed":true}');self.reject(m.checked,root,row)
   for name in ('../file','/file','a/../file','a\\file'):self.reject(m.reference,root,name)
 def test_modes_are_only_metadata_and_definition_has_no_worker_tools(self):
  source=(HERE/'blocked_checkpoint_v1.py').read_text();tree=ast.parse(source)
  imports=[n for n in ast.walk(tree)if isinstance(n,(ast.Import,ast.ImportFrom))]
  text=' '.join(ast.unparse(n)for n in imports)
  for name in ('torch','transformers','tokenizers','onnxruntime','subprocess','socket','requests'):self.assertNotIn(name,text)
  self.assertNotIn('globals()[args.mode](args)',ast.get_source_segment(source,next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='setup')))
  self.assertNotIn('c.walk_current(root)',source);self.assertIn('collect_current(root,c)',source)
 def test_protocol_exact_frozen_false_and_future_scope(self):
  value=json.loads((HERE/'PROTOCOL.v1.json').read_text());self.assertEqual(value['frozen'],m.FROZEN);self.assertEqual(value['one_exact_text_extension_exception'],m.PATCH_REF);self.assertEqual(value['remaining_slots'],m.REMAINING)
  self.assertEqual(value['actual_scientific_authorization'],0);self.assertEqual(value['used_confirmation_identities'],[]);self.assertTrue(value['champion_native104_unchanged'])
 def test_JS_main_CAS_and_uncertain_mutation_guards_in_memory(self):
  script=r"""const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');let calls=0;const ctx={mutate:async()=>{calls++;throw Error('UNCERTAIN_STOP')}};vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+'\nthis.mutateTest=blockedPublisherMutate;',ctx);(async()=>{const t='mcp__codex_apps__github_update_ref',good={repository_full_name:'ruvnet/RuVector',branch_name:'benchmarks/ruvector-sota-2026-10-22',force:false,expected_sha:'a'.repeat(40),sha:'b'.repeat(40)};for(const args of [{...good,branch_name:'main'},{...good,force:true},{...good,expected_sha:null},{...good,repository_full_name:'other/repo'}])await assert.rejects(ctx.mutateTest('fixture',t,args));await assert.rejects(ctx.mutateTest('fixture','unapproved',good));assert.equal(calls,0);await assert.rejects(ctx.mutateTest('fixture',t,good),/UNCERTAIN_STOP/);assert.equal(calls,1);process.stdout.write('6 mocked guards passed;0 external calls')})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1});"""
  run=subprocess.run(['node','-e',script,str(HERE/'publish_blocked_v1.js')],text=True,capture_output=True,timeout=10);self.assertEqual(run.returncode,0,run.stderr);self.assertIn('6 mocked guards passed',run.stdout)

if __name__=='__main__':unittest.main()
