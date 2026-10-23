"""Independent epoch12 source-only draw, preserved TRAIN and fresh DEV audit."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,zipfile
O=Path(__file__).resolve().parent;S=O.parents[1];D=S/'legal-transfer/epoch12'
def obj(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def norm(x):return ' '.join(x.casefold().split())
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def textsha(x):return hashlib.sha256(norm(x).encode()).hexdigest()
contract=obj(D/'data-contract.json');registry=obj(D/'eligibility-manifest.json');draw=obj(D/'draw-plan.json');selection=obj(D/'document-selection.json');manifest=obj(D/'source-manifest.json')
assert contract['checkpoint_parent']=='edb193532821ddc43084eca932f36ec29d045b60' and contract['calibration']==[]
assert contract['fitting']=={'train_sanity_queries':6,'training_feature_queries':0,'calibration_queries':0,'supervised_fit':False,'model_precision_or_threshold_selection':False,'temperature':1.0}
for x in manifest['files']:
 p=D/x['path'];assert p.is_file() and not p.is_symlink() and p.stat().st_size==x['bytes'] and sha(p)==x['sha256'],x['path']
sourcepath=S/'legal-transfer/epoch3/sources/original-train.json';assert sha(sourcepath)=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
source=obj(sourcepath);docs={d['id']:d for d in source['documents']};assert len(docs)==423
old=obj(S/'legal-transfer/epoch11/eligibility-manifest.json');used=obj(S/'epoch11/USED_IDENTITIES.json')
assert sha(S/'legal-transfer/epoch11/eligibility-manifest.json')==registry['previous_registry_sha256']
assert sha(S/'epoch11/USED_IDENTITIES.json')==registry['used_identity_manifest_sha256']
excluded=set(old['excluded_document_ids']);assert len(excluded)==165
excluded.update(int(x.rsplit(':',1)[1]) for x in used['source_frozen_roles']['development']['source_groups'])
assert len(excluded)==173 and excluded==set(registry['excluded_document_ids'])
reserved=set(old['reserved_confirmation_document_ids']);assert len(reserved)==16 and reserved==set(registry['reserved_confirmation_document_ids']) and not reserved&excluded
eligible=set(docs)-excluded-reserved;assert len(eligible)==234 and eligible==set(registry['eligible_document_ids'])
trainmeta=obj(S/'legal-transfer/epoch10/train-allowlist.json');assert sha(S/'legal-transfer/epoch10/train-allowlist.json')==registry['training_sanity_pool_metadata_sha256']
trainpool={int(x['source_group'].rsplit(':',1)[1]) for x in trainmeta['records']};assert trainmeta['role']=='train' and len(trainpool)==24 and trainpool<=excluded and trainpool==set(registry['training_sanity_reuse_document_ids'])
assert registry['cross_split_documents']==old['cross_split_documents'] and not registry['cross_split_labels_used_for_selection']
archive=S/'legal-transfer/epoch3/sources/original-contractnli.zip';assert sha(archive)=='e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b'
prior=obj(S/'legal-transfer/epoch9/eligibility-manifest.json');cross=[]
with zipfile.ZipFile(archive) as z:
 for pin in prior['cross_split_source_pins']:
  raw=z.read(pin['archive_member']);assert hashlib.sha256(raw).hexdigest()==pin['sha256'];rs=json.loads(raw)['documents'];assert len(rs)==pin['documents']
  cross.extend({'document_id':r['id'],'file_name':r['file_name'],'normalized_document_sha256':textsha(r['text']),'source_split':pin['source_split']} for r in rs)
assert cross==registry['cross_split_documents']
oldhashes={textsha(docs[i]['text']) for i in excluded|reserved};crossids={x['document_id'] for x in cross};crosshashes={x['normalized_document_sha256'] for x in cross}
def ranked(ids,salt):return sorted((hashlib.sha256((salt+str(i)+'|'+textsha(docs[i]['text'])).encode()).hexdigest(),i,textsha(docs[i]['text'])) for i in ids)
chosen={'dev':ranked(eligible,draw['salt'])[:8],'train_sanity':ranked(trainpool,draw['train_sanity_salt'])[:2]}
assert sha(D/'draw-plan.json')==selection['draw_plan_sha256'] and selection['gold_access_for_selection'] is False
assert datetime.fromisoformat(selection['frozen_at'])<datetime.fromisoformat(contract['frozen_at']) and contract['roles_frozen_before_new_gold_projection_at']==selection['frozen_at']
for role,key in [('dev','documents'),('train_sanity','train_sanity_documents')]:
 assert selection[key]==[{'document_rank':n,'document_id':i,'normalized_document_sha256':h,'document_draw_key':k,'role':role} for n,(k,i,h) in enumerate(chosen[role])]
 for _,i,h in chosen[role]:
  assert i not in crossids and h not in crosshashes and i not in reserved
  if role=='dev':assert h not in oldhashes
  else:assert i in trainpool and i in excluded
assert not ({i for _,i,_ in chosen['dev']}&{i for _,i,_ in chosen['train_sanity']})
labelmap={'Entailment':'Yes','Contradiction':'No','NotMentioned':'No'};allinputs=set();groups={};counts={}
for role,path,allowname,count in [('dev','development24.jsonl','dev-allowlist.json',24),('train_sanity','train-sanity6.jsonl','train-allowlist.json',6)]:
 records=rows(D/path);assert len(records)==count and sha(D/path)==contract['data_files'][path]['sha256'];counts[role]=len(records)
 assert [r['provenance']['document_id'] for r in records]==[i for _,i,_ in chosen[role] for hyp in draw['hypotheses']]
 groups[role]={'original-contractnli:'+str(i) for _,i,_ in chosen[role]};assert {r['source_group'] for r in records}==groups[role]
 expectedmeta=[]
 for r in records:
  i=r['provenance']['document_id'];hyp=r['provenance']['hypothesis_id'];doc=docs[i];positive=source['labels'][hyp]['hypothesis'];original=doc['annotation_sets'][0]['annotations'][hyp]['choice'];inp=r['input'];q=inp['questions']['decision']
  assert r['split']==role and r['source_group']=='original-contractnli:'+str(i) and inp['state']==doc['text'] and set(inp)=={'state','questions'}
  assert q['type']=='choice' and q['instructions']=='Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.'
  assert q['criteria']=={'Yes':positive,'No':'The agreement does not establish the following: '+positive}
  assert r['evaluation']['gold']==labelmap[original] and r['evaluation']['original_threeway_label']==original and r['evaluation']['labels']==['Yes','No'] and r['evaluation']['gold_distribution'] is None
  h=hashlib.sha256(canon(inp).encode()).hexdigest();assert h==r['input_sha256'] and h not in allinputs;allinputs.add(h)
  assert hashlib.sha256(norm(canon(inp)).encode()).hexdigest()==r['normalized_input_sha256']
  m={'id':r['id'],'input_sha256':h,'source_group':r['source_group'],'hypothesis_id':hyp}
  if role=='train_sanity':
   assert h in {x['input_sha256'] for x in trainmeta['records']}
   m.update(state_sha256=hashlib.sha256(inp['state'].encode()).hexdigest(),questions_sha256=hashlib.sha256(canon(inp['questions']).encode()).hexdigest(),wire_input_sha256=hashlib.sha256(json.dumps(inp,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest())
  expectedmeta.append(m)
 allow=obj(D/allowname);assert not allow['contains_labels_or_inputs'] and not allow['fit_permitted'] and not allow['model_precision_or_threshold_selection_permitted'] and allow['records']==expectedmeta
conf=obj(D/'confirmation-allowlist.json');assert sha(D/'confirmation-allowlist.json')=='65485b57d37a3341031cd4e125539e6c052f34844a60f93be7f1035db68c913e';assert not conf['contains_labels_or_inputs'] and len(conf['records'])==48 and len({r['source_group'] for r in conf['records']})==16
assert not ({x['source_group'] for x in conf['records']}&(groups['dev']|groups['train_sanity'])) and not({x['input_sha256'] for x in conf['records']}&allinputs)
assert sha(S/'legal-transfer/epoch9/confirmation48.jsonl')==contract['confirmation']['sha256']=='850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50'
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'data_contract_sha256':sha(D/'data-contract.json'),'source_manifest_sha256':sha(D/'source-manifest.json'),'manifest_pins_verified':len(manifest['files']),'DEV_sha256':sha(D/'development24.jsonl'),'TRAIN_sanity_sha256':sha(D/'train-sanity6.jsonl'),'new_DEV_document_ids':[i for _,i,_ in chosen['dev']],'reused_TRAIN_document_ids':[i for _,i,_ in chosen['train_sanity']],'reused_TRAIN_source_role_and_inputhashes_match_epoch10':True,'new_DEV_group_and_normalized_fulltext_disjoint_prior173_reserved16_officialdevtest':True,'text_only_draw_before_gold_projection_reproduced':True,'selected_TRAIN_and_DEV_gold_projection_verified':True,'metadata_only_confirmation_allowlist_preserved':True,'confirmation_labels_inspected':False,'unused_confirmation_projection_parsed':False,'TRAIN_sanity_diagnostics':6,'training_feature_HTTP':0,'calibration_queries':0,'no_supervised_fit_or_model_precision_selection':True,'prior_exposed_groups':173,'reserved_CONFIRM_groups':16,'eligible_unreserved_before':234,'unreserved_after_draw':226,'conservative_exposed_after_phase1':181,'new_TRAIN_exposure_groups':0,'limitations':'Public-source project novelty and exact normalized text checks do not prove no fuzzy versions or upstream pretraining overlap. TRAIN sanity is descriptive, not benchmark generalization.','auditor_model_native_paid_calls':0}
out=O/'data-independent-v1.json'
with out.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(out),'DEV_groups':8,'TRAIN_sanity_groups':2,'manifest_pins':len(manifest['files'])}))
