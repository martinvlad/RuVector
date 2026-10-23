"""Pure reporting fixtures, no benchmark labels/models or real study reads."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('generic_reporting',P/'build_final.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


def decision():
    return {'checks_passed':True,'accepted':True,'status':'GENERIC_ACCEPTED_FIXTURE',
            'next_priority':'GENERIC_NEXT_FIXTURE','plan_sha256':M.PLAN_SHA,
            **{k:True for k in ('independent_replays_passed','DEV_gate_passed','CONF_gate_passed',
                               'actual_confirmation_completed')}}


class Decision(unittest.TestCase):
    def test_only_explicit_independent_complete_confirmation_can_accept(self):
        self.assertTrue(M.decision_check(decision()))
        for key in ('independent_replays_passed','DEV_gate_passed','CONF_gate_passed','actual_confirmation_completed'):
            for absent in (False,None):
                d=decision();d[key]=absent
                with self.assertRaises(ValueError):M.decision_check(d)

    def test_wrong_plan_or_automatic_promotion_never_accepted(self):
        for key,value in (('plan_sha256','0'*64),('champion_promoted',True),
                          ('publisher_submission_allowed',True),('official_rank',1),('official_score',100)):
            d=decision();d[key]=value
            with self.assertRaises(ValueError):M.decision_check(d)

    def test_rejected_and_unmeasured_gate_fields_remain_unmeasured(self):
        d=decision();d.update(accepted=False,DEV_gate_passed=False,CONF_gate_passed=None,
                              actual_confirmation_completed=False)
        self.assertFalse(M.decision_check(d));self.assertIsNone(d['CONF_gate_passed'])


class Accounting(unittest.TestCase):
    def test_actual_only_cumulative_deltas_preserve_train_sanity_counts(self):
        actual={'native_process_attempts':1,'completed_native_corpora':1,
                'successful_HTTP_decisions':24,'failed_HTTP_requests':0}
        result=M.cumulative(actual,dict(M.BASE))
        self.assertEqual(result['native_corpus_attempts_including_failed_request'],19)
        self.assertEqual(result['native_corpus_batches_completed'],17)
        self.assertEqual(result['actual_HTTP_successful_decisions'],885)
        self.assertEqual(result['actual_HTTP_evaluation_diagnostic_decisions'],735)
        self.assertEqual(result['actual_HTTP_training_feature_requests'],144)
        self.assertEqual(result['actual_HTTP_training_sanity_diagnostic_requests'],6)
        old=dict(M.BASE);old['actual_HTTP_successful_decisions']-=1
        with self.assertRaises(ValueError):M.cumulative(actual,old)

    def test_missing_execution_stays_unknown_and_not_zero(self):
        self.assertIsNone(M.known_sum([None,0]));self.assertEqual(M.known_sum([3,1]),4)

    def test_latency_method_is_explicit_and_empty_is_null(self):
        self.assertIsNone(M.percentile([], .95));self.assertEqual(M.percentile([1,2,3,4],.5),2.5)
        self.assertAlmostEqual(M.percentile([1,2,3,4],.95),3.85)

    def phase(self,temp,completion):
        root=Path(temp);folder=root/M.PREFIX/'epoch18/runs/development';folder.mkdir(parents=True)
        (folder/'popen-attempt.json').write_text(json.dumps({'source_plan_sha256':M.PLAN_SHA}))
        (folder/'completion.json').write_text(json.dumps(completion));return root,folder

    def test_failed_popen_is_consumed_slot_without_model_start(self):
        with tempfile.TemporaryDirectory()as temp:
            root,_=self.phase(temp,{'native_process_started':False,'source_plan_sha256':M.PLAN_SHA})
            phase=M.phase_evidence(root,'development')
            self.assertTrue(phase['reserved_attempt']);self.assertFalse(phase['verified_worker_started'])
            self.assertEqual(phase['model_initializations'],0)
            self.assertFalse(phase['corpus_completed']);self.assertIsNone(phase['binary_metrics'])

    def test_started_process_without_receipts_keeps_unknown_model_counts(self):
        with tempfile.TemporaryDirectory()as temp:
            root,folder=self.phase(temp,{'native_process_started':True,'source_plan_sha256':M.PLAN_SHA})
            (folder/'started-requests.jsonl').write_text('{}\n{}\n')
            (folder/'wire.jsonl').write_text(json.dumps({'id':'GENERIC_ID','status':500,'elapsed_s':.3,
                'request':'OPAQUE_FIXTURE_NEVER_INSPECTED','response':'OPAQUE_FIXTURE_NEVER_INSPECTED'})+'\n')
            phase=M.phase_evidence(root,'development')
            self.assertTrue(phase['verified_worker_started']);self.assertIsNone(phase['model_initializations'])
            self.assertEqual(phase['failed_or_unanswered_HTTP_requests'],2)
            self.assertIsNone(phase['latency']['p50_seconds'])


if __name__=='__main__':unittest.main()
