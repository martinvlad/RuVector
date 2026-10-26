"""Invented metadata only; no owner, API, publication mode or dataset functions."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import json,tempfile,unittest,copy
from unittest.mock import patch
import publication_common as c
import freeze_and_results as f
import mutation_guard as g
import ack_protocol as ack
import archive_protocol as archive

class References(unittest.TestCase):
 def test_canonical_inherited_row(self):
  r={'path':'old/source.py','bytes':1,'sha256':'a'*64,'actual_git_blob_sha1':'b'*40};row,git=f.canonical_reference(r);self.assertEqual(set(row),{'path','bytes','sha256'});self.assertEqual(git,'b'*40);self.assertIn('actual_git_blob_sha1',r)
 def test_bool_bytes_rejected(self):
  with self.assertRaises(ValueError):f.canonical_reference({'path':'x.py','bytes':True,'sha256':'a'*64})
 def test_extra_field_rejected(self):
  with self.assertRaises(ValueError):f.canonical_reference({'path':'x.py','bytes':1,'sha256':'a'*64,'other':0})
 def test_git_identity_checked_separately(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);(p/'x.py').write_bytes(b'x');r={'path':'x.py','bytes':1,'sha256':c.sha(b'x'),'actual_git_blob_sha1':c.git(b'x')};rows,provenance=f.canonical_freeze_references(p,[],[r]);self.assertEqual(set(rows[0]),{'path','bytes','sha256'});self.assertTrue(provenance[0]['payload_git_blob_identity_verified']);r['actual_git_blob_sha1']='0'*40
   with self.assertRaises(ValueError):f.canonical_freeze_references(p,[],[r])
 def fixture(self,p,extra=False):
  def put(name,value):
   b=c.encoded(value)if not isinstance(value,bytes)else value;(p/name).write_bytes(b);return {'path':name,'bytes':len(b),'sha256':c.sha(b)}
  source=put('source.py',b'fixture=1\n');source.update({'actual_git_blob_sha1':c.git(b'fixture=1\n')}if extra else {})
  validator=put('validator.py',b"def validate_native_plan_contract(plan):\n if 'case_ids_by_document'not in plan:raise ValueError('MISSING_RAW_MAP')\n return {'checks_passed':True,'documents':4,'cases':12,'case_ids_by_document':plan['case_ids_by_document'],'target_calls':0,'execution_authorized':False}\n")
  contract={'external_custody_evidence_paths':f.EXTERNAL,'public_absolute_evidence_paths':f.PUBLIC_ABSOLUTE,'allowed_statuses':['REJECTED_DEV_INTEGRITY'],'status_ledger_classification':{'REJECTED_DEV_INTEGRITY':'rejections'}}
  root=put('root.json',{'publication_contract':contract,'worker_slot_reservation':{'invented':True}})
  freeze=put('freeze.json',{'epoch':47,'source_checkpoint':c.BASE,'files':[source,validator]})
  plan=put('plan.json',{'schema_version':1,'epoch':47,'phase':'dev','source_freeze':freeze,'root_contract':root,'required_refs':{'source':{k:source[k]for k in('path','bytes','sha256')}},'worker_slot_reservation':{'invented':True},'publication_contract':contract,'native_plan_contract_source':validator,'case_ids_by_document':{'invented':['metadata-only']}})
  return {'plan':plan}
 def test_actual_output_preflight_no_writes(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);x=self.fixture(p);before={a.name:a.read_bytes()for a in p.iterdir()}
   with patch.object(c,'require_operational'):r=f.preflight(p,x)
   self.assertTrue(r['actual_source_freeze_reference_closure_verified']);self.assertEqual(r['private_or_selected_new_case_bodies_read'],0);self.assertEqual(before,{a.name:a.read_bytes()for a in p.iterdir()})
   self.assertTrue(r['actual_raw_native_plan_contract_verified']);self.assertFalse(r['raw_native_plan_contract_receipt']['execution_authorized']);self.assertEqual(r['raw_native_plan_contract_receipt']['target_calls'],0)
 def test_preflight_rejects_raw_plan_without_identity_map(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);x=self.fixture(p);plan=json.loads((p/'plan.json').read_text());plan.pop('case_ids_by_document');raw=c.encoded(plan);(p/'plan.json').write_bytes(raw);x['plan']={'path':'plan.json','bytes':len(raw),'sha256':c.sha(raw)}
   with patch.object(c,'require_operational'),self.assertRaisesRegex(ValueError,'MISSING_RAW_MAP'):f.preflight(p,x)
 def test_preflight_rejects_extra_freeze_key(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);x=self.fixture(p,True)
   with patch.object(c,'require_operational'),self.assertRaises(ValueError):f.preflight(p,x)
 def test_fragment_false_is_not_integer_zero(self):
  a={'plan_fields':{'x':False},'required_refs':{},'inherited_source_refs':[]};b=copy.deepcopy(a);b['plan_fields']['x']=0
  with self.assertRaises(ValueError):f.merge_fragments([a,b])

class Responses(unittest.TestCase):
 def request(self):return {'branch_name':c.BRANCH,'force':False,'sha':'a'*40}
 def test_bare_success_requires_fresh_ref(self):
  with self.assertRaises(ValueError):ack.acknowledged_sha('github_update_ref',{'success':True},self.request())
  self.assertIsNone(ack.acknowledged_sha('github_update_ref',{'success':True},self.request(),{'ref':'refs/heads/'+c.BRANCH,'object':{'sha':'a'*40}}))
 def test_integer_success_rejected(self):
  with self.assertRaises(ValueError):ack.acknowledged_sha('github_update_ref',{'success':1},self.request())
 def test_identifying_ref_matches_commit(self):self.assertEqual(ack.acknowledged_sha('github_update_ref',{'ref':'refs/heads/'+c.BRANCH,'object':{'sha':'a'*40}},self.request()),'a'*40)
 def test_blob_bare_success_rejected(self):
  with self.assertRaises(ValueError):ack.acknowledged_sha('github_create_blob',{'success':True},{})
 def test_bad_ack_raw_retained_before_no_journal(self):
  events=[]
  with self.assertRaises(ValueError):ack.persist_validated_response('invented',b'{"ok":true,"result":{"wrong":true}}','github_create_blob',{},lambda p,b:events.append(('raw',b)),lambda v:events.append(('ack',v)))
  self.assertEqual(events,[('raw',b'{"ok":true,"result":{"wrong":true}}')])
 def test_uncertainty_stops_next_call(self):
  with self.assertRaises(ValueError):g.clean([{'phase':'intent','id':'e47-source-g12-ref'}])
 def test_false_response_stops(self):
  with self.assertRaises(ValueError):g.clean([{'phase':'intent','id':'x'},{'phase':'response','id':'x','payload':{'ok':False}}])
 def test_fake_namespace_durability(self):
  with tempfile.TemporaryDirectory()as d:
   with patch.object(c,'W',Path(d)):g.append({'fixture':1});req=g.request_directory();self.assertTrue((Path(d)/'publication/mutation-journal.jsonl').is_file());self.assertEqual(req,Path(d)/'publication/requests')
 def test_permanent_object_deny(self):
  with self.assertRaises(ValueError):archive.deny_old_object('create_tree',{'tree_elements':[{'path':c.SCOPE+'x','sha':c.FORBIDDEN}]})
 def test_replay_types_and_nulls_preserved(self):
  replay={'status':'REJECTED_DEV_INTEGRITY','metrics':None,'evaluation_executed':False,'counts':{'attempted':None}};out=archive.preserve_replay(replay,{'scope':'metadata'});self.assertTrue(all(c.same(out[k],v)for k,v in replay.items()))
 def test_no_legacy_bridges_and_fresh_get_required(self):
  text=(Path(__file__).parent/'controller.js').read_text();self.assertIn('postCAS mismatch; STOP',text);self.assertIn("object.sha!==commit.sha",text);self.assertNotIn('reserve_reconciliation_sha256',text);self.assertNotIn('source_bridge',Path(g.__file__).read_text())
if __name__=='__main__':unittest.main()
