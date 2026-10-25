"""Only unrelated generated schema fixtures; no real archive/case/labels."""
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import e41_materialize as D
F=D.F
P=Path('/workspace/ruvector-e41-engineering-impl/context-source-v1/project/experiments/sota-2026-10-22/candidate/epoch41/context_windows.py');spec=importlib.util.spec_from_file_location('e41_pure_catalog_fixture',P);C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
class Materializer(unittest.TestCase):
 def fixture(self):
  salt='unrelated-fixture-v1';keys=['nda-'+str(i)for i in range(1,18)];hyp=sorted(keys,key=lambda k:(F.sha((salt+'|hypothesis|'+k).encode()),k))[:3];pool=[];docs=[]
  for i in range(123):
   did=990000+i;text=f'Synthetic distinct document number {did}. Another independent sentence. Final clause.';name=f'fictional-{did}.txt'
   if i<15:pool.append({'document_id':did,'source_split':'test','metadata_exclusion_flags':[],'normalized_document_sha256':F.sha(F.normalized(text).encode()),'document_filename_key_sha256':F.sha(F.filename_key(name).encode())})
   docs.append({'id':did,'file_name':name,'text':text,'spans':[[0,5]],'annotation_sets':[{'annotations':{k:{'choice':'OPAQUE_GOLD_SENTINEL','spans':[0]}for k in keys}}]})
  ranked=sorted(pool,key=lambda r:(F.sha((salt+'|test|'+str(r['document_id'])+'|'+r['normalized_document_sha256']).encode()),r['document_id']));sel=[r['document_id']for r in ranked[:4]];ids=[f'contractnli:eced6528:test:{d}:{h}'for d in sel for h in hyp]
  for d in docs:
   if d['id']not in sel:d['text']='UNSELECTED_DOCUMENT_SENTINEL'
  labels={k:{'hypothesis':'A synthetic independently authored hypothesis '+k+'.'if k in hyp else'UNSELECTED_HYPOTHESIS_SENTINEL'}for k in keys};policy={'selection_salt':salt,'selected_document_ids':sel,'selected_hypothesis_ids':hyp,'case_ids':ids,'eligible_pool':pool,'expected_structural_hypothesis_catalog_keys':keys,'all_official_test_document_ids':[d['id']for d in docs],'excluded_E40_document_ids':[1,2],'excluded_E40_normalized_document_hashes':[],'archive':{'sha256':'a'*64}};return json.dumps({'labels':labels,'documents':docs}).encode(),policy
 def test_opaque_twelve_tokens_and_no_unselected_decoder(self):
  b,p=self.fixture();original=json.loads
  def observe(value,*a,**k):
   text=value.decode()if type(value)is bytes else value
   for sentinel in ['OPAQUE_GOLD_SENTINEL','UNSELECTED_DOCUMENT_SENTINEL','UNSELECTED_HYPOTHESIS_SENTINEL']:self.assertNotIn(sentinel,text)
   return original(value,*a,**k)
  progress={}
  with patch.object(D.json,'loads',side_effect=observe):r=D.prepare_member(b,p,[],C,progress)
  st=r['statistics'];self.assertEqual(st['selected_document_text_decodes'],4);self.assertEqual(st['selected_hypothesis_text_decodes'],3);self.assertEqual(st['semantic_gold_values_decoded'],0);self.assertEqual(st['selected_raw_choice_tokens_copied'],12);self.assertTrue(progress['global_hypothesis_keyset_validated']);self.assertEqual(len(r['features']['documents']),4);self.assertEqual(len(r['features']['cases']),12);self.assertEqual(st['expanded_pair_source_units'],3*st['unique_source_units']);self.assertEqual(r['vault'].count(b'OPAQUE_GOLD_SENTINEL'),12)
 def test_global_keyset_stops_before_any_selected_text_decode(self):
  b,p=self.fixture();v=json.loads(b);v['labels']['replacement']=v['labels'].pop('nda-17');progress={}
  with self.assertRaisesRegex(ValueError,'GLOBAL_HYPOTHESIS_KEYSET'):D.prepare_member(json.dumps(v).encode(),p,[],C,progress)
  self.assertEqual(progress['value_decoder_counts']['selected_document'],0);self.assertEqual(progress['value_decoder_counts']['selected_hypothesis'],0)
 def test_document_and_hypothesis_ranking_no_replacements(self):
  b,p=self.fixture();p['selected_document_ids'].reverse();p['case_ids']=[f'contractnli:eced6528:test:{d}:{h}'for d in p['selected_document_ids']for h in p['selected_hypothesis_ids']]
  with self.assertRaisesRegex(ValueError,'DOCUMENT_HASH_RANKING'):D.prepare_member(b,p,[],C,{})
  b,p=self.fixture();p['selected_hypothesis_ids'].reverse();p['case_ids']=[f'contractnli:eced6528:test:{d}:{h}'for d in p['selected_document_ids']for h in p['selected_hypothesis_ids']]
  with self.assertRaisesRegex(ValueError,'HYPOTHESIS_KEY_HASH_RANKING'):D.prepare_member(b,p,[],C,{})
 def test_alias_and_caps_stop_complete_cohort(self):
  b,p=self.fixture();progress={}
  with self.assertRaisesRegex(ValueError,'OLD_LEGAL96_EXPOSED_SUBSTRING_ALIAS_STOP'):D.prepare_member(b,p,['another independent sentence.'],C,progress)
  self.assertEqual(progress['selected_case_ids'],p['case_ids'])
  with patch.object(C,'MAX_DOCUMENT_BYTES',8):
   with self.assertRaisesRegex(ValueError,'SOURCE_DOCUMENT_CAP'):D.prepare_member(b,p,[],C,{})
 def test_choice_only_structural_string_type(self):
  b,p=self.fixture();v=json.loads(b);selected=p['selected_document_ids'][0];doc=next(d for d in v['documents']if d['id']==selected);doc['annotation_sets'][0]['annotations'][p['selected_hypothesis_ids'][0]]['choice']=False
  with self.assertRaisesRegex(ValueError,'OPAQUE_RAW_CHOICE_STRING_REQUIRED'):D.prepare_member(json.dumps(v).encode(),p,[],C,{})
 def test_linked_feature_loader_and_mutation(self):
  b,p=self.fixture();r=D.prepare_member(b,p,[],C,{})
  with tempfile.TemporaryDirectory()as d:
   file=Path(d)/'synthetic-features.json';F.put(file,r['features']);records=F.load_private_features(file,F.sha(file.read_bytes()),p['case_ids']);self.assertEqual(len(records),12);self.assertEqual(len({r['document_id']for r in records}),4);self.assertIs(records[0]['evidence'],records[1]['evidence']);r['features']['cases'][0]['input_sha256']='0'*64;bad=Path(d)/'bad.json';F.put(bad,r['features'])
   with self.assertRaisesRegex(ValueError,'SOURCE_PAIR_HASH'):F.load_private_features(bad,F.sha(bad.read_bytes()),p['case_ids'])
 def test_old_exposed_dev_only_gold_skip_and_safe_errors(self):
  rows=[{'input':{'state':'Synthetic already exposed DEV sentence.'},'evaluation':{'gold':'OLD_GOLD_SENTINEL'}}for _ in range(96)]
  with tempfile.TemporaryDirectory()as d:
   file=Path(d)/'old-exposed.jsonl';file.write_bytes(b'\n'.join(json.dumps(r).encode()for r in rows));original=json.loads
   def observe(value,*a,**k):
    self.assertNotIn('OLD_GOLD_SENTINEL',value.decode()if type(value)is bytes else value);return original(value,*a,**k)
   with patch.object(D.json,'loads',side_effect=observe):self.assertEqual(len(D.old_legal96_states(F.ref(file))),96)
  sentinel='PRIVATE_SOURCE_VALUE_SENTINEL';self.assertNotIn(sentinel,json.dumps(D.safe_error(ValueError(sentinel))))
if __name__=='__main__':unittest.main()
