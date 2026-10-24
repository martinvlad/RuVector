"""Synthetic post-reservation CPU-prepare failure; all admission gates mocked.

This tests error preservation only and cannot admit or start the real worker.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('--runtime', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
spec = importlib.util.spec_from_file_location('synthetic_startup_capture', args.runtime/'launch.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
C = launcher.C
original = {key:getattr(C,key) for key in ('ROOT','STUDY','CANDIDATE','owner_lock','admission','verify_plan','verify_runtime','load_module')}
argv = sys.argv[:]
handlers = {sig:signal.getsignal(sig) for sig in (signal.SIGTERM,signal.SIGINT)}
affinity = os.sched_getaffinity(0)
Popen = launcher.subprocess.Popen
attempted = []

def no_popen(*a, **kw):
    attempted.append(True)
    raise AssertionError('Synthetic CPU-prepare fault must precede Popen')

def fail_cpu(*a, **kw):
    raise RuntimeError('INJECTED_CPU_PREPARE_FAILURE_BEFORE_POPEN')

try:
    with tempfile.TemporaryDirectory(prefix='startup-capture-',dir=args.output.parent) as temporary:
        scope = Path(temporary)
        C.ROOT = scope/'project'
        C.CANDIDATE = C.ROOT/'experiments/sota-2026-10-22/candidate/epoch29'
        C.STUDY = C.ROOT/'experiments/sota-2026-10-22/epoch29'
        C.STUDY.mkdir(parents=True)
        (scope/'owner.json').write_text(json.dumps({'expires_unix':time.time()+3600}))
        plan = {'source_freeze_sha256':'a'*64,
            'worker_path':str((C.CANDIDATE/'worker.py').relative_to(C.ROOT)),
            'inference_python':sys.executable,'expected_operation_counters':{'native_queries_completed':1}}
        plan_path = C.STUDY/'plan.json'
        plan_path.write_text(json.dumps(plan))
        C.owner_lock = lambda *a: {}
        C.admission = lambda *a: ({}, {})
        C.verify_plan = lambda *a: plan
        C.verify_runtime = lambda *a: None
        C.load_module = fail_cpu
        launcher.subprocess.Popen = no_popen
        sys.argv = [str(args.runtime/'launch.py'),'--scope',str(scope),'--plan',str(plan_path),
            '--admission',str(C.STUDY/'NATIVE_ADMISSION.json'),'--expected-plan-sha',C.sha(plan_path)]
        with contextlib.redirect_stdout(io.StringIO()):
            result = launcher.main()
        receipt = C.read(C.STUDY/'execution.json')
        assert result == 2 and attempted == []
        assert receipt['status'] == 'WORKER_FAILED_OR_TIMEOUT'
        assert receipt['worker_attempts_reserved'] == 1 and receipt['verified_worker_starts'] == 0
        assert receipt['uncertain_start'] is False and receipt['worker_identity'] is None
        assert receipt['launcher_error']['message'] == 'INJECTED_CPU_PREPARE_FAILURE_BEFORE_POPEN'
        assert receipt['raw_operation_counters_source'] == 'UNKNOWN' and receipt['raw_operation_counters'] is None
        assert receipt['worker_cpu_guard_preexec_artifact'] is None and receipt['worker_cpu_guard_preexec'] is None
        assert receipt['owned_live_processes_closed'] is True
        assert (C.STUDY/'ATTEMPT_RESERVATION.json').is_file()
        try:
            launcher.reserve(C.STUDY,'a'*64)
        except (RuntimeError,FileExistsError):
            pass
        else:
            raise AssertionError('Failed startup reservation became retryable')
finally:
    for key,value in original.items():setattr(C,key,value)
    sys.argv = argv
    launcher.subprocess.Popen = Popen
    for sig,handler in handlers.items():signal.signal(sig,handler)
    os.sched_setaffinity(0,affinity)
assert not any(x in sys.modules for x in ('torch','transformers','numpy','onnxruntime','tokenizers'))
source = args.runtime/'launch.py'
report={'status':'PASS_SYNTHETIC_POSTRESERVATION_CPU_PREPARE_FAILURE_CAPTURE','launcher_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'all_admission_gates_mocked_for_test_only':True,
    'Popen_calls':0,'reservation_preserved':True,'execution_failure_retained':True,'absent_raw_counts':'UNKNOWN',
    'parent_affinity_restored':os.sched_getaffinity(0)==affinity,'actual_engineering_workers':0,
    'model_tokenizer_native_initializations':0,'data_or_choices_reads':0}
with args.output.open('x') as stream:json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
print(json.dumps({'report':str(args.output),'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))
