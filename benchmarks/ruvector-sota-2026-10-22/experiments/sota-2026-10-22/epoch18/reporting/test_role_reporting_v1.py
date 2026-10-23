"""Final role-state regressions using generic metadata only."""
import copy
import importlib.util
from pathlib import Path
import unittest

P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('independent_e18_roles',P/'engine-reporting/build_final.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class Roles(unittest.TestCase):
    def setUp(self):
        self.pre={'development':{'annotation_choices_projected':24,'model_attempted':False},
                  'confirmation':{'annotation_choices_projected':0,'model_attempted':False}}
        empty={'reserved_attempt':False,'verified_worker_started':False,'started_HTTP_requests':0,
               'successful_HTTP_status200':0,'completion':None,'observed_execution':{}}
        self.phases={name:copy.deepcopy(empty)for name in M.PHASES}

    def test_actual_activity_overwrites_stale_role_without_mutating_history(self):
        original=copy.deepcopy(self.pre)
        self.phases['development'].update(reserved_attempt=True,verified_worker_started=True,
            started_HTTP_requests=24,successful_HTTP_status200=24,
            observed_execution={'new_reader_forward_pairs_completed':72})
        out=M.derive_final_roles(self.pre,self.phases,0,False,{'sha256':'generic_snapshot'})
        self.assertTrue(out['development']['model_attempted'])
        self.assertEqual(out['development']['HTTP_successful_decisions'],24)
        self.assertFalse(out['confirmation']['model_attempted'])
        self.assertEqual(self.pre,original)
        self.assertEqual(out['historical_pre_native_snapshot'],{'sha256':'generic_snapshot'})

    def test_unresolved_start_never_becomes_known_zero_use(self):
        self.phases['development'].update(reserved_attempt=True,verified_worker_started=True,
            observed_execution={'new_reader_forward_pairs_completed':None})
        out=M.derive_final_roles(self.pre,self.phases,0,False,{})
        self.assertIsNone(out['development']['model_attempted'])
        self.assertTrue(out['development']['model_use_uncertainty'])

    def test_explicit_no_start_and_consumed_confirmation_are_distinct(self):
        self.phases['development'].update(reserved_attempt=True,
            completion={'native_process_started':False})
        self.phases['confirmation'].update(reserved_attempt=True,verified_worker_started=True,
            observed_execution={'new_reader_forward_pairs_attempted':1})
        out=M.derive_final_roles(self.pre,self.phases,24,True,{})
        self.assertFalse(out['development']['model_attempted'])
        self.assertTrue(out['confirmation']['model_attempted'])
        self.assertEqual(out['confirmation']['annotation_choices_projected'],24)
        self.assertTrue(out['confirmation']['conservatively_retired'])
        self.assertEqual(out['originaltrain_partition'],{'exposed':229,'unreserved':178,'reserved_unused':16})


if __name__=='__main__':unittest.main(verbosity=2)
