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
# Public official MIT text used as a self-contained source-license fixture.
FAIRSEQ_MIT = b'MIT License\n\nCopyright (c) Facebook, Inc. and its affiliates.\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the "Software"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.\n'


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
            path = (c.P+'epoch22/runs/dev/raw.json' if key == 'restored_artifact'
                    else c.P+'epoch22/publication/'+name)
            put(self.project/path, ('historical '+name+'\n').encode())
            self.transport[key] = c.ref(self.project, path)
            if key != 'restored_artifact': put(self.kit/path, c.content(self.project/path))
        self.transport['standalone_Git_leaf_omitted'] = self.transport['restored_artifact']['path']
        self.historical_refs = {self.transport[k]['path']: self.transport[k]
            for k in ('archive', 'extractor', 'publication_helper', 'restored_artifact')}
        descriptors = []
        for artifact in ('raw', 'native-result'):
            item = {'format': 'gzip+base64', 'required_before_bootstrap': True,
                'source_commit': '00d49880e0b6a7dc2aea8cb155d64549f423c782'}
            for key, suffix in [('archive', 'archives/' + artifact + '.json'),
                    ('extractor', 'restore.py'), ('publication_helper', 'prepare.py'),
                    ('restored_artifact', '../runs/dev/' + artifact + '.json')]:
                path = (c.P + 'epoch26/runs/dev/' + artifact + '.json' if key == 'restored_artifact'
                        else c.P + 'epoch26/publication/' + suffix)
                put(self.project/path, ('historical epoch26 ' + suffix + '\n').encode())
                item[key] = c.ref(self.project, path)
                self.historical_refs[path] = item[key]
                if key != 'restored_artifact': put(self.kit/path, c.content(self.project/path))
            item['standalone_Git_leaf_omitted'] = item['restored_artifact']['path']
            descriptors.append(item)
        manifest_path = c.P + 'epoch26/publication/archive-transport.v1.json'
        put(self.project/manifest_path, {'schema_version': 1, 'epoch': 26,
            'format': 'gzip+base64', 'source_commit': descriptors[0]['source_commit'],
            'descriptors': descriptors})
        put(self.kit/manifest_path, c.content(self.project/manifest_path))
        self.transports26 = {'manifest': c.ref(self.project, manifest_path), 'descriptors': descriptors}
        self.historical_refs[manifest_path] = self.transports26['manifest']
        for name in ('bootstrap.py', 'restore_checkpoint.py'):
            put(self.kit/name, ('historical ' + name + '\n').encode())
        self.restore26 = {'manifest': self.transports26['manifest'],
            'extractor': descriptors[0]['extractor'], 'run_after_inherited_epoch22_restore': True,
            'must_run_before_bootstrap': True, 'original_bootstrap': c.ref(self.kit, 'bootstrap.py'),
            'original_restore': c.ref(self.kit, 'restore_checkpoint.py'), 'instructions': 'Restore inherited archives before bootstrap.'}
        self.old_cp = {'schema_version': 1, 'scope': 'frozen history',
            'epoch26_final': {'status': 'REJECTED', 'network_operations': 1},
            'project_files': list(self.historical_refs.values())}
        ledger = {'current_epoch_closed': True, 'scope': 'ALL_EPOCHS_CLOSED_THROUGH26',
            'cumulative_native_process_attempts_including_qualification': 27,
            'cumulative_corpus_attempts_current': 22, 'epoch26_closed': {'network_operations': 1},
            'new_study_id': 'prior', 'new_study_attempt_cap': 1, 'new_study_attempts_used': 1}
        for key in ('publication_period_native_calls_allowed', 'new_study_attempts_remaining',
            'new_study_unspent_phase_slots', 'allowed_further_attempts_in_closed_study',
            'conditional_DEV_after_exact_remote_readback', 'conditional_CONF_after_independent_DEV_runtime_gates'):
            ledger[key] = 0
        self.old_cont = {'schema_version': 1, 'goal_met': False, 'official_rank': None,
            'artifact_transport': self.transport, 'checkpoint_manifest_sha256': c.sha(c.encoded(self.old_cp, pretty=True)),
            'epoch26_artifact_transports': self.transports26, 'epoch26_restore': self.restore26,
            'active_run': {'old': True}, 'prior_published_base_commit': '0'*40,
            'benchmark_refresh': {'old': True}, 'epochs': [{'epoch': 26, 'status': 'FAILED'}],
            'execution_observed': {'cumulative_bounded_native_process_attempts_including_qualification': 27,
                'epoch26_actual_execution': {'Python_network_operations_attempted': 1}},
            'cumulative_budget_ledger': ledger, 'exposed_development_sets': ['old'],
            'unused_confirmation_sets': {'native104': ['protected']}}
        for name, value in [('CHECKPOINT_MANIFEST.json', self.old_cp), ('CONTINUATION.json', self.old_cont), ('ACTIVE_RUN.json', {'old': True})]:
            put(self.kit/name, value)
        self.baseline = {p.relative_to(self.kit).as_posix(): s.leaf(p.relative_to(self.kit).as_posix(), p.read_bytes())
                         for p in self.kit.rglob('*') if p.is_file()}
        put(root/'source-filemap.json', {'scope': c.SCOPE, 'files': list(self.baseline.values())})
        self.planning = {'restored_source_head': c.BASE_COMMIT, 'confirmation_identity': []}
        self.lease_active = self.active('EPOCH27_EXCLUSIVE_PLANNING', c.BASE_COMMIT, True)
        lease = copy.deepcopy(self.old_cont)
        lease.update(active_run=dict(self.lease_active, path='ACTIVE_RUN.json'), epoch27_planning=self.planning)
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
        cp['epoch27_source'] = {'frozen': True}
        cp['project_files'] += [c.ref(self.project, p) for p in sorted(self.current())]
        return cp

    def source_files(self):
        put(self.project/(c.P+'candidate/epoch27/source.py'), b'value = 27\n')
        for path in s.ORACLE_REFS.values(): put(self.project/path, {'epoch': 27} if path.endswith('.json') else b'pass\n')
        put(self.project/(c.P+'legal-transfer/epoch27/benchmark-refresh.json'), {'epoch': 27})
        self.roles = {'train': [], 'dev': list(s.DEV_DOCUMENT_IDS), 'calibration': [], 'confirmation': []}
        put(self.project/s.FROZEN_REFS['PLAN_SPEC'], {'epoch': 27, 'data_roles': self.roles})
        entries = [c.ref(self.project, p) for p in sorted(self.current())]
        put(self.project/s.FROZEN_REFS['source_freeze'], {'epoch': 27, 'source_checkpoint': c.BASE_COMMIT,
            'source_entries': entries, 'external_runtime_assets': [{'sha256': '0'*64, 'bytes': 1, 'path': '/external/unpublished/model'}]})
        self.plan = {'epoch': 27, 'kind': s.KIND, 'source_checkpoint': c.BASE_COMMIT,
            'data_roles': self.roles, 'limits': {'owned_workers': 1, 'CPU_threads': 2, 'CPU_affinity': [0, 1],
                'seconds_per_batch': 600, 'NLI_forward_pairs': 72, 'native_queries': 24, 'paid_calls': 0, 'GPU_calls': 0},
            'pins': entries+[c.ref(self.project, s.FROZEN_REFS['source_freeze'])]}
        self.plan.update({k: c.ref(self.project, p) for k, p in s.ORACLE_REFS.items()})
        put(self.project/s.FROZEN_REFS['plan'], self.plan)
        self.frozen = {k: c.ref(self.project, p) for k, p in s.FROZEN_REFS.items()}
        self.source_cp = self.cp()
        self.source_active = self.active('EPOCH27_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION', s.LEASE_COMMIT, True)
        self.source_cont = copy.deepcopy(self.old_cont)
        refresh = c.ref(self.project, c.P+'legal-transfer/epoch27/benchmark-refresh.json')
        self.source_cont.update(epoch27_planning=self.planning, epoch27_frozen_study=self.frozen,
            epoch27_official_refresh=refresh, benchmark_refresh=refresh,
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
        raw = {'epoch': 27, 'phase': 'dev', 'counters': counters, 'cases': [{}]*int(not failed)*24,
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
        put(self.project/(s.E+'RESULTS.json'), {'epoch': 27, 'actual_execution': actual,
            'kind': s.KIND, 'source_checkpoint': c.BASE_COMMIT,
            'published_frozen_source_commit': 'a'*40,
            'diagnostic_qualified': not failed, 'benchmark_accepted': False,
            'champion_promoted': False, 'new_submission': False, 'raw': rawref,
            'execution': c.ref(self.project, s.E+'execution.json'),
            'status': 'FAILED' if failed else 'DEV_DIAGNOSTIC', 'metrics': None if failed else {'n': 24}})
        evidence = {'raw': rawref, 'execution': c.ref(self.project, s.E+'execution.json'),
                    'results': c.ref(self.project, s.E+'RESULTS.json')}
        reportpath = c.P+'audit/epoch27/independent-report.json'
        put(self.project/reportpath, {'epoch': 27, 'checks_passed': True, 'benchmark_accepted': False,
            'diagnostic_qualified': not failed, 'evidence': evidence})
        ledger = copy.deepcopy(self.old_cont['cumulative_budget_ledger'])
        ledger.update(current_epoch_closed=True, scope='ALL_EPOCHS_CLOSED_THROUGH27',
            cumulative_native_process_attempts_including_qualification=28, epoch27_actual_execution=actual)
        manifest = {'epoch': 27, 'kind': s.KIND, 'source_checkpoint': c.BASE_COMMIT,
            'published_frozen_source_commit': 'a'*40, 'all_slots_closed': True,
            'benchmark_accepted': False, 'champion_promoted': False, 'new_submission': False,
            'diagnostic_qualified': not failed, 'status': 'FAILED_DEV_DIAGNOSTIC' if failed else 'DEV_DIAGNOSTIC_QUALIFIED',
            'plan': self.frozen['plan'], 'source_freeze': self.frozen['source_freeze'],
            'actual_execution': actual, 'independent_report': c.ref(self.project, reportpath),
            'data_roles': self.roles, 'cumulative_budget_ledger': ledger, **evidence}
        put(self.project/(s.E+'EPOCH_MANIFEST.json'), manifest)
        cont = copy.deepcopy(self.source_cont)
        observed = copy.deepcopy(self.old_cont['execution_observed'])
        observed.update(cumulative_bounded_native_process_attempts_including_qualification=28, epoch27_actual_execution=actual)
        active = self.active('EPOCH27_CLOSED', 'a'*40, False)
        cp = self.cp()
        cont.update(active_run=dict(active, path='ACTIVE_RUN.json'), checkpoint_manifest_sha256=c.sha(c.encoded(cp, pretty=True)),
            prior_published_base_commit='a'*40, execution_observed=observed, cumulative_budget_ledger=ledger,
            epochs=self.old_cont['epochs']+[{'epoch': 27, 'native_worker_attempts': 1}])
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
        for target, value in [('stage_publication_v1.BASE_GIT_LEAVES', len(self.f.baseline)),
                ('stage_publication_v1.BASE_SCOPE_TREE', s.scope_tree_sha(self.f.baseline)),
                ('stage_publication_v1.BASE_CP_SHA256', c.sha(c.content(self.f.kit/'CHECKPOINT_MANIFEST.json'))),
                ('publication_common_v1.OLD_CP_ROWS', len(self.f.old_cp['project_files']))]:
            patcher = patch(target, value); patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch('stage_publication_v1.live_owner', return_value={'synthetic': True})
        patcher.start(); self.addCleanup(patcher.stop)

    def source(self): return s.prepare(self.f.args())
    def final(self, failed=False):
        self.source(); self.f.final_files(failed); return s.prepare(self.f.args('final'))

    def test_source_success_preserves_original_and_archive(self):
        result = self.source(); meta = c.parse(self.f.root/'stage-source/metadata.json')
        self.assertEqual(result['old_CP_rows'], len(self.f.old_cp['project_files']))
        self.assertEqual(meta['Git_mutations'], 0)
        leaves = s.tuple_map(c.parse(self.f.root/'stage-source/expected-leaves.json'))
        self.assertNotIn(self.f.transport['restored_artifact']['path'], leaves)
        for item in self.f.transports26['descriptors']:
            self.assertNotIn(item['restored_artifact']['path'], leaves)
            for key in ('archive', 'extractor', 'publication_helper'):
                self.assertIn(item[key]['path'], leaves)
        self.assertEqual(len(meta['inherited_archive_transport_unchanged']['CP_only_artifacts']), 3)
        self.assertEqual(meta['CAS_guards']['expected_branch_sha'], s.LEASE_COMMIT)

    def test_private_secret_refused(self):
        with self.assertRaises(ValueError): c.public_text(s.E+'leak.txt', ('ghp_'+'a'*35).encode())

    def test_raw_page_refused(self):
        with self.assertRaises(ValueError): c.public_text(s.E+'page.txt', ('<'+'html'+'>').encode())

    def test_path_and_weight_directory_refused(self):
        for path in ['../escape.json', '/absolute.json', s.E+'weights/model.json', s.E+'runtime.so']:
            with self.subTest(path=path), self.assertRaises(ValueError): c.public_text(path, b'{}')

    def test_fairseq_license_exception_is_exact_and_still_public_text(self):
        self.assertEqual(c.public_text(c.FAIRSEQ_LICENSE_PATH, FAIRSEQ_MIT), FAIRSEQ_MIT.decode())
        data = b'Synthetic public MIT license\n'
        with patch.object(c, 'FAIRSEQ_LICENSE_BYTES', len(data)), patch.object(c, 'FAIRSEQ_LICENSE_SHA256', c.sha(data)):
            self.assertEqual(c.public_text(c.FAIRSEQ_LICENSE_PATH, data), data.decode())
            for path, body in [(c.FAIRSEQ_LICENSE_PATH, b'changed license\n'),
                    (s.E+'LICENSE.fairseq', data),
                    (c.FAIRSEQ_LICENSE_PATH.replace('LICENSE', 'OTHER'), data)]:
                with self.subTest(path=path), self.assertRaises(ValueError): c.public_text(path, body)
        private = ('ghp_'+'a'*35).encode()
        with patch.object(c, 'FAIRSEQ_LICENSE_BYTES', len(private)), patch.object(c, 'FAIRSEQ_LICENSE_SHA256', c.sha(private)):
            with self.assertRaises(ValueError): c.public_text(c.FAIRSEQ_LICENSE_PATH, private)

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
        cp['epoch26_final']['network_operations'] = 0; put(path, cp)
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
        self.source(); self.f.final_files(); put(self.f.project/(c.P+'candidate/epoch27/source.py'), b'changed\n')
        self.f.review('final-reviewed-files.json')
        with self.assertRaises(ValueError): s.prepare(self.f.args('final'))

    def test_each_of_three_inherited_original_byte_changes_refused(self):
        rows = c.cp_rows(self.f.old_cp)
        originals = [self.f.transport] + self.f.transports26['descriptors']
        for item in originals:
            path = self.f.project/item['restored_artifact']['path']
            before = path.read_bytes(); path.write_bytes(b'changed original\n')
            try:
                with self.subTest(path=item['restored_artifact']['path']), self.assertRaises(ValueError):
                    c.check_transport(self.f.project, self.f.old_cont, self.f.source_cont,
                        rows, set(self.f.baseline), kit=self.f.kit)
            finally: path.write_bytes(before)

    def test_inherited_epoch26_manifest_and_restore_tamper_refused(self):
        for key in ('epoch26_artifact_transports', 'epoch26_restore'):
            cont = copy.deepcopy(self.f.source_cont); cont[key] = {}
            with self.subTest(key=key), self.assertRaises(ValueError):
                c.check_transport(self.f.project, self.f.old_cont, cont,
                    c.cp_rows(self.f.old_cp), set(self.f.baseline), kit=self.f.kit)

    def test_no_inherited_original_may_be_reintroduced_as_git_leaf(self):
        for item in [self.f.transport] + self.f.transports26['descriptors']:
            leaves = set(self.f.baseline) | {item['restored_artifact']['path']}
            with self.subTest(path=item['restored_artifact']['path']), self.assertRaises(ValueError):
                c.check_transport(self.f.project, self.f.old_cont, self.f.source_cont,
                    c.cp_rows(self.f.old_cp), leaves, kit=self.f.kit)

    def test_tampered_tuple_map_even_with_matching_kit_refused(self):
        index = c.parse(self.f.root/'source-filemap.json')
        row = next(row for row in index['files'] if row['path'].endswith('bootstrap.py'))
        put(self.f.kit/row['path'], b'changed baseline\n')
        row.update(s.leaf(row['path'], c.content(self.f.kit/row['path'])))
        with self.assertRaises(ValueError): s.verify_baseline(self.f.kit, index)

    def test_missing_raw_counters_remain_unknown(self):
        outer = {'worker_attempts_reserved': 1, 'verified_worker_starts': 0,
            'owned_live_processes_closed': True, 'CPU_affinity': [0, 1],
            'wall_seconds_including_init_cleanup': 1, 'raw_bytes': None, 'raw_sha256': None}
        actual = {k: outer[k] for k in ('verified_worker_starts', 'owned_live_processes_closed',
            'CPU_affinity', 'wall_seconds_including_init_cleanup')}
        actual.update(worker_attempts=1, errors=0, counter_observation_scope='NO_RAW_COUNTER_RECEIPT')
        self.assertFalse(s.check_actual(actual, None, outer, False))
        actual['NLI_forward_pairs_attempted'] = 0
        with self.assertRaises(ValueError): s.check_actual(actual, None, outer, False)

    def test_frozen_dev_selection_and_submission_flags_refused(self):
        for change in ('document', 'submission'):
            plan = copy.deepcopy(self.f.plan)
            if change == 'document': plan['data_roles']['dev'][0] = 610
            else: plan['new_submission_allowed'] = True
            put(self.f.project/s.FROZEN_REFS['plan'], plan)
            frozen = {k: c.ref(self.f.project, p) for k, p in s.FROZEN_REFS.items()}
            cont = dict(self.f.source_cont, epoch27_frozen_study=frozen)
            with self.subTest(change=change), self.assertRaises(ValueError):
                s.checked_plan(self.f.project, cont, c.cp_rows(self.f.cp()), self.f.current(), 'source')

    def test_results_cannot_promote_or_rebind_execution(self):
        self.source(); manifest = self.f.final_files()
        original = c.parse(self.f.project/(s.E+'RESULTS.json'))
        for field, value in [('benchmark_accepted', True), ('execution', None),
                ('diagnostic_qualified', 1)]:
            result = dict(original); result[field] = value
            put(self.f.project/(s.E+'RESULTS.json'), result)
            changed = copy.deepcopy(manifest)
            changed['results'] = c.ref(self.f.project, s.E+'RESULTS.json')
            with self.subTest(field=field), self.assertRaises(ValueError):
                s.checked_final(self.f.project, changed, c.cp_rows(self.f.cp()),
                    c.parse(self.f.root/'controls-final/CONTINUATION.json'), self.f.old_cont,
                    'a'*40, self.f.plan, self.f.frozen)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Guards)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'schema_version': 1, 'epoch': 27, 'kind': 'SYNTHETIC_PUBLICATION_GUARDS_ONLY',
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'checks_passed': result.wasSuccessful(), 'synthetic_fixtures_only': True,
        'Git_network_mail_model_native_benchmark_calls': 0,
        'cases': [case._testMethodName for case in unittest.defaultTestLoader.loadTestsFromTestCase(Guards)]}
    put(HERE/'guard-tests.v1.json', report)
    raise SystemExit(0 if result.wasSuccessful() else 1)
