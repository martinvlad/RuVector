import json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import finfact_io as I
import finfact_gold_join as G
import finfact_data as D
class LateGold(unittest.TestCase):
 def fixture(self,root,bad=None):
  ids=['unrelated-private-toy-'+str(i)for i in range(12)];h={'schema_version':1,'epoch':39,'kind':I.KIND,'role':'dev','source_archive_sha256':D.ARCHIVE_SHA,'ids':ids,'label_encoding':'OPAQUE_RAW_JSON_STRING_TOKENS_NOT_DECODED'};part=lambda b:struct.pack('<I',len(b))+b;tokens=[json.dumps('true'if i%2 else'false').encode()for i in range(12)]
  if bad is not None:tokens[bad]=b'"unsupported"'
  p=root/'toy-vault.bin';p.write_bytes(D.MAGIC+part(json.dumps(h).encode())+b''.join(part(x)for x in tokens));v=dict(I.raw_ref(p),role='dev_oracle');return {'ids':ids,'source_plan_sha256':'1'*64,'objects':{'plan':{'external_data_assets':[v]}},'references':{},'closure':{}}
 def test_once_join_no_original_archive(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);checked=self.fixture(root);out=root/'gold';project=root/'project';project.mkdir()
   with patch.object(G.C,'checked_bundle',return_value=checked):
    report=G.join_gold({'path':'purefixture','bytes':0,'sha256':'0'*64},project,out);self.assertEqual(report['status'],'GOLD_JOIN_COMPLETE_AFTER_PHYSICAL_CLOSURE');self.assertEqual(report['semantic_labels_decoded'],12);self.assertEqual(len(list(out.glob('progress-*-after.json'))),12)
    with self.assertRaises((ValueError,FileExistsError)):G.join_gold({'path':'purefixture','bytes':0,'sha256':'0'*64},project,root/'retry')
 def test_partial_failure_retains_counts_and_no_retry(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);checked=self.fixture(root,5);project=root/'project';project.mkdir()
   with patch.object(G.C,'checked_bundle',return_value=checked):
    r=G.join_gold({'path':'purefixture','bytes':0,'sha256':'0'*64},project,root/'gold');self.assertEqual(r['semantic_labels_decoded'],6);self.assertEqual(r['decode_attempted_tokens'],6);self.assertEqual(r['status'],'GOLD_JOIN_FAILED_FINAL_NO_RETRY');self.assertFalse((root/'gold'/'joined_labels.json').exists());self.assertFalse(r['semantic_decode_count_uncertain'])
    with self.assertRaises(FileExistsError):G.join_gold({'path':'purefixture','bytes':0,'sha256':'0'*64},project,root/'retry')
 def test_before_physical_fence_does_not_open_vault(self):
  with tempfile.TemporaryDirectory()as t:
   with patch.object(G.C,'checked_bundle',side_effect=ValueError('NO_CLOSURE')):
    with self.assertRaisesRegex(ValueError,'NO_CLOSURE'):G.join_gold({},Path(t)/'project',Path(t)/'out')
   self.assertFalse((Path(t)/'out').exists())
if __name__=='__main__':unittest.main()
