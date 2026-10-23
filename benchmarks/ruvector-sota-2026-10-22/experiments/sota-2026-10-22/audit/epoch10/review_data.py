"""Independent frozen TRAIN-sidecar and new DEV group/source review; no fitting."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
O=Path(__file__).resolve().parent;S=O.parents[1];D=S/'legal-transfer/epoch10';ROOT=S.parents[1]
def obj(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x)for x in p.read_text().splitlines()if x]
def norm(s):return ' '.join(s.casefold().split())
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def textsha(t):return hashlib.sha256(norm(t).encode()).hexdigest()
c=obj(D/'data-contract.json');assert sha(D/'data-contract.json')=='c6178d4d2f4144161b0b095b714e64f227fba71cc6e73908ff767dcb96105aec'
manifest=obj(D/'source-manifest.json')
for x in manifest['files']:
 p=D/x['path'];assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256']
sourcepath=S/'legal-transfer/epoch3/sources/original-train.json';assert sha(sourcepath)=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
source=obj(sourcepath);docs={d['id']:d for d in source['documents']};assert len(docs)==423
reg=obj(D/'eligibility-manifest.json');prev=obj(S/'legal-transfer/epoch9/eligibility-manifest.json');used=obj(S/'epoch9/USED_IDENTITIES.json')
exposed=set(prev['excluded_document_ids'])|{int(g.rsplit(':',1)[1])for g in used['source_frozen_roles']['development']['source_groups']}
reserved={int(g.rsplit(':',1)[1])for g in used['source_frozen_roles']['confirmation']['source_groups']}
assert len(exposed)==157 and len(reserved)==16 and not exposed&reserved
assert exposed==set(reg['excluded_document_ids']) and reserved==set(reg['reserved_confirmation_document_ids'])
eligible=set(docs)-exposed-reserved;assert len(eligible)==250 and eligible==set(reg['eligible_document_ids'])
assert reg['cross_split_documents']==prev['cross_split_documents']
oldhash={textsha(docs[i]['text'])for i in exposed|reserved};crosshash={x['normalized_document_sha256']for x in reg['cross_split_documents']};crossids={x['document_id']for x in reg['cross_split_documents']}
draw=obj(D/'draw-plan.json');sel=obj(D/'document-selection.json');assert sha(D/'draw-plan.json')==sel['draw_plan_sha256']
ranked=sorted((hashlib.sha256((draw['salt']+str(i)+'|'+textsha(docs[i]['text'])).encode()).hexdigest(),i)for i in eligible);chosen=ranked[:8]
assert not sel['gold_access_for_new_DEV_selection']
for rank,(key,i)in enumerate(chosen):
 assert sel['documents'][rank]=={'document_rank':rank,'document_id':i,'normalized_document_sha256':textsha(docs[i]['text']),'document_draw_key':key,'role':'dev'}
 assert i not in crossids and textsha(docs[i]['text'])not in oldhash|crosshash
train=rows(D/'train72.jsonl');dev=rows(D/'development24.jsonl');annotations=obj(D/'train-annotations.json');allow=obj(D/'train-allowlist.json')
assert(D/'train72.jsonl').read_bytes()==(S/'legal-transfer/epoch8/train72.jsonl').read_bytes()
assert sha(D/'train72.jsonl')==c['train_data']['sha256']=='d98f05b49ebad6a9cac447238b32aa3f8ccefa1253bdd2d52465bd111403c644'
assert len(train)==len(annotations['records'])==72 and annotations['queries']==72 and annotations['document_groups']==24
assert not annotations['contains_confirmation_data_or_labels'] and annotations['role']=='train'
evidence={a['id']:a for a in annotations['records']};assert len(evidence)==72
assert set(evidence)=={r['id']for r in train}=={r['id']for r in allow['records']}
for row in train:
 a=evidence[row['id']];d=docs[row['provenance']['document_id']];hyp=row['provenance']['hypothesis_id'];ann=d['annotation_sets'][0]['annotations'][hyp]
 assert row['split']=='train' and row['input']['state']==d['text'] and int(row['source_group'].rsplit(':',1)[1])in exposed
 assert a=={'id':row['id'],'input_sha256':row['input_sha256'],'source_group':row['source_group'],'hypothesis_id':hyp,'original_threeway_label':ann['choice'],'evidence_spans':[d['spans'][i]for i in ann['spans']],'evidence_span_ids':ann['spans'],'source_document_sha256':hashlib.sha256(d['text'].encode()).hexdigest(),'source_annotation_sha256':hashlib.sha256(canon(ann).encode()).hexdigest()}
 assert row['evaluation']['original_threeway_label']==ann['choice']
 assert row['evaluation']['gold']==('Yes'if ann['choice']=='Entailment'else'No')
 assert hashlib.sha256(canon(row['input']).encode()).hexdigest()==row['input_sha256']
assert len(dev)==24 and sha(D/'development24.jsonl')==c['development']['sha256']=='b33c63e727b2990b2efea24234af5b7b9890e4b0ed2634534d4e1e942ca9a86e'
assert [r['provenance']['document_id']for r in dev]==[i for _,i in chosen for hyp in draw['hypotheses']]
for row in dev:
 d=docs[row['provenance']['document_id']];hyp=row['provenance']['hypothesis_id'];ann=d['annotation_sets'][0]['annotations'][hyp];inp=row['input'];q=inp['questions']['decision'];positive=source['labels'][hyp]['hypothesis']
 assert row['split']=='dev' and set(inp)=={'state','questions'} and inp['state']==d['text']
 assert q['type']=='choice' and q['criteria']=={'Yes':positive,'No':'The agreement does not establish the following: '+positive}
 assert row['evaluation']['original_threeway_label']==ann['choice'] and row['evaluation']['gold']==('Yes'if ann['choice']=='Entailment'else'No')
 assert hashlib.sha256(canon(inp).encode()).hexdigest()==row['input_sha256']
 assert hashlib.sha256(norm(canon(inp)).encode()).hexdigest()==row['normalized_input_sha256']
assert not({r['source_group']for r in dev}&{r['source_group']for r in train})
assert sha(ROOT/c['confirmation']['path'])=='850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50'
assert sha(D/'confirmation-allowlist.json')==c['confirmation']['allowlist_sha256']
assert not obj(D/'confirmation-allowlist.json')['contains_labels_or_inputs']
for role in ['train_data','train_annotations','train_allowlist','development']:
 assert sha(ROOT/c[role]['path'])==c[role]['sha256']
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'data_contract_sha256':sha(D/'data-contract.json'),'source_manifest_sha256':sha(D/'source-manifest.json'),'manifest_pins_verified':len(manifest['files']),'reused_TRAIN72_byte_identical':True,'TRAIN24groups_already_exposed':True,'TRAIN_sidecar_sha256':sha(D/'train-annotations.json'),'all72annotation_gold_span_offsets_source_and_annotationhashes_verified':True,'TRAIN_sidecar_contains_only_exact72TRAINqueries_noDEV_CONF':True,'new_DEV24_sha256':sha(D/'development24.jsonl'),'new_DEV_groups':[i for _,i in chosen],'new_DEV_group_and_normalized_fulltext_disjoint_prior157_plus_reserved16_and_officialdev_test':True,'text_only_newDEV_draw_before_gold_projection_verified':True,'eligible_unreserved_before':250,'unreserved_remaining_after_draw':242,'CONF48_preserved_sha256':c['confirmation']['sha256'],'confirmation_model_unused_and_not_part_of_fit':True,'no_current_confirmation_labels_read_for_this_dataaudit':True,'calibration_queries':0,'limitations':'Inherited historical77 semanticexclusions; exactsource/group/normalizedtext checks do not ruleout fuzzyversions or upstream pretrainingcontamination. SourceTRAINreused, notfreshbenchmark.','auditor_real_TRAIN_fits_model_native_paid_calls':0}
out=O/'data-independent-v1.json'
with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'sha256':sha(out),'DEVgroups':proof['new_DEV_groups']}))
