"""Small author-only guard fixtures; never stage the actual project or run NLI.

These cover the prior publication failures: dropping a Git leaf, changing a
checkpoint identity, weakening the one archive exception, and escaped payloads
exceeding transport bounds despite smaller source files.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import copy
import json
from pathlib import Path
import tempfile
import unittest
import publication_common_v1 as c
import stage_publication_v1 as s
import validate_ref_guard_v1 as g


def record(path, data):
    return {'path': path, 'bytes': len(data), 'sha256': c.sha(data)}


def plan(cap=20):
    return {'epoch': 24, 'kind': 'SOURCE_SCOPE_ENGINEERING',
            'expected_actual_native_queries': cap,
            'limits': {'worker_attempts': 1, 'cpu_threads': 2, 'seconds_per_batch': 600}}


def checked_final(manifest, cap=20):
    return c.check_final_manifest(manifest, plan(cap))


def final_manifest():
    return {'epoch': 24, 'kind': 'SOURCE_SCOPE_ENGINEERING', 'all_slots_closed': True,
        'champion_promoted': False, 'new_submission': False, 'benchmark_accepted': False,
        'engineering_qualified': True,
        'actual_execution': {'worker_attempts': 1, 'verified_worker_starts': 1,
            'BGE_initializations': 1, 'BGE_forwards': 17, 'BGE_texts': 69,
            'native_index_initializations': 17, 'native_searches_completed': 17,
            'native_engineering_batches': 1, 'errors': 0,
            'owned_live_processes_closed': True, 'CPU_affinity': [0, 1],
            'wall_seconds_including_init_cleanup': 12.5,
            'NLI_model_initializations': 0, 'NLI_forward_pairs_attempted': 0,
            'NLI_forward_pairs_completed': 0, 'benchmark_corpora': 0,
            'benchmark_questions': 0, 'benchmark_HTTP_requests': 0,
            'TRAIN_calibration_fits': 0, 'CONF_worker_attempts': 0,
            'CONF_annotation_choices': 0, 'CONF_NLI_pairs': 0,
            'paid_API_calls': 0, 'GPU_calls': 0, 'NLI_forwards': 0,
            'fits': 0, 'paid_calls': 0, 'Python_network_operations_attempted': 0,
            'confirmation_calls': 0},
        'data_roles': {'train': [], 'dev': [], 'calibration': [], 'confirmation': []}}


class PublicationGuards(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='epoch24-publication-fixtures-')
        self.root = Path(self.work.name)

    def tearDown(self):
        self.work.cleanup()

    def rejected(self, fn, *args):
        with self.assertRaises((ValueError, UnicodeDecodeError)):
            fn(*args)

    def test_review_is_exact_set_and_byte_identity(self):
        current = {c.P + 'epoch24/a.json': b'{}'}
        row = record(next(iter(current)), b'{}')
        s.checked_review({'files': [row]}, current)
        self.rejected(s.checked_review, {'files': []}, current)
        self.rejected(s.checked_review, {'files': [row, row]}, current)
        wrong = dict(row, sha256='0' * 64)
        self.rejected(s.checked_review, {'files': [wrong]}, current)
        self.rejected(s.checked_review, {'files': [row, record('extra.json', b'x')]}, current)

    def test_published_leaf_cannot_disappear_or_change(self):
        baseline = {n: s.leaf(n, b'old') for n in [*c.CONTROLS, 'history.txt']}
        prior = copy.deepcopy(baseline)
        prior[c.P + 'epoch24/source.py'] = s.leaf(c.P + 'epoch24/source.py', b'source')
        expected = copy.deepcopy(prior)
        s.verify_prior(prior, baseline, expected)
        del expected['history.txt']
        self.rejected(s.verify_prior, prior, baseline, expected)
        expected = copy.deepcopy(prior)
        expected[c.P + 'epoch24/source.py']['sha'] = '0' * 40
        self.rejected(s.verify_prior, prior, baseline, expected)
        prior = copy.deepcopy(baseline); del prior['history.txt']
        self.rejected(s.verify_prior, prior, baseline, expected)

    def test_expected_map_key_and_scope_normalization(self):
        rows = {n: s.leaf(n, b'x') for n in c.CONTROLS}
        self.assertEqual(s.tuple_map(rows), rows)
        prefixed = [dict(r, path=c.SCOPE + p) for p, r in rows.items()]
        self.assertEqual(s.tuple_map({'scope': c.SCOPE, 'files': prefixed}), rows)
        self.rejected(s.tuple_map, {'scope': 'other/', 'files': prefixed})
        self.rejected(s.tuple_map, dict(rows, bad=next(iter(rows.values()))))
        self.rejected(s.tuple_map, {'files': prefixed + prefixed})

    def test_checkpoint_hash_size_and_duplicate_guards(self):
        data = b'prior immutable evidence\n'; (self.root / 'history.txt').write_bytes(data)
        row = record('history.txt', data); cp = {'project_files': [row]}
        self.assertEqual(c.check_history(self.root, cp), {'history.txt': row})
        self.rejected(c.cp_rows, {'project_files': [row, row]})
        self.rejected(c.cp_rows, {'project_files': [dict(row, bytes=True)]})
        (self.root / 'history.txt').write_bytes(b'changed')
        self.rejected(c.check_history, self.root, cp)

    def test_archive_exception_is_inherited_exact_and_cp_only(self):
        rows = {}; transport = {'format': 'gzip+base64', 'required_before_bootstrap': True}
        for key in ('archive', 'extractor', 'publication_helper', 'restored_artifact'):
            name = key + '.json'; data = (key + '\n').encode(); (self.root / name).write_bytes(data)
            rows[name] = record(name, data); transport[key] = rows[name]
        transport['standalone_Git_leaf_omitted'] = transport['restored_artifact']['path']
        old = {'artifact_transport': transport}; new = copy.deepcopy(old)
        git_paths = {transport[k]['path'] for k in ('archive', 'extractor', 'publication_helper')}
        c.check_transport(self.root, old, new, rows, git_paths)
        self.rejected(c.check_transport, self.root, old, new, rows,
                      git_paths | {transport['restored_artifact']['path']})
        changed = copy.deepcopy(new); changed['artifact_transport']['extra'] = True
        self.rejected(c.check_transport, self.root, old, changed, rows)
        broken = copy.deepcopy(rows); del broken[transport['archive']['path']]
        self.rejected(c.check_transport, self.root, old, new, broken)

    def test_payload_sizing_uses_utf8_and_serialized_bytes(self):
        blobs, groups = s.transport_groups({'a.txt': b'x' * 80000, 'b.txt': b'x' * 80001})
        self.assertEqual([x[0] for x in blobs], ['b.txt'])
        self.assertTrue(all(len(c.encoded({'tree_elements': g})) < s.MAX_TREE_JSON for g in groups))
        blobs, _ = s.transport_groups({'unicode.txt': ('\U0001f642' * 20001).encode()})
        self.assertEqual(len(blobs), 1)
        self.assertEqual(blobs[0][1].decode(), '\U0001f642' * 20001)
        self.rejected(s.transport_groups, {'escaped.txt': b'"' * 4200000})

    def test_source_privacy_binary_and_symlink_refusal(self):
        self.rejected(c.public_text, 'page.txt', b'<' + b'html>not publishable</html>')
        self.rejected(c.public_text, 'mail.txt', b'Received: private mail header\n')
        self.rejected(c.public_text, 'binary.json', b'\xff')
        self.rejected(c.public_text, 'binary.json', b'\0')
        self.rejected(c.public_text, 'assets/weights.json', b'{}')
        self.rejected(c.public_text, '.env/token.txt', b'value')
        (self.root / 'real').write_text('x'); (self.root / 'alias').symlink_to(self.root / 'real')
        self.rejected(c.content, self.root / 'alias')
        for bad in ('../escape', '/absolute', 'a/../b', 'a//b', 'a\\b'):
            self.rejected(c.relative, bad)

    def test_publication_sources_pass_their_own_public_text_policy(self):
        directory = Path(__file__).parent
        for name in ('publication_common_v1.py',
                     'stage_publication_v1.py', 'test_publication_guards_v1.py', 'validate_ref_guard_v1.py',
                     'test_integrated_publication_v2.py'):
            c.public_text(c.P + 'epoch24/publication/' + name,
                          (directory / name).read_bytes())

    def test_final_scope_cannot_consume_roles_or_promote(self):
        m = final_manifest()
        self.assertEqual(checked_final(m), 1)
        for key in ('champion_promoted', 'new_submission', 'benchmark_accepted'):
            bad = copy.deepcopy(m); bad[key] = True; self.rejected(checked_final, bad)
        for key in ('worker_attempts', 'CONF_pairs', 'NLI_pairs', 'paid_API_calls', 'GPU_calls'):
            bad = copy.deepcopy(m); bad['actual_execution'][key] = 2
            self.rejected(checked_final, bad)
        bad = copy.deepcopy(m); bad['data_roles']['confirmation'] = ['not a fresh gate']
        self.rejected(checked_final, bad)

    def test_final_explicit_counters_allow_embedding_but_forbid_missing_zeros(self):
        m = final_manifest(); self.assertEqual(len(c.ZERO_COUNTERS), 17)
        self.assertEqual(checked_final(m, 17), 1)
        self.rejected(checked_final, m, 16)
        for key in c.ZERO_COUNTERS:
            missing = copy.deepcopy(m); del missing['actual_execution'][key]
            self.rejected(checked_final, missing)
            nonzero = copy.deepcopy(m); nonzero['actual_execution'][key] = 1
            self.rejected(checked_final, nonzero)
        for key in ('BGE_forwards', 'native_searches_completed', 'CPU_affinity',
                    'wall_seconds_including_init_cleanup'):
            missing = copy.deepcopy(m); del missing['actual_execution'][key]
            self.rejected(checked_final, missing)
        bad = copy.deepcopy(m); bad['actual_execution']['wall_seconds_including_init_cleanup'] = 601
        self.rejected(checked_final, bad)
        bad = copy.deepcopy(m); bad['actual_execution']['TRAIN_extra_fits'] = 1
        self.rejected(checked_final, bad)
        failed = copy.deepcopy(m); failed['engineering_qualified'] = False
        failed['actual_execution'].update({key: 0 for key in c.COUNT_COUNTERS})
        self.assertEqual(checked_final(failed), 0)

    def test_final_current_allowances_close_without_rewriting_history(self):
        old = {'epoch22_closed_study': {'used': 1}, 'historical_unspent_slots': 1,
               'closed_epoch7_study': {'used': 1, 'cap': 2, 'unspent_slots': 1,
                                       'allowed_further': 0},
               'source_only_epoch14': {'native_attempts': 0},
               'cumulative_corpus_attempts_current': 22,
               'cumulative_qualification_attempts': 1,
               'cumulative_native_process_attempts_including_qualification': 23}
        updates = {key: 0 for key in c.FINAL_ZERO_ALLOWANCES}
        updates.update(current_epoch_closed=True, scope='ALL_EPOCHS_CLOSED_THROUGH24',
            epoch24_closed_qualification={'used': 1, 'cap': 1, 'allowed_further': 0,
                                           'benchmark_corpora': 0},
            cumulative_qualification_attempts=2,
            cumulative_native_process_attempts_including_qualification=24)
        m = final_manifest(); m['cumulative_budget_ledger'] = updates
        result = c.final_ledger(old, m, self.root)
        self.assertEqual(result['historical_unspent_slots'], 1)
        self.assertEqual(result['cumulative_corpus_attempts_current'], 22)
        for key in c.FINAL_ZERO_ALLOWANCES:
            bad = copy.deepcopy(m); bad['cumulative_budget_ledger'][key] = 1
            self.rejected(c.final_ledger, old, bad, self.root)
            bad = copy.deepcopy(m); del bad['cumulative_budget_ledger'][key]
            self.rejected(c.final_ledger, old, bad, self.root)
        for key, value in [('used', 2), ('cap', 2), ('allowed_further', 1), ('benchmark_corpora', 1)]:
            bad = copy.deepcopy(m); bad['cumulative_budget_ledger']['epoch24_closed_qualification'][key] = value
            self.rejected(c.final_ledger, old, bad, self.root)
        bad = copy.deepcopy(m); bad['cumulative_budget_ledger']['current_epoch_closed'] = False
        self.rejected(c.final_ledger, old, bad, self.root)
        bad = copy.deepcopy(m); bad['cumulative_budget_ledger']['epoch22_closed_study'] = {'used': 9}
        self.rejected(c.final_ledger, old, bad, self.root)
        for key in ('closed_epoch7_study', 'source_only_epoch14'):
            bad = copy.deepcopy(m); bad['cumulative_budget_ledger'][key] = {'rewritten': True}
            self.rejected(c.final_ledger, old, bad, self.root)
        for key in ('cumulative_corpus_attempts_current', 'cumulative_qualification_attempts',
                    'cumulative_native_process_attempts_including_qualification'):
            bad = copy.deepcopy(m); bad['cumulative_budget_ledger'][key] = 99
            self.rejected(c.final_ledger, old, bad, self.root)

    def test_rejection_history_cannot_be_rewritten(self):
        old = {'rejections': [{'epoch': 22, 'status': 'rejected'}],
               'preparation_blocks': ['known blocker'], 'epoch22_decision': {'accepted': False},
               'next_research_priority': 'old', 'used_identity_manifest': {'path': 'old'}}
        new = copy.deepcopy(old); new['rejections'].append({'epoch': 24, 'scope': 'engineering'})
        new['next_research_priority'] = 'new'; new['used_identity_manifest'] = {'path': 'new'}
        c.check_ledger_history(old, new)
        new['rejections'][0]['status'] = 'accepted'
        self.rejected(c.check_ledger_history, old, new)
        new = copy.deepcopy(old); del new['epoch22_decision']
        self.rejected(c.check_ledger_history, old, new)

    def test_output_cannot_overwrite_or_enter_inputs(self):
        project = self.root / 'project'; project.mkdir()
        self.rejected(c.new_output, project / 'out', (project,))
        occupied = self.root / 'occupied'; occupied.mkdir()
        self.rejected(c.new_output, occupied, (project,))
        self.assertEqual(c.new_output(self.root / 'outside', (project,)), self.root / 'outside')

    def test_pinned_inherited_count_and_new_namespace(self):
        rows = [record('history/' + str(i) + '.json', b'{}') for i in range(c.OLD_CP_ROWS)]
        self.assertEqual(len(c.check_inherited_checkpoint({'project_files': rows})), c.OLD_CP_ROWS)
        self.rejected(c.check_inherited_checkpoint, {'project_files': rows[:-1]})
        changed = copy.deepcopy(rows)
        changed[0]['path'] = c.P + 'epoch24/preexisting.json'
        self.rejected(c.check_inherited_checkpoint, {'project_files': changed})

    def test_checkpoint_metadata_cannot_be_dropped_or_rewritten(self):
        old = {'schema_version':1, 'old_nullable_metadata':None,
               'epoch23_owner_recovery':{'generation':2},
               'project_files':[record('history.json',b'old')]}
        current={c.P+'epoch24/new.json':b'{}'}
        new=copy.deepcopy(old);new['project_files'].append(record(next(iter(current)),b'{}'))
        new['epoch24_prelaunch']={'source_checkpoint':c.BASE_COMMIT}
        s.checkpoint_extension(old,new,current)
        for key in ('old_nullable_metadata','epoch23_owner_recovery'):
            bad=copy.deepcopy(new);del bad[key]
            self.rejected(s.checkpoint_extension,old,bad,current)
        bad=copy.deepcopy(new);bad['epoch23_owner_recovery']['generation']=3
        self.rejected(s.checkpoint_extension,old,bad,current)
        bad=copy.deepcopy(new);bad['unrelated_new_metadata']=True
        self.rejected(s.checkpoint_extension,old,bad,current)

    def test_observed_execution_has_no_imputed_zero_or_result_expectation(self):
        actual = final_manifest()['actual_execution']
        receipt = {'actual_execution': actual}
        self.assertEqual(c.observed_execution(receipt), actual)
        missing = copy.deepcopy(receipt); del missing['actual_execution']['NLI_forwards']
        self.rejected(c.observed_execution, missing)
        failed = final_manifest(); failed['engineering_qualified'] = False
        failed['actual_execution']['native_searches_completed'] = 3
        self.assertEqual(checked_final(failed, 100), 1)
        # A cap is not a claimed outcome; lower actual counts are not replaced.
        self.assertEqual(c.observed_execution({'actual_execution': failed['actual_execution']})
                         ['native_searches_completed'], 3)

    def test_cumulative_observed_history_preserved_with_actual_increment_only(self):
        old = {'actual_HTTP_decisions': 885, 'epoch23_note': 'inherited',
               'native_qualification_attempts': 2,
               'cumulative_bounded_native_process_attempts_including_qualification': 24}
        new = dict(old, native_qualification_attempts=3,
                   cumulative_bounded_native_process_attempts_including_qualification=25,
                   epoch24_bounded_worker_attempts=1)
        c.check_execution_history(old, new, {'worker_attempts':1})
        bad = dict(new, actual_HTTP_decisions=886)
        self.rejected(c.check_execution_history, old, bad, {'worker_attempts':1})
        self.rejected(c.check_execution_history, old, new, {'worker_attempts':0})

    def test_main_siblings_and_parent_cas(self):
        row = lambda path, value, kind='tree': {'path':path,'mode':'040000' if kind=='tree'
                       else '100644','type':kind,'sha':value*40}
        base = {'repository':g.REPOSITORY,'branch':g.BRANCH,'main_sha':'1'*40,
                'branch_sha':'2'*40,
                'root_tree':{'sha':'3'*40,'truncated':False,
                             'tree':[row('benchmarks','4'),row('README.md','5','blob')]},
                'benchmarks_tree':{'sha':'4'*40,'truncated':False,
                             'tree':[row('ruvector-sota-2026-10-22','6'),row('sibling','7')]}}
        observed = copy.deepcopy(base)
        self.assertTrue(g.verify(base, observed, '2'*40)['checks_passed'])
        for field in ('main_sha','branch_sha'):
            bad = copy.deepcopy(observed);bad[field]='8'*40
            self.rejected(g.verify, base, bad, '2'*40)
        bad = copy.deepcopy(observed);bad['benchmarks_tree']['tree'][1]['sha']='8'*40
        self.rejected(g.verify, base, bad, '2'*40)
        bad = copy.deepcopy(observed);bad['root_tree']['truncated']=True
        self.rejected(g.verify, base, bad, '2'*40)
        intent = g.cas_intent('2'*40,'9'*40,'1'*40)
        self.assertFalse(intent['force']);self.assertEqual(intent['expected_sha'],'2'*40)


if __name__ == '__main__':
    unittest.main()
