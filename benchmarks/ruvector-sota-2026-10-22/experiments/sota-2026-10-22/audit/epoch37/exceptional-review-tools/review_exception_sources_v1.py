"""Independent E37 exceptional-source review using only disjoint pure fixtures."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace

R = Path('/tmp/ruvector-sota-2026-10-22/epoch37-b4e9e4f7a8a4/project')
SRC = Path('/workspace/ruvector-e37-publication-impl/exceptional/project')
OUT = Path('/workspace/ruvector-e37-acceptance-audit')
P = 'experiments/sota-2026-10-22/'
E = P + 'epoch37/'
X = E + 'exceptional/'
NAMES = ('blocked_checkpoint_v1.py', 'PROTOCOL.v1.json', 'publish_blocked_v1.js', 'test_blocked_checkpoint_v1.py')

def raw(path):
    assert path.is_file() and not any(p.is_symlink() for p in (path, *path.parents))
    return path.read_bytes()

def ref(base, rel):
    body = raw(base / rel)
    return {'path': rel, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

def main():
    rows = [ref(SRC, X + name) for name in NAMES]
    ready_path = SRC.parent / 'READY.v1.json'
    ready_body = raw(ready_path)
    assert len(ready_body) == 1630 and hashlib.sha256(ready_body).hexdigest() == '976fb690c7e4c49346d07ab6cbf42fe12f64c9d9b822eaee48baa8331748520b'
    ready = json.loads(ready_body)
    assert sorted(ready['canonical_sources'], key=lambda x: x['path']) == sorted(rows, key=lambda x: x['path'])
    parsed = [ast.parse(raw(SRC / (X + name))) for name in (NAMES[0], NAMES[3])]
    for i, tree in enumerate(parsed):
        denied_imports = {'torch', 'transformers', 'requests', 'http', 'socket'} | ({'subprocess'} if i == 0 else set())
        assert not any(isinstance(n, ast.Import) and any(a.name.split('.')[0] in denied_imports for a in n.names) for n in ast.walk(tree))
        denied_calls = {'eval', 'exec', 'os.system', 'subprocess.Popen'} | ({'subprocess.run'} if i == 0 else set())
        assert not any(isinstance(n, ast.Call) and ast.unparse(n.func) in denied_calls for n in ast.walk(tree))
    h = SimpleNamespace(**runpy.run_path(str(SRC / (X + NAMES[0])), run_name='independent_pure_source_import'))
    c = SimpleNamespace(**runpy.run_path(str(R / (E + 'publication/publication_common_v1.py')), run_name='independent_frozen_pure_scanner_import'))
    replay_path = P + 'audit/epoch37/qualification-replay.json'
    replay = json.loads(raw(R / replay_path))
    supplement = json.loads(raw(R / h.SUPPLEMENT_REF['path']))
    assert ref(R, replay_path) == h.FROZEN['frozen_evaluation']
    assert ref(R, h.SUPPLEMENT_REF['path']) == h.SUPPLEMENT_REF
    assert h.SOURCE == 'a93a1d6922c8a14f356461fb383846157816c70b'
    tests = []
    def passes(name, action):
        action()
        tests.append({'name': name, 'passed': True})
    def refuses(name, action):
        try:
            action()
        except (ValueError, AssertionError, KeyError):
            tests.append({'name': name, 'passed': True})
        else:
            raise AssertionError('Expected refusal: ' + name)
    passes('actual_frozen_replay_rejection_accepted_as_rejected', lambda: h.validate_replay(copy.deepcopy(replay)))
    passes('actual_pinned_supplement_schema_and_prePopen_scope', lambda: h.validate_supplement(copy.deepcopy(supplement)))
    for key, value in [('checks_passed', True), ('actual_NLI_forwards', 0), ('engineering_metrics', {}), ('champion_promoted', True), ('used_confirmation_identities', ['synthetic'])]:
        bad = copy.deepcopy(replay); bad[key] = value
        refuses('reject_replay_mutation_' + key, lambda bad=bad: h.validate_replay(bad))
    for key, value in [('retained_frozen_observer_physical_closure_passed', True), ('retained_frozen_observer_unknown_physical_ownership', False), ('internal_operation_counts', 0), ('frozen_evaluation_checks_passed', True)]:
        bad = copy.deepcopy(supplement); bad[key] = value
        refuses('reject_supplement_mutation_' + key, lambda bad=bad: h.validate_supplement(bad))
    for key, value in [('observed_fd_entries', []), ('supervisor_state', 'S')]:
        bad = copy.deepcopy(supplement); bad['physical_kernel_observation'][key] = value
        refuses('reject_kernel_capture_reinterpretation_' + key, lambda bad=bad: h.validate_supplement(bad))
    bad = copy.deepcopy(supplement); bad['source_failure_boundary']['worker_Popen_line'] = 211
    refuses('reject_substituted_source_boundary', lambda: h.validate_supplement(bad))
    args = [dict(path='synthetic', bytes=0, sha256='0' * 64)] * 4
    info = h.metadata(*args)
    assert info['actual_NLI_forwards'] is info['model_initializations'] is info['corpus_batches_attempted'] is None
    assert info['frozen_physical_closure_passed'] is False and info['frozen_unknown_physical_ownership'] is True
    assert info['remaining_slots'] and all(type(v) is int and v == 0 for v in info['remaining_slots'].values())
    result = h.add_results(replay, info)
    assert set(result) == set(replay) | {'exceptional_blocked_checkpoint'}
    assert all(result[k] == v for k, v in replay.items())
    result['evidence']['raw'] = {'synthetic': True}
    assert replay['evidence']['raw'] is None
    tests.append({'name': 'append_only_metadata_deepcopy_preserves_every_original_field', 'passed': True})
    refuses('reject_duplicate_exceptional_addition', lambda: h.add_results(h.add_results(replay, info), info))
    future = Path('/workspace/ruvector-e37-engineering-impl/future-asset-identity-fix')
    patch_paths = list(future.rglob('FUTURE_ONLY_SOURCE_INTEGRATION.patch'))
    assert len(patch_paths) == 1
    patch = raw(patch_paths[0])
    assert len(patch) == h.PATCH_REF['bytes'] and hashlib.sha256(patch).hexdigest() == h.PATCH_REF['sha256']
    passes('allow_only_exact_future_patch_with_full_frozen_public_text_scan', lambda: h.public_metadata_text(c, h.PATCH_REF['path'], patch))
    refuses('reject_changed_exact_path_patch', lambda: h.public_metadata_text(c, h.PATCH_REF['path'], patch + b'\n'))
    refuses('reject_other_patch_name_with_same_bytes', lambda: h.public_metadata_text(c, E + 'exceptional/other.patch', patch))
    refuses('ordinary_metadata_still_rejects_binary', lambda: h.public_metadata_text(c, E + 'exceptional/fixture.txt', b'bad\0binary'))
    with tempfile.TemporaryDirectory(prefix='exceptional-fixtures-', dir=OUT) as work:
        synthetic = Path(work)
        target = synthetic / h.PATCH_REF['path']; target.parent.mkdir(parents=True); target.write_bytes(patch)
        assert h.collect_current(synthetic, c) == {h.PATCH_REF['path']: patch}
        tests.append({'name': 'new_collector_preserves_exact_patch_filename_and_bytes', 'passed': True})
        target.write_bytes(patch + b'\n')
        refuses('collector_rejects_changed_patch', lambda: h.collect_current(synthetic, c))
        for name, body in [('duplicate.json', b'{"same":0,"same":1}'), ('nonfinite.json', b'{"value":NaN}')]:
            file = synthetic / name; file.write_bytes(body)
            refuses('strict_parser_' + name, lambda file=file: h.parse(file))
    protocol = json.loads(raw(SRC / (X + NAMES[1])))
    assert protocol['status'] == h.STATUS and protocol['source_commit'] == h.SOURCE
    assert protocol['frozen'] == h.FROZEN and protocol['remaining_slots'] == h.REMAINING
    publisher = raw(SRC / (X + NAMES[2])).decode()
    for snippet in ('expected_sha: meta.publication_parent', 'force: false', 'return await mutate(id, tool, args)', 'main is prohibited in mutation arguments', 'verified_actual_full_tree: true', 'a93a1d6922c8a14f356461fb383846157816c70b', 'stage-blocked'):
        assert snippet in publisher
    assert 'await publishBlocked(' not in publisher
    helper_text = raw(SRC / (X + NAMES[0])).decode()
    assert "sv['evidence'].get('supervisor_stderr')" in helper_text
    assert 'EXCEPTION_ONLY_METADATA_IDENTITY' in helper_text
    assert 'c.walk_current(' not in helper_text and 'p.transport_groups(' not in helper_text
    assert 'scorer_BIND' not in [ast.unparse(n.func) for n in ast.walk(parsed[0]) if isinstance(n, ast.Call)]
    assert [ref(SRC, X + name) for name in NAMES] == rows, 'Source changed during independent review'
    supplemental = OUT / 'SUPPLEMENT_CONSISTENCY_REVIEW_v1.json'
    body = supplemental.read_bytes()
    report = {
        'schema_version': 1, 'epoch': 37, 'kind': h.KIND,
        'status': 'APPROVED_EXCEPTION_ONLY_BLOCKED_CHECKPOINT_SOURCE',
        'checks_passed': True, 'exceptional_source_only': True, 'scientific_authorization': 0,
        'files': rows,
        'owner_final_source_ready': {'path': str(ready_path), 'bytes': len(ready_body), 'sha256': hashlib.sha256(ready_body).hexdigest()},
        'frozen_pure_publication_dependencies': [ref(R, E + 'publication/' + name) for name in
            ('publication_common_v1.py', 'phase_schema_v1.py', 'phase_receipts_v1.py', 'stage_publication_v1.py')],
        'reviewed_outer_publication_controller_sources': [
            {'path': str(R.parent / name), 'bytes': len(raw(R.parent / name)),
             'sha256': hashlib.sha256(raw(R.parent / name)).hexdigest()}
            for name in ('controller.js', 'mutation_guard.py')],
        'supplement_consistency_review': {'path': str(supplemental), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()},
        'reviewed_source_parent': h.SOURCE, 'reviewed_source_trees': h.TREES,
        'pure_fixture_count': len(tests), 'pure_fixtures': tests,
        'frozen_evaluation_checks_passed': False, 'frozen_physical_closure_passed': False,
        'frozen_unknown_physical_ownership': True,
        'internal_operation_counts': 'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT',
        'actual_model_tokenizer_native_scorer_EVALUATE_BIND_Git_or_external_calls': 0,
        'actual12_case_or_oracle_content_files_opened': 0, 'new_host_or_proc_probes': 0,
        'review_findings': [
            'Frozen source/runtime/scorer/observer/replay are rehashed and never overwritten. The exceptional result deep-copies all original failed replay fields and adds one explicitly separate blocked-checkpoint metadata object.',
            'Logical dispatch burn1 and verified outer launcher1 are separated from absent captured worker/native/model/internal counters, which remain UNKNOWN/null. Known prior corpus counts33/31 are lower bounds, not new empirical E37 counts.',
            'Exceptional supplement binds exact source/trace/kernel capture and preserves frozen false closure/unknown ownership and false scientific integrity. EACCES file-descriptor enumeration stays null; no exit status or universal process absence is invented.',
            'Separate exception-only metadata comparison and independent publication acceptance replace frozen scorer BIND. No further scorer or scientific execution is authorized.',
            'Future repair remains inert source-only evidence. The sole additional text extension is exact path/4707B/f6daac patch; unchanged full frozen public-text scan applies under .txt validation, with no monkeypatch or broad suffix allowlist.',
            'New manifests seal all current public metadata nonrecursively; controls and stage revalidate the exact sealed file map. Previously published SOURCE/checkpoint bytes and all historical non-control Git tuples must remain exact.',
            'Publication is restricted to the dedicated scoped branch and exact a93 source-parent CAS with forcefalse. Mutation calls delegate to the owned durable write-ahead controller; main is read-only, immutable sibling/full-leaf readbacks precede ref update, and no retry loop or guardian release is implemented in the publisher.'
        ],
        'remaining_requirements': [
            'Root must copy these exact four reviewed source files and this review; root must preserve frozen source/ref history and exact future-only copy/review pins.',
            'After actual metadata RESULTS/ledger/used-identity creation, an independent identity comparator must verify every frozen replay field unchanged and preserve all scientific rejection/null/UNKNOWN fields.',
            'Independent final exception acceptance and exact stage/transport/tree review are required before root publishes. This source approval is not an actual publication/readback receipt.',
            'Actual dedicated-branch CAS/full tuple readback and only then guardian release remain root responsibilities. A different source parent or changed reviewed bytes requires stopping.'
        ],
        'reviewer_source': {'path': str(Path(__file__)), 'bytes': Path(__file__).stat().st_size,
                            'sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    }
    target = OUT / 'EXCEPTION_SOURCE_APPROVAL_v1.json'
    with target.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({'path': str(target), 'bytes': target.stat().st_size,
                      'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))

if __name__ == '__main__':
    main()
