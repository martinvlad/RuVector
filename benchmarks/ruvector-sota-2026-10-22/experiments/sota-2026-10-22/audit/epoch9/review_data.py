"""Independent source/group/draw/label verification. No model execution."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,zipfile

O=Path(__file__).resolve().parent;S=O.parents[1];D=S/'legal-transfer/epoch9'
def obj(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def norm(x):return ' '.join(x.casefold().split())
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def textsha(x):return hashlib.sha256(norm(x).encode()).hexdigest()
contract=obj(D/'data-contract.json');registry=obj(D/'eligibility-manifest.json');draw=obj(D/'draw-plan.json');selection=obj(D/'document-selection.json');manifest=obj(D/'source-manifest.json')
assert sha(D/'data-contract.json')=='a65d687b5bfbd34323bdeda84ba352970d074e60cd66d029a54f8a28160658bc'
assert sha(D/'source-manifest.json')==contract['source_manifest_sha256']
for pin in manifest['files']:
 p=D/pin['path'];assert p.is_file() and not p.is_symlink() and p.stat().st_size==pin['bytes'] and sha(p)==pin['sha256']
sourcepath=S/'legal-transfer/epoch3/sources/original-train.json';assert sha(sourcepath)=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
source=obj(sourcepath);docs={d['id']:d for d in source['documents']};assert len(docs)==423
old=obj(S/'legal-transfer/epoch8/eligibility-manifest.json');used=obj(S/'epoch8/USED_IDENTITIES.json')
excluded=set(docs)-set(old['eligible_document_ids']);assert len(excluded)==117
for role in ('train','development'):
 excluded.update(int(group.rsplit(':',1)[1]) for group in used['source_frozen_joint_roles'][role]['source_groups'])
assert len(excluded)==149 and excluded==set(registry['excluded_document_ids'])
eligible=set(docs)-excluded;assert len(eligible)==274 and eligible==set(registry['eligible_document_ids'])
archive=S/'legal-transfer/epoch3/sources/original-contractnli.zip';assert sha(archive)=='e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b'
cross=[]
with zipfile.ZipFile(archive) as z:
 for pin in registry['cross_split_source_pins']:
  raw=z.read(pin['archive_member']);assert hashlib.sha256(raw).hexdigest()==pin['sha256'];records=json.loads(raw)['documents'];assert len(records)==pin['documents']
  cross.extend({'document_id':r['id'],'file_name':r['file_name'],'normalized_document_sha256':textsha(r['text']),'source_split':pin['source_split']} for r in records)
assert cross==registry['cross_split_documents']
crossids={d['document_id'] for d in cross};crosshashes={d['normalized_document_sha256'] for d in cross};oldhashes={textsha(docs[i]['text']) for i in excluded}
ranked=sorted((hashlib.sha256((draw['salt']+str(i)+'|'+textsha(docs[i]['text'])).encode()).hexdigest(),i,textsha(docs[i]['text'])) for i in eligible)
chosen=ranked[:24]
for index,(key,i,h) in enumerate(chosen):
 expected={'joint_document_rank':index,'document_id':i,'role':'dev' if index<8 else 'confirmation','normalized_document_sha256':h,'document_draw_key':key}
 assert selection['documents'][index]==expected
 assert i not in crossids and h not in crosshashes and h not in oldhashes
assert sha(D/'draw-plan.json')==selection['draw_plan_sha256']
assert datetime.fromisoformat(selection['frozen_at'])<datetime.fromisoformat(contract['frozen_at'])
assert not selection['labels_read_for_draw'] and not registry['cross_split_labels_accessed_for_selection']
allinputs=set();allgroups=set();result={};labelmap={'Entailment':'Yes','Contradiction':'No','NotMentioned':'No'}
for role,filename,n,start,stop in [('dev','development24.jsonl',24,0,8),('confirmation','confirmation48.jsonl',48,8,24)]:
 data=rows(D/filename);assert len(data)==n and sha(D/filename)==contract['data_files'][filename]['sha256']
 assert [r['provenance']['document_id'] for r in data]==[i for _,i,_ in chosen[start:stop] for hyp in draw['hypotheses']]
 expectedgroups={'original-contractnli:'+str(i) for _,i,_ in chosen[start:stop]};assert not (expectedgroups&allgroups);allgroups|=expectedgroups
 for r in data:
  i=r['provenance']['document_id'];hyp=r['provenance']['hypothesis_id'];doc=docs[i];positive=source['labels'][hyp]['hypothesis'];original=doc['annotation_sets'][0]['annotations'][hyp]['choice'];inp=r['input'];q=inp['questions']['decision']
  assert r['split']==role and r['source_group']=='original-contractnli:'+str(i)
  assert inp['state']==doc['text'] and set(inp)=={'state','questions'}
  assert q['type']=='choice' and q['criteria']=={'Yes':positive,'No':'The agreement does not establish the following: '+positive}
  assert r['evaluation']['gold']==labelmap[original] and r['evaluation']['original_threeway_label']==original
  assert r['evaluation']['labels']==['Yes','No'] and r['evaluation']['gold_distribution'] is None
  h=hashlib.sha256(canon(inp).encode()).hexdigest();assert h==r['input_sha256'] and h not in allinputs;allinputs.add(h)
  assert hashlib.sha256(norm(canon(inp)).encode()).hexdigest()==r['normalized_input_sha256']
 allow=obj(D/('dev-allowlist.json' if role=='dev' else 'confirmation-allowlist.json'))
 assert not allow['contains_labels_or_inputs'] and not allow['fit_permitted']
 assert allow['records']==[{'id':r['id'],'input_sha256':r['input_sha256'],'source_group':r['source_group'],'hypothesis_id':r['provenance']['hypothesis_id']} for r in data]
 result[role]={'queries':n,'groups':len(expectedgroups),'sha256':sha(D/filename),'document_ids':[i for _,i,_ in chosen[start:stop]]}
assert len(allgroups)==24 and len(allinputs)==72
assert contract['fitting']['train_queries']==contract['fitting']['calibration_queries']==0
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'data_contract_sha256':sha(D/'data-contract.json'),'source_manifest_sha256':sha(D/'source-manifest.json'),'manifest_file_pins_verified':len(manifest['files']),'document_selection_sha256':sha(D/'document-selection.json'),'source_groups':result,'prior_officialtrain_exposed_groups':149,'old_officialdev_test_groups_excluded':len(cross),'old_confirmation96_groups_retired':32,'eligible_before_draw':274,'reserved_new_groups':24,'remaining_after_reserved_draw':250,'all_selected_groups_and_normalized_fulltexts_disjoint_from_prior149_and_officialdev_test':True,'source_text_only_draw_reproduced_before_gold_projection':True,'original_threeway_and_binary_gold_projection_verified':True,'runtime_input_projection_only_state_questions':True,'historical_novelty_limits':'Inherited original77 semantic overlap exclusions; normalized exact-text/group checks do not prove absence of fuzzy document-version overlap or unknown upstream pretraining contamination. Public project-unused bank, not sealed publisher test.','TRAIN_or_calibration_queries':0,'auditor_model_native_paid_calls':0}
out=O/'data-independent-v1.json'
with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(out),'groups':result}))
