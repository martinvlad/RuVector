"""One prospective E32 source compatibility amendment, before any dispatch.
No model/native/tokenizer/labels or external mutation. Original SOURCE is retained
in Git and as exact public version files; candidate/scorer/data/gates do not change.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,hashlib,importlib.util,json,os,re
from pathlib import Path
from types import SimpleNamespace
W=Path('/workspace/ruvector-epoch32-f8bcbc4ca7ec');R=W/'project';P='experiments/sota-2026-10-22/';E=P+'epoch32/'
D=R/(E+'preparation/source-amendment-1');PRIOR=D/'prior'
PARENT='ab8548df202b75281a3bfff6496627659fb469f6'
TREES={'root':'63aeb90f30958d57d033803d51f3b474ca6bc10f','bench':'3232e7a32034a3aecf41d28930ace1411d3bef49','scope':'fbe8fcab1a3a538e4723e462f42979bbb627f184'}
OLD={E+'plan.json':'8173421369b50736e9171da2115f1120c04db12674a138a7c41a1871aa12e6e8',E+'source-freeze.json':'af633a634de2fb92190e64f3455a7a536dfcf188a155320b9e1d88eddcbde08f',E+'preparation/runtime-assets.lock.json':'afb6504191e76f9c73bc523dbfc285392055aa82da7f93844cb03b30f27beee3'}
ALIASES={'wheel_members_reference_path':P+'epoch26/preparation/runtime-members/python-wheel-members.json','wheel_members_reference_sha256':'87254bbf6ec2aba6d08a4b55ff189faf29f78e1b1dd278fe8ffef9a8cc5523b9','wheel_members_reference_count':17498}
MAIN='c44d7337c0c5ad2ecd2294178475387facb96516'
sys.path.insert(0,str(R/(E+'publication')))
import publication_common_v1 as c
import stage_publication_v1 as pub
import phase_schema_v1 as schema

def fsync_dir(path):
 fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def put(path,body):
 path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 with path.open('xb')as f:f.write(body);f.flush();os.fsync(f.fileno())
 fsync_dir(path.parent)
def encode(value):return (json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
def replace(path,body):
 tmp=path.with_name(path.name+'.amend1-tmp');put(tmp,body);os.replace(tmp,path);fsync_dir(path.parent)
def absent_execution():
 study=R/E
 for name in ('SOURCE_ADMISSION.json','DEV_ATTEMPT_RESERVATION.json',*schema.DISPATCH_PATHS.values()):
  path=study/name if '/' not in name else R/name
  if path.exists():raise ValueError('Execution/admission already exists: '+str(path))
 if (study/'runs').exists():raise ValueError('Current worker runs already exist')
 # These are current scope reservation artifacts, not claims about unrelated
 # processes or hidden compiled calls elsewhere on the host.
 return {'current_admission_dispatch_phase_reservations_and_runs_absent':True,'source_only_no_model_native_tokenizer_or_label_calls':True}
def original_controls():
 prior=W/'controls-source-v1-published'
 return prior if prior.exists()else W/'controls-source'
def check_old():
 c.live_owner(W);absent_execution()
 for name,digest in OLD.items():
  if c.sha(c.content(R/name))!=digest:raise ValueError('Original canonical SOURCE drift: '+name)
 cp=c.parse(original_controls()/'CHECKPOINT_MANIFEST.json')
 if c.sha(c.content(original_controls()/'CHECKPOINT_MANIFEST.json'))!='2ce095428bd2e960dcab32d44674c7b7d2fd9e73b3888eb2fe88ceca0772306b':raise ValueError('Original SOURCE CP drift')
 before=pub.tuple_map(c.parse(W/'stage-source/expected-leaves.json'))
 if len(before)!=4563 or pub.scope_tree_sha(before)!=TREES['scope']:raise ValueError('Original SOURCE full tuple map drift')
 for path,row in before.items():
  if path in c.CONTROLS:body=c.content(original_controls()/path)
  else:body=c.content(R/path if (R/path).exists() else W/'kit'/path)
  if pub.leaf(path,body)!=row:raise ValueError('Original SOURCE byte drift: '+path)
 return cp,before

def amend():
 check_old();evidence=absent_execution()
 if PRIOR.exists() or (D/'AMENDMENT.json').exists()or(W/'amendment1-actual-master.json').exists():raise ValueError('Amendment already reserved; no replay')
 lock=c.parse(R/(E+'preparation/runtime-assets.lock.json'))
 if any(k in lock for k in ALIASES):raise ValueError('Aliases already present')
 member=lock['python_member_manifest']
 if member!={'path':ALIASES['wheel_members_reference_path'],'bytes':4640799,'sha256':ALIASES['wheel_members_reference_sha256']}:raise ValueError('Current member identity differs')
 if c.ref(R,member['path'])!=member:raise ValueError('Actual immutable member manifest differs')
 members=c.parse(R/member['path'])
 if not isinstance(members,list) or len(members)!=17498 or len({r['path']for r in members})!=17498:raise ValueError('Actual member manifest count/uniqueness differs')
 # Manifest's declared closure count is validated by the exact frozen manifest
 # and runtime; inspect its actual fixed schema without importing runtime code.
 if lock.get('verified_wheel_members')!=17498:raise ValueError('Installed member count differs')
 PRIOR.mkdir(mode=0o700)
 prior_refs=[]
 for name,digest in OLD.items():
  dest=PRIOR/Path(name).name;body=c.content(R/name);put(dest,body);prior_refs.append({'canonical_path':name,'prior':c.ref(R,dest.relative_to(R).as_posix())})
 record={'schema_version':1,'epoch':32,'kind':schema.KIND,'status':'UNEXECUTED_SOURCE_COMPATIBILITY_AMENDMENT','prior_source_commit':PARENT,'prior_source_trees':TREES,'preserved_original_files':prior_refs,'added_runtime_lock_aliases':ALIASES,'reason':'Published original runtime lock used canonical python_member_manifest but frozen runtime/common.py requires exact flat wheel_members_reference aliases. Root detected this compatibility blocker before admission or reservation. The three aliases refer to the same already verified immutable member manifest and count; no dependency or scientific change.','evidence_before_amendment':evidence,'candidate_scorer_observer_data_model_gates_budgets_unchanged':True,'same_permanently_retired_DEV_ids':schema.ROLES['dev'],'new_measurement_attempts':0,'new_confirmation':[],'prior_source_invalidated_for_execution':True,'original_source_retained_immutably_in_Git_and_public_versions':True}
 put(D/'AMENDMENT.json',encode(record))
 lock.update(ALIASES);replace(R/(E+'preparation/runtime-assets.lock.json'),encode(lock))
 # Preserve the old canonical bodies first. The sole replacement master is
 # produced by the already reviewed builder with the amended SOURCE parent.
 for name in (E+'plan.json',E+'source-freeze.json'):(R/name).unlink();fsync_dir((R/name).parent)
 source=R/(E+'preparation/v2/reviewed_build_plan.py')
 if c.sha(c.content(source))!='e508bade90bd59f0d8e148f86697f484303fe136d1c3b269dcd83da725f71c6e':raise ValueError('Reviewed master builder changed')
 spec=importlib.util.spec_from_file_location('reviewed_E32_amend1_master',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 outcome=module.build(SimpleNamespace(scope=W,scorer=P+'audit/epoch32/score_dev.py',source_parent=PARENT,source_root=TREES['root'],source_bench=TREES['bench'],source_scope=TREES['scope'],source_stage=W/'stage-source-amend1',final_stage=W/'stage-final',check_only=False))
 put(W/'amendment1-actual-master.json',encode(outcome))
 return outcome

def stage():
 c.live_owner(W);absent_execution()
 if not(W/'amendment1-actual-master.json').exists():raise ValueError('Amended master absent')
 plan=c.parse(R/schema.PLAN_PATH);freeze=c.parse(R/schema.FREEZE_PATH)
 if plan['publication_parent']!=PARENT or plan['publication_parent_trees']!=TREES or plan['publication_stage_paths']['source']!=str(W/'stage-source-amend1'):raise ValueError('Amended master parent/stage differs')
 for row in plan['pins']:pub.checked_ref(R,row)
 current=c.walk_current(R)
 if {r['path']for r in freeze['entries']}!=set(current)-{schema.PLAN_PATH,schema.FREEZE_PATH}:raise ValueError('Amended freeze is not exhaustive')
 old_dir=W/'controls-source';saved=W/'controls-source-v1-published'
 if saved.exists():raise ValueError('Original controls already retained; stop instead of repeating')
 prior=pub.controls_at(old_dir);oldcp=c.loads(prior['CHECKPOINT_MANIFEST.json']);oldcont=c.loads(prior['CONTINUATION.json']);active=c.loads(prior['ACTIVE_RUN.json'])
 if c.sha(prior['CHECKPOINT_MANIFEST.json'])!='2ce095428bd2e960dcab32d44674c7b7d2fd9e73b3888eb2fe88ceca0772306b':raise ValueError('Prior actual SOURCE CP drift')
 if active.get('state')!='EPOCH32_SOURCE_FROZEN_DEV_PENDING_ADMISSION' or active.get('native_allowed')!=0 or not active.get('work_active'):raise ValueError('Prior SOURCE allowances differ')
 baseline=pub.verify_baseline(W/'kit',c.parse(W/'actual-git-map.json'));c.check_history(R,c.parse(W/'kit/CHECKPOINT_MANIFEST.json'))
 oldrows=c.cp_rows(oldcp)
 for path,row in oldrows.items():
  actual=c.ref(R,path)
  if path not in OLD and actual!=row:raise ValueError('Forbidden prior source overwrite: '+path)
 for item in c.parse(D/'AMENDMENT.json')['preserved_original_files']:
  if c.ref(R,item['prior']['path'])!=item['prior'] or item['prior']['sha256']!=OLD[item['canonical_path']]:raise ValueError('Original canonical retention differs')
 rows={path:{'path':path,'bytes':len(body),'sha256':c.sha(body)}for path,body in current.items()}
 cp=copy.deepcopy(oldcp);cp['project_files']=[rows.get(row['path'],row)for row in oldcp['project_files']]
 cp['project_files'] +=[rows[path]for path in sorted(set(rows)-set(oldrows))]
 frozen={'plan':c.ref(R,schema.PLAN_PATH),'source_freeze':c.ref(R,schema.FREEZE_PATH)}
 cp['epoch32_source']={'kind':schema.KIND,'source_checkpoint':c.BASE_COMMIT,'frozen_source_parent':PARENT,**frozen}
 amendment_ref=c.ref(R,(D/'AMENDMENT.json').relative_to(R).as_posix())
 cp['epoch32_source_amendment_1']={'prior_source_commit':PARENT,'prior_source_CP_sha256':c.sha(prior['CHECKPOINT_MANIFEST.json']),'amendment':amendment_ref,'changed_existing_project_paths':sorted(OLD),'same_scientific_contract':True}
 bodies={'CHECKPOINT_MANIFEST.json':c.encoded(cp,pretty=True)}
 cont=copy.deepcopy(oldcont);active=copy.deepcopy(active)
 active['checkpoint_parent']=PARENT
 cont['epoch32_frozen_study']=frozen
 cont['epoch32_source_amendment_1']={'prior_source_commit':PARENT,'prior_frozen_study':oldcont['epoch32_frozen_study'],'amendment':amendment_ref,'replacement_frozen_study':frozen,'new_measurement_attempts':0,'confirmation_consumed':False,'prior_source_invalidated_for_execution':True}
 cont['checkpoint_manifest_sha256']=c.sha(bodies['CHECKPOINT_MANIFEST.json']);cont['prior_published_base_commit']=PARENT;cont['active_run']=dict(active,path='ACTIVE_RUN.json')
 for key in oldcont:
  if key not in {'epoch32_frozen_study','checkpoint_manifest_sha256','prior_published_base_commit','active_run'}and cont[key]!=oldcont[key]:raise ValueError('Forbidden continuation change: '+key)
 if cont['exposed_development_sets']!=oldcont['exposed_development_sets'] or cont.get('used_confirmation_sets')!=oldcont.get('used_confirmation_sets'):raise ValueError('DEV/CONF retirement changed')
 bodies.update({'CONTINUATION.json':c.encoded(cont,pretty=True),'ACTIVE_RUN.json':c.encoded(active,pretty=True)})
 before=pub.tuple_map(c.parse(W/'stage-source/expected-leaves.json'))
 if len(before)!=4563 or pub.scope_tree_sha(before)!=TREES['scope']:raise ValueError('Prior SOURCE tuple identity differs')
 expected=copy.deepcopy(baseline)
 for path,body in {**current,**bodies}.items():expected[path]=pub.leaf(path,body)
 for path,row in before.items():
  if path not in set(OLD)|c.CONTROLS and expected.get(path)!=row:raise ValueError('Forbidden published tuple mutation: '+path)
 changed={path:body for path,body in{**current,**bodies}.items()if before.get(path)!=expected[path]}
 existing_changes=set(changed)&set(before)
 if existing_changes!=set(OLD)|c.CONTROLS:raise ValueError('Existing change allowlist differs')
 parentproof=c.parse('/workspace/ruvector-e32-publication-audit/source-actual-readback-independent-v1.json')
 pub.check_readback(parentproof,'source',PARENT,tuple(TREES.values()))
 output=W/'stage-source-amend1'
 if output.exists():raise ValueError('Amendment stage already exists')
 output.mkdir(mode=0o700);(output/'transport').mkdir(mode=0o700)
 blobs,groups=pub.transport_groups(changed)
 meta={'schema_version':1,'stage':'source-amend1','prior_controls_name':'controls-source-v1-published','scope':c.SCOPE,'source_checkpoint':c.BASE_COMMIT,'source_plan_sha256':c.sha(c.content(R/schema.PLAN_PATH)),'publication_parent':PARENT,'read_only_main_observation':MAIN,'CAS_guards':{'expected_root_tree':TREES['root'],'expected_benchmarks_tree':TREES['bench'],'expected_scope_tree':TREES['scope'],'expected_branch_sha':PARENT,'force':False},'source_filemap_sha256':c.sha(c.content(W/'actual-git-map.json')),'prior_expected_sha256':c.sha(c.content(W/'stage-source/expected-leaves.json')),'parent_readback_sha256':c.sha(c.content('/workspace/ruvector-e32-publication-audit/source-actual-readback-independent-v1.json')),'historical_Git_leaves':len(baseline),'prior_Git_leaves':len(before),'old_CP_rows':len(oldrows),'new_CP_rows':len(c.cp_rows(cp)),'new_epoch32_public_files':len(current),'expected_Git_leaves':len(expected),'changed_existing_allowlist':sorted(existing_changes),'original3_retained':c.parse(D/'AMENDMENT.json')['preserved_original_files'],'changed_files':[],'large_blob_requests':[],'create_tree_groups':[],'Git_mutations':0,'native_or_model_or_corpus_calls':0}
 for path,body in sorted(changed.items()):meta['changed_files'].append({'path':path,'bytes':len(body),'sha256':c.sha(body),'git_blob_sha1':c.gitsha(body)})
 for i,(path,body,payload)in enumerate(blobs):
  name='transport/blob-%03d.json'%i;data=c.encoded(payload);put(output/name,data);meta['large_blob_requests'].append({'path':path,'file':name,'bytes':len(data),'sha256':c.sha(data),'expected_blob_sha1':c.gitsha(body),'must_verify_before_tree':True})
 for i,group in enumerate(groups):
  name='transport/tree-%03d.json'%i;data=c.encoded({'tree_elements':group});put(output/name,data);meta['create_tree_groups'].append({'file':name,'bytes':len(data),'sha256':c.sha(data),'entries':len(group)})
 leaves=c.encoded({'schema_version':1,'scope':c.SCOPE,'source_checkpoint':c.BASE_COMMIT,'files':[expected[k]for k in sorted(expected)]});put(output/'expected-leaves.json',leaves)
 meta['expected_leaves']={'file':'expected-leaves.json','bytes':len(leaves),'sha256':c.sha(leaves),'count':len(expected)};put(output/'metadata.json',c.encoded(meta,pretty=True))
 reviewed={'files':[{'path':p,'bytes':len(b),'sha256':c.sha(b)}for p,b in sorted(current.items())]};put(W/'reviewed-source-amend1-files.json',c.encoded(reviewed,pretty=True))
 os.rename(old_dir,saved);fsync_dir(W);old_dir.mkdir(mode=0o700)
 for name,body in bodies.items():put(old_dir/name,body)
 return {'stage':str(output),'metadata':{'bytes':(output/'metadata.json').stat().st_size,'sha256':c.sha(c.content(output/'metadata.json'))},'expected_Git_leaves':len(expected),'new_CP_rows':len(c.cp_rows(cp)),'changed_existing_allowlist':sorted(existing_changes),'large_blobs':len(blobs),'trees':len(groups),'models_native_labels_Git_calls':0}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['amend','stage']);print(json.dumps(amend()if parser.parse_args().mode=='amend'else stage(),sort_keys=True))
