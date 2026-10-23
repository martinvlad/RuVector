"""Rebuild only the frozen epoch11 DEV projection. Never read confirmation labels."""
from pathlib import Path
import argparse,hashlib,json
HERE=Path(__file__).resolve().parent
SOURCE_SHA='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
LABELS={'Entailment':'Yes','Contradiction':'No','NotMentioned':'No'}
INSTRUCTION='Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def norm(t):return ' '.join(t.casefold().split())
def select(source_path):
 plan=json.loads((HERE/'draw-plan.json').read_text());reg=json.loads((HERE/'eligibility-manifest.json').read_text());selection=json.loads((HERE/'document-selection.json').read_text())
 if sha(source_path)!=SOURCE_SHA or plan['source_sha256']!=SOURCE_SHA or sha(HERE/'eligibility-manifest.json')!=plan['eligibility_manifest_sha256']:raise ValueError('Pinned source/registry changed')
 source=json.loads(Path(source_path).read_text());docs={d['id']:d for d in source['documents']};old=set(reg['excluded_document_ids']);reserved=set(reg['reserved_confirmation_document_ids']);eligible=set(docs)-old-reserved
 if len(docs)!=423 or len(old)!=165 or len(reserved)!=16 or old&reserved or len(eligible)!=242 or eligible!=set(reg['eligible_document_ids']):raise ValueError('Exposed/reserved/eligible identities changed')
 cross_ids={x['document_id'] for x in reg['cross_split_documents']};cross_hashes={x['normalized_document_sha256'] for x in reg['cross_split_documents']};blocked_hashes=set(reg['old_and_reserved_normalized_document_sha256'])|cross_hashes
 ranked=[]
 for i in eligible:
  d=docs[i];h=hashlib.sha256(norm(d['text']).encode()).hexdigest()
  if i in cross_ids or h in blocked_hashes:raise ValueError('Cross-split/prior/reserved text or identity collision')
  k=hashlib.sha256((plan['salt']+str(i)+'|'+h).encode()).hexdigest();ranked.append((k,i,h))
 chosen=sorted(ranked)[:8]
 replay=[{'document_rank':j,'document_id':i,'normalized_document_sha256':h,'document_draw_key':k,'role':'dev'} for j,(k,i,h) in enumerate(chosen)]
 if selection['draw_plan_sha256']!=sha(HERE/'draw-plan.json') or replay!=selection['documents'] or selection['gold_access_for_new_DEV_selection'] is not False:raise ValueError('Frozen label-independent roles changed')
 return plan,source,chosen

def draw(source_path):
 plan,source,chosen=select(source_path);docs={d['id']:d for d in source['documents']};out=[]
 # Identity/role freeze has been verified. Only chosen DEV labels are projected.
 for j,(key,i,h) in enumerate(chosen):
  d=docs[i]
  if len(d['annotation_sets'])!=1:raise ValueError('Ambiguous source annotation')
  for hyp in plan['hypotheses']:
   positive=source['labels'][hyp]['hypothesis'];inp={'state':d['text'],'questions':{'decision':{'type':'choice','instructions':INSTRUCTION,'criteria':{'Yes':positive,'No':'The agreement does not establish the following: '+positive}}}};label=d['annotation_sets'][0]['annotations'][hyp]['choice']
   out.append({'id':f'original-contractnli:train:epoch11:dev:{i}:{hyp}','split':'dev','source':'stanfordnlp/contract-nli@eced6528dd3c1d14d73f9a87df8f7bdbc03126f9/train.json','source_group':'original-contractnli:'+str(i),'input':inp,'evaluation':{'type':'choice','gold':LABELS[label],'labels':['Yes','No'],'source_family':hyp,'group':'original-contractnli:'+str(i),'gold_distribution':None,'original_threeway_label':label},'input_sha256':hashlib.sha256(canonical(inp).encode()).hexdigest(),'normalized_input_sha256':hashlib.sha256(norm(canonical(inp)).encode()).hexdigest(),'provenance':{'document_id':i,'file_name':d['file_name'],'source_split':'train','hypothesis_id':hyp,'document_draw_key':key,'document_rank':j,'normalized_document_sha256':h,'license':'CC-BY-4.0'},'exposure':'New project-unused DEV for one frozen zero-shot protocol gate only; no fit/calibration. Internal public-source NDApilot, not sealed or pretraining-contamination-proof.'})
 return out

def allow(rows,data_sha):return {'schema_version':1,'role':'dev','queries':len(rows),'document_groups':len({x['source_group'] for x in rows}),'data_sha256':data_sha,'threeway_classes':list(LABELS),'binary_mapping':LABELS,'records':[{'id':x['id'],'input_sha256':x['input_sha256'],'source_group':x['source_group'],'hypothesis_id':x['provenance']['hypothesis_id']} for x in rows],'contains_labels_or_inputs':False,'fit_permitted':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();a.output_dir.mkdir(exist_ok=True);rows=draw(a.source);target=a.output_dir/'development24.jsonl'
 with target.open('x') as f:
  for row in rows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
 with (a.output_dir/'dev-allowlist.json').open('x') as f:f.write(json.dumps(allow(rows,sha(target)),indent=2)+'\n')
 print(json.dumps({'queries':len(rows),'document_groups':len({x['source_group'] for x in rows}),'sha256':sha(target)}))
