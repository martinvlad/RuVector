"""Public Python socket API interposition; stdin qualification needs no network.

This is an audited runtime policy, not an operating-system syscall sandbox.
All bind/DNS/connect/send/receive/listen/accept attempts remain persistently fatal.
"""
import socket
import sys
import traceback
import time


class OfflineGuard:
    def __init__(self, counters, progress):
        self.counters, self.progress = counters, progress
        self.violations = []

    def refuse(self, event, arguments):
        row = {'event': event, 'arguments': repr(arguments), 'monotonic_seconds': time.monotonic(),
               'stack': traceback.format_stack(limit=18), 'allowed': False}
        self.counters['Python_network_operations_attempted'] += 1
        self.violations.append(row)
        self.progress({'event': 'OFFLINE_FATAL_VIOLATION', 'network_record': row})
        raise RuntimeError('Persistent offline policy violation: ' + event)

    def install(self):
        guard = self
        def audit(event, arguments):
            if event.startswith(('socket.connect', 'socket.getaddrinfo', 'socket.gethostby',
                                 'socket.getnameinfo', 'socket.bind', 'socket.send', 'socket.sethostname')):
                guard.refuse(event, arguments)
        sys.addaudithook(audit)
        for name in ('bind', 'connect', 'connect_ex', 'send', 'sendall', 'sendfile', 'sendto',
                     'sendmsg', 'sendmsg_afalg', 'recv', 'recv_into', 'recvfrom', 'recvfrom_into',
                     'recvmsg', 'recvmsg_into', 'listen', 'accept', 'makefile'):
            if hasattr(socket.socket, name):
                def deny(sock, *args, _name=name, **kwargs):
                    return guard.refuse('socket.' + _name, args)
                setattr(socket.socket, name, deny)
        return self

    def assert_clean(self):
        if self.violations or self.counters['Python_network_operations_attempted']:
            raise RuntimeError('Caught network exception leaves persistent fatal flag')
