"""Invented ACK/bridge fixtures only; no actual guard/controller/target call."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import copy,json,tempfile,unittest
from unittest.mock import Mock
import publication_common as c
from ack_protocol import acknowledged_sha,persist_validated_response
from source_bridge import validate_structure,PARENT
class FinalACK(unittest.TestCase):
 def test_bare_success_never_invents_sha(self):
  request={'branch_name':c.BRANCH,'force':False,'sha':'a'*40};self.assertIsNone(acknowledged_sha('mcp__codex_apps__github_update_ref',{'success':True},request))
  for kind in('create_blob','create_tree','create_commit'):
   with self.assertRaises(ValueError):acknowledged_sha('mcp__codex_apps__github_'+kind,{'success':True},{})
  for bad in({'success':1},{'success':False},{'success':True,'sha':'a'*40}):
   with self.assertRaises(ValueError):acknowledged_sha('mcp__codex_apps__github_update_ref',bad,request)
 def test_original_payload_preserved_and_scoped(self):
  with tempfile.TemporaryDirectory()as d:
   raw=b'{"ok":true,"result":{"success":true}}';record=Mock();req={'branch_name':c.BRANCH,'force':False,'sha':'b'*40};p=Path(d)/'reply.json';result=persist_validated_response(p,raw,'mcp__codex_apps__github_update_ref',req,c.write,record);self.assertEqual(p.read_bytes(),raw);self.assertTrue(c.same(result,json.loads(raw)));record.assert_called_once_with(json.loads(raw))
   with self.assertRaises(ValueError):acknowledged_sha('mcp__codex_apps__github_update_ref',{'success':True},{**req,'branch_name':'main'})
 def test_controller_get_is_after_ref_and_before_return(self):
  s=(Path(__file__).parent/'controller_final_v1.js').read_text();ref=s.index("await mutate(prefix+'-ref'");get=s.index("if((await get(url+'/git/ref/heads/'+branch)).object.sha!==commit.sha)",ref);returned=s.index('return {epoch:43',get);self.assertLess(ref,get);self.assertLess(get,returned)
 def test_source_bridge_never_repairs_original_intent(self):
  proof={k:True for k in('checks_passed','verified_actual_remote_readback','desired_reference_state_verified','source_desired_state_verified','raw_non_identifying_success_retained','bridge_to_first_distinct_FINAL_parent_allowed_in_principle')};proof.update({k:False for k in('repeat_original_SOURCE_ref_request_authorized','write_or_repair_original_SOURCE_journal_authorized','source_durable_identifying_ref_ACK_present','source_controller_publication_receipt_present','bridge_is_actual_mutation_authorization')});proof.update(commit=PARENT,source_commit=PARENT,parent='fadb176e645b8ba5ba87a6caf088444bac650e67',original_ref_invocation_execution='NON_IDENTIFYING_SUCCESS_REPORTED_DESIRED_STATE_KNOWN',source_journal_rows=311,source_journal_successful_ACK_pairs=155,source_unclosed_intent_id='e43-source-g6-ref');rows=[]
  for i in range(155):
   name='e43-source-g6-commit'if i==154 else f'e43-source-g6-object-{i}';base={'id':name,'kind':'invented','generation':6,'owner':133450,'publication_phase':'source'};rows.extend([{**base,'phase':'intent'},{**base,'phase':'response','payload':{'ok':True,'result':{'sha':PARENT if i==154 else 'a'*40}}}])
  rows.append({'id':'e43-source-g6-ref','phase':'intent','kind':'mcp__codex_apps__github_update_ref','generation':6,'owner':133450,'publication_phase':'source'});req={'repository_full_name':c.REPO,'branch_name':c.BRANCH,'expected_sha':proof['parent'],'force':False,'sha':PARENT};raw={'ok':True,'result':{'success':True}};result=validate_structure(proof,rows,req,raw);self.assertFalse(result['source_identifying_ACK_fabricated']);self.assertEqual(len(rows),311)
  with self.assertRaises(ValueError):validate_structure({**proof,'write_or_repair_original_SOURCE_journal_authorized':True},rows,req,raw)
if __name__=='__main__':unittest.main()
