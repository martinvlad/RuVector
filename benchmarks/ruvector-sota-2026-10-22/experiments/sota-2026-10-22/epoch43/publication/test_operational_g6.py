"""Three operational metadata fixtures only; no live guard or target mode."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import copy,os,tempfile,unittest
from unittest.mock import patch
import publication_common as c
import mutation_guard_source_g6 as g
from build_phase_stage import check_source_reservation
class G6(unittest.TestCase):
 def test_no_old_owner_default_and_current_release(self):
  with patch.object(c,'OPERATIONAL_SHA',None):
   with self.assertRaises(ValueError):c.require_operational()
  with patch.multiple(c,OPERATIONAL_SHA='a'*64,OWNER_GENERATION=6,OWNER_REF={'path':str(c.W/'lease-generation6/owner.json')}):
   self.assertEqual(c.owner_release_path(),c.W/'lease-generation6/release.request');self.assertNotEqual(c.owner_release_path(),c.W/'lease-generation5/release.request')
 def test_current_reservation_cannot_use_prior5(self):
  with patch.multiple(c,OWNER_SHA='a'*64,OWNER_GENERATION=6,OWNER_PID=1234,OWNER_TICKS=5678):
   r={'epoch':43,'generation':6,'pid':1234,'startticks':5678,'reserved_worker_slots':1,'owner_sha256':'a'*64,'reservation_token':'b'*64,'permanently_burned_at_SOURCE_publication':True,'execution_counts_from_actual_receipts_only':True,'currentepoch_new_invocations_after_owner_loss_forbidden':True,'missing_receipt_after_owner_loss':'UNKNOWN_PERMANENTLY_NO_RERUN'};active={'worker_slot_reservation':r,'currentepoch_new_invocations_after_owner_loss_forbidden':True,'missing_receipt_after_owner_loss':'UNKNOWN_PERMANENTLY_NO_RERUN'};p={'epoch43_frozen_study':{'worker_slot_reservation':copy.deepcopy(r)}};plan={'worker_slot_reservation':copy.deepcopy(r)};check_source_reservation(active,p,plan)
   for row in(r,p['epoch43_frozen_study']['worker_slot_reservation'],plan['worker_slot_reservation']):row['generation']=5
   with self.assertRaises(ValueError):check_source_reservation(active,p,plan)
 def test_current_nested_WAL_parent_is_fsynced(self):
  with tempfile.TemporaryDirectory()as d:
   w=Path(d);parent=w/'lease-generation6';parent.mkdir();seen=[];real=os.fsync
   def sync(fd):seen.append((Path('/proc/self/fd')/str(fd)).resolve());return real(fd)
   with patch.object(c,'W',w),patch.object(g.os,'fsync',side_effect=sync):g.append({'fixture':'intent'});g.request_directory()
   self.assertEqual(seen,[parent/'source-final-journal.jsonl',parent,parent]);self.assertNotIn(w,seen)
if __name__=='__main__':unittest.main()
