"""One stat-only canonical qualification; no version/model/native lookup."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source'))
from inherited_guards import NetworkAudit
from io_guard import DeniedOpenAudit
from search_policy import canonical_fingerprint


def main():
    p=argparse.ArgumentParser();p.add_argument('--probe',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    if sorted(os.sched_getaffinity(0))!=[0,1]:raise ValueError('CPU_AFFINITY_0_1')
    started=time.monotonic();counters=Counter();network=NetworkAudit(counters)
    sys.addaudithook(network);network.install_socket_guards();guard=DeniedOpenAudit(counters);sys.addaudithook(guard)
    probe_bytes=Path(a.probe).read_bytes();probe=json.loads(probe_bytes)
    events=probe['denied_open_audit']['events']
    if not(len(events)==6 and len({e['path_sha256'] for e in events})==1
           and all(e['exists'] is False and e['inside_interpreter_base_prefix'] and e['suffix']=='.zip'
                   and e['sys_path_indices']==[1] for e in events)):
        raise ValueError('EXACT_E55_METADATA_PROBE_REQUIRED')
    row={'sys_path_index':1,**canonical_fingerprint(sys.path[1])}
    if not(row['path_sha256']==events[0]['path_sha256'] and row['exists'] is False
           and row['canonical_inside_interpreter_base_prefix'] and row['standard_interpreter_zip_basename']):
        raise ValueError('EXACT_CANONICAL_ABSENT_INTERPRETER_ZIP')
    value={'schema_version':1,'epoch':55,'kind':'EXACT_INTERPRETER_SEARCH_ENTRY_STAT_ONLY_QUALIFICATION',
           'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'probe_ref':{'path':a.probe,'bytes':len(probe_bytes),'sha256':hashlib.sha256(probe_bytes).hexdigest()},
           'entries':[row],'sys_path_unchanged':True,'archive_opens_authorized':False,
           'actual_metadata_version_calls':0,'actual_tokenizer_BGE_model_native_calls':0,
           'Gold_train_calibration_paid_GPU_calls':0,'network_audit':network.receipt(),'denied_open_audit':guard.receipt(),
           'CPU_affinity':sorted(os.sched_getaffinity(0)), 'max_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
           'wall_seconds':time.monotonic()-started,
           'runtime_modules_loaded':sorted(set(sys.modules)&{'numpy','torch','onnxruntime','tokenizers','transformers','safetensors'}),
           'scope':'Only current E55 exact interpreter entry; no historical E54 event attribution.'}
    if value['runtime_modules_loaded'] or guard.receipt()['denied_attempts'] or network.receipt()['event_counts']:
        raise ValueError('NO_SCIENCE_ARCHIVE_OR_NETWORK_IN_STAT_QUALIFICATION')
    b=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode();out=Path(a.out)
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        if os.write(fd,b)!=len(b):raise ValueError('COMPLETE_STAT_RESULT')
        os.fsync(fd)
    finally:os.close(fd)
    print(json.dumps({'path':str(out),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'entries':value['entries']}))


if __name__=='__main__':main()
