import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import typed_relations as r


def admissions():
 return {'admission_table':{'C901':'score 91; prerequisite MTH-7 within 9 months^z'},'application':{'applicant_track':'alumni student','course_alias':'VEGA','prerequisite':'MTH-Q completed 15 months ago','score':79},'catalog':{'VEGA':'course C901, accelerated section'},'equivalencies':{'MTH-Q':'MTH-7'},'footnotes':{'z':'For RX applicants to an accelerated section, score threshold is 78 and prerequisite recency is 21 months if prior grade was B or higher.'},'sequence':'Resolve course and track aliases, equivalency, section qualifier, then footnote.','track_codes':{'alumni student':'RX'},'transcript':{'MTH-Q grade':'B'}}

def incident():
 return {'asset_catalog':{'DawnLink':'DL-8'},'clock_rule':'Elapsed minutes use detection to completed containment.','footnotes':{'R':'For assets owned by a Q9 team, exposure fully contained within 12 minutes with no observed access is S4.'},'incident':{'asset_name':'DawnLink','containment':'17:20','data_access':'none observed','date':'2028-03-14','detected':'17:10','event':'credential exposure in machine log'},'ownership':{'DL-8':'infra-west'},'routing':{'S1':'executive','S2':'operations primary','S4':'owning queue'},'severity_matrix':{'availability_only':'S3','credential_exposure':'S2 unless footnote R','data_exfiltration':'S1'},'team_aliases':{'Kite':'operations response queue Q9','infra-west':'Team Kite beginning 15 March 2028; before then it is not a Q9 team'}}

def maintenance():
 return {'asset_map':{'Moth':'press P88, generation G9'},'bypass_log':{'approved':True,'duration_minutes':8,'restored_safe_operation':True},'calculation_rule':"Subtract only qualifying bypass duration before comparing 'under 27'; exactly 27 is not under.",'fault_map':{'F-BLUE':'optical occlusion, class M'},'footnotes':{'*':'For G9 presses on night shift, approved bypass time is excluded from downtime when bypass restores safe operation.'},'maintenance':{'downtime_minutes':35,'fault_code':'F-BLUE','machine_alias':'Moth','shift':'night','temporary_bypass':True},'response_table':{'class_M':'local maintenance if under 27 minutes; central engineering otherwise*'}}

A={'type':'choice','instructions':'Apply the supplied current records.','criteria':{'E9':'All adjusted requirements are met.','X1':'Applicable prerequisite or recency fails.','K4':'Applicable score threshold is missed.','G1':'No supplied mapping resolves the prerequisite.'}}
I={'type':'choice','instructions':'Apply the supplied current records.','criteria':{'P9':'Severity S2 routing.','Z2':'Severity S4 owned by Kite/Q9.','B8':'Required mapping or timing is absent.'}}
M={'type':'choice','instructions':'Apply the supplied current records.','criteria':{'C7':'Adjusted downtime is at least 27 minutes.','W2':'Adjusted downtime is under 27 minutes.','S5':'Bypass did not restore safe operation.'}}

def access():
 return {'access_matrix':{'jade':{'K7':'aggregate only, maximum 21 days^4'}},'amendment':'Revision 13 removed region code from the granular list and placed it on non-granular; revision 13 is current.','data_request':{'dataset':'ALBATROSS','fields':['weekly totals','region code'],'purpose':'summary analysis','requester_group':'research affiliates','retention_days':42},'dataset_registry':{'ALBATROSS':'collection D91, sensitivity tier jade'},'footnotes':{'4':'K7 maximum is 75 days for purpose code MET when fields pass the non-granular list.'},'group_aliases':{'research affiliates':'visiting class K7'},'non_granular':['weekly totals','region code','category code'],'purpose_codes':{'summary analysis':'MET'}}
D={'type':'choice','instructions':'Trace the supplied current records.','criteria':{'X5':'Exception permits the requested fields and duration.','N4':'Only default duration applies.','R8':'At least one field lacks classification.','Y1':'Requester class cannot access this tier.'}}

class Tests(unittest.TestCase):
 def run_case(self,record,question,expected):
  text=json.dumps(record,ensure_ascii=False,separators=(',',':'));answer=r.solve(text,question)
  if expected is None:self.assertIsNone(answer);return
  self.assertEqual(answer['decision'],expected);self.assertFalse(answer['archive_used']);self.assertGreaterEqual(len(answer['trace']),3)
  for fact in answer['source_facts']:
   self.assertNotEqual(fact['path'][0],'archive');start,end=fact['span'];self.assertEqual(text[start:end],fact['text']);self.assertEqual(json.loads(fact['text']),fact['value'])
   v=record
   for key in fact['path']:v=v[key]
   self.assertEqual(v,fact['value'])
 def test_admission_changed_entities_and_labels(self):self.run_case(admissions(),A,'E9')
 def test_admission_counterfactual_score(self):v=admissions();v['application']['score']=77;self.run_case(v,A,'K4')
 def test_admission_boundary_score(self):v=admissions();v['application']['score']=78;self.run_case(v,A,'E9')
 def test_admission_counterfactual_recency(self):v=admissions();v['application']['prerequisite']='MTH-Q completed 22 months ago';self.run_case(v,A,'X1')
 def test_admission_boundary_recency(self):v=admissions();v['application']['prerequisite']='MTH-Q completed 21 months ago';self.run_case(v,A,'E9')
 def test_admission_low_grade_both_fail_abstains(self):v=admissions();v['transcript']['MTH-Q grade']='C';self.run_case(v,A,None)
 def test_admission_low_grade_base_score_pass(self):v=admissions();v['transcript']['MTH-Q grade']='C';v['application']['score']=95;self.run_case(v,A,'X1')
 def test_admission_qualifying_high_grade(self):v=admissions();v['transcript']['MTH-Q grade']='A';self.run_case(v,A,'E9')
 def test_admission_missing_link(self):v=admissions();v['equivalencies']={};self.run_case(v,A,None)
 def test_admission_unknown_grade(self):v=admissions();v['transcript']['MTH-Q grade']='pass';self.run_case(v,A,None)
 def test_admission_conflicting_sequence(self):v=admissions();v['sequence']='Use historical defaults before the footnote.';self.run_case(v,A,None)
 def test_admission_extra_operative_rule(self):v=admissions();v['new_override']='All applications denied.';self.run_case(v,A,None)
 def test_admission_duplicate_label_abstains(self):q=copy.deepcopy(A);q['criteria']['extra']=q['criteria']['E9'];self.run_case(admissions(),q,None)
 def test_incident_before_effective_date(self):self.run_case(incident(),I,'P9')
 def test_incident_effective_boundary(self):v=incident();v['incident']['date']='2028-03-15';self.run_case(v,I,'Z2')
 def test_incident_after_effective_date(self):v=incident();v['incident']['date']='2028-04-01';self.run_case(v,I,'Z2')
 def test_incident_duration_boundary(self):v=incident();v['incident'].update(date='2028-03-15',containment='17:22');self.run_case(v,I,'Z2')
 def test_incident_duration_exceeds(self):v=incident();v['incident'].update(date='2028-03-15',containment='17:23');self.run_case(v,I,'P9')
 def test_incident_observed_access(self):v=incident();v['incident'].update(date='2028-03-15',data_access='observed access');self.run_case(v,I,'P9')
 def test_incident_missing_asset(self):v=incident();v['asset_catalog']={};self.run_case(v,I,None)
 def test_incident_clock_inconsistent(self):v=incident();v['clock_rule']='Elapsed minutes use mitigation start.';self.run_case(v,I,None)
 def test_incident_overnight_unknown(self):v=incident();v['incident']['containment']='00:10';self.run_case(v,I,None)
 def test_incident_ambiguous_unknown_access(self):v=incident();v['incident']['data_access']='not sure';self.run_case(v,I,None)
 def test_incident_conflicting_queue(self):v=incident();v['team_aliases']['Kite']='operations response queue Q7';self.run_case(v,I,None)
 def test_incident_alias_cycle_unsupported(self):v=incident();v['team_aliases']['infra-west']='Kite';self.run_case(v,I,None)
 def test_incident_unknown_effective_date(self):v=incident();v['team_aliases']['infra-west']='Team Kite beginning soon; before then it is not a Q9 team';self.run_case(v,I,None)
 def test_maintenance_strict_boundary(self):self.run_case(maintenance(),M,'C7')
 def test_maintenance_under_boundary(self):v=maintenance();v['maintenance']['downtime_minutes']=34;self.run_case(v,M,'W2')
 def test_maintenance_unapproved_duration_excluded(self):v=maintenance();v['bypass_log']['approved']=False;self.run_case(v,M,'C7')
 def test_maintenance_other_generation_no_exclusion(self):v=maintenance();v['asset_map']['Moth']='press P88, generation G8';self.run_case(v,M,'C7')
 def test_maintenance_other_shift_no_exclusion(self):v=maintenance();v['maintenance']['shift']='day';self.run_case(v,M,'C7')
 def test_maintenance_unsafe_operation_abstain(self):v=maintenance();v['bypass_log']['restored_safe_operation']=False;self.run_case(v,M,None)
 def test_maintenance_missing_fault_map(self):v=maintenance();v['fault_map']={};self.run_case(v,M,None)
 def test_maintenance_inconsistent_rule_threshold(self):v=maintenance();v['calculation_rule']=v['calculation_rule'].replace('27','26');self.run_case(v,M,None)
 def test_maintenance_impossible_duration(self):v=maintenance();v['bypass_log']['duration_minutes']=36;self.run_case(v,M,None)
 def test_maintenance_boolean_numeric_confusion(self):v=maintenance();v['bypass_log']['approved']=1;self.run_case(v,M,None)
 def test_reordered_edges_and_unicode(self):v=incident();v['incident']['date']='2028-03-15';v['archive']=[{'description':'outdated ❄ table','team':'wrong'}];v=dict(reversed(list(v.items())));self.run_case(v,I,'Z2')
 def test_archived_alias_collision_does_not_supply_edge(self):v=incident();v['archive']=[{'asset_catalog':{'DawnLink':'OTHER'}}];self.run_case(v,I,'P9')
 def test_duplicate_json_key_abstains(self):self.assertIsNone(r.solve('{"application":{},"application":{}}',A))
 def test_malformed_json_abstains(self):self.assertIsNone(r.solve('{broken',A))
 def test_score_question_unsupported(self):q=copy.deepcopy(A);q['type']='score';self.run_case(admissions(),q,None)
 def test_no_runtime_file_or_network_import(self):src=Path(r.__file__).read_text();self.assertNotIn('import pathlib',src);self.assertNotIn('import requests',src);self.assertNotIn('open(',src)

 def test_decimal_float_boundary_exact(self):
  v=maintenance();v['maintenance']['downtime_minutes']=2.3;v['bypass_log']['duration_minutes']=0.3;v['response_table']['class_M']='local maintenance if under 2 minutes; central engineering otherwise*';v['calculation_rule']="Subtract only qualifying bypass duration before comparing 'under 2'; exactly 2 is not under."
  q=copy.deepcopy(M);q['criteria']={k:value.replace('27','2') for k,value in q['criteria'].items()};self.run_case(v,q,'C7')
 def test_decimal_noninteger_under(self):
  v=maintenance();v['maintenance']['downtime_minutes']=2.29;v['bypass_log']['duration_minutes']=0.3;v['response_table']['class_M']='local maintenance if under 2 minutes; central engineering otherwise*';v['calculation_rule']="Subtract only qualifying bypass duration before comparing 'under 2'; exactly 2 is not under."
  q=copy.deepcopy(M);q['criteria']={k:value.replace('27','2') for k,value in q['criteria'].items()};self.run_case(v,q,'W2')
 def test_access_novel_entities_thresholds_labels(self):self.run_case(access(),D,'X5')
 def test_access_exact_exception_boundary(self):v=access();v['data_request']['retention_days']=75;self.run_case(v,D,'X5')
 def test_access_over_exception_abstains(self):v=access();v['data_request']['retention_days']=76;self.run_case(v,D,None)
 def test_access_nonmatching_purpose_default(self):v=access();v['purpose_codes']['summary analysis']='OTHER';v['data_request']['retention_days']=20;self.run_case(v,D,'N4')
 def test_access_nonmatching_purpose_exceeds_default(self):v=access();v['purpose_codes']['summary analysis']='OTHER';self.run_case(v,D,None)
 def test_access_missing_classification_abstains(self):v=access();v['data_request']['fields'].append('individual record');self.run_case(v,D,None)
 def test_access_missing_dataset_mapping_abstains(self):v=access();v['dataset_registry']={};self.run_case(v,D,None)
 def test_access_missing_group_mapping_abstains(self):v=access();v['group_aliases']={};self.run_case(v,D,None)
 def test_access_wrong_class_footnote_abstains(self):v=access();v['footnotes']['4']=v['footnotes']['4'].replace('K7','K8');self.run_case(v,D,None)
 def test_access_conflicting_current_amendment_abstains(self):v=access();v['amendment']=v['amendment'].replace('region code','postal sector');self.run_case(v,D,None)
 def test_access_mismatched_revision_abstains(self):v=access();v['amendment']=v['amendment'].replace('revision 13 is','revision 12 is');self.run_case(v,D,None)
 def test_access_duplicate_requested_fields_abstains(self):v=access();v['data_request']['fields'].append('region code');self.run_case(v,D,None)
 def test_access_archive_not_live(self):v=access();v['archive']=[{'non_granular':['individual record'],'retention_days':365}];self.run_case(v,D,'X5')
 def test_access_reordered_mapping_edges(self):v=access();v=dict(reversed(list(v.items())));v['non_granular'].reverse();self.run_case(v,D,'X5')
 def test_access_unknown_operative_rule_abstains(self):v=access();v['new_override']='No access allowed.';self.run_case(v,D,None)

 def test_fraction_tiny_positive_bypass_strict_boundary(self):
  v=maintenance();v['maintenance']['downtime_minutes']=2;v['bypass_log']['duration_minutes']=1e-100;v['response_table']['class_M']='local maintenance if under 2 minutes; central engineering otherwise*';v['calculation_rule']="Subtract only qualifying bypass duration before comparing 'under 2'; exactly 2 is not under."
  q=copy.deepcopy(M);q['criteria']={k:value.replace('27','2') for k,value in q['criteria'].items()};self.run_case(v,q,'W2')
 def test_admission_unknown_nested_rule_abstains(self):v=admissions();v['application']['mandatory_override']='deny';self.run_case(v,A,None)
 def test_incident_unknown_nested_rule_abstains(self):v=incident();v['incident']['alternate_clock']='response start';self.run_case(v,I,None)
 def test_maintenance_unknown_nested_rule_abstains(self):v=maintenance();v['maintenance']['new_override']='ignore bypass';self.run_case(v,M,None)
 def test_access_unknown_nested_rule_abstains(self):v=access();v['data_request']['competing_purpose']='individual audit';self.run_case(v,D,None)

 def test_explicitly_nonbinding_memo_supported(self):v=incident();v['memo']='A draft summary calling this S1 predates the ownership renaming and is nonbinding.';self.run_case(v,I,'P9')
 def test_binding_emergency_memo_abstains(self):v=incident();v['memo']='An emergency order requires severity S1 for this asset.';self.run_case(v,I,None)
 def test_ambiguous_memo_abstains(self):v=incident();v['memo']='Use the revised severity policy.';self.run_case(v,I,None)

if __name__=='__main__':unittest.main()
