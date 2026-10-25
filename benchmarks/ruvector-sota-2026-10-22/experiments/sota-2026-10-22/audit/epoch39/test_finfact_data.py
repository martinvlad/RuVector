"""Disjoint synthetic custody/API fixtures only; never opens Fin-Fact archive."""
import copy,hashlib,json,os,tempfile,unittest
from pathlib import Path
import finfact_data as D
import finfact_guard as G
from finfact_json_spans import SpanJSON

class CustodyTests(unittest.TestCase):
 def toy(self,n=12):
  return [{'url':f'https://fixture.invalid/article/{i}','claim':f'Toy ledger {i} has a recorded item.','evidence':[{'sentence':f'Independent source fixture {i} describes an allocation.','hrefs':['never decoded']}],'label':['true','false','neutral'][i%3],'justification':'SECRET_RATIONALE_MUST_NOT_DECODE','sci_digest':['SECRET_DIGEST_MUST_NOT_DECODE'],'nested':{'label':'SECRET_NESTED_GOLD'}}for i in range(n)]
 def payload(self,rows):return json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()
 def test_span_scanner_matches_structural_offsets_without_values(self):
  b=b'[{"url":"https://fixture.invalid/a","claim":"C","evidence":[{"sentence":"S"}],"label":"GOLD_DENY","nested":{"secret":[false,null,-1.2e2,{"x":"escaped\\\"ok"}]}}]';x=SpanJSON(b);rows=list(x.root_records());self.assertEqual(len(rows),1);fields=x.members(rows[0][1]);self.assertEqual(x.raw(fields['label']),b'"GOLD_DENY"');self.assertEqual(x.decode_string(fields['url'],'url'),'https://fixture.invalid/a')
  with self.assertRaises(ValueError):x.decode_string(fields['label'],'label')
  self.assertEqual(x.gold_values_decoded,0);self.assertEqual(x.decoded['selected_claim'],0)
 def test_forbidden_json_values_never_pass_to_decoder(self):
  rows=self.toy();rows[0]['label']='GOLD_DENY';real=D.J.json.loads
  def watch(s,*a,**kw):
   if isinstance(s,(str,bytes))and ('GOLD_DENY'in(s.decode()if isinstance(s,bytes)else s)or'SECRET_RATIONALE'in(s.decode()if isinstance(s,bytes)else s)):raise AssertionError('Forbidden semantic decoder invoked')
   return real(s,*a,**kw)
  D.J.json.loads=watch
  try:r=D.prepare_bytes(self.payload(rows))
  finally:D.J.json.loads=real
  self.assertEqual(r['status'],'READY_LABEL_BLIND_DEV_FEATURES_AND_OPAQUE_VAULT');self.assertEqual(r['raw_gold_tokens_copied'],12);self.assertEqual(r['statistics']['semantic_gold_values_decoded'],0);self.assertEqual(r['statistics']['decoded_value_counts']['selected_claim'],12)
 def test_url_identity_preserves_empty_path_query_and_port_text(self):
  self.assertEqual(D.canonical_url('HTTP://EXAMPLE.COM:0080?Q=VaL#fragment'),'http://example.com:0080?Q=VaL')
  self.assertEqual(D.canonical_url('https://EXAMPLE.COM'),'https://example.com')
  self.assertEqual(D.canonical_url('https://EXAMPLE.COM?#f'),'https://example.com?')
  self.assertEqual(D.canonical_url('https://EXAMPLE.COM/a%2FB?x=%2F#f'),'https://example.com/a%2FB?x=%2F')
  self.assertEqual(D.canonical_url('HTTP://[ABCD::1]:0080/path?q=Hi#f'),'http://[abcd::1]:0080/path?q=Hi')
  with self.assertRaises(ValueError):D.canonical_url('https://user:pass@example.com/a')
 def test_url_group_first_ordinal_and_hash_order(self):
  rows=self.toy();dup=copy.deepcopy(rows[0]);dup['evidence']=[{'sentence':'Later accumulating source text must not win representative selection.'}];rows.append(dup);r=D.prepare_bytes(self.payload(rows));ids=r['statistics']['selected_ids'];self.assertEqual(len(ids),12);self.assertIn('finfact:b3038781:ordinal:0',ids);self.assertNotIn('finfact:b3038781:ordinal:12',ids);self.assertEqual(r['statistics']['eligible_unique_URL_groups'],12)
 def test_structural_nonempty_only_and_no_label_selection(self):
  rows=self.toy();rows[0]['evidence'][0]['sentence']=' \t\n';rows.append(copy.deepcopy(rows[0]));rows[-1]['url']='https://fixture.invalid/extra';rows[-1]['evidence'][0]['sentence']='Replacement structural eligible independent source.'
  r=D.prepare_bytes(self.payload(rows));self.assertEqual(r['statistics']['structurally_ineligible_rows'],1);self.assertEqual(r['statistics']['selected_count'],12);self.assertNotIn('finfact:b3038781:ordinal:0',r['statistics']['selected_ids'])
 def test_post_selection_cap_stops_without_replacement_or_vault_copy(self):
  rows=self.toy();rows[0]['claim']='z'*65537;r=D.prepare_bytes(self.payload(rows));self.assertEqual(r['status'],'STOP_INPUT_ADMISSION_NO_REPLACEMENT');self.assertEqual(r['statistics']['selected_count'],12);self.assertEqual(len(r['identities']),12);self.assertIsNone(r['features']);self.assertIsNone(r['vault']);self.assertEqual(r['raw_gold_tokens_copied'],0);self.assertEqual(r['statistics']['semantic_gold_values_decoded'],0)
 def test_direct_verdict_stops_whole_selection(self):
  rows=self.toy();rows[3]['evidence'][0]['sentence']='Our ruling: false.';r=D.prepare_bytes(self.payload(rows));self.assertEqual(r['status'],'STOP_INPUT_ADMISSION_NO_REPLACEMENT');self.assertEqual(len(r['statistics']['selected_ids']),12);self.assertEqual(r['raw_gold_tokens_copied'],0)
 def test_private_feature_exact_hash_and_forbidden_fields(self):
  r=D.prepare_bytes(self.payload(self.toy()))
  with tempfile.TemporaryDirectory()as t:
   p=Path(t)/'features.json';D.put(p,r['features']);ids=r['statistics']['selected_ids'];out=D.load_private_features(p,D.sha(p.read_bytes()),ids);self.assertEqual(len(out),12)
   bad=copy.deepcopy(r['features']);bad['records'][0]['label']='true';q=Path(t)/'bad.json';D.put(q,bad)
   with self.assertRaises(ValueError):D.load_private_features(q,D.sha(q.read_bytes()),ids)
 def test_unicode_nonempty_without_string_decoder(self):
  for raw,want in [(b'" \\t\\n"',False),(b'"\\u2000"',False),(b'"\\u2000x"',True),(b'"\\\\"',True)]:
   x=SpanJSON(raw);self.assertIs(x.string_nonempty(x.value(0)),want);self.assertEqual(sum(x.decoded.values()),0)
 def test_malformed_duplicate_and_trailing_json_rejected(self):
  for b in [b'[{"x":1,}]',b'[{"x":"bad\\q"}]',b'[{"x":1}] junk']:
   with self.assertRaises(ValueError):list(SpanJSON(b).root_records())
  x=SpanJSON(b'[{"x":1,"x":2}]');_,r=next(x.root_records())
  with self.assertRaises(ValueError):x.members(r)
 def closure(self,ids,proofpath):
  return {'physical_readouts_completed':48,'required_readout_ids':[i+'::'+a for i in ids for a in D.ARMS],'completed_readout_ids':[i+'::'+a for i in ids for a in D.ARMS],'model_profiles_disposed':['xxlarge','b354'],'native_child_closed':True,'all_forecasts_closed_before_gold':True,'source_plan_sha256':'a'*64,'physical_closure_evidence':D.ref(proofpath)}
 def proof(self):
  return {'schema_version':1,'epoch':39,'kind':D.KIND,'phase':'dev','source_plan_sha256':'a'*64,'physical_closure_passed':True,'physical_supervisor_closed':True,'unknown_physical_ownership':False,'owned_worker_group_members':[],'supervisor_identity':{'pid':999999991,'startticks':1,'pgid':999999991,'sid':999999991},'kernel_boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'pid_namespace_inode':os.stat('/proc/self/ns/pid').st_ino}
 def test_gold_separate_physical_fence_and_once_only(self):
  r=D.prepare_bytes(self.payload(self.toy()));ids=r['statistics']['selected_ids']
  with tempfile.TemporaryDirectory()as t:
   p=Path(t);vault=p/'oracle.bin';D.put_bytes(vault,r['vault']);proof=p/'proof.json';D.put(proof,self.proof());closure=self.closure(ids,proof);labels,receipt=D.read_selected_gold(vault,D.sha(vault.read_bytes()),ids,closure);self.assertEqual(len(labels),12);self.assertEqual(receipt['semantic_labels_decoded'],12);self.assertEqual(receipt['physical_raw_tokens_copied_before_measurement'],12)
   with self.assertRaises(ValueError):D.read_selected_gold(vault,D.sha(vault.read_bytes()),ids,closure)
 def test_gold_refuses_incomplete_or_unclosed(self):
  r=D.prepare_bytes(self.payload(self.toy()));ids=r['statistics']['selected_ids']
  with tempfile.TemporaryDirectory()as t:
   p=Path(t);vault=p/'oracle.bin';D.put_bytes(vault,r['vault']);proof=p/'proof.json';D.put(proof,self.proof())
   for field,value in [('physical_readouts_completed',47),('model_profiles_disposed',['b354','xxlarge']),('native_child_closed',False),('completed_readout_ids',[])]:
    c=self.closure(ids,proof);c[field]=value
    with self.assertRaises(ValueError):D.read_selected_gold(vault,D.sha(vault.read_bytes()),ids,c)
   self.assertFalse(Path(str(vault)+'.DECODE_ATTEMPT.json').exists())
 def test_no_actual_dataset_without_local_root_approval(self):
  with tempfile.TemporaryDirectory()as t:
   p=Path(t);policy=p/'policy.json';D.put(policy,{'epoch':39,'kind':D.KIND,'DEV_cases':12,'roles':{'train':[],'calibration':[],'confirmation':[]}});seal=p/'seal.json';D.put(seal,{'epoch':39,'kind':D.KIND,'policy_sha256':D.sha(policy.read_bytes()),'source_files':[]});approval=p/'approval.json';D.put(approval,{'approved':False})
   with self.assertRaises((KeyError,ValueError)):D.verify_local_approval(policy,seal,approval,D.sha(approval.read_bytes()))

class GuardTests(unittest.TestCase):
 def test_six_fixed_verdict_cues(self):
  examples=['Our ruling is below.','We rated this claim.','The statement was labelled.','This claim is mostly false.','Verdict: neutral.','That is pants-on-fire.']
  for i,text in enumerate(examples):self.assertIn('DIRECT_VERDICT_PATTERN_'+str(i+1),G.guard_premise('A different hypothesis.',text)['flags'])
 def test_selfclaim_normalization_and_valid_negative_evidence(self):
  self.assertFalse(G.guard_features('Recorded VALUE.', [' recorded value. ','RECORDED VALUE.'])['passed']);self.assertTrue(G.guard_features('Rates were unchanged.', ['The bond rating fell and the reported rate was not unchanged.'])['passed']);self.assertTrue(G.guard_premise('Revenue increased.','The false ceiling was replaced; revenue decreased.')['passed'])
 def test_cap_all_units_before_any_model(self):
  self.assertIn('PROVIDED_UNIT_CAP_STOP',G.guard_features('A distinct claim.',['evidence']*257)['flags']);self.assertIn('UNIT_BYTE_CAP_STOP',G.guard_features('A distinct claim.',['x'*262145])['flags'])

if __name__=='__main__':unittest.main()
