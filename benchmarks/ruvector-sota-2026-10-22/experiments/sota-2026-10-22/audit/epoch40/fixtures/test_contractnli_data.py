import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import contractnli_data as D
import contractnli_guard as G

class Custodian(unittest.TestCase):
 def fixture(self,unknown_gold=False):
  salt='unrelated-synthetic-schema-fixtures-v1';keys=['hyp-'+str(i)for i in range(17)];chosen=min(keys,key=lambda k:D.sha((salt+'|hypothesis|'+k).encode()));labels={k:{'hypothesis':'An unrelated schema test hypothesis.'if k==chosen else'UNSELECTED_HYPOTHESIS_SENTINEL'}for k in keys};docs=[];pool=[];eligible=[]
  for i in range(123):
   did=900000+i;text=f'Independent synthetic document {did}.\nSecond passage.\nFinal tail.';name=f'synthetic-{did}.txt';norm=G.digest(G.normalized(text));flag=[]if i<12 else['unrelated_fixture_exclusion'];pool.append({'document_id':did,'source_split':'test','metadata_exclusion_flags':flag,'normalized_document_sha256':norm,'document_filename_key_sha256':D.sha(D.filename_key(name).encode())})
   if not flag:eligible.append(did)
   annotations={k:{'choice':'OPAQUE_UNKNOWN_GOLD_SENTINEL'if unknown_gold else['NotMentioned','Entailment','Contradiction'][i%3],'spans':[0]}for k in keys};docs.append({'id':did,'file_name':name,'text':text if i<12 else'UNSELECTED_DOCUMENT_SENTINEL','spans':[[0,20],[21,30]],'annotation_sets':[{'annotations':annotations}]})
  by={r['document_id']:r for r in pool};ranked=sorted(eligible,key=lambda did:(D.sha((salt+'|test|'+str(did)+'|'+by[did]['normalized_document_sha256']).encode()),did));policy={'selection_salt':salt,'selected_document_ids':ranked,'eligible_pool_document_count':12,'all_official_test_document_ids':[d['id']for d in docs]};return json.dumps({'labels':labels,'documents':docs},ensure_ascii=False).encode(),policy,pool,chosen
 def test_exact_schema_only_raw_gold_remains_opaque(self):
  member,policy,pool,hyp=self.fixture(unknown_gold=True);progress={};original=json.loads
  def observe(value,*args,**kwargs):
   text=value.decode()if type(value)is bytes else value
   self.assertNotIn('OPAQUE_UNKNOWN_GOLD_SENTINEL',text);self.assertNotIn('UNSELECTED_DOCUMENT_SENTINEL',text);self.assertNotIn('UNSELECTED_HYPOTHESIS_SENTINEL',text)
   return original(value,*args,**kwargs)
  with patch.object(D.json,'loads',side_effect=observe):r=D.prepare_member(member,policy,pool,[], '1'*64,progress)
  self.assertEqual(r['statistics']['semantic_gold_values_decoded'],0);self.assertEqual(r['statistics']['raw_gold_tokens_copied'],12);self.assertEqual(r['statistics']['selected_document_text_decodes'],12);self.assertEqual(r['statistics']['selected_hypothesis_text_decodes'],1);self.assertIn(b'OPAQUE_UNKNOWN_GOLD_SENTINEL',r['vault']);self.assertEqual(progress['document_IDs_seen'],123);self.assertEqual(r['statistics']['selected_hypothesis_id'],hyp)
 def test_source_partition_preserves_prefix_gaps_and_tail(self):
  text='Prefix\nA phrase\nTail.';units=G.partition(text,[[7,8],[9,15],[7,8]]);self.assertEqual(''.join(u['sentence']for u in units),text);self.assertEqual([u['start']for u in units],[0,8,15]);self.assertEqual(units[-1]['end'],len(text))
 def test_duplicate_alias_stops_whole_fixed_selection(self):
  member,p,pool,_=self.fixture();progress={}
  with self.assertRaisesRegex(ValueError,'CLAUSE_SUBSTRING_STOP'):D.prepare_member(member,p,pool,['second passage.'],'1'*64,progress)
  self.assertEqual(len(progress['selected_case_ids']),12);self.assertEqual(progress['value_decoder_counts']['selected_document'],1)
 def test_source_version_hash_mismatch_stops_without_replacement(self):
  member,p,pool,_=self.fixture();pool[0]['normalized_document_sha256']='0'*64;by={r['document_id']:r for r in pool};p['selected_document_ids']=sorted(p['selected_document_ids'],key=lambda i:(D.sha((p['selection_salt']+'|test|'+str(i)+'|'+by[i]['normalized_document_sha256']).encode()),i))
  with self.assertRaisesRegex(ValueError,'DOCUMENT_IDENTITY_MISMATCH'):D.prepare_member(member,p,pool,[],'1'*64)
 def test_metadata_hash_ranking_is_enforced(self):
  member,p,pool,_=self.fixture();p['selected_document_ids']=list(reversed(p['selected_document_ids']))
  with self.assertRaisesRegex(ValueError,'HASH_SELECTION_MISMATCH'):D.prepare_member(member,p,pool,[],'1'*64)
 def test_non_string_choice_is_structural_stop_without_decode(self):
  member,p,pool,hyp=self.fixture();v=json.loads(member);v['documents'][0]['annotation_sets'][0]['annotations'][hyp]['choice']=0
  with self.assertRaisesRegex(ValueError,'RAW_CHOICE_STRING'):D.prepare_member(json.dumps(v).encode(),p,pool,[],'1'*64)
 def test_prospective_caps_post_selection_stop(self):
  member,p,pool,_=self.fixture()
  with patch.object(D.G,'MAX_DOCUMENT_BYTES',8):
   with self.assertRaisesRegex(ValueError,'INPUT_ADMISSION_STOP'):D.prepare_member(member,p,pool,[],'1'*64)
 def test_private_bank_identity_and_source_offsets(self):
  member,p,pool,_=self.fixture();r=D.prepare_member(member,p,pool,[],'1'*64)
  with tempfile.TemporaryDirectory()as t:
   f=Path(t)/'toy-features.json';D.put(f,r['features']);rows=D.load_private_features(f,D.sha(f.read_bytes()),r['selected_ids']);self.assertEqual(len(rows),12);self.assertTrue(all(G.guard_features(x['claim'],[u['sentence']for u in x['evidence']])['passed']for x in rows))
 def test_old_exposed_DEV_alias_parser_never_decodes_gold(self):
  rows=[{'input':{'state':'A synthetic already exposed DEV passage.'},'evaluation':{'gold':'FORBIDDEN_OLD_GOLD_SENTINEL'}}for _ in range(96)]
  with tempfile.TemporaryDirectory()as t:
   p=Path(t)/'old-dev-only.jsonl';p.write_bytes(b'\n'.join(json.dumps(r).encode()for r in rows));original=json.loads
   def observe(value,*args,**kwargs):
    text=value.decode()if type(value)is bytes else value;self.assertNotIn('FORBIDDEN_OLD_GOLD_SENTINEL',text);return original(value,*args,**kwargs)
   with patch.object(D.json,'loads',side_effect=observe):states=D.old_legal96_states(p,D.sha(p.read_bytes()))
   self.assertEqual(len(states),96)
 def test_safe_actionable_enum_never_exposes_private_exception(self):
  row=D.safe_error(ValueError('OLD_EXPOSED_LEGAL96_NORMALIZED_CLAUSE_SUBSTRING_STOP'));self.assertEqual(row['code'],'OLD_EXPOSED_LEGAL96_NORMALIZED_CLAUSE_SUBSTRING_STOP');row=D.safe_error(ValueError('INPUT_ADMISSION_STOP:SOURCE_DOCUMENT_UTF8_CAP'));self.assertEqual(row['input_flags'],['SOURCE_DOCUMENT_UTF8_CAP'])
  private='PRIVATE_CONTRACT_SOURCE_OR_FILENAME_SENTINEL';row=D.safe_error(ValueError(private));self.assertNotIn(private,json.dumps(row));self.assertEqual(row['code'],'CUSTODIAN_SOURCE_OR_INPUT_ADMISSION_STOP');row=D.safe_error(ValueError('INPUT_ADMISSION_STOP:'+private));self.assertNotIn(private,json.dumps(row));self.assertNotIn('input_flags',row)
if __name__=='__main__':unittest.main()
