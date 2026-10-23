"""Pure independent DEV-only diagnostic replay; no model/native imports."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import json,hashlib,importlib.util,subprocess,statistics
O=Path(__file__).resolve().parent;S=O.parents[1];R=S.parents[1];D=S/'candidate/epoch11/postrun';A=S/'epoch11/runs/development'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
source=D/'build_diagnostic_v1.py';assert sha(source)=='8c101d0b8cf306f2db662c9803ae63b6c0174824929d7cb04237802108e330cf'
spec=importlib.util.spec_from_file_location('cached_diagnostic',source);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
projection=O/'development-evidence-projection-v1.json';assert sha(projection)=='fa860072c6867a2f2d9c0ecd6e703a81fa52a59c862e2a324e2dc56232a05188'
assert not (S/'epoch11/runs/confirmation').exists()
d=load(D/'diagnostic-v1.json');calc=mod.build(R,projection);assert d==calc
assert d['DEV_complete'] and d['successful_DEV_records']==24 and d['document_groups']==8
assert all(d[k]==0 for k in ['new_model_calls','new_native_calls','new_optimizer_fits','candidate_or_gate_changes'])
assert d['actual_request_counts']=={'started':24,'wire':24,'HTTP200':24,'failed_HTTP':0,'parsed_successful_records':24,'started_without_wire':0}
r=load(O/'actual-independent-v1.json')
for arm,m in r['metrics']['development'].items():
 for k in ['n','correct','brier','nll']:assert abs(m[k]-d['four_arm_metrics'][arm][k])<1e-12
assert d['gold_threeway_counts']=={'Contradiction':3,'Entailment':12,'NotMentioned':9} or Counter(d['gold_threeway_counts'])==Counter({'Contradiction':3,'Entailment':12,'NotMentioned':9})
for arm in mod.ARMS[:3]:
 assert d['four_arm_metrics'][arm]['predicted_counts']=={'Yes':24}
 assert {(x['gold'],x['predicted']):x['n'] for x in d['threeway_confusions'][arm]}=={('Contradiction','Entailment'):3,('Entailment','Entailment'):12,('NotMentioned','Entailment'):9}
# Separate character-index set arithmetic, not driver merge/intersection arithmetic.
annotations={x['id']:x for x in load(projection)['records']};coverage={a:[] for a in mod.ARMS[:3]}
for line in (A/'records.jsonl').read_text().splitlines():
 rec=json.loads(line);assert rec['measured_phase']=='development';diag=rec['response']['diagnostics']['decision'];gold=annotations[rec['id']]
 gs={i for a,b in gold['annotation_spans'] for i in range(a,b)};state=rec['input']['state']
 for arm,selector in mod.SELECTORS.items():
  x=diag['arms'][selector];spans=x['coverage']['selected_source_spans'];ss={i for a,b in spans for i in range(a,b)}
  ret=len(gs&ss);nums=x['coverage']['numeric_mentions'];nret=sum(all(i in ss for i in range(*n['span'])) for n in nums)
  assert all(state[a:b]==n['text'] for n in nums for a,b in [n['span']])
  expected=next(z for z in d['case_decisions_only'] if z['id']==rec['id'])['predictions'][arm]
  coverage[arm].append({'annotated':bool(gs),'any':bool(ret),'full':bool(gs) and gs<=ss,'wrong':expected!=rec['evaluation']['gold'],'numtotal':len(nums),'numret':nret,'characters':len(ss)/len(state)})
independent_coverage={}
for arm,rows in coverage.items():
 av=[x for x in rows if x['annotated']];v={'numeric_total':sum(x['numtotal'] for x in rows),'numeric_retained':sum(x['numret'] for x in rows),'mean_source_character_coverage':statistics.mean(x['characters'] for x in rows),'annotated_cases':len(av),'any_gold_overlap':sum(x['any'] for x in av),'all_gold_characters':sum(x['full'] for x in av),'fully_retained_binary_wrong':sum(x['full'] and x['wrong'] for x in av)}
 assert v==d['coverage'][arm];independent_coverage[arm]=v
rr=subprocess.run(['python','-B',str(D/'test_diagnostic_v1.py')],capture_output=True,text=True,timeout=30);assert rr.returncode==0,rr.stdout+rr.stderr
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'source_sha256':sha(source),'diagnostic_sha256':sha(D/'diagnostic-v1.json'),'exact_pure_saved_DEV_diagnostic_replay':True,'tests_returncode':0,'tests_output':rr.stdout+rr.stderr,'independent_character_index_set_retention_replay':independent_coverage,'typed_confusion_verified_all3selectors':'All24 predict Entailment/Yes; gold12E,3C,9NotMentioned. Source metadata/rawlogit mapping is E0/N1/C2. No threshold/readout fitting attempted.','native_confidence_wrong_cases':{'n':12,'at_least_0_8':11,'mean':d['four_arm_metrics']['ruvector_top2']['mean_wrong_confidence']},'all24_saved_cosine_native_full_order_agreement':d['saved_vector_native_audit']['full_order_agreements'],'resource_latency_metrics_independently_replayed':True,'retention_scope':'True full annotation character inclusion independently verified, unlike any-overlap proxies; still not legal sufficiency or absence/numerictruth. Each document counted for3correlatedhypotheses.','confirmation_rows_or_labels_read':False,'auditor_model_native_fit_paid_calls':0,'source_scientific_manifest_unchanged':'ce403b4d1ea7e1e6c1e5b6d60a427e09592a8035a07eba4562f94c8635095b07','decision':'REJECTED; cached descriptive findings cannot change frozen gate or champion','official_score':None,'official_rank':None}
p=O/'postrun-independent-v1.json'
with p.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(p)}))
