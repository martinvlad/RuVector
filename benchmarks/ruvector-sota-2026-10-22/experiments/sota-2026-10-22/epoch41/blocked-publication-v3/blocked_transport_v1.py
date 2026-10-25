"""Generic E41 tree/history/transport guards, no model/data/scorer execution."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,copy,hashlib,json,re
from blocked_common_v1 import *
P='experiments/sota-2026-10-22/'
E=P+'epoch41/'
KIND='REAL_CONTRACTNLI_MULTI_HYPOTHESIS_CONTEXT_DEV_PILOT'
PHASE='dev'
PLAN_PATH=E+'plan.json'
FREEZE_PATH=E+'source-freeze.json'
BASE_GIT_LEAVES=6875
BASE_SCOPE_TREE='376445ff79b3d51f41fa548daf1b2b4263777f84'
MAX_BLOB_JSON=8384512
MAX_TREE_JSON=175904
LARGE_FILE_BYTES=65536
TUPLE_KEYS=('path','mode','type','sha','size')
FLAGS={'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_SOTA_verified':False,'official_rank':None}
MUTABLE={'active_run','checkpoint_manifest_sha256','prior_published_base_commit','benchmark_refresh'}
FINAL_MUTABLE=MUTABLE|{'execution_observed','epochs','latest_learning','rejection_ledger','next_research_priority','cumulative_budget_ledger'}
def leaf(path,body):
 return {'path':path,'mode':'100644','type':'blob','sha':gitsha(body),'size':len(body)}

def tuple_map(document):
 require(isinstance(document,dict) and isinstance(document.get('files'),list),'Canonical Git file map required')
 require(document.get('scope',SCOPE).rstrip('/')==SCOPE.rstrip('/'),'Wrong Git scope')
 answer={}
 for item in document['files']:
  require(isinstance(item,dict) and set(TUPLE_KEYS)<=set(item),'Incomplete Git tuple')
  row={k:item[k] for k in TUPLE_KEYS};path=row['path']
  require(isinstance(path,str),'Git path must be text')
  if path.startswith(SCOPE):path=path[len(SCOPE):]
  row['path']=relative(path)
  require(row['mode']=='100644' and row['type']=='blob' and re.fullmatch('[0-9a-f]{40}',row['sha'] or '') and type(row['size']) is int and row['size']>=0 and path not in answer,'Invalid/duplicate Git tuple')
  answer[path]=row
 require(CONTROLS<=set(answer),'Original control tuples required')
 return answer

def scope_tree_sha(rows):
 root={}
 for path,row in rows.items():
  node=root;parts=relative(path).split('/')
  for part in parts[:-1]:
   require(part not in node or isinstance(node[part],dict),'Git file/directory collision')
   node=node.setdefault(part,{})
  require(parts[-1] not in node,'Git file/directory collision');node[parts[-1]]=row['sha']
 def digest(node):
  entries=[]
  for name,value in node.items():
   is_dir=isinstance(value,dict);identity=digest(value) if is_dir else value
   entries.append((name.encode()+ (b'/' if is_dir else b''),(b'40000' if is_dir else b'100644')+b' '+name.encode()+b'\0'+bytes.fromhex(identity)))
  body=b''.join(value for _,value in sorted(entries))
  return hashlib.sha1(b'tree '+str(len(body)).encode()+b'\0'+body).hexdigest()
 return digest(root)

def verify_baseline(kit,index):
 require(index.get('source_commit',BASE_COMMIT)==BASE_COMMIT,'Wrong source checkpoint')
 rows=tuple_map(index)
 require(len(rows)==BASE_GIT_LEAVES and scope_tree_sha(rows)==BASE_SCOPE_TREE,'Actual original6875 Git identity required')
 for path,row in rows.items():require(leaf(path,content(kit/path))==row,'Historical Git byte drift: '+path)
 return rows

def checked_review(document,current):
 require(isinstance(document,dict) and isinstance(document.get('files'),list),'Explicit exhaustive review required')
 rows={}
 for row in document['files']:
  require(isinstance(row,dict) and set(row)=={'path','bytes','sha256'},'Canonical review ref required')
  path=relative(row['path']);require(path not in rows,'Duplicate review path');rows[path]=row
 require(set(rows)==set(current),'Review must cover all and only three-root current files')
 for path,body in current.items():require(rows[path]=={'path':path,'bytes':len(body),'sha256':sha(body)},'Review byte drift: '+path)

def checkpoint_extension(old,new,current):
 before,after=cp_rows(old),cp_rows(new)
 require(set(old)<=set(new) and all(k=='project_files' or new[k]==v for k,v in old.items()) and all(k.startswith('epoch41_') for k in set(new)-set(old)),'Historical checkpoint metadata changed')
 require(set(after)==set(before)|set(current),'Checkpoint must cover exactly original and current public files')
 for path,row in before.items():require(after.get(path)==row,'Historical checkpoint row changed: '+path)
 for path,body in current.items():require(after[path]=={'path':path,'bytes':len(body),'sha256':sha(body)},'Current checkpoint byte mismatch: '+path)
 return before,after

def controls_at(path,fallback_kit=None):
 directory(path);names={p.name for p in path.iterdir()}
 require(names<=CONTROLS|{'hashes.json'} and {'CONTINUATION.json','ACTIVE_RUN.json'}<=names,'Unexpected control files')
 out={}
 for name in sorted(CONTROLS):
  source=path/name
  if not source.exists():require(name=='CHECKPOINT_MANIFEST.json' and fallback_kit is not None,'Missing control file');source=fallback_kit/name
  out[name]=content(source);public_text(name,out[name])
 return out

def preserve_history(before,after,mutable):
 require(set(before)<=set(after) and all(k in before or k.startswith('epoch41_') for k in after),'Historical continuation metadata removed/new key outside E41')
 for key,value in before.items():
  if key not in mutable:require(after[key]==value,'Historical continuation field changed: '+key)
 for key in ('used_confirmation_sets','champion','epoch27_data_roles'):
  if key in before:require(after[key]==before[key],'Protected source role/champion changed: '+key)
 if 'exposed_development_sets' in mutable:
  old,new=before.get('exposed_development_sets'),after.get('exposed_development_sets')
  if isinstance(old,list):require(isinstance(new,list) and new[:len(old)]==old,'Historical exposed DEV records changed')
  elif isinstance(old,dict):require(isinstance(new,dict) and all(new.get(k)==v for k,v in old.items()),'Historical exposed DEV map changed')
 if 'cumulative_budget_ledger' in mutable:
  old,new=before.get('cumulative_budget_ledger'),after.get('cumulative_budget_ledger')
  if isinstance(old,dict):require(isinstance(new,dict) and all(new.get(k)==v for k,v in old.items()) and all(k in old or k.startswith('epoch41_') for k in new),'Historical budget ledger changed')

def transport_groups(changed):
 entries=[];blobs=[];groups=[];large_identities={}
 for path,body in sorted(changed.items()):
  text=public_text(path,body);entry={'path':SCOPE+path,'mode':'100644','type':'blob'}
  if len(body)>LARGE_FILE_BYTES:
   payload={'content':text,'encoding':'utf-8'};require(len(encoded(payload))<MAX_BLOB_JSON,'Blob JSON strict cap exceeded')
   identity=gitsha(body)
   if identity in large_identities:require(large_identities[identity]==body,'Refuse unequal large payloads with the same Git blob SHA')
   else:large_identities[identity]=body;blobs.append((path,body,payload))
   entry['sha']=identity
  else:entry['content']=text
  require(len(encoded({'tree_elements':[entry]}))<MAX_TREE_JSON,'Single tree entry strict cap exceeded');entries.append(entry)
 batch=[]
 for entry in entries:
  if len(encoded({'tree_elements':batch+[entry]}))>=MAX_TREE_JSON:require(batch,'Cannot fit tree entry');groups.append(batch);batch=[]
  batch.append(entry)
 if batch:groups.append(batch)
 return blobs,groups

