"""Saved-output postrun replay plus independent character-set intersection oracle."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,importlib.util,json,math,os,statistics,subprocess,sys
O=Path(__file__).resolve().parent;S=O.parents[1];C=S/'candidate/epoch13/postrun';ROOT=S.parents[1]
def obj(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def module(p,n):
 spec=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def canon(v):return json.dumps(v,indent=2,allow_nan=False)+'\n'
allow=obj(C/'public-allowlist-v1.json')
for pin in allow['files']:
 p=ROOT/pin['path'];assert p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256'],pin['path']
records_path=S/'epoch13/runs/development/records.jsonl';records=[json.loads(x)for x in records_path.read_text().splitlines()];projection=obj(O/'dev-annotation-spans-v1.json');assert len(records)==len(projection['records'])==24 and not projection['reserved_confirmation_annotations_accessed']
d=module(C/'build_diagnostic_v1.py','e13_saved_diagnostic');rebuilt=d.analyze(records);rebuilt.update(saved_records_sha256=sha(records_path),frozen_candidate_manifest_sha256=d.CANDIDATE_SHA,scope='Pure terminal saved DEV24 analysis only; no CONF/full-source/model/native access.')
assert canon(rebuilt)==(C/'diagnostic-v1.json').read_text()
c=module(C/'build_reference_coverage_v1.py','e13_saved_reference');coverage=c.analyze(records,projection);coverage.update(saved_records_sha256=sha(records_path),DEV_only_projection_sha256=sha(O/'dev-annotation-spans-v1.json'));assert canon(coverage)==(C/'reference-coverage-v1.json').read_text()
f=module(C/'build_findings_v1.py','e13_saved_findings');assert canon(f.build(C/'diagnostic-v1.json',O/'actual-independent-v1.json'))==(C/'findings-v1.json').read_text()
f2=module(C/'build_findings_v2.py','e13_saved_findings2');assert canon(f2.build(C/'findings-v1.json',C/'reference-coverage-v1.json'))==(C/'findings-v2.json').read_text()
# An independent oracle uses source character index sets, not the candidate's interval union implementation.
refs={x['id']:x for x in projection['records']};saved={(x['id'],x['arm']):x for x in coverage['examples']};arms={'ruvector_top2':'ruvector_top2','same_nli_lexical_top2':'lexical_top2','same_nli_positional_first2':'positional_first2'};independent={}
for name,alias in arms.items():
 values=[];typedcounts=Counter();goldcounts=Counter();confusion={g:Counter()for g in ['Entailment','Contradiction','NotMentioned']};numbers=keptnumbers=0
 for r in records:
  ref=refs[r['id']];a=r['response']['diagnostics']['decision']['arms'][alias];state=r['input']['state'];reference=set();selected=set()
  for lo,hi in ref['original_gold_character_spans']:assert 0<=lo<hi<=len(state);reference.update(range(lo,hi))
  for lo,hi in a['coverage']['selected_source_spans']:assert 0<=lo<hi<=len(state);selected.update(range(lo,hi))
  retained=len(reference&selected);total=len(reference);full=bool(reference) and reference<=selected
  old=saved[(r['id'],name)];assert old['reference_union_characters']==total and old['retained_reference_union_characters']==retained and old['all_reference_characters_retained']==full and old['any_span_overlap']==bool(reference&selected)
  assert old['every_span_overlap']==(bool(reference) and all(bool(set(range(lo,hi))&selected)for lo,hi in ref['original_gold_character_spans']))
  probs=a['decoding']['raw_threeway_probabilities'];pred=min(probs,key=lambda k:(-probs[k],k));gold=r['evaluation']['original_threeway_label'];typedcounts[pred]+=1;goldcounts[gold]+=1;confusion[gold][pred]+=1;values.append({'full':full,'typed_correct':pred==gold,'gold':gold,'hasref':bool(reference),'binary_correct':old['binary_correct']})
  numbers+=len(a['coverage']['numeric_mentions']);keptnumbers+=sum(x['retained']for x in a['coverage']['numeric_mentions'])
 full=[x for x in values if x['full']];own={'queries':24,'reference_bearing':sum(x['hasref']for x in values),'full_reference_characters':len(full),'fully_retained_typed_correct':sum(x['typed_correct']for x in full),'fully_retained_binary_correct':sum(x['binary_correct']for x in full),'fully_retained_gold_counts':dict(Counter(x['gold']for x in full)),'typed_predicted_counts':dict(typedcounts),'gold_counts':dict(goldcounts),'gold_to_typed_prediction':{k:dict(v)for k,v in confusion.items()},'numeric_positions_per_query':numbers,'retained_numeric_positions_per_query':keptnumbers};independent[name]=own
 reported=coverage['summary'][name];assert reported['all_reference_characters_retained_n']==own['full_reference_characters'] and reported['fully_retained_typed_correct_n']==own['fully_retained_typed_correct'] and reported['fully_retained_binary_correct_n']==own['fully_retained_binary_correct']
 assert rebuilt['arms'][name]['typed_predicted_counts']==own['typed_predicted_counts'] and rebuilt['arms'][name]['source_retention']['numeric_positions_per_query']==numbers and rebuilt['arms'][name]['source_retention']['numeric_retained_per_query']==keptnumbers
assert independent['ruvector_top2']['fully_retained_typed_correct']==0 and independent['ruvector_top2']['full_reference_characters']==9
r=subprocess.run([sys.executable,'-B',str(C/'test_diagnostic_v1.py')],capture_output=True,text=True,timeout=30,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'));assert r.returncode==0,(r.stdout,r.stderr)
datareport=S/'legal-transfer/epoch13/postrun/dev-annotation-spans-independent-v1.json'
reports=list((S/'legal-transfer/epoch13/postrun').glob('*.json'));validation=[p for p in reports if obj(p).get('checks_passed')is True or obj(p).get('all_checks_passed')is True]
result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'candidate_public_allowlist_sha256':sha(C/'public-allowlist-v1.json'),'diagnostic_sha256':sha(C/'diagnostic-v1.json'),'findings_v1_sha256':sha(C/'findings-v1.json'),'reference_coverage_sha256':sha(C/'reference-coverage-v1.json'),'findings_v2_sha256':sha(C/'findings-v2.json'),'exact_rebuild_all4_candidate_outputs_byteidentical':True,'independent_source_character_set_oracle_rows':72,'independent_summary':independent,'engineering_tests':{'source_sha256':sha(C/'test_diagnostic_v1.py'),'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr},'data_independent_report_pins':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)}for p in validation],'direction':'Reader/task decision semantics remains a live blocker even on9native/9lexical/7positional queries with every annotated reference character retained: typed0correct. Full references may be alternative or incomplete and do not prove sufficient evidence. Native retrieval improves no exclusive binarycorrect over either matchedselector; exactANN validates implementation, not semantic evidence quality. Future separatelyfrozen/bounded task-specific semantics+evidence study may use exposedTRAIN/DEV only; no reservedCONF design/labels or extra probes.','proper_scope':'Candidate supplemental Pythonfloat-normalized proper diagnostics may differ by tiny massrounding; frozen canonical actualaudit governs all acceptance/table. No gate/model/data/source changes.','new_model_native_session_fit_paid_or_externalwrite_calls':0,'confirmation_labels_or_annotations_accessed':False,'official_rank':None,'SOTA_established':False}
out=O/'postrun-independent-v1.json'
with out.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(out),'native':independent['ruvector_top2']}))
