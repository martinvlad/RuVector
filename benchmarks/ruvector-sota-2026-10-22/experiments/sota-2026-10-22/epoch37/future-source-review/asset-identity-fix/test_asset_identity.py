"""Small independent fixtures plus real pinned metadata; no actual model files/guard calls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('future_source_payload_identity',HERE/'asset_identity.py');A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
EXPECTED=json.loads((HERE/'MODEL_ASSETS.expected.json').read_text())['files']
OBSERVED=json.loads((HERE/'E37_OBSERVED_MODEL_ASSETS.json').read_text())['files']
BY_EXPECTED={r['path']:r for r in EXPECTED};BY_OBSERVED={r['path']:r for r in OBSERVED}
RAW=b'Pure ordinary source metadata fixture.\n'
PAYLOAD=b'Pure small LFS payload fixture; never pretrained model bytes.\n'
def digest(b):return hashlib.sha256(b).hexdigest()
def raw_row():return {'path':'fixture.json','bytes':len(RAW),'source_url':'https://example.invalid/fixed/fixture.json',
 'upstream_git_blob_sha1':A.git_blob_sha1(RAW),'metadata_body_sha256':digest(RAW)}
def lfs_row():
 sha=digest(PAYLOAD);pointer=f'version https://git-lfs.github.com/spec/v1\noid sha256:{sha}\nsize {len(PAYLOAD)}\n'.encode()
 return {'path':'fixture.bin','bytes':len(PAYLOAD),'source_url':'https://example.invalid/fixed/fixture.bin',
  'upstream_git_blob_sha1':A.git_blob_sha1(pointer),'upstream_sha256':sha}
def observed(row):return {k:v for k,v in row.items()if k not in('metadata_body_sha256','upstream_sha256')}|{'sha256':row.get('upstream_sha256',row.get('metadata_body_sha256'))}
class TypedIdentityFixtures(unittest.TestCase):
 def test_raw_git_exact_both_hashes(self):
  r=A.verify_payload_observation(raw_row(),len(RAW),digest(RAW),A.git_blob_sha1(RAW))
  self.assertEqual(r['representation'],A.RAW_GIT);self.assertTrue(r['raw_payload_git_sha1_verified'])
 def test_raw_git_wrong_digest_rejected(self):
  with self.assertRaises(ValueError):A.verify_payload_observation(raw_row(),len(RAW),'0'*64,A.git_blob_sha1(RAW))
 def test_raw_git_wrong_git_body_rejected(self):
  with self.assertRaises(ValueError):A.verify_payload_observation(raw_row(),len(RAW),digest(RAW),'0'*40)
 def test_raw_git_missing_git_body_rejected(self):
  with self.assertRaises(ValueError):A.verify_payload_observation(raw_row(),len(RAW),digest(RAW))
 def test_lfs_pointer_and_payload_distinct_hashes_accepted(self):
  r=lfs_row();self.assertNotEqual(A.git_blob_sha1(PAYLOAD),r['upstream_git_blob_sha1'])
  result=A.verify_payload_observation(r,len(PAYLOAD),digest(PAYLOAD),A.git_blob_sha1(PAYLOAD))
  self.assertEqual(result['representation'],A.LFS);self.assertFalse(result['raw_payload_git_sha1_verified'])
  self.assertFalse(result['LFS_pointer_SHA1_compared_to_payload_SHA1'])
 def test_lfs_actual_payload_git_hash_not_required(self):
  self.assertTrue(A.verify_payload_observation(lfs_row(),len(PAYLOAD),digest(PAYLOAD))['payload_size_and_SHA256_verified'])
 def test_lfs_corrupt_payload_rejected(self):
  with self.assertRaises(ValueError):A.verify_payload_observation(lfs_row(),len(PAYLOAD),'f'*64)
 def test_lfs_wrong_size_rejected(self):
  with self.assertRaises(ValueError):A.verify_payload_observation(lfs_row(),len(PAYLOAD)+1,digest(PAYLOAD))
 def test_lfs_wrong_upstream_pointer_identity_rejected(self):
  r=lfs_row();r['upstream_git_blob_sha1']='0'*40
  with self.assertRaises(ValueError):A.expected_payload(r)
 def test_untyped_observed_materialization_cannot_alias_declaration(self):
  for r in [observed(raw_row()),observed(lfs_row()),*OBSERVED]:
   with self.assertRaises(ValueError):A.expected_payload(r)
 def test_ambiguous_or_missing_type_rejected(self):
  r=raw_row();r['upstream_sha256']=r['metadata_body_sha256']
  with self.assertRaises(ValueError):A.expected_payload(r)
  r.pop('upstream_sha256');r.pop('metadata_body_sha256')
  with self.assertRaises(ValueError):A.expected_payload(r)
 def test_sourceurl_or_pointer_binding_cannot_change(self):
  for key,value in [('source_url','https://example.invalid/different'),('upstream_git_blob_sha1','0'*40),('sha256','0'*64)]:
   r=observed(lfs_row());r[key]=value
   with self.assertRaises(ValueError):A.bind_observed_lock(lfs_row(),r)
 def test_duplicate_missing_extra_catalog_rejected(self):
  e=[raw_row(),lfs_row()];o=[observed(r)for r in e]
  for bad_e,bad_o in [(e+e[:1],o),(e,o+o[:1]),(e,o[:1]),(e[:1],o)]:
   with self.assertRaises(ValueError):A.bind_catalog(bad_e,bad_o)
 def test_all_five_actual_reviewed_metadata_bind_without_payload_reads(self):
  # Pure terminal policy only: inputs are exact pinned metadata, not model bytes.
  with patch('builtins.open',side_effect=AssertionError('No payload read permitted')):
   result=A.bind_catalog(EXPECTED,OBSERVED)
   self.assertEqual([r['representation']for r in result],[A.RAW_GIT]*3+[A.LFS]*2)
 def test_both_real_lfs_pointer_git_objects_exact(self):
  identities={r['path']:r for r in A.bind_catalog(EXPECTED,OBSERVED)}
  self.assertEqual(identities['spm.model']['upstream_lfs_pointer_bytes'],132)
  self.assertEqual(identities['spm.model']['upstream_lfs_pointer_git_sha1'],'c146a1df1f80d26596bbb4d0fadc43bca9a8145c')
  self.assertEqual(identities['pytorch_model.bin']['upstream_lfs_pointer_bytes'],135)
  self.assertEqual(identities['pytorch_model.bin']['upstream_lfs_pointer_git_sha1'],'aba315cb1d255ada5671f0de52bcbc5148771376')
 def test_actual_spm_terminal_regression_from_independent_observation(self):
  # Independent actual SPM hash observation, retained in d7e2277... report.
  payload_git='1f77a5ca5173931f43d45117ed425a317e6cf553'
  e=BY_EXPECTED['spm.model'];o=BY_OBSERVED['spm.model']
  legacy_bad_selector=not o.get('upstream_sha256')and bool(o.get('upstream_git_blob_sha1'))
  self.assertTrue(legacy_bad_selector);self.assertNotEqual(payload_git,o['upstream_git_blob_sha1'])
  result=A.verify_payload_observation(e,o['bytes'],o['sha256'],payload_git)
  self.assertFalse(result['LFS_pointer_SHA1_compared_to_payload_SHA1'])
 def test_small_lfs_fixture_reproduces_e37_loss_then_fixed(self):
  e=lfs_row();o=observed(e)
  self.assertTrue(not o.get('upstream_sha256')and o.get('upstream_git_blob_sha1'))
  self.assertNotEqual(A.git_blob_sha1(PAYLOAD),o['upstream_git_blob_sha1'])
  self.assertTrue(A.bind_observed_lock(e,o)['representation']==A.LFS)
  with self.assertRaises(ValueError):A.bind_observed_lock(o,o)
 def test_no_io_or_ml_needed_for_complete_terminal_identity_reducer(self):
  with patch('builtins.open',side_effect=AssertionError('No IO allowed')):
   for e in EXPECTED:
    o=BY_OBSERVED[e['path']];identity=A.expected_payload(e)
    git=e['upstream_git_blob_sha1']if identity['raw_payload_git_blob_sha1_required']else None
    self.assertTrue(A.verify_payload_observation(e,o['bytes'],o['sha256'],git)['payload_size_and_SHA256_verified'])
  self.assertEqual([m for m in ['torch','transformers','onnxruntime','tokenizers','numpy']if m in sys.modules],[])

if __name__=='__main__':unittest.main()
