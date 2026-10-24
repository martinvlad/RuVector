"""Pure fixtures only. Never invoke supplemental main or live proc reads."""
from pathlib import Path
import copy
import unittest
from unittest.mock import patch
import supplemental_observer as S

ROOT = Path('/tmp/ruvector-sota-2026-10-22/epoch31-de468eba3faa/project')
O = S.load_frozen(ROOT)  # Exact hash-verified stdlib source only, no main call.


class NarrowCapacityFixtures(unittest.TestCase):
    def setUp(self):
        self.row = {'pid': 200, 'ticks': 1000, 'pgid': 200, 'sid': 200, 'ppid': 1, 'state': 'Z'}
        self.status = 'Name:\tpython\nState:\tZ (zombie)\nTgid:\t200\nPid:\t200\nFDSize:\t0\nThreads:\t1\n'
        self.args = {'expected': self.row, 'before': self.row, 'after': self.row,
            'statm': '0 0 0 0 0 0 0\n', 'status': self.status, 'fd_errno': 13,
            'boot_before': O.BOOT, 'boot_after': O.BOOT, 'namespace_before': O.PIDNS, 'namespace_after': O.PIDNS}
        guard = patch.object(O, 'snapshot', side_effect=AssertionError('Live proc observation forbidden'))
        guard.start();self.addCleanup(guard.stop)

    def check(self, **changes):
        return S.terminal_capacity(O, **dict(self.args, **changes))

    def test_exact_z_and_x_capacity_proofs(self):
        self.assertTrue(self.check())
        x = dict(self.row, state='X')
        self.assertTrue(self.check(before=x, after=x, status=self.status.replace('Z (zombie)', 'X (dead)')))

    def test_other_errno_nonzero_or_missing_capacity_threads_block(self):
        for value in (None, 0, 1, 2, True):
            self.assertFalse(self.check(fd_errno=value))
        for text in (self.status.replace('FDSize:\t0', 'FDSize:\t1'),
                     self.status.replace('Threads:\t1', 'Threads:\t2'),
                     self.status.replace('FDSize:\t0\n', ''),
                     self.status.replace('Threads:\t1\n', ''),
                     self.status + 'FDSize:\t0\n', self.status.replace('FDSize:\t0', 'FDSize:\t00')):
            self.assertFalse(self.check(status=text))

    def test_nonzero_missing_memory_and_live_process_block(self):
        for text in ('0 0 0 0 0 0', '0 0 1 0 0 0 0', '', '0 0 0 0 0 0 00'):
            self.assertFalse(self.check(statm=text))
        live = dict(self.row, state='S')
        self.assertFalse(self.check(before=live, after=live, status=self.status.replace('Z (zombie)', 'S (sleeping)')))

    def test_identity_boot_namespace_or_status_mismatch_block(self):
        self.assertFalse(self.check(after=dict(self.row, ticks=1001)))
        self.assertFalse(self.check(before=dict(self.row, ticks=1001), after=dict(self.row, ticks=1001)))
        self.assertFalse(self.check(boot_after='another-boot'))
        self.assertFalse(self.check(namespace_after=O.PIDNS + 1))
        self.assertFalse(self.check(status=self.status.replace('Pid:\t200', 'Pid:\t201')))
        self.assertFalse(self.check(status=self.status.replace('Tgid:\t200', 'Tgid:\t201')))

    def test_same_frozen_reducer_requires_all_other_closure_evidence(self):
        sup = {'pid': 200, 'startticks': 1000, 'pgid': 200, 'sid': 200}
        worker = {'pid': 201, 'ticks': 1001, 'pgid': 201, 'sid': 201, 'ppid': 200, 'state': 'R'}
        execution = {'status': 'WORKER_COMPLETED', 'worker_popen_attempted': True,
            'worker_popen_attempts': 1, 'worker_start_boundary': 'WORKER_POPEN_ATTEMPTED',
            'worker_identity': worker, 'verified_worker_starts': 1, 'uncertain_start': False,
            'owned_live_processes_closed': True, 'owned_live_group_members': [],
            'owned_process_closure_observation': 'OBSERVED'}
        docs = {'execution': execution, 'dispatch_attempt': {}}
        refs = {key: None for key in O.PATHS}
        snap = {'scan_error': False, 'rows': [], 'processes': {
            200: {'absent': None, 'row': None, 'closed': None},
            201: {'absent': True, 'row': None, 'closed': True}}}
        before = copy.deepcopy(execution)
        self.assertFalse(O.evaluate(S.PLAN_SHA, refs, docs, sup, [worker], snap, True)['physical_closure_passed'])
        self.assertTrue(self.check())
        snap['processes'][200] = {'absent': False, 'row': self.row, 'closed': True}
        value = O.evaluate(S.PLAN_SHA, refs, docs, sup, [worker], snap, True)
        self.assertTrue(value['physical_closure_passed'])
        self.assertEqual(len(value), 18)
        self.assertFalse(value['physical_supervisor_absent'])
        self.assertEqual(execution, before)
        snap['rows'] = [worker]
        self.assertFalse(O.evaluate(S.PLAN_SHA, refs, docs, sup, [worker], snap, True)['physical_closure_passed'])
        snap['rows'] = [];snap['scan_error'] = True
        self.assertTrue(O.evaluate(S.PLAN_SHA, refs, docs, sup, [worker], snap, True)['unknown_physical_ownership'])
        docs['execution'] = None
        self.assertFalse(O.evaluate(S.PLAN_SHA, refs, docs, sup, [worker], snap, True)['physical_closure_passed'])


if __name__ == '__main__':
    unittest.main()
