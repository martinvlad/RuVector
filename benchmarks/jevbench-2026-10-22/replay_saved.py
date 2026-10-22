"""Stdlib-only replay of selected saved wire bytes and original official scoring.

No HTTP, native/model execution, installation, weights, API credentials, or paid
calls occur. Public expected labels are used only in this evaluation-only reader.
"""
import argparse,hashlib,importlib.util,json
from pathlib import Path,PurePosixPath
import sys
from types import ModuleType
from unittest.mock import patch
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
D=ROOT/'experiments/submission-2026-10-22/jevbench/round2-v2'
A=ROOT/'experiments/swarm/jevbench-adapter/sources'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path);args=parser.parse_args()
 manifest=load(ROOT/'PUBLIC_MANIFEST.json');assert manifest['official_rank'] is None
 for row in manifest['files']:
  rel=PurePosixPath(row['path']);assert not rel.is_absolute() and '..' not in rel.parts
  path=ROOT/row['path'];assert path.is_file() and not path.is_symlink() and path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],row['path']
 plan=load(D/'plan.json');runtime=load(ROOT/'experiments/submission-2026-10-22/jevbench/runtime-manifest.json')
 for rel,h in plan['source_sha256'].items():assert sha(ROOT/rel)==h,rel
 assert sha(D/'plan.json')==runtime['selected_plan']['sha256']
 pkg=ModuleType('portable_jev');pkg.__path__=[];sys.modules[pkg.__name__]=pkg
 sub=ModuleType('portable_jev.adapters');sub.__path__=[];sys.modules[sub.__name__]=sub
 m={name:module('portable_jev.'+name,A/('jevbench_'+name.replace('.','_')+'.py')) for name in ['tasks','scoring','adapters.base','adapters.typesafe']}
 records=[]
 for cohort in ['original','hard']:
  p=ROOT/'data/jevbench'/(cohort+'.jsonl');assert sha(p)==plan['input_files'][str(p.relative_to(ROOT))]
  items=[m['tasks'].Task.from_dict(json.loads(line)) for line in p.read_text().splitlines()]
  assert [t.id for t in items]==plan['ids'][cohort]
  records.extend((cohort,t) for t in items)
 assert len(records)==183
 refs=[json.loads(line) for line in (ROOT/'saved-score-reference.jsonl').read_text().splitlines()]
 assert [r['id'] for r in refs]==[t.id for _,t in records]
 wire=load(D/'wire-index.json');assert len(wire)==184 and sum(bool(r['warmup']) for r in wire)==1 and wire[0]['warmup']
 engine=module('portable_engine',ROOT/'experiments/submission-2026-10-22/jevbench/engine.py')
 rules=module('portable_rules',D/'rules.py')
 counts={c:{'n':0,'correct':0,'native_correct':0,'baseline100_correct':0,'strict_valid':0} for c in ['original','hard']}
 score_calls=0;gains=0;losses=0;new_relations=0
 def probabilities(answer,task):
  if task.question['type']=='noul':return {'yes':answer['noul'],'no':1-answer['noul']}
  return answer['probabilities']
 for i,row in enumerate(wire):
  index=0 if row['warmup'] else i-1;cohort,task=records[index];assert row['task_id']==task.id
  parts=[]
  for field in ['request','response']:
   rec=row[field];path=ROOT/rec['path'];raw=path.read_bytes();assert len(raw)==rec['bytes'] and sha(path)==rec['sha256']
   head,body=raw.split(b'\r\n\r\n',1);parts.append((head,json.loads(body)))
  request_head,request=parts[0];response_head,response=parts[1]
  assert request_head.startswith(b'POST /v1/systemone HTTP/') and response_head.startswith(b'HTTP/1.0 200')
  adapter=m['adapters.typesafe'].TypeSafeAdapter(endpoint='http://saved.invalid',model=runtime['candidate_id'],key_env='')
  assert request==adapter.build_request(task)
  def saved_reply(url,body,headers,timeout):
   assert url=='http://saved.invalid/v1/systemone' and body==request
   return 200,response,0.0
  with patch.object(m['adapters.typesafe'],'http_post_json',saved_reply):result=adapter.run(task)
  assert result.ok and result.model==runtime['candidate_id']
  answer=response['answers']['decision'];native=answer['native_original_answer'];baseline=answer['baseline100_answer']
  score=m['scoring'].score_task(result.probs,task);old=m['scoring'].score_task(probabilities(baseline,task),task);original=m['scoring'].score_task(probabilities(native,task),task);score_calls+=3
  assert score['strict_valid'] and old['strict_valid'] and original['strict_valid'] and not score['renormalized']
  state,questions=engine.server.validate_request(request);q=questions['decision'];proof=rules.solve(state,q)
  computed=engine.apply_proof(native,q,proof);base=engine.apply_proof(native,q,rules.baseline_proof(state,q))
  computed.update(native_original_answer=native,baseline100_answer=base,native_fallback_used=proof is None)
  assert computed==answer,task.id
  if row['warmup']:continue
  ref=refs[index];assert score==ref['official_score'] and row['request']['sha256']==ref['request_sha256'] and row['response']['sha256']==ref['response_sha256']
  c=counts[cohort];c['n']+=1;c['correct']+=bool(score['correct']);c['native_correct']+=bool(original['correct']);c['baseline100_correct']+=bool(old['correct']);c['strict_valid']+=bool(score['strict_valid'])
  gains+=bool(score['correct'] and not old['correct']);losses+=bool(old['correct'] and not score['correct'])
  new_relations+=bool(proof is not None and proof['rule']=='explicit_typed_relation_join')
 total={key:sum(c[key] for c in counts.values()) for key in counts['original']}
 assert total=={'n':183,'correct':104,'native_correct':77,'baseline100_correct':100,'strict_valid':183}
 assert counts['original']['correct']==56 and counts['hard']['correct']==48 and gains==4 and losses==0 and new_relations==4
 results=load(D/'results.json');assert results['metrics']['all']['correct']==104 and results['metrics']['all']['errors']==0
 out={'status':'passed','public_manifest_files_rehashed':len(manifest['files']),'selected_source_files_rehashed':len(plan['source_sha256']),'literal_HTTP_pairs':184,'official_original_adapter_saved_response_calls':184,'official_original_score_calls':score_calls,'candidate_native77_baseline100_score_calls_each':184,'pure_solver_answer_construction_replayed':184,'n':183,'correct':104,'accuracy':104/183,'original_correct':56,'hard_correct':48,'strict_valid':183,'errors':0,'gains_vs100':gains,'regressions_vs100':losses,'new_relation_proofs':new_relations,'new_HTTP_native_model_API_paid_calls':0,'scope':'Observed public183 development; saved bytes and pure scoring/rules only, not physical native/model replay or matching official sealed evaluation','official_rank':None,'official_Capability':None}
 if args.out:args.out.write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps(out,indent=2))

if __name__=='__main__':main()
