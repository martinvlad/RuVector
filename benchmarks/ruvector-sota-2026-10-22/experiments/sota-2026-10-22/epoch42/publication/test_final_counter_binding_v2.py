"""One disjoint source-grounded FINAL-counter regression, no production modes."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import ast,copy,unittest
import publication_common_v1 as c
import epoch_bindings_v1 as binding

class FinalCounterBinding(unittest.TestCase):
 def test_actual_final_counter_predicate_keeps_module_namespace(self):
  source=Path(__file__).with_name('stage_publication_v1.py').read_text()
  tree=ast.parse(source);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='checked_final')
  local=next(n for n in fn.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='bound_report'for t in n.targets))
  counter=next(n for n in fn.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='counts'for t in n.targets))
  pos=fn.body.index(counter);predicate=fn.body[pos+1]
  self.assertIn('binding.PRIOR_BOUNDED_NATIVE_PROCESS_ATTEMPTS',ast.unparse(predicate))
  # Compile exact actual statements into a bounded metadata-only probe. The
  # fabricated parse returns a document; no file/model/dataset is opened.
  probe=ast.FunctionDef(name='probe',args=ast.arguments(posonlyargs=[],args=[ast.arg(arg='root'),ast.arg(arg='m')],kwonlyargs=[],kw_defaults=[],defaults=[]),body=[copy.deepcopy(local),copy.deepcopy(counter),copy.deepcopy(predicate),ast.Return(value=ast.Name(id='counts',ctx=ast.Load()))],decorator_list=[])
  code=ast.fix_missing_locations(ast.Module(body=[probe],type_ignores=[]))
  documents=[]
  def fake_parse(path):
   documents.append(path);return {'publication_binding_checks_passed':True,'evidence':{'fixture':True}}
  scope={'binding':binding,'parse':fake_parse,'require':c.require};exec(compile(code,'actual-final-counter-statements','exec'),scope)
  counts={'corpus_attempts':None,'completed_corpus_batches':None,'legacy_native_qualification_process_attempts':6,'bounded_native_process_attempts':binding.PRIOR_BOUNDED_NATIVE_PROCESS_ATTEMPTS+1,'benchmark_HTTP_successes':binding.CUMULATIVE_HTTP_SUCCESSES,'benchmark_HTTP_failures':binding.CUMULATIVE_HTTP_FAILURES}
  m={'binding':{'path':'fabricated-public-binding.json'},'actual_execution':{'worker_attempts':1},'cumulative_execution':counts}
  self.assertEqual(scope['probe'](Path('/source-fixture-only'),m),counts);self.assertEqual(len(documents),1)
  wrong=copy.deepcopy(m);wrong['cumulative_execution']['bounded_native_process_attempts']+=1
  with self.assertRaises(ValueError):scope['probe'](Path('/source-fixture-only'),wrong)
  self.assertEqual(len(documents),2)

if __name__=='__main__':unittest.main()
