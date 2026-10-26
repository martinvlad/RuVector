"""Restore only the reviewed287 public project files from one exact E42 ZIP.

All archive members, manifest bodies, projection rows and existing output
collisions are validated before any mkdir/write. No Git/model/scoring calls.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

PLAN_SHA='d41c1afe052646110a2102ccb5ea2c69dda8cfe20a49c01c028028db905ca921'
PROJECTION_BYTES=122071
PROJECTION_SHA='749265d94e7c5389671642bda12e9a2c83d4d618589961ec5303c671c6471823'
ARCHIVE_BYTES=4531795
ARCHIVE_SHA='b1563d4bd7b8ea54e69f6a2d1047130b95a94748d58e83fabcf465431c64cbca'
ARCHIVE_GIT='22669777496cdcb3d957bbe237bb8e5b70f5fde5'
WORKDIR=Path('/tmp/ruvector-sota-2026-10-22/epoch42-archive-recovery-20261026T040538')
IMMUTABLE_ROOTS=(Path('/tmp/ruvector-sota-2026-10-22/epoch42-222874558c0b'),
    Path('/tmp/ruvector-sota-2026-10-22/epoch42-recovery-20261026T0318'))
IMMUTABLE_FILES=(Path('/workspace/ruvector-epoch42-public-recovery.zip'),
    Path('/workspace/ruvector-e42-recovery-supplement-20261026.zip'))
POLICY={'members':357,'manifest_rows':356,'manifest':'RECOVERY_MANIFEST.json',
        'manifest_bytes':82489,'manifest_sha256':'b7ec88e16590d03293366bb5db30d07848f939487f371988c42d5e08587982a5',
        'total_bytes':20067025,'selected':287,'selected_bytes':4900638,'prefix':'public-project/'}


def digest(data):return hashlib.sha256(data).hexdigest()


def git_blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


def require(ok,code):
    if not ok:raise ValueError(code)


def pairs(rows):
    value={}
    for key,item in rows:
        require(key not in value,'DUPLICATE_JSON_KEY');value[key]=item
    return value


def parse(data):
    return json.loads(data,object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in()).throw(ValueError('NONFINITE_JSON')))


def safe_name(name):
    require(type(name)is str and name and '\\'not in name and '\0'not in name and ':'not in name,'UNSAFE_RELATIVE_NAME')
    path=PurePosixPath(name)
    require(name!='.'and path.parts and not path.is_absolute()and path.as_posix()==name and not name.endswith('/')
        and all(part not in('','.','..')for part in path.parts),'UNSAFE_RELATIVE_NAME')
    name.encode('utf-8',errors='strict')
    return name


def no_symlink(path):
    path=Path(path)
    for item in (path,*path.parents):
        try:info=item.lstat()
        except FileNotFoundError:continue
        require(not stat.S_ISLNK(info.st_mode),'SYMLINK_ANCESTOR_OR_FILE')
        if item!=path:require(stat.S_ISDIR(info.st_mode),'ANCESTOR_NOT_DIRECTORY')
    return path


def checked_read(path,size,sha,git=None):
    path=no_symlink(path);info=path.stat()
    require(stat.S_ISREG(info.st_mode)and info.st_size==size,'INPUT_SIZE_OR_TYPE_MISMATCH')
    with path.open('rb')as stream:data=stream.read(size+1)
    require(len(data)==size and digest(data)==sha,'INPUT_SHA256_MISMATCH')
    if git is not None:require(git_blob(data)==git,'DECODED_GIT_BLOB_SHA1_MISMATCH')
    return data


def _validated_payloads(data,projection,policy):
    """Pure validator; fixture policies are internal-only, never a CLI option."""
    require(type(projection)is dict and type(projection.get('project_files'))is list,'BAD_PROJECTION')
    selected={}
    for row in projection['project_files']:
        require(type(row)is dict and set(row)=={'path','archive_member','bytes','sha256','present_in_SOURCE_Git'},'BAD_PROJECTION_ROW')
        path=safe_name(row['path']);member=safe_name(row['archive_member'])
        require(member==policy['prefix']+path and path not in selected,'PROJECTION_DUPLICATE_OR_PREFIX')
        require(type(row['bytes'])is int and 0<=row['bytes']<=policy['total_bytes']
            and type(row['sha256'])is str and re.fullmatch('[0-9a-f]{64}',row['sha256'])
            and type(row['present_in_SOURCE_Git'])is bool,'BAD_PROJECTION_IDENTITY')
        selected[path]=row
    require(len(selected)==policy['selected'],'WRONG_SELECTED_COUNT')
    require(sum(row['bytes']for row in selected.values())==policy['selected_bytes'],'WRONG_SELECTED_BYTES')
    payloads={};all_names=set();total=0
    with zipfile.ZipFile(io.BytesIO(data),'r')as archive:
        infos=archive.infolist();require(len(infos)==policy['members'],'WRONG_ARCHIVE_MEMBER_COUNT')
        for info in infos:
            name=safe_name(info.filename)
            require(info.orig_filename==info.filename and name not in all_names,'DUPLICATE_OR_TRUNCATED_ARCHIVE_NAME')
            all_names.add(name);mode=info.external_attr>>16
            require(not info.is_dir()and not(info.external_attr&0x10)
                and stat.S_IFMT(mode)in(0,stat.S_IFREG)and not(mode&0o7000),'ARCHIVE_DIRECTORY_SYMLINK_OR_SPECIAL')
            require(not(info.flag_bits&0x41),'ENCRYPTED_ARCHIVE_MEMBER')
            require(type(info.file_size)is int and 0<=info.file_size<=policy['total_bytes'],'MEMBER_SIZE_BOUND')
            require(0<=info.compress_size<=len(data),'COMPRESSED_SIZE_BOUND');total+=info.file_size
        require(total==policy['total_bytes'],'ARCHIVE_UNCOMPRESSED_BOUND_OR_IDENTITY')
        require(policy['manifest']in all_names,'MISSING_EMBEDDED_MANIFEST')
        manifest_info=archive.getinfo(policy['manifest'])
        require(manifest_info.file_size==policy['manifest_bytes'],'MANIFEST_SIZE')
        manifest_data=archive.read(manifest_info)
        require(digest(manifest_data)==policy['manifest_sha256'],'MANIFEST_SHA256')
        manifest=parse(manifest_data);rows=manifest.get('files')
        require(type(rows)is list and len(rows)==policy['manifest_rows'],'MANIFEST_ROW_COUNT')
        declared={}
        for row in rows:
            require(type(row)is dict and set(row)=={'path','bytes','sha256'},'BAD_MANIFEST_ROW')
            name=safe_name(row['path'])
            require(name not in declared and name!=policy['manifest'],'DUPLICATE_OR_SELF_MANIFEST_ROW')
            require(type(row['bytes'])is int and 0<=row['bytes']<=policy['total_bytes']
                and type(row['sha256'])is str and re.fullmatch('[0-9a-f]{64}',row['sha256']),'BAD_MANIFEST_IDENTITY')
            declared[name]=row
        require(set(declared)==all_names-{policy['manifest']},'MANIFEST_MEMBER_SET_MISMATCH')
        require({name for name in all_names if name.startswith(policy['prefix'])}
            =={row['archive_member']for row in selected.values()},'EXACT_PUBLIC_MEMBER_SELECTION_MISMATCH')
        wanted={row['archive_member']:path for path,row in selected.items()}
        for name,row in declared.items():
            info=archive.getinfo(name);require(info.file_size==row['bytes'],'DECLARED_MEMBER_SIZE_MISMATCH')
            with archive.open(info,'r')as stream:body=stream.read(row['bytes']+1)
            require(len(body)==row['bytes']and digest(body)==row['sha256'],'MEMBER_BODY_HASH_OR_SIZE_MISMATCH')
            if name in wanted:
                path=wanted[name];selected_row=selected[path]
                require(row['bytes']==selected_row['bytes']and row['sha256']==selected_row['sha256'],'PROJECTION_MANIFEST_MISMATCH')
                payloads[path]=body
    require(len(payloads)==policy['selected'],'SELECTED_VALIDATION_INCOMPLETE')
    return payloads,{'archive_members_verified':len(all_names),'manifest_bodies_verified':len(declared),
        'archive_uncompressed_bytes_verified':total,'selected_files_verified':len(payloads),
        'selected_bytes_verified':sum(map(len,payloads.values()))}


def _check_roots(kit,dest,scope):
    scope=no_symlink(scope).absolute()
    require(scope==scope.resolve(),'NONCANONICAL_SCOPE')
    require(all(not _overlap(scope,old)for old in(*IMMUTABLE_ROOTS,*IMMUTABLE_FILES)),
        'RESTORE_SCOPE_OVERLAPS_IMMUTABLE_ORIGINAL')
    roots=[]
    for root in(kit,dest):
        root=no_symlink(root).absolute()
        require(root==root.resolve()and root!=scope and scope in root.parents,'TARGET_MUST_BE_CANONICAL_NEW_SCOPE_CHILD')
        require(all(not _overlap(root,old)for old in(*IMMUTABLE_ROOTS,*IMMUTABLE_FILES)),
            'TARGET_OVERLAPS_IMMUTABLE_ORIGINAL')
        if root.exists():require(root.is_dir(),'TARGET_ROOT_NOT_DIRECTORY')
        roots.append(root)
    require(roots[0]!=roots[1]and roots[0]not in roots[1].parents and roots[1]not in roots[0].parents,'OVERLAPPING_KIT_AND_PROJECT')
    require(roots[0].parent==roots[1].parent,'KIT_AND_PROJECT_MUST_BE_SIBLINGS')
    return roots


def _overlap(left,right):return left==right or left in right.parents or right in left.parents


def _preflight_targets(payloads,roots,verify_only,inputs=()):
    actions=[];input_set={Path(path).absolute()for path in(*inputs,*IMMUTABLE_FILES)}
    for root in roots:
        for relative,body in payloads.items():
            target=no_symlink(root/safe_name(relative))
            require(all(not _overlap(target,path)for path in input_set),'OUTPUT_WOULD_MUTATE_SOURCE_INPUT')
            for parent in target.parents:
                if parent.exists():require(parent.is_dir(),'TARGET_PARENT_NOT_DIRECTORY')
                if parent==root:break
            if target.exists():
                require(stat.S_ISREG(target.stat().st_mode),'EXISTING_TARGET_NOT_REGULAR')
                require(target.stat().st_size==len(body)and target.read_bytes()==body,'EXISTING_TARGET_DIFFERS_NO_OVERWRITE')
                actions.append((target,body,False))
            else:
                require(not verify_only,'VERIFY_ONLY_TARGET_MISSING');actions.append((target,body,True))
    return actions


def _mkdirs(path):
    missing=[];cursor=path
    while not cursor.exists():missing.append(cursor);cursor=cursor.parent
    require(cursor.is_dir(),'MISSING_PARENT_IS_NOT_DIRECTORY')
    for item in reversed(missing):
        no_symlink(item)
        try:os.mkdir(item,0o755)
        except FileExistsError:require(item.is_dir()and not item.is_symlink(),'DIRECTORY_RACE_MISMATCH')
        fd=os.open(item.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)


def _materialize(payloads,kit,dest,scope,verify_only=False,inputs=()):
    roots=_check_roots(kit,dest,scope)
    # Both complete target sets are checked before the first mkdir/filewrite.
    actions=_preflight_targets(payloads,roots,verify_only,inputs)
    written=[0,0];existing=[0,0]
    for index,(target,body,missing)in enumerate(actions):
        root_index=index//len(payloads)
        if not missing:existing[root_index]+=1;continue
        _mkdirs(target.parent);no_symlink(target)
        try:fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
        except FileExistsError:
            require(target.is_file()and not target.is_symlink()and target.read_bytes()==body,'FILE_RACE_MISMATCH_NO_OVERWRITE')
            existing[root_index]+=1;continue
        with os.fdopen(fd,'wb')as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
        directory=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
        written[root_index]+=1
    # Recheck every projected body in both destinations after all fsynced writes.
    _preflight_targets(payloads,roots,True,inputs)
    return {'kit_written':written[0],'dest_written':written[1],
        'kit_identical_existing_verified':existing[0],'dest_identical_existing_verified':existing[1],
        'both_destinations_complete':True,'overwrites':0,'hardlinks_created':0,'verify_only':verify_only}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit-root','--kit',dest='kit_root',type=Path,required=True)
    parser.add_argument('--dest',type=Path,required=True)
    parser.add_argument('--restore-scope',type=Path,default=WORKDIR,
        help='Canonical fresh isolated scope; historical transaction owner remains recorded in the pinned plan')
    parser.add_argument('--archive',type=Path,required=True,help='Relative to KIT, or exact absolute regular input')
    parser.add_argument('--projection',type=Path,required=True,help='Relative to KIT, or exact absolute regular input')
    parser.add_argument('--plan',type=Path,default=Path('recoveries/epoch42-publication-20261026/RECOVERY_TRANSACTION_PLAN.v1.json'))
    parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
    kit,dest=_check_roots(args.kit_root,args.dest,args.restore_scope)
    locate=lambda path:path if path.is_absolute()else kit/path
    archive_path,projection_path,plan_path=map(locate,(args.archive,args.projection,args.plan))
    plan_data=checked_read(plan_path,12133,PLAN_SHA);plan=parse(plan_data)
    require(plan['new_exclusive_owner']['workdir']==str(WORKDIR),'PLAN_NEW_SCOPE_MISMATCH')
    projection_data=checked_read(projection_path,PROJECTION_BYTES,PROJECTION_SHA)
    projection=parse(projection_data)
    require(projection['project_prefix']==POLICY['prefix']and projection['archive_total_members']==357
        and projection['archive_uncompressed_bytes']==POLICY['total_bytes'],'PROJECTION_HEADER_MISMATCH')
    archive_data=checked_read(archive_path,ARCHIVE_BYTES,ARCHIVE_SHA,ARCHIVE_GIT)
    payloads,report=_validated_payloads(archive_data,projection,POLICY)
    # No selected or unselected archive member has yet caused any targetwrite.
    report.update(_materialize(payloads,kit,dest,args.restore_scope,args.verify_only,
        inputs=(archive_path,projection_path,plan_path,Path(__file__))))
    report.update(schema_version=1,epoch=42,status='EXACT_ARCHIVE_PUBLIC_PROJECTION_RESTORED',
        archive_bytes=ARCHIVE_BYTES,archive_sha256=ARCHIVE_SHA,archive_Git_blob_sha1=ARCHIVE_GIT,
        projection_sha256=PROJECTION_SHA,kit_root=str(kit),dest=str(dest),
        nonselected_members_extracted=0,Git_model_native_Gold_EVAL_calls=0)
    print(json.dumps(report,sort_keys=True));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status':'ARCHIVE_RESTORATION_REFUSED','error_type':type(error).__name__,
            'message_sha256':digest(str(error).encode()),'Git_model_native_Gold_EVAL_calls':0}),file=sys.stderr)
        raise SystemExit(2)
