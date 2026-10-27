"""Stdlib-only resource and audit guards. Never retain network arguments."""
import os
from pathlib import Path

MIN_HEADROOM_BYTES = 3 * 1024 ** 3
HASH_CHUNK_BYTES = 1024 ** 2
FINITE_CHUNK_ELEMENTS = 1000000
NETWORK_EVENTS = frozenset(('socket.connect', 'socket.connect_ex', 'socket.bind',
    'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.sendto',
    'socket.sendmsg', 'socket.send', 'socket.sendall', 'socket.recv', 'socket.recv_into',
    'socket.recvfrom', 'socket.recvfrom_into', 'socket.recvmsg', 'socket.recvmsg_into',
    'socket.listen', 'socket.accept', 'socket.gethostbyname_ex', 'urllib.Request', 'http.client.connect'))
IMPORT_STAGES = frozenset(('reader_torch_import', 'reader_transformers_import'))


def memory_snapshot(root=Path('/sys/fs/cgroup')):
    maximum = (root / 'memory.max').read_text().strip()
    current = int((root / 'memory.current').read_text())
    events = {}
    for row in (root / 'memory.events').read_text().splitlines():
        key, value = row.split(); events[key] = int(value)
    return {'memory_max_bytes': None if maximum == 'max' else int(maximum),
            'memory_current_bytes': current,
            'headroom_bytes': None if maximum == 'max' else int(maximum) - current,
            'memory_events': events,
            'scope': 'Shared cgroup snapshot; not candidate incremental use or cause proof.'}


def require_headroom(snapshot):
    if type(snapshot['headroom_bytes']) is not int or snapshot['headroom_bytes'] < MIN_HEADROOM_BYTES:
        raise ValueError('MINIMUM_THREE_GIB_CGROUP_HEADROOM_REQUIRED')


class NetworkAudit:
    """Every audited operation raises before I/O, including optional import probes."""
    def __init__(self, counters):
        self.counters = counters; self.stage = 'worker_admission'; self.event_counts = {}
        self.stage_event_counts = {}; self.unexpected_blocked_attempts = 0

    def set_stage(self, stage):
        if type(stage) is not str or not stage.replace('_', '').isalnum():
            raise ValueError('NETWORK_STAGE_NAME')
        self.stage = stage

    def __call__(self, event, args):
        if event in NETWORK_EVENTS:
            self.counters['Python_network_operations_attempted'] += 1
            self.counters['Python_network_operations_blocked'] += 1
            self.event_counts[event] = self.event_counts.get(event, 0) + 1
            group = self.stage_event_counts.setdefault(self.stage, {})
            group[event] = group.get(event, 0) + 1
            # Only this source-evidenced optional import probe may be classified separately.
            # It is still denied; one total is the maximum over both import stages.
            if event != 'socket.bind' or self.stage not in IMPORT_STAGES:
                self.unexpected_blocked_attempts += 1
            raise RuntimeError('PYTHON_NETWORK_FORBIDDEN')

    def install_socket_guards(self):
        # CPython does not audit every send/receive API. Wrap the public socket
        # class before any framework import; wrappers still deny, never emulate I/O.
        import socket
        self.patched_socket_operations = []
        for name in ('connect', 'connect_ex', 'bind', 'send', 'sendall', 'sendto', 'sendmsg',
                     'recv', 'recv_into', 'recvfrom', 'recvfrom_into', 'recvmsg', 'recvmsg_into',
                     'listen', 'accept'):
            if hasattr(socket.socket, name):
                def deny(instance, *args, _event='socket.' + name, **kwargs):
                    self(_event, ())
                setattr(socket.socket, name, deny)
                self.patched_socket_operations.append('socket.' + name)
        for name in ('getaddrinfo', 'gethostbyname', 'gethostbyname_ex', 'gethostbyaddr'):
            def deny(*args, _event='socket.' + name, **kwargs):
                self(_event, ())
            setattr(socket, name, deny)
            self.patched_socket_operations.append('socket.' + name)

    def receipt(self):
        probe_count = sum(group.get('socket.bind', 0) for stage, group in
                          self.stage_event_counts.items() if stage in IMPORT_STAGES)
        return {'all_audited_operations_denied_before_IO': True,
                'public_socket_wrappers_installed': list(getattr(self, 'patched_socket_operations', [])),
                'audited_successful_network_operations': 0,
                'event_counts': dict(self.event_counts),
                'stage_event_counts': {k: dict(v) for k, v in self.stage_event_counts.items()},
                'blocked_optional_import_bind_probes': probe_count,
                'unexpected_blocked_attempts': self.unexpected_blocked_attempts,
                'admissible': self.unexpected_blocked_attempts == 0 and probe_count <= 1,
                'attribution': 'Optional urllib3 IPv6-probe compatibility, not E48 event attribution proof.',
                'scope': 'Python audit-hook events only; native Node guard separately checked; no host/argument values retained.'}
