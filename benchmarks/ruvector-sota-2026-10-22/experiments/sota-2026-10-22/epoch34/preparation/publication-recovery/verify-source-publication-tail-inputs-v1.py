"""SOURCE publication tail metadata checks; never calls Git/model/native/gold.

The only write entry point is an exclusive outside-project tail intent after
hash-bound independent approval. No source, control, staged payload, WAL or
request file is changed by this module.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat

W=Path('/workspace/ruvector-epoch34-047dbc740dc2')
R=W/'project'
E=R/'experiments/sota-2026-10-22/epoch34'
A=Path('/workspace/ruvector-e34-independent-audit')
OWN=Path('/workspace/ruvector-e34-publication-impl')
SELF=OWN/'verify-source-publication-tail-inputs-v1.py'
HELPER=OWN/'resume-source-publication-tail-v1.js'
APPROVAL=A/'source-publication-tail-independent-v1.json'
INTENT=W/'source-publication-tail-intent-v1.json'
EXECUTION=W/'source-publication-tail-execution-v1.json'
PARENT='eafd332309fef5873086cf66c911b1787c320820'
PARENT_ROOT='821b12fe6f0608aef0afe1dd77b27da3aa6f94b1'
PARENT_BENCH='889dcddc771c8712f6210a2a40fa9cb3df20a02d'
PARENT_SCOPE='f229146613b61b3ca6b38cf8356d428efcf02802'
CREATED={'root':'e8093d1ac7cf51182f7e74cd15bca110b2cd65a1',
         'bench':'bc3e85292fb9397791f3185ee532002bbea37efc',
         'scope':'ef33a23a99eafea16a3526ab6de2065db398b4f6'}
REPO='ruvnet/RuVector'
SCOPE='benchmarks/ruvector-sota-2026-10-22/'
COMMIT_ID='e34-source-commit'
REF_ID='e34-source-ref'
COMMIT_MESSAGE='benchmarks: freeze epoch34 lexical-anchor native-complement NLI source and engineering-gated DEV roles'
WAL_SHA='41b3075f18364ff6c5257bb6021684aaa8009663b4658248080059149396b5a2'
PINS={
 W/'mutation-journal.jsonl':(11319,WAL_SHA),
 W/'controller.js':(3571,'9837cf7e16c5210af1a8a8b0ade1d89e2c1dadb767b042a3464ca949fa42f7b3'),
 E/'preparation/reviewed_publish_phase.js':(12009,'d3d75b8b90acec78258291a2ef6d78dbc3b79291ea7a6c2896c87fe996277ead'),
 E/'plan.json':(61282,'53ea8a9341154b3a0612712c7e73fd56d56fba279bd4ec6343471f2c5e052839'),
 E/'source-freeze.json':(41154,'b9add85c349b8004141054dbadc15bce08338d6c187f53e9b6130323e304e0e9'),
 W/'stage-source/metadata.json':(64890,'d5b92f29be2f18e85ccff3001e0364d587dde0d0caa177f4743b21c34e7ad9a3'),
 W/'stage-source/expected-leaves.json':(914051,'bc8e6a5bfd60cc1eea92ced7fe8508f692117dfd6455c9335bece7f658859632'),
 W/'controls-source/ACTIVE_RUN.json':(1617,'2589dd5f07a99b57a15dc04cb54b27e54bfcc7992bc3b5a07b8083a765962249'),
 W/'controls-source/CONTINUATION.json':(233626,'0550732771dfe07a61d8f318cec43cb7b45902d95f061e4dfbae583bf382eb99'),
 W/'controls-source/CHECKPOINT_MANIFEST.json':(1086301,'4d87b4fcf7fa71061e143868e0b8f2fede634da50990e60aa2b06d0d63dcdba7'),
 W/'baseline-0.json':(9350,'941e0b2050a1dcd5ce451104106240431e939db64966d4ff2cb5fd8fee61b478'),
 W/'baseline-1.json':(2962,'54d47c5942b2cbf26f0459408d57f1273779533b42be5c8a1c7f0b72049bfab2'),
 W/'source-created-root.json':(9350,'b2b363233e7908b19c4cdf94b5596a82644a396150e91c65d7f3e0a5d469612d'),
 W/'source-created-bench.json':(2962,'5b90e95d3c791f3c1501ceaa25651e7e7f8d05c655d3823b16530d4b17ffec40'),
 W/'source-created-scope.json':(1551050,'3faa7c2117a2df8628e145ccd73cedb9010fcb350a120949ed565e36f2ca0472'),
 W/'source-publication-interruption-v1.json':(1205,'cf41a52143d626465d2bd112a24d05883681a3963c6726031e75929618818579'),
 A/'source-stage-independent-v1.json':(3211,'42ede904e8f7ad49e64b8223725b13f4889d867d34f87e4ac262e44baa34cd63'),
 A/'source-created-objects-independent-v1.json':(5459,'d4e4174c4c01283f39949f8ec98a1bd6bf5fa0cb30524b8240e7164db4d79c27'),
}

def require(value,reason):
 if not value:raise ValueError(reason)

def same(left,right):
 if type(left)is not type(right):return False
 if isinstance(left,dict):return set(left)==set(right)and all(same(left[k],right[k])for k in left)
 if isinstance(left,list):return len(left)==len(right)and all(same(a,b)for a,b in zip(left,right))
 return left==right

def canonical(path):
 p=Path(path).absolute();require(p==p.resolve()and not any(q.is_symlink()for q in(p,*p.parents)),'Canonical non-symlink path required');return p

def file_ref(path,expected=None):
 p=canonical(path);require(stat.S_ISREG(p.lstat().st_mode),'Regular metadata/source file required');b=p.read_bytes();row={'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 if expected is not None:require((row['bytes'],row['sha256'])==tuple(expected),'Pinned byte identity changed: '+str(p))
 return row

def parse(path):return json.loads(canonical(path).read_bytes())

def safe_relative(value):
 require(isinstance(value,str)and value and not Path(value).is_absolute()and'\\'not in value and not any(p in('','.','..')for p in value.split('/')),'Unsafe metadata relative path');return value

def git_tree_sha(tree):
 require(tree.get('truncated')is False and isinstance(tree.get('tree'),list),'Full actual Git tree required');entries=[];seen=set()
 for row in tree['tree']:
  n=row['path'];require('/'not in n and n not in seen,'Unique immediate Git names required');seen.add(n)
  d=row['type']=='tree';mode='40000'if d else row['mode'];require(row['type']in('tree','blob','commit')and re.fullmatch('[0-9a-f]{40}',row['sha']or''),'Invalid Git object entry')
  entries.append((n.encode()+(b'/'if d else b''),mode.encode()+b' '+n.encode()+b'\0'+bytes.fromhex(row['sha'])))
 body=b''.join(x[1]for x in sorted(entries));return hashlib.sha1(b'tree '+str(len(body)).encode()+b'\0'+body).hexdigest()

def check_siblings(tree,baseline,changed,replacement):
 require(len(tree['tree'])==len(baseline['tree']),'Sibling count changed')
 actual={x['path']:x for x in tree['tree']};require(len(actual)==len(tree['tree']),'Duplicate actual tree entries')
 for old in baseline['tree']:
  now=actual.get(old['path']);require(now is not None and now['mode']==old['mode']and now['type']==old['type']and now['sha']==(replacement if old['path']==changed else old['sha']),'Sibling identity changed')

def check_wal(rows,meta,requests=W/'mutation-requests',stage=W/'stage-source'):
 ids=['e34-lease-cont-blob','e34-lease-tree','e34-lease-commit','e34-lease-ref']+[f'e34-source-blob-{i}'for i in range(6)]+[f'e34-source-tree-{i}'for i in range(10)]
 require(len(rows)==40 and len(ids)==20,'Exactly40 existing WAL rows/20 pairs required')
 require({p.name for p in canonical(requests).iterdir()}=={n+'.json'for n in ids},'Only20 resolved request files may exist; commit/ref must be unused')
 pairs={}
 for i,identifier in enumerate(ids):
  intent,response=rows[2*i:2*i+2]
  require(intent.get('id')==response.get('id')==identifier and intent.get('phase')=='intent'and response.get('phase')=='response'and intent.get('kind')==response.get('kind')and intent.get('owner')==response.get('owner')==100799,'Exact ordered owner-bound WAL pair required')
  require(response.get('payload',{}).get('ok')is True,'Uncertain/failed external mutation; stop')
  request=canonical(requests)/(identifier+'.json');require(same(intent['payload'],file_ref(request)),'Persisted request args differ from WAL intent')
  args=parse(request);require(args.get('repository_full_name')==REPO,'Wrong repository in retained mutation');pairs[identifier]=(args,response['payload']['result'],intent['kind'])
 require(len(meta['large_blob_requests'])==6 and len(meta['create_tree_groups'])==10,'Exact staged6blob10tree object budget required')
 for i,row in enumerate(meta['large_blob_requests']):
  n=safe_relative(row['file']);p=canonical(stage)/n;file_ref(p,(row['bytes'],row['sha256']));args,result,kind=pairs[f'e34-source-blob-{i}'];require(kind=='mcp__codex_apps__github_create_blob'and same(args,{'repository_full_name':REPO,**parse(p)})and result.get('sha')==row['expected_blob_sha1'],'Completed blob response/request is not exact staged object')
 prior=PARENT_ROOT
 for i,row in enumerate(meta['create_tree_groups']):
  p=canonical(stage)/safe_relative(row['file']);file_ref(p,(row['bytes'],row['sha256']));args,result,kind=pairs[f'e34-source-tree-{i}'];require(kind=='mcp__codex_apps__github_create_tree'and same(args,{'repository_full_name':REPO,'base_tree_sha':prior,**parse(p)}),'Completed tree request differs from staged ordered chain')
  prior=result.get('sha');require(isinstance(prior,str)and re.fullmatch('[0-9a-f]{40}',prior),'Invalid completed tree response')
 require(prior==CREATED['root'],'Last completed object is not the exact known created root')
 return {'WAL_rows':40,'successful_pairs':20,'SOURCE_blob_pairs':6,'SOURCE_tree_pairs':10,'uncertain_mutations':0,'unused_tail_ids':[COMMIT_ID,REF_ID]}

def guard_held(plan):
 name='experiments/sota-2026-10-22/epoch34/preparation/mutation_guard.py';pin=next(row for row in plan['pins']if row['path']==name);file_ref(W/'mutation_guard.py',(pin['bytes'],pin['sha256']))
 spec=importlib.util.spec_from_file_location('source_tail_hash_bound_guard',W/'mutation_guard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);owner=m.guard();require(owner['pid']==100799 and owner['startticks']==22293151,'Wrong live guardian');return {'held':True,'pid':owner['pid'],'ticks':owner['startticks']}

def verify_all():
 pinned=[file_ref(path,expected)for path,expected in PINS.items()]
 meta=parse(W/'stage-source/metadata.json');require(meta['stage']=='source'and meta['scope']==SCOPE and meta['publication_parent']==PARENT and meta['source_plan_sha256']=='53ea8a9341154b3a0612712c7e73fd56d56fba279bd4ec6343471f2c5e052839'and meta['expected_Git_leaves']==5096,'Wrong exactSOURCE stage')
 require(meta['CAS_guards']=={'expected_root_tree':PARENT_ROOT,'expected_benchmarks_tree':PARENT_BENCH,'expected_scope_tree':PARENT_SCOPE,'expected_branch_sha':PARENT,'force':False},'Exact nonforce parent CAS guard required')
 proof=parse(A/'source-stage-independent-v1.json');require(proof.get('checks_passed')is True and proof['stage']==str(W/'stage-source')and proof['manifest_sha256']==PINS[W/'stage-source/metadata.json'][1]and proof['manifest_bytes']==64890,'Independent actualSOURCEstage proof required')
 certainty=parse(A/'source-created-objects-independent-v1.json');require(certainty.get('checks_passed')is True,'Independent exact object/absence certainty proof required')
 failure=parse(W/'source-publication-interruption-v1.json');require(failure['status']=='KNOWN_LOCAL_READ_FAILURE_BEFORE_COMMIT_OR_REF'and failure['uncertain_mutations']==0 and failure['SOURCE_commit_or_ref_intents']==0 and failure['actual_branch_head_rechecked']==PARENT,'Interruption certainty changed')
 plan=parse(E/'plan.json');require(plan['publication_parent']==PARENT and len(plan['pins'])==195 and len({x['path']for x in plan['pins']})==195,'Exactly195 frozen source pins required')
 for row in plan['pins']:file_ref(R/safe_relative(row['path']),(row['bytes'],row['sha256']))
 cp=parse(W/'controls-source/CHECKPOINT_MANIFEST.json');require(len(cp['project_files'])==5022 and len({x['path']for x in cp['project_files']})==5022,'ExactSOURCECP5022 identities required')
 for row in cp['project_files']:file_ref(R/safe_relative(row['path']),(row['bytes'],row['sha256']))
 rows=[json.loads(line)for line in(W/'mutation-journal.jsonl').read_text().splitlines()];wal=check_wal(rows,meta)
 oldroot,oldbench,root,bench,scope=[parse(W/name)for name in('baseline-0.json','baseline-1.json','source-created-root.json','source-created-bench.json','source-created-scope.json')]
 require(len(oldroot['tree'])==44 and len(oldbench['tree'])==13,'Exact44root/13bench baseline entries required')
 for tree,expected in [(oldroot,PARENT_ROOT),(oldbench,PARENT_BENCH),(root,CREATED['root']),(bench,CREATED['bench'])]:require(tree['sha']==expected==git_tree_sha(tree),'Actual parent/created immediate tree identity changed')
 check_siblings(root,oldroot,'benchmarks',CREATED['bench']);check_siblings(bench,oldbench,'ruvector-sota-2026-10-22',CREATED['scope'])
 expected=parse(W/'stage-source/expected-leaves.json');keys=('path','mode','type','sha','size');expected_map={r['path']:{k:r[k]for k in keys}for r in expected['files']};actual=[r for r in scope['tree']if r['type']!='tree'];require(scope.get('truncated')is False and scope['sha']==CREATED['scope']and len(actual)==len(expected_map)==5096 and len({r['path']for r in actual})==5096 and all(same({k:r[k]for k in keys},expected_map[r['path']])for r in actual),'All5096 exact full Git tuples required')
 require(not any(os.path.lexists(p)for p in(INTENT,EXECUTION,W/'publication-source.json',W/'mutation-requests'/f'{COMMIT_ID}.json',W/'mutation-requests'/f'{REF_ID}.json')),'Tail already attempted/published or commit/ref request exists; no replay')
 return {'checks_passed':True,'phase':'source','parent':PARENT,'created_trees':CREATED,'expected_Git_leaves':5096,'all195source_pins_unchanged':True,'CP_rows_verified':5022,'siblings_verified':{'root_nonbench':43,'bench_nonscope':12},'guardian':guard_held(plan),'WAL':wal,'input_pins':pinned,'model_native_tokenizer_gold_Git_calls':0}

def approved():
 v=parse(APPROVAL);require(v.get('checks_passed')is True and v.get('helper')==file_ref(HELPER)and v.get('local_validator')==file_ref(SELF),'Hash-bound independent tail source approval required');return file_ref(APPROVAL)

def completed_wal(commit):
 require(isinstance(commit,str)and re.fullmatch('[0-9a-f]{40}',commit),'Exact created SOURCE commit SHA required');lines=(W/'mutation-journal.jsonl').read_bytes().splitlines(keepends=True)
 require(len(lines)==44 and hashlib.sha256(b''.join(lines[:40])).hexdigest()==WAL_SHA,'Old40WALrows changed or tail is not exactly4newrows');rows=[json.loads(line)for line in lines[40:]]
 expected=[(COMMIT_ID,'mcp__codex_apps__github_create_commit',{'repository_full_name':REPO,'parent_sha':PARENT,'tree_sha':CREATED['root'],'message':COMMIT_MESSAGE}),(REF_ID,'mcp__codex_apps__github_update_ref',{'repository_full_name':REPO,'branch_name':SCOPE.rstrip('/'),'expected_sha':PARENT,'force':False,'sha':commit})]
 for i,(identifier,kind,args)in enumerate(expected):
  intent,response=rows[2*i:2*i+2];require(intent.get('id')==response.get('id')==identifier and intent.get('kind')==response.get('kind')==kind and intent.get('phase')=='intent'and response.get('phase')=='response'and intent.get('owner')==response.get('owner')==100799 and response.get('payload',{}).get('ok')is True,'Tail WAL pair uncertain or differs')
  p=W/'mutation-requests'/(identifier+'.json');require(same(intent['payload'],file_ref(p))and same(parse(p),args),'Tail request args/pin differ')
  if i==0:require(response['payload']['result'].get('sha')==commit,'Created commit response differs')
 require(os.path.lexists(INTENT),'Exclusive tail intent missing')
 return {'WAL_rows':44,'successful_pairs':22,'prior40rows_unchanged':True,'tail_commit_pairs':1,'tail_ref_pairs':1,'uncertain_mutations':0}

def write_new(path,value):
 p=canonical(path);require(not os.path.lexists(p),'Exclusive new tail receipt required')
 with p.open('x')as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def main():
 cli=argparse.ArgumentParser();cli.add_argument('mode',choices=('preflight','intent','postflight'));cli.add_argument('--observations');cli.add_argument('--commit');args=cli.parse_args();require(Path(__file__).absolute()==SELF,'Exact reviewed validator source required');approval=approved()
 if args.mode=='postflight':print(json.dumps(completed_wal(args.commit),sort_keys=True));return
 result=verify_all()
 if args.mode=='intent':
  require(args.observations is not None,'Actual fresh connectedGit observations required');o=json.loads(base64.b64decode(args.observations,validate=True));require(o.get('actual_parent_head')==PARENT and o.get('created_trees')==CREATED and o.get('full_tuples_verified')==5096 and all(isinstance(o.get(k),str)and re.fullmatch('[0-9a-f]{40}',o[k])for k in('read_only_main_before','read_only_main_before_tail')),'Fresh actual Git observations differ')
  receipt={'schema_version':1,'epoch':34,'phase':'source','tail_only':True,'reserved_unused_mutations':[COMMIT_ID,REF_ID],'forbidden_replays':['blob','tree','publishPhase'],'before_tail_API_calls':True,'approval':approval,'helper':file_ref(HELPER),'local_validator':file_ref(SELF),'preflight':result,'actual_connected_Git_observations':o,'created_at':datetime.now(timezone.utc).isoformat(),'further_tail_attempts':0}
  write_new(INTENT,receipt);result={'intent':file_ref(INTENT),'preflight':result}
 print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
