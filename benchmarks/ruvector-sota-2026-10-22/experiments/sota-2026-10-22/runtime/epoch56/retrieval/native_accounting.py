"""E56 validated native snapshots: assignment is idempotent for dict and Counter.

No native/runtime imports or fabricated operation counts. Expected totals are
validation bounds only. Only captured helper snapshots can populate counters;
a missing/partial/invalid capture remains unqualified and uncertain.
"""
import hashlib
import json
import math
import os
import stat
from pathlib import Path

KEYS = ('native_index_initializations_attempted','native_index_initializations_completed',
        'native_insertions_attempted','native_insertions_completed',
        'native_queries_attempted','native_queries_completed',
        'native_len_calls_attempted','native_len_calls_completed',
        'native_hit_source_validations','native_binary_loads_attempted',
        'native_binary_loads_completed','native_version_calls_attempted',
        'native_version_calls_completed','Node_network_operations_attempted')
EVENTS = {'NATIVE_LOAD_BEFORE','NATIVE_LOAD_COMPLETE','NATIVE_VERSION_BEFORE',
          'INDEX_BEFORE','INSERT_BEFORE','QUERY_BEFORE','QUERY_COMPLETE',
          'COMPLETE','FAILED','FORBIDDEN_NETWORK'}
MAX_BYTES = 4194304
MAX_RECORDS = 10000


def need(value, code):
    if not value:
        raise ValueError(code)


def unique_object(pairs):
    out = {}
    for key,value in pairs:
        need(key not in out, 'NATIVE_PROGRESS_DUPLICATE_JSON_KEY')
        out[key] = value
    return out


def expected_totals(plan, bundle):
    caps = plan['operation_caps']
    docs = bundle['documents']
    need(len(docs) == 4 and caps['native_indexes'] == 4
         and caps['native_queries'] == 12 and caps['engineering_total_fragment_cap'] == 256,
         'FROZEN_NATIVE_ACCOUNTING_GEOMETRY_CAPS')
    need(all(len(d['queries']) == 3 and type(d['vectors']['shape'][0]) is int
             and 1 <= d['vectors']['shape'][0] <= 256 for d in docs),
         'FROZEN_NATIVE_ACCOUNTING_DOCUMENT_GEOMETRY')
    insertions = sum(d['vectors']['shape'][0] for d in docs)
    need(insertions <= caps['engineering_total_fragment_cap'], 'FROZEN_NATIVE_INSERTION_CAP')
    return dict(zip(KEYS, (4,4,insertions,insertions,12,12,8,8,insertions*3,1,1,1,1,0)))


class NativeSnapshotLedger:
    def __init__(self, counters, expected):
        need(set(expected) == set(KEYS) and all(type(x) is int and x >= 0
                                              for x in expected.values()), 'NATIVE_EXPECTED_COUNTER_SCHEMA')
        need(all(type(counters.get(k,0)) is int and counters.get(k,0) == 0 for k in KEYS),
             'NATIVE_COUNTERS_MUST_START_AT_ZERO')
        self.counters = counters
        self.expected = dict(expected)
        self.latest = None
        self.last_event = None
        self.last_milliseconds = -1
        self.records = 0
        self.event_counts = {}
        self.last_row = None
        self.identical_snapshot_replays = 0
        self.qualified = False
        self.validation_failed = False
        self.capture_ref = None
        self.capture_complete = False

    def ingest(self, row):
        try:
            need(not self.validation_failed, 'NATIVE_ACCOUNTING_FAILURE_LATCHED')
            return self._ingest(row)
        except Exception:
            self.validation_failed = True
            self.qualified = False
            raise

    def _ingest(self, row):
        need(type(row) is dict and set(row) == {'event','monotonic_milliseconds','counters'},
             'NATIVE_PROGRESS_ROW_SCHEMA')
        event = row['event']; clock = row['monotonic_milliseconds']; snapshot = row['counters']
        need(event in EVENTS and type(clock) in (int,float) and math.isfinite(clock)
             and 0 <= clock <= 600000 and clock >= self.last_milliseconds, 'NATIVE_PROGRESS_EVENT_CLOCK')
        need(type(snapshot) is dict and set(snapshot) == set(KEYS), 'NATIVE_SNAPSHOT_EXACT_KEYS')
        need(all(type(v) is int and 0 <= v <= self.expected[k] for k,v in snapshot.items()),
             'NATIVE_SNAPSHOT_INTEGER_OPERATION_CAPS')
        for k in KEYS:
            if k.endswith('_attempted'):
                completed = k.replace('_attempted','_completed')
                if completed in snapshot:
                    need(snapshot[completed] <= snapshot[k], 'NATIVE_COMPLETED_NOT_ABOVE_ATTEMPTED')
        previous = self.latest or {k:0 for k in KEYS}
        need(all(snapshot[k] >= previous[k] for k in KEYS), 'NATIVE_SNAPSHOT_NONDECREASING')
        need(all(type(self.counters.get(k,0)) is int and self.counters.get(k,0) == previous[k]
                 for k in KEYS), 'NATIVE_PARENT_COUNTER_DRIFT')
        need(self.last_event not in ('COMPLETE','FAILED') or
             (event == self.last_event and snapshot == self.latest and clock == self.last_milliseconds),
             'NO_NATIVE_EVENTS_AFTER_TERMINAL_CAPTURE')
        if self.latest == snapshot:
            self.identical_snapshot_replays += 1
        if row != self.last_row:
            self.event_counts[event] = self.event_counts.get(event,0) + 1
        self.last_row = {'event':event,'monotonic_milliseconds':clock,'counters':dict(snapshot)}
        # Counter.update ADDS; direct assignment is essential and works for dict too.
        for k in KEYS:
            self.counters[k] = snapshot[k]
        self.latest = dict(snapshot)
        self.last_event = event
        self.last_milliseconds = clock
        self.records += 1
        self.qualified = False

    def capture(self, path):
        try:
            need(not self.validation_failed, 'NATIVE_ACCOUNTING_FAILURE_LATCHED')
            need(self.records == 0 and self.capture_ref is None, 'NATIVE_PROGRESS_CAPTURE_ONE_SHOT')
            self.capture_complete = False
            self.qualified = False
            return self._capture(path)
        except Exception:
            self.validation_failed = True
            self.qualified = False
            raise

    def _capture(self, path):
        path = Path(path)
        need(path.is_file() and not path.is_symlink(), 'NATIVE_PROGRESS_CAPTURE_REQUIRED')
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(descriptor)
            need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= MAX_BYTES,
                 'NATIVE_PROGRESS_CAPTURE_BYTE_CAP')
            chunks = []; size = 0
            while size <= MAX_BYTES:
                block = os.read(descriptor, min(65536,MAX_BYTES+1-size))
                if not block:
                    break
                size += len(block); chunks.append(block)
            after = os.fstat(descriptor)
            raw = b''.join(chunks)
            self.capture_ref = {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            need(len(raw) <= MAX_BYTES, 'NATIVE_PROGRESS_CAPTURE_BYTE_CAP')
            signature = lambda st:(st.st_dev,st.st_ino,st.st_mode,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
            need(signature(before) == signature(after) and len(raw) == before.st_size,
                 'NATIVE_PROGRESS_CAPTURE_STABLE_SOURCE')
        finally:
            os.close(descriptor)
        # Keep valid prefix evidence even when the final record is truncated.
        lines = raw.splitlines(keepends=True)
        need(len(lines) <= MAX_RECORDS, 'NATIVE_PROGRESS_CAPTURE_RECORD_CAP')
        for line in lines:
            need(line.endswith(b'\n'), 'NATIVE_PROGRESS_FINAL_NEWLINE')
            self.ingest(json.loads(line, object_pairs_hook=unique_object))
        self.capture_complete = True

    def finalize(self, value):
        try:
            need(not self.validation_failed, 'NATIVE_ACCOUNTING_FAILURE_LATCHED')
            return self._finalize(value)
        except Exception:
            self.validation_failed = True
            self.qualified = False
            raise

    def _finalize(self, value):
        need(self.capture_complete and self.records > 0 and self.last_event == 'COMPLETE',
             'NATIVE_TERMINAL_CAPTURE_REQUIRED')
        need(type(value) is dict and value.get('stage') == 'COMPLETE' and value.get('errors') == [],
             'NATIVE_TERMINAL_RECEIPT_REQUIRED')
        terminal = {k:value.get(k) for k in KEYS}
        need(all(type(terminal[k]) is int and terminal[k] == self.expected[k]
                 and terminal[k] == self.latest[k] and terminal[k] == self.counters.get(k)
                 for k in KEYS), 'NATIVE_TERMINAL_PARENT_SNAPSHOT_EXACT_AGREEMENT')
        expected_events = {'NATIVE_LOAD_BEFORE':self.expected['native_binary_loads_attempted'],
                           'NATIVE_LOAD_COMPLETE':self.expected['native_binary_loads_completed'],
                           'NATIVE_VERSION_BEFORE':self.expected['native_version_calls_attempted'],
                           'INDEX_BEFORE':self.expected['native_index_initializations_attempted'],
                           'INSERT_BEFORE':self.expected['native_insertions_attempted'],
                           'QUERY_BEFORE':self.expected['native_queries_attempted'],
                           'QUERY_COMPLETE':self.expected['native_queries_completed'],'COMPLETE':1}
        expected_events = {k:v for k,v in expected_events.items() if v}
        need(self.event_counts == expected_events, 'NATIVE_TERMINAL_EVENT_COUNTS_EXACT')
        self.qualified = True

    def receipt(self):
        pending = None if self.latest is None else any(
            self.latest[k] != self.latest[k.replace('_attempted','_completed')]
            for k in KEYS if k.endswith('_attempted')
            and k.replace('_attempted','_completed') in self.latest)
        return {'schema_version':1,'qualified':self.qualified,'validation_failure_latched':self.validation_failed,
                'single_source_of_truth':'Captured validated native helper progress plus exact terminal agreement.',
                'merge_semantics':'Direct per-key assignment, never Counter.update or expected-value fill.',
                'idempotence_scope':'Identical validated snapshot rows only. Full progress-file capture is one-shot; recapture fails closed.',
                'snapshot_records':self.records,'validated_unique_event_counts':dict(self.event_counts),'identical_counter_snapshot_replays':self.identical_snapshot_replays,
                'latest_validated_snapshot':self.latest,'last_event':self.last_event,
                'capture_ref':self.capture_ref,'capture_complete':self.capture_complete,
                'expected_totals_validation_only':dict(self.expected),
                'pending_attempt_completion_gap':pending,
                'inflight_native_call_outcome_uncertain':not self.qualified,
                'native_parent_totals_equal_captured_terminal':self.qualified}
