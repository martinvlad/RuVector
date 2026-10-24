"""Two independently admitted CPU phases; no ML import occurs at module import."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time
import traceback

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('e30_phase_runtime', HERE / 'runtime/common.py')
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)
A = C.load_module('e30_fixed_algorithm_worker', HERE / 'algorithm.py')
INPUT_SHAS = {'train': 'bf1eff95845e301b56abd1a5284df0dcbbf531b952ea4dd1d89351fef845570a',
    'dev': '5e6ab03f00b6f0581057457ff2a8278113576b1f5ea699895d5126144019aaf4'}
CHOICE_HELPER = 'experiments/sota-2026-10-22/audit/epoch30/train_choices.py'
CHOICE_HELPER_SHA = 'fe90a4608a3d022cfd849bb3aca3af7bf5c98900ac79c26ce9b4c4a7879a3f68'


def expected_counters(phase):
    common = {name: 1 for name in ('BART_initializations_attempted', 'BART_initializations_completed',
        'LoRA_initializations_attempted', 'LoRA_initializations_completed',
        'BGE_initializations_attempted', 'BGE_initializations_completed', 'ORT_sessions_attempted', 'ORT_sessions_completed',
        'native_helper_starts_attempted', 'native_helper_starts_completed', 'native_binary_loads_attempted', 'native_binary_loads_completed',
        'native_version_calls_attempted', 'native_version_calls_completed')}
    common.update({name: 8 for name in ('native_index_initializations_attempted', 'native_index_initializations_completed')})
    common.update({name: 24 for name in ('native_queries_attempted', 'native_queries_completed')})
    common.update({name: 16 for name in ('native_len_calls_attempted', 'native_len_calls_completed')})
    train = {'NLI_forward_calls_attempted': 24, 'NLI_forward_calls_completed': 24,
        'pair_tokenizations_attempted': 24, 'pair_tokenizations_completed': 24,
        'TRAIN_forward_calls_attempted': 24, 'TRAIN_forward_calls_completed': 24,
        'optimizer_initializations_attempted': 1, 'optimizer_initializations_completed': 1,
        'backward_calls_attempted': 24, 'backward_calls_completed': 24,
        'optimizer_steps_attempted': 24, 'optimizer_steps_completed': 24,
        'gradient_clips_attempted': 24, 'gradient_clips_completed': 24,
        'LoRA_B_gradient_checks_attempted': 96, 'LoRA_B_gradient_checks_completed': 96,
        'training_steps': 24, 'parameter_artifacts_write_attempted': 1, 'parameter_artifacts_write_completed': 1,
        'TRAIN_input_bank_reads': 2, 'TRAIN_annotation_choices_attempted': 24, 'TRAIN_annotation_choices_accessed': 24,
        'TRAIN_label_reads': 24, 'TRAIN_contexts_completed': 24, 'fits': 1}
    dev = {'NLI_forward_calls_attempted': 96, 'NLI_forward_calls_completed': 96,
        'pair_tokenizations_attempted': 96, 'pair_tokenizations_completed': 96,
        'original_DEV_forward_calls_attempted': 24, 'original_DEV_forward_calls_completed': 24,
        'adapted_DEV_forward_calls_attempted': 72, 'adapted_DEV_forward_calls_completed': 72,
        'parameter_artifacts_load_attempted': 1, 'parameter_artifacts_load_completed': 1,
        'DEV_input_bank_reads': 1, 'DEV_reads': 1, 'DEV_contexts_completed': 72}
    all_keys = set(common) | set(train) | set(dev)
    selected = {**common, **(train if phase == 'train' else dev)}
    return {key: selected.get(key, 0) for key in sorted(all_keys)}


def status(pid):
    result, observed, races = {}, [], []
    try:
        for line in Path('/proc/' + str(pid) + '/status').read_text().splitlines():
            if line.startswith(('VmRSS:', 'VmHWM:')):
                key, value, _unit = line.split()
                result[key.rstrip(':') + '_bytes'] = int(value) * 1024
            elif line.startswith(('Threads:', 'Cpus_allowed_list:', 'NoNewPrivs:', 'Seccomp:', 'Seccomp_filters:')):
                key, value = line.split(':', 1)
                result[key] = value.strip()
        tasks = list((Path('/proc') / str(pid) / 'task').iterdir())
    except FileNotFoundError:
        tasks = []
    for task in sorted(tasks, key=lambda path: int(path.name)):
        try:
            for line in (task / 'status').read_text().splitlines():
                if line.startswith('Cpus_allowed_list:'):
                    literal = line.split(':', 1)[1].strip()
                    cpus = set()
                    for item in literal.split(','):
                        ends = item.split('-')
                        cpus.update(range(int(ends[0]), int(ends[-1]) + 1))
                    observed.append({'tid': int(task.name), 'Cpus_allowed_list': literal,
                        'observed_affinity_within_CPU0_1': bool(cpus) and cpus <= {0, 1}})
                    break
        except FileNotFoundError:
            races.append(int(task.name))
    result.update(observed_thread_affinities=observed, thread_status_disappearance_races=races,
        observability_scope='Read-only current tasks; helper thread count need not equal2.')
    if any(not row['observed_affinity_within_CPU0_1'] for row in observed):
        error = RuntimeError('Observed thread outside fixed kernel CPU0,1 policy')
        error.observed_process_status = result
        raise error
    return result


def checkpoint(raw, out):
    prior = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM, signal.SIGTERM})
    try:
        pending = out / 'raw.partial.pending.json'
        with pending.open('x', encoding='utf-8') as target:
            json.dump(raw, target, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            target.write('\n')
            target.flush()
            os.fsync(target.fileno())
        os.replace(pending, out / 'raw.partial.json')
        directory = os.open(out, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, prior)


def file_ref(path):
    return {'path': str(path.relative_to(C.ROOT)), 'bytes': path.stat().st_size, 'sha256': C.sha(path)}


def node_events(out, counters, fatal=True):
    path = out / 'node-progress.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    if rows:
        for key in ('Node_network_operations_attempted', 'native_binary_loads_attempted', 'native_binary_loads_completed'):
            counters[key] = rows[-1][key]
    if fatal and counters['Node_network_operations_attempted']:
        raise RuntimeError('Persistent Node network API violation')
    return rows


def run_native(bundle, raw, args, progress):
    counters = raw['counters']
    source, target = args.out / 'native-bundle.json', args.out / 'native-result.json'
    C.put(source, bundle)
    raw['vector_bundle'] = file_ref(source)
    process = identity = None
    stdout = stderr = b''
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='e30-' + args.phase + '-native-', dir=C.ROOT.parent) as scratch:
        raw['native_scratch'] = {'path': scratch, 'outside_public_project': True}
        command = ['node', '--require=' + str(HERE / 'runtime/node_guard.cjs'),
            str(HERE / 'native_helper.cjs'), str(source), str(target)]
        counters['native_helper_starts_attempted'] += 1
        progress({'event': 'NATIVE_HELPER_POPEN_BEFORE', 'argv': command})
        try:
            process = subprocess.Popen(command, cwd=scratch, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            counters['native_helper_starts_completed'] += 1
            identity = C.proc(process.pid)
            if not identity or identity['pgid'] != os.getpgrp() or identity['sid'] != os.getsid(0):
                raise ValueError('Native helper escaped exact owned worker session')
            C.put(args.out / 'native-attempt.json', {'pid': process.pid, 'identity': identity,
                'argv': command, 'source_sha256': C.sha(HERE / 'native_helper.cjs'),
                'bundle_sha256': C.sha(source), 'CPU_policy': 'Inherited whole-worker NNP/seccomp; no affinity reset'})
            stdout, stderr = process.communicate(timeout=min(60, C.remaining(args.deadline)))
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.output or b'', error.stderr or b''
            raise
        finally:
            if process is not None and process.poll() is None:
                current = C.proc(process.pid)
                if not identity or not current or current['ticks'] != identity['ticks']:
                    raise RuntimeError('Cannot prove exact native child PID/ticks for cleanup')
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate(timeout=1)
            (args.out / 'native.stdout').write_bytes(stdout)
            (args.out / 'native.stderr').write_bytes(stderr)
            raw['native_child_closed'] = process is None or process.poll() is not None
            raw['native_child_exit_code'] = process.returncode if process is not None else None
            raw['Node_guard_events'] = node_events(args.out, counters, fatal=False)
            log = args.out / 'native-progress.jsonl'
            if log.exists():
                events = [json.loads(line) for line in log.read_text().splitlines()]
                if events:
                    for key, value in events[-1].items():
                        if key.startswith('native_') and type(value) is int:
                            counters[key] = value
            raw['native_helper_seconds_including_initialization'] = time.perf_counter() - started
            files = []
            for path in sorted(Path(scratch).rglob('*')):
                C.no_symlink(path)
                if path.is_file():
                    files.append({'path': str(path.relative_to(scratch)), 'bytes': path.stat().st_size, 'sha256': C.sha(path)})
            raw['native_scratch']['files_before_owned_cleanup'] = files
        if process.returncode != 0:
            failure = Path(str(target) + '.failure.json')
            if failure.exists():
                raw['native_failure_ref'] = file_ref(failure)
            raise RuntimeError('Genuine native helper failed; complete failure/stdout/stderr retained')
    raw['native_scratch']['removed_after_child_exit'] = not Path(scratch).exists()
    result = C.read(target)
    raw['native_result'] = file_ref(target)
    if (result.get('epoch') != 30 or result.get('kind') != A.KIND or result.get('phase') != args.phase
            or result.get('native') is not True or result.get('bundle_sha256') != C.sha(source)
            or result.get('native_binary_sha256') != C.BINARY_SHA or result.get('helper_pid') != process.pid
            or result.get('source_sha256') != C.sha(HERE / 'native_helper.cjs')
            or result.get('package_version') != '0.1.33' or result.get('platform_package_version') != '0.1.31'
            or result.get('binary_version') != '2.3.0' or result.get('compact_schema') != 'epoch30-native-context-f32le-v1'
            or len(result['documents']) != 8 or result.get('errors') != []):
        raise ValueError('Actual native/source/bundle phase receipt differs')
    for key, value in result.items():
        if key.startswith('native_') and type(value) is int:
            counters[key] = value
    node_events(args.out, counters)
    progress({'event': 'NATIVE_HELPER_CLOSED', 'helper_pid': process.pid})
    return result


def prepare_phase(raw, plan, args, progress, offline):
    counters = raw['counters']
    path = C.checked(plan[args.phase + '_inputs_path'])
    if plan[args.phase + '_inputs_sha256'] != INPUT_SHAS[args.phase] or C.sha(path) != INPUT_SHAS[args.phase]:
        raise ValueError('Wrong fixed phase inputs-only bank')
    counters[args.phase.upper() + '_input_bank_reads'] += 1
    if args.phase == 'dev':
        counters['DEV_reads'] += 1
    bank = C.read(path)
    evidence = C.load_module('e30_pure_evidence', HERE / 'evidence.py')
    records = evidence.validate_inputs(bank, args.phase)
    raw['phase_input_bank'] = file_ref(path)
    offline.assert_clean()
    original = C.load_module('e30_exact_original_safe_reader', C.checked(plan['original_reader_path']))
    model_module = C.load_module('e30_parameter_efficient_model', HERE / 'model.py')
    model = model_module.LegalBartAdapter(original, C.ROOT / plan['bart_model_directory'],
        C.checked(plan['bart_assets_lock_path']), args.phase, counters, progress)
    raw['model_initialization'] = model.runtime_checks
    offline.assert_clean()
    tokenizer = evidence.PairTokenizer(model.tokenizer)
    codec = C.load_module('e30_lossless_BGE_codec', HERE / 'vector_codec.py')
    engine = C.load_module('e30_fixed_source_context_engine', HERE / 'context_engine.py')
    context, documents, bundle, bge_receipt = engine.prepare(C, records, tokenizer, counters, progress, codec)
    offline.assert_clean()
    bundle['phase'] = args.phase
    raw['documents'], raw['BGE'] = documents, bge_receipt
    native = run_native(bundle, raw, args, progress)
    raw['cases'] = engine.pack_all(records, documents, native, args.phase, context, evidence,
        tokenizer, counters, progress)
    offline.assert_clean()
    return model, records


def train(raw, plan, args, progress, offline, model, records):
    counters = raw['counters']
    if len(raw['cases']) != 24 or counters['TRAIN_contexts_completed'] != 24:
        raise ValueError('All label-free native contexts must precede any TRAIN choice access')
    if C.sha(C.checked(CHOICE_HELPER)) != CHOICE_HELPER_SHA:
        raise ValueError('Frozen selective TRAIN extractor changed')
    common_path = C.checked('experiments/sota-2026-10-22/audit/epoch30/data_common.py')
    if 'data_common' in sys.modules and Path(sys.modules['data_common'].__file__).resolve() != common_path:
        raise ValueError('Selective data helper resolved outside frozen epoch30 scope')
    sys.modules['data_common'] = C.load_module('data_common', common_path)
    extractor = C.load_module('e30_selective_TRAIN_choices', C.checked(CHOICE_HELPER))
    source_path = C.ROOT.parent / 'data-source-cache/original-train.json'
    C.no_symlink(source_path)
    def read_choice(case_id):
        index = counters['TRAIN_annotation_choices_attempted']
        if index >= 24 or case_id != A.TRAIN_CASE_IDS[index]:
            raise ValueError('Unexpected source choice field traversal')
        counters['TRAIN_annotation_choices_attempted'] += 1
        counters['TRAIN_label_reads'] += 1
        progress({'event': 'EXACT_TRAIN_CHOICE_FIELD_BEFORE', 'case_id': case_id})
    # The frozen extractor independently parses the same inputs-only TRAIN bank
    # to verify every source identity before its first choice read. Count this
    # second semantic bank-read attempt separately from preparation above.
    counters['TRAIN_input_bank_reads'] += 1
    progress({'event': 'SELECTIVE_HELPER_TRAIN_BANK_REREAD_BEFORE'})
    selected = extractor.extract_train_choices(source_path, C.checked(plan['train_inputs_path']), on_choice=read_choice)
    counters['TRAIN_annotation_choices_accessed'] = len(selected['records'])
    if ([row['id'] for row in selected['records']] != list(A.TRAIN_CASE_IDS)
            or selected['DEV_annotation_choices_accessed'] or selected['CONF_annotation_choices_accessed']
            or selected['other_role_annotation_choices_accessed'] or selected['source_evidence_lists_accessed']):
        raise ValueError('Only exact TRAIN24 choices may enter fitting')
    raw['choice_read_receipt'] = {key: value for key, value in selected.items() if key != 'records'}
    raw['choice_read_receipt']['selected'] = [{key: row[key] for key in ('id', 'document_id', 'hypothesis_id', 'input_sha256')}
        for row in selected['records']]
    raw['TRAIN_class_counts'] = {name: sum(row['source_choice'] == name for row in selected['records'])
        for name in ('Entailment', 'Contradiction', 'NotMentioned')}
    targets = {row['id']: row['native_target_index'] for row in selected['records']}
    counters['fits'] += 1
    for case in raw['cases']:
        C.remaining(args.deadline)
        arm = case['arms']['actual_native']
        step = {'id': case['id'], 'context_ref': {'case_id': case['id'], 'arm': 'actual_native'}, 'reader': {}}
        raw['steps'].append(step)
        offline.assert_clean()
        model.train_step(case['id'], arm['premise'], case['hypothesis'], targets[case['id']], step['reader'])
        if step['reader']['pair_tokens'] != arm['joint_pair_tokens']:
            raise ValueError('Actual TRAIN native pair differs from frozen context')
        offline.assert_clean()
    artifact_path = args.out / 'trained-parameters.public.json'
    reference, integrity = model.export_artifact(artifact_path, args.expected_plan_sha, plan['train_inputs_sha256'])
    reference['path'] = str(artifact_path.relative_to(C.ROOT))
    raw['parameter_artifact'], raw['train_integrity'] = reference, integrity
    raw['status'] = 'COMPLETED_TRAIN_AWAITING_INDEPENDENT_MODEL_SEAL'


def dev(raw, plan, args, progress, offline, model, admission):
    for case in raw['cases']:
        C.remaining(args.deadline)
        arm = case['arms']['actual_native']
        receipt = {}
        arm['reader']['original'] = receipt
        offline.assert_clean()
        model.score_original(arm['premise'], case['hypothesis'], receipt)
        if receipt['pair_tokens'] != arm['joint_pair_tokens']:
            raise ValueError('Original DEV native input differs from frozen context')
        offline.assert_clean()
    if model.original_valid_count != 24:
        raise ValueError('All original24 native outputs must precede trained tensor decoding')
    ref = admission['parameter_artifact']
    path = C.checked(ref['path'])
    raw['adapted_state_load'] = model.load_adaptation(path, ref['sha256'], args.expected_plan_sha, plan['train_inputs_sha256'])
    for case in raw['cases']:
        for arm_name in ('actual_native', 'lexical', 'positional'):
            C.remaining(args.deadline)
            arm = case['arms'][arm_name]
            receipt = {}
            arm['reader']['adapted'] = receipt
            offline.assert_clean()
            model.score_adapted(arm['premise'], case['hypothesis'], receipt)
            if receipt['pair_tokens'] != arm['joint_pair_tokens']:
                raise ValueError('Adapted DEV true pair differs from frozen context')
            if arm_name == 'actual_native' and any(receipt[key] != arm['reader']['original'][key]
                    for key in ('native_pair_input_ids_sha256', 'premise_sha256', 'hypothesis_sha256', 'pair_tokens')):
                raise ValueError('Paired original/adapted native contexts are not byte/token identical')
            offline.assert_clean()
    raw['loaded_parameter_artifact'] = model.loaded_artifact
    raw['status'] = 'COMPLETED_DEV_AWAITING_INDEPENDENT_GOLD_JOIN'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('train', 'dev'), required=True)
    for name in ('plan', 'admission', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--expected-plan-sha', required=True)
    parser.add_argument('--deadline', type=float, required=True)
    args = parser.parse_args()
    if args.out.absolute() != C.STUDY / 'runs' / args.phase or args.out.resolve() != args.out.absolute():
        raise ValueError('Wrong phase output directory')
    C.no_symlink(args.out)
    started = time.monotonic()
    expected = expected_counters(args.phase)
    raw = {'schema_version': 1, 'epoch': 30, 'kind': A.KIND, 'phase': args.phase,
        'source_checkpoint': C.SOURCE, 'plan_sha256': args.expected_plan_sha, 'status': 'INITIALIZING',
        'worker_pid': os.getpid(), 'worker_identity': C.proc(os.getpid()), 'cases': [], 'steps': [], 'errors': [],
        'data_roles': {'train': list(A.TRAIN_DOCUMENT_IDS), 'dev': list(A.DEV_DOCUMENT_IDS), 'calibration': [], 'confirmation': []},
        'benchmark_accepted': False, 'champion_promoted': False, 'new_submission': False,
        'confirmation': [], 'calibration': [], 'benchmark_accuracy': None, 'proper_scores': None,
        'NLI_scope': 'Full native C/N/E head,T1; matched fixed source contexts; net LoRA+existing-head adaptation, not exclusive attention causality.',
        'counters': {**dict.fromkeys(set(expected) | set(C.phase_zero(args.phase)), 0),
            'BGE_forward_calls_attempted': 0, 'BGE_forward_calls_completed': 0, 'BGE_texts_attempted': 0,
            'BGE_texts_completed': 0, 'BGE_forward_seconds': 0.0, 'automatically_extracted_units': 0,
            'native_insertions_attempted': 0, 'native_insertions_completed': 0, 'native_hit_source_validations': 0,
            'Python_literal_loopback_capability_binds_allowed': 0}}
    stream = (args.out / 'progress.jsonl').open('xb')
    def progress(event):
        row = {'at_unix': time.time(), 'elapsed_seconds': time.monotonic() - started,
            'event': event, 'counters': dict(raw['counters']), 'process': status(os.getpid())}
        stream.write((json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())
        checkpoint(raw, args.out)
    offline = C.load_module('e30_phase_network_policy', HERE / 'runtime/network_guard.py').OfflineGuard(raw['counters'], progress).install()
    def stop(signum, frame):
        raise TimeoutError('Bounded E30 phase stop signal: ' + str(signum))
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGALRM, stop)
    code = 0
    try:
        C.remaining(args.deadline)
        signal.setitimer(signal.ITIMER_REAL, max(.001, C.remaining(args.deadline) - 7))
        cpu = status(os.getpid())
        if os.sched_getaffinity(0) != {0, 1} or cpu.get('NoNewPrivs') != '1' or cpu.get('Seccomp') != '2':
            raise ValueError('Whole-worker CPU0,1/NNP/seccomp required before Torch/ORT')
        if args.plan.absolute() != C.STUDY / 'plan.json' or C.sha(args.plan) != args.expected_plan_sha:
            raise ValueError('Unknown exact source plan')
        provisional = C.read(args.plan)
        admission, owner = C.admission(args.admission, provisional, args.expected_plan_sha, args.phase)
        plan = C.verify_plan(args.plan, args.expected_plan_sha, args.phase)
        C.verify_runtime(plan)
        if plan.get('training_algorithm') != A.ALGORITHM:
            raise ValueError('Fixed premeasurement algorithm differs from source plan')
        if any(plan['expected_operation_counters'][args.phase].get(key) != value for key, value in expected.items()):
            raise ValueError('Fixed phase counter table differs from source')
        attempt_path = args.out / 'attempt.json'
        while not attempt_path.exists():
            C.remaining(args.deadline)
            if time.monotonic() - started > 15:
                raise ValueError('Outer phase worker identity not sealed')
            time.sleep(.01)
        attempt, current = C.read(attempt_path), C.proc(os.getpid())
        if (attempt.get('pid') != os.getpid() or attempt.get('pgid') != os.getpid() or attempt.get('sid') != os.getpid()
                or attempt.get('startticks') != current['ticks'] or current['pgid'] != os.getpid() or current['sid'] != os.getpid()):
            raise ValueError('Exact phase PID/ticks/session identity missing')
        cpu_file = args.out / 'worker-cpu-preexec.json'
        raw.update(admission=admission, owner_lock=owner, source_freeze_sha256=plan['source_freeze_sha256'],
            worker_cpu_guard_preexec=C.read(cpu_file), worker_cpu_guard_preexec_artifact=file_ref(cpu_file),
            CPU_policy_before_model_import=cpu)
        progress({'event': 'ALL_PHASE_SOURCE_MODEL_RUNTIME_CPU_GATES_BEFORE_ML'})
        offline.assert_clean()
        model, records = prepare_phase(raw, plan, args, progress, offline)
        if args.phase == 'train':
            train(raw, plan, args, progress, offline, model, records)
        else:
            dev(raw, plan, args, progress, offline, model, admission)
        C.verify_plan(args.plan, args.expected_plan_sha, args.phase)
        C.verify_runtime(plan)
        C.owner_lock(admission)
        C.remaining(args.deadline)
        offline.assert_clean()
        if any(raw['counters'][key] != value for key, value in expected.items()) or any(raw['counters'][key] for key in C.phase_zero(args.phase)):
            raise ValueError('Exact finite phase operation counts/zero-forbidden closure failed')
        if not raw.get('native_child_closed') or raw['errors']:
            raise ValueError('Phase errors or unclosed native helper remain')
    except BaseException as error:
        raw['status'] = 'FAILED_TRAIN' if args.phase == 'train' else 'FAILED_DEV'
        raw['errors'].append({'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()})
        if hasattr(error, 'observed_process_status'):
            raw['CPU_affinity_violation_snapshot'] = error.observed_process_status
        code = 2
    finally:
        signal.signal(signal.SIGALRM, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.setitimer(signal.ITIMER_REAL, 0)
        own, child = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
        raw.update(completed_at=datetime.now(timezone.utc).isoformat(),
            wall_seconds_including_initialization_cleanup=time.monotonic() - started,
            Python_network_events=offline.events, Python_network_violations=offline.violations,
            resources={'CPU_affinity': sorted(os.sched_getaffinity(0)), 'worker': status(os.getpid()),
                'worker_user_seconds': own.ru_utime, 'worker_system_seconds': own.ru_stime,
                'worker_peak_RSS_bytes': own.ru_maxrss * 1024, 'child_user_seconds': child.ru_utime,
                'child_system_seconds': child.ru_stime, 'largest_child_peak_RSS_bytes': child.ru_maxrss * 1024,
                'memory_scope': 'Separate high-water observations, not simultaneous summed RSS.'})
        try:
            progress({'event': 'WORKER_FINAL', 'phase': args.phase, 'status': raw['status'], 'errors': raw['errors']})
        except BaseException as error:
            raw['status'] = 'FAILED_TRAIN' if args.phase == 'train' else 'FAILED_DEV'
            raw['errors'].append({'stage': 'final_checkpoint', 'type': type(error).__name__, 'message': str(error)})
            code = 2
        pending = args.out / 'raw.partial.pending.json'
        if pending.is_file():
            raw['leftover_partial_checkpoint'] = {**file_ref(pending), 'retained_without_overwrite': True}
        C.put(args.out / 'raw.json', raw)
        stream.close()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
