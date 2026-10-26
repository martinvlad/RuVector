"""One source-bound, synthetic regression; never imports or runs the launcher."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import unittest
from test_e42_qualification import Qualification, Q

CORE_READY_SHA256 = '014fc07c6373636d5f40af68f86ff7aa2e1a2cf83d0ba588a3acd7d577727d7d'
LAUNCH_PATH = 'experiments/sota-2026-10-22/candidate/epoch42/runtime/launch.py'
LAUNCH_SHA256 = '06dd36136ff831b6fb06e31318403ddec865873f4b136f99bdb12bc71a865f34'
CPU_KEY = 'whole_worker_CPU_guard_before_exec'

class FinalRuntimeInvariants(unittest.TestCase):
 def test_final_ast_emitted_fifteen_and_cpu_guard_required(self):
  core = Path(os.environ['E42_FINAL_CORE_SNAPSHOT'])
  ready_bytes = (core/'READY.v1.json').read_bytes()
  self.assertEqual(hashlib.sha256(ready_bytes).hexdigest(), CORE_READY_SHA256)
  refs = [r for r in json.loads(ready_bytes)['files'] if r['path'] == LAUNCH_PATH]
  self.assertEqual(len(refs), 1)
  launch = (core/'project'/LAUNCH_PATH).read_bytes()
  self.assertEqual(len(launch), refs[0]['bytes'])
  self.assertEqual(hashlib.sha256(launch).hexdigest(), refs[0]['sha256'])
  self.assertEqual(refs[0]['sha256'], LAUNCH_SHA256)
  tree = ast.parse(launch)
  reducers = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'completion_invariants']
  self.assertEqual(len(reducers), 1)
  returns = [n.value for n in ast.walk(reducers[0]) if isinstance(n, ast.Return)]
  self.assertEqual(len(returns), 1)
  self.assertIsInstance(returns[0], ast.Dict)
  base = {ast.literal_eval(k) for k in returns[0].keys}
  self.assertEqual(len(base), 14)
  appended = []
  for n in ast.walk(tree):
   if isinstance(n, ast.Assign):
    for target in n.targets:
     if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == 'invariants':
      appended.append((ast.literal_eval(target.slice), n.value))
  self.assertEqual([k for k, _ in appended], [CPU_KEY])
  # The added predicate still checks the actual pre-exec artifact facts.
  cpu_predicate = ast.dump(appended[0][1], include_attributes=False)
  for literal in ['CPU_GUARD_INSTALLED_BEFORE_EXEC', 'CPU_affinity', 'NoNewPrivs', 'Seccomp']:
   self.assertIn(literal, cpu_predicate)
  raw_emissions = [n for n in ast.walk(tree) if isinstance(n, ast.Dict) and any(isinstance(k, ast.Constant) and k.value == 'raw_closure_invariants' for k in n.keys)]
  self.assertTrue(any(any(isinstance(k, ast.Constant) and k.value == 'raw_closure_invariants' and isinstance(v, ast.Name) and v.id == 'invariants' for k, v in zip(n.keys, n.values)) for n in raw_emissions))
  emitted = base | {CPU_KEY}
  self.assertEqual(len(emitted), 15)
  self.assertEqual(emitted, Q.INVARIANTS)
  fixture = Qualification()
  positive = fixture.fixture()
  positive[0]['raw_closure_invariants'] = dict.fromkeys(emitted, True)
  self.assertTrue(fixture.call(positive)['actual_all15_invariants_true'])
  for mutation in ['false_cpu', 'missing_cpu', 'extra_key']:
   sample = copy.deepcopy(positive)
   values = sample[0]['raw_closure_invariants']
   if mutation == 'false_cpu': values[CPU_KEY] = False
   elif mutation == 'missing_cpu': del values[CPU_KEY]
   else: values['unrecognized_runtime_fact'] = True
   with self.assertRaisesRegex(ValueError, 'ALL15_RAW_CLOSURE_INVARIANTS_REQUIRED'):
    fixture.call(sample)
  sample = copy.deepcopy(positive)
  sample[-1]['actual_proc_status']['Seccomp'] = '0'
  with self.assertRaisesRegex(ValueError, 'ACTUAL_CPU_GUARD_BEFORE_EXEC'):
   fixture.call(sample)

if __name__ == '__main__': unittest.main()
