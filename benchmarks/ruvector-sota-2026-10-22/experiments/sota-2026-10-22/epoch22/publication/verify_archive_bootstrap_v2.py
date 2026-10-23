"""Cold source restoration through the reviewed archive hook and bootstrap."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, sys, time

P='experiments/sota-2026-10-22/'
RAW=P+'epoch22/runs/dev/raw.json'
BOOT='eceb2ca259feaf642bc81172aca57a2a209cc34cd17f9b281861c51f21b95806'
RESTORE='affd9ecf660f380c3632f78cd14fb7a36e00797ceb097cf48c0c60136fac0be8'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_bytes())
def checked(p,directory=False):
    p=Path(p).absolute();assert p==p.resolve()
    assert not any(x.is_symlink() for x in [p,*p.parents])
    assert p.is_dir() if directory else p.is_file()
    return p
def safe(root,n):
    assert isinstance(n,str) and n and '\\' not in n
    assert not Path(n).is_absolute() and not any(x in ('','.','..') for x in n.split('/'))
    p=root/n;assert p.resolve().is_relative_to(root)
    assert not any(x.is_symlink() for x in [p,*p.parents])
    return p
def put(p,v):
    with p.open('x') as f:
        json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def main():
    os.sched_setaffinity(0,{0,1})
    ap=argparse.ArgumentParser()
    for n in ('project','kit','controls-dir','work','out'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();r=checked(a.project,True);oldkit=checked(a.kit,True);c=checked(a.controls_dir,True)
    work=a.work.absolute();out=a.out.absolute()
    for p in (work,out):
        assert p==p.resolve() and not os.path.lexists(p)
        assert not any(x.is_symlink() for x in p.parents)
    assert not work.is_relative_to(r) and not work.is_relative_to(oldkit)
    assert out.parent==r/P/'epoch22/publication'
    cp=read(c/'CHECKPOINT_MANIFEST.json');cont=read(c/'CONTINUATION.json');at=cont['artifact_transport']
    assert sha(c/'CHECKPOINT_MANIFEST.json')==cont['checkpoint_manifest_sha256']
    assert sha(oldkit/'bootstrap.py')==BOOT and sha(oldkit/'restore_checkpoint.py')==RESTORE
    assert at['required_before_bootstrap'] is True and at['restored_artifact']['path']==RAW
    rows={x['path']:x for x in cp['project_files']}
    for original in read(oldkit/'KIT_MANIFEST.json')['project_files']:
        x={k:original[k] for k in ('path','bytes','sha256')}
        assert x['path'] not in rows or rows[x['path']]==x;rows[x['path']]=x
    bm={x['path']:x for x in read(oldkit/'BASE_PUBLIC_MANIFEST.json')['files']}
    for n in read(oldkit/'BASE_DOWNLOADS.json')['paths']:
        x={k:bm[n][k] for k in ('path','bytes','sha256')}
        assert n not in rows or rows[n]==x;rows[n]=x
    need=sum(x['bytes'] for x in rows.values())+rows[RAW]['bytes']+24*1024*1024
    assert shutil.disk_usage(work.parent).free>need,'Insufficient space; cold test not started'
    started=time.monotonic();work.mkdir(mode=0o700);kit=work/'kit';dest=work/'project';kit.mkdir()
    # Actual fresh kit is assembled from exact bytes, excluding decoded RAW.
    # Hard links avoid redundant staging copies; every source is verified first.
    for n,x in rows.items():
        if n==RAW:continue
        source=checked(safe(r,n));assert source.stat().st_size==x['bytes'] and sha(source)==x['sha256']
        target=safe(kit,n);target.parent.mkdir(parents=True,exist_ok=True);os.link(source,target)
    for n in ('bootstrap.py','restore_checkpoint.py','KIT_MANIFEST.json','BASE_PUBLIC_MANIFEST.json','BASE_DOWNLOADS.json'):
        shutil.copyfile(checked(oldkit/n),kit/n)
    for n in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'):
        shutil.copyfile(checked(c/n),kit/n)
    assert not (kit/RAW).exists() and not dest.exists()
    env=dict(os.environ);env.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',
        OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',RAYON_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false')
    commands=[
        [sys.executable,'-B',str(kit/at['extractor']['path']),'--kit-root',str(kit),
         '--archive',at['archive']['path'],'--expected-archive-sha256',at['archive']['sha256']],
        [sys.executable,'-B',str(kit/'bootstrap.py'),'--dest',str(dest),'--base-local-directory',str(r)],
        [sys.executable,'-B',str(kit/'restore_checkpoint.py'),'--dest',str(dest),'--base-local-directory',str(r)],
        [sys.executable,'-B',str(kit/'restore_checkpoint.py'),'--dest',str(dest),
         '--base-local-directory',str(r),'--verify-only']]
    results=[]
    for i,cmd in enumerate(commands):
        put(work/('command-'+str(i)+'.intent.json'),{'argv':cmd,'native_model_parser_gold_calls':0})
        t=time.monotonic();q=subprocess.run(cmd,cwd=kit,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
        row={'argv':cmd,'exit_code':q.returncode,'elapsed_seconds':time.monotonic()-t,
            'stdout':q.stdout.decode(),'stderr':q.stderr.decode()}
        put(work/('command-'+str(i)+'.result.json'),row);results.append(row)
        assert q.returncode==0,row
    for n,x in rows.items():
        target=checked(safe(dest,n));assert target.stat().st_size==x['bytes'] and sha(target)==x['sha256'],n
    assert sha(dest/RAW)==at['restored_artifact']['sha256'] and sha(kit/RAW)==at['restored_artifact']['sha256']
    result={'schema_version':1,'epoch':22,'status':'ACTUAL_COLD_ARCHIVE_THEN_UNCHANGED_BOOTSTRAP_RESTORE_VERIFY_PASS',
        'checks_passed':True,'tested_checkpoint_sha256':sha(c/'CHECKPOINT_MANIFEST.json'),
        'tested_CP_files':len(cp['project_files']),'unique_project_files_verified':len(rows),
        'archive':at['archive'],'extractor':at['extractor'],'restored_artifact':at['restored_artifact'],
        'unchanged_bootstrap_sha256':BOOT,'unchanged_restore_checkpoint_sha256':RESTORE,
        'raw_absent_in_fresh_staged_kit_before_extractor':True,'fresh_destination_was_absent':True,
        'commands':results,'elapsed_seconds':time.monotonic()-started,'CPU_affinity':sorted(os.sched_getaffinity(0)),
        'work':str(work),'network_gets':0,'dependency_or_model_installations':0,
        'model_native_tokenizer_original_corpus_or_gold_parse_calls':0,
        'benchmark_measurements_or_acceptance_changed':False,
        'scope':'Source archive engineering proof, not benchmark inference or generalization. Later metadata leaves are separately pinned and checked by the final checkpoint stage.'}
    put(out,result);print(json.dumps({k:result[k] for k in ('status','checks_passed','tested_CP_files','unique_project_files_verified','elapsed_seconds')}))

if __name__=='__main__':main()
