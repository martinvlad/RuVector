"""Independent source-only jointTRAIN/DEV draw/label/provenance audit; no model imports."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
O=Path(__file__).resolve().parent;S=O.parents[1];D=S/'legal-transfer/epoch8'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def obj(p):return json.loads(p.read_text())
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def norm(x):return ' '.join(x.casefold().split())
src=S/'legal-transfer/epoch3/sources/original-train.json';assert sha(src)=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5';source=obj(src);reg=obj(D/'eligibility-manifest.json');oldreg=obj(S/'legal-transfer/epoch7/eligibility-manifest.json')
assert reg['historical_exclusions']==oldreg['historical_exclusions'];historical={x['id'] for x in reg['historical_exclusions']['excluded_documents']};oldrecords=[];prior=set()
for epoch in (3,4,5,6,7):
 rs=rows(S/f'legal-transfer/epoch{epoch}/development24.jsonl');ids={r['provenance']['document_id'] for r in rs};assert len(ids)==8 and ids==set(reg[f'consumed_epoch{epoch}_dev']['document_ids']);assert not (prior&ids);prior|=ids;oldrecords+=rs
assert len(historical)==77 and len(prior)==40 and not historical&prior
eligible={d['id'] for d in source['documents']}-historical-prior;assert len(eligible)==306 and eligible==set(reg['eligible_document_ids'])
rank=[]
for d in source['documents']:
 if d['id'] in eligible:
  textsha=hashlib.sha256(norm(d['text']).encode()).hexdigest();key=hashlib.sha256(f"ruvector-original-contractnli-epoch8-joint-v1|{d['id']}|{textsha}".encode()).hexdigest();rank.append((key,d))
selected=[d for key,d in sorted(rank,key=lambda v:v[0])[:32]];expected={'train':selected[:24],'dev':selected[24:]};files={'train':D/'train72.jsonl','dev':D/'development24.jsonl'};actual={role:rows(path) for role,path in files.items()};label={'Entailment':'Yes','Contradiction':'No','NotMentioned':'No'};hyps=['nda-17','nda-7','nda-3'];instruction='Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.'
for role,documents in expected.items():
 records=actual[role];assert len(records)==len(documents)*3==({'train':72,'dev':24}[role]);assert len({r['id'] for r in records})==len(records)
 for i,d in enumerate(documents):
  for j,h in enumerate(hyps):
   r=records[i*3+j];hyp=source['labels'][h]['hypothesis'];inp={'state':d['text'],'questions':{'decision':{'type':'choice','instructions':instruction,'criteria':{'Yes':hyp,'No':'The agreement does not establish the following: '+hyp}}}}
   assert r['id']==f"original-contractnli:train:epoch8:{role}:{d['id']}:{h}" and r['split']==role and r['provenance']['source_split']=='train'
   assert r['input']==inp and r['input_sha256']==hashlib.sha256(canonical(inp).encode()).hexdigest() and r['normalized_input_sha256']==hashlib.sha256(norm(canonical(inp)).encode()).hexdigest()
   assert r['source_group']==r['evaluation']['group']==f"original-contractnli:{d['id']}";original=d['annotation_sets'][0]['annotations'][h]['choice'];assert r['evaluation']['original_threeway_label']==original and r['evaluation']['gold']==label[original]
   assert r['provenance']['normalized_document_sha256']==hashlib.sha256(norm(d['text']).encode()).hexdigest()
 allow=obj(D/(role+'-allowlist.json'));assert allow['role']==role and allow['queries']==len(records) and allow['data_sha256']==sha(files[role]) and not allow['contains_labels_or_inputs']
 assert allow['records']==[{'id':r['id'],'input_sha256':r['input_sha256'],'source_group':r['source_group'],'hypothesis_id':r['provenance']['hypothesis_id']} for r in records]
 assert set(records[0]['input'])=={'state','questions'}
confirmation=rows(S/'legal-transfer/epoch3/confirmation96.jsonl');assert sha(S/'legal-transfer/epoch3/confirmation96.jsonl')=='f01894b231b744c8297344615ce6037524b6eb0794c7548e931839d2936cd79f'
roles=[actual['train'],actual['dev'],oldrecords,confirmation]
for i,a in enumerate(roles):
 for b in roles[i+1:]:
  assert {r['source_group'] for r in a}.isdisjoint({r['source_group'] for r in b})
  assert {norm(r['input']['state']) for r in a}.isdisjoint({norm(r['input']['state']) for r in b})
assert {r['evaluation']['original_threeway_label'] for r in actual['train']}==set(label)
manifest=obj(D/'source-manifest.json')
for x in manifest['files']:assert sha(D/x['path'])==x['sha256'] and (D/x['path']).stat().st_size==x['bytes']
r={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'source_manifest_sha256':sha(D/'source-manifest.json'),'data_contract_sha256':sha(D/'data-contract.json'),'TRAIN_sha256':sha(files['train']),'DEV_sha256':sha(files['dev']),'counts':{'officialTRAINdocs':423,'historicalexcluded':77,'priorepoch3to7DEVdocs':40,'allpriorexcluded':117,'eligiblebeforejointdraw':306,'selectedTRAINdocs':24,'selectedDEVdocs':8,'TRAINqueries':72,'DEVqueries':24,'remainingfreshafterTRAINandDEVexposure':274},'document_ids':{role:[d['id'] for d in ds] for role,ds in expected.items()},'checks':['Independently rebuiltONEtext-onlysalted306docdraw andfirst24TRAIN/next8DEV assignment beforegoldprojection.','Exactsource text/hypothesis andoriginal3wayannotations mappedYesE/NoC+N withoutinventedNeutral; all3TRAINtargetclassespresent.','Inputcanonical/normalizedSHA/group/role/source fields andbothlabel-freeallowlists exact.','TRAIN/DEV/prior40DEV/CONF32groups andnormalizedsourcefulltext pairwisedisjoint.','Allsourcepins hash/sizechecked, officialdev/testneverfit; inherited77historicalnoveltyqualified.'],'source_pins_checked':len(manifest['files']),'novelty_limit':'Publicdata/projectgroupfreshness only, inheritedsemanticnovelty/sourcepins andunknownpretrainingoverlap, notsealed/universalunseen.','auditor_model_native_calls':0}
p=O/'data-independent-v1.json';assert not p.exists();p.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'checks_passed':True,'sha256':sha(p),'TRAIN':r['TRAIN_sha256'],'DEV':r['DEV_sha256']}))
