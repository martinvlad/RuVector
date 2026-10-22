"""One bounded owned process group, cleanup within600s, preserve every outcome."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from save_attempt import save

HERE=Path(__file__).resolve().parent

def main():
    name=sys.argv[1]
    if name not in ['round1','round2']:raise ValueError('Finite two-round cycle only')
    directory=HERE/name
    if (directory/'supervisor-terminal.json').exists() or (directory/'launch-receipt.json').exists():raise ValueError('Never replace an attempted round')
    os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);started=time.monotonic();timed_out=False
    environment={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','RAYON_NUM_THREADS':'2'}
    with (directory/'worker.log').open('x') as log:
        worker=subprocess.Popen([sys.executable,str(HERE/'run.py'),'--round',name],stdout=log,stderr=subprocess.STDOUT,env=environment,start_new_session=True)
        try:worker.wait(timeout=595)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(worker.pid,signal.SIGTERM)
            try:worker.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(worker.pid,signal.SIGKILL);worker.wait(timeout=1)
        finally:
            if worker.poll() is None:os.killpg(worker.pid,signal.SIGKILL);worker.wait(timeout=1)
    observed={'worker':worker.pid};native_file=directory/'native-process.json'
    if native_file.exists():observed['native']=json.loads(native_file.read_text())['pid']
    absent={name:not Path('/proc',str(pid)).exists() for name,pid in observed.items()}
    terminal={'status':'completed' if worker.returncode==0 and not timed_out else 'failed_execution','at':datetime.now(timezone.utc).isoformat(),'worker_returncode':worker.returncode,'timeout':timed_out,'elapsed_seconds':time.monotonic()-started,'max_seconds':600,'CPU_affinity':sorted(os.sched_getaffinity(0)),'observed_PIDs':observed,'processes_absent':absent,'new_paid_calls':0}
    (directory/'supervisor-terminal.json').write_text(json.dumps(terminal,indent=2)+'\n')
    receipt=save(directory);print(json.dumps({'terminal':terminal,'artifact':receipt['artifact']},indent=2))
    if terminal['status']!='completed' or not all(absent.values()):raise SystemExit(1)

if __name__=='__main__':main()
