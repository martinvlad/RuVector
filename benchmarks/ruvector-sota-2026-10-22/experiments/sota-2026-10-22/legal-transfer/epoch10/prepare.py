"""Freeze data roles before new gold projection; source/data operations only."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,shutil
HERE=Path(__file__).resolve().parent
S=HERE.parents[1]
KIT=S/'epoch10/durable-kit'
SOURCE=S/'epoch10/project/experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json'
TRAIN_REL='experiments/sota-2026-10-22/legal-transfer/epoch8/train72.jsonl'
CONF_REL='experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation48.jsonl'
TRAIN_SHA='d98f05b49ebad6a9cac447238b32aa3f8ccefa1253bdd2d52465bd111403c644'
CONF_SHA='850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50'
SOURCE_SHA='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(n,x):
 with (HERE/n).open('x') as f:json.dump(x,f,indent=2,ensure_ascii=False);f.write('\n')
def now():return datetime.now(timezone.utc).isoformat()
def norm(t):return ' '.join(t.casefold().split())
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
assert not (HERE/'data-contract.json').exists()
c=load(KIT/'CONTINUATION.json');manifest=load(KIT/'CHECKPOINT_MANIFEST.json');assert sha(KIT/'CHECKPOINT_MANIFEST.json')==c['checkpoint_manifest_sha256']
pins={x['path']:x for x in manifest['project_files']}
required=[TRAIN_REL,CONF_REL,'experiments/sota-2026-10-22/legal-transfer/epoch9/eligibility-manifest.json','experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation-allowlist.json','experiments/sota-2026-10-22/epoch9/USED_IDENTITIES.json','experiments/sota-2026-10-22/legal-transfer/epoch9/data-contract.json','experiments/sota-2026-10-22/legal-transfer/epoch9/CC-BY-4.0.txt']
for rel in required:
 assert sha(KIT/rel)==pins[rel]['sha256'] and (KIT/rel).stat().st_size==pins[rel]['bytes'],rel
assert sha(KIT/TRAIN_REL)==TRAIN_SHA and sha(KIT/CONF_REL)==CONF_SHA and sha(SOURCE)==SOURCE_SHA
registry=load(KIT/'experiments/sota-2026-10-22/legal-transfer/epoch9/eligibility-manifest.json')
used=load(KIT/'experiments/sota-2026-10-22/epoch9/USED_IDENTITIES.json')
reserved=load(KIT/'experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation-allowlist.json')
idof=lambda g:int(g.rsplit(':',1)[1])
old=set(registry['excluded_document_ids'])|{idof(g) for g in used['source_frozen_roles']['development']['source_groups']}
reserve={idof(r['source_group']) for r in reserved['records']}
assert len(old)==157 and len(reserve)==16 and not old&reserve
source=load(SOURCE);docs={d['id']:d for d in source['documents']};assert len(docs)==423
eligible=set(docs)-old-reserve;assert len(eligible)==250
cross_ids={x['document_id'] for x in registry['cross_split_documents']};cross_text={x['normalized_document_sha256'] for x in registry['cross_split_documents']}
hashes={i:hashlib.sha256(norm(d['text']).encode()).hexdigest() for i,d in docs.items()}
old_text={hashes[i] for i in old|reserve};assert not eligible&cross_ids
salt='ruvector-sota-epoch10-new-dev24-v1|'
ranked=sorted((hashlib.sha256((salt+str(i)+'|'+hashes[i]).encode()).hexdigest(),i) for i in eligible)
chosen=ranked[:8];ids={i for _,i in chosen};assert len(ids)==8
assert not {hashes[i] for i in ids}&(old_text|cross_text)
shutil.copy2(KIT/'experiments/sota-2026-10-22/legal-transfer/epoch9/CC-BY-4.0.txt',HERE/'CC-BY-4.0.txt')
save('restored-source-verification.json',{'at':now(),'checkpoint_commit':'9f899fc6d9e75f69993dcf80927116584740e7b8','checkpoint_manifest_sha256':c['checkpoint_manifest_sha256'],'restored_pins_verified':[pins[x] for x in required],'original_train_sha256':SOURCE_SHA,'source_only':True,'native_model_paid_calls':0})
save('eligibility-manifest.json',{'schema_version':1,'checkpoint_commit':'9f899fc6d9e75f69993dcf80927116584740e7b8','source_sha256':SOURCE_SHA,'excluded_document_ids':sorted(old),'reserved_confirmation_document_ids':sorted(reserve),'eligible_document_ids':sorted(eligible),'counts':{'officialtrain':423,'exposed':157,'reserved_confirmation':16,'eligible_unreserved':250},'cross_split_documents':registry['cross_split_documents'],'cross_split_labels_used_for_selection':False,'old_and_reserved_normalized_document_sha256':sorted(old_text),'selected_cross_split_or_prior_text_collisions':0,'previous_registry_sha256':sha(KIT/'experiments/sota-2026-10-22/legal-transfer/epoch9/eligibility-manifest.json'),'used_identity_manifest_sha256':sha(KIT/'experiments/sota-2026-10-22/epoch9/USED_IDENTITIES.json')})
save('draw-plan.json',{'schema_version':1,'source_sha256':SOURCE_SHA,'source_commit':'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9','eligibility_manifest_sha256':sha(HERE/'eligibility-manifest.json'),'salt':salt,'hypotheses':['nda-17','nda-7','nda-3'],'dev_documents':8,'selection':'One text/ID-only SHA256 ranking from250 unreserved eligible officialtrain groups; first8; no gold/outcome/length stratification or redraw.','train_reuse_sha256':TRAIN_SHA,'confirmation_preserved_sha256':CONF_SHA})
roles_at=now()
save('document-selection.json',{'schema_version':1,'frozen_at':roles_at,'draw_plan_sha256':sha(HERE/'draw-plan.json'),'gold_access_for_new_DEV_selection':False,'documents':[{'document_rank':j,'document_id':i,'normalized_document_sha256':hashes[i],'document_draw_key':k,'role':'dev'} for j,(k,i) in enumerate(chosen)],'train':'Reuse exact exposed epoch8 TRAIN72; no new train draw','confirmation':'Preserve exact epoch9 reserved48; no confirmation labels accessed'})
# New document roles are now immutable. Gold is only projected for TRAIN/DEV below.
assert ids.isdisjoint(reserve)
shutil.copy2(KIT/TRAIN_REL,HERE/'train72.jsonl');assert sha(HERE/'train72.jsonl')==TRAIN_SHA
train=[json.loads(x) for x in (HERE/'train72.jsonl').read_text().splitlines()]
assert len(train)==72 and len({r['source_group'] for r in train})==24
annotations=[]
for row in train:
 i=row['provenance']['document_id'];hyp=row['provenance']['hypothesis_id'];d=docs[i];assert i in old and i not in ids|reserve
 ann=d['annotation_sets'][0]['annotations'][hyp];assert ann['choice']==row['evaluation']['original_threeway_label'] and d['text']==row['input']['state']
 spans=[d['spans'][i] for i in ann['spans']]
 assert all(0<=a<b<=len(d['text']) for a,b in spans)
 annotations.append({'id':row['id'],'input_sha256':row['input_sha256'],'source_group':row['source_group'],'hypothesis_id':hyp,'original_threeway_label':ann['choice'],'evidence_spans':spans,'evidence_span_ids':ann['spans'],'source_document_sha256':hashlib.sha256(d['text'].encode()).hexdigest(),'source_annotation_sha256':hashlib.sha256(canonical(ann).encode()).hexdigest()})
save('train-annotations.json',{'schema_version':1,'role':'train','queries':72,'document_groups':24,'train_data_sha256':TRAIN_SHA,'source_sha256':SOURCE_SHA,'source_commit':'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9','span_units':'Half-open Python character offsets into exact full input.state; annotations are TRAIN-only fit targets, never inference features','target_semantics':'Any-character intersection with annotated goldspans is annotation coverage, not semantic sufficiency or legal absence proof','records':annotations,'contains_confirmation_data_or_labels':False,'native_model_paid_calls':0})
LABELS={'Entailment':'Yes','Contradiction':'No','NotMentioned':'No'};INSTRUCTION='Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.'
dev=[]
for j,(key,i) in enumerate(chosen):
 d=docs[i];assert len(d['annotation_sets'])==1
 for hyp in ['nda-17','nda-7','nda-3']:
  positive=source['labels'][hyp]['hypothesis'];inp={'state':d['text'],'questions':{'decision':{'type':'choice','instructions':INSTRUCTION,'criteria':{'Yes':positive,'No':'The agreement does not establish the following: '+positive}}}};label=d['annotation_sets'][0]['annotations'][hyp]['choice']
  dev.append({'id':f'original-contractnli:train:epoch10:dev:{i}:{hyp}','split':'dev','source':'stanfordnlp/contract-nli@eced6528dd3c1d14d73f9a87df8f7bdbc03126f9/train.json','source_group':'original-contractnli:'+str(i),'input':inp,'evaluation':{'type':'choice','gold':LABELS[label],'labels':['Yes','No'],'source_family':hyp,'group':'original-contractnli:'+str(i),'gold_distribution':None,'original_threeway_label':label},'input_sha256':hashlib.sha256(canonical(inp).encode()).hexdigest(),'normalized_input_sha256':hashlib.sha256(norm(canonical(inp)).encode()).hexdigest(),'provenance':{'document_id':i,'file_name':d['file_name'],'source_split':'train','hypothesis_id':hyp,'document_draw_key':key,'document_rank':j,'normalized_document_sha256':hashes[i],'license':'CC-BY-4.0'},'exposure':'New project-unused DEV for frozen protocol gate only; no fitting/calibration. Internal public-source NDApilot, not sealed or pretraining-contamination-proof.'})
with (HERE/'development24.jsonl').open('x') as f:
 for row in dev:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
def allow(rows,role,hashv,fit):return {'schema_version':1,'role':role,'queries':len(rows),'document_groups':len({r['source_group'] for r in rows}),'data_sha256':hashv,'threeway_classes':list(LABELS),'binary_mapping':LABELS,'records':[{'id':r['id'],'input_sha256':r['input_sha256'],'source_group':r['source_group'],'hypothesis_id':r['provenance']['hypothesis_id']} for r in rows],'contains_labels_or_inputs':False,'fit_permitted':fit}
save('train-allowlist.json',allow(train,'train',TRAIN_SHA,True));save('dev-allowlist.json',allow(dev,'dev',sha(HERE/'development24.jsonl'),False));shutil.copy2(KIT/'experiments/sota-2026-10-22/legal-transfer/epoch9/confirmation-allowlist.json',HERE/'confirmation-allowlist.json')
contract={'schema_version':1,'frozen':True,'frozen_at':now(),'checkpoint_parent':'9f899fc6d9e75f69993dcf80927116584740e7b8','scope':'Internal source-licensed originalContractNLI3predicate NDApilot. TRAIN reused and already exposed; DEV newly drawn; confirmation48 preserved project-model-unused. No full LegalBench/Jev300/ClaimBench score.','train_data':{'path':'experiments/sota-2026-10-22/legal-transfer/epoch10/train72.jsonl','sha256':TRAIN_SHA,'queries':72,'document_groups':24,'status':'Exact reused epoch8 TRAIN bytes, already exposed, not fresh evaluation'},'train_annotations':{'path':'experiments/sota-2026-10-22/legal-transfer/epoch10/train-annotations.json','sha256':sha(HERE/'train-annotations.json'),'queries':72,'role':'TRAIN-only source-gold annotation coverage target; never legal sufficiency/absence evidence'},'train_allowlist':{'path':'experiments/sota-2026-10-22/legal-transfer/epoch10/train-allowlist.json','sha256':sha(HERE/'train-allowlist.json')},'development':{'path':'experiments/sota-2026-10-22/legal-transfer/epoch10/development24.jsonl','sha256':sha(HERE/'development24.jsonl'),'queries':24,'document_groups':8,'status':'New project-unused source groups, no fit/normalization/calibration'},'confirmation':{'path':CONF_REL,'sha256':CONF_SHA,'queries':48,'document_groups':16,'status':'Existing epoch9 bank unchanged and unconsumed; labels only scorer/auditor after frozen gates; no selection/fit use','allowlist_path':'experiments/sota-2026-10-22/legal-transfer/epoch10/confirmation-allowlist.json','allowlist_sha256':sha(HERE/'confirmation-allowlist.json')},'calibration':[],'roles_frozen_before_new_gold_projection_at':roles_at,'draw':{'plan_sha256':sha(HERE/'draw-plan.json'),'selection_sha256':sha(HERE/'document-selection.json'),'eligible_unreserved_before':250,'new_DEV_groups':8,'unreserved_remaining_after':242,'prior_exposed_train_groups':157,'reserved_confirmation_groups':16,'selection_uses_labels_or_outcomes':False},'source':{'repository':'stanfordnlp/contract-nli','commit':'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9','member':'contract-nli/train.json','member_sha256':SOURCE_SHA,'archive_sha256':'e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b','license':'CC-BY-4.0','license_sha256':sha(HERE/'CC-BY-4.0.txt')},'inference_boundary':{'only':['state','questions'],'forbidden':['gold','evidence annotations','record IDs','source groups','roles','provenance'],'original_threeway_label_field':'evaluation.original_threeway_label','binary_mapping':LABELS},'native_model_paid_calls':0,'official_score':None,'official_rank':None}
save('data-contract.json',contract)
save('data-ids.json',{'schema_version':1,'train':allow(train,'train',TRAIN_SHA,True),'development':allow(dev,'dev',sha(HERE/'development24.jsonl'),False),'confirmation':reserved,'calibration':[],'contains_labels_or_inputs':False})
print(json.dumps({'frozen_at':contract['frozen_at'],'roles_at':roles_at,'data_contract_sha256':sha(HERE/'data-contract.json'),'train_sha256':TRAIN_SHA,'annotations_sha256':sha(HERE/'train-annotations.json'),'train_allowlist_sha256':sha(HERE/'train-allowlist.json'),'DEV_sha256':sha(HERE/'development24.jsonl'),'confirmation_sha256':CONF_SHA,'new_DEV_group_ids':sorted(ids),'native_model_paid_calls':0}))
