"""Meaningful invented-fixture custody checks; never benchmark measurements."""
import ast,copy,hashlib,importlib.util,json,sys,unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('e52_custody_fixture_source',HERE/'e52_custody.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
POLICY=json.loads((HERE/'IDENTITY_POLICY.v2.json').read_bytes())

def fixture(choice='OPAQUE_CHOICE_FIXTURE_A'):
 policy=copy.deepcopy(POLICY);all_ids=sorted(set(x['document_id']for x in policy['metadata_pool_after_retirement'])|set(policy['retired_originalDEV96_document_ids'])|set(policy['prior_epoch48_all_excluded_document_ids'])|set(policy['prior_epoch50_all_excluded_document_ids'])|set(policy['prior_epoch51_all_excluded_document_ids']))
 assert len(all_ids)==61
 metadata=[];records=[]
 for did in all_ids:
  name=f'invented-fixture-{did}.txt';text=f'Invented nonbenchmark source {did}. Quantity 3.14; date 2026-10-26.\n\nNo source text from a benchmark is used.'
  row={'document_id':did,'source_split':'dev','normalized_document_sha256':C.sha(C.normalized(text).encode()),'document_filename_key_sha256':C.sha(C.filename_key(name).encode()),'metadata_exclusion_flags':[]};metadata.append(row)
  selected=did in C.DEV_DOCS
  # Unselected payloads deliberately violate the selected document schema.
  # Traversing these semantically would fail; DATA must only skip raw spans.
  record={'id':did,'file_name':name if selected else {'MUST_NOT_DECODE_NAME':True},'text':text if selected else {'MUST_NOT_DECODE_TEXT':True},'annotation_sets':[{'annotations':{h:{'choice':choice if selected else {'MUST_NOT_DECODE_CHOICE':True}}for h in C.CATALOG_KEYS}}]}
  records.append(record)
 policy['selected_dev_documents']=[next(x for x in metadata if x['document_id']==did)for did in C.DEV_DOCS]
 labels={h:{'hypothesis':f'Invented hypothesis {h}: quantity is 3.14.'}for h in C.CATALOG_KEYS}
 member=json.dumps({'labels':labels,'documents':records},ensure_ascii=True).encode()
 return member,policy,{'Legal96_identity_hashes':[],'blocked_names':[],'blocked_hashes':[],'excluded_DEV_document_ids':sorted(set(all_ids)-set(x['document_id']for x in policy['all9_ranked_DEV_metadata']))},metadata,records,labels

def run_fixture(member,policy,audit,metadata,legacy=()):
 progress={};value=C.prepare_member(member,policy,'dev',list(legacy),audit,metadata,C.source_catalog(),progress)
 return value,progress

class CustodyFixtures(unittest.TestCase):
 def test_actual_DATA_and_GOLD_report_paths_use_current_epoch(self):
  tree=ast.parse((HERE/'e52_custody.py').read_text())
  for name in ('materialize','join_gold'):
   fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef)and x.name==name)
   report=next(x.value for x in ast.walk(fn)if isinstance(x,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='report_path'for t in x.targets))
   strings=[x.value for x in ast.walk(report)if isinstance(x,ast.Constant)and isinstance(x.value,str)]
   self.assertIn('experiments/sota-2026-10-22/audit/epoch52',strings)
   self.assertFalse(any('epoch51'in s for s in strings))
 def test_CURRENT_role_pool_excludes_all_E51_exposed_and_CF_is_reserved(self):
  self.assertEqual(POLICY['prior_epoch51_all_excluded_document_ids'],[7,28,406,73])
  self.assertTrue(set(C.DEV_DOCS).isdisjoint(POLICY['prior_epoch51_all_excluded_document_ids']))
  self.assertEqual(len(POLICY['all9_ranked_DEV_metadata']),9)
  self.assertTrue(all(not r['project_unused_unassigned_metadata_eligible']and r['exclusion_reasons']for r in POLICY['conditional_confirmation_documents']))
  self.assertFalse(POLICY['conditional_confirmation_newly_selected'])
  self.assertEqual(POLICY['confirmation_lineage_status'],'UNQUALIFIED_HOLD')
 def test_only_selected_values_decode_and_no_confirmation_body(self):
  member,policy,audit,metadata,records,labels=fixture();(bank,vault,identities,stats),progress=run_fixture(member,policy,audit,metadata)
  self.assertEqual([x['document_id']for x in bank['documents']],list(C.DEV_DOCS));self.assertEqual(len(bank['cases']),12)
  self.assertEqual(stats['semantic_gold_values_decoded'],0);self.assertEqual(stats['unselected_document_text_or_choice_decodes'],0)
  self.assertEqual(stats['value_decoder_counts']['selected_document'],4);self.assertEqual(stats['value_decoder_counts']['selected_hypothesis'],3)
  self.assertEqual(len(vault['opaque_raw_choice_tokens_base64']),12)
  self.assertTrue(set(C.CONF_DOCS).isdisjoint(x['document_id']for x in bank['documents']))
  self.assertEqual(progress['document_IDs_seen'],61)
 def test_choice_changes_never_change_model_features(self):
  a=fixture('OPAQUE_CHOICE_FIXTURE_A');b=fixture('OPAQUE_CHOICE_FIXTURE_B')
  (ba,va,_,_),_=run_fixture(*a[:4]);(bb,vb,_,_),_=run_fixture(*b[:4])
  self.assertEqual(C.canonical(ba),C.canonical(bb));self.assertNotEqual(C.canonical(va),C.canonical(vb))
 def test_selected_choice_is_never_semantically_json_decoded(self):
  f=fixture();original=C.json.loads;decoded=[]
  def track(value,*args,**kwargs):
   if isinstance(value,(bytes,str)):decoded.append(value.encode()if isinstance(value,str)else value)
   return original(value,*args,**kwargs)
  C.json.loads=track
  try:run_fixture(*f[:4])
  finally:C.json.loads=original
  self.assertFalse(any(b'OPAQUE_CHOICE_FIXTURE_A'in x for x in decoded))
  self.assertFalse(any(b'MUST_NOT_DECODE_TEXT'in x for x in decoded))
 def test_exact_source_partition_and_numeric_bytes(self):
  f=fixture();(bank,_,_,_),_=run_fixture(*f[:4])
  for d in bank['documents']:
   text=''.join(x['sentence']for x in d['evidence']);self.assertIn('3.14',text);self.assertIn('2026-10-26',text)
   self.assertEqual(C.sha(text.encode()),d['source_document_sha256']);self.assertEqual(C.sha(C.normalized(text).encode()),d['normalized_document_sha256'])
   self.assertEqual(d['evidence'][0]['start'],0);self.assertEqual(d['evidence'][-1]['end'],len(text))
 def test_selected_name_alias_rejects_before_text(self):
  m,p,a,metadata,records,labels=fixture();a['blocked_names']=[p['selected_dev_documents'][0]['document_filename_key_sha256']]
  with self.assertRaisesRegex(ValueError,'SOURCE_FILENAME_IDENTITY_OR_LEGAL96_ALIAS'):run_fixture(m,p,a,metadata)
 def test_exposed_substring_rejects_no_replacement(self):
  f=fixture()
  with self.assertRaisesRegex(ValueError,'EXPOSED_LEGAL96_SUBSTRING_ALIAS_NO_REPLACEMENT'):run_fixture(*f[:4],legacy=['quantity 3.14'])
 def test_duplicate_document_id_rejects(self):
  m,p,a,metadata,records,labels=fixture();records.append(records[0]);m=json.dumps({'labels':labels,'documents':records}).encode()
  with self.assertRaisesRegex(ValueError,'UNIQUE_DOCUMENT_IDS'):run_fixture(m,p,a,metadata)
 def test_missing_selected_document_rejects(self):
  m,p,a,metadata,records,labels=fixture();records=[r for r in records if r['id']!=C.DEV_DOCS[0]];m=json.dumps({'labels':labels,'documents':records}).encode()
  with self.assertRaisesRegex(ValueError,'EXACT_DEV_MEMBER_IDS_AND_SELECTED_FOUR'):run_fixture(m,p,a,metadata)
 def test_wrong_normalized_identity_rejects(self):
  m,p,a,metadata,records,labels=fixture();p['selected_dev_documents'][0]['normalized_document_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'SOURCE_DOCUMENT_IDENTITY_OR_PRIOR_ALIAS'):run_fixture(m,p,a,metadata)
 def test_metadata_original_dev_retirement_enforced(self):
  m,p,a,metadata,records,labels=fixture();a['excluded_DEV_document_ids'].append(C.DEV_DOCS[0])
  with self.assertRaisesRegex(ValueError,'ONLY_FROZEN_FRESH_SELECTED_DOCUMENTS'):run_fixture(m,p,a,metadata)
 def test_wrong_hypothesis_catalog_rejects(self):
  m,p,a,metadata,records,labels=fixture();labels.pop('nda-20');labels['nda-999']={'hypothesis':'Invented wrong key'};m=json.dumps({'labels':labels,'documents':records}).encode()
  with self.assertRaisesRegex(ValueError,'EXACT_17_HYPOTHESIS_CATALOG'):run_fixture(m,p,a,metadata)
 def test_selected_raw_choice_type_rejects_without_decode(self):
  m,p,a,metadata,records,labels=fixture();next(r for r in records if r['id']==C.DEV_DOCS[0])['annotation_sets'][0]['annotations']['nda-1']['choice']=4;m=json.dumps({'labels':labels,'documents':records}).encode()
  with self.assertRaisesRegex(ValueError,'OPAQUE_CHOICE_MUST_BE_STRING_TOKEN'):run_fixture(m,p,a,metadata)
 def test_semantic_gold_decoder_capability_absent_in_span_parser(self):
  s=C.SpanJSON(b'"OPAQUE_CHOICE_FIXTURE"')
  with self.assertRaisesRegex(ValueError,'FORBIDDEN_VALUE_DECODER'):s.decode_string(s.value(0),'choice')
  self.assertEqual(s.gold_values_decoded,0)
 def test_duplicate_json_field_and_bad_escape_reject(self):
  s=C.SpanJSON(b'{"id":1,"id":2}')
  with self.assertRaisesRegex(ValueError,'DUPLICATE_JSON_KEY'):s.members(s.value(0))
  with self.assertRaisesRegex(ValueError,'JSON_ESCAPE'):C.SpanJSON(b'"bad\\x"').value(0)
 def test_unqualified_physical_report_cannot_read_target_proc(self):
  with self.assertRaisesRegex(ValueError,'PHYSICAL_CLOSURE_REPORT_REQUIRED'):C.check_physical_closure({'schema_version':1,'epoch':52,'kind':C.KIND,'checks_passed':False},{})
 def test_original_policy_hash_and_roles_are_immutable(self):
  b=(HERE/'IDENTITY_POLICY.v2.json').read_bytes();r={'path':str(HERE/'IDENTITY_POLICY.v2.json'),'bytes':len(b),'sha256':C.sha(b)}
  C.verify_policy(POLICY,r);p=copy.deepcopy(POLICY);p['selected_dev_document_ids'][0]=72
  with self.assertRaisesRegex(ValueError,'FROZEN_IDENTITIES'):C.verify_policy(p,r)

 def test_CF_lineage_HOLD_rejects_before_any_file_or_archive_read(self):
  for action,args in [(C.materialize,(None,None,None,'confirmation')),(C.join_gold,(None,None,'confirmation')),(C.verify_data_admission,(None,None,'confirmation')),(C.verify_late_bundle,(None,None,'confirmation'))]:
   with self.assertRaisesRegex(ValueError,'CONFIRMATION_UNQUALIFIED_LINEAGE_HOLD_NO_ACCESS'):action(*args)
 def physical_fixture(self,windows=1):
  rows=[]
  for cid in C.phase_ids('dev'):
   for arm in C.ARMS:
    n=windows if arm=='whole_source'else 1
    row={'case_id':cid,'arm':arm,'model_forward_calls':n,'window_count':n}
    if arm=='whole_source':row.update(window_forecasts=[{}for _ in range(n)],evidence={'aggregation':{'all_window_count':n}})
    rows.append(row)
  n=36+12*windows
  return {'rows':rows,'expected_physical_forwards':n,'counters':{'forecasts_completed':48,'NLI_forwards_attempted':n,'NLI_forwards_completed':n}}
 def test_variable_physical_counts_include_each_whole_source_window(self):
  self.assertEqual(C.verify_forecast_work_counts(self.physical_fixture(1)),48)
  self.assertEqual(C.verify_forecast_work_counts(self.physical_fixture(16)),228)
  self.assertEqual(C.verify_forecast_work_counts(self.physical_fixture(7)),120)
 def test_out_of_budget_or_incomplete_window_counts_reject(self):
  with self.assertRaisesRegex(ValueError,'COMPLETE_WHOLE_SOURCE_WINDOW_COUNT'):C.verify_forecast_work_counts(self.physical_fixture(17))
  raw=self.physical_fixture(2);raw['rows'][3]['window_forecasts'].pop()
  with self.assertRaisesRegex(ValueError,'COMPLETE_WHOLE_SOURCE_WINDOW_COUNT'):C.verify_forecast_work_counts(raw)
 def test_physical_success_must_match_actual_expected_and_perrow_counts(self):
  raw=self.physical_fixture(3);raw['counters']['NLI_forwards_completed']-=1
  with self.assertRaisesRegex(ValueError,'EXACT_VARIABLE_PHYSICAL_FORWARD_COUNTS'):C.verify_forecast_work_counts(raw)
  raw=self.physical_fixture(3);raw['rows'][3]['model_forward_calls']=1
  with self.assertRaisesRegex(ValueError,'PER_FORECAST_PHYSICAL_FORWARD_COUNT'):C.verify_forecast_work_counts(raw)

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(CustodyFixtures);result=unittest.TextTestRunner(verbosity=1).run(suite)
 print(json.dumps({'scope':'INVENTED_NONBENCHMARK_CUSTODY_FIXTURES_ONLY','testsRun':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'real_source_archive_reads':0,'real_case_or_choice_decodes':0,'model_tokenizer_native_or_Git_calls':0},sort_keys=True))
 raise SystemExit(0 if result.wasSuccessful()else 1)
