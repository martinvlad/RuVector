"""Pure byte restoration verification; never parse benchmark case bodies."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import stat

SOURCE_COMMIT = '0eac156990f5a4ee0084af635eb3089913b437ff'
SOURCE_SCOPE_TREE = 'bd87fafff1552a352aa7d5f53d5cdc682fcf06ea'
BASE_MANIFEST_SHA = '0db67a018ad5fd9deba1cfb0bd8897537a330dd2353f169e6e387e86e09fce7a'


def digest(raw): return hashlib.sha256(raw).hexdigest()
def read(path): return json.loads(path.read_text())
def identity(path):
    raw=path.read_bytes()
    return {'bytes':len(raw),'sha256':digest(raw)}


def regular(path):
    assert path.is_file() and stat.S_ISREG(path.stat().st_mode)
    assert not any(p.is_symlink() for p in [path,*path.parents]),str(path)


def verify_records(root, rows):
    assert len(rows)==len({r['path'] for r in rows})
    checked=[]
    for row in rows:
        relative=Path(row['path'])
        assert not relative.is_absolute() and '..' not in relative.parts
        path=root/relative;regular(path)
        actual=identity(path)
        assert actual=={k:row[k] for k in ('bytes','sha256')},row['path']
        checked.append({'path':row['path'],**actual})
    raw=json.dumps(checked,sort_keys=True,separators=(',',':')).encode()
    return {'records':len(checked),'actual_bytes':sum(r['bytes'] for r in checked),
            'checked_identities_SHA256':digest(raw)}


def verify(scope):
    kit=scope/'kit';project=scope/'project'
    fresh=read(scope/'FRESH_RECONSTRUCTION_READY.json')
    assert fresh['source_commit']==SOURCE_COMMIT
    filemap=read(scope/'source-filemap.json')
    assert len(filemap)==2582 and len({r['path'] for r in filemap})==2582
    blob_bytes=0
    for row in filemap:
        path=kit/row['path'];regular(path);raw=path.read_bytes()
        assert len(raw)==row['size'],row['path']
        header=b'blob '+str(len(raw)).encode()+b'\0'
        assert hashlib.sha1(header+raw).hexdigest()==row['sha'],row['path']
        assert row['type']=='blob'
        blob_bytes+=len(raw)
    cp=read(kit/'CHECKPOINT_MANIFEST.json');continuation=read(kit/'CONTINUATION.json')
    assert identity(kit/'CHECKPOINT_MANIFEST.json')['sha256']==continuation['checkpoint_manifest_sha256']
    cp_result=verify_records(project,cp['project_files']);assert cp_result['records']==2505
    km=read(kit/'KIT_MANIFEST.json');kit_result=verify_records(project,km['project_files'])
    assert kit_result['records']==61
    base_raw=(kit/'BASE_PUBLIC_MANIFEST.json').read_bytes();assert digest(base_raw)==BASE_MANIFEST_SHA
    base_index={r['path']:r for r in json.loads(base_raw)['files']}
    base_rows=[base_index[n] for n in read(kit/'BASE_DOWNLOADS.json')['paths']]
    base_result=verify_records(project,base_rows);assert base_result['records']==48
    return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,
        'status':'INDEPENDENT_FRESH_SOURCE_GIT_AND_PROJECT_BYTE_RESTORATION_PASS',
        'source_commit':SOURCE_COMMIT,'source_root_tree':'991498c09a973d3430d4fb4f977d2e508dea09d8',
        'source_benchmarks_tree':'a0a4a5e9a0a202d098b9fac5c524c360329f79b0',
        'source_scope_tree':SOURCE_SCOPE_TREE,'connected_Git_tree_untruncated_nodes':2791,
        'independent_connected_Git_blob_tuple_comparison':2582,
        'kit_Git_blobs_rehashed':2582,'kit_Git_blob_bytes_rehashed':blob_bytes,
        'source_blob_index':identity(scope/'source-filemap.json'),
        'checkpoint_manifest':identity(kit/'CHECKPOINT_MANIFEST.json'),
        'checkpoint_project_files':cp_result,'KIT_project_files':kit_result,'BASE_project_files':base_result,
        'reviewed_bootstrap':identity(kit/'bootstrap.py'),'reviewed_restore_checkpoint':identity(kit/'restore_checkpoint.py'),
        'all_historical_CP_files_unchanged':True,'source_symlinks_refused':True,
        'scope':'Connected Git immutable source tree independently matched fresh source metadata; all2582kit blob size/GitSHA1 and all2505CP+61KIT+48BASE project byte/SHA256 checks passed. Metadata JSON only; benchmark case file bytes are hashed, never parsed. No model/native binary/ABI/session claim.',
        'reviewer_original_corpus_or_input_or_annotation_JSON_parses':0,
        'reviewer_model_native_fit_paid_GPU_calls':0,'Git_mutations':0,
        'official_score':None,'official_rank':None,'SOTA_established':False}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scope',required=True,type=Path);ap.add_argument('--out',required=True,type=Path)
    a=ap.parse_args();result=verify(a.scope.resolve())
    raw=(json.dumps(result,indent=2)+'\n').encode()
    with a.out.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
    print(json.dumps({'checks_passed':True,'status':result['status'],'report_SHA256':digest(raw),
        'Git_blobs':2582,'CP':2505,'KIT':61,'BASE':48,'model_native_calls':0}))


if __name__=='__main__':main()
