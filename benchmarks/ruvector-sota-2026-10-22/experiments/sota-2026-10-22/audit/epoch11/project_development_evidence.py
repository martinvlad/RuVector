from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
O=Path(__file__).resolve().parent;S=O.parents[1];P=S/'epoch11/project';study=P/'experiments/sota-2026-10-22/epoch11'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records=[json.loads(x) for x in (study/'runs/development/records.jsonl').read_text().splitlines()];dev=[r for r in records if r['measured_phase']=='development'];assert len(dev)==24 and len({r['source_group'] for r in dev})==8
assert not (study/'runs/confirmation').exists(); assert not (study/'runs/confirmation/popen-attempt.json').exists()
source=S/'legal-transfer/epoch3/sources/original-train.json';assert sha(source)=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5';docs={d['id']:d for d in json.loads(source.read_text())['documents']};result=[]
for r in dev:
 d=docs[r['provenance']['document_id']];assert d['text']==r['input']['state'];a=d['annotation_sets'][0]['annotations'][r['provenance']['hypothesis_id']];assert a['choice']==r['evaluation']['original_threeway_label'];result.append({'id':r['id'],'source_group':r['source_group'],'hypothesis_id':r['provenance']['hypothesis_id'],'gold_threeway':a['choice'],'annotation_spans':[d['spans'][i] for i in a['spans']],'scope':'Postrun annotation exposure for this already-consumed DEV query only; never runtime input or semantic sufficiency proof.'})
p=O/'development-evidence-projection-v1.json';assert not p.exists();p.write_text(json.dumps({'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(source),'saved_DEV_records_sha256':sha(study/'runs/development/records.jsonl'),'queries':24,'document_groups':8,'only_consumed_DEV_hypotheses':True,'confirmation_records_or_labels_included':False,'records':result},indent=2)+'\n');print(json.dumps({'sha256':sha(p),'queries':24}))
