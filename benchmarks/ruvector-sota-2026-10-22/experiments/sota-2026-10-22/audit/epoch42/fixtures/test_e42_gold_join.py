"""Once-only progress tests over unrelated synthetic JSON tokens, not real gold."""
import json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import e42_gold_join as G
F=G.F
class Gold(unittest.TestCase):
 def fixture(self,t,unsupported=False):
  root=Path(t)/'project';root.mkdir();out=Path(t)/'private-join';ids=['synthetic:'+str(i)for i in range(12)];arc='a'*64;header={'schema_version':1,'epoch':42,'kind':F.KIND,'role':'dev','source_archive_sha256':arc,'ids':ids,'label_encoding':'OPAQUE_RAW_JSON_STRING_TOKENS_NOT_DECODED','official_codec_source_sha256':G.CODEC_SHA};enc=lambda b:struct.pack('<I',len(b))+b;values=[G.M.LABELS[i%3]for i in range(12)]
  if unsupported:values[1]='UNSUPPORTED_UNRELATED_SYNTHETIC_LITERAL'
  vault=Path(t)/'toy-vault.bin';F.put_bytes(vault,F.MAGIC+enc(F.canonical(header))+b''.join(enc(json.dumps(v).encode())for v in values));vr=F.ref(vault);plan={'external_custody_evidence_paths':{'joined_labels':str(out/'joined_labels.json'),'gold_join_report':str(out/'GOLD_JOIN_REPORT.json')},'external_data_assets':[dict(vr,role='dev_oracle')],'data_archive_sha256':arc};pr=F.put(root/'plan.json',plan);ar=F.put(root/'admission.json',{'evidence':{'plan':pr}});checked={'ids':ids,'source_plan_sha256':pr['sha256'],'objects':{'plan':plan},'references':{'raw':{'path':'raw.json','bytes':1,'sha256':'b'*64}}};return root,out,vault,ar,checked
 def test_once_twelve_join_then_no_retry(self):
  with tempfile.TemporaryDirectory()as t:
   root,out,vault,a,checked=self.fixture(t)
   with patch.object(G.Q,'checked_bundle',return_value=checked):r=G.join_gold(a,root,out)
   self.assertEqual(r['semantic_labels_decoded'],12);self.assertEqual(r['decode_attempted_tokens'],12);self.assertEqual(r['status'],'GOLD_JOIN_COMPLETE_AFTER_PHYSICAL_CLOSURE');self.assertTrue((out/'joined_labels.json').exists())
   with self.assertRaises(ValueError):G.join_gold(a,root,out)
 def test_qualification_stop_precedes_every_vault_byte(self):
  with tempfile.TemporaryDirectory()as t:
   root,out,vault,a,checked=self.fixture(t);original=F.read_ref;seen=[]
   def read(r,*args):
    if r['path']==str(vault):seen.append(True);raise AssertionError('VAULT_READ_BEFORE_QUALIFICATION')
    return original(r,*args)
   with patch.object(G.Q,'checked_bundle',side_effect=ValueError('SYNTHETIC_UNQUALIFIED')),patch.object(F,'read_ref',side_effect=read):r=G.join_gold(a,root,out)
   self.assertEqual(seen,[]);self.assertEqual(r['semantic_labels_decoded'],0);self.assertEqual(r['label_reader_calls'],0);self.assertFalse(Path(str(vault)+'.DECODE_ATTEMPT.json').exists());self.assertFalse((out/'joined_labels.json').exists())
 def test_partial_second_literal_retained_without_echo_or_remap(self):
  with tempfile.TemporaryDirectory()as t:
   root,out,vault,a,checked=self.fixture(t,True)
   with patch.object(G.Q,'checked_bundle',return_value=checked):r=G.join_gold(a,root,out)
   self.assertEqual(r['semantic_labels_decoded'],2);self.assertEqual(r['decode_attempted_tokens'],2);self.assertFalse(r['semantic_decode_count_uncertain']);self.assertNotIn('UNSUPPORTED_UNRELATED_SYNTHETIC_LITERAL',json.dumps(r));self.assertFalse((out/'joined_labels.json').exists());self.assertTrue(Path(str(vault)+'.DECODE_ATTEMPT.json').exists())
if __name__=='__main__':unittest.main()
