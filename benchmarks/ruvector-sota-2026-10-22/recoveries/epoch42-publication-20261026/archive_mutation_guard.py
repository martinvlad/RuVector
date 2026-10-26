"""New gen3 append-only WAL; never reads/rewrites old mutation as success."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,json,os,base64,re
import recovery_common as c

def stage_request(row):
 p=c.W/'prepared/stage'/c.relative(row['file']);raw=c.body(p);c.need((len(raw),c.sha(raw))==(row['bytes'],row['sha256']),'Frozen stage request changed');return json.loads(raw)

def append(row):
 with (c.W/'recovery-mutation-journal.jsonl').open('a')as f:f.write(json.dumps(row,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
 fd=os.open(c.W,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def main(a):
 owner=c.held_owner();approval=c.body(a.approval);c.need(c.sha(approval)==a.expected_approval_sha,'Approval identity drift');p=json.loads(approval)
 for key in('checks_passed','distinct_archive_transaction_allowed','new_archive_restore_verified','source_and_denylist_review_passed'):c.need(p.get(key)is True,'Independent final recovery approval missing: '+key)
 c.need(p.get('original_blob5_execution')=='UNKNOWN_PERMANENTLY'and p.get('forbidden_Git_object_sha1')==c.FORBIDDEN,'Old UNKNOWN/denylist must remain')
 meta=c.parse(c.W/'prepared/stage/metadata.json');c.need(c.sha(c.body(c.W/'prepared/stage/metadata.json'))==p.get('stage_metadata_sha256')and meta['source_parent']==c.PARENT,'Stage exact identity')
 if a.mode=='guard':return {'held':True,'generation':3,'old_invocation':'UNKNOWN_PERMANENTLY'}
 path=c.W/'recovery-mutation-journal.jsonl';rows=[json.loads(l)for l in c.body(path).splitlines()]if path.exists()else[]
 ids=meta['mutation_ID_order'];c.need(a.id in ids,'Unreviewed recovery ID');responses=[r for r in rows if r['phase']=='response'];prior=[r for r in rows if r['id']==a.id]
 if a.mode in('reserve','intent'):
  c.need(all(r['payload'].get('ok')is True for r in responses)and len(rows)==2*len(responses),'New uncertainty/open intent: STOP')
  c.need(a.id==ids[len(responses)]and not prior,'No retry/duplicate/order bypass')
 requests=c.W/'recovery-requests';requests.mkdir(mode=0o700,exist_ok=True)
 if a.mode=='reserve':
  idx=len(responses);kinds=['mcp__codex_apps__github_create_blob']*len(meta['blobs'])+['mcp__codex_apps__github_create_tree']*len(meta['trees'])+['mcp__codex_apps__github_create_commit','mcp__codex_apps__github_update_ref']
  c.need(a.kind==kinds[idx],'Exact planned tool/order required')
  if idx<len(meta['blobs']):request=stage_request(meta['blobs'][idx])
  elif idx<len(meta['blobs'])+len(meta['trees']):
   k=idx-len(meta['blobs']);request={'repository_full_name':'ruvnet/RuVector','base_tree_sha':meta['expected_source_root']if k==0 else responses[-1]['payload']['result']['sha'],**stage_request(meta['trees'][k])}
  elif a.id.endswith('-commit'):request={'repository_full_name':'ruvnet/RuVector','parent_sha':c.PARENT,'tree_sha':responses[-1]['payload']['result']['sha'],'message':'benchmarks: recover rejected epoch42 checkpoint from reviewed immutable archive; original blob invocation remains UNKNOWN'}
  else:request={'repository_full_name':'ruvnet/RuVector','branch_name':'benchmarks/ruvector-sota-2026-10-22','expected_sha':c.PARENT,'force':False,'sha':responses[-1]['payload']['result']['sha']}
  c.validate_request(a.kind,request,meta);c.write(requests/(a.id+'.reserved'),b'EXCLUSIVE_ONCE\n');c.write(requests/(a.id+'.json'),c.encoded(request));return {'reserved':a.id,'request_file':str(requests/(a.id+'.json'))}
 if a.mode=='intent':
  c.need((requests/(a.id+'.reserved')).is_file(),'Exclusive request not reserved');request=c.parse(requests/(a.id+'.json'));c.validate_request(a.kind,request,meta)
  idx=len(responses)
  if idx<len(meta['blobs']):
   r=meta['blobs'][idx];expected=stage_request(r);c.need(c.same(request,expected),'Different reviewed blob request')
  elif idx<len(meta['blobs'])+len(meta['trees']):
   k=idx-len(meta['blobs']);r=meta['trees'][k];expected=stage_request(r);c.need(c.same(request['tree_elements'],expected['tree_elements']),'Different reviewed treegroup')
   base=meta['expected_source_root']if k==0 else responses[-1]['payload']['result']['sha'];c.need(request['base_tree_sha']==base,'Tree chain differs from acknowledged new objects')
  elif a.id.endswith('-commit'):c.need(request['tree_sha']==responses[-1]['payload']['result']['sha']==p.get('expected_final_root_sha'),'Commit must use independently bound full finalroot and last ACKtree')
  else:c.need(request['sha']==responses[-1]['payload']['result']['sha'],'CAS must use sole ACKcommit')
  raw=c.body(requests/(a.id+'.json'));payload={'path':str(requests/(a.id+'.json')),'bytes':len(raw),'sha256':c.sha(raw)}
 else:
  c.need(len(prior)==1 and prior[0]['phase']=='intent'and rows[-1]['id']==a.id,'Response without unique open intent');payload=json.loads(base64.b64decode(a.payload,validate=True))
 append({'id':a.id,'phase':a.mode,'kind':a.kind,'owner':owner['pid'],'generation':3,'payload':payload,'original_blob5_execution':'UNKNOWN_PERMANENTLY'});return {'recorded':a.id,'phase':a.mode}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('guard','reserve','intent','response'));p.add_argument('--approval',type=Path,required=True);p.add_argument('--expected-approval-sha',required=True);p.add_argument('--id');p.add_argument('--kind');p.add_argument('--payload');print(json.dumps(main(p.parse_args()),sort_keys=True))
