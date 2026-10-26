"""Two-phase E45 once-only guard. No Git, dataset or scientific entrypoint."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,base64,json,os,re,time
import publication_common as c
from ack_protocol import persist_validated_response
from future_response_protocol import completed,response_intent

def namespace():
 p=c.W/'publication';p.mkdir(mode=0o700,exist_ok=True)
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d);return p
def journal_rows():
 p=c.W/'publication/mutation-journal.jsonl';return [json.loads(x)for x in c.body(p).splitlines()]if p.exists()else []
def append(v):
 p=namespace()/'mutation-journal.jsonl'
 with p.open('a')as f:f.write(json.dumps(v,sort_keys=True,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
def request_directory():
 p=namespace()/'requests';p.mkdir(mode=0o700,exist_ok=True)
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d);return p
def clean(rows):completed(rows)
def load_stage(a):
 stage=c.W/('stage-'+a.phase);p=stage/'metadata.json';raw=c.body(p);m=json.loads(raw);approval=c.parse(a.approval)
 c.require(c.sha(c.body(a.approval))==a.expected_approval_sha,'Approval SHA changed')
 for k in('checks_passed','publication_phase_allowed','source_and_denylist_review_passed','dual_unknown_denylist_reviewed'):c.require(approval.get(k)is True,'Independent publication approval missing '+k)
 c.require(approval.get('stage_metadata_sha256')==c.sha(raw)and approval.get('expected_final_root_sha')==m['expected_final_root']and approval.get('phase')==a.phase,'Exact phase and full-tree approval')
 c.require(approval.get('original_blob5_execution')=='UNKNOWN_PERMANENTLY'and approval.get('forbidden_Git_object_sha1')==c.FORBIDDEN,'Permanent previous uncertainty')
 c.require(approval.get('forbidden_Git_objects')==sorted(c.FORBIDDEN_OBJECTS)and m['forbidden_Git_objects']==sorted(c.FORBIDDEN_OBJECTS),'Exact dual-unknown denylist')
 c.require(m['operational_binding_sha256']==c.OPERATIONAL_SHA and approval.get('operational_binding_sha256')==c.OPERATIONAL_SHA,'Exact reviewed current operational binding')
 c.require(m['epoch']==45 and m['phase']==a.phase and m['source_checkpoint']==c.BASE and m['owner_sha256']==c.OWNER_SHA,'Exact source/phase/owner')
 c.require(m['mutation_ID_prefix']=='e45-'+a.phase+'-g10','Exact new E45 phase ID prefix')
 c.require(m['mutation_ID_order']==[r['id']for r in m['blobs']+m['trees']]+[m['mutation_ID_prefix']+'-commit',m['mutation_ID_prefix']+'-ref'],'Exact frozen mutation order')
 return stage,m
def stage_request(stage,r):return json.loads(c.checked(stage/c.relative(r['file']),r))
def request_for(stage,m,responses,index):
 n=len(m['blobs']);t=len(m['trees']);kind=('create_blob'if index<n else 'create_tree'if index<n+t else 'create_commit'if index==n+t else 'update_ref')
 if index<n:r=stage_request(stage,m['blobs'][index])
 elif index<n+t:r={'repository_full_name':c.REPO,'base_tree_sha':m['expected_source_root']if index==n else responses[-1]['payload']['result']['sha'],**stage_request(stage,m['trees'][index-n])}
 elif index==n+t:r={'repository_full_name':c.REPO,'parent_sha':m['source_parent'],'tree_sha':responses[-1]['payload']['result']['sha'],'message':m['commit_message']}
 else:r={'repository_full_name':c.REPO,'branch_name':c.BRANCH,'expected_sha':m['source_parent'],'force':False,'sha':responses[-1]['payload']['result']['sha']}
 return 'mcp__codex_apps__github_'+kind,r

def phase_prefix(rows,m,phase):
 """Validate completed prior phase and exact current prefix, allowing own last intent."""
 ids=m['mutation_ID_order']
 if phase=='source':
  c.require(m['source_parent']==c.BASE,'SOURCE sole parent is fresh actual base');current=rows
 else:
  sr=json.loads(c.checked(m['actual_SOURCE_receipt']['path'],m['actual_SOURCE_receipt']))
  smraw=c.body(c.W/'stage-source/metadata.json');sm=json.loads(smraw)
  c.require(sr.get('epoch')==45 and sr.get('phase')=='source'and sr.get('verified_actual_full_tree')is True and sr.get('commit')==m['source_parent']and sr.get('parent')==c.BASE,'FINAL extends actual acknowledged SOURCE')
  c.require(sr.get('stage_metadata_sha256')==c.sha(smraw)and sm['owner_sha256']==c.OWNER_SHA and sm['operational_binding_sha256']==c.OPERATIONAL_SHA,'Exact actual SOURCE stage and current owner')
  source_ids=sm['mutation_ID_order'];n=2*len(source_ids);c.require(len(rows)>=n,'SOURCE phase not completed');prior=rows[:n];clean(prior)
  c.require([r['id']for r in prior[::2]]==source_ids and all(r['publication_phase']=='source'for r in prior),'Exact completed SOURCE prefix')
  c.require(prior[-1]['payload'].get('fresh_ref',{}).get('object',{}).get('sha')==sr['commit'],'SOURCE receipt agrees with fresh post-CAS reference')
  current=rows[n:]
 whole=len(current)//2
 c.require(whole<=len(ids),'Too many current phase mutations')
 c.require([r['id']for r in current[::2]]==ids[:(len(current)+1)//2],'Exact current phase prefix')
 c.require(all(r['publication_phase']==phase and r['generation']==10 for r in current),'Current phase/generation only')
 for i in range(0,len(current)-1,2):clean(current[i:i+2])
 return current

def raw_result(raw):
 c.require(isinstance(raw,dict)and not raw.get('isError'),'MCP raw return is an error')
 structured=raw.get('structuredContent')
 return json.loads(structured['content'])if isinstance(structured,dict)and isinstance(structured.get('content'),str)else structured

def main(a):
 owner=c.held_owner();stage,m=load_stage(a);rows=journal_rows();phase_rows=phase_prefix(rows,m,a.phase)
 if a.mode=='guard':clean(rows);return {'held':True,'pid':owner['pid'],'generation':c.OWNER_GENERATION,'phase':a.phase}
 ids=m['mutation_ID_order'];responses=[r for r in phase_rows if r['phase']=='response'];index=len(responses)
 c.require(a.id in ids and a.id.startswith(m['mutation_ID_prefix']+'-')and re.fullmatch(r'e45-(source|final)-g10-[a-z0-9-]+',a.id),'Only unique current E45 phase IDs')
 if a.mode in('reserve','intent'):clean(rows);c.require(index<len(ids)and a.id==ids[index]and not any(r['id']==a.id for r in rows),'No retry/order bypass')
 reqdir=request_directory();p=reqdir/(a.id+'.json')
 if a.mode in('reserve','intent'):
  kind,request=request_for(stage,m,responses,index);c.require(a.kind==kind,'Frozen mutation kind/order');c.validate_request(kind,request)
  if kind.endswith('create_tree'):c.require(len(request['tree_elements'])<=32 and len(c.encoded(request))<175904,'Exact tree request caps')
  if kind.endswith('create_commit'):c.require(request['tree_sha']==m['expected_final_root'],'Commit exact independently reviewed full root')
  if a.mode=='reserve':c.write(p,c.encoded(request));return {'reserved':a.id,'request_file':str(p)}
  c.require(c.same(c.parse(p),request),'Reserved request changed');payload=c.pin(p)
 else:
  response_intent(rows,a.id,a.kind);c.require(rows[-1]['publication_phase']==a.phase,'Response matches phase of own current intent')
  raw=base64.b64decode(a.payload,validate=True);payload=json.loads(raw)
  raw_path=reqdir/(a.id+'.raw-tool-return.json');raw_ref=c.pin(raw_path);returned=c.parse(raw_path)
  if payload.get('ok')is True:c.require(c.same(raw_result(returned),payload.get('result')),'Response result differs from complete raw MCP return')
  blob=next((r for r in m['blobs']if r['id']==a.id),None)
  if a.kind.endswith('update_ref')and payload.get('ok')is True:
   fresh=payload.get('fresh_ref');request=c.parse(p);c.require(isinstance(fresh,dict)and fresh.get('ref')=='refs/heads/'+c.BRANCH and fresh.get('object',{}).get('sha')==request['sha'],'Every reference requires fresh matching post-CAS GET')
  def record(value):append({'id':a.id,'phase':'response','kind':a.kind,'time':time.time(),'owner':owner['pid'],'generation':c.OWNER_GENERATION,'publication_phase':a.phase,'payload':value,'returned_response_file':str(reqdir/(a.id+'.returned-response.json')),'raw_tool_return':raw_ref,'original_blob5_execution':'UNKNOWN_PERMANENTLY'})
  persist_validated_response(reqdir/(a.id+'.returned-response.json'),raw,a.kind,c.parse(p),c.write,record,blob['GitSHA']if blob else None)
  return {'recorded':a.id,'mode':a.mode}
 append({'id':a.id,'phase':'intent','kind':a.kind,'time':time.time(),'owner':owner['pid'],'generation':c.OWNER_GENERATION,'publication_phase':a.phase,'payload':payload,'original_blob5_execution':'UNKNOWN_PERMANENTLY'})
 return {'recorded':a.id,'mode':a.mode}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('guard','reserve','intent','response'));p.add_argument('--phase',choices=('source','final'),required=True);p.add_argument('--approval',type=Path,required=True);p.add_argument('--expected-approval-sha',required=True);p.add_argument('--id');p.add_argument('--kind');p.add_argument('--payload');p.add_argument('--operational-binding',type=Path,required=True);p.add_argument('--expected-operational-binding-sha',required=True);a=p.parse_args();c.configure(a.operational_binding,a.expected_operational_binding_sha);print(json.dumps(main(a),sort_keys=True))
