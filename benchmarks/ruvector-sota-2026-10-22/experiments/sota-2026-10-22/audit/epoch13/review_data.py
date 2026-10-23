"""Independent new-DEV source/identity/draw audit; never examines CONF labels."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,zipfile
O=Path(__file__).resolve().parent;S=O.parents[1];D=S/'legal-transfer/epoch13'
def obj(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def norm(x):return ' '.join(x.casefold().split())
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def textsha(x):return hashlib.sha256(norm(x).encode()).hexdigest()
contract=obj(D/'data-contract.json');registry=obj(D/'eligibility-manifest.json');draw=obj(D/'draw-plan.json');selection=obj(D/'document-selection.json');manifest=obj(D/'source-manifest.json')
assert contract['checkpoint_parent']=='cd18a712d1adbaba92d7c26080923b437ae36af8'
assert contract['train']==contract['calibration']==[] and contract['training_questions']==contract['training_feature_questions']==contract['fitting']['training_feature_queries']==contract['fitting']['calibration_queries']==0
for x in manifest['files']:
 p=D/x['path'];assert p.is_file() and not p.is_symlink() and p.stat().st_size==x['bytes'] and sha(p)==x['sha256'],x['path']
sourcepath=S/'legal-transfer/epoch3/sources/original-train.json';assert sha(sourcepath)=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
source=obj(sourcepath);docs={d['id']:d for d in source['documents']};assert len(docs)==423
old=obj(S/'legal-transfer/epoch12/eligibility-manifest.json');used=obj(S/'epoch12/USED_IDENTITIES.json')
assert sha(S/'legal-transfer/epoch12/eligibility-manifest.json')==registry['previous_registry_sha256']
assert sha(S/'epoch12/USED_IDENTITIES.json')==registry['used_identity_manifest_sha256']
excluded=set(old['excluded_document_ids']);assert len(excluded)==173
excluded.update(int(x.rsplit(':',1)[1]) for x in used['source_frozen_roles']['development']['source_groups'])
assert len(excluded)==181 and excluded==set(registry['excluded_document_ids'])
reserved=set(old['reserved_confirmation_document_ids']);assert len(reserved)==16 and reserved==set(registry['reserved_confirmation_document_ids']) and not (reserved&excluded)
eligible=set(docs)-excluded-reserved;assert len(eligible)==226 and eligible==set(registry['eligible_document_ids'])
assert registry['cross_split_documents']==old['cross_split_documents'] and not registry['cross_split_labels_used_for_selection']
archive=S/'legal-transfer/epoch3/sources/original-contractnli.zip';assert sha(archive)=='e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b'
# Only IDs/text fields are consulted for official cross-split checks.
prior=obj(S/'legal-transfer/epoch9/eligibility-manifest.json');cross=[]
with zipfile.ZipFile(archive) as z:
 for pin in prior['cross_split_source_pins']:
  raw=z.read(pin['archive_member']);assert hashlib.sha256(raw).hexdigest()==pin['sha256'];rs=json.loads(raw)['documents'];assert len(rs)==pin['documents']
  cross.extend({'document_id':r['id'],'file_name':r['file_name'],'normalized_document_sha256':textsha(r['text']),'source_split':pin['source_split']} for r in rs)
assert cross==registry['cross_split_documents']
oldhashes={textsha(docs[i]['text']) for i in excluded|reserved};crossids={x['document_id'] for x in cross};crosshashes={x['normalized_document_sha256'] for x in cross}
ranked=sorted((hashlib.sha256((draw['salt']+str(i)+'|'+textsha(docs[i]['text'])).encode()).hexdigest(),i,textsha(docs[i]['text'])) for i in eligible);chosen=ranked[:8]
assert sha(D/'draw-plan.json')==selection['draw_plan_sha256'] and not selection['gold_access_for_selection']
assert datetime.fromisoformat(selection['frozen_at'])<datetime.fromisoformat(contract['frozen_at']) and contract['roles_frozen_before_new_gold_projection_at']==selection['frozen_at']
for n,(key,i,h) in enumerate(chosen):
 assert selection['documents'][n]=={'document_rank':n,'document_id':i,'normalized_document_sha256':h,'document_draw_key':key,'role':'dev'}
 assert i not in crossids and h not in crosshashes and h not in oldhashes
assert len(selection['documents'])==8
records=rows(D/'development24.jsonl');assert len(records)==24 and sha(D/'development24.jsonl')==contract['development']['sha256']
assert [r['provenance']['document_id'] for r in records]==[i for _,i,_ in chosen for hyp in draw['hypotheses']]
expectedgroups={'original-contractnli:'+str(i) for _,i,_ in chosen};assert {r['source_group'] for r in records}==expectedgroups
labelmap={'Entailment':'Yes','Contradiction':'No','NotMentioned':'No'};inputs=set()
for r in records:
 i=r['provenance']['document_id'];hyp=r['provenance']['hypothesis_id'];doc=docs[i];positive=source['labels'][hyp]['hypothesis'];original=doc['annotation_sets'][0]['annotations'][hyp]['choice'];inp=r['input'];q=inp['questions']['decision']
 assert r['split']=='dev' and r['source_group']=='original-contractnli:'+str(i)
 assert inp['state']==doc['text'] and set(inp)=={'state','questions'}
 assert q['type']=='choice' and q['criteria']=={'Yes':positive,'No':'The agreement does not establish the following: '+positive}
 assert r['evaluation']['gold']==labelmap[original] and r['evaluation']['original_threeway_label']==original
 assert r['evaluation']['labels']==['Yes','No'] and r['evaluation']['gold_distribution'] is None
 h=hashlib.sha256(canon(inp).encode()).hexdigest();assert h==r['input_sha256'] and h not in inputs;inputs.add(h)
 assert hashlib.sha256(norm(canon(inp)).encode()).hexdigest()==r['normalized_input_sha256']
allow=obj(D/'dev-allowlist.json');assert not allow['contains_labels_or_inputs'] and not allow['fit_permitted'];assert allow['records']==[{'id':r['id'],'input_sha256':r['input_sha256'],'source_group':r['source_group'],'hypothesis_id':r['provenance']['hypothesis_id']} for r in records]
conf=obj(D/'confirmation-allowlist.json');assert sha(D/'confirmation-allowlist.json')=='65485b57d37a3341031cd4e125539e6c052f34844a60f93be7f1035db68c913e';assert not conf['contains_labels_or_inputs'] and len(conf['records'])==48 and len({r['source_group'] for r in conf['records']})==16;assert not({x['id'] for x in conf['records']}&{x['id'] for x in records});assert not({x['source_group'] for x in conf['records']}&expectedgroups);assert not({x['input_sha256'] for x in conf['records']}&inputs)
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'data_contract_sha256':sha(D/'data-contract.json'),'source_manifest_sha256':sha(D/'source-manifest.json'),'manifest_pins_verified':len(manifest['files']),'DEV_sha256':sha(D/'development24.jsonl'),'new_DEV_document_ids':[i for _,i,_ in chosen],'new_DEV_group_and_normalized_fulltext_disjoint_prior181_reserved16_officialdevtest':True,'text_only_draw_before_gold_projection_reproduced':True,'original_threeway_and_binary_DEV_gold_verified':True,'metadata_only_confirmation_allowlist_preserved':True,'confirmation_labels_inspected':False,'TRAIN_calibration_queries':0,'prior_exposed_groups':181,'reserved_CONFIRM_groups':16,'eligible_unreserved_before':226,'unreserved_after_draw':218,'conservative_exposed_after_phase1':189,'limitations':'Inherited historical semantic exclusions; exact group/normalized text checks do not prove no fuzzy versions or unknown upstream pretraining overlap. Internal public NDA pilot, no full benchmark rank.','auditor_model_native_paid_calls':0}
out=O/'data-independent-v1.json'
with out.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'PASS':True,'sha256':sha(out),'DEV_groups':8,'manifest_pins':len(manifest['files'])}))
