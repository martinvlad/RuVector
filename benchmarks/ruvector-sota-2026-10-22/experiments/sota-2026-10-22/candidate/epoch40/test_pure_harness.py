"""Disjoint fake features/process metadata/JSdecoder only. No actualmodel/case/native."""
from pathlib import Path
import ast,contextlib,importlib.util,io,json,math,re,struct,subprocess,tempfile,time,unittest
from unittest.mock import patch
H=Path(__file__).resolve().parent

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
N=load('unrelated_nli_fixture',H/'nli.py');K=load('unrelated_counter_fixture',H/'counters.py');L=load('unrelated_launch_fixture',H/'runtime/launch.py');V=load('unrelated_vectors',H/'vector_codec.py')
class Encoding(dict):
 def __init__(self,ids,seq,offsets):super().__init__(input_ids=ids,attention_mask=[1]*len(ids),offset_mapping=offsets);self.seq=seq
 def sequence_ids(self):return self.seq
class FakeTokenizer:
 def __init__(self):self.calls=[]
 def __call__(self,text,*,text_pair,**kw):
  self.calls.append(kw);a=list(re.finditer(r'\S+',text));b=list(re.finditer(r'\S+',text_pair))
  if kw.get('truncation')=='only_first':a=a[:max(0,kw['max_length']-len(b)-3)]
  return Encoding([1]+list(range(10,10+len(a)))+[2]+list(range(10000,10000+len(b)))+[2],[None]+[0]*len(a)+[None]+[1]*len(b)+[None],[(0,0)]+[m.span()for m in a]+[(0,0)]+[m.span()for m in b]+[(0,0)])
class HarnessFixtures(unittest.TestCase):
 def test_official_threeway_canonical_argmax_no_finfact_threshold(self):
  for tag in('b354','tasksource'):
   r=N.decisions([math.log(.4),math.log(.35),math.log(.25)],tag);self.assertEqual(r['primary_label'],'Entailment');self.assertEqual(r['canonical_argmax_index'],1);self.assertEqual(r['argmax_label'],r['primary_label'])
   self.assertEqual(N.decisions([0,0,-10000],tag)['primary_label'],'NotMentioned');self.assertEqual(N.decisions([0,0,0],tag)['primary_label'],'NotMentioned')
 def test_stable_unclipped_logp_and_exact_native_mapping(self):
  r=N.decisions([10000,0,-10000],'tasksource');self.assertEqual(r['log_probabilities_N_E_C'],[-10000.0,0.0,-20000.0]);self.assertEqual(r['probabilities_N_E_C'],[0,1,0]);self.assertEqual(r['primary_label'],'Entailment')
 def test_joint512_onlyfirst_keeps_whole_claim_three_real_tokenizer_ops(self):
  t=FakeTokenizer();c=K.initial(12);f,a,private,elapsed=N.prepare(t,' '.join('unrelated'+str(i)for i in range(600)),'Unrelated invented assertion 2099',['unit'],c)
  self.assertEqual(len(t.calls),3);self.assertEqual(t.calls[-1]['truncation'],'only_first');self.assertEqual(a['joint_tokens'],512);self.assertTrue(a['claim_complete']);self.assertTrue(a['premise_truncated']);self.assertNotIn('premise',a);self.assertIn('premise',private)
  for key in('NLI_full_pair_tokenizer_calls_completed','NLI_claim_fit_tokenizer_calls_completed','NLI_capped_pair_tokenizer_calls_completed'):self.assertEqual(c[key],1)
 def test_oversized_hypothesis_stops_before_capped_or_model(self):
  t=FakeTokenizer()
  with self.assertRaisesRegex(ValueError,'FULL_HYPOTHESIS_EXCEEDS512'):N.prepare(t,'tiny unrelated source',' '.join('claim'for _ in range(600)),[])
  self.assertEqual(len(t.calls),2)
 def test1024_unit_bound_actual_python_and_pure_js_transport(self):
  payload=(struct.pack('<f',1.0)+bytes(383*4))*1024;block=V.encode(payload,1024);self.assertEqual(V.decode(block),payload)
  with self.assertRaises(ValueError):V.encode(payload+payload[:1536],1025)
  with tempfile.TemporaryDirectory(prefix='e40-pure-transport-')as d:
   p=Path(d)/'invented.json';p.write_text(json.dumps(block));script="const fs=require('fs');const m=require(process.argv[1]);const b=JSON.parse(fs.readFileSync(process.argv[2]));if(m.decode(b).length!==1024)process.exit(2);if(Object.keys(require.cache).some(p=>p.endsWith('.node')))process.exit(3);console.log('PURE1024_NO_NATIVE_LOAD');"
   result=subprocess.run(['node','-e',script,str(H/'native_helper.cjs'),str(p)],capture_output=True,text=True,check=True);self.assertEqual(result.stdout.strip(),'PURE1024_NO_NATIVE_LOAD')
 def test_unit_counters_derive_only_admitted_complete_source_total(self):
  a=K.expected(12);b=K.expected(120);self.assertEqual(len(a),68);self.assertEqual(b['native_insertions_completed'],120);self.assertEqual(b['BGE_texts_completed'],132);self.assertEqual(b['NLI_forward_calls_completed'],48);self.assertEqual(b['canonical_argmax_decisions_completed'],48)
  with self.assertRaises(ValueError):K.expected(True)
 def test_known_guard_failure_captured_no_popen_unknown_counter_state(self):
  with tempfile.TemporaryDirectory(prefix='e40-fake-launch-')as d:
   base=Path(d);root=base/'project';study=root/'study';study.mkdir(parents=True);scope=base/'scope';scope.mkdir();planfile=study/'plan.json';plan={'expected_operation_counters':{'dev':K.expected(12)},'data_roles':{'dev':['fixture'+str(i)for i in range(12)]},'arms':['a','b','c','d']};planfile.write_text(json.dumps(plan));admission=study/'SOURCE_ADMISSION.json';admission.write_text('{}');sha=L.C.sha(planfile);claim={'dispatch_monotonic_seconds':time.monotonic(),'dispatch_unix_seconds':time.time()}
   (study/'DISPATCH_RESERVATION.json').write_text('{}');(study/'DISPATCH_ATTEMPT.json').write_text('{}');fake={'pid':12345,'ticks':54321,'pgid':12345,'sid':12345,'ppid':1,'state':'R'};argv=['launch.py','--plan',str(planfile),'--admission',str(admission),'--scope',str(scope),'--expected-plan-sha',sha,'--phase','dev']
   with patch.object(L.sys,'argv',argv),patch.object(L.C,'SCOPE',scope),patch.object(L.C,'STUDY',study),patch.object(L.C,'ROOT',root),patch.object(L.C,'owner_lock'),patch.object(L.C,'dispatch_proof',return_value=(claim,{})),patch.object(L.C,'admission',return_value=({},{})),patch.object(L.C,'verify_plan',return_value=plan),patch.object(L.C,'verify_runtime',side_effect=ValueError('invented guard failure')),patch.object(L.C,'proc',return_value=fake),patch.object(L.os,'getpid',return_value=12345),patch.object(L.os,'sched_setaffinity'),patch.object(L.os,'sched_getaffinity',return_value={0,1}),patch.object(L.subprocess,'Popen',side_effect=AssertionError('NO POPEN'))as forbidden,contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(L.main(),2);forbidden.assert_not_called()
   value=json.loads((study/'runs/dev/execution.json').read_text());self.assertFalse(value['worker_popen_attempted']);self.assertTrue(value['owned_live_processes_closed']);self.assertEqual(value['raw_operation_counters_source'],'UNKNOWN');self.assertIsNone(value['raw_operation_counters']);self.assertFalse(value['operation_counts_complete']);self.assertIsNone(value['raw']);self.assertEqual(json.loads((study/'SUPERVISOR_COMPLETION.json').read_text())['plan_sha256'],sha)
 def test_source_ast_below500_and_no_top_level_ml_import(self):
  for p in H.rglob('*.py'):
   tree=ast.parse(p.read_text());self.assertLess(len(p.read_text().splitlines()),500,str(p))
   for node in tree.body:
    if isinstance(node,(ast.Import,ast.ImportFrom)):
     names=[a.name.split('.')[0]for a in node.names]if isinstance(node,ast.Import)else[node.module.split('.')[0]];self.assertFalse(set(names)&{'torch','transformers','tokenizers','numpy','onnxruntime'})
if __name__=='__main__':unittest.main()
