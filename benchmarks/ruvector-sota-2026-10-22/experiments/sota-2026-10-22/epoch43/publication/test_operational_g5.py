"""New metadata-only operational fixtures. No guard, controller, model or data modes."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import copy,json,tempfile,unittest
from unittest.mock import patch,Mock
import publication_common as c
from ack_protocol import persist_validated_response
from build_phase_stage import check_source_reservation
class Operational(unittest.TestCase):
 def test_no_default_operational_fallback(self):
  with patch.object(c,'OPERATIONAL_SHA',None):
   with self.assertRaises(ValueError):c.require_operational()
 def test_current_release_path_ignores_old_marker(self):
  with patch.multiple(c,OPERATIONAL_SHA='a'*64,OWNER_GENERATION=5,OWNER_REF={'path':str(c.W/'lease-generation5/owner.json')}):self.assertEqual(c.owner_release_path(),c.W/'lease-generation5/release.request');self.assertNotEqual(c.owner_release_path(),c.W/'release.request')
 def test_invalid_ACK_retained_without_journal_ACK(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'returned-response.json';raw=b'{"ok":true,"result":{"sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}';record=Mock();req={'branch_name':c.BRANCH,'force':False,'sha':'a'*40}
   with self.assertRaises(ValueError):persist_validated_response(p,raw,'mcp__codex_apps__github_update_ref',req,c.write,record)
   self.assertEqual(p.read_bytes(),raw);record.assert_not_called()
 def test_valid_ACK_retained_and_recorded_once(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'returned-response.json';payload={'ok':True,'result':{'ref':'refs/heads/'+c.BRANCH,'object':{'sha':'b'*40}},'diagnostic':None};raw=c.encoded(payload);record=Mock();req={'branch_name':c.BRANCH,'force':False,'sha':'b'*40}
   persist_validated_response(p,raw,'mcp__codex_apps__github_update_ref',req,c.write,record);self.assertEqual(p.read_bytes(),raw);record.assert_called_once_with(payload)
   with self.assertRaises(FileExistsError):persist_validated_response(p,raw,'mcp__codex_apps__github_update_ref',req,c.write,record)
   record.assert_called_once_with(payload)
 def test_current5_reservation_not_retired4(self):
  with patch.multiple(c,OWNER_SHA='e'*64,OWNER_GENERATION=5,OWNER_PID=12345,OWNER_TICKS=67890):
   r={'epoch':43,'generation':5,'pid':12345,'startticks':67890,'reserved_worker_slots':1,'owner_sha256':'e'*64,'reservation_token':'f'*64,'permanently_burned_at_SOURCE_publication':True,'execution_counts_from_actual_receipts_only':True,'currentepoch_new_invocations_after_owner_loss_forbidden':True,'missing_receipt_after_owner_loss':'UNKNOWN_PERMANENTLY_NO_RERUN'};a={'worker_slot_reservation':r,'currentepoch_new_invocations_after_owner_loss_forbidden':True,'missing_receipt_after_owner_loss':'UNKNOWN_PERMANENTLY_NO_RERUN'};p={'epoch43_frozen_study':{'worker_slot_reservation':copy.deepcopy(r)}};plan={'worker_slot_reservation':copy.deepcopy(r)};check_source_reservation(a,p,plan)
   for q in(r,p['epoch43_frozen_study']['worker_slot_reservation'],plan['worker_slot_reservation']):q['generation']=4
   with self.assertRaises(ValueError):check_source_reservation(a,p,plan)
if __name__=='__main__':unittest.main()
