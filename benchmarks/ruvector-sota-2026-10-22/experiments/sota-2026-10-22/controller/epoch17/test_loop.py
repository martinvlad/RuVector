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

spec = importlib.util.spec_from_file_location('epoch17_loop_tests', Path(__file__).with_name('loop.py'))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


class FrozenGateAndBudget(unittest.TestCase):
    def test_only_exact_reserved_pid_group_plan_phase_and_deadline_can_initialize(self):
        with tempfile.TemporaryDirectory() as temp:
            study=Path(temp);folder=study/'runs/development';folder.mkdir(parents=True)
            clock=time.time();deadline=clock+500;plan=self.plan();digest='1'*64
            attempt={'pid':1234,'pgid':1234,'phase':'development','study_id':plan['study_id'],
                'source_plan_sha256':digest,'model_deadline_unix':deadline,
                'new_study_native_attempt':1,'lifetime_native_attempt':19,
                'invocation_started_unix':clock-1,'hard_cleanup_deadline_unix':clock+505,'automatic_retry':False}
            reservation={'phase':'development','plan_sha256':digest,'automatic_retry':False}
            invoked={'phase':'development','source_plan_sha256':digest,'study_id':plan['study_id'],
                     'new_study_native_attempt':1,'lifetime_native_attempt':19,'automatic_retry':False}
            for name,value in [('attempt.json',attempt),('reservation.json',reservation),('popen-attempt.json',invoked)]:
                (folder/name).write_text(json.dumps(value))
            with mock.patch.object(M,'STUDY',study),mock.patch.object(M.os,'getpid',return_value=1234),mock.patch.object(M.os,'getpgrp',return_value=1234):
                M.verify_worker_reservation(plan,digest,deadline,'development')
                for key,value in [('pid',4321),('pgid',4321),('phase','confirmation'),('source_plan_sha256','0'*64),('model_deadline_unix',deadline-1),('new_study_native_attempt',2),('lifetime_native_attempt',20),('hard_cleanup_deadline_unix',clock+700)]:
                    changed={**attempt,key:value};(folder/'attempt.json').write_text(json.dumps(changed))
                    with self.assertRaises(ValueError,msg=key):M.verify_worker_reservation(plan,digest,deadline,'development')
                (folder/'attempt.json').write_text(json.dumps(attempt));(folder/'popen-attempt.json').unlink()
                with self.assertRaises(FileNotFoundError):M.verify_worker_reservation(plan,digest,deadline,'development')

    def test_typed_wire_scoring_preserves_three_classes_and_previous_reader_control(self):
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
            self.assertEqual(value['strict_valid_count'],24)
            self.assertEqual(value['gold_counts'],value['prediction_counts'])
            self.assertEqual(value['confusion']['Contradiction']['Contradiction'],8)
        rows[0]['response']['answers']['decision']['typed_probabilities']['Entailment']=float('nan')
        with self.assertRaises(ValueError):M.SC.typed_scores(rows)

    def binary_record(self, probabilities=None):
        return {'id':'ENGINEERING_ONLY_BINARY','input':{'questions':{'decision':{}}},
                'evaluation':{'type':'choice','gold':'Yes','labels':['Yes','No']},
                'response':{'answers':{'decision':{'type':'choice','choice':'Yes',
                    'probabilities':probabilities or {'Yes':.80000004,'No':.2}}}}}

    def test_pinned_scorer_float32_mass_is_literal_strict_and_never_normalized(self):
        evaluator=M.importlib.import_module('benchmark.evaluate')
        row=self.binary_record();original=copy.deepcopy(row)
        scored=M.SC.validate_literal_binary(row,evaluator)
        self.assertTrue(scored['strict_valid']);self.assertFalse(scored['renormalized'])
        self.assertEqual(scored['probs'],original['response']['answers']['decision']['probabilities'])
        self.assertEqual(row,original)
        self.assertGreater(abs(sum(scored['probs'].values())-1),1e-10)

    def test_binary_sum_tolerance_boundary_and_renormalization_rejection(self):
        evaluator=M.importlib.import_module('benchmark.evaluate')
        M.SC.validate_literal_binary(self.binary_record({'Yes':.5,'No':.5009999999}),evaluator)
        for probs in ({'Yes':.5,'No':.501000001},{'Yes':.5,'No':.51},
                      {'Yes':True,'No':0.},{'Yes':float('nan'),'No':.2},
                      {'Yes':.8,'No':.2,'Extra':0.},{'Yes':1.1,'No':-.1}):
            with self.assertRaises(ValueError):
                M.SC.validate_literal_binary(self.binary_record(probs),evaluator)

    def test_binary_guard_checks_actual_strict_flags_and_probability_identity(self):
        evaluator=M.importlib.import_module('benchmark.evaluate');row=self.binary_record()
        actual=evaluator.score_record(row)
        for update in ({'strict_valid':False},{'renormalized':True},
                       {'probs':{'Yes':.8,'No':.2}}):
            with mock.patch.object(evaluator,'score_record',return_value={**actual,**update}):
                with self.assertRaises(ValueError):M.SC.validate_literal_binary(row,evaluator)

    def test_confirmation_requires_exact_durable_quality_and_runtime_admission(self):
        with tempfile.TemporaryDirectory() as temp:
            study=Path(temp);dev=study/'runs/development';dev.mkdir(parents=True)
            comparison=dev/'development-comparison.json';runtime=study/'runtime-admission.json'
            digest='1'*64
            def write_lock():
                (study/'confirmation-selection-lock.json').write_text(json.dumps({
                    'plan_sha256':digest,'development_comparison_sha256':M.T.digest(comparison),
                    'runtime_admission_sha256':M.T.digest(runtime)}))
            with mock.patch.object(M,'STUDY',study):
                for gate,allowed in ((True,True),(False,True),(True,False),(1,True)):
                    comparison.write_text(json.dumps({'frozen_development_gate_passed':gate}))
                    runtime.write_text(json.dumps({'allowed':allowed}));write_lock()
                    if gate is True and allowed is True:M.verify_confirmation_admission(digest)
                    else:
                        with self.assertRaises(ValueError):M.verify_confirmation_admission(digest)
                comparison.write_text(json.dumps({'frozen_development_gate_passed':True}));write_lock()
                comparison.write_text(json.dumps({'frozen_development_gate_passed':False}))
                with self.assertRaises(ValueError):M.verify_confirmation_admission(digest)

    def test_unreserved_worker_cannot_import_model_or_server(self):
        with mock.patch.object(M,'require_plan',return_value=self.plan()), \
             mock.patch.object(M,'verify_worker_reservation',side_effect=ValueError('ENGINEERING_REJECT')), \
             mock.patch.object(M.importlib,'import_module') as imported:
            with self.assertRaises(ValueError):M.worker(Path('ENGINEERING_NO_PLAN'),'1'*64,time.time()+500,'development')
            imported.assert_not_called()

    def test_only_fixed_phase_attempt_pairs_are_accepted_before_mutation(self):
        for phase,number in (('development',2),('confirmation',1),('other',1)):
            with self.assertRaises(ValueError):M.run_phase(Path('ENGINEERING_NO_PLAN'),'1'*64,self.plan(),phase,number)

    def test_actual_new_original_checkpoint_and_previous_reader_receipts_required(self):
        plan={'expected_new_reader_receipt':copy.deepcopy(M.NEW_READER_REQUIRED),
              'expected_previous_reader_receipt':copy.deepcopy(M.PREVIOUS_READER_REQUIRED),
              'expected_nli_revision':M.PREVIOUS_READER_REQUIRED['revision'],
              'expected_nli_sha256':M.PREVIOUS_READER_REQUIRED['model_sha256']}
        old=copy.deepcopy(M.PREVIOUS_READER_REQUIRED)
        receipt={'new_reader':copy.deepcopy(M.NEW_READER_REQUIRED),'previous_reader':old,'nli':copy.deepcopy(old)}
        receipt['new_reader'].update(quantized_linear_count=1,quantized_linear_modules=[{
                                     'name':'ENGINEERING_Q1','weight_dtype':'torch.qint8',
                                     'shape':[2,2],'qscheme':'torch.per_tensor_affine'}],
                                     quantized_weight_state_sha256='1'*64)
        M.verify_reader_receipts(plan,receipt)
        for arm,key in (('new_reader','original_checkpoint_sha256'),('new_reader','revision'),
                        ('new_reader','quantization_recipe'),('previous_reader','model_sha256')):
            changed=copy.deepcopy(receipt);changed[arm][key]='ENGINEERING_WRONG'
            with self.assertRaises(ValueError):M.verify_reader_receipts(plan,changed)
        changed=copy.deepcopy(receipt);changed['nli']['model_sha256']='ENGINEERING_WRONG'
        with self.assertRaises(ValueError):M.verify_reader_receipts(plan,changed)
        for key,value in (('quantized_linear_count',0),('quantized_linear_modules',[]),
                          ('quantized_weight_state_sha256','ENGINEERING_NOT_A_HASH')):
            changed=copy.deepcopy(receipt);changed['new_reader'][key]=value
            with self.assertRaises(ValueError):M.verify_reader_receipts(plan,changed)

    def test_exact_actual_four_forward_counters_required_before_scoring(self):
        counters={key:factor*24 for key,factor in (
            ('nli_forward_pairs_attempted',4),('nli_forward_pairs_completed',4),
            ('new_reader_forward_pairs_attempted',3),('new_reader_forward_pairs_completed',3),
            ('previous_reader_forward_pairs_attempted',1),('previous_reader_forward_pairs_completed',1))}
        engine=mock.Mock();engine.execution_snapshot.return_value={'counters':counters}
        M.verify_complete_execution(engine,24)
        with self.assertRaises(ValueError):M.verify_complete_execution(engine,23)
        for key in counters:
            for value in (counters[key]-1,counters[key]+1,float(counters[key])):
                engine.execution_snapshot.return_value={'counters':{**counters,key:value}}
                with self.assertRaises(ValueError):M.verify_complete_execution(engine,24)

    def frozen_plan(self):
        plan=self.plan()
        plan.update(controller_version=M.CONTROLLER_VERSION,epoch=17,revision=M.STUDY_REVISION,
                    binary_probability_policy=copy.deepcopy(M.SC.BINARY_PROBABILITY_POLICY),
                    expected_new_reader_receipt=copy.deepcopy(M.NEW_READER_REQUIRED),
                    expected_previous_reader_receipt=copy.deepcopy(M.PREVIOUS_READER_REQUIRED),
                    expected_nli_revision=M.PREVIOUS_READER_REQUIRED['revision'],
                    expected_nli_sha256=M.PREVIOUS_READER_REQUIRED['model_sha256'],
                    prior_closed_study_native_attempts=18,prior_closed_original_study_attempts=6,
                    prior_closed_epoch5_study_attempts=1,prior_closed_epoch6_study_attempts=1,
                    prior_closed_epoch7_study_attempts=1,prior_closed_epoch8_study_attempts=2,
                    prior_closed_epoch9_study_attempts=1,prior_closed_epoch10_study_attempts=1,
                    prior_closed_epoch11_study_attempts=1,prior_closed_epoch12_study_attempts=1,
                    prior_closed_epoch13_study_attempts=1,prior_closed_epoch14_native_attempts=0,
                    prior_closed_epoch15_study_attempts=1,prior_closed_epoch16_study_attempts=1,
                    new_study_native_attempt_cap=2,new_study_native_attempts_before=0,
                    train='none',calibration='none',
                    datasets={'development':'experiments/sota-2026-10-22/legal-transfer/epoch17/development24.jsonl','confirmation':'experiments/sota-2026-10-22/legal-transfer/epoch17/confirmation24.jsonl'},
                    lazy_confirmation={'builder_path':'experiments/sota-2026-10-22/legal-transfer/epoch17/build.py',
                        'source_path':'experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json',
                        'source_freeze_sha256':'1'*64},
                    pins=[{'path':p} for p in ('experiments/sota-2026-10-22/benchmark/evaluate.py',
                        'experiments/sota-2026-10-22/benchmark/sources/jevbench_scoring.py',
                        'experiments/sota-2026-10-22/benchmark/source-manifest.json',
                        'experiments/swarm/jevbench-adapter/sources/jevbench_scoring.py')])
        plan['limits'].update(native_batches=2,threads=2,candidate_configs=1,paid_calls=0,GPU_calls=0)
        return plan

    def test_plan_rejects_wrong_prior_ledger_readers_or_numeric_policy_before_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'ENGINEERING_ONLY_plan.json';plan=self.frozen_plan()
            path.write_text(json.dumps(plan))
            with mock.patch.object(M.T,'verify_plan'):
                M.require_plan(path)
                for key,value in (('prior_closed_study_native_attempts',17),
                                  ('prior_closed_epoch16_study_attempts',0),
                                  ('controller_version','ENGINEERING_WRONG'),
                                  ('epoch',16),('revision','ENGINEERING_WRONG'),
                                  ('binary_probability_policy',{**M.SC.BINARY_PROBABILITY_POLICY,'SUM_TOL':1e-10}),
                                  ('expected_new_reader_receipt',{**M.NEW_READER_REQUIRED,'original_checkpoint_sha256':'0'*64})):
                    path.write_text(json.dumps({**plan,key:value}))
                    with self.assertRaises(ValueError,msg=key):M.require_plan(path)

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
        return {'study_id': 'native-microsoft-xlarge-typed-reader-e17',
                'limits': {'seconds_per_batch': 600}, 'lease_expires_unix': time.time()+3600,
                'runtime_admission': {'formula_id': '24xDEVmaxHTTPxunitratio+2xDEVinit+60-v1',
                                      'max_DEV_units': 10, 'max_confirmation_units': 10}}

    def test_complete_binary_and_typed_improvement_passes(self):
        self.assertTrue(M.development_gate(*self.metrics())[0])

    def test_one_extra_correct_is_insufficient_against_any_binary_control(self):
        for name in M.ARMS[1:]:
            b,t = self.metrics(); b[name]['correct'] = 15
            self.assertFalse(M.development_gate(b,t)[0], name)

    def test_previous_reader_confidence_only_improvement_cannot_pass(self):
        b,t = self.metrics(); b['previous_reader_native_same_premise']['correct'] = 16
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
        b,t=self.metrics();t.pop('previous_reader_native_same_premise')
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
        for rows in ([{'elapsed_s':2.}]*23,[{'elapsed_s':0.}]*24,[{'elapsed_s':float('nan')}]*24,[{'elapsed_s':True}]*24):
            with self.assertRaises(ValueError):M.confirmation_runtime_admission(self.plan(),rows,3.)
        with self.assertRaises(ValueError):M.confirmation_runtime_admission(self.plan(),[{'elapsed_s':2.}]*24,True)

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
            self.assertEqual(d['lifetime_native_attempts'],19);self.assertFalse(d['confirmation_consumed_or_attempted'])
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
