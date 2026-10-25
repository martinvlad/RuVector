"""Unrelated fake tokenization/metadata only; no ML/native/data capabilities."""
from pathlib import Path
import ast,contextlib,importlib.util,io,json,math,re,tempfile,time,unittest
from unittest.mock import patch
H=Path(__file__).resolve().parent

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
N=load('unrelated_nli_fixture',H/'nli.py');K=load('unrelated_counter_fixture',H/'counters.py');L=load('unrelated_launcher_fixture',H/'runtime/launch.py')
class Encoding(dict):
 def __init__(self,tokens,sequences,offsets):super().__init__(input_ids=tokens,attention_mask=[1]*len(tokens),offset_mapping=offsets);self.seq=sequences
 def sequence_ids(self):return self.seq
class FakeTokenizer:
 def __init__(self):self.calls=[]
 def __call__(self,text,*,text_pair,**kw):
  self.calls.append(kw);a=list(re.finditer(r'\S+',text));b=list(re.finditer(r'\S+',text_pair));count=len(a)
  if kw.get('truncation')=='only_first':a=a[:max(0,kw['max_length']-len(b)-3)]
  tokens=[1]+list(range(10,10+len(a)))+[2]+list(range(10000,10000+len(b)))+[2]
  return Encoding(tokens,[None]+[0]*len(a)+[None]+[1]*len(b)+[None],[(0,0)]+[m.span()for m in a]+[(0,0)]+[m.span()for m in b]+[(0,0)])
class HarnessFixtures(unittest.TestCase):
 def test_official_ordered_threshold_is_not_argmax(self):
  r=N.decisions([math.log(.4),math.log(.35),math.log(.25)],'b354');self.assertEqual(r['primary_label'],'false');self.assertEqual(r['argmax_label'],'true')
  self.assertEqual(N.decisions([0,-10000,0],'b354')['primary_label'],'false')
  self.assertEqual(N.decisions([-10000,1,0],'b354')['primary_label'],'neutral')
 def test_stable_unclipped_logprobs_and_label_maps(self):
  r=N.decisions([10000,0,-10000],'xxlarge');self.assertEqual(r['argmax_label'],'false');self.assertEqual(r['log_probabilities_E_C_N'],[-20000.0,0.0,-10000.0]);self.assertEqual(r['probabilities_E_C_N'][0],0)
 def test_only_first_preserves_whole_claim_and_counts_real_three_tokenizer_calls(self):
  t=FakeTokenizer();c=K.initial();f,a,private,elapsed=N.prepare(t,' '.join('fixture'+str(i)for i in range(300)),'Invented quarterly assertion 2099',['unit'],c)
  self.assertEqual(len(t.calls),3);self.assertEqual(t.calls[-1]['truncation'],'only_first');self.assertTrue(a['claim_complete']);self.assertTrue(a['premise_truncated']);self.assertEqual(a['joint_tokens'],248)
  self.assertEqual(c['NLI_full_pair_tokenizer_calls_completed'],1);self.assertEqual(c['NLI_claim_fit_tokenizer_calls_completed'],1);self.assertEqual(c['NLI_capped_pair_tokenizer_calls_completed'],1)
  self.assertNotIn('premise',a);self.assertNotIn('input_ids',a);self.assertIn('premise',private)
 def test_claim_cannot_fit_stops_before_capped_or_NNI(self):
  t=FakeTokenizer()
  with self.assertRaisesRegex(ValueError,'FULL_HYPOTHESIS_EXCEEDS248'):N.prepare(t,'tiny invented source',' '.join('claim'for _ in range(300)),[])
  self.assertEqual(len(t.calls),2)
 def test_known_fullguard_failure_captured_without_popen_and_unknown_counts(self):
  with tempfile.TemporaryDirectory(prefix='e39-fake-launch-')as d:
   base=Path(d);root=base/'project';study=root/'study';study.mkdir(parents=True);external=base/'run-external';scope=base/'scope';scope.mkdir();planfile=study/'plan.json'
   plan={'expected_operation_counters':{'dev':K.expected()},'data_roles':{'dev':['fixture'+str(i)for i in range(12)]},'arms':['a','b','c','d']};planfile.write_text(json.dumps(plan));admission=study/'SOURCE_ADMISSION.json';admission.write_text('{}')
   sha=L.C.sha(planfile);claim={'dispatch_monotonic_seconds':time.monotonic(),'dispatch_unix_seconds':time.time()}
   (study/'DISPATCH_RESERVATION.json').write_text('{}');(study/'DISPATCH_ATTEMPT.json').write_text('{}')
   fakeproc={'pid':12345,'ticks':54321,'pgid':12345,'sid':12345,'ppid':1,'state':'R'}
   args=['launch.py','--plan',str(planfile),'--admission',str(admission),'--scope',str(scope),'--expected-plan-sha',sha,'--phase','dev']
   with patch.object(L.sys,'argv',args),patch.object(L.C,'SCOPE',scope),patch.object(L.C,'STUDY',study),patch.object(L.C,'ROOT',root),patch.object(L.C,'owner_lock'),patch.object(L.C,'dispatch_proof',return_value=(claim,{})),patch.object(L.C,'admission',return_value=({},{})),patch.object(L.C,'verify_plan',return_value=plan),patch.object(L.C,'verify_runtime',side_effect=ValueError('invented full guard stop')),patch.object(L.C,'proc',return_value=fakeproc),patch.object(L.os,'getpid',return_value=12345),patch.object(L.os,'sched_setaffinity'),patch.object(L.os,'sched_getaffinity',return_value={0,1}),patch.object(L.subprocess,'Popen',side_effect=AssertionError('NO POPEN ALLOWED IN GUARD FIXTURE'))as forbidden,contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(L.main(),2);forbidden.assert_not_called()
   execution=json.loads((study/'runs/dev/execution.json').read_text());self.assertFalse(execution['worker_popen_attempted']);self.assertTrue(execution['owned_live_processes_closed']);self.assertEqual(execution['raw_operation_counters_source'],'UNKNOWN');self.assertIsNone(execution['raw_operation_counters']);self.assertFalse(execution['operation_counts_complete']);self.assertNotIn('message',execution['launcher_error']);self.assertIsNone(execution['raw']);self.assertTrue((study/'SUPERVISOR_COMPLETION.json').is_file())
 def test_source_syntax_and_no_top_level_ml_imports(self):
  for p in H.rglob('*.py'):
   tree=ast.parse(p.read_text());self.assertLess(len(p.read_text().splitlines()),500,str(p))
   for x in tree.body:
    if isinstance(x,(ast.Import,ast.ImportFrom)):
     names=[a.name.split('.')[0]for a in x.names]if isinstance(x,ast.Import)else[x.module.split('.')[0]]
     self.assertFalse(set(names)&{'torch','transformers','tokenizers','numpy','onnxruntime'},str(p))
if __name__=='__main__':unittest.main()
