"""Shared, stdlib-only REAL payload validator; no ML/tokenizer/native import.

The exact common.verify_model_assets wrapper uses this function before SOURCE
and in the dispatcher/worker path. It reads all supplied payload bytes for hashes;
it never loads the model or substitutes observed locks for source declarations.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import os
import stat
import time

HERE=Path(__file__).resolve().parent
HELPER=HERE.parent/'asset_identity.py'
HELPER_SHA='f271c0077be23c34fbb29cfb5728d671371a4646ac9030072ec7b538eb819499'
FILENAMES={'config.json','tokenizer_config.json','LICENSE','spm.model','pytorch_model.bin'}

def no_symlink(path):
    p=Path(path)
    if any(q.is_symlink()for q in(p,*p.parents)):raise ValueError('Symlink asset/source component refused')
    return p

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()

def source_ref(path,root):
    p=no_symlink(path)
    return {'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':sha(p)}

def object_pairs(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('Duplicate asset metadata key')
        result[k]=v
    return result

def read_metadata(path):
    p=no_symlink(path)
    if not p.is_file()or not stat.S_ISREG(p.stat().st_mode):raise ValueError('Regular source metadata required')
    return json.loads(p.read_text(encoding='utf-8'),object_pairs_hook=object_pairs,
        parse_constant=lambda value:(_ for _ in()).throw(ValueError('Nonfinite metadata')))

def validate_model_assets(directory,public_lock_path,expected_catalog_path,*,root,
        public_lock_sha256,expected_catalog_sha256,epoch,kind,source_checkpoint,
        repository='microsoft/deberta-v2-xxlarge-mnli',revision='8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06'):
    """Perform the entire actual five-file validator, with NO terminal stub.

    common enforces the exact a65 source authority, source pins and fixed A38
    directory. Separating those arguments permits disjoint tiny-file unit tests;
    fixture receipts are never runtime/SOURCE admission evidence.
    """
    started=time.monotonic();root=Path(root);directory=no_symlink(directory)
    public_lock_path=no_symlink(public_lock_path);expected_catalog_path=no_symlink(expected_catalog_path)
    if sha(HELPER)!=HELPER_SHA:raise ValueError('Exact independently reviewed typed Git/LFS identity helper required')
    sp=importlib.util.spec_from_file_location('e38_exact_typed_model_asset_identity',HELPER)
    identities=importlib.util.module_from_spec(sp);sp.loader.exec_module(identities)
    if sha(public_lock_path)!=public_lock_sha256 or sha(expected_catalog_path)!=expected_catalog_sha256:
        raise ValueError('Changed source-pinned public lock or separate expected catalog')
    lock=read_metadata(public_lock_path);expected=read_metadata(expected_catalog_path)
    if (lock.get('epoch')!=epoch or lock.get('kind')!=kind or lock.get('repository')!=repository
            or lock.get('revision')!=revision or lock.get('model_directory')!=str(directory)
            or expected.get('repository')!=repository or expected.get('revision')!=revision):
        raise ValueError('Wrong exact source revision/directory/materialization epoch')
    direct=directory/'asset-lock.json';no_symlink(direct)
    if not direct.is_file()or direct.read_bytes()!=public_lock_path.read_bytes():
        raise ValueError('External direct lock must equal frozen public lock byte for byte')
    rows=lock.get('files');declared=expected.get('files')
    if (not isinstance(rows,list)or not isinstance(declared,list)or len(rows)!=5 or len(declared)!=5
            or {r.get('path')for r in rows}!=FILENAMES or {r.get('path')for r in declared}!=FILENAMES
            or {p.name for p in directory.iterdir()}!=FILENAMES|{'asset-lock.json'}):
        raise ValueError('Exact five original payloads and one direct lock required; extras/missing refused')
    metadata=identities.bind_catalog(declared,rows);by_source={r['path']:r for r in declared};by_identity={r['path']:r for r in metadata}
    results=[];total_bytes=0
    for observed in rows:
        name=observed['path'];declaration=by_source[name];identity=by_identity[name];file=no_symlink(directory/name)
        before=file.stat()
        if not stat.S_ISREG(before.st_mode):raise ValueError('Regular original payload required')
        payload_sha=hashlib.sha256();raw_git=(hashlib.sha1(b'blob '+str(before.st_size).encode()+b'\0')
            if identity['raw_payload_git_blob_sha1_required']else None)
        count=0;fd=os.open(file,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            opened=os.fstat(fd)
            if (opened.st_dev,opened.st_ino,opened.st_size)!=(before.st_dev,before.st_ino,before.st_size):raise ValueError('Payload changed before hash scan')
            with os.fdopen(fd,'rb',closefd=False)as stream:
                for block in iter(lambda:stream.read(1048576),b''):
                    count+=len(block);payload_sha.update(block)
                    if raw_git is not None:raw_git.update(block)
            after=os.fstat(fd)
        finally:os.close(fd)
        path_after=file.stat()
        if ((path_after.st_dev,path_after.st_ino,path_after.st_size)!=(before.st_dev,before.st_ino,before.st_size)or count!=before.st_size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_mode)
                !=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_mode)):
            raise ValueError('Original payload changed during exact hash scan')
        actual_sha=payload_sha.hexdigest();actual_git=raw_git.hexdigest()if raw_git is not None else None
        verified=identities.verify_payload_observation(declaration,count,actual_sha,actual_git)
        if actual_sha!=observed['sha256']or count!=observed['bytes']:raise ValueError('Actual payload differs from observed materialization lock')
        results.append({**verified,'actual_payload_bytes_hashed':count,'actual_payload_sha256':actual_sha,
            'actual_ordinary_payload_git_blob_sha1':actual_git,'actual_full_payload_scan':True,
            'payload_git_SHA1_computed':raw_git is not None,'LFS_payload_git_SHA1_not_required':raw_git is None})
        total_bytes+=count
    return {'schema_version':1,'epoch':epoch,'kind':kind,'source_checkpoint':source_checkpoint,
        'status':'ALL_FIVE_REAL_MODEL_ASSETS_VERIFIED_WITH_TYPED_SOURCE_IDENTITIES',
        'validator_function':'model_assets_guard.validate_model_assets','validator_source':source_ref(Path(__file__),root),
        'identity_helper_source':source_ref(HELPER,root),'expected_catalog':source_ref(expected_catalog_path,root),
        'public_model_assets_lock':source_ref(public_lock_path,root),'external_direct_lock':{
            'path':str(direct),'bytes':direct.stat().st_size,'sha256':sha(direct),'byte_identical_to_public':True},
        'repository':repository,'revision':revision,'model_directory':str(directory),'directory_inventory':sorted(p.name for p in directory.iterdir()),
        'actual_payload_files_verified':5,'actual_payload_bytes_hashed':total_bytes,'ordinary_Git_payloads_verified':sum(r['raw_payload_git_sha1_verified']for r in results),
        'canonical_LFS_pointers_verified':sum(not r['raw_payload_git_sha1_verified']for r in results),'files':results,'stubs_used':False,'monkeypatches':[],
        'model_native_tokenizer_initializations_or_calls':0,'case_oracle_reads':0,'network_calls':0,
        'wall_seconds_hash_validation_only':time.monotonic()-started}
