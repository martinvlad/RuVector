"""Bind one exact archived evidence object before unchanged source bootstrap."""
from pathlib import Path
import argparse, hashlib, json, os, stat

P='experiments/sota-2026-10-22/'
RAW=P+'epoch22/runs/dev/raw.json'
RAW_SHA='2b012e1595bdb9b3bb1e5dacc242e9136a189638704f3a55229fe4d828cd0414'
BOOT='eceb2ca259feaf642bc81172aca57a2a209cc34cd17f9b281861c51f21b95806'
RESTORE='affd9ecf660f380c3632f78cd14fb7a36e00797ceb097cf48c0c60136fac0be8'

def checked(p,directory=False):
    p=Path(p).absolute()
    assert p==p.resolve() and not any(x.is_symlink() for x in [p,*p.parents])
    assert p.is_dir() if directory else stat.S_ISREG(p.lstat().st_mode)
    return p

def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(checked(p).read_bytes())
def ref(root,n):
    p=checked(root/n);assert p.is_relative_to(root)
    b=p.read_bytes();return {'path':n,'bytes':len(b),'sha256':sha(b)}

def main():
    ap=argparse.ArgumentParser()
    for n in ('project','kit','controls-dir','out'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();r=checked(a.project,True);k=checked(a.kit,True);c=checked(a.controls_dir,True)
    out=a.out.absolute();assert out==out.resolve() and not os.path.lexists(out)
    assert not any(x.is_symlink() for x in out.parents)
    assert not out.is_relative_to(r) and not out.is_relative_to(k)
    cp_bytes=(c/'CHECKPOINT_MANIFEST.json').read_bytes();cp=json.loads(cp_bytes)
    cont=read(c/'CONTINUATION.json');active=read(c/'ACTIVE_RUN.json')
    assert cont['checkpoint_manifest_sha256']==sha(cp_bytes)
    assert active['experiments_active'] is False and active['native_allowed']==0
    assert active['native_allowed_after_exact_remote_readback']==0
    assert active['conditional_confirmation_after_independent_DEV_runtime_gates']==0
    assert active['all_unspent_epoch22_slots_permanently_closed'] is True
    raw=ref(r,RAW);assert raw['bytes']==21631719 and raw['sha256']==RAW_SHA
    archive=ref(r,P+'epoch22/publication/actualarchive.dev.raw.v1.json')
    extractor=ref(r,P+'epoch22/publication/restore_archived_artifact_v1.py')
    helper=ref(r,P+'epoch22/publication/prepare_publication_archive_v1.py')
    rows={x['path']:x for x in cp['project_files']}
    for x in (raw,archive,extractor,helper):assert rows[x['path']]==x
    assert sha((k/'bootstrap.py').read_bytes())==BOOT
    assert sha((k/'restore_checkpoint.py').read_bytes())==RESTORE
    assert archive['bytes']<8*1024*1024
    assert 'artifact_transport' not in cont
    cont['artifact_transport']={'format':'gzip+base64',
        'archive':archive,'extractor':extractor,'restored_artifact':raw,
        'publication_helper':helper,'required_before_bootstrap':True,
        'standalone_Git_leaf_omitted':RAW}
    cont['artifact_transport_policy']={'schema_version':1,
        'only_unpublished_original_raw_Git_leaf_omitted':True,
        'restoration_order':['Stage all exact Git leaves into an isolated kit.',
            'Run the pinned extractor with --kit-root KIT --archive ARCHIVE_PATH --expected-archive-sha256 ARCHIVE_SHA256.',
            'Run unchanged reviewed bootstrap.py and restore_checkpoint.py; verify all checkpoint hashes.',
            'Run restore_checkpoint.py --verify-only before any dependencies or inference.'],
        'unchanged_bootstrap_sha256':BOOT,'unchanged_restore_checkpoint_sha256':RESTORE,
        'MCP_request_limit_bytes':16*1024*1024,'archive_blob_request_cap_bytes':8*1024*1024,
        'rejected_request_not_retried':True,'benchmark_measurements_unchanged':True,
        'source':'The project checkpoint pins decoded raw bytes. Git stores their reviewed lossless envelope; extraction precedes source reconstruction.'}
    for field,name in [('publication_transport_blocker','TRANSPORT_LIMIT.v1.json'),
                       ('publication_transport_recovery','PUBLICATION_RECOVERY.v1.json'),
                       ('publication_transport_source_manifest','SOURCE_MANIFEST.archive-v1.json')]:
        n=P+'epoch22/publication/'+name
        if (r/n).exists():cont[field]=ref(r,n)
    out.mkdir(mode=0o700)
    for name,b in [('CHECKPOINT_MANIFEST.json',cp_bytes),
        ('CONTINUATION.json',(json.dumps(cont,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()),
        ('ACTIVE_RUN.json',(c/'ACTIVE_RUN.json').read_bytes())]:
        with (out/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    print(json.dumps({'status':'ONE_ARCHIVED_RAW_BOUND_TO_CLOSED_CONTROLS','CP_files':len(rows),
        'archive':archive,'extractor':extractor,'publication_helper':helper,
        'native_calls':0,'bootstrap_or_restore_source_changed':False}))

if __name__=='__main__':main()
