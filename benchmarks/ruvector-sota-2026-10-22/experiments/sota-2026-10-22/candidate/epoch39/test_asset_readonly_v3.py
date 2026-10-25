"""Invented tiny four-alias inodes only. No actual cache or real guard invocation."""
from pathlib import Path
import errno,importlib.util,os,tempfile,unittest
from unittest.mock import patch
H=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('tiny_mode_v3',H/'runtime/materialize_assets_v3.py');M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
class ModeFixtures(unittest.TestCase):
 def tiny(self,root):
  p=root/'a';p.write_bytes(b'Invented tiny mode-transition bytes; no tensors\n');p.chmod(0o600);aliases=[p]
  for n in ['b','c','d']:q=root/n;os.link(p,q);aliases.append(q)
  v=p.stat();identity={'device':v.st_dev,'inode':v.st_ino,'bytes':v.st_size,'mtime_ns':v.st_mtime_ns,'nlink_before':4,'all_known_aliases':[str(q)for q in aliases]}
  return p,v,identity
 def test_exact_four_alias_mode_transition_then_hardlink_no_userspace_copy(self):
  with tempfile.TemporaryDirectory(prefix='e39-invented-v3-')as d:
   p,b,i=self.tiny(Path(d));record={};M.transition_readonly(p,b,i,record);after=p.stat()
   self.assertEqual(after.st_mode&0o777,0o444);self.assertEqual((b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_nlink),(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_nlink));self.assertEqual(record['after_fd']['mode_octal'],'0444');self.assertFalse(record['rollback_attempted'])
   q=Path(d)/'target';os.link(p,q);self.assertEqual(q.stat().st_ino,p.stat().st_ino);self.assertEqual(p.stat().st_nlink,5)
 def test_partial_own_fchmod_exception_restores_only_same_fd_original_mode(self):
  with tempfile.TemporaryDirectory(prefix='e39-invented-v3-')as d:
   p,b,i=self.tiny(Path(d));record={};actual=os.fchmod;calls=[]
   def failure(fd,mode):
    calls.append(mode);actual(fd,mode)
    if len(calls)==1:raise OSError(errno.ENOSPC,'invented partial mode error')
   with patch.object(M.os,'fchmod',side_effect=failure):
    with self.assertRaises(OSError):M.transition_readonly(p,b,i,record)
   self.assertEqual(calls,[0o444,0o600]);self.assertEqual(p.stat().st_mode&0o777,0o600);self.assertEqual(record['after_fd']['mode_octal'],'0600');self.assertTrue(record['rollback_attempted']);self.assertEqual(record['exception_fd']['mode_octal'],'0444')
 def test_fchmod_failure_without_mode_change_preserves_state_and_never_rolls_back(self):
  with tempfile.TemporaryDirectory(prefix='e39-invented-v3-')as d:
   p,b,i=self.tiny(Path(d));record={}
   with patch.object(M.os,'fchmod',side_effect=OSError(errno.ENOSPC,'invented failure'))as x:
    with self.assertRaises(OSError):M.transition_readonly(p,b,i,record)
    self.assertEqual(x.call_count,1)
   self.assertEqual(record['after_path']['mode_octal'],'0600');self.assertFalse(record['rollback_attempted']);self.assertEqual(p.stat().st_ino,b.st_ino)
 def test_wrong_alias_refuses_before_fchmod(self):
  with tempfile.TemporaryDirectory(prefix='e39-invented-v3-')as d:
   p,b,i=self.tiny(Path(d));other=Path(d)/'wrong';other.write_bytes(b'other');i['all_known_aliases'][-1]=str(other);record={}
   with patch.object(M.os,'fchmod',side_effect=AssertionError('NO CHMOD'))as x:
    with self.assertRaises(ValueError):M.transition_readonly(p,b,i,record)
    x.assert_not_called()
   self.assertEqual(p.stat().st_mode&0o777,0o600);self.assertIn('after_fd',record)
 def test_target_device_failure_is_prospective_before_permission(self):
  with tempfile.TemporaryDirectory(prefix='e39-invented-v3-')as d:
   parent=Path(d);device=parent.stat().st_dev;M.same_filesystem_before_permission(parent,device)
   with self.assertRaisesRegex(ValueError,'STOP_BEFORE_SOURCE_CHMOD'):M.same_filesystem_before_permission(parent,device+1)
 def test_other_large_writable_payload_has_no_copy_or_chmod_fallback(self):
  from types import SimpleNamespace
  with self.assertRaisesRegex(ValueError,'WRITABLE_LARGE_SOURCE_STOP'):M.select_transfer('b354',{'path':'other.bin','bytes':870182606},SimpleNamespace(st_mode=0o100600,st_size=870182606),Path('/invented/a'),Path('/invented/z'),{})
if __name__=='__main__':unittest.main()
