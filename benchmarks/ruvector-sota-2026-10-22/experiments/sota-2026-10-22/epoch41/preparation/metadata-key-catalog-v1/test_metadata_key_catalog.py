"""Unrelated structural metadata fixtures only; no official catalog/case reads."""
import json,unittest
from unittest.mock import patch
import metadata_key_catalog as M
class Catalog(unittest.TestCase):
 def test_nonsequential_keys_no_string_values_decoded(self):
  v={'labels':{'task-2':{'hypothesis':'HYPOTHESIS_SENTINEL'},'task-9':{'hypothesis':'HYPOTHESIS_SENTINEL'},'task-44':{'hypothesis':'HYPOTHESIS_SENTINEL'}},'documents':[{'id':123,'text':'DOCUMENT_SENTINEL','annotation_sets':[{'annotations':{'task-2':{'choice':'CHOICE_SENTINEL'}}}]}]};b=json.dumps(v).encode();orig=json.loads
  def observe(x,*a,**k):
   t=x.decode()if type(x)is bytes else x
   for s in ['HYPOTHESIS_SENTINEL','DOCUMENT_SENTINEL','CHOICE_SENTINEL']:self.assertNotIn(s,t)
   return orig(x,*a,**k)
  with patch.object(M.J.json,'loads',side_effect=observe):r=M.catalog_only(b)
  self.assertEqual(r['source_order_keys'],['task-2','task-9','task-44']);self.assertEqual(r['key_count'],3);self.assertFalse(r['matches_advertised_count']);self.assertEqual(r['semantic_gold_values_decoded'],0);self.assertEqual(r['old_Legal96_text_decodes'],0);self.assertTrue(all(x==0 for k,x in r['decoder_counts'].items()if k!='field_name'));self.assertFalse(r['hypothesis_or_case_selection'])
 def test_duplicate_or_nonobject_catalog_stops(self):
  for b in [b'{"labels":{"task-2":{},"task-2":{}},"documents":[]}',b'{"labels":[],"documents":[]}']:
   with self.assertRaises(ValueError):M.catalog_only(b)
 def test_safe_errors_do_not_echo_values(self):
  private='UNRELATED_PRIVATE_SENTINEL';self.assertNotIn(private,json.dumps(M.safe_error(ValueError(private))));self.assertEqual(M.safe_error(ValueError('EXACT_ROOT_OBJECT'))['code'],'EXACT_ROOT_OBJECT')
if __name__=='__main__':unittest.main()
