"""Synthetic local publication guards; no benchmark/model/network/Git calls."""
import sys
sys.dont_write_bytecode = True
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import publication_common_v1 as c
import stage_publication_v1 as s

HERE = Path(__file__).resolve().parent


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else c.encoded(value, pretty=True))


class Fixture:
    def __init__(self, root):
        self.root = root; self.project = root/'project'; self.kit = root/'kit'
        self.project.mkdir(); self.kit.mkdir()
        self.transport = {'format': 'gzip+base64', 'required_before_bootstrap': True}
        for key, name in [('archive', 'archive.json'), ('extractor', 'restore.py'),
                          ('publication_helper', 'helper.py'), ('restored_artifact', 'raw.json')]:
            path = c.P+'epoch22/'+name
            put(self.project/path, ('historical '+name+'\n').encode())
            self.transport[key] = c.ref(self.project, path)
            if key != 'restored_artifact': put(self.kit/path, c.content(self.project/path))
        self.transport['standalone_Git_leaf_omitted'] = self.transport['restored_artifact']['path']
        self.old_cp = {'schema_version': 1, 'scope': 'frozen history',
            'epoch25_final': {'status': 'REJECTED', 'network_operations': 1},
            'project_files': [self.transport[k] for k in ('archive', 'extractor', 'publication_helper', 'restored_artifact')]}
        ledger = {'current_epoch_closed': True, 'scope': 'ALL_EPOCHS_CLOSED_THROUGH25',
            'cumulative_native_process_attempts_including_qualification': 26,
            'cumulative_corpus_attempts_current': 22, 'epoch25_closed': {'network_operations': 1},
            'new_study_id': 'prior', 'new_study_attempt_cap': 1, 'new_study_attempts_used': 1}
        for key in ('publication_period_native_calls_allowed', 'new_study_attempts_remaining',
            'new_study_unspent_phase_slots', 'allowed_further_attempts_in_closed_study',
            'conditional_DEV_after_exact_remote_readback', 'conditional_CONF_after_independent_DEV_runtime_gates'):
            ledger[key] = 0
        self.old_cont = {'schema_version': 1, 'goal_met': False, 'official_rank': None,
            'artifact_transport': self.transport, 'checkpoint_manifest_sha256': c.sha(c.encoded(self.old_cp, pretty=True)),
            'active_run': {'old': True}, 'prior_published_base_commit': '0'*40,
            'benchmark_refresh': {'old': True}, 'epochs': [{'epoch': 25, 'status': 'FAILED'}],
            'execution_observed': {'cumulative_bounded_native_process_attempts_including_qualification': 26,
                'epoch25_actual_execution': {'Python_network_operations_attempted': 1}},
            'cumulative_budget_ledger': ledger, 'exposed_development_sets': ['old'],
            'unused_confirmation_sets': {'native104': ['protected']}}
        for name, value in [('CHECKPOINT_MANIFEST.json', self.old_cp), ('CONTINUATION.json', self.old_cont), ('ACTIVE_RUN.json', {'old': True})]:
            put(self.kit/name, value)
        self.baseline = {p.relative_to(self.kit).as_posix(): s.leaf(p.relative_to(self.kit).as_posix(), p.read_bytes())
                         for p in self.kit.rglob('*') if p.is_file()}
        put(root/'source-filemap.json', {'scope': c.SCOPE, 'files': list(self.baseline.values())})
        self.planning = {'restored_source_head': c.BASE_COMMIT, 'confirmation_identity': []}
        self.lease_active = self.active('EPOCH26_EXCLUSIVE_PLANNING', c.BASE_COMMIT, True)
        lease = copy.deepcopy(self.old_cont)
        lease.update(active_run=dict(self.lease_active, path='ACTIVE_RUN.json'), epoch26_planning=self.planning)
        self.controls(root/'controls-lease', self.old_cp, lease, self.lease_active)
        self.source_files()

    def active(self, state, parent, work):
        return {'run_id': c.OWNER_RUN_ID, 'state': state, 'checkpoint_parent': parent,
            'work_active': work, 'experiments_active': False, 'OS_lock_held': True,
            'native_allowed': 0, 'conditional_confirmation_allowed': 0,
            'native_allowed_after_exact_remote_readback': int(work and 'SOURCE' in state),
            'physical_owner': {'pid': c.OWNER_PIN[0], 'startticks': c.OWNER_PIN[1],
                'lock_inode': c.OWNER_PIN[2], 'expires_unix': c.OWNER_EXPIRES_UNIX}}

    def controls(self, path, cp, cont, active):
        for name, value in [('CHECKPOINT_MANIFEST.json', cp), ('CONTINUATION.json', cont), ('ACTIVE_RUN.json', active)]: put(path/name, value)

    def current(self): return c.walk_current(self.project)

    def review(self, name):
        put(self.root/name, {'files': [{'path': p, 'bytes': len(b), 'sha256': c.sha(b)} for p, b in sorted(self.current().items())]})

    def cp(self):
        cp = copy.deepcopy(self.old_cp)
        cp['epoch26_source'] = {'frozen': True}
        cp['project_files'] += [c.ref(self.project, p) for p in sorted(self.current())]
        return cp

    def source_files(self):
        put(self.project/(c.P+'candidate/epoch26/source.py'), b'value = 26\n')
        for path in s.ORACLE_REFS.values(): put(self.project/path, {'epoch': 26} if path.endswith('.json') else b'pass\n')
        put(self.project/(c.P+'legal-transfer/epoch26/benchmark-refresh.json'), {'epoch': 26})
        self.roles = {'train': [], 'dev': list(range(8)), 'calibration': [], 'confirmation': []}
        put(self.project/s.FROZEN_REFS['PLAN_SPEC'], {'epoch': 26, 'data_roles': self.roles})
        entries = [c.ref(self.project, p) for p in sorted(self.current())]
        put(self.project/s.FROZEN_REFS['source_freeze'], {'epoch': 26, 'source_checkpoint': c.BASE_COMMIT,
            'source_entries': entries, 'external_runtime_assets': [{'sha256': '0'*64, 'bytes': 1, 'path': '/external/unpublished/model'}]})
        self.plan = {'epoch': 26, 'kind': s.KIND, 'source_checkpoint': c.BASE_COMMIT,
            'data_roles': self.roles, 'limits': {'owned_workers': 1, 'CPU_threads': 2, 'CPU_affinity': [0, 1],
                'seconds_per_batch': 600, 'NLI_forward_pairs': 72, 'native_queries': 24, 'paid_calls': 0, 'GPU_calls': 0},
            'pins': entries+[c.ref(self.project, s.FROZEN_REFS['source_freeze'])]}
        self.plan.update({k: c.ref(self.project, p) for k, p in s.ORACLE_REFS.items()})
        put(self.project/s.FROZEN_REFS['plan'], self.plan)
        self.frozen = {k: c.ref(self.project, p) for k, p in s.FROZEN_REFS.items()}
        self.source_cp = self.cp()
        self.source_active = self.active('EPOCH26_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION', s.LEASE_COMMIT, True)
        self.source_cont = copy.deepcopy(self.old_cont)
        refresh = c.ref(self.project, c.P+'legal-transfer/epoch26/benchmark-refresh.json')
        self.source_cont.update(epoch26_planning=self.planning, epoch26_frozen_study=self.frozen,
            epoch26_official_refresh=refresh, benchmark_refresh=refresh,
            prior_published_base_commit=s.LEASE_COMMIT,
            checkpoint_manifest_sha256=c.sha(c.encoded(self.source_cp, pretty=True)),
            active_run=dict(self.source_active, path='ACTIVE_RUN.json'))
        self.controls(self.root/'controls-source', self.source_cp, self.source_cont, self.source_active)
        put(self.root/'lease-readback.json', {'commit': s.LEASE_COMMIT, 'parent': c.BASE_COMMIT,
            'verified': True, **dict(zip(('root', 'bench', 'scope'), s.LEASE_TREES))})
        self.review('source-reviewed-files.json')

    def args(self, phase='source'):
        final = phase == 'final'
        return SimpleNamespace(project=self.project, kit=self.kit, source_filemap=self.root/'source-filemap.json',
            phase=phase, controls=self.root/('controls-final' if final else 'controls-source'),
            priorcontrols=self.root/('controls-source' if final else 'controls-lease'),
            reviewed_files=self.root/('final-reviewed-files.json' if final else 'source-reviewed-files.json'),
            prior_expected=self.root/'stage-source/expected-leaves.json' if final else None,
            parent_readback=self.root/('source-readback.json' if final else 'lease-readback.json'),
            parent='a'*40 if final else s.LEASE_COMMIT, expected_main=s.MAIN_COMMIT,
            expected_root='b'*40 if final else s.LEASE_TREES[0], expected_bench='c'*40 if final else s.LEASE_TREES[1],
            expected_scope='d'*40 if final else s.LEASE_TREES[2], out=self.root/('stage-final' if final else 'stage-source'))

    def final_files(self, failed=False):
        counters = dict.fromkeys(s.ZERO_COUNTERS+s.COUNT_COUNTERS, 0)
        counters.update(NLI_model_initializations=1, NLI_model_initializations_completed=1,
            NLI_forward_pairs_attempted=72, NLI_forward_pairs_completed=72, NLI_forwards=72,
            native_index_initializations_attempted=8, native_index_initializations_completed=8,
            native_queries_attempted=24, native_queries_completed=24, DEV_cases_completed=24,
            DEV_pairs_completed=72, BGE_initializations_attempted=1, BGE_initializations_completed=1,
            BGE_forwards_attempted=1, BGE_forwards_completed=1, BGE_texts_attempted=1, BGE_texts_completed=1,
            Python_literal_loopback_binds_allowed=1)
        if failed:
            counters.update(Python_network_operations_attempted=1, NLI_forward_pairs_completed=1,
                NLI_forwards=1, DEV_pairs_completed=1, DEV_cases_completed=0)
        raw = {'epoch': 26, 'phase': 'dev', 'counters': counters, 'cases': [{}]*int(not failed)*24,
               'errors': [{'type': 'ForbiddenNetwork'}] if failed else []}
        put(self.project/(s.E+'runs/dev/raw.json'), raw)
        rawref = c.ref(self.project, s.E+'runs/dev/raw.json')
        execution = {'worker_attempts_reserved': 1, 'verified_worker_starts': 1,
            'CPU_affinity': [0, 1], 'wall_seconds_including_init_cleanup': 700 if failed else 100,
            'owned_live_processes_closed': True, 'owned_live_group_members': [],
            'raw_bytes': rawref['bytes'], 'raw_sha256': rawref['sha256'],
            'status': 'WORKER_FAILED_OR_TIMEOUT' if failed else 'WORKER_COMPLETED', 'exit_code': 2 if failed else 0}
        put(self.project/(s.E+'execution.json'), execution)
        actual = dict(counters, worker_attempts=1, verified_worker_starts=1,
            errors=len(raw['errors']), owned_live_processes_closed=True, CPU_affinity=[0, 1],
            wall_seconds_including_init_cleanup=execution['wall_seconds_including_init_cleanup'])
        actual.update({k: counters[v] for k, v in s.ALIASES.items()})
        put(self.project/(s.E+'RESULTS.json'), {'epoch': 26, 'actual_execution': actual,
            'status': 'FAILED' if failed else 'DEV_DIAGNOSTIC', 'metrics': None if failed else {'n': 24}})
        evidence = {'raw': rawref, 'execution': c.ref(self.project, s.E+'execution.json'),
                    'results': c.ref(self.project, s.E+'RESULTS.json')}
        reportpath = c.P+'audit/epoch26/independent-report.json'
        put(self.project/reportpath, {'epoch': 26, 'checks_passed': True, 'benchmark_accepted': False,
            'diagnostic_qualified': not failed, 'evidence': evidence})
        ledger = copy.deepcopy(self.old_cont['cumulative_budget_ledger'])
        ledger.update(current_epoch_closed=True, scope='ALL_EPOCHS_CLOSED_THROUGH26',
            cumulative_native_process_attempts_including_qualification=27, epoch26_actual_execution=actual)
        manifest = {'epoch': 26, 'kind': s.KIND, 'source_checkpoint': c.BASE_COMMIT,
            'published_frozen_source_commit': 'a'*40, 'all_slots_closed': True,
            'benchmark_accepted': False, 'champion_promoted': False, 'new_submission': False,
            'diagnostic_qualified': not failed, 'status': 'FAILED_DEV_DIAGNOSTIC' if failed else 'DEV_DIAGNOSTIC_QUALIFIED',
            'plan': self.frozen['plan'], 'source_freeze': self.frozen['source_freeze'],
            'actual_execution': actual, 'independent_report': c.ref(self.project, reportpath),
            'data_roles': self.roles, 'cumulative_budget_ledger': ledger, **evidence}
        put(self.project/(s.E+'EPOCH_MANIFEST.json'), manifest)
        cont = copy.deepcopy(self.source_cont)
        observed = copy.deepcopy(self.old_cont['execution_observed'])
        observed.update(cumulative_bounded_native_process_attempts_including_qualification=27, epoch26_actual_execution=actual)
        active = self.active('EPOCH26_CLOSED', 'a'*40, False)
        cp = self.cp()
        cont.update(active_run=dict(active, path='ACTIVE_RUN.json'), checkpoint_manifest_sha256=c.sha(c.encoded(cp, pretty=True)),
            prior_published_base_commit='a'*40, execution_observed=observed, cumulative_budget_ledger=ledger,
            epochs=self.old_cont['epochs']+[{'epoch': 26, 'native_worker_attempts': 1}])
        self.controls(self.root/'controls-final', cp, cont, active)
        put(self.root/'source-readback.json', {'commit': 'a'*40, 'root': 'b'*40, 'bench': 'c'*40,
            'scope': 'd'*40, 'verified_actual_full_tree': True})
        self.review('final-reviewed-files.json')
        return manifest


class Guards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='synthetic-', dir=HERE)
        self.addCleanup(self.tmp.cleanup)
        self.f = Fixture(Path(self.tmp.name))
        for target, value in [('stage_publication_v1.BASE_GIT_LEAVES', 6), ('publication_common_v1.OLD_CP_ROWS', 4)]:
            patcher = patch(target, value); patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch('stage_publication_v1.live_owner', return_value={'synthetic': True})
        patcher.start(); self.addCleanup(patcher.stop)

    def source(self): return s.prepare(self.f.args())
    def final(self, failed=False):
        self.source(); self.f.final_files(failed); return s.prepare(self.f.args('final'))

    def test_source_success_preserves_original_and_archive(self):
        result = self.source(); meta = c.parse(self.f.root/'stage-source/metadata.json')
        self.assertEqual(result['old_CP_rows'], 4)
        self.assertEqual(meta['Git_mutations'], 0)
        leaves = s.tuple_map(c.parse(self.f.root/'stage-source/expected-leaves.json'))
        self.assertNotIn(self.f.transport['restored_artifact']['path'], leaves)
        self.assertEqual(meta['CAS_guards']['expected_branch_sha'], s.LEASE_COMMIT)

    def test_private_secret_refused(self):
        with self.assertRaises(ValueError): c.public_text(s.E+'leak.txt', ('ghp_'+'a'*35).encode())

    def test_raw_page_refused(self):
        with self.assertRaises(ValueError): c.public_text(s.E+'page.txt', ('<'+'html'+'>').encode())

    def test_path_and_weight_directory_refused(self):
        for path in ['../escape.json', '/absolute.json', s.E+'weights/model.json', s.E+'runtime.so']:
            with self.subTest(path=path), self.assertRaises(ValueError): c.public_text(path, b'{}')

    def test_symlink_refused(self):
        link = self.f.root/'link'; link.symlink_to(self.f.root/'source-filemap.json')
        with self.assertRaises(ValueError): c.content(link)

    def test_nonfinite_and_duplicate_json_refused(self):
        for data in [b'{"x":NaN}', b'{"x":1e400}', b'{"x":1,"x":2}']:
            with self.subTest(data=data), self.assertRaises(ValueError): c.loads(data)

    def test_original_git_tuple_change_refused(self):
        path = self.f.transport['archive']['path']; put(self.f.kit/path, b'drift\n')
        with self.assertRaises(ValueError): self.source()

    def test_old_checkpoint_metadata_change_refused(self):
        path = self.f.root/'controls-source/CHECKPOINT_MANIFEST.json'; cp = c.parse(path)
        cp['epoch25_final']['network_operations'] = 0; put(path, cp)
        with self.assertRaises(ValueError): self.source()

    def test_unreviewed_extra_source_refused(self):
        put(self.f.project/(s.E+'extra.py'), b'pass\n')
        with self.assertRaises(ValueError): self.source()

    def test_wrong_parent_readback_refused(self):
        args = self.f.args(); args.parent = '9'*40
        with self.assertRaises(ValueError): s.prepare(args)

    def test_frozen_pin_change_refused(self):
        put(self.f.project/s.ORACLE_REFS['independent_scorer'], b'value = 1\n')
        self.f.review('source-reviewed-files.json')
        with self.assertRaises(ValueError): self.source()

    def test_tree_blob_caps_and_utf8_identity(self):
        blobs, groups = s.transport_groups({s.E+'large.json': ('é'*50000).encode()})
        self.assertEqual(len(blobs), 1)
        self.assertLess(len(c.encoded(blobs[0][2])), s.MAX_BLOB_JSON)
        self.assertTrue(all(len(c.encoded({'tree_elements': g})) < s.MAX_TREE_JSON for g in groups))

    def test_final_success_is_diagnostic_only(self):
        result = self.final(); self.assertEqual(result['stage'], 'final')
        manifest = c.parse(self.f.project/(s.E+'EPOCH_MANIFEST.json'))
        self.assertTrue(manifest['diagnostic_qualified']); self.assertFalse(manifest['benchmark_accepted'])

    def test_failed_timeout_partial_and_network_counter_retained(self):
        result = self.final(True); self.assertEqual(result['stage'], 'final')
        raw = c.parse(self.f.project/(s.E+'runs/dev/raw.json'))
        self.assertEqual(raw['counters']['Python_network_operations_attempted'], 1)
        self.assertEqual(len(raw['cases']), 0)

    def test_failed_runtime_cannot_qualify(self):
        self.source(); m = self.f.final_files(True)
        raw = c.parse(self.f.project/m['raw']['path']); outer = c.parse(self.f.project/m['execution']['path'])
        with self.assertRaises(ValueError): s.check_actual(m['actual_execution'], raw, outer, True)

    def test_manifest_actual_counter_rewrite_refused(self):
        self.source(); m = self.f.final_files()
        m['actual_execution']['native_queries_completed'] = 0
        raw = c.parse(self.f.project/m['raw']['path']); outer = c.parse(self.f.project/m['execution']['path'])
        with self.assertRaises(ValueError): s.check_actual(m['actual_execution'], raw, outer, False)

    def test_final_frozen_source_change_refused(self):
        self.source(); self.f.final_files(); put(self.f.project/(c.P+'candidate/epoch26/source.py'), b'changed\n')
        self.f.review('final-reviewed-files.json')
        with self.assertRaises(ValueError): s.prepare(self.f.args('final'))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Guards)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'schema_version': 1, 'epoch': 26, 'kind': 'SYNTHETIC_PUBLICATION_GUARDS_ONLY',
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'checks_passed': result.wasSuccessful(), 'synthetic_fixtures_only': True,
        'Git_network_mail_model_native_benchmark_calls': 0,
        'cases': [case._testMethodName for case in unittest.defaultTestLoader.loadTestsFromTestCase(Guards)]}
    put(HERE/'guard-tests.v1.json', report)
    raise SystemExit(0 if result.wasSuccessful() else 1)
