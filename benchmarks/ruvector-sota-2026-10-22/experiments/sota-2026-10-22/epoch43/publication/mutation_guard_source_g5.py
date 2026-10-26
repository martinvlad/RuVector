"""Append-only E43 once protocol. Any unacknowledged mutation stops later work."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,base64,json,os,re,time
import publication_common as c
from ack_protocol import persist_validated_response
from reserve_bridge import checked_bridge,PARENT

def journal_rows():
 p=c.W/'lease-generation5/source-final-journal.jsonl';return [json.loads(x)for x in c.body(p).splitlines()]if p.exists()else []
def append(v):
 p=c.W/'lease-generation5/source-final-journal.jsonl'
 with p.open('a')as f:f.write(json.dumps(v,sort_keys=True,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
def request_directory():
 p=c.W/'lease-generation5/source-final-requests';p.mkdir(mode=0o700,exist_ok=True)
 d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
 return p
def clean(rows):
 c.require(len(rows)%2==0,'Open earlier intent: stop; no repeated mutation')
 for i in range(0,len(rows),2):
  a,b=rows[i:i+2];c.require(a['phase']=='intent'and b['phase']=='response'and a['id']==b['id']and b['payload'].get('ok')is True,'Earlier uncertain external mutation: stop')
 c.require(len({r['id']for r in rows[::2]})==len(rows)//2,'Repeated external ID')
def load_stage(a):
 stage=c.W/('stage-'+a.phase);p=stage/'metadata.json';raw=c.body(p);m=json.loads(raw);approval=c.parse(a.approval)
 c.require(c.sha(c.body(a.approval))==a.expected_approval_sha,'Approval SHA changed')
 for k in('checks_passed','publication_phase_allowed','source_and_denylist_review_passed'):c.require(approval.get(k)is True,'Independent publication approval missing '+k)
 c.require(approval.get('stage_metadata_sha256')==c.sha(raw)and approval.get('expected_final_root_sha')==m['expected_final_root']and approval.get('phase')==a.phase,'Exact phase and full-tree approval')
 c.require(approval.get('original_blob5_execution')=='UNKNOWN_PERMANENTLY'and approval.get('forbidden_Git_object_sha1')==c.FORBIDDEN,'Permanent previous uncertainty')
 c.require(m['operational_binding_sha256']==c.OPERATIONAL_SHA and approval.get('operational_binding_sha256')==c.OPERATIONAL_SHA,'Exact reviewed current operational binding');c.require(m['epoch']==43 and m['phase']==a.phase and m['source_checkpoint']==c.BASE and m['owner_sha256']==c.OWNER_SHA,'Exact source/phase/owner')
 return stage,m
def stage_request(stage,r):return json.loads(c.checked(stage/c.relative(r['file']),r))
def request_for(stage,m,responses,index):
 n=len(m['blobs']);t=len(m['trees']);kind=('create_blob'if index<n else 'create_tree'if index<n+t else 'create_commit'if index==n+t else 'update_ref')
 if index<n:r=stage_request(stage,m['blobs'][index])
 elif index<n+t:r={'repository_full_name':c.REPO,'base_tree_sha':m['expected_source_root']if index==n else responses[-1]['payload']['result']['sha'],**stage_request(stage,m['trees'][index-n])}
 elif index==n+t:r={'repository_full_name':c.REPO,'parent_sha':m['source_parent'],'tree_sha':responses[-1]['payload']['result']['sha'],'message':m['commit_message']}
 else:r={'repository_full_name':c.REPO,'branch_name':c.BRANCH,'expected_sha':m['source_parent'],'force':False,'sha':responses[-1]['payload']['result']['sha']}
 return 'mcp__codex_apps__github_'+kind,r
def main(a):
 owner=c.held_owner();bridge=checked_bridge();stage,m=load_stage(a)
 c.require(a.phase in('source','final'),'All reserve IDs permanently retired')
 if a.phase=='source':c.require(m['source_parent']==PARENT,'First distinct SOURCE child of independently verified reserve state')
 if a.mode=='guard':return {'held':True,'pid':owner['pid'],'generation':c.OWNER_GENERATION,'phase':a.phase}
 rows=journal_rows();ids=m['mutation_ID_order'];phase_rows=[r for r in rows if r['id']in ids];responses=[r for r in phase_rows if r['phase']=='response'];index=len(responses)
 if a.phase=='final':
  source_refs=[r for r in rows if r['id']=='e43-source-g5-ref'and r['phase']=='response'];source_commits=[r for r in rows if r['id']=='e43-source-g5-commit'and r['phase']=='response']
  c.require(len(source_refs)==len(source_commits)==1 and source_refs[0]['payload']['ok']is True and source_commits[0]['payload']['ok']is True and source_refs[0]['payload']['result']['object']['sha']==source_commits[0]['payload']['result']['sha']==m['source_parent'],'Normal FINAL must extend the sole acknowledged SOURCE commit')
 c.require(a.id in ids and a.id.startswith(m['mutation_ID_prefix']+'-')and re.fullmatch(r'e43-(source|final)-g5-[a-z0-9-]+',a.id),'All retired reserve IDs forbidden; unique current phase ID')
 if a.mode in('reserve','intent'):clean(rows);c.require(index<len(ids)and a.id==ids[index]and not any(r['id']==a.id for r in rows),'No retry/order bypass')
 reqdir=request_directory();p=reqdir/(a.id+'.json')
 if a.mode in('reserve','intent'):
  kind,request=request_for(stage,m,responses,index);c.require(a.kind==kind,'Frozen mutation kind/order');c.validate_request(kind,request)
  if kind.endswith('create_commit'):c.require(request['tree_sha']==m['expected_final_root'],'Commit exact independently reviewed final root')
  if a.mode=='reserve':c.write(p,c.encoded(request));return {'reserved':a.id,'request_file':str(p)}
  c.require(c.same(c.parse(p),request),'Reserved request changed');payload=c.pin(p)
 else:
  prior=[r for r in rows if r['id']==a.id];c.require(len(prior)==1 and prior[0]['phase']=='intent'and rows[-1]['id']==a.id and prior[0]['kind']==a.kind,'Response requires sole last intent')
  raw=base64.b64decode(a.payload,validate=True);blob=next((r for r in m['blobs']if r['id']==a.id),None)
  def record(payload):append({'id':a.id,'phase':a.mode,'kind':a.kind,'time':time.time(),'owner':owner['pid'],'generation':c.OWNER_GENERATION,'publication_phase':a.phase,'payload':payload,'returned_response_file':str(reqdir/(a.id+'.returned-response.json')),'original_blob5_execution':'UNKNOWN_PERMANENTLY'})
  persist_validated_response(reqdir/(a.id+'.returned-response.json'),raw,a.kind,c.parse(p),c.write,record,blob['GitSHA']if blob else None)
  return {'recorded':a.id,'mode':a.mode}
 append({'id':a.id,'phase':a.mode,'kind':a.kind,'time':time.time(),'owner':owner['pid'],'generation':c.OWNER_GENERATION,'publication_phase':a.phase,'payload':payload,'original_blob5_execution':'UNKNOWN_PERMANENTLY'})
 return {'recorded':a.id,'mode':a.mode}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('guard','reserve','intent','response'));p.add_argument('--phase',choices=('source','final'),required=True);p.add_argument('--approval',type=Path,required=True);p.add_argument('--expected-approval-sha',required=True);p.add_argument('--id');p.add_argument('--kind');p.add_argument('--payload');p.add_argument('--operational-binding',type=Path,required=True);p.add_argument('--expected-operational-binding-sha',required=True);a=p.parse_args();c.configure(a.operational_binding,a.expected_operational_binding_sha);print(json.dumps(main(a),sort_keys=True))
