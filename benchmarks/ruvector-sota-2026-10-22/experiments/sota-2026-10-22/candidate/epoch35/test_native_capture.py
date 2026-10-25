"""AST-isolated failure-boundary fixtures: no process, model or addon starts."""
import ast
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest


SOURCE=Path(__file__).with_name('worker.py')
NAMES={'file_ref','node_events','run_native','native_capture_observation','write_raw_capture'}
tree=ast.parse(SOURCE.read_text())
isolated=ast.Module(body=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in NAMES],type_ignores=[])


def put(path,value):
    with path.open('x')as out:
        json.dump(value,out,allow_nan=False);out.write('\n');out.flush();os.fsync(out.fileno())


def checkpoint(raw,out):
    pending=out/'authored-fixture.partial.pending'
    put(pending,raw);os.replace(pending,out/'raw.partial.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class NativeCapture(unittest.TestCase):
    def fixture(self,base,popen):
        root=base/'project';out=root/'runs';out.mkdir(parents=True)
        here=root/'candidate';here.mkdir();(here/'native_helper.cjs').write_text('AUTHORED_METADATA_NOT_EXECUTABLE')
        C=SimpleNamespace(ROOT=root,VENV=base/'unused-venv',BINARY_SHA='b'*64,
            put=put,sha=sha,read=lambda p:json.loads(Path(p).read_text()),
            read_json_line=json.loads,remaining=lambda deadline:deadline-time.time(),
            proc=lambda pid:{'pid':pid,'ticks':1,'pgid':os.getpgrp(),'sid':os.getsid(0)})
        env={'C':C,'A':SimpleNamespace(KIND='ENGINEERING_QUANTITATIVE_SOURCE_SCOPE_STRESS'),
            'HERE':here,'os':os,'Path':Path,'tempfile':tempfile,'time':time,
            'subprocess':SimpleNamespace(Popen=popen,PIPE=subprocess.PIPE,TimeoutExpired=subprocess.TimeoutExpired),
            'checkpoint':checkpoint}
        exec(compile(isolated,str(SOURCE),'exec'),env)
        counters={key:0 for key in ('native_helper_starts_attempted','native_helper_starts_completed',
            'corpus_batches_attempted','corpus_batches_completed','native_queries_attempted','native_queries_completed',
            'Node_network_operations_attempted','native_binary_loads_attempted','native_binary_loads_completed')}
        corpus={'native_child_closed':None};raw={'status':'FAILED_ENGINEERING','counters':counters,
            'corpora':{'engineering':corpus},'corpus_reservations':{}}
        args=SimpleNamespace(out=out,deadline=time.time()+30,expected_plan_sha='a'*64)
        return env,raw,corpus,args

    def complete_fixture(self,base,with_guard):
        class Closed:
            pid=123456;returncode=0
            def poll(self):return 0
            def communicate(self,**kwargs):return b'',b''
        bundle={'documents':[{'document_id':str(-35001-i),'vectors':{'shape':[1,384]},
            'queries':[{'id':f'epoch35:cc0:numeric-scope:{i+1:02}::retrieval:{variant}'}
                for variant in ('original',)]} for i in range(12)]}
        def returned(command,**kwargs):
            source,target=Path(command[-2]),Path(command[-1])
            documents=[{'document_id':doc['document_id'],'initialized_vectors':1,
                'queries':[{'case_id':query['id'],'requested_k':1,'ids':[0],
                    'raw_hits':[{'AUTHORED_METADATA_ONLY':True}]} for query in doc['queries']]}
                for doc in bundle['documents']]
            result={'epoch':35,'kind':'ENGINEERING_QUANTITATIVE_SOURCE_SCOPE_STRESS',
                'phase':'engineering','role':'engineering','native':True,'helper_pid':Closed.pid,
                'source_sha256':sha(base/'project/candidate/native_helper.cjs'),
                'bundle_sha256':sha(source),'native_binary_sha256':'b'*64,
                'package_version':'0.1.33','platform_package_version':'0.1.31','binary_version':'2.3.0',
                'compact_schema':'epoch35-native-context-f32le-v1','errors':[],
                'stage':'HELPER_COMPLETED','documents':documents,
                'native_index_initializations_attempted':12,'native_index_initializations_completed':12,
                'native_queries_attempted':12,'native_queries_completed':12,
                'native_len_calls_attempted':24,'native_len_calls_completed':24,
                'native_version_calls_attempted':1,'native_version_calls_completed':1,
                'native_insertions_attempted':12,'native_insertions_completed':12,
                'native_hit_source_validations':12}
            put(target,result)
            if with_guard:
                row={'event':'NATIVE_BINARY_LOAD_AFTER','pid':Closed.pid,'phase':'engineering','role':'engineering',
                    'Node_network_operations_attempted':0,'native_binary_loads_attempted':1,
                    'native_binary_loads_completed':1}
                (target.parent/'engineering-node-progress.jsonl').write_text(json.dumps(row)+'\n')
            return Closed()
        env,raw,corpus,args=self.fixture(base,returned)
        return env,raw,corpus,args,bundle

    def test_lost_native_Popen_return_preserves_UNKNOWN_partial(self):
        calls=[]
        with tempfile.TemporaryDirectory()as temporary:
            base=Path(temporary)
            def interrupted(*args,**kwargs):
                calls.append(True)
                # A last progress observation can lag the unknown child. It
                # cannot establish complete totals even if it contains counts.
                progress=base/'project/runs/engineering-native-progress.jsonl'
                progress.write_text(json.dumps({'native_queries_attempted':12,'native_queries_completed':12})+'\n')
                raise InterruptedError('AUTHORED_UNRETURNED_POPEN_NO_PROCESS_STARTED')
            env,raw,corpus,args=self.fixture(base,interrupted)
            with self.assertRaises(InterruptedError):
                env['run_native']({'authored_fixture_only':True},corpus,raw,args,lambda e:None,'engineering')
            self.assertEqual(len(calls),1)
            self.assertTrue(corpus['native_helper_popen_attempted'])
            self.assertFalse(corpus['native_helper_returned_handle'])
            self.assertIsNone(corpus['native_child_closed'])
            self.assertEqual(raw['counters']['native_queries_completed'],12)
            self.assertEqual(env['write_raw_capture'](raw,args.out),'raw.partial.json')
            self.assertFalse((args.out/'raw.json').exists())
            observed=json.loads((args.out/'raw.partial.json').read_text())['native_backend_capture']
            self.assertFalse(observed['native_backend_counter_totals_complete'])
            self.assertEqual(observed['backend_execution_since_checkpoint'],'UNKNOWN')
            self.assertEqual(observed['captured_native_counter_values']['native_queries_completed'],12)

    def test_known_closed_helper_missing_result_is_still_UNKNOWN(self):
        class Closed:
            pid=123456;returncode=0
            def poll(self):return 0
            def communicate(self,**kwargs):return b'',b''
        with tempfile.TemporaryDirectory()as temporary:
            env,raw,corpus,args=self.fixture(Path(temporary),lambda *a,**k:Closed())
            with self.assertRaises(FileNotFoundError):
                env['run_native']({'authored_fixture_only':True},corpus,raw,args,lambda e:None,'engineering')
            self.assertTrue(corpus['native_helper_returned_handle'])
            self.assertTrue(corpus['native_child_closed'])
            self.assertFalse(corpus['native_counter_capture_complete'])
            self.assertEqual(env['write_raw_capture'](raw,args.out),'raw.partial.json')
            self.assertFalse((args.out/'raw.json').exists())
            self.assertEqual(raw['native_backend_capture']['backend_execution_since_checkpoint'],'UNKNOWN')

    def test_known_closed_helper_truncated_result_is_still_UNKNOWN(self):
        class Closed:
            pid=123456;returncode=0
            def poll(self):return 0
            def communicate(self,**kwargs):return b'',b''
        with tempfile.TemporaryDirectory()as temporary:
            base=Path(temporary)
            def returned(*a,**k):
                (base/'project/runs/engineering-native-result.json').write_text('{"native_queries_completed":')
                return Closed()
            env,raw,corpus,args=self.fixture(base,returned)
            with self.assertRaises(ValueError):
                env['run_native']({'authored_fixture_only':True},corpus,raw,args,lambda e:None,'engineering')
            self.assertTrue(corpus['native_child_closed'])
            self.assertFalse(corpus['native_counter_capture_complete'])
            self.assertEqual(env['write_raw_capture'](raw,args.out),'raw.partial.json')
            self.assertFalse((args.out/'raw.json').exists())

    def test_valid_helper_result_without_guard_counter_capture_is_UNKNOWN(self):
        with tempfile.TemporaryDirectory()as temporary:
            env,raw,corpus,args,bundle=self.complete_fixture(Path(temporary),False)
            with self.assertRaisesRegex(ValueError,'Node guard counters'):
                env['run_native'](bundle,corpus,raw,args,lambda e:None,'engineering')
            self.assertTrue(corpus['native_child_closed'])
            self.assertFalse(corpus['native_counter_capture_complete'])
            self.assertEqual(raw['counters']['native_queries_completed'],12)
            self.assertEqual(env['write_raw_capture'](raw,args.out),'raw.partial.json')
            self.assertFalse((args.out/'raw.json').exists())
            self.assertEqual(raw['native_backend_capture']['backend_execution_since_checkpoint'],'UNKNOWN')

    def test_closed_validated_helper_and_guard_receipts_allow_complete_capture(self):
        with tempfile.TemporaryDirectory()as temporary:
            env,raw,corpus,args,bundle=self.complete_fixture(Path(temporary),True)
            env['run_native'](bundle,corpus,raw,args,lambda e:None,'engineering')
            self.assertTrue(corpus['native_child_closed'])
            self.assertTrue(corpus['native_counter_capture_complete'])
            self.assertEqual(raw['counters']['native_binary_loads_completed'],1)
            self.assertEqual(raw['counters']['corpus_batches_completed'],1)
            self.assertEqual(env['write_raw_capture'](raw,args.out),'raw.json')
            self.assertTrue((args.out/'raw.json').exists())
            self.assertTrue(raw['native_backend_capture']['native_backend_counter_totals_complete'])

    def test_known_valid_native_capture_does_not_broaden_model_error_scope(self):
        with tempfile.TemporaryDirectory()as temporary:
            env,raw,corpus,args=self.fixture(Path(temporary),lambda *a,**k:None)
            raw['counters']['native_helper_starts_attempted']=1
            corpus.update(native_helper_popen_attempted=True,native_helper_returned_handle=True,
                native_child_closed=True,native_child_exit_code=0,native_counter_capture_complete=True,
                native_result={'path':'runs/valid-native-result.json','bytes':27,'sha256':'c'*64},
                validated_Node_guard_counter_receipt={'path':'runs/valid-node-guard.jsonl','bytes':31,'sha256':'d'*64})
            # The later neural API error stays a failure, but this scope fix
            # does not turn validated native operations into UNKNOWN.
            raw['errors']=[{'stage':'NLI','error':'AUTHORED_MODEL_API_ERROR'}]
            self.assertEqual(env['write_raw_capture'](raw,args.out),'raw.json')
            self.assertTrue((args.out/'raw.json').exists())
            self.assertTrue(raw['native_backend_capture']['native_backend_counter_totals_complete'])
            self.assertEqual(raw['status'],'FAILED_ENGINEERING')


if __name__=='__main__':
    unittest.main(verbosity=2)
