"""Root-only reversible metadata staging. Scientific functions are never imported."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,copy,json,re
import publication_common as c

def check_source_reservation(active,patch,plan):
 r=active['worker_slot_reservation'];c.require(c.same(r,patch['epoch45_frozen_study']['worker_slot_reservation'])and c.same(r,plan['worker_slot_reservation']),'Same SOURCE/CONT/plan worker reservation')
 c.require(r['epoch']==45 and r['generation']==c.OWNER_GENERATION and r['owner_sha256']==c.OWNER_SHA and re.fullmatch(r'[0-9a-f]{64}',r['reservation_token']),'Exact current owner/token reservation')
 c.require((r['pid'],r['startticks'])==(c.OWNER_PID,c.OWNER_TICKS)and type(r['reserved_worker_slots'])is int and r['reserved_worker_slots']==1,'Exactly one slot for original PID/startticks')
 c.require(r['permanently_burned_at_SOURCE_publication']is True and r['execution_counts_from_actual_receipts_only']is True,'Burned capability is not an actual execution count')
 c.require(r['currentepoch_new_invocations_after_owner_loss_forbidden']is True and r['missing_receipt_after_owner_loss']=='UNKNOWN_PERMANENTLY_NO_RERUN','Reservation cannot reopen after lost owner')
 c.require(active['currentepoch_new_invocations_after_owner_loss_forbidden']is True and active['missing_receipt_after_owner_loss']=='UNKNOWN_PERMANENTLY_NO_RERUN','No invocation after lost owner or missing receipt')

def check_controls(old,new,active,phase,cpref,patch):
 c.require(set(patch)<=({'epoch45_frozen_study','epoch45_data_roles'}if phase=='source'else {'epoch45_final','next_research_priority','rejection_ledger','latest_learning','cumulative_budget_ledger','benchmark_refresh','publisher_status','exposed_development_sets','unused_confirmation_sets'}),'Unreviewed CONT patch keys')
 expected=copy.deepcopy(old);expected.update(copy.deepcopy(patch));expected['active_run']=copy.deepcopy(active);expected['checkpoint_manifest_sha256']=cpref
 c.require(c.same(new,expected),'CONT history/patch differs')
 c.require(new['goal_met']is False and new['official_rank']is None and c.same(new['champion'],old['champion']),'Champion/official goal changed')
 for key in('epoch42_archive_recovery','epoch44_publication_recovery9','epoch44_final','epoch44_frozen_study','epoch44_data_roles','unused_confirmation_sets'):
  c.require(c.same(new[key],old[key]),'Inherited history/UNKNOWN/protected CONF changed: '+key)
 for key,value in old.get('cumulative_budget_ledger',{}).items():c.require(c.same(new['cumulative_budget_ledger'][key],value),'Prior typed cumulative execution field changed')
 c.require(active['epoch']==45 and active['phase']==phase and active['source_checkpoint']==c.BASE,'E45 active descriptor')
 expected_slots={'TRAIN':0,'DEV':1 if phase=='source'else 0,'calibration':0,'CONF':0,'paid_calls':0,'GPU_calls':0,'retries':0}
 c.require(c.same(active['remaining_allowance'],expected_slots),'Exact phase allowance')
 c.require(active['scientific_authorization_requires_actual_SOURCE_readback']is True and active['second_native_batch_closed']is True,'SOURCE readback/one-batch fence')
 c.require(active['OS_lock_observation_scope']=='PREPUBLICATION_SNAPSHOT_NOT_CURRENT_REMOTE_LEASE','Persisted owner is historical snapshot')
 c.require(active['work_active']is (phase!='final')and active['experiments_active']is False,'No publication claim of active science')

def build(a):
 c.require_operational();raw=c.body(a.input);c.require(c.sha(raw)==a.expected_input_sha,'Exact phase-input SHA required');x=json.loads(raw)
 proof=c.parse(a.approval);c.require(c.sha(c.body(a.approval))==a.expected_approval_sha and proof.get('phase_preparation_allowed')is True and proof.get('phase_input_sha256')==a.expected_input_sha,'Independent metadata preparation approval')
 phase=x['phase'];c.require(phase in('source','final')and x['epoch']==45 and x['source_checkpoint']==c.BASE,'E45 phase binding')
 c.require(x['owner_sha256']==c.OWNER_SHA,'Exact actual current owner')
 if phase=='source':c.require(x['parent']==c.BASE,'SOURCE must be first distinct child of actual E45 base')
 else:
  sr=json.loads(c.checked(x['actual_SOURCE_receipt']['path'],x['actual_SOURCE_receipt']));c.require(sr.get('epoch')==45 and sr.get('phase')=='source'and sr.get('verified_actual_full_tree')is True and sr.get('commit')==x['parent'],'FINAL extends actual acknowledged SOURCE plus fresh ref GET')
 sm=json.loads(c.checked(x['source_map']['path'],x['source_map']));c.require(sm.get('commit',sm.get('source_commit'))==x['parent'],'Actual parent/source map')
 files=sm['files'];c.require(len({r['path']for r in files})==len(files),'Unique original Git leaves')
 c.require(all(r['mode']=='100644'and r['type']=='blob'and r['sha']not in c.FORBIDDEN_OBJECTS and type(r['size'])is int for r in files),'Original regular/nonforbidden typed Git leaves')
 rb=json.loads(c.checked(x['root_baseline']['path'],x['root_baseline']));bb=json.loads(c.checked(x['bench_baseline']['path'],x['bench_baseline']))
 c.require(c.tree_sha(rb['tree'])==rb['sha']==sm['root'] and c.tree_sha(bb['tree'])==bb['sha'],'Actual nonrecursive baseline trees')
 oldcp_raw=c.checked(x['current_CP']['path'],x['current_CP']);oldcp=json.loads(oldcp_raw);oldcont_raw=c.checked(x['current_CONT']['path'],x['current_CONT']);old=json.loads(oldcont_raw)
 oldrows={r['path']:r for r in oldcp['project_files']};c.require(len(oldrows)==len(oldcp['project_files']),'Unique CP rows')
 c.require(len(oldrows)>=7592,'All old CP7592 rows retained')
 if phase=='source':c.require(len(oldrows)==7592 and len(files)==7599,'Fresh E45 base CP7592/Git7599 required')
 oldgit={r['path']:r for r in files};oldonly=set(oldrows)-set(oldgit)
 for p,raw in(('CHECKPOINT_MANIFEST.json',oldcp_raw),('CONTINUATION.json',oldcont_raw)):
  c.require(p in oldgit and oldgit[p]['sha']==c.git(raw)and oldgit[p]['size']==len(raw),'Current control bytes must match actual parent Git blob: '+p)
 c.require(len(oldonly)==70,'All historical70 CP-only files retained')
 projection=json.loads(c.checked(x['archive_projection']['path'],x['archive_projection']));c.verify_70_projection(old,oldcp,oldgit,projection)
 overlay=old['epoch44_publication_recovery9']['archive_overlay'];c.require(overlay['CP_project_files_includes_overlay55']is False and overlay['project_additions_AFTER_standard_restore']==55 and overlay['canonical_members']==137,'Separate unchanged E44 overlay55 transport')
 paths={};newrows={}
 for r in x['artifacts']:
  p=c.relative(r['path']);c.require(any(p.startswith(root+'/')for root in c.ROOTS)and p not in oldgit and p not in oldrows,'Only new E45 artifact paths')
  c.require(p not in paths,'Duplicate artifact');b=c.checked(r['local_path'],r);c.public_text(p,b);c.require(c.git(b)not in c.FORBIDDEN_OBJECTS,'Forbidden old payload');paths[p]=b;newrows[p]={'path':p,'bytes':len(b),'sha256':c.sha(b)}
 cp=copy.deepcopy(oldcp);key='epoch45_'+phase;c.require(key not in cp,'No duplicate phase CP record');cp[key]=copy.deepcopy(x['CP_phase_record']);cp['project_files']=sorted([*oldrows.values(),*newrows.values()],key=lambda r:r['path']);cpraw=c.encoded(cp)
 active=copy.deepcopy(x['ACTIVE']);cont=copy.deepcopy(old);cont.update(copy.deepcopy(x['CONT_patch']));cont['active_run']=copy.deepcopy(active);cont['checkpoint_manifest_sha256']=c.sha(cpraw)
 check_controls(old,cont,active,phase,c.sha(cpraw),x['CONT_patch'])
 if phase=='source':
  check_source_reservation(active,x['CONT_patch'],json.loads(paths['experiments/sota-2026-10-22/epoch45/plan.json']));preflight=json.loads(c.checked(x['source_preflight']['path'],x['source_preflight']));c.require(preflight.get('checks_passed')is True and preflight.get('actual_source_freeze_reference_closure_verified')is True and c.same(preflight.get('plan'),{k:x['plan'][k]for k in('path','bytes','sha256')}),'Actual SOURCE output reference preflight required')
  plan=json.loads(paths[x['plan']['path']]);c.require(c.same(newrows[x['plan']['path']],x['plan']),'Exact staged frozen plan')
  fr=plan['source_freeze'];freeze=json.loads(paths[fr['path']]);c.require(c.same(newrows[fr['path']],fr),'Exact staged SOURCE_FREEZE')
  current={r['path']:r for r in freeze['files']if any(r['path'].startswith(root+'/')for root in c.ROOTS)}
  c.require(set(paths)==set(current)|{x['plan']['path'],fr['path']},'SOURCE includes every frozen current artifact and only plan/freeze additions')
  for p,row in current.items():c.require(c.same(newrows[p],row),'Staged source differs from frozen reference')
 else:
  er=x['epoch_manifest'];ep=er['path'];c.require(c.same(newrows[ep],er),'Exact staged immutable EPOCH_MANIFEST')
  epoch=json.loads(paths[ep]);c.require(epoch['epoch']==45 and epoch['source_checkpoint']==c.BASE and epoch['no_project_additions_after_manifest']is True,'Immutable final manifest required')
  closed={r['path']:r for r in epoch['files']};c.require(len(closed)==len(epoch['files']),'Unique final manifest rows')
  all45={p:r for p,r in {**oldrows,**newrows}.items()if any(p.startswith(root+'/')for root in c.ROOTS)}
  c.require(set(closed)|{ep}==set(all45),'No new project additions after immutable epoch manifest')
  for p,row in closed.items():c.require(c.same(all45[p],row),'Final manifest bytes changed')
 paths.update({'CONTINUATION.json':c.encoded(cont),'ACTIVE_RUN.json':c.encoded(active)})
 paths['CHECKPOINT_MANIFEST.json']=cpraw
 out=Path(a.out);c.require(out.is_absolute()and not out.exists(),'Fresh outside-project stage required');c.require(out.is_relative_to(c.W)and not out.is_relative_to(c.W/'project'),'Stage stays outside project')
 out.mkdir(mode=0o700)
 leaves={r['path']:copy.deepcopy(r)for r in files};blobs=[];elements=[]
 prefix='e45-'+phase+'-g'+str(c.OWNER_GENERATION)
 for i,(p,b)in enumerate(sorted(paths.items())):
  c.public_text(p,b);g=c.git(b);c.require(g not in c.FORBIDDEN_OBJECTS,'Forbidden decoded payload');name=f'blob-{i}.json';request={'repository_full_name':c.REPO,'encoding':'utf-8','content':b.decode()};c.validate_request('github_create_blob',request);raw=c.encoded(request);c.require(len(raw)<8384512,'Blob JSON transport cap');c.write(out/name,raw)
  blobs.append({'id':prefix+f'-blob-{i}','file':name,'bytes':len(raw),'sha256':c.sha(raw),'GitSHA':g,'project_path':p,'payload_bytes':len(b),'payload_sha256':c.sha(b)})
  elements.append({'path':c.SCOPE+p,'mode':'100644','type':'blob','sha':g});leaves[p]={'path':p,'mode':'100644','type':'blob','sha':g,'size':len(b)}
 trees=[]
 for i,at in enumerate(range(0,len(elements),32)):
  request={'tree_elements':elements[at:at+32]};c.require(len(request['tree_elements'])<=32,'Tree request element cap');c.deny_old_object('create_tree',request);raw=c.encoded(request);c.require(len(raw)<175904,'Tree JSON transport cap');name=f'tree-{i}.json';c.write(out/name,raw);trees.append({'id':prefix+f'-tree-{i}','file':name,'bytes':len(raw),'sha256':c.sha(raw)})
 scope=c.full_scope_sha(list(leaves.values()));benchentries=copy.deepcopy(bb['tree']);rootentries=copy.deepcopy(rb['tree'])
 for rows,key,value in((benchentries,'ruvector-sota-2026-10-22',scope),):
  selected=[r for r in rows if r['path']==key];c.require(len(selected)==1 and selected[0]['type']=='tree','Scoped baseline parent');selected[0]['sha']=value
 bench=c.tree_sha(benchentries)
 selected=[r for r in rootentries if r['path']=='benchmarks'];c.require(len(selected)==1 and selected[0]['sha']==bb['sha'],'Original bench baseline');selected[0]['sha']=bench;root=c.tree_sha(rootentries)
 expected={'scope':c.SCOPE,'files':sorted(leaves.values(),key=lambda r:r['path'])};raw=c.encoded(expected);c.write(out/'expected-leaves.json',raw)
 meta={'schema_version':1,'epoch':45,'phase':phase,'source_checkpoint':c.BASE,'source_parent':x['parent'],'expected_source_root':rb['sha'],'expected_source_bench':bb['sha'],'expected_source_scope':sm.get('scope_sha',sm.get('scope')),'expected_final_root':root,'expected_final_bench':bench,'expected_final_scope':scope,'owner_sha256':c.OWNER_SHA,'operational_binding_sha256':c.OPERATIONAL_SHA,'mutation_ID_prefix':prefix,'phase_input_sha256':a.expected_input_sha,'blobs':blobs,'trees':trees,'expected_leaves':{'file':'expected-leaves.json','bytes':len(raw),'sha256':c.sha(raw)},'new_Git_leaves':len(leaves),'CP_rows':len(cp['project_files']),'CP_only_paths':sorted(oldonly),'original_blob5_execution':'UNKNOWN_PERMANENTLY','forbidden_Git_object_sha1':c.FORBIDDEN,'commit_message':x['commit_message']}
 meta['forbidden_Git_objects']=sorted(c.FORBIDDEN_OBJECTS)
 meta['E44_overlay55_remains_separate_from_CP_rows']=True
 if phase=='final':meta['actual_SOURCE_receipt']=x['actual_SOURCE_receipt']
 meta['mutation_ID_order']=[r['id']for r in blobs+trees]+[prefix+'-commit',prefix+'-ref'];c.write(out/'metadata.json',c.encoded(meta));return meta

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--expected-input-sha',required=True);p.add_argument('--approval',type=Path,required=True);p.add_argument('--expected-approval-sha',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--operational-binding',type=Path,required=True);p.add_argument('--expected-operational-binding-sha',required=True);a=p.parse_args();c.configure(a.operational_binding,a.expected_operational_binding_sha);print(json.dumps(build(a),sort_keys=True))
