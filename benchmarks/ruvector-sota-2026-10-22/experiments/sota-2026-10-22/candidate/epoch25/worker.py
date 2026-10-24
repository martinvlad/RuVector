"""One offline native+BGE+fixed-Qwen engineering worker; no gold or generation."""
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
STUDY = ROOT / PREFIX / 'epoch25'
BGE_SOURCE = PREFIX + 'candidate/epoch3/models.py'
BGE_SOURCE_SHA = 'c5cf3500a89837e71adc754f0dc96d090e172068031545fc55ee349e80210716'
SOURCE = 'A09506046843bc0c4e28e30865b610b283942e2d'.lower()
CONTRACT_PATH = PREFIX + 'candidate/epoch25/evidence-contract.json'
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
    if (admission.get('owner_pid') != 70365
            or admission.get('owner_startticks') != 13868579):
        raise ValueError('Wrong exact epoch25 owner')
    fields = Path('/proc/70365/stat').read_text().rsplit(')', 1)[1].split()
    if fields[0] in ('Z', 'X') or int(fields[19]) != 13868579:
        raise ValueError('Owner exited or PID reused')
    owner = read(ROOT.parent / 'owner.json')
    if (owner.get('pid') != 70365 or owner.get('startticks') != 13868579
            or time.time() >= owner['expires_unix'] or (ROOT.parent / 'release.request').exists()):
        raise ValueError('Exact guardian lease expired or released')
    lock = ROOT.parent.parent / 'exclusive.work.lock'
    if any(p.is_symlink() for p in (lock, *lock.parents)):
        raise ValueError('Symlink work lock')
    fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_ino != 13626:
            raise ValueError('Nonregular work lock')
        target = (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)
        active = False
        for line in Path('/proc/locks').read_text().splitlines():
            words = line.split()
            if len(words) < 8 or words[1:4] != ['FLOCK', 'ADVISORY', 'WRITE'] or words[4] != '70365':
                continue
            a, b, c = words[5].split(':')
            active |= (int(a, 16), int(b, 16), int(c)) == target
        if not active:
            raise ValueError('Exact owner does not hold kernel FLOCK')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'owner_pid': 70365, 'owner_startticks': 13868579,
                    'lock_inode': info.st_ino, 'contender_denied': True}
        fcntl.flock(fd, fcntl.LOCK_UN)
        raise ValueError('Work lock contender acquired unexpectedly')
    finally:
        os.close(fd)


def verify(args):
    if args.plan.resolve() != STUDY / 'plan.json' or sha(args.plan) != args.expected_plan_sha:
        raise ValueError('Plan path/identity mismatch')
    plan = read(args.plan)
    if (plan.get('schema_version') != 1 or plan.get('epoch') != 25
            or plan.get('source_checkpoint', '').lower() != SOURCE
            or plan.get('actual_project') != str(ROOT)):
        raise ValueError('Wrong isolated epoch25 plan')
    if plan.get('benchmark_roles') != dict.fromkeys(('train', 'dev', 'calibration', 'confirmation'), []):
        raise ValueError('Engineering requires empty benchmark roles')
    for key, value in {'worker_attempts': 1, 'native_corpus_batches': 1,
                       'cpu_threads': 2, 'seconds_per_batch': 600,
                       'paid_calls': 0, 'GPU_calls': 0,
                       'NLI_model_initializations': 1, 'NLI_forward_pairs': 18}.items():
        if type(plan['limits'].get(key)) is not int or plan['limits'][key] != value:
            raise ValueError('Wrong exact engineering budget: ' + key)
    if not 0 < remaining(args.deadline) <= 600 or sorted(os.sched_getaffinity(0)) != [0, 1]:
        raise ValueError('Exact CPU0/1 affinity and finite whole-process deadline required')
    pins = plan['pins']
    by_path = {row['path']: row for row in pins}
    if len(by_path) != len(pins):
        raise ValueError('Duplicate source pin')
    for row in pins:
        path = checked(row['path'])
        if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('Frozen source changed: ' + row['path'])
    required = ['worker.py', 'native.cjs', 'evidence.py', 'evidence-contract.json', 'PREPARATION.json', 'reader.py', 'prompt.json', 'reader-contract.json', 'MODEL_ASSETS.json', 'reader-PREPARATION.json']
    for name in required:
        if str((HERE / name).relative_to(ROOT)) not in by_path:
            raise ValueError('Unpinned candidate source: ' + name)
    if by_path.get(BGE_SOURCE, {}).get('sha256') != BGE_SOURCE_SHA:
        raise ValueError('Exact original BGE wrapper required')
    for key in ('fixtures', 'runtime_assets_lock', 'source_freeze', 'reader_assets_lock', 'reader_admission'):
        relative, expected = plan[key + '_path'], plan[key + '_sha256']
        if by_path.get(relative, {}).get('sha256') != expected or sha(checked(relative)) != expected:
            raise ValueError('Unpinned source/fixture/runtime protocol: ' + key)
    admission = read(args.admission)
    if (args.admission.resolve() != STUDY / 'NATIVE_ADMISSION.json'
            or admission.get('epoch') != 25 or admission.get('phase') != 'engineering'
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
    versions = {name: importlib.metadata.version(name) for name in plan['python_expected_versions']}
    if versions != plan['python_expected_versions']:
        raise ValueError('Installed Python runtime versions changed')
    model_dir = ROOT / plan['reader_model_dir']
    if model_dir != ROOT / 'models/qwen3-0.6b-c1899de' or not model_dir.is_dir() or model_dir.resolve() != model_dir:
        raise ValueError('Wrong frozen Qwen model directory')
    # External runtime bytes are never public source pins or checkpoint files.
    # Their metadata locks are pinned, then every actual byte is checked here.
    reader_lock = read(checked(plan['reader_assets_lock_path']))
    locked_files = reader_lock['assets']
    if (reader_lock.get('model_id') != 'Qwen/Qwen3-0.6B'
            or reader_lock.get('revision') != 'c1899de289a04d12100db370d81485cdf75e47ca'
            or reader_lock.get('model_dir') != plan['reader_model_dir']
            or len(locked_files) != 8 or len({row['path'] for row in locked_files}) != 8
            or {Path(row['path']).name for row in locked_files} != {
                'LICENSE', 'merges.txt', 'config.json', 'generation_config.json',
                'model.safetensors', 'tokenizer.json', 'tokenizer_config.json', 'vocab.json'}
            or any(not row['path'].startswith(plan['reader_model_dir'] + '/') for row in locked_files)):
        raise ValueError('Exact eight official locked Qwen assets required')
    for row in locked_files:
        path = checked(row['path'])
        if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('External Qwen runtime asset changed: ' + row['path'])
    freeze = read(checked(plan['source_freeze_path']))
    external = freeze['external_runtime_assets']
    identity = lambda row: (row['path'], row['bytes'], row['sha256'])
    if (len(external) != 18 or len({row['path'] for row in external}) != 18
            or set(map(identity, external)) != set(map(identity, rows + locked_files))):
        raise ValueError('Source freeze must bind exact eighteen external runtime identities')
    evidence_spec = importlib.util.spec_from_file_location('epoch25_pinned_evidence', HERE / 'evidence.py')
    evidence = importlib.util.module_from_spec(evidence_spec)
    evidence_spec.loader.exec_module(evidence)
    fixtures = read(checked(plan['fixtures_path']))
    evidence.validate_bundle(fixtures, by_path[CONTRACT_PATH]['sha256'])
    return plan, admission, lock, rows, versions, fixtures, evidence


def load_bge():
    spec = importlib.util.spec_from_file_location('epoch25_pinned_BGE', checked(BGE_SOURCE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BgeEncoder(ROOT)


class CountedSession:
    def __init__(self, session, counters, progress):
        self.session, self.counters, self.progress = session, counters, progress

    def run(self, names, feed):
        count = len(feed['input_ids'])
        self.counters['BGE_forwards_attempted'] += 1
        self.counters['BGE_texts_attempted'] += count
        self.progress({'event': 'BGE_FORWARD_BEFORE', 'texts': count})
        start = time.perf_counter()
        result = self.session.run(names, feed)
        self.counters['BGE_forwards_completed'] += 1
        self.counters['BGE_texts_completed'] += count
        self.counters['BGE_forward_seconds'] += time.perf_counter() - start
        self.progress({'event': 'BGE_FORWARD_AFTER', 'texts': count})
        return result


def native_call(bundle, out, deadline, counters, args, progress):
    with tempfile.TemporaryDirectory(prefix='ruvector-e25-native-') as temporary:
        working = Path(temporary)
        source, target = out / 'bundle.json', out / 'native-result.json'
        write_new(source, bundle)
        progress({'event': 'NATIVE_HELPER_BEFORE'})
        started = time.perf_counter()
        helper = subprocess.Popen(['node', str(HERE / 'native.cjs'), str(ROOT), str(source), str(target),
            str(args.plan), args.expected_plan_sha, str(args.admission), str(out / 'native-progress.jsonl')],
            cwd=working, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        counters['native_helper_starts'] += 1
        attempt = {'pid': helper.pid, 'pgid': os.getpgid(helper.pid), 'worker_pid': os.getpid(),
            'source_path': str((HERE / 'native.cjs').relative_to(ROOT)),
            'source_sha256': sha(HERE / 'native.cjs'), 'bundle_sha256': sha(source),
            'native_cases_scheduled': len(bundle['cases'])}
        write_new(out / 'native-attempt.json', attempt)
        stdout = stderr = ''
        try:
            stdout, stderr = helper.communicate(timeout=min(60, remaining(deadline)))
        finally:
            if helper.poll() is None:
                helper.kill()
                helper.wait()
            (out / 'native.stdout').write_text(stdout)
            (out / 'native.stderr').write_text(stderr)
            # Last fsynced native event survives a helper failure or kill.
            log = out / 'native-progress.jsonl'
            if log.is_file():
                for line in log.read_text().splitlines():
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    for key in ('native_index_initializations_attempted', 'native_queries_attempted',
                                'native_queries_completed', 'Node_network_operations_attempted'):
                        if key in event:
                            counters[key] = event[key]
        if helper.returncode != 0:
            failure_path = Path(str(target) + '.failure.json')
            if failure_path.is_file():
                failure = read(failure_path)
                write_new(out / 'native-failure.json', failure)
                for key in ('native_index_initializations_attempted', 'native_queries_attempted',
                            'native_queries_completed', 'Node_network_operations_attempted'):
                    counters[key] = failure.get(key, counters[key])
                counters['native_indexes_completed'] = len(failure.get('cases', []))
            raise RuntimeError('Actual native helper failed: ' + stderr[-1000:])
        result = read(target)
        if (result.get('native') is not True or result.get('bundle_sha256') != sha(source)
                or result.get('native_binary_sha256') != 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
                or result.get('package_version') != '0.1.33'
                or result.get('platform_package_version') != '0.1.31'
                or result.get('binary_version') != '2.3.0'
                or result.get('helper_pid') != helper.pid or len(result['cases']) != len(bundle['cases'])):
            raise ValueError('Literal native helper identity/receipt mismatch')
        counters['native_indexes_completed'] = len(result['cases'])
        for key in ('native_index_initializations_attempted', 'native_queries_attempted',
                    'native_queries_completed', 'Node_network_operations_attempted'):
            counters[key] = result[key]
        progress({'event': 'NATIVE_HELPER_AFTER', 'helper_pid': helper.pid,
                  'helper_wall_seconds': time.perf_counter() - started, 'helper_exited': True})
    return result


def perform(raw, plan, fixtures, evidence, out, deadline, args, progress):
    counters = raw['counters']
    progress({'event': 'TORCH_THREAD_CONFIGURATION_BEFORE'})
    import torch
    torch.set_num_threads(2)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    if torch.get_num_threads() != 2 or torch.get_num_interop_threads() != 1:
        raise ValueError('Exact global torch2/inter-op1 bounds required before BGE')
    progress({'event': 'TORCH_THREAD_CONFIGURATION_AFTER', 'intra_op': 2, 'inter_op': 1})
    raw['source_only_guards'] = evidence.owned_source_guards()
    valid = []
    for case in fixtures['cases']:
        units = [evidence.source_unit(source) for source in case['sources']]
        row = {'id': case['id'], 'hypothesis': case['hypothesis'], 'query': case['query'],
               'source_units': units, 'arms': {}, 'native': None}
        raw['cases'].append(row)
        counters['source_cases_completed'] += 1
        counters['automatically_extracted_units'] += len(units)
        counters['numeric_literals_extracted'] += sum(len(unit['numeric_literals']) for unit in units)
        valid.append((case, row, [unit['text'] for unit in units]))
    if sum(len(texts) + 1 for _, _, texts in valid) > 102:
        raise ValueError('Finite authored BGE batch exceeds 6*(16+1) bound')
    remaining(deadline)
    counters['BGE_initializations_attempted'] += 1
    progress({'event': 'BGE_INITIALIZATION_BEFORE'})
    start = time.perf_counter()
    bge = load_bge()
    counters['BGE_initializations_completed'] += 1
    bge.session = CountedSession(bge.session, counters, progress)
    raw['BGE'] = dict(bge.receipt, source_path=BGE_SOURCE, source_sha256=BGE_SOURCE_SHA,
        initialization_seconds=time.perf_counter() - start, query_prefix=QUERY_PREFIX,
        no_warmup=True, one_session=True, actual_semantic_embeddings=True)
    progress({'event': 'BGE_INITIALIZATION_AFTER'})
    bundle = {'cases': []}
    for case, row, texts in valid:
        remaining(deadline)
        query = QUERY_PREFIX + case['query']
        if any(len(bge.raw_tokenizer.encode(text).ids) > 256 for text in texts + [query]):
            raise ValueError('Entire supplied source/query exceeds BGE256; no silent truncation')
        start = time.perf_counter()
        vectors, diagnostics = bge.encode(texts)
        query_vectors, query_diagnostics = bge.encode([query])
        if vectors.shape != (len(texts), 384) or query_vectors.shape != (1, 384):
            raise ValueError('Exact BGE384 output shape required')
        norms = [math.sqrt(math.fsum(float(x) * float(x) for x in vector)) for vector in [*vectors, *query_vectors]]
        if any(not math.isfinite(n) or abs(n - 1.0) > 1e-5 for n in norms):
            raise ValueError('Finite normalized BGE embeddings required')
        row['embedding'] = {'exact_query_text': query, 'source_ids': [s['source_id'] for s in case['sources']],
            'source_diagnostics': diagnostics, 'query_diagnostics': query_diagnostics,
            'embedding_norm_min': min(norms), 'embedding_norm_max': max(norms),
            'wall_seconds': time.perf_counter() - start}
        bundle['cases'].append({'id': case['id'], 'vectors': vectors.tolist(),
            'query_vector': query_vectors[0].tolist(), 'seed_limit': 1})
    native_result = native_call(bundle, out, deadline, counters, args, progress)
    spec = importlib.util.spec_from_file_location('epoch25_fixed_reader', HERE / 'reader.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reader = module.FixedZeroShotReader(ROOT / plan['reader_model_dir'], counters, progress, deadline)
    for (case, row, texts), native in zip(valid, native_result['cases']):
        if native['case_id'] != case['id'] or len(native['ids']) != 1:
            raise ValueError('Native case/order/top1 changed')
        row['native'] = native
        lexical, scores = evidence.lexical_order(texts, case['query'])
        row['lexical_jaccard_scores'] = scores
        rankings = {'actual_native': native['ids'], 'lexical': lexical, 'positional': list(range(len(texts)))}
        for arm in ARMS:
            remaining(deadline)
            progress({'event': 'ARM_PACK_BEFORE', 'case_id': case['id'], 'arm': arm})
            pack = evidence.pack(case['sources'], rankings[arm])
            arm_row = {'observed_ranking': rankings[arm], 'pack': pack,
                'seed_origin': 'ACTUAL_NATIVE_OBSERVATION' if arm == 'actual_native' else 'MATCHED_CONTROL',
                'reader': None, 'decision': None}
            row['arms'][arm] = arm_row
            token_count = reader.token_count(pack['context'], case['hypothesis'])
            arm_row['validated_total_prompt_tokens'] = token_count
            if type(token_count) is not int or not 0 < token_count <= 512:
                raise ValueError('Total actual Qwen prompt exceeds512; entire source cannot be truncated')
            if pack['guard']['structural_unknown']:
                counters['structural_unknowns'] += 1
                raise ValueError('Main authored source has explicit unit/period ambiguity; no legal inference')
            result = reader.score(pack['context'], case['hypothesis'])
            if result['token_count'] != token_count:
                raise ValueError('Reader token budget changed between check and forward')
            probabilities = result['probabilities']
            if (set(probabilities) != {'entailment', 'contradiction', 'not_mentioned'}
                    or any(not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in probabilities.values())
                    or abs(math.fsum(probabilities.values()) - 1) > 1e-6):
                raise ValueError('Finite normalized conditional label probabilities required')
            if result['prediction'] not in probabilities:
                raise ValueError('Invalid typed reader prediction')
            arm_row['reader'], arm_row['decision'] = result, result['prediction']
            counters['engineering_pairs_completed'] += 1
            progress({'event': 'ARM_COMPLETE', 'case_id': case['id'], 'arm': arm})
        counters['engineering_cases_completed'] += 1
    raw['reader'] = reader.receipt
    if (counters['NLI_model_initializations'] != 1 or counters['NLI_forward_pairs_attempted'] != 18
            or counters['NLI_forward_pairs_completed'] != 18 or counters['NLI_forwards'] != 18
            or counters['engineering_pairs_completed'] != 18 or counters['native_queries_completed'] != 6):
        raise ValueError('Exact one-init18pairs6native count closure failed')
    raw['status'] = 'COMPLETED_ENGINEERING_AWAITING_INDEPENDENT_ORACLE'


ZERO_COUNTERS = ('benchmark_corpora', 'benchmark_questions', 'benchmark_HTTP_requests',
    'TRAIN_calibration_fits', 'CONF_worker_attempts', 'CONF_annotation_choices', 'CONF_NLI_pairs',
    'paid_API_calls', 'GPU_calls', 'fits', 'paid_calls', 'Python_network_operations_attempted',
    'confirmation_calls', 'generation_calls', 'generated_tokens', 'training_steps', 'optimizer_steps')
AUX_ZERO_COUNTERS = ('Node_network_operations_attempted', 'external_API_calls',
    'benchmark_corpus_reads', 'benchmark_label_reads', 'train_calls', 'dev_calls', 'calibration_calls')
COUNTED = ('BGE_initializations_attempted', 'BGE_initializations_completed', 'BGE_forwards_attempted',
    'BGE_forwards_completed', 'BGE_texts_attempted', 'BGE_texts_completed', 'native_helper_starts',
    'native_indexes_completed', 'native_index_initializations_attempted', 'native_queries_attempted',
    'native_queries_completed', 'source_cases_completed', 'automatically_extracted_units',
    'numeric_literals_extracted', 'structural_unknowns', 'NLI_model_initializations',
    'NLI_forward_pairs_attempted', 'NLI_forward_pairs_completed', 'NLI_forwards',
    'NLI_model_initializations_completed', 'NLI_forward_calls_attempted',
    'NLI_forward_calls_completed', 'engineering_pairs_completed', 'engineering_cases_completed')


def main():
    parser = argparse.ArgumentParser()
    for key in ('plan', 'admission', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--expected-plan-sha', required=True)
    parser.add_argument('--deadline', type=float, required=True)
    args = parser.parse_args()
    args.out = args.out.absolute()
    if args.out != STUDY / 'runs/engineering' or args.out.resolve() != args.out:
        raise ValueError('Unsafe output directory')
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    raw = {'schema_version': 1, 'epoch': 25, 'source_checkpoint': SOURCE,
        'plan_sha256': args.expected_plan_sha, 'status': 'INITIALIZING', 'cases': [],
        'source_only_guards': [], 'contract_sha256': None, 'accuracy': None,
        'proper_scores': None, 'benchmark_results': None,
        'roles_used': dict.fromkeys(('train', 'dev', 'calibration', 'confirmation'), []),
        'scope': 'Six authored source-only evidence retrieval/typed zero-shot engineering cases; no benchmark gain or SOTA.',
        'started_at': datetime.now(timezone.utc).isoformat(), 'worker_pid': os.getpid(),
        'worker_pgid': os.getpgid(0), 'errors': [],
        'counters': {**dict.fromkeys(ZERO_COUNTERS + AUX_ZERO_COUNTERS + COUNTED, 0), 'BGE_forward_seconds': 0.0}}
    fd = os.open(args.out / 'progress.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)

    def progress(event):
        status = {}
        try:
            for line in Path('/proc/self/status').read_text().splitlines():
                if line.startswith(('VmRSS:', 'VmHWM:')):
                    name, value, unit = line.split()
                    status[name.rstrip(':') + '_bytes'] = int(value) * 1024
        except OSError:
            pass
        row = {'at_unix': time.time(), 'elapsed_seconds': time.perf_counter() - started,
            'worker_pid': os.getpid(), 'event': event, 'counters': dict(raw['counters']), 'memory': status}
        payload = (json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise RuntimeError('Cannot fsync progress event')
            view = view[written:]
        os.fsync(fd)

    def network_audit(event, arguments):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.bind'):
            raw['counters']['Python_network_operations_attempted'] += 1
            progress({'event': 'OFFLINE_NETWORK_REFUSAL', 'audit_event': event})
            raise RuntimeError('Offline engineering worker refuses network access')
    sys.addaudithook(network_audit)
    code = 0
    progress({'event': 'WORKER_STARTED_NO_MODEL_INITIALIZED'})
    try:
        plan, admission, lock, assets, versions, fixtures, evidence = verify(args)
        raw['contract_sha256'] = fixtures['contract_sha256']
        raw.update(admission=admission, owner_lock=lock, runtime_assets=assets,
            python_versions=versions, fixtures_sha256=plan['fixtures_sha256'],
            reader_assets_lock_sha256=plan['reader_assets_lock_sha256'],
            reader_admission_sha256=plan['reader_admission_sha256'])
        attempt_path = args.out / 'attempt.json'
        while not attempt_path.exists() and remaining(args.deadline) > 0:
            if time.perf_counter() - started > 5:
                raise ValueError('Outer launcher did not seal worker identity')
            time.sleep(.01)
        attempt = read(attempt_path)
        if (attempt.get('pid') != os.getpid() or attempt.get('pgid') != os.getpgid(0)
                or attempt.get('startticks') != int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
                or os.getpgid(0) != os.getpid()):
            raise ValueError('Exact owned worker/group launch identity required')
        raw['preparation_seconds'] = time.perf_counter() - started
        progress({'event': 'ADMISSION_ALL_PINS_AND_EXACT_OWNER_VERIFIED'})
        perform(raw, plan, fixtures, evidence, args.out, args.deadline, args, progress)
        owner_lock(admission)
        remaining(args.deadline)
        if any(raw['counters'][key] != 0 for key in ZERO_COUNTERS + AUX_ZERO_COUNTERS):
            raise ValueError('Forbidden operation counter nonzero')
    except BaseException as error:
        raw['status'] = 'FAILED_ENGINEERING_PROCESS'
        raw['errors'].append({'type': type(error).__name__, 'message': str(error)})
        code = 2
    finally:
        raw.update(wall_seconds_including_initialization_cleanup=time.perf_counter() - started,
            resources=resources(), completed_at=datetime.now(timezone.utc).isoformat())
        progress({'event': 'WORKER_FINAL', 'status': raw['status'], 'errors': raw['errors']})
        write_new(args.out / 'raw.json', raw)
        os.close(fd)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
