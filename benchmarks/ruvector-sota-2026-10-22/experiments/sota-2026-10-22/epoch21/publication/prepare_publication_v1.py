"""Prepare reviewed public21 bytes and Git payloads locally; never contact GitHub.

Source/final stages are exclusive new directories. A final stage must pin its
published source expected-leaves file. Large UTF8 files get create_blob requests;
tree payloads reference their independently computable Git blob identities.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

SCOPE = 'benchmarks/ruvector-sota-2026-10-22/'
PREFIX = 'experiments/sota-2026-10-22/'
SOURCE_COMMIT = '0c4392bb8b13a901dc416882f850230c1075fb6a'
SOURCE_FILEMAP_SHA = '7a20bbd31f09eb1be72d5bcc73d5cc2c00a0612bfff7405396ab0fe5d7782b58'
SOURCE_CP_SHA = '96f7cb566db59102b79bd9d9b6f935e642a930b8014887e879349bc84dc4a74b'
CONTROLS = {'CONTINUATION.json','ACTIVE_RUN.json','CHECKPOINT_MANIFEST.json'}
EXTERNAL_PARENT = PREFIX+'candidate/epoch21/assets'
EXTERNAL_ROOT = EXTERNAL_PARENT+'/official-deberta-v3-large-nli'
EXTERNAL_LOCK = PREFIX+'legal-transfer/epoch21/model-assets.lock.json'
EXTERNAL_REPOSITORY = 'MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
EXTERNAL_REVISION = 'b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7'
EXTERNAL_FILES = {'.gitattributes': (1227, '400b270bc8f5cb44fda65b1a4532ceca0fb452d0637425e861829560cf393ae2'), 'README.md': (7580, '216c3ac9ea77beec4e35a347c8b4edc47fbb3465e7c2a00dc923ae7b975cf346'), 'config.json': (1056, '7f9d420b616691c5b575bab8839719aefbddc656d8e1316519414b097ce43e3d'), 'added_tokens.json': (18, 'cd0141b19e809eb963a8f8244fad72530233f729e1f6960d281e1fbb3537b2fb'), 'special_tokens_map.json': (156, 'fcfbeb4e25cd37fb5b8030406394253b245230fd3b552750092bab7d24d827da'), 'tokenizer_config.json': (395, '556a192d83e3edb45a09a6207095dd9295c3b2279062e5cc430feac4cb7a0817'), 'tokenizer.json': (8648889, '7aa118770f066a74530d161c7d0b994d0629cc0ff3a0df213f184192773f960a'), 'spm.model': (2464616, 'c679fbf93643d19aab7ee10c0b99e460bdbc02fedf34b92b05af343b4af586fd'), 'model.safetensors': (870182606, 'c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b')}
EXTERNAL_LOCK_SHA = 'fafdae110e1f0dfb97bc51e61af3d012d64be3f18236ae1addab7c56a19b5400'

DIRS = tuple(PREFIX+x for x in ('candidate/epoch21','controller/epoch21',
                               'legal-transfer/epoch21','audit/epoch21','epoch21'))
EXTENSIONS = {'.py','.mjs','.cjs','.js','.json','.jsonl','.md','.txt','.log','.yaml','.yml','.csv','.tsv'}
BANNED_PARTS = {'assets','__pycache__','.git','.cache','cache','venv','.venv',
                'node_modules','site-packages','credentials','secrets','private','raw','raw-pages','raw-email'}
SECRETS = tuple(re.compile(x,re.I|re.M) for x in (
    r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    r'\bgh[pousr]_[A-Za-z0-9]{30,}\b',r'\bgithub_pat_[A-Za-z0-9_]{30,}\b',
    r'\bAKIA[0-9A-Z]{16}\b',r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b',
    r'\b(?:authorization|proxy-authorization)\s*[:=]\s*[\x22\x27]?(?:Bearer|Basic)\s+[A-Za-z0-9+/_.=-]{20,}',
    r'^[ \t]*(?:Received:|DKIM-Signature:|Return-Path:|MIME-Version:)',
    r'<(?:!DOCTYPE\s+html|html|head|body)(?:\s|>)'))


def fail(message):
    raise ValueError(message)


def raw_json(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def gitsha(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def relative(value):
    if (not isinstance(value,str) or not value or '\\' in value
            or PurePosixPath(value).is_absolute()
            or any(x in ('','.','..')for x in value.split('/'))):
        fail('Unsafe relative publication path')
    return value


def regular(path):
    path=Path(path).absolute()
    if path != path.resolve():fail('Noncanonical publication path refused: '+str(path))
    for ancestor in (path,*path.parents):
        if ancestor.is_symlink():fail('Symlink or symlink ancestor refused: '+str(path))
    if not stat.S_ISREG(path.lstat().st_mode):fail('Nonregular file refused: '+str(path))
    return path


def regular_dir(path):
    path=Path(path).absolute()
    if path != path.resolve():fail('Noncanonical publication path refused: '+str(path))
    for ancestor in (path,*path.parents):
        if ancestor.is_symlink():fail('Symlink directory/ancestor refused: '+str(path))
    if not path.is_dir():fail('Required directory absent: '+str(path))
    return path


def content(path):
    return regular(path).read_bytes()


def parse(path):
    return json.loads(content(path).decode('utf-8'))


def public_text(path,data):
    pieces=PurePosixPath(relative(path)).parts
    lower=[x.lower()for x in pieces]
    if (set(lower)&BANNED_PARTS or any('.private'in x or x.startswith('.env')for x in lower)
            or any(x.endswith(('.eml','.mbox','.html','.htm','.pem','.key','.sqlite','.db',
                               '.bin','.onnx','.pt','.pth','.safetensors','.model','.whl',
                               '.so','.pyc','.zip','.tar','.gz'))for x in lower)
            or any(Path(x).stem in ('private','credentials','secrets')for x in lower)
            or any(x in ('inbox','mailbox','messages')for x in lower)):
        fail('Private/raw/model/cache path refused: '+path)
    if Path(path).suffix not in EXTENSIONS:fail('Unreviewed public file extension: '+path)
    text=data.decode('utf-8',errors='strict')
    if '\0'in text or any(ord(c)<32 and c not in '\t\n\r'for c in text):
        fail('Binary/control payload refused: '+path)
    if any(pattern.search(text)for pattern in SECRETS):
        fail('Credential, raw email or raw page payload refused: '+path)
    return text


def external_model_assets(project):
    """Validate then exclude only nine exact frozen external runtime files.

    Stream hashes never load the original870MBsafetensorscheckpoint into publication RAM.
    The public lock/card/config/API remain ordinary reviewed source artifacts.
    """
    root=project/EXTERNAL_PARENT;lock=project/EXTERNAL_LOCK
    if not root.exists()and not lock.exists():return {}
    regular_dir(root)
    if sha(content(lock))!=EXTERNAL_LOCK_SHA:fail('Exact qualified external model lock changed')
    value=parse(lock)
    if value.get('repository')!=EXTERNAL_REPOSITORY or value.get('revision')!=EXTERNAL_REVISION:
        fail('External model lock repository/revision changed')
    rows=value['assets'];declared={relative(r['path']):r for r in rows}
    expected={EXTERNAL_ROOT+'/'+name:{'path':EXTERNAL_ROOT+'/'+name,'bytes':size,'sha256':digest}
              for name,(size,digest)in EXTERNAL_FILES.items()}
    if len(rows)!=9 or len(declared)!=9 or set(declared)!=set(expected):
        fail('Only the exact nine frozen external model asset paths may be excluded')
    for rel,row in declared.items():
        if {k:row[k]for k in ('path','bytes','sha256')}!=expected[rel]:
            fail('External model lock identity changed: '+rel)
    allowed_dirs={EXTERNAL_PARENT,EXTERNAL_ROOT};actual=set()
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in dirs:
            path=regular_dir(Path(base)/name)
            if path.relative_to(project).as_posix()not in allowed_dirs:
                fail('Unknown external asset directory refused')
        for name in files:
            path=regular(Path(base)/name);rel=path.relative_to(project).as_posix()
            if rel not in expected:fail('Unknown external model asset refused: '+rel)
            actual.add(rel)
    if actual!=set(expected):fail('Missing declared external model asset')
    for rel,row in expected.items():
        path=regular(project/rel)
        if path.stat().st_size!=row['bytes']:fail('External model asset size changed: '+rel)
        h=hashlib.sha256()
        with path.open('rb')as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
        if h.hexdigest()!=row['sha256']:fail('External model asset SHA256 changed: '+rel)
    return expected


def walk_current(project):
    excluded=external_model_assets(project)
    found={}
    for directory in DIRS:
        root=project/directory
        if not root.exists():
            for ancestor in (root,*root.parents):
                if ancestor.is_symlink():fail('Symlink optional21 directory/ancestor refused')
            if directory==PREFIX+'epoch21':fail('Required epoch21 root absent')
            continue
        root=regular_dir(root)
        for base,dirs,files in os.walk(root,followlinks=False):
            for name in dirs:regular_dir(Path(base)/name)
            for name in files:
                file=regular(Path(base)/name);rel=file.relative_to(project).as_posix()
                if rel in excluded:continue
                public_text(rel,b'')  # Refuse unknown raw/model/private paths before reading their bytes.
                data=file.read_bytes();public_text(rel,data)
                if rel in found:fail('Duplicate new21 file: '+rel)
                found[rel]=data
    if not found:fail('No public21 artifacts selected')
    return found


def leaf(path,data):
    return {'path':path,'mode':'100644','type':'blob','sha':gitsha(data),'size':len(data)}


def verify_map(kit,rows):
    if not isinstance(rows,list)or len(rows)!=3090:fail('Exact3090 current-source leaves required')
    answer={}
    for row in rows:
        rel=relative(row['path'])
        if rel in answer or row['mode']!='100644'or row['type']!='blob':
            fail('Duplicate/nonregular current-source leaf: '+rel)
        data=content(kit/rel);expected=leaf(rel,data)
        if any(row[k]!=expected[k]for k in ('path','mode','type','sha','size')):
            fail('Historical source Git tuple changed: '+rel)
        answer[rel]=expected
    if not CONTROLS<=set(answer):fail('Historical controls absent')
    return answer


def checked_controls(directory,old_cp,new_files,mode):
    actual={p.name for p in directory.iterdir()}
    if actual!=CONTROLS:fail('Controls directory must contain exactly3 derived controls')
    blobs={n:content(directory/n)for n in sorted(CONTROLS)}
    for n,b in blobs.items():public_text(n,b)
    cp=json.loads(blobs['CHECKPOINT_MANIFEST.json']);before={r['path']:r for r in old_cp['project_files']}
    after={r['path']:r for r in cp['project_files']}
    if len(before)!=3013 or len(after)!=len(cp['project_files']):fail('Checkpoint path count/duplicates invalid')
    if any(after.get(p)!=r for p,r in before.items()):fail('Historical3013 checkpoint records changed')
    expected={p:{'path':p,'bytes':len(b),'sha256':sha(b)}for p,b in new_files.items()}
    if set(after)-set(before)!=set(expected):fail('Checkpoint does not cover exactly current public21 leaves')
    if any(after[p]!=row for p,row in expected.items()):fail('New21 checkpoint bytes/hash mismatch')
    continuation=json.loads(blobs['CONTINUATION.json']);active=json.loads(blobs['ACTIVE_RUN.json'])
    if continuation.get('checkpoint_manifest_sha256')!=sha(blobs['CHECKPOINT_MANIFEST.json']):
        fail('Continuation checkpoint hash mismatch')
    if mode=='source':
        if active.get('experiments_active')is not True or type(active.get('native_allowed'))is not int or active['native_allowed']!=0:
            fail('Source controls must hold active ownership with zero native admission')
        ref=continuation.get('active_run',{})
        if ref.get('experiments_active')is not True or type(ref.get('native_allowed'))is not int or ref['native_allowed']!=0:
            fail('Source continuation must also withhold native admission')
        if PREFIX+'epoch21/launch.json'in new_files or any(p.startswith(PREFIX+'epoch21/runs/')for p in new_files):
            fail('Source stage cannot include native invocation evidence')
    else:
        if PREFIX+'epoch21/EPOCH_MANIFEST.json'not in new_files:fail('Final epoch manifest required')
        if active.get('experiments_active')is not False or type(active.get('native_allowed'))is not int or active['native_allowed']!=0:
            fail('Final control must close experiments and all native admission')
        allowance=active.get('native_allowed_after_exact_remote_readback',0)
        if type(allowance)is not int or allowance!=0:fail('Final conditional native allowance must be closed')
        confirmation=active.get('conditional_confirmation_after_independent_DEV_runtime_gates',0)
        if type(confirmation)is not int or confirmation!=0:fail('Final conditional confirmation allowance must be closed')
        ref=continuation.get('active_run',{})
        if ref.get('experiments_active')is not False or type(ref.get('native_allowed'))is not int or ref['native_allowed']!=0:
            fail('Final continuation must close experiments and all native admission')
    owner=active.get('run_id')
    if not isinstance(owner,str)or not owner.strip():fail('Explicit active owner identity required')
    if mode=='final':
        value=continuation.get('active_run',{}).get('native_allowed_after_exact_remote_readback',0)
        if type(value)is not int or value!=0:fail('Final continuation conditional allowance must be closed')
        value=continuation.get('active_run',{}).get('conditional_confirmation_after_independent_DEV_runtime_gates',0)
        if type(value)is not int or value!=0:fail('Final continuation confirmation allowance must be closed')
    if active.get('run_id')!=continuation.get('active_run',{}).get('run_id'):
        fail('Continuation and active owner disagree')
    return blobs


def previous_leaves(path,baseline,current):
    value=parse(path)
    if value.get('scope')!=SCOPE or value.get('source_checkpoint')!=SOURCE_COMMIT:
        fail('Prior source publication scope/checkpoint mismatch')
    rows=value['files'];prior={relative(r['path'][len(SCOPE):]):r for r in rows
                               if isinstance(r.get('path'),str)and r['path'].startswith(SCOPE)}
    if len(prior)!=len(rows):fail('Duplicate/escaping prior expected leaf')
    for rel,old in baseline.items():
        expected=dict(old,path=SCOPE+rel)
        if rel not in CONTROLS and prior.get(rel)!=expected:fail('Prior historical leaf changed: '+rel)
    for rel,row in prior.items():
        if rel in CONTROLS:continue
        if rel in baseline:continue
        if rel not in current or row!=dict(leaf(rel,current[rel]),path=SCOPE+rel):
            fail('Published21 source changed or disappeared: '+rel)
    return prior


def checked_review(path,current):
    if path is None:fail('Exact reviewed public allowlist required')
    value=parse(path);rows=value['files']if isinstance(value,dict)else value
    refs={relative(r['path']):r for r in rows}
    if len(refs)!=len(rows)or set(refs)!=set(current):fail('Reviewed allowlist must match all current21 leaves exactly')
    for rel,b in current.items():
        if refs[rel].get('bytes')!=len(b)or refs[rel].get('sha256')!=sha(b):
            fail('Reviewed public allowlist identity changed: '+rel)


def write(path,data):
    with path.open('xb')as file:file.write(data);file.flush();os.fsync(file.fileno())


def transport_groups(changed):
    entries=[];big=[]
    for rel,data in sorted(changed.items()):
        text=public_text(rel,data);entry={'path':SCOPE+rel,'mode':'100644','type':'blob','content':text}
        if len(raw_json({'tree_elements':[entry]}))>=190000:
            number=len(big);entry.pop('content');entry['sha']=gitsha(data)
            big.append((f'blob-{number:03d}.json',{'content':text,'encoding':'utf-8'},rel,data))
        entries.append(entry)
    groups=[];batch=[]
    for entry in entries:
        test=batch+[entry]
        if len(raw_json({'tree_elements':test}))>=190000:
            if not batch:fail('Single create_tree entry exceeds190k')
            groups.append(batch);batch=[entry]
        else:batch=test
    if batch:groups.append(batch)
    return entries,big,groups


def prepare(args):
    project=regular_dir(args.project);kit=regular_dir(args.kit)
    controls=regular_dir(args.controls_dir);out=Path(args.out).absolute()
    if out != out.resolve():fail('Stage output must be canonical')
    if out.exists()or out.is_symlink():fail('Stage output must be a new directory')
    for parent in out.parents:
        if parent.is_symlink():fail('Stage output symlink ancestor')
    if any(out.is_relative_to(root)or root.is_relative_to(out)for root in (project,kit)):
        fail('Stage must be outside project and kit scopes')
    filemap=content(args.source_filemap)
    if sha(filemap)!=SOURCE_FILEMAP_SHA:fail('Current actual Git source-filemap hash changed')
    index=json.loads(filemap)
    if index.get('source_commit')!=SOURCE_COMMIT or index.get('scope')!=SCOPE:
        fail('Source-filemap scope/checkpoint mismatch')
    baseline=verify_map(kit,index['files']);old_cp_bytes=content(kit/'CHECKPOINT_MANIFEST.json')
    if sha(old_cp_bytes)!=SOURCE_CP_SHA:fail('Current connected-source checkpoint hash changed')
    if args.mode=='final'and args.prior_expected is None:fail('Final stage requires prior published source leaves')
    current=walk_current(project);checked_review(args.reviewed_files,current)
    derived=checked_controls(controls,json.loads(old_cp_bytes),current,args.mode)
    prior=previous_leaves(args.prior_expected,baseline,current)if args.prior_expected else None
    expected={p:dict(r,path=SCOPE+p)for p,r in baseline.items()}
    for rel,data in {**current,**derived}.items():
        if rel in baseline and rel not in CONTROLS:fail('Attempted historical overwrite: '+rel)
        expected[rel]=dict(leaf(rel,data),path=SCOPE+rel)
    changed={**current,**derived}
    if prior:
        changed={p:b for p,b in changed.items()if prior.get(p)!=expected[p]}
    entries,big,groups=transport_groups(changed)
    out.mkdir(mode=0o700,parents=False)
    transport=out/'transport';transport.mkdir(mode=0o700)
    stage=out/'changed';stage.mkdir(mode=0o700)
    meta={'schema_version':1,'stage':args.mode,'scope':SCOPE,'source_checkpoint':SOURCE_COMMIT,
          'source_filemap_sha256':sha(filemap),'source_checkpoint_manifest_sha256':sha(old_cp_bytes),
          'historical_leaf_count':3090,'historical_unchanged_except_controls':3087,
          'new_public21_leaves':len(current),'controls_replaced':sorted(CONTROLS),
          'native_or_model_calls':0,'Git_mutations':0,'all_payloads_UTF8':True,
          'external_model_asset_files_not_republished':9 if (project/EXTERNAL_PARENT).exists()else 0,
          'large_blob_requests':[],'create_tree_groups':[],'new_and_control_files':[]}
    for rel,data in sorted(changed.items()):
        path=stage/rel;path.parent.mkdir(parents=True,exist_ok=True);write(path,data)
        meta['new_and_control_files'].append({'path':rel,'bytes':len(data),'sha256':sha(data),'git_blob_sha1':gitsha(data)})
    for name,payload,rel,data in big:
        raw=raw_json(payload);write(transport/name,raw)
        meta['large_blob_requests'].append({'path':rel,'file':'transport/'+name,'bytes':len(raw),'sha256':sha(raw),'expected_blob_sha1':gitsha(data),'must_create_and_verify_before_tree':True})
    for number,batch in enumerate(groups):
        name=f'tree-{number:03d}.json';raw=raw_json({'tree_elements':batch})
        if len(raw)>=200000:fail('Tree transport cap exceeded')
        write(transport/name,raw);meta['create_tree_groups'].append({'file':'transport/'+name,'bytes':len(raw),'sha256':sha(raw),'entries':len(batch)})
    expect={'schema_version':1,'scope':SCOPE,'source_checkpoint':SOURCE_COMMIT,
            'files':[expected[p]for p in sorted(expected)]}
    raw=raw_json(expect);write(out/'expected-leaves.json',raw)
    meta['expected_leaves']={'file':'expected-leaves.json','bytes':len(raw),'sha256':sha(raw),'count':len(expected)}
    write(out/'manifest.json',raw_json(meta))
    return {k:v for k,v in meta.items()if k not in ('new_and_control_files','large_blob_requests','create_tree_groups')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('project','kit','source-filemap','controls-dir','out'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--mode',choices=('source','final'),required=True)
    parser.add_argument('--prior-expected',type=Path)
    parser.add_argument('--reviewed-files',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args),sort_keys=True))


if __name__=='__main__':main()
