"""Source-only fixtures. No process/model/native start and no live /proc read."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import observe_supervisor_closure as O


class ClosureFixtures(unittest.TestCase):
    def setUp(self):
        launch_guard = patch.object(O, 'PRE_POPEN_LAUNCH_SHA', '0' * 64)
        launch_guard.start(); self.addCleanup(launch_guard.stop)
        self.sup = {'pid': 200, 'startticks': 1000, 'pgid': 200, 'sid': 200}
        self.worker = {'pid': 201, 'ticks': 1001, 'pgid': 201, 'sid': 201, 'ppid': 200, 'state': 'S'}
        self.refs = {key: {'path': path, 'bytes': 1, 'sha256': '1' * 64} for key, path in O.PATHS.items()}
        self.execution = {'uncertain_start': False, 'verified_worker_starts': 1,
            'status': 'WORKER_COMPLETED', 'corpus_reservations': {'engineering': None}, 'corpus_reservation_count': 0,
            'worker_popen_attempted': True, 'worker_popen_attempts': 1,
            'worker_start_boundary': 'WORKER_POPEN_ATTEMPTED', 'worker_identity': self.worker,
            'recovered_preexec_child_identity': None, 'owned_live_processes_closed': True,
            'owned_live_group_members': [], 'owned_process_closure_observation': 'OBSERVED'}
        self.docs = {'execution': self.execution, 'dispatch_attempt': {'verified_launcher_start': True}}
        self.snap = {'scan_error': False, 'rows': [], 'processes': {
            200: {'absent': True, 'row': None, 'closed': True},
            201: {'absent': True, 'row': None, 'closed': True}}}
        # Any accidental invocation of the production observer fails this suite.
        self.guard = patch.object(O, 'snapshot', side_effect=AssertionError('Live observation forbidden in preflight'))
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def reduce(self, approved=True, identities=None):
        return O.evaluate('2' * 64, self.refs, self.docs, self.sup,
                          [self.worker] if identities is None else identities, self.snap, approved)

    def test_known_absent_is_closed_exact_wire(self):
        result = self.reduce()
        self.assertTrue(result['physical_closure_passed'])
        self.assertTrue(result['physical_supervisor_absent'])
        self.assertEqual(set(result), O.KEYS)
        self.assertEqual(len(result), 18)
        self.assertNotIn('exit_code', result)

    def test_terminal_z_closed_not_absent(self):
        row = {'pid': 200, 'ticks': 1000, 'pgid': 200, 'sid': 200, 'ppid': 1, 'state': 'Z'}
        self.assertTrue(O.terminal_closed('Z', [0] * 7, 0))
        self.assertTrue(O.terminal_closed('X', [0] * 7, 0))
        self.assertFalse(O.terminal_closed('Z', [0, 1, 0], 0))
        self.assertFalse(O.terminal_closed('Z', [0] * 7, 1))
        self.assertFalse(O.terminal_closed('S', [0] * 7, 0))
        self.snap['processes'][200] = {'absent': False, 'row': row, 'closed': True}
        self.snap['rows'] = [row]
        result = self.reduce()
        self.assertTrue(result['physical_closure_passed'])
        self.assertFalse(result['physical_supervisor_absent'])
        self.assertEqual(result['observed_supervisor_state'], 'Z')
        self.snap['processes'][200]['closed'] = False
        self.assertFalse(self.reduce()['physical_closure_passed'])

    def test_missing_execution_never_infers_zero_start(self):
        self.docs['execution'] = None
        self.refs['execution'] = None
        result = self.reduce(identities=[])
        self.assertTrue(result['unknown_physical_ownership'])
        self.assertIsNone(result['owned_worker_group_members'])
        self.assertFalse(result['physical_closure_passed'])
        self.assertIsNotNone(result['dispatch_reservation'])

    def test_unknown_or_reused_identity_blocks(self):
        self.snap['processes'][201] = {'absent': None, 'row': None, 'closed': None}
        self.assertTrue(self.reduce()['unknown_physical_ownership'])
        self.snap['processes'][201] = {'absent': False, 'row': dict(self.worker, ticks=9999), 'closed': False}
        self.assertFalse(self.reduce()['physical_closure_passed'])
        self.snap['processes'][200] = {'absent': False, 'row': dict(self.worker, pid=200, ticks=9999), 'closed': False}
        result = self.reduce()
        self.assertIsNone(result['physical_supervisor_absent'])
        self.assertIsNone(result['physical_supervisor_closed'])

    def test_live_group_or_session_member_blocks(self):
        # SID membership alone is included, even with a distinct PGID.
        self.snap['rows'] = [dict(self.worker, pid=202, pgid=202)]
        result = self.reduce()
        self.assertFalse(result['physical_closure_passed'])
        self.assertEqual(len(result['owned_worker_group_members']), 1)
        self.snap['scan_error'] = True
        self.assertIsNone(self.reduce()['owned_worker_group_members'])

    def test_before_popen_requires_explicit_frozen_provenance(self):
        self.execution.update(uncertain_start=False, verified_worker_starts=0,
            status='WORKER_FAILED_OR_TIMEOUT',
            worker_popen_attempted=False, worker_popen_attempts=0,
            worker_start_boundary='KNOWN_FAILURE_BEFORE_WORKER_POPEN', worker_identity=None,
            launcher_error={'type': 'ValueError', 'message': 'captured setup failure'})
        self.assertTrue(self.reduce(identities=[])['physical_closure_passed'])
        self.assertFalse(self.reduce(approved=False, identities=[])['physical_closure_passed'])
        del self.execution['worker_popen_attempted']
        self.assertFalse(self.reduce(identities=[])['physical_closure_passed'])

    def test_recovered_closed_preserves_uncertain_failed_nonqualification(self):
        self.execution.update(uncertain_start=True, verified_worker_starts=0, exit_code=None,
            status='WORKER_FAILED_OR_TIMEOUT', worker_identity_source='durable_preexec_only',
            recovered_preexec_child_identity=self.worker,
            worker_cpu_guard_preexec={'status': 'CPU_GUARD_FAILED_BEFORE_EXEC', 'process_identity': self.worker},
            worker_cpu_guard_preexec_artifact={'path': O.STUDY + 'runs/engineering/worker-cpu-preexec.json',
                'bytes': 1, 'sha256': '3' * 64}, raw_operation_counters_source='UNKNOWN', operation_counts_complete=False)
        before = copy.deepcopy(self.execution)
        result = self.reduce()
        self.assertTrue(result['physical_closure_passed'])
        self.assertFalse(result['unknown_physical_ownership'])
        self.assertEqual(self.execution, before)
        qualifies = (self.execution['status'] == 'WORKER_COMPLETED'
                     and self.execution['verified_worker_starts'] == 1
                     and self.execution['uncertain_start'] is False
                     and self.execution['operation_counts_complete'] is True)
        self.assertFalse(qualifies)
        self.execution['worker_cpu_guard_preexec']['process_identity'] = dict(self.worker, ticks=9)
        self.assertFalse(self.reduce()['physical_closure_passed'])

    def test_unreturned_popen_without_identity_remains_unknown(self):
        self.execution.update(uncertain_start=True, verified_worker_starts=0, worker_identity=None,
            owned_live_processes_closed=None, owned_live_group_members=None,
            owned_process_closure_observation='UNKNOWN_UNRETURNED_POPEN_WITHOUT_IDENTITY_PROOF')
        self.assertTrue(self.reduce(identities=[])['unknown_physical_ownership'])

    def test_duplicate_json_and_symlink_and_ref_tampering_rejected(self):
        with self.assertRaises(ValueError):
            O.parse(b'{"epoch":31,"epoch":30}')
        with self.assertRaises(ValueError):
            O.parse(b'{"value":1e999}')
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / 'data.json').write_bytes(b'{}')
            row = O.file_ref(root, 'data.json')
            self.assertEqual(row['sha256'], hashlib.sha256(b'{}').hexdigest())
            O.reference(root, row)
            (root / 'link.json').symlink_to(root / 'data.json')
            with self.assertRaises(OSError):
                O.file_ref(root, 'link.json')
            with self.assertRaises(ValueError):
                O.file_ref(root, '../data.json')
            (root / 'data.json').write_bytes(b'{"tamper":true}')
            with self.assertRaises(ValueError):
                O.reference(root, row)

    def test_dispatch_execution_completion_exact_chain(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            expected = {'schema_version': 1, 'epoch': 35, 'kind': O.KIND, 'phase': 'engineering',
                'plan_sha256': 'a' * 64, 'source_freeze_sha256': 'b' * 64,
                'pretrained_model_source_sha256': 'c' * 64, 'model_assets_lock_sha256': 'e' * 64, 'admission_sha256': 'd' * 64,
                'kernel_boot_id': O.BOOT, 'pid_namespace_inode': O.PIDNS,
                'logical_native_budget_reserved': 1, 'allowed_further_dispatches': 0}
            def put(key, value):
                path = root / O.PATHS[key]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
                return O.file_ref(root, O.PATHS[key])
            claim = dict(expected, dispatch_monotonic_seconds=1.5, dispatch_unix_seconds=2.5)
            claim_ref = put('dispatch_reservation', claim)
            attempt_ref = put('dispatch_attempt', dict(claim, **self.sup,
                verified_launcher_start=True, uncertain_launcher_start=False))
            execution = dict(self.execution, **{k: expected[k] for k in
                ('schema_version', 'epoch', 'kind', 'phase', 'plan_sha256', 'kernel_boot_id', 'pid_namespace_inode')},
                supervisor_identity=self.sup, dispatch_reservation=claim_ref, dispatch_attempt=attempt_ref,
                logical_native_budget_reserved=1, source_plan_unchanged=True, status='WORKER_COMPLETED')
            execution_ref = put('execution', execution)
            completion = {k: expected[k] for k in ('schema_version', 'epoch', 'kind', 'phase', 'kernel_boot_id', 'pid_namespace_inode')}
            completion.update(status='SUPERVISOR_ABOUT_TO_EXIT', supervisor_identity=self.sup,
                execution_sha256=execution_ref['sha256'], execution_status='WORKER_COMPLETED',
                intended_exit_code=0, exit_code_observed_by_root=False,
                requires_external_physical_supervisor_closure=True)
            put('supervisor_completion', completion)
            refs, docs, identity, identities, extras, approved = O.load_evidence(root, expected, {})
            self.assertEqual(docs['execution'], execution)
            self.assertEqual(identity, self.sup)
            self.assertEqual(identities, [self.worker])
            self.assertEqual(refs['execution'], execution_ref)
            completion['execution_sha256'] = 'f' * 64
            put('supervisor_completion', completion)
            with self.assertRaises(ValueError):
                O.load_evidence(root, expected, {})
            completion['execution_sha256'] = execution_ref['sha256']
            put('supervisor_completion', completion)
            # Actual launcher reserves an empty CPU file before setup/Popen.
            cpu_path = root / (O.STUDY + 'runs/engineering/worker-cpu-preexec.json')
            cpu_path.write_bytes(b'')
            failed = dict(execution, status='WORKER_FAILED_OR_TIMEOUT', worker_popen_attempted=False,
                worker_popen_attempts=0, worker_start_boundary='KNOWN_FAILURE_BEFORE_WORKER_POPEN',
                worker_identity=None, verified_worker_starts=0,
                launcher_error={'type': 'RuntimeError', 'message': 'captured pre-Popen setup failure'},
                worker_cpu_guard_preexec_artifact=O.file_ref(root, str(cpu_path.relative_to(root))),
                worker_cpu_guard_preexec=None, raw_operation_counters_source='UNKNOWN', operation_counts_complete=False)
            failed_ref = put('execution', failed)
            completion.update(execution_sha256=failed_ref['sha256'], execution_status=failed['status'], intended_exit_code=2)
            put('supervisor_completion', completion)
            approved_pins = {O.LAUNCH: {'sha256': O.PRE_POPEN_LAUNCH_SHA}}
            refs2, docs2, sup2, ids2, extras2, approved2 = O.load_evidence(root, expected, approved_pins)
            result = O.evaluate('a' * 64, refs2, docs2, sup2, ids2, self.snap, approved2)
            self.assertTrue(result['physical_closure_passed'])
            self.assertEqual(docs2['execution'], failed)
            self.assertEqual(extras2[0]['bytes'], 0)
            self.assertEqual(ids2, [])
            self.assertEqual(failed['raw_operation_counters_source'], 'UNKNOWN')
            self.assertFalse(failed['operation_counts_complete'])
            self.assertNotEqual(failed['status'], 'WORKER_COMPLETED')
            with self.assertRaises(ValueError):
                O.load_evidence(root, expected, {})
            failed['worker_popen_attempted'] = True
            put('execution', failed)
            with self.assertRaises(ValueError):
                O.load_evidence(root, expected, approved_pins)

    def test_output_is_exclusive_outside_and_fsynced(self):
        with tempfile.TemporaryDirectory() as name:
            parent = Path(name)
            root = parent / 'project'
            root.mkdir()
            outside = parent / 'SUPERVISOR_OBSERVED_CLOSURE.json'
            receipt = O.write_outside(root, outside, self.reduce())
            self.assertEqual(receipt['bytes'], outside.stat().st_size)
            with self.assertRaises(FileExistsError):
                O.write_outside(root, outside, self.reduce())
            with self.assertRaises(ValueError):
                O.write_outside(root, root / outside.name, self.reduce())

    def test_source_has_only_stdlib_and_no_process_or_model_imports(self):
        tree = ast.parse(Path(O.__file__).read_text())
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module.split('.')[0])
        self.assertEqual(modules, {'argparse', 'errno', 'hashlib', 'json', 'math', 'os', 'pathlib', 're', 'stat'})
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, {'kill', 'killpg', 'fork', 'execv', 'execve', 'posix_spawn', 'system', 'popen'})

    def test_prospective_terminal_capacity_exact_predicate_and_races(self):
        row = {'pid': 200, 'ticks': 1000, 'pgid': 200, 'sid': 200, 'ppid': 1, 'state': 'Z'}
        status = 'State:\tZ (zombie)\nPid:\t200\nTgid:\t200\nFDSize:\t0\nThreads:\t1\n'
        args = dict(expected=row, before=row, after=row, memory=[0]*7, status=status, fd_errno=13,
            boot_before=O.BOOT, boot_after=O.BOOT, namespace_before=O.PIDNS, namespace_after=O.PIDNS)
        self.assertTrue(O.terminal_capacity(**args))
        for changes in ({'fd_errno': 1}, {'fd_errno': None}, {'after': dict(row, ticks=99)},
                {'expected': dict(row, ticks=99)}, {'memory': [0]*6}, {'memory': [0,0,1,0,0,0,0]},
                {'boot_after': 'changed'}, {'namespace_after': O.PIDNS+1},
                {'status': status.replace('Threads:\t1', 'Threads:\t2')},
                {'status': status.replace('FDSize:\t0', 'FDSize:\t1')},
                {'status': status.replace('FDSize:\t0\n', '')},
                {'status': status+'Threads:\t1\n'}):
            self.assertFalse(O.terminal_capacity(**dict(args, **changes)))
        x = dict(row, state='X')
        self.assertTrue(O.terminal_capacity(**dict(args,before=x,after=x,status=status.replace('Z (zombie)','X (dead)'))))

    def test_mocked_terminal_EACCES_status_and_unknown_without_live_proc(self):
        from types import SimpleNamespace
        row = {'pid': 200, 'ticks': 1000, 'pgid': 200, 'sid': 200, 'ppid': 1, 'state': 'Z'}
        status = 'State:\tZ (zombie)\nPid:\t200\nTgid:\t200\nFDSize:\t0\nThreads:\t1\n'
        values = {'/proc/sys/kernel/random/boot_id':O.BOOT,
                  '/proc/200/statm':'0 0 0 0 0 0 0', '/proc/200/status':status}
        def read_text(path, *args, **kwargs):
            self.assertIn(str(path), values)
            return values[str(path)]
        with patch.object(O, 'read_proc', side_effect=[row,row]), \
                patch.object(O.Path, 'read_text', read_text), \
                patch.object(O.Path, 'iterdir', side_effect=PermissionError(13,'denied')), \
                patch.object(O.os, 'stat', return_value=SimpleNamespace(st_ino=O.PIDNS)):
            actual=O.observed_process(200,row)
        self.assertEqual(actual,{'absent':False,'row':row,'closed':True})
        values['/proc/200/status']=status.replace('Threads:\t1','Threads:\t2')
        with patch.object(O, 'read_proc', return_value=row), \
                patch.object(O.Path, 'read_text', read_text), \
                patch.object(O.Path, 'iterdir', side_effect=PermissionError(13,'denied')), \
                patch.object(O.os, 'stat', return_value=SimpleNamespace(st_ino=O.PIDNS)):
            actual=O.observed_process(200,row)
        self.assertEqual(actual,{'absent':None,'row':None,'closed':None})

    def test_one_engineering_native_role_is_closed_and_injected_DEV_role_is_refused(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            expected={'schema_version':1,'epoch':35,'kind':O.KIND,'phase':'engineering',
                'plan_sha256':'a'*64,'source_freeze_sha256':'b'*64,
                'pretrained_model_source_sha256':'c'*64,'model_assets_lock_sha256':'d'*64,
                'admission_sha256':'e'*64,'kernel_boot_id':O.BOOT,'pid_namespace_inode':O.PIDNS,
                'logical_native_budget_reserved':1,'allowed_further_dispatches':0}
            def put(path,value):
                target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(value))
                return O.file_ref(root,path)
            claim=dict(expected,dispatch_monotonic_seconds=1.5,dispatch_unix_seconds=2.5)
            cr=put(O.PATHS['dispatch_reservation'],claim)
            ar=put(O.PATHS['dispatch_attempt'],dict(claim,**self.sup,verified_launcher_start=True,uncertain_launcher_start=False))
            corpus={};native_ids=[]
            for index,role in enumerate(('engineering',)):
                corpus[role]=put(O.STUDY+'runs/engineering/'+role.upper()+'_CORPUS_ATTEMPT_RESERVATION.json',
                    {'schema_version':1,'epoch':35,'kind':O.KIND,'phase':'engineering','role':role,'plan_sha256':'a'*64,
                     'corpus_batches_reserved':1,'allowed_further_role_helpers':0,'before_Popen':True,'automatic_retry':False,'at_unix':3.5})
                native=dict(self.worker,pid=202+index,ppid=201,ticks=1002+index)
                native_ids.append(native)
                put(O.STUDY+'runs/engineering/'+role+'-native-attempt.json',
                    {'pid':native['pid'],'identity':native,'role':role,'source_sha256':'f'*64})
            execution=dict(self.execution,**{k:expected[k] for k in
                ('schema_version','epoch','kind','phase','plan_sha256','kernel_boot_id','pid_namespace_inode')},
                supervisor_identity=self.sup,dispatch_reservation=cr,dispatch_attempt=ar,
                logical_native_budget_reserved=1,source_plan_unchanged=True,corpus_reservations=corpus,corpus_reservation_count=1)
            helper='experiments/sota-2026-10-22/candidate/epoch35/native_helper.cjs'
            pins={helper:{'sha256':'f'*64}}
            def write_chain():
                ex=put(O.PATHS['execution'],execution)
                put(O.PATHS['supervisor_completion'],dict(
                    {k:expected[k] for k in ('schema_version','epoch','kind','phase','kernel_boot_id','pid_namespace_inode')},
                    status='SUPERVISOR_ABOUT_TO_EXIT',supervisor_identity=self.sup,execution_sha256=ex['sha256'],
                    execution_status=execution['status'],intended_exit_code=0 if execution['status']=='WORKER_COMPLETED' else 2,
                    exit_code_observed_by_root=False,requires_external_physical_supervisor_closure=True))
            write_chain()
            refs,docs,sup,ids,extras,approved=O.load_evidence(root,expected,pins)
            self.assertEqual(len(ids),2)
            self.assertEqual(len(extras),2)
            for row in native_ids:self.snap['processes'][row['pid']]={'absent':True,'row':None,'closed':True}
            self.assertTrue(O.evaluate('a'*64,refs,docs,sup,ids,self.snap,approved)['physical_closure_passed'])
            # A semantic refusal still closes the same one helper; physical closure
            # must never infer DEV permission or accept a new role reservation.
            before=copy.deepcopy(docs['execution'])
            self.assertEqual(docs['execution'],before)
            execution['corpus_reservations']=dict(corpus,dev=None)
            write_chain()
            with self.assertRaises(ValueError):O.load_evidence(root,expected,pins)



if __name__ == '__main__':
    unittest.main()
