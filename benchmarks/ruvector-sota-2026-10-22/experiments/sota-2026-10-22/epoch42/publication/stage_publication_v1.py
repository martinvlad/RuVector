"""Generic E42 tree/history/transport guards, no model/data/scorer execution."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,copy,hashlib,json,re
from publication_common_v1 import *
P='experiments/sota-2026-10-22/'
E=P+'epoch42/'
KIND='REAL_CONTRACTNLI_MULTI_HYPOTHESIS_CONTEXT_DEV_PILOT'
PHASE='dev'
PLAN_PATH=E+'plan.json'
FREEZE_PATH=E+'source-freeze.json'
BASE_GIT_LEAVES=binding.BASE_GIT_LEAVES
BASE_SCOPE_TREE=binding.BASE_SCOPE_TREE
MAX_BLOB_JSON=8384512
MAX_TREE_JSON=175904
LARGE_FILE_BYTES=65536
TUPLE_KEYS=('path','mode','type','sha','size')
FLAGS={'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_SOTA_verified':False,'official_rank':None,'benchmark_generalization_claim':False}
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
 require(len(rows)==BASE_GIT_LEAVES and scope_tree_sha(rows)==BASE_SCOPE_TREE,'Actual original Git identity required')
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
 require(set(old)<=set(new) and all(k=='project_files' or same_fact(new[k],v) for k,v in old.items()) and all(k.startswith('epoch42_') for k in set(new)-set(old)),'Historical checkpoint metadata changed')
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
 require(set(before)<=set(after) and all(k in before or k.startswith('epoch42_') for k in after),'Historical continuation metadata removed/new key outside E42')
 for key,value in before.items():
  if key not in mutable:require(same_fact(after[key],value),'Historical continuation field changed: '+key)
 for key in ('used_confirmation_sets','champion','epoch27_data_roles'):
  if key in before:require(same_fact(after[key],before[key]),'Protected source role/champion changed: '+key)
 if 'exposed_development_sets' in mutable:
  old,new=before.get('exposed_development_sets'),after.get('exposed_development_sets')
  if isinstance(old,list):require(isinstance(new,list) and same_fact(new[:len(old)],old),'Historical exposed DEV records changed')
  elif isinstance(old,dict):require(isinstance(new,dict) and all(same_fact(new.get(k),v) for k,v in old.items()),'Historical exposed DEV map changed')
 if 'cumulative_budget_ledger' in mutable:
  old,new=before.get('cumulative_budget_ledger'),after.get('cumulative_budget_ledger')
  if isinstance(old,dict):require(isinstance(new,dict) and all(same_fact(new.get(k),v) for k,v in old.items()) and all(k in old or k.startswith('epoch42_') for k in new),'Historical budget ledger changed')

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

def verify_flags(value):
 for k,v in FLAGS.items():require(same_fact(value.get(k),v),'Forbidden acceptance/promotion/rank: '+k)

def check_phase_main(value,observed):
 require(isinstance(observed,str) and re.fullmatch('[0-9a-f]{40}',observed),'A well-formed read-only main observation is required')
 require(isinstance(value.get('main'),str) and re.fullmatch('[0-9a-f]{40}',value['main']),'Independent parent readback must retain its own point-in-time main observation')

def check_readback(value,phase,parent,trees):
 require(value.get('commit')==parent and(value.get('verified')is True or value.get('verified_actual_full_tree')is True or(value.get('checks_passed')is True and value.get('verified_actual_remote_readback')is True)),'Actual independent parent readback required')
 require(all(value.get(k)==v for k,v in zip(('root','bench','scope'),trees)),'Actual parent trees differ')
 parents=[value[k]for k in ('parent','sole_parent')if k in value];require(parents and all(v==parents[0]for v in parents),'Missing/conflicting actual sole parent')
 require(parent!=BASE_COMMIT,'SOURCE/FINAL must extend scoped planning/source commit')

from phase_contract_v1 import ARMS,PHASE,STATUSES,LIMITS,REMAINING,WINDOWS_PER_CASE_ARM

def checked_ref(root,row,rows=None):
 require(isinstance(row,dict)and set(row)=={'path','bytes','sha256'}and ref(root,row['path'])==row,'Exact current public reference required')
 if rows is not None:require(rows.get(row['path'])==row,'Reference not bound to current checkpoint')
 return row

def checked_plan(root,current,rows,phase):
 pr=ref(root,PLAN_PATH);fr=ref(root,FREEZE_PATH);plan=parse(root/PLAN_PATH);freeze=parse(root/FREEZE_PATH)
 require(plan.get('epoch')==freeze.get('epoch')==42 and plan.get('kind')==freeze.get('kind')==KIND and plan.get('phase')==freeze.get('phase')==PHASE and plan.get('source_checkpoint')==freeze.get('source_checkpoint')==BASE_COMMIT,'Exact E42 source plan/freeze')
 verify_flags(plan);roles=plan.get('data_roles',{});require(set(roles)=={'train','dev','calibration','confirmation'}and all(roles[k]==[]for k in ('train','calibration','confirmation'))and len(roles['dev'])==12 and len({encoded(v)for v in roles['dev']})==12,'Twelve DEV identities only')
 require(plan.get('arms')==ARMS and type(plan.get('actual_NLI_forwards'))is int and plan['actual_NLI_forwards']==72 and type(plan.get('derived_forecasts'))is int and plan['derived_forecasts']==36 and type(plan.get('windows_per_case_arm'))is int and plan['windows_per_case_arm']==WINDOWS_PER_CASE_ARM and plan.get('limits')==LIMITS and plan.get('benchmark_accuracy')is None and plan.get('used_confirmation_identities')==[]and plan.get('official_eligibility')=='HOLD','Exact frozen72window/36mixture design; DEV-only no placement')
 require(plan.get('actual_project')==str(root)and plan.get('guardian_scope')==str(root.parent)and plan.get('source_freeze')==fr,'Exact source root/freeze')
 pins={r['path']:r for r in plan['pins']};require(len(pins)==len(plan['pins']),'Duplicate frozen source')
 for row in pins.values():checked_ref(root,row)
 entries={r['path']:r for r in freeze['entries']};require(len(entries)==len(freeze['entries']),'Duplicate source-freeze entry')
 require(all(pins.get(name)==row for name,row in entries.items())and pins.get(FREEZE_PATH)==fr,'Freeze source unpinned')
 require(freeze.get('external_data_assets')==plan.get('external_data_assets'),'Frozen external data descriptor changed')
 for row in list(plan['required_refs'].values())+[plan['root_contract'],plan['plan_inputs'],plan['source_review']]:checked_ref(root,row,rows);require(pins.get(row['path'])==row,'Required reviewed source unpinned')
 if phase=='source':require(set(entries)==set(current)-{PLAN_PATH,FREEZE_PATH},'All and only current source frozen before measurement')
 else:require(set(entries)<=set(current),'Previously frozen source missing')
 return plan,pr,fr

def checked_final(root,current,rows,cont,prior,plan):
 m=parse(root/(E+'EPOCH_MANIFEST.json'));result=parse(root/(E+'RESULTS.json'))
 require(m.get('epoch')==42 and m.get('kind')==KIND and m.get('phase')==PHASE and m.get('status')in STATUSES,'Current final DEV pilot')
 verify_flags(m);verify_flags(result);require(m.get('all_slots_closed')is True and m.get('phase_remaining')==REMAINING and m.get('used_confirmation_identities')==[]and m.get('benchmark_accuracy')is None and m.get('goal_verified')is False,'All allowances closed, no benchmark/confirmation success')
 require(type(m.get('dev_passed'))is bool and(m['status']=='ACCEPTED_DEV_PILOT_ONLY')is m['dev_passed'],'Consistent DEV-only verdict')
 for key in ('status','dev_passed','actual_execution'):require(result.get(key)==m[key],'Result/manifest factual/verdict projection differs')
 for key in ('plan','source_freeze','root_contract','results','rejection_ledger','learnings','used_identities','source_manifest','qualification_replay','binding','independent_report','physical_closure_report'):checked_ref(root,m.get(key),rows)
 replay=parse(root/m['qualification_replay']['path']);require(all(same_fact(result.get(k),v) for k,v in replay.items()),'Every evaluated field must be retained unchanged')
 closure=parse(root/m['physical_closure_report']['path']);require(closure.get('checks_passed')is True and closure.get('physical_closure_passed')is True and closure.get('source_plan_sha256')==m['plan']['sha256']and m['actual_execution'].get('owned_live_processes_closed')is True,'Known independent physical closure required')
 bound_report=parse(root/m['binding']['path']);require(bound_report.get('publication_binding_checks_passed')is True and bound_report.get('evaluated_integrity_checks_passed')is replay['checks_passed']and bound_report.get('evidence',{}).get('results')==m['results']and bound_report['evidence'].get('qualification_replay')==m['qualification_replay'],'Independent metadata identity binding')
 report=parse(root/m['independent_report']['path']);require(report.get('checks_passed')is True and report.get('publication_allowed')is True and report.get('dev_passed')is m['dev_passed']and report.get('no_raw_third_party_text_in_public_files')is True and report.get('results')==m['results']and report.get('binding')==m['binding']and report.get('closure_report')==m['physical_closure_report'],'Independent final/privacy report')
 now={name:{'path':name,'bytes':len(body),'sha256':sha(body)}for name,body in current.items()}
 require({r['path']:r for r in m['files']}=={name:r for name,r in now.items()if name!=E+'EPOCH_MANIFEST.json'},'No project writes after immutable EPOCH seal')
 source=parse(root/m['source_manifest']['path']);require({r['path']:r for r in source['files']}=={name:r for name,r in now.items()if name not in {E+'EPOCH_MANIFEST.json',E+'SOURCE_MANIFEST.json'}},'Nonrecursive source manifest inventory differs')
 counts=m['cumulative_execution'];require(counts['corpus_attempts']is None and counts['completed_corpus_batches']is None and counts['legacy_native_qualification_process_attempts']==6 and counts['bounded_native_process_attempts']==binding.PRIOR_BOUNDED_NATIVE_PROCESS_ATTEMPTS+m['actual_execution']['worker_attempts']and counts['benchmark_HTTP_successes']==binding.CUMULATIVE_HTTP_SUCCESSES and counts['benchmark_HTTP_failures']==binding.CUMULATIVE_HTTP_FAILURES,'E37 UNKNOWN tail/outer/logical/official request accounting preserved')
 oldobs=prior.get('execution_observed',{});newobs=cont.get('execution_observed',{});require(all(newobs.get(k)==v for k,v in oldobs.items())and all(k in oldobs or k.startswith('epoch42_')for k in newobs),'Old execution history changed')
 require(cont.get('epochs',[])[:-1]==prior.get('epochs',[])and cont['epochs'][-1].get('epoch')==42 and cont['epochs'][-1].get('status')==m['status'],'Append exactly one honest epoch')
 oldledger=parse(root/prior['rejection_ledger']['path']);ledger=parse(root/m['rejection_ledger']['path'])
 for key,value in oldledger.items():require(ledger.get(key,[])[:len(value)]==value if key=='rejections'else same_fact(ledger.get(key),value),'Historical rejection metadata changed')
 require(all(k in oldledger or k.startswith('epoch42_')for k in ledger),'Unreviewed new ledger key')
 expected_added=0 if m['dev_passed']else 1;require(len(ledger['rejections'])==len(oldledger['rejections'])+expected_added,'Exact accepted/rejected record count')
 require(cont.get('epoch42_final',{}).get('manifest')==ref(root,E+'EPOCH_MANIFEST.json')and cont['epoch42_final'].get('status')==m['status'],'Final continuation must point to exact result')


def prepare(args):
 binding.require_bound()
 root,kit,controls,priorcontrols=map(directory,(args.project,args.kit,args.controls,args.priorcontrols));live_owner(root.parent);output=new_output(args.out,(root,kit,controls,priorcontrols))
 for key in ('parent','expected_main','expected_root','expected_bench','expected_scope'):require(re.fullmatch('[0-9a-f]{40}',getattr(args,key)or''),'Exact actual Git identity required')
 proofbytes=content(args.parent_readback);proof=loads(proofbytes);check_phase_main(proof,args.expected_main);check_readback(proof,args.phase,args.parent,(args.expected_root,args.expected_bench,args.expected_scope))
 baseline=verify_baseline(kit,parse(args.source_filemap));current=walk_current(root);checked_review(parse(args.reviewed_files),current)
 prior=controls_at(priorcontrols,kit);bodies=controls_at(controls);oldcp=parse(kit/'CHECKPOINT_MANIFEST.json');require(sha(content(kit/'CHECKPOINT_MANIFEST.json'))==BASE_CP_SHA256,'Exact base CP')
 pcp,pcont,pactive=(loads(prior[k])for k in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'));cp,cont,active=(loads(bodies[k])for k in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'))
 _,rows=checkpoint_extension(oldcp,cp,current);check_history(root,oldcp);preserve_history(pcont,cont,FINAL_MUTABLE if args.phase=='final'else MUTABLE)
 require(cont['active_run']==dict(active,path='ACTIVE_RUN.json')and cont['checkpoint_manifest_sha256']==sha(bodies['CHECKPOINT_MANIFEST.json'])and cont['prior_published_base_commit']==args.parent,'Exact owned control/hash/parent projection')
 owner=active.get('physical_owner',{});require(active.get('run_id')==OWNER_RUN_ID and(owner.get('pid'),owner.get('startticks'),owner.get('lock_inode'))==OWNER_PIN and owner.get('expires_unix')==OWNER_EXPIRES_UNIX,'Exact current owner')
 require(active.get('experiments_active')is False and active.get('native_allowed')==0 and active.get('OS_lock_held')is True and active.get('checkpoint_parent')==args.parent,'Immediate native path closed')
 for key in ('conditional_train_allowed','conditional_calibration_allowed','conditional_engineering_allowed','confirmation_allowed','conditional_confirmation_allowed'):require(type(active.get(key))is int and active[key]==0,'No other scientific allowance')
 plan,pr,fr=checked_plan(root,current,rows,args.phase);require(cont.get('epoch42_frozen_study')=={'plan':pr,'source_freeze':fr},'Exact source control refs')
 if args.phase=='source':
  require(pcp==oldcp and pactive.get('state')=='EPOCH42_PLANNING_LEASE'and active.get('state')=='EPOCH42_SOURCE_FROZEN_DEV_PENDING_ADMISSION'and active.get('work_active')is True and active.get('conditional_dev_allowed')==1,'SOURCE follows planning conditional DEV only')
  require(plan['publication_parent']==args.parent and plan['publication_parent_trees']==dict(zip(('root','bench','scope'),(args.expected_root,args.expected_bench,args.expected_scope))),'Frozen actual source parent/trees')
 else:
  require(all(cp[k]==v for k,v in pcp.items()if k!='project_files')and all(rows.get(k)==v for k,v in cp_rows(pcp).items()),'Previously published source checkpoint changed')
  require(pactive.get('state')=='EPOCH42_SOURCE_FROZEN_DEV_PENDING_ADMISSION'and active.get('state')=='EPOCH42_CLOSED'and active.get('work_active')is False and active.get('conditional_dev_allowed')==0,'FINAL closes sole DEV slot')
  checked_final(root,current,rows,cont,pcont,plan)
 require(plan['publication_stage_paths'][args.phase]==str(output),'Exact frozen stage placement')
 before=tuple_map(parse(args.prior_expected))if args.prior_expected else copy.deepcopy(baseline)
 if not args.prior_expected:
  require(args.phase=='source','FINAL requires exact prior SOURCE full map')
  for name,body in prior.items():before[name]=leaf(name,body)
 for name,body in prior.items():require(before.get(name)==leaf(name,body),'Actual prior control tuple differs')
 expected=copy.deepcopy(baseline)
 for name,body in {**current,**bodies}.items():require(name not in baseline or name in CONTROLS,'Historical Git overwrite refused');expected[name]=leaf(name,body)
 require(all(expected.get(name)==row for name,row in before.items()if name not in CONTROLS),'Previously published source tuple changed')
 check_transport(root,parse(kit/'CONTINUATION.json'),cont,rows,set(expected),kit=kit)
 changed={name:body for name,body in {**current,**bodies}.items()if before.get(name)!=expected[name]};require(CONTROLS<=set(changed),'Three controls required');blobs,groups=transport_groups(changed)
 meta={'schema_version':1,'stage':args.phase,'prior_controls_name':priorcontrols.name,'scope':SCOPE,'source_checkpoint':BASE_COMMIT,'source_plan_sha256':pr['sha256'],'publication_parent':args.parent,'read_only_main_observation':args.expected_main,'CAS_guards':{'expected_root_tree':args.expected_root,'expected_benchmarks_tree':args.expected_bench,'expected_scope_tree':args.expected_scope,'expected_branch_sha':args.parent,'force':False},'prior_Git_leaves':len(before),'expected_Git_leaves':len(expected),'old_CP_rows':len(cp_rows(oldcp)),'new_CP_rows':len(rows),'historical_Git_leaves':len(baseline),'reviewed_files_sha256':sha(content(args.reviewed_files)),'parent_readback_sha256':sha(proofbytes),'old_noncontrol_tuples_preserved':True,'Git_mutations':0,'native_or_model_or_corpus_calls':0,'large_blob_requests':[],'create_tree_groups':[],'changed_files':[{'path':name,'bytes':len(body),'sha256':sha(body),'git_blob_sha1':gitsha(body)}for name,body in sorted(changed.items())]}
 output.mkdir(mode=0o700);(output/'transport').mkdir(mode=0o700)
 for i,(name,body,payload)in enumerate(blobs):
  file='transport/blob-%03d.json'%i;data=encoded(payload);write(output/file,data);meta['large_blob_requests'].append({'path':name,'file':file,'bytes':len(data),'sha256':sha(data),'expected_blob_sha1':gitsha(body)})
 for i,group in enumerate(groups):
  file='transport/tree-%03d.json'%i;data=encoded({'tree_elements':group});require(len(data)<MAX_TREE_JSON,'Strict serialized tree cap');write(output/file,data);meta['create_tree_groups'].append({'file':file,'bytes':len(data),'sha256':sha(data),'entries':len(group)})
 leaves=encoded({'schema_version':1,'scope':SCOPE,'source_checkpoint':BASE_COMMIT,'files':[expected[k]for k in sorted(expected)]});write(output/'expected-leaves.json',leaves);meta['expected_leaves']={'file':'expected-leaves.json','bytes':len(leaves),'sha256':sha(leaves),'count':len(expected)};write(output/'metadata.json',encoded(meta,pretty=True))
 return {key:meta[key]for key in ('stage','publication_parent','old_CP_rows','new_CP_rows','expected_Git_leaves','expected_leaves','Git_mutations')}

if __name__=='__main__':
 parser=argparse.ArgumentParser()
 for name in ('project','kit','controls','priorcontrols','source-filemap','reviewed-files','parent-readback','out'):parser.add_argument('--'+name,type=Path,required=True)
 parser.add_argument('--phase',choices=('source','final'),required=True);parser.add_argument('--prior-expected',type=Path)
 for name in ('parent','expected-main','expected-root','expected-bench','expected-scope'):parser.add_argument('--'+name,required=True)
 print(json.dumps(prepare(parser.parse_args()),sort_keys=True))
