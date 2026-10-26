"""FUTURE ONLY: pinned absolute Node runtime, no native/module/model calls."""
import os
from pathlib import Path
import stat


def verify(C,plan):
    row=plan['node_runtime_manifest'];file=C.checked(row['path'])
    C.require(file.stat().st_size==row['bytes'] and C.sha(file)==row['sha256'],
              'NODE_RUNTIME_MANIFEST_IDENTITY')
    manifest=C.read(file);declaration=manifest['executable']
    path=C.no_symlink(plan['node_executable'])
    C.require(path==Path(declaration['path']) and path.is_absolute(),
              'NODE_EXECUTABLE_ABSOLUTE_DECLARATION')
    before=path.stat()
    C.require(stat.S_ISREG(before.st_mode) and before.st_uid==0 and
              before.st_mode&0o111 and not before.st_mode&0o022 and
              before.st_size==declaration['bytes'],'NODE_EXECUTABLE_FILE_ADMISSION')
    digest=C.sha(path);after=path.stat()
    signature=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid)
    C.require(signature(before)==signature(after) and digest==declaration['sha256'],
              'NODE_EXECUTABLE_STABLE_HASH')
    with path.open('rb')as source:header=source.read(20)
    C.require(header[:6]==b'\x7fELF\x02\x01' and header[18:20]==b'\x3e\x00',
              'NODE_EXECUTABLE_ELF64_X86_64')
    return {'path':str(path),'bytes':after.st_size,'sha256':digest,
            'observed_local_version':manifest['observed_local_version'],
            'full_payload_hash_verified':True,'ELF64_x86_64':True,
            'native_helper_or_module_initialized':False,
            'upstream_binary_reproducibility':'NOT_ESTABLISHED_LOCAL_EXECUTABLE_PIN_ONLY'}


def build_native_command(C,plan,source,target):
    executable=plan['node_executable']
    C.require(type(executable)is str and Path(executable).is_absolute(),
              'ABSOLUTE_PINNED_NODE_REQUIRED')
    return [executable,'--require='+str(C.CANDIDATE/'node_guard.cjs'),
            str(C.CANDIDATE/'native_helper.cjs'),str(source),str(target)]
