"""Disjoint tiny-file and fake-guard-failure fixtures; no real assets or driver."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch
import io
from contextlib import redirect_stdout
HERE=Path(__file__).resolve().parent

def load(name,path):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
G=load('e38_tiny_payload_guard_fixture',HERE/'runtime/model_assets_guard.py')
I=load('e38_pure_identity_fixture',HERE/'asset_identity.py')
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def put(p,x):p.write_text(json.dumps(x,sort_keys=True)+'\n')
class ActualValidatorTinyFixtures(unittest.TestCase):
 def fixture(self,root):
  d=root/'tiny-five-payload-fixture';d.mkdir();rows=[];source=[]
  for i,name in enumerate(['config.json','tokenizer_config.json','LICENSE','spm.model','pytorch_model.bin']):
   body=('Invented tiny payload fixture '+name+'\n').encode();(d/name).write_bytes(body);h=sha_bytes(body)
   row={'path':name,'bytes':len(body),'source_url':'https://example.invalid/tiny/'+name}
   if i<3:row.update(metadata_body_sha256=h,upstream_git_blob_sha1=I.git_blob_sha1(body))
   else:
    pointer=f'version https://git-lfs.github.com/spec/v1\noid sha256:{h}\nsize {len(body)}\n'.encode()
    row.update(upstream_sha256=h,upstream_git_blob_sha1=I.git_blob_sha1(pointer))
   source.append(row);rows.append({k:v for k,v in row.items()if k not in('metadata_body_sha256','upstream_sha256')}|{'sha256':h})
  e=root/'tiny-expected.json';l=root/'tiny-observed.json';base={'repository':'microsoft/deberta-v2-xxlarge-mnli','revision':'8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06'}
  put(e,{**base,'files':source});put(l,{**base,'epoch':38,'kind':'PURE_TINY_FIXTURE','model_directory':str(d),'files':rows});(d/'asset-lock.json').write_bytes(l.read_bytes())
  return d,l,e
 def run_guard(self,d,l,e):
  return G.validate_model_assets(d,l,e,root=Path('/'),public_lock_sha256=G.sha(l),expected_catalog_sha256=G.sha(e),
   epoch=38,kind='PURE_TINY_FIXTURE',source_checkpoint='PURE_FIXTURE_NOT_A_RUNTIME_ADMISSION')
 def test_five_actual_tiny_file_scans_and_both_git_types(self):
  with tempfile.TemporaryDirectory(prefix='e38-tiny-fixture-')as name:
   d,l,e=self.fixture(Path(name));r=self.run_guard(d,l,e)
   self.assertEqual(r['actual_payload_files_verified'],5);self.assertEqual(r['ordinary_Git_payloads_verified'],3);self.assertEqual(r['canonical_LFS_pointers_verified'],2)
   self.assertEqual(r['actual_payload_bytes_hashed'],sum(x['actual_payload_bytes_hashed']for x in r['files']))
   self.assertTrue(all(x['actual_full_payload_scan']for x in r['files']))
   self.assertTrue(all(x['actual_ordinary_payload_git_blob_sha1']is None for x in r['files'][3:]))
 def test_direct_lock_mismatch_rejected(self):
  with tempfile.TemporaryDirectory(prefix='e38-tiny-fixture-')as name:
   d,l,e=self.fixture(Path(name));(d/'asset-lock.json').write_text('{}')
   with self.assertRaises(ValueError):self.run_guard(d,l,e)
 def test_payload_corruption_rejected(self):
  with tempfile.TemporaryDirectory(prefix='e38-tiny-fixture-')as name:
   d,l,e=self.fixture(Path(name));(d/'spm.model').write_bytes(b'corrupted invented toy payload')
   with self.assertRaises(ValueError):self.run_guard(d,l,e)
 def test_observed_lock_cannot_replace_source_authority(self):
  with tempfile.TemporaryDirectory(prefix='e38-tiny-fixture-')as name:
   d,l,e=self.fixture(Path(name));e.write_bytes(l.read_bytes())
   with self.assertRaises(ValueError):self.run_guard(d,l,e)
 def test_extra_file_and_symlink_refused(self):
  with tempfile.TemporaryDirectory(prefix='e38-tiny-fixture-')as name:
   d,l,e=self.fixture(Path(name));(d/'unexpected').write_text('invented')
   with self.assertRaises(ValueError):self.run_guard(d,l,e)
   (d/'unexpected').unlink();q=d/'LICENSE';body=q.read_bytes();q.unlink();p=Path(name)/'outside-fixture';p.write_bytes(body);q.symlink_to(p)
   with self.assertRaises(ValueError):self.run_guard(d,l,e)
class DurablePreworkerCaptureFixture(unittest.TestCase):
 def test_real_launcher_control_flow_captures_mock_guard_failure_without_popen(self):
  # The actual launcher main is exercised with invented paths and mocked kernel/
  # source guards. This is NOT the root driver or an actual model/asset check.
  L=load('e38_fake_guard_failure_launcher',HERE/'runtime/launch.py');C=L.C
  with tempfile.TemporaryDirectory(prefix='e38-capture-fixture-')as name:
   root=Path(name);study=root/'study';study.mkdir();scope=root/'scope';scope.mkdir();candidate=root/'candidate';candidate.mkdir()
   plan={'expected_operation_counters':{'engineering':{}},'source_freeze_sha256':'PURE_FIXTURE'};planfile=study/'plan.json';put(planfile,plan);digest=C.sha(planfile)
   admission=study/'SOURCE_ADMISSION.json';put(admission,{'fixture':True})
   for file in ['DISPATCH_RESERVATION.json','DISPATCH_ATTEMPT.json']:put(study/file,{'fixture':True})
   C.ROOT=root;C.STUDY=study;C.SCOPE=scope;C.CANDIDATE=candidate
   C.owner_lock=lambda *a,**k:{};C.dispatch_proof=lambda *a,**k:({'dispatch_monotonic_seconds':time.monotonic(),'dispatch_unix_seconds':time.time()}, {})
   C.admission=lambda *a,**k:({},{});C.verify_plan=lambda *a,**k:plan
   calls=[]
   def failed_guard(*a,**k):calls.append('GUARD_CALLED');raise ValueError('Invented disjoint guard failure before worker Popen')
   C.verify_runtime=failed_guard
   fake_supervisor={'pid':424242,'startticks':55,'pgid':424242,'sid':424242}
   args=['launch.py','--plan',str(planfile),'--admission',str(admission),'--scope',str(scope),'--expected-plan-sha',digest,'--phase','engineering']
   with patch.object(L.sys,'argv',args),patch.object(L.os,'sched_setaffinity'),patch.object(L.os,'sched_getaffinity',return_value={0,1}),\
     patch.object(L.signal,'signal'),patch.object(L.signal,'setitimer'),patch.object(L,'supervisor_identity',return_value=fake_supervisor),\
     patch.object(L.subprocess,'Popen',side_effect=AssertionError('No real or fake Popen allowed'))as popen,redirect_stdout(io.StringIO()):
    code=L.main()
   self.assertEqual(code,2);self.assertEqual(calls,['GUARD_CALLED']);popen.assert_not_called()
   execution=json.loads((study/'runs/engineering/execution.json').read_text());completion=json.loads((study/'SUPERVISOR_COMPLETION.json').read_text())
   self.assertTrue((study/'ENGINEERING_ATTEMPT_RESERVATION.json').is_file())
   self.assertEqual(execution['worker_start_boundary'],'KNOWN_FAILURE_BEFORE_WORKER_POPEN');self.assertFalse(execution['worker_popen_attempted'])
   self.assertEqual(execution['worker_popen_attempts'],0);self.assertFalse(execution['uncertain_start']);self.assertIsNone(execution['worker_identity'])
   self.assertTrue(execution['owned_live_processes_closed']);self.assertEqual(execution['raw_operation_counters_source'],'UNKNOWN')
   self.assertIsNone(execution['raw_operation_counters']);self.assertFalse(execution['operation_counts_complete']);self.assertIsNone(execution['paid_calls'])
   self.assertEqual(completion['execution_sha256'],C.sha(study/'runs/engineering/execution.json'))
   self.assertEqual(completion['intended_exit_code'],2);self.assertFalse((study/'runs/engineering/raw.json').exists())
   observer=load('e38_fake_capture_observer',HERE.parents[1]/'audit/epoch38/observe_supervisor_closure.py')
   self.assertTrue(observer.known_before_popen(execution,True,[]));self.assertFalse(observer.known_before_popen(execution,False,[]))
if __name__=='__main__':unittest.main()
