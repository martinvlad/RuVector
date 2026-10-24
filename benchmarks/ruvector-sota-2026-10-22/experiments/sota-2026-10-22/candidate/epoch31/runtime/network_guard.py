"""Persistent offline API policy plus one pinned local IPv6 capability bind.

No dependency is preimported to hide its probe. This does not permit a service,
communication, or OS network syscall sandbox claim.
"""
import hashlib
from pathlib import Path
import socket
import sys
import threading
import time
import traceback

CAPABILITY_SOURCE_SHA = '2633bbdb69731e5ccb5cf4e4afd65605d86c7979cc5633126f50c92d5ad74a74'
CAPABILITY_COUNTER = 'Python_literal_loopback_capability_binds_allowed'


def literal_capability_bind(family, socket_type, protocol, address):
    return (family == socket.AF_INET6 and socket_type == socket.SOCK_STREAM and protocol == 0
        and type(address) is tuple and len(address) == 2
        and type(address[0]) is str and address[0] == '::1'
        and type(address[1]) is int and address[1] == 0)


class OfflineGuard:
    def __init__(self, counters, progress):
        self.counters, self.progress = counters, progress
        self.counters.setdefault(CAPABILITY_COUNTER, 0)
        self.events, self.violations = [], []
        self.pending = threading.local()
        self.lock = threading.RLock()
        self.allowed_sockets = {}
        self.expected_source = Path(sys.prefix) / 'lib/python3.12/site-packages/urllib3/util/connection.py'

    def record(self, event, arguments, allowed=False, provenance=None):
        sock = arguments[0] if arguments else None
        row = {'event': event, 'allowed': allowed, 'monotonic_seconds': time.monotonic(),
            'family': int(getattr(sock, 'family', 0)), 'socket_type': int(getattr(sock, 'type', 0)),
            'protocol': int(getattr(sock, 'proto', 0)), 'address': repr(arguments[-1] if arguments else None),
            'stack': traceback.format_stack(limit=20), 'bind_outcome': 'PENDING' if allowed else None,
            'close_outcome': 'PENDING' if allowed else None, 'source_provenance': provenance}
        self.events.append(row)
        if allowed:
            self.counters[CAPABILITY_COUNTER] += 1
            self.allowed_sockets[sock] = row
        else:
            self.counters['Python_network_operations_attempted'] += 1
            self.violations.append(row)
        self.progress({'event': 'OFFLINE_LITERAL_CAPABILITY_BIND_ALLOWED' if allowed else 'OFFLINE_FATAL_VIOLATION',
                       'network_record': row})
        if not allowed:
            raise RuntimeError('Persistent offline policy violation: ' + event)
        return row

    def permitted_caller(self, frame):
        path = Path(frame.f_code.co_filename).absolute()
        if (path != self.expected_source or frame.f_code.co_name != '_has_ipv6' or frame.f_lineno != 127
                or any(p.is_symlink() for p in (path, *path.parents))):
            return None
        if hashlib.sha256(path.read_bytes()).hexdigest() != CAPABILITY_SOURCE_SHA:
            return None
        return {'path': str(path), 'sha256': CAPABILITY_SOURCE_SHA,
                'function': '_has_ipv6', 'line': 127}

    def audit(self, event, arguments):
        if event == 'socket.bind':
            pending = getattr(self.pending, 'bind', None)
            if pending is not None and arguments[0] is pending[0] and arguments[1] == pending[1]:
                return
            self.record('socket.bind_unverified', arguments)
        elif event.startswith(('socket.connect', 'socket.getaddrinfo', 'socket.gethostby',
                                'socket.getnameinfo', 'socket.send', 'socket.sethostname')):
            self.record(event, arguments)

    def install(self):
        guard = self
        original_bind, original_close = socket.socket.bind, socket.socket.close
        sys.addaudithook(self.audit)

        def bind(sock, address):
            with guard.lock:
                provenance = guard.permitted_caller(sys._getframe(1))
                allowed = (type(sock) is socket.socket and provenance is not None
                    and guard.counters[CAPABILITY_COUNTER] < 1
                    and literal_capability_bind(sock.family, sock.type, sock.proto, address))
                row = guard.record('socket.bind', (sock, address), allowed, provenance)
            guard.pending.bind = (sock, address)
            try:
                result = original_bind(sock, address)
                row['bind_outcome'] = 'SUCCESS'
                return result
            except BaseException as error:
                row.update(bind_outcome='ERROR', bind_error_type=type(error).__name__,
                           bind_error_errno=getattr(error, 'errno', None))
                raise
            finally:
                guard.pending.bind = None
                guard.progress({'event': 'OFFLINE_LITERAL_CAPABILITY_BIND_OUTCOME', 'network_record': row})

        def close(sock, *args, **kwargs):
            row = guard.allowed_sockets.get(sock)
            try:
                result = original_close(sock, *args, **kwargs)
                if row is not None:
                    row.update(close_outcome='SUCCESS', close_monotonic_seconds=time.monotonic(),
                               file_descriptor_after_close=sock.fileno())
                return result
            except BaseException as error:
                if row is not None:
                    row.update(close_outcome='ERROR', close_error_type=type(error).__name__)
                raise
            finally:
                if row is not None:
                    guard.progress({'event': 'OFFLINE_LITERAL_CAPABILITY_BIND_CLOSED', 'network_record': row})

        socket.socket.bind, socket.socket.close = bind, close
        for name in ('connect', 'connect_ex', 'send', 'sendall', 'sendfile', 'sendto', 'sendmsg',
                     'sendmsg_afalg', 'recv', 'recv_into', 'recvfrom', 'recvfrom_into',
                     'recvmsg', 'recvmsg_into', 'listen', 'accept', 'makefile'):
            if hasattr(socket.socket, name):
                def deny(sock, *args, _name=name, **kwargs):
                    return guard.record('socket.' + _name, (sock, repr(args)))
                setattr(socket.socket, name, deny)
        return self

    def assert_clean(self):
        if self.violations or self.counters['Python_network_operations_attempted']:
            raise RuntimeError('Offline fatal flag persists after caught exceptions')
        count = self.counters[CAPABILITY_COUNTER]
        if type(count) is not int or not 0 <= count <= 1 or len(self.allowed_sockets) != count:
            raise RuntimeError('Pinned capability-bind allowance exceeded or inconsistent')
        for sock, row in self.allowed_sockets.items():
            if (row['bind_outcome'] not in ('SUCCESS', 'ERROR') or row['close_outcome'] != 'SUCCESS'
                    or row.get('file_descriptor_after_close') != -1 or sock.fileno() != -1):
                raise RuntimeError('Pinned capability socket did not close immediately after its probe')
