import json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import contractnli_io as I
import contractnli_gold_join as G
import contractnli_data as D
class Gold(unittest.TestCase):
 def setup_case(self,root,bad=None):
  ids=['unrelated-private-codec-fixture-'+str(i)for i in range(12)];header={'schema_version':1,'epoch':40,'kind':I.KIND,'role':'dev','source_archive_sha256':'1'*64,'ids':ids,'label_encoding':'OPAQUE_RAW_JSON_STRING_TOKENS_NOT_DECODED','official_codec_source_sha256':'9c63102a01576c230da94695f593fd7bd4fe2d0b20672b74e8a7f62aba426fc4'};piece=lambda x:struct.pack('<I',len(x))+x;tokens=[json.dumps(['NotMentioned','Entailment','Contradiction'][i%3]).encode()for i in range(12)]
  if bad is not None:tokens[bad]=b'"UnsupportedSyntheticChoice"'
  vault=root/'toy-vault.bin';vault.write_bytes(D.MAGIC+piece(json.dumps(header).encode())+b''.join(piece(x)for x in tokens));return {'ids':ids,'source_plan_sha256':'2'*64,'objects':{'plan':{'external_data_assets':[dict(I.raw_ref(vault),role='dev_oracle')],'data_archive_sha256':'1'*64}},'references':{},'closure':{}}
 def test_exact_author_literals_join_once_no_normalization(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);c=self.setup_case(root);project=root/'project';project.mkdir()
   with patch.object(G.C,'checked_bundle',return_value=c):
    r=G.join_gold({'path':'purefixture','bytes':0,'sha256':'0'*64},project,root/'join');self.assertEqual(r['status'],'GOLD_JOIN_COMPLETE_AFTER_PHYSICAL_CLOSURE');self.assertEqual(r['semantic_labels_decoded'],12)
    with self.assertRaises(FileExistsError):G.join_gold({'path':'purefixture','bytes':0,'sha256':'0'*64},project,root/'retry')
 def test_partial_unknown_literal_count_retained_and_no_join(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);c=self.setup_case(root,bad=1);project=root/'project';project.mkdir()
   with patch.object(G.C,'checked_bundle',return_value=c):
    r=G.join_gold({'path':'purefixture','bytes':0,'sha256':'0'*64},project,root/'join');self.assertEqual(r['semantic_labels_decoded'],2);self.assertEqual(r['decode_attempted_tokens'],2);self.assertFalse(r['semantic_decode_count_uncertain']);self.assertFalse((root/'join/joined_labels.json').exists());self.assertEqual(len(list((root/'join').glob('progress-*-after.json'))),2)
 def test_no_vault_open_before_full_qualified_closure(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t)
   with patch.object(G.C,'checked_bundle',side_effect=ValueError('SYNTHETIC_SOURCE_OR_SUPERVISOR_REJECTION')):
    with self.assertRaises(ValueError):G.join_gold({},root/'project',root/'out')
   self.assertFalse((root/'out').exists())
if __name__=='__main__':unittest.main()
