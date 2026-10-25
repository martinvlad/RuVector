"""Disjoint invented bytes only: no real cache/model/plan/guard invocation."""
from pathlib import Path
import hashlib,importlib.util,os,tempfile,unittest
from types import SimpleNamespace
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('tiny_snapshot_v2',H/'runtime/materialize_assets_v2.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
class SnapshotFixtures(unittest.TestCase):
 def test_writable_tiny_model_new_physical_copy_preserves_source(self):
  with tempfile.TemporaryDirectory(prefix='e39-v2-invented-')as d:
   a=Path(d)/'source';a.mkdir();z=Path(d)/'target';z.mkdir();src=a/'model.safetensors';dst=z/'model.safetensors'
   raw=b'Invented non-model bytes for physical-copy policy only\n';src.write_bytes(raw);src.chmod(0o600);before=src.stat()
   M.copy_readonly(src,dst,before);after=src.stat()
   self.assertEqual(dst.read_bytes(),raw);self.assertEqual(hashlib.sha256(dst.read_bytes()).digest(),hashlib.sha256(raw).digest())
   self.assertEqual(dst.stat().st_mode&0o777,0o444);self.assertNotEqual(dst.stat().st_ino,src.stat().st_ino)
   self.assertEqual((before.st_size,before.st_mode,before.st_mtime_ns,before.st_nlink),(after.st_size,after.st_mode,after.st_mtime_ns,after.st_nlink))
 def allowed(self,mode):
  declaration={'path':'model.safetensors','bytes':870182606,'upstream_sha256':'c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'}
  a=Path('/invented-source/model.safetensors');z=Path('/invented-target/model.safetensors')
  allowance={'profile':'b354','path':declaration['path'],'source_path':str(a),'target_path':str(z),'bytes':declaration['bytes'],'sha256':declaration['upstream_sha256'],'force_new_physical_copy':True,'maximum_stream_chunk_bytes':1048576,'target_mode':'0444','source_mode_mtime_bytes_unchanged':True,'source_link_count_unchanged_for_copy':True,'all_other_writable_files_above_16MiB':'STOP_NO_FALLBACK'}
  return declaration,SimpleNamespace(st_mode=mode,st_size=870182606),a,z,allowance
 def test_exact_declared_weight_forces_copy_even_if_source_readonly(self):
  for mode in (0o100600,0o100444):
   d,i,a,z,x=self.allowed(mode);self.assertEqual(M.select_transfer('b354',d,i,a,z,x),'READONLY_PHYSICAL_WEIGHT_SNAPSHOT')
 def test_other_writable_large_stops(self):
  d,i,a,z,x=self.allowed(0o100600);d['path']='other.bin'
  with self.assertRaisesRegex(ValueError,'WRITABLE_LARGE_SOURCE_STOP'):M.select_transfer('b354',d,i,a,z,x)
 def test_wrong_copy_allowance_stops(self):
  d,i,a,z,x=self.allowed(0o100600);x['maximum_stream_chunk_bytes']=2097152
  with self.assertRaisesRegex(ValueError,'EXACT_FROZEN'):M.select_transfer('b354',d,i,a,z,x)
 def test_existing_target_not_overwritten(self):
  with tempfile.TemporaryDirectory(prefix='e39-v2-invented-')as d:
   a=Path(d)/'a';z=Path(d)/'z';a.write_bytes(b'new');z.write_bytes(b'old')
   with self.assertRaises(FileExistsError):M.copy_readonly(a,z,a.stat())
   self.assertEqual(z.read_bytes(),b'old')
if __name__=='__main__':unittest.main()
