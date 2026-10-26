"""Inherited x86_64 CPU0,1 and AF_UNIX-only socket-creation boundary."""
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import platform

FILTER_ROWS = [
    (0x20, 0, 0, 4), (0x15, 1, 0, 0xC000003E), (0x06, 0, 0, 0x80000000),
    (0x20, 0, 0, 0), (0x15, 8, 0, 203), (0x45, 7, 0, 0x40000000),
    (0x15, 6, 0, 425), (0x15, 5, 0, 426), (0x15, 4, 0, 427),
    (0x15, 1, 0, 41), (0x15, 0, 3, 53), (0x20, 0, 0, 16),
    (0x15, 1, 0, 1), (0x06, 0, 0, 0x00050000 | errno.EPERM),
    (0x06, 0, 0, 0x7FFF0000),
]


class Filter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint)]


class Program(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(Filter))]


def make_preexec(fd):
    if platform.machine() != "x86_64" or len(list(Path("/proc/self/task").iterdir())) != 1:
        raise RuntimeError("PREEXEC_SINGLE_THREAD_X86_64_REQUIRED")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    filters = (Filter * len(FILTER_ROWS))(*(Filter(*row) for row in FILTER_ROWS))
    program = Program(len(filters), filters)
    def install():
        record = {"status": "FAILED_BEFORE_EXEC", "pid": os.getpid()}
        try:
            os.sched_setaffinity(0, {0, 1})
            if os.sched_getaffinity(0) != {0, 1}: raise RuntimeError("CPU_AFFINITY")
            if libc.prctl(38, 1, 0, 0, 0) != 0: raise RuntimeError("NO_NEW_PRIVS")
            pointer = ctypes.cast(ctypes.pointer(program), ctypes.c_void_p).value
            if libc.prctl(22, 2, pointer, 0, 0) != 0: raise RuntimeError("SECCOMP_INSTALL")
            status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
            if status["NoNewPrivs"].strip() != "1" or status["Seccomp"].strip() != "2":
                raise RuntimeError("GUARD_NOT_OBSERVED")
            record.update(status="CPU_AND_UNIX_GUARD_INSTALLED_BEFORE_EXEC", CPU_affinity=[0, 1],
                          allowed_socket_domain=1, denied_sched_setaffinity=True,
                          denied_x32_and_io_uring=True, inherited_by_threads_and_exec=True,
                          filter_rows_sha256=hashlib.sha256(json.dumps(FILTER_ROWS).encode()).hexdigest(),
                          NoNewPrivs=1, Seccomp=2)
        except BaseException as error:
            record["error_type"] = type(error).__name__
            os.write(fd, (json.dumps(record) + "\n").encode()); os.fsync(fd); os.close(fd)
            raise
        os.write(fd, (json.dumps(record) + "\n").encode()); os.fsync(fd); os.close(fd)
    return install
