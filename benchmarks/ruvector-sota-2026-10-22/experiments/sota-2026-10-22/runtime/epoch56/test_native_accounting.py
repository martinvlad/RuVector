"""Invented scalar snapshots and mocked subprocesses; no real native/model calls."""
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_accounting import NativeSnapshotLedger, expected_totals, KEYS, MAX_BYTES
import native_accounting
import support


def geometry():
    bundle={'schema_version':1,'epoch':56,'kind':support.KIND,'phase':'engineering','documents':[
        {'vectors':{'shape':[n,384]},'queries':[{}, {}, {}]}for n in [3,4,2,1]]}
    plan={'operation_caps':{'native_indexes':4,'native_queries':12,'engineering_total_fragment_cap':256}}
    return plan,bundle


def invented_stream():
    plan,bundle=geometry();expected=expected_totals(plan,bundle);counts={k:0 for k in KEYS};rows=[]
    def event(name,**changes):
        for k,v in changes.items():counts[k]+=v
        rows.append({'event':name,'monotonic_milliseconds':float(len(rows)+1),'counters':dict(counts)})
    event('NATIVE_LOAD_BEFORE',native_binary_loads_attempted=1)
    event('NATIVE_LOAD_COMPLETE',native_binary_loads_completed=1)
    event('NATIVE_VERSION_BEFORE',native_version_calls_attempted=1);counts['native_version_calls_completed']+=1
    for d in bundle['documents']:
        event('INDEX_BEFORE',native_index_initializations_attempted=1);counts['native_index_initializations_completed']+=1
        counts['native_len_calls_attempted']+=1;counts['native_len_calls_completed']+=1
        for _ in range(d['vectors']['shape'][0]):
            event('INSERT_BEFORE',native_insertions_attempted=1);counts['native_insertions_completed']+=1
        counts['native_len_calls_attempted']+=1;counts['native_len_calls_completed']+=1
        for _ in range(3):
            event('QUERY_BEFORE',native_queries_attempted=1)
            event('QUERY_COMPLETE',native_queries_completed=1,native_hit_source_validations=d['vectors']['shape'][0])
    event('COMPLETE');assert counts==expected
    value={'stage':'COMPLETE','errors':[],**counts}
    return rows,value,expected


def capture(ledger,root,rows):
    p=root/'native-progress.jsonl';p.write_text(''.join(json.dumps(x)+'\n'for x in rows));ledger.capture(p)


class SnapshotTests(unittest.TestCase):
    def test_counter_and_dict_full_native_event_totals_not_doubled(self):
        rows,value,expected=invented_stream()
        for factory in [dict,Counter]:
            with self.subTest(factory=factory.__name__),tempfile.TemporaryDirectory()as d:
                c=factory();l=NativeSnapshotLedger(c,expected);capture(l,Path(d),rows);l.finalize(value)
                self.assertTrue(l.receipt()['qualified']);self.assertEqual({k:c[k]for k in KEYS},expected)
                self.assertEqual(c['native_queries_completed'],12)
    def test_identical_snapshot_replay_is_idempotent_for_dict_and_counter(self):
        rows,value,expected=invented_stream();rows=rows+[copy.deepcopy(rows[-1])]
        for factory in [dict,Counter]:
            with tempfile.TemporaryDirectory()as d:
                c=factory();l=NativeSnapshotLedger(c,expected);capture(l,Path(d),rows);l.finalize(value)
                self.assertEqual(c['native_index_initializations_completed'],4)
                self.assertEqual(l.receipt()['validated_unique_event_counts']['COMPLETE'],1)
    def test_generic_single_index_large_snapshot_schema(self):
        # Invented event scalars only: no corpus, embeddings, model or native code.
        e=dict(zip(KEYS,(1,1,5183,5183,16,16,2,2,160,1,1,1,1,0)));c=Counter();l=NativeSnapshotLedger(c,e)
        counts={k:0 for k in KEYS};rows=[]
        def event(name,**changes):
            for k,v in changes.items():counts[k]+=v
            rows.append({'event':name,'monotonic_milliseconds':len(rows)+1,'counters':dict(counts)})
        event('NATIVE_LOAD_BEFORE',native_binary_loads_attempted=1);event('NATIVE_LOAD_COMPLETE',native_binary_loads_completed=1)
        event('NATIVE_VERSION_BEFORE',native_version_calls_attempted=1);counts['native_version_calls_completed']=1
        event('INDEX_BEFORE',native_index_initializations_attempted=1);counts['native_index_initializations_completed']=1
        counts['native_len_calls_attempted']=1;counts['native_len_calls_completed']=1
        for _ in range(5183):event('INSERT_BEFORE',native_insertions_attempted=1);counts['native_insertions_completed']+=1
        counts['native_len_calls_attempted']=2;counts['native_len_calls_completed']=2
        for _ in range(16):
            event('QUERY_BEFORE',native_queries_attempted=1);event('QUERY_COMPLETE',native_queries_completed=1,native_hit_source_validations=10)
        event('COMPLETE');self.assertEqual(counts,e)
        with tempfile.TemporaryDirectory()as d:capture(l,Path(d),rows)
        l.finalize({'stage':'COMPLETE','errors':[],**counts});self.assertEqual({k:c[k]for k in KEYS},e)
        self.assertTrue(l.receipt()['qualified']);self.assertLess(l.receipt()['capture_ref']['bytes'],MAX_BYTES)
    def test_unrelated_python_counters_preserved(self):
        _,_,e=invented_stream();c=Counter(BGE_forward_calls_attempted=7,native_corpus_batches_attempted=1)
        l=NativeSnapshotLedger(c,e);l.ingest(invented_stream()[0][0]);self.assertEqual(c['BGE_forward_calls_attempted'],7)
        self.assertEqual(c['native_corpus_batches_attempted'],1)
    def test_pending_attempt_stays_uncertain_without_terminal(self):
        rows,_,e=invented_stream();c=Counter();l=NativeSnapshotLedger(c,e);l.ingest(rows[0])
        self.assertEqual(c['native_binary_loads_attempted'],1);self.assertEqual(c['native_binary_loads_completed'],0)
        self.assertTrue(l.receipt()['pending_attempt_completion_gap']);self.assertTrue(l.receipt()['inflight_native_call_outcome_uncertain'])
    def test_missing_capture_never_fills_expected_counts(self):
        _,v,e=invented_stream();c=Counter();l=NativeSnapshotLedger(c,e)
        with tempfile.TemporaryDirectory()as d:
            with self.assertRaises(ValueError):l.capture(Path(d)/'missing')
        with self.assertRaises(ValueError):l.finalize(v)
        self.assertEqual(dict(c),{});self.assertTrue(l.receipt()['validation_failure_latched'])
    def test_partial_last_record_retains_valid_prefix(self):
        rows,_,e=invented_stream();c=Counter();l=NativeSnapshotLedger(c,e)
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'partial';p.write_text(json.dumps(rows[0])+'\n'+json.dumps(rows[1])[:-5])
            with self.assertRaisesRegex(ValueError,'NATIVE_PROGRESS_FINAL_NEWLINE'):l.capture(p)
            self.assertEqual(l.receipt()['capture_ref']['sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertEqual(c['native_binary_loads_attempted'],1);self.assertEqual(c['native_binary_loads_completed'],0)
        self.assertTrue(l.receipt()['inflight_native_call_outcome_uncertain'])
    def test_full_log_capture_is_explicitly_one_shot(self):
        rows,value,e=invented_stream();l=NativeSnapshotLedger(Counter(),e)
        with tempfile.TemporaryDirectory()as d:
            root=Path(d);capture(l,root,rows);l.finalize(value)
            with self.assertRaisesRegex(ValueError,'NATIVE_PROGRESS_CAPTURE_ONE_SHOT'):l.capture(root/'native-progress.jsonl')
        self.assertFalse(l.receipt()['qualified']);self.assertTrue(l.receipt()['validation_failure_latched'])
    def test_invalid_counts_types_keys_and_caps_latch_failure(self):
        rows,_,e=invented_stream()
        edits=[lambda s:s.update(native_binary_loads_attempted=True),lambda s:s.update(native_binary_loads_attempted=1.0),
               lambda s:s.update(native_binary_loads_attempted=-1),lambda s:s.update(native_binary_loads_attempted=2),
               lambda s:s.update(native_extra_count=0),lambda s:s.pop('native_queries_attempted'),
               lambda s:s.update(native_binary_loads_completed=1,native_binary_loads_attempted=0),
               lambda s:s.update(Node_network_operations_attempted=1)]
        for edit in edits:
            c=Counter();l=NativeSnapshotLedger(c,e);row=copy.deepcopy(rows[0]);edit(row['counters'])
            with self.subTest(edit=edit),self.assertRaises(ValueError):l.ingest(row)
            self.assertEqual(dict(c),{});self.assertTrue(l.receipt()['validation_failure_latched'])
    def test_negative_or_nonfinite_clock_and_unknown_stage_rejected(self):
        rows,_,e=invented_stream()
        for k,v in [('monotonic_milliseconds',-1),('monotonic_milliseconds',float('nan')),
                    ('monotonic_milliseconds',float('inf')),('monotonic_milliseconds',True),('event','UNEXPECTED')]:
            l=NativeSnapshotLedger(Counter(),e);r=copy.deepcopy(rows[0]);r[k]=v
            with self.assertRaises(ValueError):l.ingest(r)
    def test_counter_decrease_rejected(self):
        rows,_,e=invented_stream();l=NativeSnapshotLedger(Counter(),e);l.ingest(rows[0]);l.ingest(rows[1]);r=copy.deepcopy(rows[0]);r['monotonic_milliseconds']=3
        with self.assertRaisesRegex(ValueError,'NATIVE_SNAPSHOT_NONDECREASING'):l.ingest(r)
    def test_parent_addition_drift_is_detected_not_overwritten(self):
        rows,_,e=invented_stream();c=Counter();l=NativeSnapshotLedger(c,e);l.ingest(rows[0]);c['native_binary_loads_attempted']+=1
        with self.assertRaisesRegex(ValueError,'NATIVE_PARENT_COUNTER_DRIFT'):l.ingest(rows[1])
        self.assertEqual(c['native_binary_loads_attempted'],2)
    def test_terminal_without_full_event_evidence_rejected(self):
        _,v,e=invented_stream();r={'event':'COMPLETE','monotonic_milliseconds':1,'counters':dict(e)};l=NativeSnapshotLedger(Counter(),e)
        with tempfile.TemporaryDirectory()as d:
            capture(l,Path(d),[r])
            with self.assertRaisesRegex(ValueError,'NATIVE_TERMINAL_EVENT_COUNTS_EXACT'):l.finalize(v)
    def test_bad_terminal_receipt_cannot_be_replaced_after_failure(self):
        rows,v,e=invented_stream();l=NativeSnapshotLedger(Counter(),e)
        with tempfile.TemporaryDirectory()as d:capture(l,Path(d),rows)
        bad=copy.deepcopy(v);bad['native_queries_completed']=11
        with self.assertRaises(ValueError):l.finalize(bad)
        with self.assertRaisesRegex(ValueError,'NATIVE_ACCOUNTING_FAILURE_LATCHED'):l.finalize(v)
        self.assertTrue(l.receipt()['inflight_native_call_outcome_uncertain'])
    def test_invalid_event_after_qualification_latches_uncertainty(self):
        rows,v,e=invented_stream();l=NativeSnapshotLedger(Counter(),e)
        with tempfile.TemporaryDirectory()as d:capture(l,Path(d),rows)
        l.finalize(v);r=copy.deepcopy(rows[-1]);r['event']='FAILED';r['monotonic_milliseconds']+=1
        with self.assertRaises(ValueError):l.ingest(r)
        self.assertFalse(l.receipt()['qualified']);self.assertTrue(l.receipt()['inflight_native_call_outcome_uncertain'])
    def test_duplicate_json_key_rejected(self):
        _,_,e=invented_stream();l=NativeSnapshotLedger(Counter(),e)
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'duplicate';p.write_text('{"event":"COMPLETE","event":"FAILED"}\n')
            with self.assertRaisesRegex(ValueError,'NATIVE_PROGRESS_DUPLICATE_JSON_KEY'):l.capture(p)
    def test_capture_file_symlink_and_byte_cap_rejected(self):
        _,_,e=invented_stream()
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'large';p.write_bytes(b'x'*(MAX_BYTES+1));l=NativeSnapshotLedger(Counter(),e)
            with self.assertRaisesRegex(ValueError,'NATIVE_PROGRESS_CAPTURE_BYTE_CAP'):l.capture(p)
            s=Path(d)/'link';s.symlink_to(p);l=NativeSnapshotLedger(Counter(),e)
            with self.assertRaisesRegex(ValueError,'NATIVE_PROGRESS_CAPTURE_REQUIRED'):l.capture(s)
    def test_changed_source_signature_rejected_after_bounded_read(self):
        rows,_,e=invented_stream();l=NativeSnapshotLedger(Counter(),e)
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'changed';p.write_text(json.dumps(rows[0])+'\n');before=p.stat()
            after=SimpleNamespace(**{k:getattr(before,k)for k in ['st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns']})
            after.st_mtime_ns+=1
            with mock.patch.object(native_accounting.os,'fstat',side_effect=[before,after]):
                with self.assertRaisesRegex(ValueError,'NATIVE_PROGRESS_CAPTURE_STABLE_SOURCE'):l.capture(p)
        self.assertTrue(l.receipt()['validation_failure_latched']);self.assertIsNone(l.latest)
    def test_post_read_byte_cap_catches_growth_after_initial_stat(self):
        _,_,e=invented_stream();l=NativeSnapshotLedger(Counter(),e)
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'grown';p.write_bytes(b'x'*(MAX_BYTES+1));actual=p.stat()
            before=SimpleNamespace(**{k:getattr(actual,k)for k in ['st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns']});before.st_size=1
            with mock.patch.object(native_accounting.os,'fstat',side_effect=[before,actual]):
                with self.assertRaisesRegex(ValueError,'NATIVE_PROGRESS_CAPTURE_BYTE_CAP'):l.capture(p)
        self.assertEqual(l.receipt()['capture_ref']['bytes'],MAX_BYTES+1);self.assertTrue(l.validation_failed)
    def test_frozen_geometry_and_caps_cannot_be_relaxed(self):
        p,b=geometry()
        for k,v in [('native_indexes',5),('native_queries',13),('engineering_total_fragment_cap',257)]:
            bad=copy.deepcopy(p);bad['operation_caps'][k]=v
            with self.assertRaises(ValueError):expected_totals(bad,b)
        b['documents'][0]['vectors']['shape'][0]=True
        with self.assertRaises(ValueError):expected_totals(p,b)


class MockedTransportTests(unittest.TestCase):
    def exercise(self,mode,factory=Counter):
        p,b=geometry();rows,value,expected=invented_stream();p.update(node={'path':'/inert/node'},native_binary={'path':'/inert/native'},_sha256='e'*64)
        c=factory();state={}
        with tempfile.TemporaryDirectory()as d:
            root=Path(d)
            class Child:
                pid=987654;returncode=2 if mode=='partial'else 0
                def poll(self):return self.returncode
                def communicate(self,timeout):
                    if mode!='missing':
                        use=rows[:1]if mode=='partial'else rows
                        (root/'native-progress.jsonl').write_text(''.join(json.dumps(x)+'\n'for x in use))
                    if mode in ('success','bad_receipt'):
                        v={**value,'schema_version':1,'epoch':56,'kind':support.KIND,'phase':'engineering',
                           'helper_pid':self.pid,'bundle_sha256':hashlib.sha256((root/'native-bundle.json').read_bytes()).hexdigest(),
                           'helper_source_sha256':hashlib.sha256((HERE/'native_helper.cjs').read_bytes()).hexdigest(),'plan_sha256':p['_sha256']}
                        if mode=='bad_receipt':v['native_queries_completed']=11
                        (root/'native-result.json').write_text(json.dumps(v))
                    return b'',b''
            identity={'pid':987654,'startticks':1,'state':'R','pgid':support.os.getpgrp(),'sid':support.os.getsid(0)}
            with mock.patch.object(support,'verify_file',return_value=Path('/inert/verified')),mock.patch.object(support.subprocess,'Popen',return_value=Child())as popen,mock.patch.object(support,'proc',return_value=identity):
                if mode=='success':support.run_native(p,b,root,c,lambda stage:None,lambda:10,state)
                else:
                    with self.assertRaises(ValueError):support.run_native(p,b,root,c,lambda stage:None,lambda:10,state)
                self.assertEqual(popen.call_count,1)
            closure=json.loads((root/'native-process-closure.json').read_text());self.assertTrue(closure['child_closed'])
        return c,state,expected
    def test_success_counter_and_dict_use_actual_snapshot_once(self):
        for factory in [dict,Counter]:
            c,s,e=self.exercise('success',factory);self.assertEqual({k:c[k]for k in KEYS},e)
            self.assertTrue(s['native_counter_accounting']['qualified']);self.assertFalse(s['inflight_native_call_outcome_uncertain'])
            self.assertEqual(c['native_corpus_batches_completed'],1)
    def test_missing_capture_is_not_expected_filled(self):
        c,s,e=self.exercise('missing');self.assertFalse(s['native_counter_accounting']['qualified']);self.assertTrue(s['inflight_native_call_outcome_uncertain'])
        self.assertFalse(any(k in c for k in KEYS));self.assertNotIn('native_corpus_batches_completed',c)
    def test_partial_native_failure_retains_pending_attempt(self):
        c,s,e=self.exercise('partial');self.assertEqual(c['native_binary_loads_attempted'],1);self.assertEqual(c['native_binary_loads_completed'],0)
        self.assertTrue(s['inflight_native_call_outcome_uncertain']);self.assertFalse(s['native_counter_accounting']['qualified'])
    def test_mismatched_terminal_rejects_even_when_progress_complete(self):
        c,s,e=self.exercise('bad_receipt');self.assertEqual(c['native_queries_completed'],12)
        self.assertTrue(s['inflight_native_call_outcome_uncertain']);self.assertFalse(s['native_counter_accounting']['qualified'])
        self.assertNotIn('native_corpus_batches_completed',c)


if __name__=='__main__':unittest.main(verbosity=2)
