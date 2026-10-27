"""One-shot CPU study supervisor. No model, tokenizer, native or Gold imports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time


KIND = 'REAL_CONTRACTNLI_ROBERTA_FAITHFUL_MMAP_TRANSFER_PILOT'


def canonical_relative(value):
    assert type(value) is str and value and not value.startswith('/') and '\\' not in value
    parts = value.split('/')
    assert all(part not in ('', '.', '..') for part in parts)
    assert str(Path(value)) == value
    return Path(value)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def exact(ref):
    p = Path(ref['path'])
    assert p.is_absolute() and p.is_file() and not p.is_symlink()
    data = p.read_bytes()
    assert len(data) == ref['bytes'] and digest(data) == ref['sha256'], str(p)
    return data


def write_once(path, value):
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as f:
            f.write(data)
            f.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)
    return {'path': str(path), 'bytes': len(data), 'sha256': digest(data)}


def snapshot(pid):
    try:
        p = Path('/proc') / str(pid)
        fields = (p / 'stat').read_text().rsplit(')', 1)[1].split()
        status = (p / 'status').read_text()
        fdsize = next(int(x.split(':', 1)[1]) for x in status.splitlines() if x.startswith('FDSize:'))
        return {'pid': pid, 'state': fields[0], 'ppid': int(fields[1]),
                'pgid': int(fields[2]), 'sid': int(fields[3]),
                'startticks': int(fields[19]), 'wait_status': int(fields[49]),
                'FDSize': fdsize, 'statm': [int(x) for x in (p / 'statm').read_text().split()]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def group_members(groups):
    found = []
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            s = snapshot(int(p.name))
            if s and (s['pgid'] in groups or s['sid'] in groups):
                found.append(s)
    return found


def signal_owned_group(pgid, sig):
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass  # The exact owned group already ended; closure is still checked below.


def fence(owner_ref, work):
    owner = json.loads(exact(owner_ref))
    assert owner['epoch'] == 50 and owner['generation'] == 15
    assert owner['pid'] == 158817 and owner['startticks'] == 38479788
    assert time.time() < owner['expires_unix'] and not (work / 'release.request').exists()
    s = snapshot(owner['pid'])
    assert s and s['state'] not in ('Z', 'X') and s['startticks'] == owner['startticks']
    st = os.stat('/proc/' + str(owner['pid']) + '/fd/3')
    assert (st.st_dev, st.st_ino) == (owner['lock_device'], owner['lock_inode']) == (33, 13626)
    assert 'FLOCK' in Path('/proc/' + str(owner['pid']) + '/fdinfo/3').read_text()
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == owner['kernel_boot_id']
    return owner


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--expected-plan-sha256', required=True)
    p.add_argument('--admission', type=Path, required=True)
    p.add_argument('--expected-admission-sha256', required=True)
    p.add_argument('--phase', choices=['dev', 'confirmation'], required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    plan_raw, admission_raw = a.plan.read_bytes(), a.admission.read_bytes()
    assert digest(plan_raw) == a.expected_plan_sha256
    assert digest(admission_raw) == a.expected_admission_sha256
    plan, admission = json.loads(plan_raw), json.loads(admission_raw)
    assert plan['epoch'] == admission['epoch'] == 50 and plan['kind'] == admission['kind'] == KIND
    assert admission['phase'] == a.phase and admission['plan_sha256'] == digest(plan_raw)
    assert admission['owner_ref'] == admission['owner']
    assert admission['features_ref'] == admission['features']
    assert admission['data_admission_ref'] == admission['data_admission']
    work, project = Path(plan['work_root']), Path(plan['project_root'])
    assert work == Path('/dev/shm/ruvector-sota-2026-10-22/epoch50-ad86e60e2402') and project.is_relative_to(work)
    expected_env = {'BLIS_NUM_THREADS': '2', 'MKL_DYNAMIC': 'FALSE', 'OMP_THREAD_LIMIT': '2',
                    'RAYON_NUM_THREADS': '2', 'UV_THREADPOOL_SIZE': '2', 'VECLIB_MAXIMUM_THREADS': '2'}
    assert plan['launch_environment'] == expected_env
    assert all(os.environ.get(k) == v for k, v in expected_env.items())
    owner = fence(admission['owner_ref'], work)
    sf_raw = exact(admission['source_freeze_ref'])
    assert digest(sf_raw) == admission['source_freeze_sha256']
    sf = json.loads(sf_raw)
    assert sf['epoch'] == 50 and sf['kind'] == KIND
    for row in sf['files']:
        exact({'path': str(project / canonical_relative(row['path'])), 'bytes': row['bytes'], 'sha256': row['sha256']})
    assert admission['source_files'] == [
        {'path': str(project / canonical_relative(row['path'])), 'bytes': row['bytes'], 'sha256': row['sha256']}
        for row in sf['files']]
    source = json.loads(exact(admission['source_admission_ref']))
    assert source['source_full_tree_verified'] is True
    assert source['source_publication_independently_verified'] is True
    assert source['source_commit'] == admission['source_commit']
    assert source['plan_ref']['sha256'] == digest(plan_raw)
    assert source['source_freeze_ref']['sha256'] == digest(sf_raw)
    data = json.loads(exact(admission['data_admission_ref']))
    assert data['status'] == 'READY_LABEL_BLIND_FEATURES_AND_OPAQUE_VAULT' and data['phase'] == a.phase
    assert data['errors'] == [] and data['semantic_gold_values_decoded'] == 0
    assert data['plan_sha256'] == digest(plan_raw) and data['source_freeze_sha256'] == digest(sf_raw)
    assert data['features']['sha256'] == admission['features_ref']['sha256']
    exact(admission['features_ref'])  # bytes only; no feature/Gold parse by supervisor
    assert admission['worker_slot_token'] and admission['native_batch_ordinal'] == (1 if a.phase == 'dev' else 2)
    if a.phase == 'confirmation':
        assert admission['dev_independent_acceptance_ref'] == admission['independent_DEV_acceptance']
        acceptance = json.loads(exact(admission['dev_independent_acceptance_ref']))
        assert acceptance['checks_passed'] is True and acceptance['dev_passed'] is True
        assert acceptance['plan_sha256'] == digest(plan_raw)
        assert admission['confirmation_materialization_authorized'] is True
    assert not a.out_dir.exists()
    a.out_dir.mkdir(parents=True)
    assert sorted(os.sched_getaffinity(0)) == [0, 1]
    attempt = {'schema_version': 1, 'epoch': 50, 'kind': KIND, 'phase': a.phase,
               'plan_sha256': digest(plan_raw), 'admission_sha256': digest(admission_raw),
               'worker_slot_token': admission['worker_slot_token'],
               'native_batch_ordinal': admission['native_batch_ordinal'],
               'attempts': 1, 'no_retry_after_any_failure': True,
               'supervisor_identity': snapshot(os.getpid()),
               'kernel_boot_id': owner['kernel_boot_id'], 'owner_ref': admission['owner_ref']}
    write_once(a.out_dir / 'DISPATCH_ATTEMPT.json', attempt)
    worker_ref = plan['worker_source']
    worker = project / canonical_relative(worker_ref['path'])
    exact({'path': str(worker), 'bytes': worker_ref['bytes'], 'sha256': worker_ref['sha256']})
    raw_path = a.out_dir / 'raw.json'
    private = work / 'private-run' / a.phase
    assert not private.exists()
    private.mkdir(parents=True)
    start = time.monotonic()
    env = os.environ.copy()
    env.update({'CUDA_VISIBLE_DEVICES': '', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                'HF_DATASETS_OFFLINE': '1', 'TOKENIZERS_PARALLELISM': 'false',
                'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2',
                'NUMEXPR_NUM_THREADS': '2'})
    command = [plan['python_executable'], '-I', '-B', '-X', 'pycache_prefix=' + str(private / 'empty-pycache'),
               str(worker), '--plan', str(a.plan), '--expected-plan-sha256', digest(plan_raw),
               '--phase', a.phase, '--admission', str(a.admission),
               '--expected-admission-sha256', digest(admission_raw), '--output', str(raw_path),
               '--private-run-directory', str(private), '--deadline-monotonic-seconds', str(start + 570)]
    observed = {}
    killed, reason = False, None
    with (a.out_dir / 'worker.stdout').open('xb') as out, (a.out_dir / 'worker.stderr').open('xb') as err:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                 env=env, start_new_session=True)
        initial = snapshot(child.pid)
        assert initial is not None
        observed[(initial['pid'], initial['startticks'])] = initial
        groups = {child.pid}
        while child.poll() is None:
            for s in group_members(groups):
                observed[(s['pid'], s['startticks'])] = s
            elapsed = time.monotonic() - start
            try:
                fence(admission['owner_ref'], work)
            except Exception:
                reason = 'OWNER_LOST_NO_NEW_WORK'
            if reason or elapsed >= 580:
                reason = reason or 'HARD_BATCH_DEADLINE'
                signal_owned_group(child.pid, signal.SIGTERM)
                killed = True
                break
            time.sleep(0.25)
        if killed:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                signal_owned_group(child.pid, signal.SIGKILL)
                child.wait(timeout=5)
        rc = child.wait()
    live = [s for s in group_members(groups) if s['state'] not in ('Z', 'X')]
    if live:
        signal_owned_group(child.pid, signal.SIGKILL)
        for _ in range(40):
            live = [s for s in group_members(groups) if s['state'] not in ('Z', 'X')]
            if not live:
                break
            time.sleep(0.1)
    assert not live, 'Owned worker group did not close'
    elapsed = time.monotonic() - start
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    complete = {'schema_version': 1, 'epoch': 50, 'kind': KIND, 'phase': a.phase,
                'plan_sha256': digest(plan_raw), 'source_freeze_sha256': digest(sf_raw),
                'actual_worker_starts': 1, 'exit_code': rc, 'killed': killed, 'reason': reason,
                'wall_seconds_including_worker_init_and_owned_cleanup': elapsed,
                'within_600_seconds': elapsed < 600, 'command': command,
                'owned_process_identities': list(observed.values()), 'live_owned_group_members': live,
                'supervisor_identity': snapshot(os.getpid()), 'cpu_affinity': sorted(os.sched_getaffinity(0)),
                'resources': {'children_user_seconds': usage.ru_utime, 'children_system_seconds': usage.ru_stime,
                              'children_max_rss_kib': usage.ru_maxrss,
                              'scope': 'RUSAGE_CHILDREN after worker wait; child CPU includes waited descendants; maxRSS is a high-water, not a sum.'},
                'Gold_or_evaluation_calls': 0}
    if raw_path.exists():
        raw = raw_path.read_bytes()
        complete['raw_ref'] = {'path': str(raw_path), 'bytes': len(raw), 'sha256': digest(raw)}
        forecast_count = len(json.loads(raw).get('rows', []))
        write_once(a.out_dir / 'raw-seal.json', {'schema_version': 1, 'epoch': 50, 'kind': KIND,
                   'phase': a.phase, 'plan_sha256': digest(plan_raw), 'source_freeze_sha256': digest(sf_raw),
                   'raw_ref': complete['raw_ref'], 'worker_exit_code': rc,
                   'forecast_count': forecast_count,
                   'raw_capture_not_yet_independently_qualified': True,
                   'Gold_decoded_by_supervisor': 0})
    ref = write_once(a.out_dir / 'execution.json', complete)
    print(json.dumps({'execution': ref, 'worker_exit_code': rc, 'wall_seconds': elapsed,
                      'within_600_seconds': elapsed < 600, 'Gold_calls': 0}, sort_keys=True))
    if rc or killed or elapsed >= 600 or not raw_path.exists():
        raise SystemExit(17)


if __name__ == '__main__':
    main()
