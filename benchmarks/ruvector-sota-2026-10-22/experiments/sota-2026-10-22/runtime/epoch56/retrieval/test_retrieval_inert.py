"""Meaningful source/geometry/tie-policy tests. No real models/native/data imports."""
import ast
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('retrieval_support',HERE/'retrieval_support.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

class InertTests(unittest.TestCase):
 def test_import_no_scientific_runtime(self):
  import sys
  self.assertFalse(set(sys.modules)&{'numpy','torch','onnxruntime','tokenizers','transformers'})
 def test_bm25_retrieves_term(self):
  idx=s.bm25_index(['alpha beta','gamma delta','alpha gamma'])
  ids=['b','a','c'];order,score=s.bm25_query('beta',idx,ids)
  self.assertEqual(order[0],0);self.assertGreater(score[0],score[1])
 def test_bm25_zero_ties_lexical(self):
  idx=s.bm25_index(['alpha','beta','gamma']);ids=['z','a','m'];order,_=s.bm25_query('unseen',idx,ids)
  self.assertEqual([ids[i]for i in order],['a','m','z'])
 def test_filehash_rejects_modified_size(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'x';p.write_bytes(b'abc');r={'path':str(p),'bytes':4,'sha256':hashlib.sha256(b'abc').hexdigest()}
   with self.assertRaisesRegex(ValueError,'EXACT_ASSET_SIZE_SHA256'):s.verify(r)
 def test_filehash_rejects_symlink(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'x';p.write_bytes(b'abc');q=Path(d)/'y';q.symlink_to(p);r={'path':str(q),'bytes':3,'sha256':hashlib.sha256(b'abc').hexdigest()}
   with self.assertRaisesRegex(ValueError,'REGULAR_NONSYMLINK_ASSET'):s.verify(r)
 def test_output_once_only(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'result';s.put(p,{'x':1})
   with self.assertRaises(FileExistsError):s.put(p,{'x':2})
 def test_supervisor_exact_guardian21(self):
  t=ast.parse((HERE/'retrieval_supervisor.py').read_text());f=next(n for n in ast.walk(t)if isinstance(n,ast.FunctionDef)and n.name=='fence');const=[n.value for n in ast.walk(f)if isinstance(n,ast.Constant)]
  for x in [56,21,181168,42762589]:self.assertIn(x,const)
  for x in [55,20,177383,42200361]:self.assertNotIn(x,const)
 def test_supervisor_no_async_raise_signal_handler(self):
  t=ast.parse((HERE/'retrieval_supervisor.py').read_text());f=next(n for n in ast.walk(t)if isinstance(n,ast.FunctionDef)and n.name=='stop_for_external_signal');self.assertFalse(any(isinstance(n,ast.Raise)for n in ast.walk(f)))
 def test_supervisor_requires_engineering_first(self):
  txt=(HERE/'retrieval_supervisor.py').read_text();self.assertIn("parse(ad['prerequisite_engineering_acceptance_ref'])",txt);self.assertIn("first['native_counter_accounting']['qualified'] is True",txt)
 def test_worker_no_qrels_scoring_imports(self):
  t=ast.parse((HERE/'retrieval_worker.py').read_text());names=[]
  for n in ast.walk(t):
   if isinstance(n,ast.Import):names +=[a.name for a in n.names]
   if isinstance(n,ast.ImportFrom):names.append(n.module or '')
  self.assertFalse(any(any(x in n for x in ['pytrec','custom_metrics','pyarrow'])for n in names))
 def test_worker_seals_before_qualified_status(self):
  txt=(HERE/'retrieval_worker.py').read_text();self.assertLess(txt.index("s.put(out/'forecasts.json',forecasts)"),txt.index("raw['status']='RETRIEVAL_DEVELOPMENT_FORECASTS_SEALED_NOT_SCORED'"))
 def test_worker_has_no_NLI_or_model_forward(self):
  txt=(HERE/'retrieval_worker.py').read_text();self.assertNotIn('Reader(',txt);self.assertNotIn('torch.',txt);self.assertNotIn('from_pretrained',txt)
 def test_native_child_hash_pid_bindings(self):
  txt=(HERE/'retrieval_support.py').read_text()
  for x in ["value['helper_pid']==identity['pid']","value['bundle_sha256']==source['sha256']","value['native_binary_sha256']==plan['native_binary']['sha256']","value['helper_source_sha256']==plan['native_helper_source']['sha256']"]:self.assertIn(x,txt)
 def test_ledger_no_expected_fill(self):
  txt=(HERE/'retrieval_support.py').read_text();self.assertIn('ledger.capture(',txt);self.assertIn('ledger.finalize(value)',txt);self.assertNotIn('counters.update(',txt)
 def test_syntax_all_sources(self):
  for p in HERE.glob('*.py'):ast.parse(p.read_text(),filename=str(p))

if __name__=='__main__':unittest.main()
