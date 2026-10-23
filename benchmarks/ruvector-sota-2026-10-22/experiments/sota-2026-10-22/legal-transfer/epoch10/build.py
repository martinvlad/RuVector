"""Standalone replay of frozen TRAIN reuse, annotations and new DEV; no CONF gold access."""
from pathlib import Path
import argparse,hashlib,json,shutil
HERE=Path(__file__).resolve().parent
SOURCE_SHA='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
TRAIN_SHA='d98f05b49ebad6a9cac447238b32aa3f8ccefa1253bdd2d52465bd111403c644'
LABELS={'Entailment':'Yes','Contradiction':'No','NotMentioned':'No'}
INSTRUCTION='Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def norm(t):return ' '.join(t.casefold().split())
def allow(rows,role,hashv,fit):return {'schema_version':1,'role':role,'queries':len(rows),'document_groups':len({r['source_group'] for r in rows}),'data_sha256':hashv,'threeway_classes':list(LABELS),'binary_mapping':LABELS,'records':[{'id':r['id'],'input_sha256':r['input_sha256'],'source_group':r['source_group'],'hypothesis_id':r['provenance']['hypothesis_id']} for r in rows],'contains_labels_or_inputs':False,'fit_permitted':fit}
def draw(source_path,train_path=None):
 if sha(source_path)!=SOURCE_SHA:raise ValueError('Changed official source')
 plan=load(HERE/'draw-plan.json');registry=load(HERE/'eligibility-manifest.json');selection=load(HERE/'document-selection.json')
 if sha(HERE/'eligibility-manifest.json')!=plan['eligibility_manifest_sha256'] or sha(HERE/'draw-plan.json')!=selection['draw_plan_sha256']:raise ValueError('Changed frozen draw source')
 source=load(source_path);docs={d['id']:d for d in source['documents']};old=set(registry['excluded_document_ids']);reserve=set(registry['reserved_confirmation_document_ids']);eligible=set(docs)-old-reserve
 if (len(docs),len(old),len(reserve),len(eligible))!=(423,157,16,250) or eligible!=set(registry['eligible_document_ids']) or old&reserve:raise ValueError('Changed exclusion identities')
 hashes={i:hashlib.sha256(norm(d['text']).encode()).hexdigest() for i,d in docs.items()};crossids={d['document_id'] for d in registry['cross_split_documents']};crosshashes={d['normalized_document_sha256'] for d in registry['cross_split_documents']}
 ranked=sorted((hashlib.sha256((plan['salt']+str(i)+'|'+hashes[i]).encode()).hexdigest(),i) for i in eligible);chosen=ranked[:8]
 expected=[{'document_rank':j,'document_id':i,'normalized_document_sha256':hashes[i],'document_draw_key':k,'role':'dev'} for j,(k,i) in enumerate(chosen)]
 if expected!=selection['documents']:raise ValueError('Changed label-independent selection/roles')
 selected={i for _,i in chosen};oldhash={hashes[i] for i in old|reserve}
 if selected&(old|reserve|crossids) or {hashes[i] for i in selected}&(oldhash|crosshashes):raise ValueError('Prior or cross-split collision')
 # Gold projection starts only after every document role/draw identity passes.
 train_path=Path(train_path) if train_path else HERE/'train72.jsonl'
 if sha(train_path)!=TRAIN_SHA:raise ValueError('Exact reused TRAIN72 changed')
 train=[json.loads(x) for x in train_path.read_text().splitlines()]
 if len(train)!=72 or len({r['source_group'] for r in train})!=24:raise ValueError('Wrong training denominator')
 annotations=[]
 for row in train:
  i=row['provenance']['document_id'];hyp=row['provenance']['hypothesis_id'];d=docs[i]
  if i not in old or i in selected|reserve or d['text']!=row['input']['state']:raise ValueError('TRAIN role/source leak')
  ann=d['annotation_sets'][0]['annotations'][hyp]
  if ann['choice']!=row['evaluation']['original_threeway_label'] or LABELS[ann['choice']]!=row['evaluation']['gold']:raise ValueError('TRAIN source gold mismatch')
  if hashlib.sha256(canonical(row['input']).encode()).hexdigest()!=row['input_sha256'] or set(row['input'])!={'state','questions'}:raise ValueError('Changed TRAIN inference input')
  spans=[d['spans'][j] for j in ann['spans']]
  if not all(0<=a<b<=len(d['text']) for a,b in spans):raise ValueError('Invalid annotation offsets')
  annotations.append({'id':row['id'],'input_sha256':row['input_sha256'],'source_group':row['source_group'],'hypothesis_id':hyp,'original_threeway_label':ann['choice'],'evidence_spans':spans,'evidence_span_ids':ann['spans'],'source_document_sha256':hashlib.sha256(d['text'].encode()).hexdigest(),'source_annotation_sha256':hashlib.sha256(canonical(ann).encode()).hexdigest()})
 sidecar={'schema_version':1,'role':'train','queries':72,'document_groups':24,'train_data_sha256':TRAIN_SHA,'source_sha256':SOURCE_SHA,'source_commit':'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9','span_units':'Half-open Python character offsets into exact full input.state; annotations are TRAIN-only fit targets, never inference features','target_semantics':'Any-character intersection with annotated goldspans is annotation coverage, not semantic sufficiency or legal absence proof','records':annotations,'contains_confirmation_data_or_labels':False,'native_model_paid_calls':0}
 dev=[]
 for j,(key,i) in enumerate(chosen):
  d=docs[i]
  if len(d['annotation_sets'])!=1:raise ValueError('Ambiguous source annotation')
  for hyp in plan['hypotheses']:
   positive=source['labels'][hyp]['hypothesis'];inp={'state':d['text'],'questions':{'decision':{'type':'choice','instructions':INSTRUCTION,'criteria':{'Yes':positive,'No':'The agreement does not establish the following: '+positive}}}};label=d['annotation_sets'][0]['annotations'][hyp]['choice']
   dev.append({'id':f'original-contractnli:train:epoch10:dev:{i}:{hyp}','split':'dev','source':'stanfordnlp/contract-nli@eced6528dd3c1d14d73f9a87df8f7bdbc03126f9/train.json','source_group':'original-contractnli:'+str(i),'input':inp,'evaluation':{'type':'choice','gold':LABELS[label],'labels':['Yes','No'],'source_family':hyp,'group':'original-contractnli:'+str(i),'gold_distribution':None,'original_threeway_label':label},'input_sha256':hashlib.sha256(canonical(inp).encode()).hexdigest(),'normalized_input_sha256':hashlib.sha256(norm(canonical(inp)).encode()).hexdigest(),'provenance':{'document_id':i,'file_name':d['file_name'],'source_split':'train','hypothesis_id':hyp,'document_draw_key':key,'document_rank':j,'normalized_document_sha256':hashes[i],'license':'CC-BY-4.0'},'exposure':'New project-unused DEV for frozen protocol gate only; no fitting/calibration. Internal public-source NDApilot, not sealed or pretraining-contamination-proof.'})
 return {'train':train,'dev':dev,'annotations':sidecar}
def write(source_path,output,train_path=None):
 result=draw(source_path,train_path);output=Path(output);output.mkdir(parents=True,exist_ok=True)
 train_path=Path(train_path) if train_path else HERE/'train72.jsonl';dest=output/'train72.jsonl'
 with dest.open('xb') as f:f.write(train_path.read_bytes())
 for name,value in [('train-annotations.json',result['annotations']),('train-allowlist.json',allow(result['train'],'train',TRAIN_SHA,True))]:
  with (output/name).open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n')
 with (output/'development24.jsonl').open('x') as f:
  for row in result['dev']:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
 with (output/'dev-allowlist.json').open('x') as f:json.dump(allow(result['dev'],'dev',sha(output/'development24.jsonl'),False),f,indent=2,ensure_ascii=False);f.write('\n')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--train-reference',type=Path);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();x=write(a.source,a.output_dir,a.train_reference);print(json.dumps({'train':len(x['train']),'dev':len(x['dev']),'annotation_records':len(x['annotations']['records']),'confirmation_records_read_or_generated':0,'native_model_paid_calls':0}))
