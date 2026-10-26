"""Bounded publication-only guard fixtures. No API/owner/restore/model execution."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import base64,zipfile,unittest
import recovery_common as c

class RecoveryGuards(unittest.TestCase):
 def test_distinct_object_and_forensic_string_allowed(self):
  b=b'{"historical_unknown":"'+c.FORBIDDEN.encode()+b'"}'
  args={'repository_full_name':'ruvnet/RuVector','encoding':'utf-8','content':b.decode()};meta={'blobs':[{'GitSHA':c.git(b),'body_bytes':len(b),'body_sha256':c.sha(b)}]};c.validate_request('github_create_blob',args,meta)
 def test_forbidden_decoded_blob_and_inline_tree(self):
  with zipfile.ZipFile(c.ARCHIVE)as z:b=z.read('public-project/experiments/sota-2026-10-22/epoch42/REJECTION_LEDGER.json')
  self.assertEqual(c.git(b),c.FORBIDDEN)
  for encoding,content in [('utf-8',b.decode()),('base64',base64.b64encode(b).decode())]:
   with self.assertRaises(ValueError):c.validate_request('github_create_blob',{'repository_full_name':'ruvnet/RuVector','encoding':encoding,'content':content},{'blobs':[]})
  for value in ({'sha':c.FORBIDDEN},{'content':b.decode()}):
   with self.assertRaises(ValueError):c.validate_request('github_create_tree',{'repository_full_name':'ruvnet/RuVector','base_tree_sha':'a'*40,'tree_elements':[{'path':c.SCOPE+c.NEW+'fixture.json','mode':'100644','type':'blob',**value}]},{})
 def test_scope_and_sole_parent_and_CAS(self):
  for args in ({'parent_sha':c.PARENT,'additional_parent_shas':['a'*40]},{'parent_sha':'a'*40}):
   with self.assertRaises(ValueError):c.validate_request('github_create_commit',{'repository_full_name':'ruvnet/RuVector',**args},{})
  with self.assertRaises(ValueError):c.validate_request('github_update_ref',{'repository_full_name':'ruvnet/RuVector','branch_name':'main','expected_sha':c.PARENT,'force':False},{})
  with self.assertRaises(ValueError):c.validate_request('github_create_tree',{'repository_full_name':'ruvnet/RuVector','tree_elements':[{'path':c.SCOPE+'experiments/sota-2026-10-22/epoch42/REJECTION_LEDGER.json','mode':'100644','type':'blob','sha':'a'*40}]},{})
 def test_empty_unsafe_paths_types_and_changed_hash(self):
  for p in ('','/a','a/../b','a\\b'):
   with self.assertRaises(ValueError):c.relative(p)
  args={'repository_full_name':'ruvnet/RuVector','encoding':'base64','content':base64.b64encode(b'newfixture').decode()};meta={'blobs':[{'GitSHA':c.git(b'newfixture'),'body_bytes':10,'body_sha256':'0'*64}]}
  with self.assertRaises(ValueError):c.validate_request('github_create_blob',args,meta)

if __name__=='__main__':unittest.main()
