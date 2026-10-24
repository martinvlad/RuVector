"""Separate read-only terminal FD-capacity attestation; no frozen source edits.

The original UNKNOWN proof stays immutable. The only supplemental observation
is an exact known terminal Z/X process whose FD-directory read is EACCES13,
whose seven statm fields are zero and whose kernel status reports FDSize0 and
Threads1. This proves the same zero-live-MM/FD criterion. Every other observation,
whole-group scan, source/ref validation and closure reduction uses frozen4f5.
No model/gold/raw prediction decoding, process start, signals, or exit-code claim.
"""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import types

OBS = 'experiments/sota-2026-10-22/audit/epoch31/observe_supervisor_closure.py'
OBSERVER_SHA = '4f5e295bbe0b2b6d978eb8d22edacf1aa9d6dddab6aab0c17f809c3dc678aab5'
SOURCE_COMMIT = '8d6f6a34d302cbfc1cd5904cc4d59939d4fb840e'
PLAN_SHA = 'b1f63e8f0df4558c2eb91c856f7d98451f76f738ab375a6158e95b4f973b7196'
FREEZE_SHA = '9970ec1e03bbd4fa4a67add78a1b18d1857d12903d3981081a9ae44ee1531b57'
BOUND = {
 'original_unknown': ('/tmp/ruvector-e31-observer-actual/SUPERVISOR_OBSERVED_CLOSURE.json', '8abe31de7d9d2204753b60bf1e963bd158137757ac464e290eb8d7a3e7e6380d'),
 'original_diagnostic': ('/tmp/ruvector-e31-observer-actual/exact-pid-failure-diagnostic.json', '250528f71b64eca16c5f95be169c4d5f798e4d18aef8c1504c0c4d32f9b274bd'),
 'independent_equivalence': ('/tmp/ruvector-e31-publication-audit/terminal-FDSize-zero-determination-independent-v1.json', '6ef6e0be6fee40645a7ee5d6737bc5087cb5a2ed0d15a30556d08ab6b5958e85'),
 'independent_method_decision': ('/tmp/ruvector-e31-independent-audit/fdsize-supplemental-method-decision.json', '5a33121ad6be17bf00f4b5e503570d14577730696147deb98d1b30b8928801d7')}
EXPECTED_SUPERVISOR = {'pid': 89769, 'startticks': 19640964, 'pgid': 89769, 'sid': 89769}
METHOD = 'EXACT_TERMINAL_ZX_STATM7_ZERO_FD_EACCES13_KERNEL_FDSIZE0_THREADS1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load_frozen(root):
    """Import only verified UTF-8 source bytes, bypassing unverified pyc caches."""
    path = root / OBS
    require(path.resolve(strict=True) == path and not path.is_symlink(), 'Observer path symlink')
    payload = path.read_bytes()
    require(len(payload) == 28330 and hashlib.sha256(payload).hexdigest() == OBSERVER_SHA,
            'Frozen observer hash changed')
    module = types.ModuleType('verified_frozen_epoch31_observer_4f5')
    module.__file__ = str(path)
    exec(compile(payload, str(path), 'exec'), module.__dict__)
    return module


def status_values(text):
    result = {}
    for line in text.splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            require(key not in result, 'Duplicate kernel status field')
            result[key] = value.strip()
    return result


def terminal_capacity(O, expected, before, after, statm, status, fd_errno, boot_before,
                      boot_after, namespace_before, namespace_after):
    """Pure narrow equivalence predicate; no /proc access in this reducer."""
    try:
        require(fd_errno == errno.EACCES and type(fd_errno) is int, 'Only EACCES13')
        require(boot_before == boot_after == O.BOOT and namespace_before == namespace_after == O.PIDNS,
                'Boot/namespace changed')
        require(before is not None and after is not None and O.same(before, after), 'Unstable process')
        require(O.identity_key(before) == O.identity_key(expected) and before['state'] in ('Z', 'X'),
                'Not exact known terminal identity')
        fields = statm.split()
        require(len(fields) == 7 and all(value == '0' for value in fields), 'Not exact zero statm7')
        values = status_values(status)
        require(values.get('FDSize') == '0' and values.get('Threads') == '1', 'FD capacity/threads not exact0/1')
        require(values.get('Pid') == str(before['pid']) and values.get('Tgid') == str(before['pid'])
                and values.get('State', '').split()[0] == before['state'], 'Kernel status identity differs')
        return True
    except (ValueError, TypeError, KeyError, IndexError):
        return False


def capacity_fallback(O, expected, base_observation, records):
    """Called only after the frozen observer reports UNKNOWN for a known PID."""
    record = {'pid': expected['pid'], 'expected_identity': expected, 'original_observation': base_observation,
              'method': METHOD, 'capacity_equivalence_passed': False}
    try:
        pid = expected['pid']
        record['boot_before'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        record['namespace_before'] = os.stat('/proc/self/ns/pid').st_ino
        record['stat_before'] = Path('/proc', str(pid), 'stat').read_text()
        before = O.proc_row(record['stat_before'])
        require(O.identity_key(before) == O.identity_key(expected) and before['state'] in ('Z', 'X'),
                'Supplement requires exact known terminal process')
        record['statm'] = Path('/proc', str(pid), 'statm').read_text()
        try:
            record['fd_entries'] = [entry.name for entry in Path('/proc', str(pid), 'fd').iterdir()]
            record['fd_errno'] = None
        except PermissionError as error:
            record['fd_errno'] = error.errno
            record['fd_error'] = type(error).__name__
        require(record['fd_errno'] == errno.EACCES, 'FD read did not fail with EACCES13')
        record['status'] = Path('/proc', str(pid), 'status').read_text()
        record['stat_after'] = Path('/proc', str(pid), 'stat').read_text()
        after = O.proc_row(record['stat_after'])
        record['boot_after'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        record['namespace_after'] = os.stat('/proc/self/ns/pid').st_ino
        passed = terminal_capacity(O, expected, before, after, record['statm'], record['status'],
            record['fd_errno'], record['boot_before'], record['boot_after'],
            record['namespace_before'], record['namespace_after'])
        record['capacity_equivalence_passed'] = passed
        if passed:
            return {'absent': False, 'row': after, 'closed': True}
    except (OSError, ValueError, KeyError, IndexError) as error:
        record['fallback_error'] = {'type': type(error).__name__, 'errno': getattr(error, 'errno', None),
                                    'message': str(error)}
    finally:
        records.append(record)
    return base_observation


def install_capacity_observation(O, identity, identities, records):
    known = {row['pid']: row for row in identities}
    supervisor = {'pid': identity['pid'], 'ticks': identity['startticks'], 'pgid': identity['pgid'],
                  'sid': identity['sid']}
    known[identity['pid']] = supervisor
    original = O.observed_process
    def observed(pid):
        base = original(pid)
        if pid in known and base.get('closed') is None and base.get('absent') is None:
            return capacity_fallback(O, known[pid], base, records)
        return base
    O.observed_process = observed


def opaque_bound(O, path, digest):
    path = Path(path)
    require(path.resolve(strict=True) == path and not path.is_symlink(), 'Bound file symlink')
    row = O.file_ref(path.parent, path.name)
    require(row['sha256'] == digest, 'Bound evidence changed')
    return {'path': str(path), 'bytes': row['bytes'], 'sha256': row['sha256']}


def exclusive_json(O, path, value):
    payload = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    directory = O.directory_fd(path.parent)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            view = memoryview(payload)
            while view:
                count = os.write(fd, view)
                require(count > 0, 'Write stalled')
                view = view[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory)
    finally:
        os.close(directory)
    return {'path': str(path), 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--output-directory', required=True)
    parser.add_argument('--approved-wrapper-sha256', required=True)
    parser.add_argument('--approved-proposal-sha256', required=True)
    args = parser.parse_args()
    root = Path(os.path.abspath(args.project))
    require(root.resolve(strict=True) == root, 'Noncanonical project')
    O = load_frozen(root)
    root = O.check_root(root)
    own = opaque_bound(O, Path(__file__).absolute(), args.approved_wrapper_sha256)
    proposal = opaque_bound(O, Path(__file__).absolute().with_name('proposal.json'), args.approved_proposal_sha256)
    bound = {key: opaque_bound(O, *value) for key, value in BOUND.items()}
    plan_ref, plan, pins, admission_ref, expected = O.verify_source(root)
    require(plan_ref['sha256'] == PLAN_SHA and plan['source_freeze_sha256'] == FREEZE_SHA,
            'Master SOURCE identity changed')
    _, admission = O.file_ref(root, O.STUDY + 'SOURCE_ADMISSION.json', True)
    require(admission.get('published_source_commit') == SOURCE_COMMIT, 'Actual SOURCE commit changed')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == O.BOOT
            and os.stat('/proc/self/ns/pid').st_ino == O.PIDNS, 'Current namespace differs')
    refs, docs, identity, identities, extras, approved_launch = O.load_evidence(root, expected, pins)
    require(O.same(identity, EXPECTED_SUPERVISOR), 'Wrong actual supervisor')
    records = []
    install_capacity_observation(O, identity, identities, records)
    first = O.evaluate(plan_ref['sha256'], refs, docs, identity, identities,
                       O.snapshot(identity, identities), approved_launch)
    second = O.evaluate(plan_ref['sha256'], refs, docs, identity, identities,
                        O.snapshot(identity, identities), approved_launch)
    require(O.same(first, second), 'Two strict snapshots disagree; no output/no retry')
    for row in [plan_ref, admission_ref, *pins.values(), *extras, *[r for r in refs.values() if r]]:
        O.reference(root, row)
    for key, relative in O.PATHS.items():
        if refs[key] is None:
            try:
                O.file_ref(root, relative)
            except FileNotFoundError:
                continue
            raise ValueError('Previously absent metadata appeared')
    for key, value in BOUND.items():
        require(O.same(opaque_bound(O, *value), bound[key]), 'Bound original evidence changed')
    require(O.same(opaque_bound(O, Path(__file__).absolute(), args.approved_wrapper_sha256), own), 'Wrapper changed')
    require(O.same(opaque_bound(O, Path(__file__).absolute().with_name('proposal.json'), args.approved_proposal_sha256), proposal), 'Proposal changed')
    output = Path(os.path.abspath(args.output_directory))
    require(output.resolve(strict=True) == output and output.is_dir() and not output.is_relative_to(root)
            and output != Path(BOUND['original_unknown'][0]).parent and not any(output.iterdir()),
            'New empty outside output directory required')
    closure = O.write_outside(root, output / 'SUPERVISOR_OBSERVED_CLOSURE.json', first)
    attestation = {'schema_version': 1, 'epoch': 31, 'kind': O.KIND, 'phase': 'dev',
        'method': METHOD, 'source_commit': SOURCE_COMMIT, 'source_plan_sha256': PLAN_SHA,
        'source_freeze_sha256': FREEZE_SHA, 'frozen_observer_sha256': OBSERVER_SHA,
        'supplemental_source': own, 'proposal': proposal, 'bound_original_evidence': bound,
        'canonical18_closure': closure, 'two_strict_snapshots_equal': True,
        'whole_group_scan_and_reducer': 'UNCHANGED_FROZEN_4F5', 'kernel_observations': records,
        'physical_closure_passed': first['physical_closure_passed'],
        'scope': 'Direct kernel FD capacity proof for EACCES13 terminal exact known identities only. No scientific/scoring qualification, inferred operation counts, detached exit status or future survival claim.'}
    extra = exclusive_json(O, output / 'SUPPLEMENTAL_TERMINAL_CAPACITY_ATTESTATION.json', attestation)
    print(json.dumps({'closure': closure, 'attestation': extra, 'physical_closure_passed': first['physical_closure_passed']}, sort_keys=True))
    return 0 if first['physical_closure_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
