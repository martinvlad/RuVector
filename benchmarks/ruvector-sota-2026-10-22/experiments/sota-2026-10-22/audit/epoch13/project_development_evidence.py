"""Expose only consumed DEV annotations; never access reserved CONF annotations."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
O=Path(__file__).resolve().parent;S=O.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def obj(p):return json.loads(p.read_text())
sourcepath=S/'legal-transfer/epoch3/sources/original-train.json';assert sha(sourcepath)=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
devpath=S/'legal-transfer/epoch13/development24.jsonl';dev=[json.loads(x)for x in devpath.read_text().splitlines()];actual=[json.loads(x)for x in(S/'epoch13/runs/development/records.jsonl').read_text().splitlines()];assert [x['id']for x in actual]==[x['id']for x in dev]
allow=obj(S/'legal-transfer/epoch13/confirmation-allowlist.json');assert not({x['source_group']for x in allow['records']}&{x['source_group']for x in dev})
source=obj(sourcepath);ids={x['provenance']['document_id']for x in dev};docs={d['id']:d for d in source['documents']if d['id']in ids};rows=[]
for r in dev:
 doc=docs[r['provenance']['document_id']];ann=doc['annotation_sets'][0]['annotations'][r['provenance']['hypothesis_id']];assert doc['text']==r['input']['state'] and ann['choice']==r['evaluation']['original_threeway_label']
 rows.append({'id':r['id'],'source_group':r['source_group'],'input_sha256':r['input_sha256'],'source_split':'train','document_id':doc['id'],'hypothesis_id':r['provenance']['hypothesis_id'],'source_state_sha256':hashlib.sha256(doc['text'].encode()).hexdigest(),'original_threeway_label':ann['choice'],'original_gold_span_ids':ann['spans'],'original_gold_character_spans':[doc['spans'][i]for i in ann['spans']]})
result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'scope':'Only24 completed permanentlyexposed DEV queries/8groups; exact original annotation character spans and label for saved-output diagnostics only, never fresh confirmation. Candidate may join state from consumed records. No reserved CONF labels or evidence accessed.','source_revision':'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9','source_train_sha256':sha(sourcepath),'DEV_sha256':sha(devpath),'actual_records_sha256':sha(S/'epoch13/runs/development/records.jsonl'),'source_license':'OriginalContractNLI CC-BY4 attribution/license preserved.','queries':len(rows),'document_groups':len(ids),'records':rows,'reserved_confirmation_annotations_accessed':False,'model_native_session_or_fit_calls':0}
out=O/'dev-annotation-spans-v1.json'
with out.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'sha256':sha(out),'queries':len(rows),'groups':len(ids)}))
