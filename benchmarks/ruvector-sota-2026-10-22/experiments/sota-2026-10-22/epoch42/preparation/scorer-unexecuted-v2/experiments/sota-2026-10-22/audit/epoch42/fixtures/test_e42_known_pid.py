"""Exact-known-PID read failures are never absence; no actual owned PID used."""
import os,unittest
from pathlib import Path
from unittest.mock import patch
import e42_qualification as Q
class KnownPID(unittest.TestCase):
 def proof(self):return {'physical_supervisor_closed':True,'physical_closure_passed':True,'unknown_physical_ownership':False,'owned_worker_group_members':[],'kernel_boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'pid_namespace_inode':os.stat('/proc/self/ns/pid').st_ino,'supervisor_identity':{'pid':999990,'startticks':91,'pgid':999990,'sid':999990}}
 def test_permission_denial_of_known_pid_stops_before_scan(self):
  proof=self.proof();old=Path.read_text
  def read(path,*a,**k):
   if str(path)=='/proc/999990/stat':raise PermissionError('UNRELATED_SYNTHETIC_EACCES')
   return old(path,*a,**k)
  with patch.object(Path,'read_text',read),patch.object(Path,'iterdir')as scan:
   with self.assertRaisesRegex(ValueError,'KNOWN_SUPERVISOR_PROC_UNREADABLE'):Q.current_physical_fence(proof)
   scan.assert_not_called()
 def test_malformed_known_pid_stops(self):
  proof=self.proof();old=Path.read_text
  def read(path,*a,**k):return 'malformed'if str(path)=='/proc/999990/stat'else old(path,*a,**k)
  with patch.object(Path,'read_text',read),patch.object(Path,'iterdir')as scan:
   with self.assertRaisesRegex(ValueError,'KNOWN_SUPERVISOR_PROC_UNREADABLE'):Q.current_physical_fence(proof)
   scan.assert_not_called()
 def test_only_filenotfound_can_be_absence_after_recorded_proof(self):
  proof=self.proof();old=Path.read_text
  def read(path,*a,**k):
   if str(path)=='/proc/999990/stat':raise FileNotFoundError('UNRELATED_VANISHED_PID')
   return old(path,*a,**k)
  with patch.object(Path,'read_text',read),patch.object(Path,'iterdir',return_value=[]):Q.current_physical_fence(proof)
if __name__=='__main__':unittest.main()
