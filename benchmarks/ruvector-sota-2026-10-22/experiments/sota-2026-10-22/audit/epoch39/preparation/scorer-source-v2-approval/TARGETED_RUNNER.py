"""Exact source of the executed V2-only inline regression runner; no real modes."""
import sys,unittest,tempfile,copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/workspace/ruvector-e39-runtime-source-audit/scorer-source-review-v2/snapshot/experiments/sota-2026-10-22/audit/epoch39')
import test_finfact_closure as CT
import finfact_closure as C
import finfact_io as I
class V2TargetedPositiveAndExit(unittest.TestCase):
 def test_complete_qualified_bundle_passes_and_actual_nonzero_wait_rejects(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);a=CT.Closure().fixture(root)
   with patch.object(C.D,'check_physical_gold_fence',return_value={})as fence:
    checked=C.checked_bundle(a,root);self.assertTrue(checked['supervisor_qualification']['checks_passed']);fence.assert_called_once()
   body=checked['objects'];refs=checked['references'];physical=copy.deepcopy(body['physical_closure']);physical['observed_supervisor_exit_wait_status']=256
   completion=I.load_ref(physical['evidence']['completion'],root)
   with self.assertRaisesRegex(ValueError,'ACTUAL_SUPERVISOR_EXIT_STATUS_ZERO_REQUIRED'):
    C.X.supervisor_qualification(body['execution'],completion,body['raw'],refs,physical,root,body['dispatch'])
names=['test_finfact_execution.Execution.test_exact_canonical_counter_document_without_invented_variable_field','test_finfact_closure.Closure.test_failed_overbudget_and_false_invariant_supervisors_rejected_before_gold']
suite=unittest.defaultTestLoader.loadTestsFromNames(names);suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(V2TargetedPositiveAndExit));assert suite.countTestCases()==3
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
