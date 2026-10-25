"""Read-only E37 source/retained-evidence review; no runtime or scorer imports."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path('/tmp/ruvector-sota-2026-10-22/epoch37-b4e9e4f7a8a4/project')
OUT = Path('/workspace/ruvector-e37-acceptance-audit')
P = 'experiments/sota-2026-10-22/'
E = P + 'epoch37/'
A = P + 'audit/epoch37/'
SOURCE = 'a93a1d6922c8a14f356461fb383846157816c70b'

def data(path):
    p = Path(path)
    assert p.is_file() and not any(q.is_symlink() for q in (p, *p.parents))
    return p.read_bytes()

def ref(rel):
    b = data(ROOT / rel)
    return {'path': rel, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}

def read(rel):
    return json.loads(data(ROOT / rel))

def check(row):
    assert set(row) == {'path', 'bytes', 'sha256'}
    assert ref(row['path']) == row

def call_name(call):
    return ast.unparse(call.func)

def main():
    srel = A + 'exceptional-preworker-resolution-independent-v1.json'
    drel = A + 'actual-LFS-identity-failure-independent-v1.json'
    assert ref(srel)['sha256'] == 'd8164d037fe1cbdaebd17bc649dd6409625e12edb799d6ac86a8ec9238925db8'
    assert ref(drel)['sha256'] == 'd7e2277a0ff851118d7ad96491194918df3b7b78efcee34586e6d50b249e9f5a'
    supplement, diagnosis = read(srel), read(drel)
    for row in supplement['evidence'].values():
        check(row)
    assert supplement['published_source_commit'] == SOURCE
    observer = read(supplement['evidence']['frozen_observer']['path'])
    replay = read(supplement['evidence']['frozen_evaluation']['path'])
    assert observer['physical_supervisor_closed'] is True
    assert observer['physical_closure_passed'] is False
    assert observer['unknown_physical_ownership'] is True
    assert observer['physical_supervisor_absent'] is False
    assert observer['execution'] is observer['supervisor_completion'] is None
    assert replay['status'] == 'REJECTED_ENGINEERING_INTEGRITY'
    assert replay['checks_passed'] is replay['engineering_passed'] is False
    assert replay['actual_NLI_forwards'] is replay['final_derived_forecasts'] is None
    assert replay['evidence']['raw'] is replay['evidence']['execution'] is None
    assert replay['authored_oracle_traversals_by_scorer'] == 0
    assert replay['model_native_tokenizer_calls_by_scorer'] == 0
    assert replay['used_confirmation_identities'] == []
    launch_rel = supplement['evidence']['launch_source']['path']
    launch = ast.parse(data(ROOT / launch_rel))
    entry = next(n for n in launch.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    calls = [(call_name(n), n.lineno) for n in ast.walk(entry) if isinstance(n, ast.Call)]
    runtime_line = next(line for name, line in calls if name == 'C.verify_runtime')
    reserve_line = next(line for name, line in calls if name == 'reserve')
    popens = [line for name, line in calls if name == 'subprocess.Popen']
    assert popens == [263] and runtime_line == 212 and reserve_line == 220
    assert runtime_line < reserve_line < popens[0]
    runtime_stmt = next(n for n in entry.body if n.lineno == runtime_line)
    assert isinstance(runtime_stmt, ast.Expr)
    stderr = data(ROOT / supplement['evidence']['supervisor_stderr']['path']).decode()
    assert 'line 212, in main' in stderr and 'line 447, in verify_runtime' in stderr
    assert 'line 388, in verify_model_assets' in stderr
    assert stderr.endswith('ValueError: Original upstream Git blob differs\n')
    for path in supplement['source_failure_boundary']['known_missing_canonical_paths']:
        assert not (ROOT / path).exists()
    reservation = read(supplement['evidence']['dispatch_reservation']['path'])
    attempt = read(supplement['evidence']['dispatch_attempt']['path'])
    assert reservation['logical_native_budget_reserved'] == 1
    assert reservation['allowed_further_dispatches'] == 0
    assert attempt['verified_launcher_start'] is True and attempt['uncertain_launcher_start'] is False
    assert {k: attempt[k] for k in ('pid', 'startticks', 'pgid', 'sid')} == observer['supervisor_identity']
    driver = read(supplement['evidence']['driver_result']['path'])
    assert json.loads(driver['stdout'])['supervisor_exit_code_observed'] is False
    kernel = supplement['physical_kernel_observation']
    assert kernel['supervisor_state'] == 'Z' and kernel['supervisor_startticks'] == attempt['startticks']
    assert all(int(x) == 0 for x in kernel['statm_literal'].split())
    assert kernel['status_fields']['FDSize'] == '0'
    assert kernel['observed_fd_entries'] is None and kernel['fd_directory_observation'] == 'DENIED_EACCES'
    assert kernel['live_scoped_PGID_or_SID_members'] == []
    assert kernel['current_direct_children'] == []
    assert kernel['same_identity_before_and_after_scan'] is True
    assert supplement['internal_operation_counts'] == 'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT'
    assert supplement['retained_frozen_observer_physical_closure_passed'] is False
    assert supplement['retained_frozen_observer_unknown_physical_ownership'] is True
    assert supplement['frozen_evaluation_checks_passed'] is False
    expected_rel = diagnosis['exact_predecessor_expected_catalog']['path']
    check(diagnosis['exact_predecessor_expected_catalog'])
    old = {x['path']: x for x in read(expected_rel)['files']}
    current_rel = P + 'candidate/epoch37/MODEL_ASSETS.json'
    current = {x['path']: x for x in read(current_rel)['files']}
    pointer_checks = []
    for row in diagnosis['two_exact_original_LFS_pointers_reconstructed_without_network']:
        name = row['path']
        body = ('version https://git-lfs.github.com/spec/v1\n'
                f"oid sha256:{old[name]['upstream_sha256']}\nsize {old[name]['bytes']}\n").encode()
        blob = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
        assert body.decode() == row['canonical_LFS_pointer_text']
        assert blob == row['canonical_LFS_pointer_Git_SHA1'] == old[name]['upstream_git_blob_sha1']
        assert current[name]['sha256'] == old[name]['upstream_sha256']
        assert 'upstream_sha256' not in current[name]
        pointer_checks.append({'path': name, 'pointer_git_sha1_reconstructed': blob,
                               'payload_sha256_same_catalog': True, 'LFS_discriminator_missing_current': True})
    assert diagnosis['first_failing_actual_payload']['payload_Git_SHA1_equals_upstream_pointer_Git_SHA1'] is False
    result = {
        'schema_version': 1, 'epoch': 37, 'checks_passed': True,
        'status': 'SUPPLEMENT_CONSISTENT_WITH_PRESERVED_PREWORKER_INTEGRITY_REJECTION',
        'scientific_authorization': 0, 'exceptional_source_only': True,
        'source_commit': SOURCE, 'supplement': ref(srel), 'diagnosis': ref(drel),
        'evidence_rehashed': list(supplement['evidence'].values()),
        'model_catalogs_read_only_metadata': [ref(expected_rel), ref(current_rel)],
        'source_boundary': {'verify_runtime_line': runtime_line, 'reserve_line': reserve_line,
                            'sole_worker_Popen_line': popens[0], 'consistent_traceback': True,
                            'scope': 'Exact retained source/trace supports failure before this worker Popen; no captured worker-operation receipt exists.'},
        'captured_runtime_counts': None, 'captured_runtime_counts_status': 'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT',
        'logical_dispatch_slots_burned': 1, 'allowed_further_dispatches': 0,
        'frozen_evaluation_checks_passed': False, 'frozen_physical_closure_passed': False,
        'frozen_unknown_physical_ownership': True,
        'supplemental_kernel_capture_consistent': True,
        'direct_fd_entries': None, 'direct_fd_enumeration': 'DENIED_EACCES',
        'supervisor_absent': False, 'observed_launcher_exit_code': None,
        'independent_new_host_or_proc_probes': 0,
        'pointer_reconstruction_checks': pointer_checks,
        'accuracy': None, 'proper_scores': None, 'official_rank': None,
        'benchmark_accepted': False, 'champion_promoted': False, 'official_SOTA_verified': False,
        'limits': [
            'Audits retained source/trace/kernel captures and exact hashes; does not claim a new live kernel observation.',
            'Known-session scan alone cannot rule out arbitrary detached processes; scoped resolution depends on the exact pre-Popen source/trace boundary.',
            'Payload SHA256 validity and payload Git SHA1 in diagnosis were not recomputed by rereading model/tokenizer assets; no payload or large weight reread occurred.',
            'All167 plan source pins are preserved by frozen source review and evaluation; this review rehashes only the listed non-case evidence, never actual12 cases or oracle files.',
            'Separate metadata publication is permissible only through independently reviewed append-only helpers, parent CAS, durable write-ahead journal and actual readback; none are executed by this report.'
        ],
        'reviewer_source': {'path': str(Path(__file__)), 'bytes': len(data(__file__)),
                            'sha256': hashlib.sha256(data(__file__)).hexdigest()},
        'actual_model_tokenizer_native_scorer_EVALUATE_BIND_Git_or_external_calls': 0
    }
    target = OUT / 'SUPPLEMENT_CONSISTENCY_REVIEW_v1.json'
    with target.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'path': str(target), 'bytes': target.stat().st_size,
                      'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))

if __name__ == '__main__':
    main()
