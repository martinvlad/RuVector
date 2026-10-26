"""New source-interface/fence fixtures only; never real cases/private artifacts or modes."""
import ast,copy,importlib.util,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import e43_qualification as Q
import e43_evaluate as E
F=Q.F
CORE=Path('/workspace/ruvector-e43-engineering/implementation-v1/project/experiments/sota-2026-10-22/runtime/epoch43')
def isolated(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);return m
class ExactInterfaces(unittest.TestCase):
 def test_actual_counter_source_vs_independent_recipe_and_no_backend_invention(self):
  C=isolated('pure_counter_fixture',CORE/'counters.py');d={'357':3,'227':9,'46':17,'212':2};expected=C.expected_fixed(d);self.assertTrue(Q.same_fact(expected,Q.expected_counts(d)));self.assertEqual(expected['native_insertions_completed'],31);self.assertEqual(expected['BGE_texts_completed'],43);self.assertEqual(expected['BGE_forward_calls_completed'],19);self.assertEqual(expected['completion_requests_completed'],36);self.assertNotIn('backend_forward_batch_count',expected);self.assertEqual(set(C.initial()),set(expected)|{'local_HTTP_requests_attempted','local_HTTP_requests_completed','health_requests_attempted','health_requests_completed','prompt_tokenize_requests_attempted','prompt_tokenize_requests_completed'})
 def test_final_launcher_exact_twelve_predicates_and_strong_supervisor_fence(self):
  tree=ast.parse((CORE/'launch.py').read_text());runtime=next(ast.literal_eval(n.value)for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='INVARIANTS'for t in n.targets));self.assertEqual(set(runtime),Q.INVARIANTS);self.assertEqual(len(runtime),12)
  identity={'pid':12345,'startticks':45678,'pgid':12345,'sid':12345};r={'path':'raw.json','bytes':2,'sha256':'a'*64};x={'path':'execution.json','bytes':2,'sha256':'b'*64};refs={'raw':r,'execution':x};execution={'status':'WORKER_COMPLETED','worker_exit_code':0,'errors':[],'wall_seconds':100.0,'raw':r,'plan_sha256':'c'*64,'supervisor_identity':identity};completion={'schema_version':1,'epoch':43,'kind':F.KIND,'phase':'dev','plan_sha256':'c'*64,'execution':x,'errors':[],'invariants':{k:True for k in runtime},'supervisor_identity':identity};physical={'physical_supervisor_absent':False,'observed_supervisor_state':'Z','supervisor_exit_status_source':'PROC_STAT_FIELD52_EXACT_STABLE_ZOMBIE','observed_supervisor_exit_wait_status':0,'observed_closed_by_monotonic_seconds':610.0,'supervisor_identity':identity};dispatch={'dispatch_monotonic_seconds':500.0}
  self.assertEqual(Q.supervisor_qualification(execution,completion,{'work_completed_monotonic_seconds':590.0},refs,physical,None,dispatch)['observed_full_supervisor_bound_seconds'],110.0)
  changes=[('wait',256),('wait',None),('end',1100.000001),('absent',True),('invariant',False),('exit',False),('extra',True)]
  for key,value in changes:
   p=copy.deepcopy(physical);c=copy.deepcopy(completion);e=copy.deepcopy(execution)
   if key=='wait':p['observed_supervisor_exit_wait_status']=value
   elif key=='end':p['observed_closed_by_monotonic_seconds']=value
   elif key=='absent':p['physical_supervisor_absent']=value
   elif key=='invariant':c['invariants']['worker_preexec_CPU_network_guard_valid']=False
   elif key=='exit':e['worker_exit_code']=False
   else:c['invariants']['extra']=True
   with self.subTest(key=key,value=value),self.assertRaises(ValueError):Q.supervisor_qualification(e,c,{'work_completed_monotonic_seconds':590.0},refs,p,None,dispatch)
 def test_570_work_600_all_cleanup_scope_from_actual_producer(self):
  tree=ast.parse((CORE/'launch.py').read_text());self.assertIn('whole_soft_deadline_met',(CORE/'launch.py').read_text());self.assertIn('work_completed_monotonic_seconds',(CORE/'launch.py').read_text());identity={'pid':12345,'startticks':45678,'pgid':12345,'sid':12345};r={'path':'raw.json','bytes':2,'sha256':'a'*64};x={'path':'execution.json','bytes':2,'sha256':'b'*64};refs={'raw':r,'execution':x};e={'status':'WORKER_COMPLETED','worker_exit_code':0,'errors':[],'wall_seconds':590.0,'raw':r,'plan_sha256':'c'*64,'supervisor_identity':identity};c={'schema_version':1,'epoch':43,'kind':F.KIND,'phase':'dev','plan_sha256':'c'*64,'execution':x,'errors':[],'invariants':{k:True for k in Q.INVARIANTS},'supervisor_identity':identity};p={'physical_supervisor_absent':False,'observed_supervisor_state':'Z','supervisor_exit_status_source':'PROC_STAT_FIELD52_EXACT_STABLE_ZOMBIE','observed_supervisor_exit_wait_status':0,'observed_closed_by_monotonic_seconds':1091.,'supervisor_identity':identity};d={'dispatch_monotonic_seconds':500.}
  result=Q.supervisor_qualification(e,c,{'work_completed_monotonic_seconds':1069.},refs,p,None,d);self.assertEqual(result['observed_full_supervisor_bound_seconds'],591.)
  with self.assertRaisesRegex(ValueError,'INDEPENDENT_REPLAY570_WORK600_ALL_BOUND'):Q.supervisor_qualification(e,c,{'work_completed_monotonic_seconds':1071.},refs,p,None,d)
  for bad in [float('nan'),float('inf'),True,499.]:
   with self.subTest(work=bad),self.assertRaises(ValueError):Q.supervisor_qualification(e,c,{'work_completed_monotonic_seconds':bad},refs,p,None,d)
 def test_actual_prompt_constant_and_strict_767_cap(self):
  source=(CORE/'protocol.py').read_text();tree=ast.parse(source);values={}
  for n in tree.body:
   if isinstance(n,ast.Assign):
    for t in n.targets:
     if isinstance(t,ast.Name):
      try:values[t.id]=ast.literal_eval(n.value)
      except(ValueError,TypeError):pass
  self.assertEqual(values['SYSTEM'],Q.A.SYSTEM);self.assertEqual(Q.A.render('Invented claim.','Invented first.','Invented second.'),'<|im_start|>system\n'+values['SYSTEM']+'<|im_end|>\n<|im_start|>user\nSOURCE EXCERPT 1:\nInvented first.\n\nSOURCE EXCERPT 2:\nInvented second.\n\nCLAIM:\nInvented claim.\n\nANSWER (N, E, or C):<|im_end|>\n<|im_start|>assistant\n');self.assertEqual(values['MAX_PROMPT_TOKENS'],767)
 def test_public_descriptor_relative_private_descriptor_absolute_and_capture_traversal_stop(self):
  with tempfile.TemporaryDirectory()as td:
   w=Path(td);p=w/'project/audit/safe.json';p.parent.mkdir(parents=True);p.write_text('{}');private=w/'private.json';private.write_text('{}')
   with patch.object(F,'WORKDIR',w):self.assertEqual(F.ref(p)['path'],'audit/safe.json');self.assertEqual(F.ref(private)['path'],str(private));self.assertEqual(E.public_emit(F.ref(p),w/'project')['path'],'audit/safe.json')
  for path in ['../escape','/absolute','http/../../escape','http/link/../escape']:
   with self.subTest(path=path),self.assertRaises(ValueError):Q.A.private_bytes({'reference_root':'external_run_directory','path':path,'bytes':1,'sha256':'a'*64},F.WORKDIR/'private/run')
 def test_failure_unknown_custody_and_type_exact_binding_without_gold_body(self):
  command={'requested_mode':'EVALUATE','CLI_invocations':1,'evaluate_function_calls':0,'capture_failure_function_calls':1,'bind_function_calls':0};v=E.baseline('REJECTED_DEV_INTEGRITY','c'*64,command);self.assertFalse(v['evaluation_executed']);self.assertIsNone(v['metrics']);self.assertTrue(all(x=='NOT_EVALUATED'for x in v['gate_checks'].values()));self.assertIsNone(v['label_custody']['semantic_label_decodes']);self.assertTrue(v['label_custody']['semantic_decode_count_uncertain']);self.assertEqual(E.report_custody({'semantic_label_decodes':2,'decode_attempted_tokens':3,'semantic_decode_count_uncertain':True}),{'semantic_label_decodes':2,'decode_attempted_tokens':3,'semantic_decode_count_uncertain':True});self.assertFalse(Q.same_fact({'v':[0,{'b':False}]},{'v':[False,{'b':0}]}))
if __name__=='__main__':unittest.main()
