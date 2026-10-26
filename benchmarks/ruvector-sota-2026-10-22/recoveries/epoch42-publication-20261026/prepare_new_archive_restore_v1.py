"""Source-only, fresh-scope reconstruction for the distinct E42 archive transaction."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, os, stat, time

W = Path('/tmp/ruvector-sota-2026-10-22/epoch42-archive-recovery-20261026T040538')
OLD = Path('/tmp/ruvector-sota-2026-10-22/epoch42-recovery-20261026T0318')
CONTROLS = {'CONTINUATION.json', 'CHECKPOINT_MANIFEST.json', 'ACTIVE_RUN.json'}
OWNER_SHA = 'b503f119766f65dd85c6eff140483e2140b1279a9e33b467ccce204f96d0297c'
SOURCE_CP_SHA = '2612c58bf6040e2a5f5b5726e0038ae637269020ad336b58bc1d6844867ccd87'
SOURCE_HEAD = '4201146a603127e9a536d266e38058deec4c3658'

def sha(b): return hashlib.sha256(b).hexdigest()
def gitsha(b): return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def safe(root, name):
    p = PurePosixPath(name)
    assert not p.is_absolute() and all(x not in ('', '.', '..') for x in name.split('/')) and '\\' not in name
    target = root / name
    assert not any(q.is_symlink() for q in (target, *target.parents))
    assert target.resolve().is_relative_to(root.resolve())
    return target
def checked(p, size, digest, git=False):
    assert stat.S_ISREG(p.stat().st_mode) and not any(q.is_symlink() for q in (p, *p.parents))
    b = p.read_bytes()
    assert len(b) == size and (gitsha(b) if git else sha(b)) == digest, str(p)
    return b
def put(p, b):
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with p.open('xb') as f:
        f.write(b); f.flush(); os.fsync(f.fileno())
def jsonput(p, v): put(p, (json.dumps(v, indent=2, ensure_ascii=False)+'\n').encode())
def held():
    owner_b = (W/'owner.json').read_bytes(); assert sha(owner_b) == OWNER_SHA
    owner = json.loads(owner_b); assert time.time() < owner['expires_unix']
    p = Path('/proc')/str(owner['pid']); raw = (p/'stat').read_text(); tail=raw[raw.rfind(')')+2:].split()
    assert tail[0] != 'Z' and int(tail[19]) == owner['startticks']
    lock = Path(owner['lock']); fd = p/'fd/3'; a=lock.stat(); b=fd.stat()
    assert (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino)==(owner['lock_device'],owner['lock_inode'])
    assert any('FLOCK' in line and f' {owner["pid"]} ' in line and f':{owner["lock_inode"]} ' in line for line in Path('/proc/locks').read_text().splitlines())

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--overlay', type=Path, required=True); ap.add_argument('--overlay-manifest', type=Path, required=True)
    args=ap.parse_args(); overlay=args.overlay.resolve(); manifest_raw=args.overlay_manifest.read_bytes(); manifest=json.loads(manifest_raw)
    # Manifest is independently frozen before execution; exact rows include all three new controls.
    rows=manifest['files']; assert len(rows)==len({r['path'] for r in rows})
    by={r['path']:r for r in rows}; assert CONTROLS <= set(by)
    actual={p.relative_to(overlay).as_posix() for p in overlay.rglob('*') if p.is_file()}
    assert actual == set(by)
    assert all(n in CONTROLS or n.startswith('recoveries/epoch42-publication-20261026/') for n in by)
    for row in rows: checked(safe(overlay,row['path']),row['bytes'],row['sha256'])
    held(); K=W/'kit'; R=W/'project'; B=W/'base-cache'
    assert not any(p.exists() for p in (K,R,B)), 'Never replay partial fresh reconstruction'
    source_map=json.loads((OLD/'actual-git-map.json').read_text()); assert source_map['commit']==SOURCE_HEAD
    gr=source_map['files']; assert len(gr)==7254 and len({r['path'] for r in gr})==7254
    oldcp_b=(OLD/'kit/CHECKPOINT_MANIFEST.json').read_bytes(); assert sha(oldcp_b)==SOURCE_CP_SHA
    oldcp=json.loads(oldcp_b)['project_files']; assert len(oldcp)==7180
    newcp_b=checked(safe(overlay,'CHECKPOINT_MANIFEST.json'),by['CHECKPOINT_MANIFEST.json']['bytes'],by['CHECKPOINT_MANIFEST.json']['sha256'])
    C=json.loads((overlay/'CONTINUATION.json').read_text()); assert C['checkpoint_manifest_sha256']==sha(newcp_b)
    cp=json.loads(newcp_b)['project_files']; cpi={r['path']:r for r in cp}; assert len(cpi)==len(cp)
    for row in oldcp: assert cpi[row['path']]==row, row['path']
    projection=json.loads((overlay/'recoveries/epoch42-publication-20261026/ARCHIVE_PROJECTED_FILES.v1.json').read_text())
    delayed=set(projection['additional_archive_backed_CP_only_paths']); assert len(delayed)==67
    legacy=projection['historical_CP_only_paths_restored_by_unchanged_legacy_transports']; assert len(legacy)==3
    km=json.loads((OLD/'kit/KIT_MANIFEST.json').read_text())['project_files']
    bm_b=(OLD/'kit/BASE_PUBLIC_MANIFEST.json').read_bytes(); assert sha(bm_b)=='0db67a018ad5fd9deba1cfb0bd8897537a330dd2353f169e6e387e86e09fce7a'
    bm={r['path']:r for r in json.loads(bm_b)['files']}; bp=json.loads((OLD/'kit/BASE_DOWNLOADS.json').read_text())['paths']
    assert (len(km),len(bp))==(61,48)
    need=sum(r['size'] for r in gr if r['path'] not in CONTROLS)+sum(cpi[n]['bytes'] for n in legacy)+sum(bm[n]['bytes'] for n in bp)+sum(r['bytes'] for r in rows)+projection['archive_uncompressed_bytes']+50*1024**2
    sv=os.statvfs(W); free=sv.f_bavail*sv.f_frsize; assert free>need, (free,need)
    once=W/'fresh-reconstruction-ONCE.json'; jsonput(once,{'overlay_manifest_sha256':sha(manifest_raw),'source':SOURCE_HEAD,'started_unix':time.time(),'native_model_Gold_EVAL_Git_calls':0})
    started=time.monotonic(); K.mkdir(); R.mkdir(); B.mkdir()
    for row in gr:
        if row['path'] not in CONTROLS:
            put(safe(K,row['path']),checked(safe(OLD/'kit',row['path']),row['size'],row['sha'],True))
    for name in legacy:
        row=cpi[name]; put(safe(K,name),checked(safe(OLD/'kit',name),row['bytes'],row['sha256']))
    for row in rows: put(safe(K,row['path']),checked(safe(overlay,row['path']),row['bytes'],row['sha256']))
    for name in bp:
        row=bm[name]; put(safe(B,name),checked(safe(OLD/'base-cache',name),row['bytes'],row['sha256']))
    union={}
    for original in [*cp,*km,*[bm[n] for n in bp]]:
        row={k:original[k] for k in ('path','bytes','sha256')}; name=row['path']
        if name in union: assert union[name]==row
        union[name]=row
    for name,row in union.items():
        if name in delayed: assert not safe(K,name).exists(); continue
        src=safe(K,name) if safe(K,name).is_file() else safe(B,name)
        checked(src,row['bytes'],row['sha256']); dst=safe(R,name); dst.parent.mkdir(mode=0o700,parents=True,exist_ok=True);os.link(src,dst)
        checked(dst,row['bytes'],row['sha256'])
    held(); proof={'source_commit':SOURCE_HEAD,'Git_rows':7254,'old_CP_rows_preserved':7180,'new_CP_rows':len(cp),'new_archive_members_delayed_to_reviewed_decoder':67,'legacy_CP_only_verified':3,'KIT_rows':61,'BASE_rows':48,'expected_project_union':len(union),'overlay_manifest_sha256':sha(manifest_raw),'all_copied_bytes_hash_verified':True,'hardlinks_only_within_fresh_scope':True,'original_files_modified':False,'native_model_Gold_EVAL_Git_calls':0,'wall_seconds':time.monotonic()-started}
    jsonput(W/'fresh-pre-restoration-proof.json',proof);jsonput(W/'fresh-expected-project-union.json',{'files':list(union.values())})
    for parent in (W,K,R,B):
        d=os.open(parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
    print(json.dumps(proof),flush=True)

if __name__=='__main__': main()
