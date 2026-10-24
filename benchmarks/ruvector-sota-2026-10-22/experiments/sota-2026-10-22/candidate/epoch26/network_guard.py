"""Prospective offline policy: audited loopback binds, persistent fatal violations.

No dependency is preimported outside this policy to conceal a network event.
The urllib3 IPv6 capability probe may bind literal ::1:0; it cannot connect.
"""
from __future__ import annotations
import socket
import sys
import time
import traceback


def literal_loopback_bind(family, address):
    if family not in (socket.AF_INET, socket.AF_INET6) or type(address) is not tuple:
        return False
    if ((family == socket.AF_INET and len(address) != 2)
            or (family == socket.AF_INET6 and len(address) not in (2, 4))):
        return False
    host, port = address[:2]
    if (host != ('127.0.0.1' if family == socket.AF_INET else '::1')
            or type(port) is not int or not 0 <= port <= 65535):
        return False
    if family == socket.AF_INET6 and len(address) == 4 and (type(address[2]) is not int or type(address[3]) is not int
                                      or address[2] != 0 or address[3] != 0):
        return False
    return True


class OfflineGuard:
    def __init__(self, counters, progress):
        self.counters, self.progress = counters, progress
        self.events, self.violations = [], []
        self.pending_bind = None

    def record(self, event, arguments, *, allowed=False):
        sock = arguments[0] if arguments else None
        family = getattr(sock, 'family', None)
        address = arguments[-1] if arguments else None
        row = {'event': event, 'allowed': allowed,
               'monotonic_seconds': time.monotonic(),
               'family': int(family) if family is not None else None,
               'socket_type': int(getattr(sock, 'type', 0)) if family is not None else None,
               'protocol': int(getattr(sock, 'proto', 0)) if family is not None else None,
               'address': repr(address),
               'bind_outcome': 'PENDING' if allowed else None,
               'stack': traceback.format_stack(limit=18)}
        self.events.append(row)
        if allowed:
            self.counters['Python_literal_loopback_binds_allowed'] += 1
        else:
            self.counters['Python_network_operations_attempted'] += 1
            self.violations.append(row)
        self.progress({'event': 'OFFLINE_LOOPBACK_BIND_ALLOWED' if allowed else 'OFFLINE_FATAL_VIOLATION',
                       'network_record': row})
        if not allowed:
            raise RuntimeError('Persistent offline policy violation: ' + event)
        return row

    def audit(self, event, arguments):
        if event == 'socket.bind':
            # Only the wrapper below can establish and finish an allowed bind.
            if (self.pending_bind is not None and arguments[0] is self.pending_bind[0]
                    and arguments[1] == self.pending_bind[1]):
                return
            self.record('socket.bind_unverified', arguments)
        elif event in ('socket.connect', 'socket.connect_ex', 'socket.getaddrinfo',
                       'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.getnameinfo',
                       'socket.sendto', 'socket.sendmsg', 'socket.sethostname'):
            self.record(event, arguments)

    def install(self):
        sys.addaudithook(self.audit)
        # CPython does not emit audit events for every connected send or listen.
        # Explicit wrappers cover these methods; caught exceptions leave violations.
        guard = self
        original_bind = socket.socket.bind

        def bind(sock, address):
            row = guard.record('socket.bind', (sock, address),
                allowed=literal_loopback_bind(sock.family, address))
            guard.pending_bind = (sock, address)
            try:
                result = original_bind(sock, address)
                row['bind_outcome'] = 'SUCCESS'
                return result
            except BaseException as error:
                row['bind_outcome'] = 'ERROR'
                row['bind_error_type'] = type(error).__name__
                row['bind_error_errno'] = getattr(error, 'errno', None)
                raise
            finally:
                guard.pending_bind = None
                guard.progress({'event': 'OFFLINE_LOOPBACK_BIND_OUTCOME', 'network_record': row})

        socket.socket.bind = bind
        for name in ('send', 'sendall', 'sendfile', 'sendto', 'sendmsg', 'sendmsg_afalg',
                     'recv', 'recv_into', 'recvfrom', 'recvfrom_into', 'recvmsg', 'recvmsg_into',
                     'listen', 'accept', 'makefile'):
            if hasattr(socket.socket, name):
                def deny(sock, *args, _name=name, **kwargs):
                    return guard.record('socket.' + _name, (sock, repr(args)))
                setattr(socket.socket, name, deny)
        return self

    def assert_clean(self):
        if self.violations or self.counters['Python_network_operations_attempted']:
            raise RuntimeError('Offline policy fatal flag persists after caught exception')
