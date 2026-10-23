"""Engineering-only acceptance/resource/retirement tests; no real inference."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('epoch16_loop_tests', Path(__file__).with_name('loop.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


class FrozenGateAndBudget(unittest.TestCase):
    def test_only_exact_reserved_pid_group_plan_phase_and_deadline_can_initialize(self):
        with tempfile.TemporaryDirectory() as temp:
            study=Path(temp);folder=study/'runs/development';folder.mkdir(parents=True)
            clock=time.time();deadline=clock+500;plan=self.plan();digest='1'*64
            attempt={'pid':1234,'pgid':1234,'phase':'development','study_id':plan['study_id'],
                'source_plan_sha256':digest,'model_deadline_unix':deadline,
                'new_study_native_attempt':1,'lifetime_native_attempt':18,
                'invocation_started_unix':clock-1,'hard_cleanup_deadline_unix':clock+505}
            reservation={'phase':'development','plan_sha256':digest}
            invoked={'phase':'development','source_plan_sha256':digest,'study_id':plan['study_id'],'new_study_native_attempt':1}
            for name,value in [('attempt.json',attempt),('reservation.json',reservation),('popen-attempt.json',invoked)]:
                (folder/name).write_text(json.dumps(value))
            with mock.patch.object(M,'STUDY',study),mock.patch.object(M.os,'getpid',return_value=1234),mock.patch.object(M.os,'getpgrp',return_value=1234):
                M.verify_worker_reservation(plan,digest,deadline,'development')
                for key,value in [('pid',4321),('pgid',4321),('phase','confirmation'),('source_plan_sha256','0'*64),('model_deadline_unix',deadline-1),('new_study_native_attempt',2),('lifetime_native_attempt',19),('hard_cleanup_deadline_unix',clock+700)]:
                    changed={**attempt,key:value};(folder/'attempt.json').write_text(json.dumps(changed))
                    with self.assertRaises(ValueError,msg=key):M.verify_worker_reservation(plan,digest,deadline,'development')
                (folder/'attempt.json').write_text(json.dumps(attempt));(folder/'popen-attempt.json').unlink()
                with self.assertRaises(FileNotFoundError):M.verify_worker_reservation(plan,digest,deadline,'development')

    def test_typed_wire_scoring_preserves_three_classes_and_raw_h_control(self):
        rows=[]
        for gold in M.SC.CLASSES:
            for i in range(8):
                probabilities={k:(.8 if k==gold else .1) for k in M.SC.CLASSES}
                answer={'typed_probabilities':probabilities,'typed_prediction':gold}
                response={'answers':{'decision':answer},'ablation_responses':{
                    k:{'answers':{'decision':copy.deepcopy(answer)}} for k in M.SC.TYPED_ARMS if k!='ruvector_top2'}}
                rows.append({'id':'ENGINEERING_ONLY_'+gold+str(i),'input':{'questions':{'decision':{}}},
                             'evaluation':{'original_threeway_label':gold},'response':response})
        metrics,confusions=M.SC.typed_scores(rows)
        self.assertEqual(set(metrics),set(M.SC.TYPED_ARMS))
        for value in metrics.values():
            self.assertEqual(value['correct'],24);self.assertAlmostEqual(value['brier'],.06)
            self.assertAlmostEqual(value['nll'],-math.log(.8))
            self.assertEqual(value['by_class']['Contradiction'],{'n':8,'correct':8})
        rows[0]['response']['answers']['decision']['typed_probabilities']['Entailment']=float('nan')
        with self.assertRaises(ValueError):M.SC.typed_scores(rows)

    def metrics(self):
        binary = {a: {'n': 24, 'correct': 12, 'strict_valid': 24, 'errors': 0,
                      'brier': .5, 'nll': .7} for a in M.ARMS}
        binary['ruvector_top2'].update(correct=16, brier=.3, nll=.4)
        typed = {a: {'n': 24, 'correct': 12, 'strict_valid': 24, 'errors': 0,
                     'brier': .8, 'nll': 1.1,
                     'by_class': {k: {'n': 8, 'correct': 4} for k in M.SC.CLASSES}}
                 for a in M.SC.TYPED_ARMS}
        typed['ruvector_top2'].update(correct=16, brier=.4, nll=.6)
        for k,v in zip(M.SC.CLASSES, (6,5,5)):
            typed['ruvector_top2']['by_class'][k]['correct'] = v
        return binary, typed

    def plan(self):
        return {'study_id': 'native-paired-whole-proposition-negation-e16',
                'limits': {'seconds_per_batch': 600}, 'lease_expires_unix': time.time()+3600,
                'runtime_admission': {'formula_id': '24xDEVmaxHTTPxunitratio+2xDEVinit+60-v1',
                                      'max_DEV_units': 10, 'max_confirmation_units': 10}}

    def test_complete_binary_and_typed_improvement_passes(self):
        self.assertTrue(M.development_gate(*self.metrics())[0])

    def test_one_extra_correct_is_insufficient_against_any_binary_control(self):
        for name in M.ARMS[1:]:
            b,t = self.metrics(); b[name]['correct'] = 15
            self.assertFalse(M.development_gate(b,t)[0], name)

    def test_raw_h_confidence_only_improvement_cannot_pass(self):
        b,t = self.metrics(); b['same_nli_native_raw_h']['correct'] = 16
        self.assertFalse(M.development_gate(b,t)[0])

    def test_both_binary_proper_scores_must_be_nonworse_every_control(self):
        for name in M.ARMS[1:]:
            for key in ('brier','nll'):
                b,t = self.metrics(); b[name][key] = b['ruvector_top2'][key]-.01
                self.assertFalse(M.development_gate(b,t)[0], (name,key))

    def test_binary_success_cannot_hide_typed_failure(self):
        for name in M.SC.TYPED_ARMS[1:]:
            b,t = self.metrics(); t[name]['correct'] = 15
            for k,v in zip(M.SC.CLASSES,(5,5,5)):t[name]['by_class'][k]['correct']=v
            self.assertFalse(M.development_gate(b,t)[0], name)

    def test_typed_proper_scores_must_be_nonworse(self):
        for name in M.SC.TYPED_ARMS[1:]:
            for key in ('brier','nll'):
                b,t = self.metrics();t[name][key] = t['ruvector_top2'][key]-.01
                self.assertFalse(M.development_gate(b,t)[0])

    def test_zero_contradiction_competence_is_rejected(self):
        b,t = self.metrics();c=t['ruvector_top2']['by_class']
        c['Entailment']['correct']=8;c['Contradiction']['correct']=0;c['NotMentioned']['correct']=8
        self.assertFalse(M.development_gate(b,t)[0])

    def test_absent_class_is_inconclusive_and_no_redraw(self):
        b,t = self.metrics()
        for name,x in t.items():
            n=8 if name=='ruvector_top2' else 6
            x['by_class']={'Entailment':{'n':12,'correct':n},'Contradiction':{'n':0,'correct':0},'NotMentioned':{'n':12,'correct':n}}
        passed,proof=M.development_gate(b,t)
        self.assertFalse(passed);self.assertFalse(proof['class_guards']['all_three_gold_classes_present'])

    def test_nonfinite_or_incomplete_measurements_fail(self):
        for value in (float('nan'),float('inf')):
            b,t=self.metrics();b['ruvector_top2']['nll']=value
            self.assertFalse(M.development_gate(b,t)[0])
        b,t=self.metrics();t.pop('same_nli_native_raw_h')
        self.assertFalse(M.development_gate(b,t)[0])

    def test_confirmation_cost_uses_24_and_source_ratio(self):
        p=self.plan();p['runtime_admission']['max_confirmation_units']=20
        r=M.confirmation_runtime_admission(p,[{'elapsed_s':2.}]*24,3.)
        self.assertEqual(r['projected_confirmation_seconds'],162.)
        self.assertTrue(r['allowed'])

    def test_cost_boundary_and_lease_margin_are_enforced(self):
        p=self.plan();p['lease_expires_unix']=630.
        r=M.confirmation_runtime_admission(p,[{'elapsed_s':22.25}]*24,3.,at_unix=0.)
        self.assertTrue(r['allowed']);self.assertEqual(r['projected_confirmation_seconds'],600.)
        self.assertFalse(M.confirmation_runtime_admission(p,[{'elapsed_s':22.25001}]*24,3.,at_unix=0.)['allowed'])
        p['lease_expires_unix']=629.
        self.assertFalse(M.confirmation_runtime_admission(p,[{'elapsed_s':22.25}]*24,3.,at_unix=0.)['allowed'])

    def test_invalid_timing_or_partial_dev_never_admits_confirmation(self):
        for rows in ([{'elapsed_s':2.}]*23,[{'elapsed_s':0.}]*24,[{'elapsed_s':float('nan')}]*24):
            with self.assertRaises(ValueError):M.confirmation_runtime_admission(self.plan(),rows,3.)

    def test_dev_rejection_never_starts_or_projects_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            study=Path(temp);path=study/'plan.json';path.write_text('{}');b,t=self.metrics();b['ruvector_top2']['correct']=12
            def phase(*args):
                folder=study/'runs/development';folder.mkdir(parents=True)
                (folder/'popen-attempt.json').write_text('{}');(folder/'attempt.json').write_text('{}')
                return {'metrics':b,'typed_metrics':t,'records':[{'elapsed_s':2.}]*24,'initialization_seconds':3.}
            with mock.patch.object(M,'STUDY',study),mock.patch.object(M,'require_plan',return_value=self.plan()),mock.patch.object(M,'run_phase',side_effect=phase) as run:
                M.parent(path)
                with self.assertRaises(FileExistsError):M.parent(path)
            d=json.loads((study/'study-completion.json').read_text())
            self.assertEqual(run.call_count,1);self.assertEqual(d['actual_native_attempts'],1)
            self.assertEqual(d['lifetime_native_attempts'],18);self.assertFalse(d['confirmation_consumed_or_attempted'])
            self.assertEqual(d['allowed_further_attempts_in_closed_study'],0)

    def test_failed_popen_consumes_one_attempt_without_claiming_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            study=Path(temp);path=study/'plan.json';path.write_text('{}')
            with mock.patch.object(M,'STUDY',study),mock.patch.object(M,'require_plan',return_value=self.plan()),mock.patch.object(M.subprocess,'Popen',side_effect=OSError('ENGINEERING_INJECTED')) as popen:
                with self.assertRaises(RuntimeError):M.parent(path)
            d=json.loads((study/'study-completion.json').read_text())
            self.assertEqual(popen.call_count,1);self.assertEqual(d['actual_native_attempts'],1)
            self.assertEqual(d['native_processes_started'],0);self.assertTrue(d['development_conservatively_exposed_DEV'])
            self.assertFalse(d['confirmation_consumed_or_attempted'])

    def test_pid_receipt_failure_cleans_owned_group_and_closes_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            study=Path(temp);path=study/'plan.json';path.write_text('{}');real=M.T.save
            process=mock.Mock(pid=987654321,returncode=0)
            def save(path,value):
                if Path(path).name=='attempt.json':raise OSError('ENGINEERING_PID_RECEIPT_FAILURE')
                return real(path,value)
            cleanup={'live_members_after':[],'finished_within_deadline':True}
            with mock.patch.object(M,'STUDY',study),mock.patch.object(M,'require_plan',return_value=self.plan()),mock.patch.object(M.T,'save',side_effect=save),mock.patch.object(M.subprocess,'Popen',return_value=process),mock.patch.object(M,'close_owned_group',return_value=cleanup) as closed:
                with self.assertRaises(RuntimeError):M.parent(path)
            d=json.loads((study/'study-completion.json').read_text())
            self.assertEqual(closed.call_count,1);self.assertEqual(d['actual_native_attempts'],1)
            self.assertEqual(d['native_processes_started'],1);self.assertEqual(d['allowed_further_attempts_in_closed_study'],0)


if __name__=='__main__':unittest.main()
