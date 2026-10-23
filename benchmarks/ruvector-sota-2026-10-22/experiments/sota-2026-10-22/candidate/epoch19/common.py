"""Epoch19 source/identity protocol and pure engineering vector arithmetic."""
from __future__ import annotations
import hashlib
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
PREFIX='experiments/sota-2026-10-22/'
STUDY=ROOT/PREFIX/'epoch19'
SOURCE='6eb624feef9ea93c3b1a8f76c20e8442c6bece50'
STUDY_ID='native-semantic-precision-qualification-e19'
SPEC_PATH=PREFIX+'epoch18/reporting/SEMANTIC_PRECISION_QUALIFICATION_SPEC.json'
SPEC_SHA='93564659aa991dc85a6ee129cc5ab2964946f26696b987352006dcde648f74ae'
FIXTURES_PATH=PREFIX+'legal-transfer/epoch19/canaries.json'
FIXTURES_SHA='4bd2e363117600603d6f215813bd77ea0f62acedb8c399700e8ae210161c7820'
NATIVE_SCRIPT='retrieval/native-candidates.cjs'
NATIVE_SCRIPT_SHA='45efc7fecd2d249aea7bd1f5e7d36bf26cfe57cd6f91de51ffd15adc039ec4a3'
NATIVE_BINARY_SHA='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
VOCAB=('lamp','on','not','box','blue')
LIMITS={'native_batches':1,'worker_attempts':1,'threads':2,'interop_threads':1,
 'seconds_per_batch':600,'seconds_per_decision':30,'candidate_configs':1,'paid_calls':0,
 'GPU_calls':0,'nli_forwards':6,'native_invocations':1,'native_queries':3,
 'other_model_forwards':0,'benchmark_corpora':0}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def checked(relative,root=ROOT):
    if not isinstance(relative,str)or not relative or '\\'in relative or PurePosixPath(relative).is_absolute()or any(p in ('','.','..')for p in relative.split('/')):
        raise ValueError('Unsafe protocol/source path')
    path=Path(root)/relative
    if any(p.is_symlink()for p in (path,*path.parents))or not path.is_file():raise ValueError('Missing/nonregular source: '+relative)
    return path


def read(path):return json.loads(Path(path).read_text())
def write_new(path,value):
    with Path(path).open('x')as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def replace_report(path,value):
    temporary=Path(str(path)+'.tmp')
    with temporary.open('w')as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)


def inherited_verifier():
    path=checked(PREFIX+'controller/epoch3_loop.py')
    if sha(path)!='0b4ac6af58b4f421681d5b62d3243d17cc8c8426c47ee738a36eaae195d388d1':raise ValueError('Inherited verifier source changed')
    spec=importlib.util.spec_from_file_location('epoch19_unchanged_primitives',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def fixtures(plan):
    spec=read(checked(plan['spec_path']));data=read(checked(plan['fixtures_path']))
    rows=spec['engineering_canaries']['fixtures']
    if data['fixtures']!=rows or data.get('new_benchmark_inputs_or_labels')!=0 or any(data['benchmark_roles'].values()):raise ValueError('Only unchanged public engineering canaries allowed')
    if len(rows)!=3 or [r['id']for r in rows]!=['semantic-e-v1','semantic-c-v1','semantic-n-v1']:raise ValueError('Fixed three engineering identities required')
    for row in rows:
        core={k:row[k]for k in ('id','premise','hypothesis','expected_typed_label')}
        raw=json.dumps(core,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Canary text/label identity changed')
    return rows


def require_plan(path,expected=None):
    if expected is not None and sha(path)!=expected:raise ValueError('Actual plan bytes changed')
    plan=read(path)
    if plan.get('epoch')!=19 or plan.get('schema_version')!=1 or plan.get('source_checkpoint')!=SOURCE or plan.get('study_id')!=STUDY_ID:raise ValueError('Wrong independently scoped qualification plan')
    if any(type(plan['limits'].get(k))is not int or plan['limits'][k]!=v for k,v in LIMITS.items()):raise ValueError('Exact engineering resource budget required')
    if plan.get('actual_project')!=str(ROOT)or any(plan.get(k)for k in ('train','calibration','datasets','confirmation')):raise ValueError('No benchmark role, training or calibration input is allowed')
    pins=plan['pins'];by_path={r['path']:r['sha256']for r in pins}
    if len(by_path)!=len(pins):raise ValueError('Duplicate source pin')
    # Actual, unchanged full legacy verifier: hashes every pin and checks CPU/time.
    inherited_verifier().verify_plan(plan)
    for key,required_path,required_sha in [('spec',SPEC_PATH,SPEC_SHA),('fixtures',FIXTURES_PATH,FIXTURES_SHA)]:
        if plan[key+'_path']!=required_path or plan[key+'_sha256']!=required_sha:raise ValueError('Published frozen spec/fixtures changed')
    for key in ('spec','fixtures','native_addendum','model_assets_lock','wheel_lock','native_closure','source_freeze'):
        rel=plan[key+'_path'];expected_sha=plan[key+'_sha256']
        if by_path.get(rel)!=expected_sha or sha(checked(rel))!=expected_sha:raise ValueError('Unpinned protocol artifact: '+key)
    ref=plan['audit_protocol']
    if by_path.get(ref['path'])!=ref['sha256']or sha(checked(ref['path']))!=ref['sha256']:raise ValueError('Independent qualification protocol not frozen')
    if by_path.get(NATIVE_SCRIPT)!=NATIVE_SCRIPT_SHA:raise ValueError('Exact native helper required')
    snapshot=read(checked(plan['source_freeze_path']))
    if snapshot.get('source_checkpoint')!=SOURCE:raise ValueError('Current-source snapshot required')
    for row in snapshot['files']:
        file=checked(row['path'])
        if file.stat().st_size!=row['bytes']or by_path.get(row['path'])!=row['sha256']or sha(file)!=row['sha256']:raise ValueError('Frozen source member changed')
    if not math.isfinite(plan['lease_expires_unix']):raise ValueError('Finite lease required')
    fixtures(plan)
    return plan


def verify_owner_lock(value):
    owner=value['owner_pid'];ticks=value['owner_start_ticks'];inode=value['lock_inode']
    if any(type(v)is not int or v<1 for v in (owner,ticks,inode)):raise ValueError('Exact owner PID/start/inode required')
    state=Path('/proc/'+str(owner)+'/stat').read_text().rsplit(')',1)[1].split()
    if state[0]in ('Z','X')or int(state[19])!=ticks:raise ValueError('Owner exited or PID identity changed')
    lock=Path(value['lock_path'])
    if not lock.is_absolute()or any(p.is_symlink()for p in (lock,*lock.parents)):raise ValueError('Absolute nonsymlink work lock required')
    fd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        actual=os.fstat(fd)
        if not stat.S_ISREG(actual.st_mode)or actual.st_ino!=inode:raise ValueError('Exact regular work-lock inode required')
        identity=(os.major(actual.st_dev),os.minor(actual.st_dev),inode)
        active=False
        for line in Path('/proc/locks').read_text().splitlines():
            parts=line.split()
            if len(parts)<8 or parts[1:4]!=['FLOCK','ADVISORY','WRITE']or parts[4]!=str(owner):continue
            major,minor,entry_inode=parts[5].split(':')
            if (int(major,16),int(minor,16),int(entry_inode))==identity:active=True
        if not active:raise ValueError('Exact owner has no active kernel FLOCK on work lock')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        fcntl.flock(fd,fcntl.LOCK_UN)
        raise ValueError('Exclusive work-lock contender unexpectedly acquired lock')
    finally:os.close(fd)


def verify_admission(path,plan_sha):
    path=Path(path).absolute()
    if path!=STUDY/'NATIVE_ADMISSION.json' or path.is_symlink():raise ValueError('Exact late native admission path required')
    value=read(path)
    if value.get('lock_path')!=str(ROOT.parent.parent/'exclusive.work.lock'):raise ValueError('Exact RuVector research work-lock scope required')
    if any(value.get(k)is not True for k in ('checks_passed','independent_remote_readback_passed','exclusive_lock_held'))or value.get('plan_sha256')!=plan_sha:
        raise ValueError('Matching published-source/lock admission required')
    proof=checked(value['readback_path'])
    if sha(proof)!=value['independent_readback_sha256']:raise ValueError('Independent readback identity changed')
    remote=read(proof)
    if remote.get('independent_remote_readback_passed')is not True or remote.get('commit')!=value['source_commit']:raise ValueError('Actual published source readback required')
    verify_owner_lock(value)
    return value


def engineering_vectors(rows):
    def vector(text):
        tokens=re.findall('[a-z]+',text.lower())
        return [tokens.count(word)for word in VOCAB]+[0]*379
    documents=[vector(row['premise'])for row in rows];queries=[vector(row['hypothesis'])for row in rows]
    ranks=[];lexical=[];cosines=[]
    for query_row,q in zip(rows,queries):
        scores=[math.fsum(a*b for a,b in zip(v,q))/math.sqrt(math.fsum(a*a for a in v)*math.fsum(b*b for b in q))for v in documents]
        cosines.append(scores);ranks.append(sorted(range(3),key=lambda i:(-scores[i],i)))
        qt=re.findall('[a-z]+',query_row['hypothesis'].lower())
        overlap=[sum(min(qt.count(word),re.findall('[a-z]+',row['premise'].lower()).count(word))for word in set(qt))for row in rows]
        lexical.append(sorted(range(3),key=lambda i:(-overlap[i],i)))
    return {'vectors':documents,'query_vectors':queries}, {'cosine_similarity':cosines,'cosine_distance':[[1-x for x in row]for row in cosines],
        'cosine_order':ranks,'lexical_order':lexical,'lexical_formula':'Lowercase ASCII [a-z]+ all-word multiset overlap sum(min(query_count,document_count)); descending overlap, ascending declared source ID',
        'tokenization':'re.findall([a-z]+, text.lower())','vocabulary':list(VOCAB),'dimensions':384,'native_selection_affects_NLI':False}
