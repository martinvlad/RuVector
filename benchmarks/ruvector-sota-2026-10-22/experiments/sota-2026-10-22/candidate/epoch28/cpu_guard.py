"""Per-child Linux x86_64 CPU-affinity enforcement, before Node/native init.

After fixing the child to CPU0,1, no_new_privs and an inherited seccomp filter
deny sched_setaffinity (including its x32 number) with EPERM. This is a narrow
OS resource boundary, not a network or general syscall sandbox.
"""
import ctypes
import errno
import json
import os
from pathlib import Path
import platform

PR_SET_SECCOMP, PR_SET_NO_NEW_PRIVS = 22, 38
SECCOMP_MODE_FILTER = 2
AUDIT_ARCH_X86_64 = 0xC000003E
SCHED_SETAFFINITY_X86_64 = 203


class SockFilter(ctypes.Structure):
    _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte),
                ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint)]


class SockFprog(ctypes.Structure):
    _fields_ = [('len', ctypes.c_ushort), ('filter', ctypes.POINTER(SockFilter))]


def prepare():
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError('Frozen CPU guard supports Linux x86_64 only')
    # Preload libc before fork; the admitted worker must have one OS thread.
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    filters = (SockFilter * 8)(
        SockFilter(0x20, 0, 0, 4),                         # load seccomp_data.arch
        SockFilter(0x15, 1, 0, AUDIT_ARCH_X86_64),          # correct arch skips kill
        SockFilter(0x06, 0, 0, 0x80000000),                # KILL_PROCESS wrong arch
        SockFilter(0x20, 0, 0, 0),                         # load syscall nr
        SockFilter(0x15, 1, 0, SCHED_SETAFFINITY_X86_64),  # deny native ABI
        SockFilter(0x15, 0, 1, SCHED_SETAFFINITY_X86_64 | 0x40000000),
        SockFilter(0x06, 0, 0, 0x00050000 | errno.EPERM), # ERRNO EPERM
        SockFilter(0x06, 0, 0, 0x7FFF0000))               # ALLOW all other syscalls
    program = SockFprog(len(filters), filters)

    def install():
        if len(filters) != 8:
            raise RuntimeError('Frozen BPF storage changed')
        os.sched_setaffinity(0, {0, 1})
        if os.sched_getaffinity(0) != {0, 1}:
            raise RuntimeError('Exact child CPU0,1 affinity was not established')
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            error = ctypes.get_errno()
            raise OSError(error, 'PR_SET_NO_NEW_PRIVS failed')
        address = ctypes.cast(ctypes.pointer(program), ctypes.c_void_p).value
        if libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, address, 0, 0) != 0:
            error = ctypes.get_errno()
            raise OSError(error, 'PR_SET_SECCOMP filter failed')
        values = {}
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith(('NoNewPrivs:', 'Seccomp:', 'Seccomp_filters:', 'Cpus_allowed_list:')):
                key, value = line.split(':', 1)
                values[key] = value.strip()
        if values.get('NoNewPrivs') != '1' or values.get('Seccomp') != '2':
            raise RuntimeError('Actual child NNP/seccomp enforcement not observed')
        return {'status': 'CPU_GUARD_INSTALLED_BEFORE_EXEC', 'platform': 'linux-x86_64',
            'CPU_affinity': sorted(os.sched_getaffinity(0)), 'denied_syscalls': [203, 0x400000CB],
            'denial_errno': errno.EPERM, 'inherited_by_all_future_threads_and_exec': True,
            'actual_proc_status': values, 'global_kernel_configuration_changed': False}
    # Keep the complete BPF storage alive through the closure, including install.
    return install


def make_preexec(receipt_fd):
    if len(list(Path('/proc/self/task').iterdir())) != 1:
        raise RuntimeError('preexec CPU policy requires exactly one parent OS thread')
    install = prepare()
    def child():
        try:
            record = install()
        except BaseException as error:
            record = {'status': 'CPU_GUARD_FAILED_BEFORE_EXEC', 'type': type(error).__name__,
                'message': str(error), 'errno': getattr(error, 'errno', None)}
            payload = (json.dumps(record, allow_nan=False) + '\n').encode('utf-8')
            os.write(receipt_fd, payload)
            os.fsync(receipt_fd)
            os.close(receipt_fd)
            raise
        payload = (json.dumps(record, allow_nan=False) + '\n').encode('utf-8')
        view = memoryview(payload)
        while view:
            count = os.write(receipt_fd, view)
            if count <= 0:
                raise RuntimeError('Cannot persist preexec CPU policy receipt')
            view = view[count:]
        os.fsync(receipt_fd)
        os.close(receipt_fd)
    return child
