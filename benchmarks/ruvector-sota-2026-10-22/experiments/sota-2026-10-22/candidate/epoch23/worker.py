"""One bounded native+BGE source-scope engineering process; no NLI or gold."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import resource
import stat
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = 'experiments/sota-2026-10-22/'
STUDY = ROOT / PREFIX / 'epoch23'
BGE_SOURCE = PREFIX + 'candidate/epoch3/models.py'
BGE_SOURCE_SHA = 'c5cf3500a89837e71adc754f0dc96d090e172068031545fc55ee349e80210716'
SOURCE = '99efd3517516f3089ea2c669add1c2b1fa521fb1'
CONTRACT_SHA = 'e493ce94cb47022c46669750643b87ef5c79b1da840bb2f2e6741e0cc330a502'
QUERY_PREFIX = 'Represent this sentence for searching relevant passages: '
ARMS = ('actual_native', 'lexical', 'positional')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def checked(relative):
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or PurePosixPath(relative).is_absolute()
            or any(x in ('', '.', '..') for x in relative.split('/'))):
        raise ValueError('Unsafe frozen relative path')
    path = ROOT / relative
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('Missing/nonregular frozen file: ' + relative)
    return path


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink output refused')
    with path.open('x') as target:
        target.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        target.flush()
        os.fsync(target.fileno())


def remaining(deadline):
    seconds = deadline - time.time()
    if seconds <= 0:
        raise TimeoutError('Whole engineering process deadline reached')
    return seconds


def resources():
    own = resource.getrusage(resource.RUSAGE_SELF)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'worker_user_seconds': own.ru_utime, 'worker_system_seconds': own.ru_stime,
        'worker_peak_RSS_bytes': own.ru_maxrss * 1024,
        'reaped_child_user_seconds': child.ru_utime,
        'reaped_child_system_seconds': child.ru_stime,
        'largest_reaped_child_peak_RSS_bytes': child.ru_maxrss * 1024,
        'CPU_affinity': sorted(os.sched_getaffinity(0)),
        'scope': 'Separate Linux process/child high-water observations, not simultaneous RSS sum.'}


def owner_lock(admission):
    if (admission.get('owner_pid') != 66088
            or admission.get('owner_startticks') != 12864421):
        raise ValueError('Wrong exact epoch23 owner')
    fields = Path('/proc/66088/stat').read_text().rsplit(')', 1)[1].split()
    if fields[0] in ('Z', 'X') or int(fields[19]) != 12864421:
        raise ValueError('Owner exited or PID reused')
    lock = ROOT.parent.parent / 'exclusive.work.lock'
    if any(p.is_symlink() for p in (lock, *lock.parents)):
        raise ValueError('Symlink work lock')
    fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Nonregular work lock')
        target = (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)
        active = False
        for line in Path('/proc/locks').read_text().splitlines():
            words = line.split()
            if len(words) < 8 or words[1:4] != ['FLOCK', 'ADVISORY', 'WRITE'] or words[4] != '66088':
                continue
            a, b, c = words[5].split(':')
            active |= (int(a, 16), int(b, 16), int(c)) == target
        if not active:
            raise ValueError('Exact owner does not hold kernel FLOCK')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'owner_pid': 66088, 'owner_startticks': 12864421,
                    'lock_inode': info.st_ino, 'contender_denied': True}
        fcntl.flock(fd, fcntl.LOCK_UN)
        raise ValueError('Work lock contender acquired unexpectedly')
    finally:
        os.close(fd)


def verify(args):
    if sha(args.plan) != args.expected_plan_sha:
        raise ValueError('Plan identity mismatch')
    plan = read(args.plan)
    if (plan.get('schema_version') != 1 or plan.get('epoch') != 23
            or plan.get('source_checkpoint') != SOURCE
            or plan.get('actual_project') != str(ROOT)):
        raise ValueError('Wrong isolated epoch23 plan')
    if plan.get('benchmark_roles') != dict.fromkeys(('train', 'dev', 'calibration', 'confirmation'), []):
        raise ValueError('Engineering requires empty benchmark roles')
    limits = plan['limits']
    for key, value in {'cpu_threads': 2, 'seconds_per_batch': 600,
                       'paid_calls': 0, 'GPU_calls': 0}.items():
        if type(limits.get(key)) is not int or limits[key] != value:
            raise ValueError('Wrong exact engineering budget: ' + key)
    if not 0 < remaining(args.deadline) <= 600:
        raise ValueError('Invalid whole-process deadline')
    if sorted(os.sched_getaffinity(0)) != [0, 1]:
        raise ValueError('Exact CPU0/1 affinity required')
    pins = plan['pins']
    by_path = {row['path']: row for row in pins}
    if len(by_path) != len(pins):
        raise ValueError('Duplicate source pin')
    for row in pins:
        path = checked(row['path'])
        if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('Frozen source changed: ' + row['path'])
    for file in (HERE / 'scope.py', HERE / 'worker.py', HERE / 'native.cjs'):
        if str(file.relative_to(ROOT)) not in by_path:
            raise ValueError('Unpinned candidate source')
    if by_path.get(BGE_SOURCE, {}).get('sha256') != BGE_SOURCE_SHA:
        raise ValueError('Exact original BGE wrapper required')
    for key in ('fixtures', 'runtime_assets_lock', 'source_freeze'):
        relative = plan[key + '_path']
        expected = plan[key + '_sha256']
        if by_path.get(relative, {}).get('sha256') != expected or sha(checked(relative)) != expected:
            raise ValueError('Unpinned source/fixture/runtime protocol: ' + key)
    admission = read(args.admission)
    if (args.admission.resolve() != STUDY / 'NATIVE_ADMISSION.json'
            or admission.get('epoch') != 23 or admission.get('phase') != 'engineering'
            or admission.get('scope') != 'benchmarks/ruvector-sota-2026-10-22/'
            or admission.get('verified_actual_remote_readback') is not True
            or admission.get('plan_sha256') != args.expected_plan_sha
            or admission.get('source_freeze_sha256') != plan['source_freeze_sha256']
            or not re.fullmatch('[0-9a-f]{40}', admission.get('published_source_commit', ''))):
        raise ValueError('Late immutable-source engineering admission failed')
    lock = owner_lock(admission)
    assets = read(checked(plan['runtime_assets_lock_path']))
    rows = assets['assets']
    if len(rows) != 10 or len({row['path'] for row in rows}) != 10:
        raise ValueError('Exactly two BGE plus eight native closure files required')
    if {row['path'] for row in rows if row['path'].startswith('models/')} != {
            'models/bge-small-en-v1.5/model.onnx', 'models/bge-small-en-v1.5/tokenizer.json'}:
        raise ValueError('Only exact BGE model assets admitted')
    for row in rows:
        path = checked(row['path'])
        if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('Runtime asset changed: ' + row['path'])
    expected_versions = plan['python_expected_versions']
    if set(expected_versions) != {'numpy', 'onnxruntime', 'tokenizers'}:
        raise ValueError('Exact three Python runtime versions required')
    actual_versions = {name: importlib.metadata.version(name) for name in expected_versions}
    if actual_versions != expected_versions:
        raise ValueError('Installed Python runtime versions changed')
    fixtures = read(checked(plan['fixtures_path']))
    if (set(fixtures) != {'schema_version', 'epoch', 'contract_sha256', 'license',
                         'authorship', 'scope', 'cases'}
            or fixtures['schema_version'] != 1 or fixtures['contract_sha256'] != CONTRACT_SHA
            or fixtures['epoch'] != 23 or fixtures['license'] != 'CC0-1.0'
            or not isinstance(fixtures['authorship'], str) or not fixtures['authorship'].strip()
            or not isinstance(fixtures['scope'], str) or not fixtures['scope'].strip()
            or not isinstance(fixtures['cases'], list) or not 1 <= len(fixtures['cases']) <= 64):
        raise ValueError('Frozen input-only engineering fixture schema changed')
    return plan, admission, lock, rows, actual_versions, fixtures


def load_bge():
    spec = importlib.util.spec_from_file_location('epoch23_pinned_BGE', checked(BGE_SOURCE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BgeEncoder(ROOT)


class CountedSession:
    def __init__(self, session, counters):
        self.session, self.counters = session, counters

    def run(self, names, feed):
        count = len(feed['input_ids'])
        self.counters['BGE_forwards_attempted'] += 1
        self.counters['BGE_texts_attempted'] += count
        start = time.perf_counter()
        result = self.session.run(names, feed)
        self.counters['BGE_forwards_completed'] += 1
        self.counters['BGE_texts_completed'] += count
        self.counters['BGE_forward_seconds'] += time.perf_counter() - start
        return result


def lexical_order(texts, query):
    words = set(re.findall(r'\w+', query.casefold()))
    sets = [set(re.findall(r'\w+', text.casefold())) for text in texts]
    scores = [len(words & value) / max(1, len(words | value)) for value in sets]
    return sorted(range(len(texts)), key=lambda i: (-scores[i], i)), scores


def native_call(bundle, out, deadline, counters):
    with tempfile.TemporaryDirectory(prefix='ruvector-e23-native-') as temporary:
        working = Path(temporary)
        source = working / 'bundle.json'
        target = working / 'result.json'
        write_new(source, bundle)
        write_new(out / 'bundle.json', bundle)
        started = time.perf_counter()
        helper = subprocess.Popen(['node', str(HERE / 'native.cjs'), str(ROOT), str(source), str(target)],
            cwd=working, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        attempt = {'pid': helper.pid, 'pgid': os.getpgid(helper.pid), 'worker_pid': os.getpid(),
            'source_path': str((HERE / 'native.cjs').relative_to(ROOT)),
            'source_sha256': sha(HERE / 'native.cjs'), 'bundle_sha256': sha(source),
            'native_cases_attempted': len(bundle['cases'])}
        counters['native_helper_starts'] += 1
        try:
            write_new(out / 'native-attempt.json', attempt)
            stdout, stderr = helper.communicate(timeout=min(60, remaining(deadline)))
        finally:
            if helper.poll() is None:
                helper.kill()
                helper.wait()
        if helper.returncode != 0:
            if Path(str(target) + '.failure.json').is_file():
                write_new(out / 'native-failure.json', read(str(target) + '.failure.json'))
            raise RuntimeError('Actual native helper failed: ' + stderr[-1000:])
        result = read(target)
        if (result.get('native') is not True or result.get('bundle_sha256') != sha(source)
                or result.get('native_binary_sha256') != 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
                or result.get('package_version') != '0.1.33'
                or result.get('platform_package_version') != '0.1.31'
                or result.get('binary_version') != '2.3.0'
                or result.get('helper_pid') != helper.pid or len(result['cases']) != len(bundle['cases'])):
            raise ValueError('Literal native helper identity/receipt mismatch')
        result.update(helper_pgid=attempt['pgid'], helper_exit_code=helper.returncode,
            helper_exited=True, helper_wall_seconds=time.perf_counter() - started,
            stdout=stdout, stderr=stderr)
        counters['native_indexes_completed'] = len(result['cases'])
        counters['native_queries_completed'] = len(result['cases'])
        write_new(out / 'native-result.json', result)
    return result


def perform(raw, plan, fixtures, out, deadline):
    scope_spec = importlib.util.spec_from_file_location('epoch23_pinned_scope', HERE / 'scope.py')
    scope_module = importlib.util.module_from_spec(scope_spec)
    scope_spec.loader.exec_module(scope_module)
    pack_scope, validate_graph = scope_module.pack_scope, scope_module.validate_graph
    valid = []
    for case in fixtures['cases']:
        validation = validate_graph(case)
        row = {'id': case.get('id'), 'graph_validation': {
            'valid': validation['valid'], 'errors': validation['errors']},
            'native': None, 'arms': {}, 'forced_seed_checks': []}
        raw['cases'].append(row)
        if not validation['valid']:
            row['closure'] = pack_scope(case, [], True)
            continue
        if not validation['units']:
            row['closure'] = pack_scope(case, [], True)
            row['no_native_reason'] = 'EMPTY_SUPPLIED_UNIT_GRAPH'
            continue
        texts = [validation['excerpts'][unit['excerpt_id']]['text'][unit['start']:unit['end']]
                 for unit in case['units']]
        valid.append((case, row, texts))
    if not valid:
        raise ValueError('Engineering batch must include a real nonempty native corpus')
    if len({case['id'] for case in fixtures['cases']}) != len(fixtures['cases']):
        raise ValueError('Duplicate fixture ID')
    if sum(len(texts) + 1 for _, _, texts in valid) > 2048:
        raise ValueError('Frozen engineering BGE corpus exceeds safety bound')
    remaining(deadline)
    raw['counters']['BGE_initializations_attempted'] += 1
    start = time.perf_counter()
    bge = load_bge()
    raw['counters']['BGE_initializations_completed'] += 1
    bge.session = CountedSession(bge.session, raw['counters'])
    raw['BGE'] = dict(bge.receipt, source_path=BGE_SOURCE, source_sha256=BGE_SOURCE_SHA,
        initialization_seconds=time.perf_counter()-start, query_prefix=QUERY_PREFIX,
        no_warmup=True, one_session=True, actual_semantic_embeddings=True)
    bundle = {'cases': []}
    for case, row, texts in valid:
        remaining(deadline)
        query = QUERY_PREFIX + case['query']
        if any(len(bge.raw_tokenizer.encode(text).ids) > 256 for text in texts + [query]):
            raise ValueError('Supplied engineering unit/query exceeds BGE256; no truncation allowed')
        start = time.perf_counter()
        vectors, diagnostics = bge.encode(texts)
        query_vectors, query_diagnostics = bge.encode([query])
        if vectors.shape != (len(texts), 384) or query_vectors.shape != (1, 384):
            raise ValueError('Exact BGE384 output shape required')
        norms = [math.sqrt(math.fsum(float(x)*float(x) for x in vector))
                 for vector in [*vectors, *query_vectors]]
        if any(not math.isfinite(value) or abs(value-1.0) > 1e-5 for value in norms):
            raise ValueError('BGE vectors must be finite nonzero unit-normalized embeddings')
        row['embedding'] = {'unit_ids': [unit['id'] for unit in case['units']],
            'exact_unit_texts': texts, 'exact_query_text': query,
            'unit_diagnostics': diagnostics, 'query_diagnostics': query_diagnostics,
            'embedding_norm_min': min(norms), 'embedding_norm_max': max(norms),
            'wall_seconds': time.perf_counter()-start}
        bundle['cases'].append({'id': case['id'], 'vectors': vectors.tolist(),
            'query_vector': query_vectors[0].tolist(), 'seed_limit': case['seed_limit']})
    remaining(deadline)
    result = native_call(bundle, out, deadline, raw['counters'])
    for (case, row, texts), native in zip(valid, result['cases']):
        if native['case_id'] != case['id']:
            raise ValueError('Native case order changed')
        count = len(case['units'])
        k = min(max(1, case['seed_limit']), count)
        if (len(native['ids']) != k or len(set(native['ids'])) != k
                or any(type(i) is not int or not 0 <= i < count for i in native['ids'])):
            raise ValueError('Invalid actual native ranking')
        row['native'] = native
        lexical, scores = lexical_order(texts, case['query'])
        ranking = {'actual_native': native['ids'], 'lexical': lexical, 'positional': list(range(count))}
        row['lexical_jaccard_scores'] = scores
        for arm in ARMS:
            remaining(deadline)
            ids = [case['units'][i]['id'] for i in ranking[arm]]
            seeds = ids[:case['seed_limit']]
            started = time.perf_counter()
            baseline = pack_scope(case, seeds, False)
            baseline_seconds = time.perf_counter()-started
            started = time.perf_counter()
            closure = pack_scope(case, seeds, True)
            closure_seconds = time.perf_counter()-started
            row['arms'][arm] = {'observed_seed_ids': ids, 'effective_seed_ids': seeds,
                'baseline': baseline, 'closure': closure,
                'baseline_seconds': baseline_seconds, 'closure_seconds': closure_seconds,
                'seed_origin': 'ACTUAL_NATIVE_OBSERVATION' if arm == 'actual_native' else 'MATCHED_CONTROL'}
        raw['counters']['engineering_cases_completed'] += 1
        row['latency_seconds'] = row['embedding']['wall_seconds'] + (
            native['initialization_ms'] + native['query_ms']) / 1000 + sum(
            row['arms'][arm]['baseline_seconds'] + row['arms'][arm]['closure_seconds']
            for arm in ARMS)
        row['latency_with_amortized_encoder_initialization_seconds'] = (
            row['latency_seconds'] + raw['BGE']['initialization_seconds'] / len(valid))
        row['latency_scope'] = ('BGE unit/query encoding + literal native insertion/search + '
            'three-arm baseline/closure packing; excludes common source checks and forced guards.')
        for kind, seeds in (
                ('unknown_seed', ['__engineering_unknown_seed__']),
                ('duplicate_seed', [case['units'][0]['id'], case['units'][0]['id']]),
                ('empty_seed', [])):
            raw['forced_seed_checks'].append({'origin': 'FORCED_SCOPE_GUARD_ONLY_NOT_NATIVE',
                'case_id': case['id'], 'kind': kind, 'seed_ids': seeds,
                'baseline': pack_scope(case, seeds, False),
                'closure': pack_scope(case, seeds, True)})
    def summary(values):
        ordered = sorted(values)
        def percentile(p):
            at = (len(ordered)-1) * p
            low, high = math.floor(at), math.ceil(at)
            return ordered[low] + (ordered[high]-ordered[low]) * (at-low)
        return {'n': len(ordered), 'p50': percentile(.5), 'p95': percentile(.95),
                'quantile': 'Linear interpolation of sorted observations at (n-1)*p.'}
    raw['latency'] = {
        'native_query_ms': summary([case['native']['query_ms'] for _, case, _ in valid]),
        'native_initialization_ms': summary([case['native']['initialization_ms'] for _, case, _ in valid]),
        'baseline_pack_seconds': summary([case['arms'][arm]['baseline_seconds']
                                         for _, case, _ in valid for arm in ARMS]),
        'closure_pack_seconds': summary([case['arms'][arm]['closure_seconds']
                                        for _, case, _ in valid for arm in ARMS]),
        'case_components_seconds': summary([case['latency_seconds'] for _, case, _ in valid]),
        'case_with_amortized_encoder_initialization_seconds': summary([
            case['latency_with_amortized_encoder_initialization_seconds'] for _, case, _ in valid]),
        'scope': 'Engineering observed component timings; not NLI or production serving latency.'}
    raw['status'] = 'COMPLETED_ENGINEERING_AWAITING_INDEPENDENT_ORACLE'


def main():
    parser = argparse.ArgumentParser()
    for key in ('plan', 'admission', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--expected-plan-sha', required=True)
    parser.add_argument('--deadline', type=float, required=True)
    args = parser.parse_args()
    args.out = args.out.absolute()
    args.out.relative_to(STUDY / 'runs')
    if any(path.is_symlink() for path in (args.out, *args.out.parents)):
        raise ValueError('Unsafe output directory')
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    raw = {'schema_version': 1, 'epoch': 23, 'source_checkpoint': SOURCE,
        'plan_sha256': args.expected_plan_sha, 'status': 'INITIALIZING', 'cases': [],
        'forced_seed_checks': [],
        'contract_sha256': CONTRACT_SHA,
        'accuracy': None, 'proper_scores': None, 'benchmark_results': None,
        'roles_used': dict.fromkeys(('train', 'dev', 'calibration', 'confirmation'), []),
        'scope': 'Source annotation engineering only; not benchmark generalization or SOTA.',
        'started_at': datetime.now(timezone.utc).isoformat(), 'worker_pid': os.getpid(),
        'worker_pgid': os.getpgid(0), 'errors': [],
        'counters': {**dict.fromkeys(('BGE_initializations_attempted', 'BGE_initializations_completed',
            'BGE_forwards_attempted', 'BGE_forwards_completed', 'BGE_texts_attempted',
            'BGE_texts_completed', 'native_helper_starts', 'native_indexes_completed',
            'native_queries_completed', 'engineering_cases_completed', 'NLI_forwards',
            'fits', 'paid_calls', 'GPU_calls', 'Python_network_operations_attempted'), 0),
            'BGE_forward_seconds': 0.0}}

    def network_audit(event, arguments):
        if event in ('socket.connect', 'socket.getaddrinfo'):
            raw['counters']['Python_network_operations_attempted'] += 1
            raise RuntimeError('Offline engineering worker refuses network access')
    sys.addaudithook(network_audit)
    code = 0
    try:
        plan, admission, lock, assets, versions, fixtures = verify(args)
        raw.update(admission=admission, owner_lock=lock, runtime_assets=assets,
                   python_versions=versions, fixtures_sha256=plan['fixtures_sha256'])
        attempt_path = args.out / 'attempt.json'
        while not attempt_path.exists() and remaining(args.deadline) > 0:
            if time.perf_counter()-started > 5:
                raise ValueError('Outer launcher did not seal worker identity')
            time.sleep(.01)
        attempt = read(attempt_path)
        if (attempt.get('pid') != os.getpid() or attempt.get('pgid') != os.getpgid(0)
                or os.getpgid(0) != os.getpid()):
            raise ValueError('Exact owned worker/group launch identity required')
        raw['preparation_seconds'] = time.perf_counter()-started
        perform(raw, plan, fixtures, args.out, args.deadline)
        owner_lock(admission)
        remaining(args.deadline)
    except BaseException as error:
        raw['status'] = 'FAILED_ENGINEERING_PROCESS'
        raw['errors'].append({'type': type(error).__name__, 'message': str(error)})
        code = 2
    finally:
        raw.update(wall_seconds_including_initialization_cleanup=time.perf_counter()-started,
            resources=resources(), completed_at=datetime.now(timezone.utc).isoformat())
        write_new(args.out / 'raw.json', raw)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
