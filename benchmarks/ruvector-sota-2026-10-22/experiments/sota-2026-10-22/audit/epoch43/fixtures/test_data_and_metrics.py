"""Invented inputs/oracles only; no benchmark payloads, network, ML or Gold calls."""
import base64,copy,hashlib,json,math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import e43_features as F
import e43_materialize as D
import e43_metrics as M
class SourceData(unittest.TestCase):
 def fixture(self):
  pool=[];texts={d:f'Invented entity {d} keeps its records for two years.'for d in F.DEV_DOCUMENT_IDS};keys=['nda-'+str(i)for i in range(1,21)if i not in [6,9,14]];claims={h:{'hypothesis':'Invented condition '+h+'.'}for h in keys}
  for d in [2,46,62,212,227,321,357]:pool.append({'document_id':d,'source_split':'test','normalized_document_sha256':F.sha(F.normalized(texts.get(d,'FORBIDDEN_PROTECTED_BODY')).encode()),'document_filename_key_sha256':F.sha(F.filename_key('company-'+str(d)+'.txt').encode()),'metadata_exclusion_flags':[]})
  ids=list(F.DEV_DOCUMENT_IDS)+list(F.PROTECTED_DOCUMENT_IDS)+list(range(2000,2116));assert len(ids)==123;docs=[]
  for d in ids:docs.append({'id':d,'file_name':'company-'+str(d)+'.txt','text':texts.get(d,'FORBIDDEN_PROTECTED_BODY'),'annotation_sets':[{'annotations':{h:{'choice':'Entailment'}for h in F.HYPOTHESIS_IDS}}]})
  policy={'selected_document_ids':list(F.DEV_DOCUMENT_IDS),'selected_hypothesis_ids':list(F.HYPOTHESIS_IDS),'case_ids':list(F.DEV_CASE_IDS),'eligible_pool':pool,'selection_prefix':'RuVector-E43-Qwen3-4B-joint-context-2026-10-26/test/','protected_confirmation_document_ids':list(F.PROTECTED_DOCUMENT_IDS),'expected_structural_hypothesis_catalog_keys':keys,'excluded_prior_document_ids':[9000],'excluded_prior_normalized_document_hashes':[],'excluded_prior_filename_key_hashes':[],'all_official_test_document_ids':ids,'archive':{'sha256':F.ARCHIVE_SHA}}
  class Catalog:
   @staticmethod
   def sentence_catalog(text):return [{'unit_id':0,'start':0,'end':len(text),'sentence':text}]
  return {'labels':claims,'documents':docs},policy,Catalog
 def test_exact_four_docs_twelve_opaque_tokens_no_label_decode(self):
  data,p,c=self.fixture();body=F.canonical(data);original=json.loads
  def no_label_loads(b,*a,**kw):
   if b==b'"Entailment"':raise AssertionError('Premature semantic choice decoder')
   return original(b,*a,**kw)
  with patch.object(json,'loads',side_effect=no_label_loads):r=D.prepare_member(body,p,[],c,{})
  self.assertEqual(r['statistics']['selected_raw_choice_tokens_copied'],12);self.assertEqual(r['statistics']['semantic_gold_values_decoded'],0);self.assertEqual(r['statistics']['selected_document_text_decodes'],4);self.assertEqual(r['statistics']['selected_hypothesis_text_decodes'],3);self.assertEqual([d['document_id']for d in r['features']['documents']],list(F.DEV_DOCUMENT_IDS));v=original(r['vault']);self.assertEqual(len(v['opaque_raw_choice_tokens_base64']),12);self.assertTrue(all(base64.b64decode(t)==b'"Entailment"'for t in v['opaque_raw_choice_tokens_base64']))
 def test_protected_body_and_choice_string_decoders_never_called(self):
  data,p,c=self.fixture();decoder=D.SpanJSON.decode_string
  def guard(scan,span,field):
   if field!='field_name'and b'FORBIDDEN_PROTECTED_BODY'in scan.raw(span):raise AssertionError('Protected body decoded')
   return decoder(scan,span,field)
  with patch.object(D.SpanJSON,'decode_string',guard):r=D.prepare_member(F.canonical(data),p,[],c,{})
  self.assertEqual(r['statistics']['unselected_document_text_or_choice_decodes'],0)
 def test_wrong_global_catalog_stops_before_hypothesis_or_doc_values(self):
  data,p,c=self.fixture();del data['labels']['nda-20'];progress={}
  with self.assertRaisesRegex(ValueError,'EXACT_GLOBAL_HYPOTHESIS_KEYSET'):D.prepare_member(F.canonical(data),p,[],c,progress)
  self.assertEqual(progress['value_decoder_counts']['selected_document'],0);self.assertEqual(progress['value_decoder_counts']['selected_hypothesis'],0)
 def test_source_alias_or_hash_failure_has_safe_enum_no_replacement(self):
  data,p,c=self.fixture();data['documents'][0]['text']='Private-looking invented wrong source';progress={}
  with self.assertRaisesRegex(ValueError,'SOURCE_DOCUMENT_IDENTITY_MISMATCH')as ctx:D.prepare_member(F.canonical(data),p,[],c,progress)
  err=D.safe_error(ctx.exception);self.assertEqual(err['code'],'SOURCE_DOCUMENT_IDENTITY_MISMATCH');self.assertNotIn('Private-looking',str(err));self.assertEqual(progress.get('selected_raw_choice_tokens_copied',0),0)
 def test_exact_feature_bank_never_accepts_annotation_fields(self):
  data,p,c=self.fixture();r=D.prepare_member(F.canonical(data),p,[],c,{});bank=r['features']
  with tempfile.TemporaryDirectory()as td:
   path=Path(td)/'features.json';path.write_bytes(F.canonical(bank));rows=F.load_private_features(path,F.sha(path.read_bytes()),F.DEV_CASE_IDS);self.assertEqual(len(rows),12);bank['labels']={};path.write_bytes(F.canonical(bank))
   with self.assertRaisesRegex(ValueError,'EXACT_PRIVATE_BANK_SCHEMA'):F.load_private_features(path,F.sha(path.read_bytes()),F.DEV_CASE_IDS)
class MetricMath(unittest.TestCase):
 def test_manual_brier_and_log_observed_probability(self):
  a=M.row_score([.8,.1,.1],'NotMentioned');b=M.row_score([.8,.1,.1],'Contradiction');self.assertAlmostEqual(a['Brier'],.06);self.assertAlmostEqual(b['Brier'],1.46);self.assertEqual(a['NLL'],-math.log(.8));self.assertEqual(b['NLL'],-math.log(.1))
 def test_observed_F32_mass_unchanged_and_canonical_ties(self):
  p=[.2,.3,.50000002];self.assertIs(M.observed_probabilities(p),p);self.assertEqual(M.row_score(p,'Contradiction')['NLL'],-math.log(.50000002));self.assertEqual(M.winner([1/3]*3),0)
 def test_missing_zero_nonfinite_or_boolean_probability_rejected(self):
  for p in [[0.,.5,.5],[float('nan'),.5,.5],[True,.1,.1],[.2,.2,.2],[1.,0.,0.]]:
   with self.assertRaises(ValueError):M.observed_probabilities(p)
 def rows(self,all_N=False):
  cases=[];labels={}
  for i,cid in enumerate(F.DEV_CASE_IDS):
   label='NotMentioned'if all_N else M.LABELS[i%3];labels[cid]=label;gold=M.LABELS.index(label);forecasts={}
   for arm in M.ARMS:
    right=i<(8 if arm==M.PRIMARY else 6);pred=gold if right else(gold+1)%3;p=[.1]*3;p[pred]=.8;forecasts[arm]={'forecast_id':cid+'::'+arm,'probabilities':p,'forecast':M.TOKENS[pred]}
   cases.append({'id':cid,'document_id':F.DEV_DOCUMENT_IDS[i//3],'hypothesis_id':F.HYPOTHESIS_IDS[i%3],'forecasts':forecasts})
  return cases,labels
 def test_fixed_all_class_gates_manual_eight_vs_six_and_256_clusters(self):
  r=M.evaluate_rows(*self.rows());self.assertTrue(r['dev_passed']);self.assertEqual(r['metrics'][M.PRIMARY]['correct'],8);self.assertEqual(r['metrics'][M.CONTROLS[0]]['correct'],6);self.assertEqual(r['descriptive']['four_document_bootstrap']['replicates'],256);self.assertEqual(r['descriptive']['independent_document_clusters'],4)
 def test_missing_gold_class_fails_no_drop_or_resample(self):
  r=M.evaluate_rows(*self.rows(True));self.assertFalse(r['dev_passed']);self.assertFalse(r['gate_checks']['all_three_gold_classes_represented']);self.assertEqual(r['metrics'][M.PRIMARY]['N'],12);self.assertIsNone(r['metrics'][M.PRIMARY]['author_helper_metrics']['f1_mean'])
 def test_signed_interval_and_zero_denominator_diagnostic(self):
  self.assertEqual(M.interval([-1.,0.,1.])['lower_2_5_percentile'],-.95);r=M.numeric_diagnostic(0,0);self.assertFalse(r['applicable']);self.assertIsNone(r['fraction'])
if __name__=='__main__':unittest.main()
