from pathlib import Path
import json,hashlib,os,time,stat
O=Path(__file__).resolve().parent;W=Path('/dev/shm/ruvector-sota-2026-10-22/epoch54-6187205840a9');OLD=Path('/dev/shm/ruvector-sota-2026-10-22/epoch53-655e7aa57e34')
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(n,x):
 b=(json.dumps(x,sort_keys=True,indent=2)+'\n').encode();p=O/n
 with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 return ref(p)
m=json.loads((O/'ALL_OLD_PUBLIC_FILES_EXACT_PRESERVED_MIRRORS.v1.json').read_bytes());v=json.loads((O/'DUPLICATE_PUBLIC_ROOT_MIRROR_VERIFICATION.actual.v1.json').read_bytes());assert v['checks_passed']and v['all_old_public_files_accounted']and not m['unmirrored_old_files']
assert v['manifest']==ref(O/'ALL_OLD_PUBLIC_FILES_EXACT_PRESERVED_MIRRORS.v1.json')
assert len(m['files'])==17384 and v['total_regular_files']==17384 and v['total_logical_bytes']==1131475886
owner=json.loads((W/'owner.json').read_bytes());assert owner['epoch']==54 and owner['generation']==19 and time.time()<owner['expires_unix']and not(W/'release.request').exists()
p=Path('/proc')/str(owner['pid']);s=(p/'stat').read_text().rsplit(')',1)[1].split();assert s[0]not in('Z','X')and int(s[19])==owner['startticks'];lock=Path(owner['lock']);st=lock.stat();assert stat.S_ISREG(st.st_mode)and not lock.is_symlink()and(st.st_dev,st.st_ino)==(owner['lock_device'],owner['lock_inode'])
infos=[f.read_text()for f in(p/'fdinfo').iterdir()if f.is_file()];assert any('FLOCK' in x and str(st.st_ino)in x for x in infos)
controls=[r for r in m['files']if r['relative_path']in('CONTINUATION.json','CHECKPOINT_MANIFEST.json','ACTIVE_RUN.json')]
assert len(controls)==3 and all(r['old_root']==str(OLD/'kit')for r in controls)
for r in controls:assert not Path(r['preserved_mirror']['path']).is_relative_to(OLD/'kit')and not Path(r['preserved_mirror']['path']).is_relative_to(OLD/'project')
targets=[str(OLD/'kit'),str(OLD/'project')];dirs=[]
for a in targets:
 st=Path(a).stat();dirs.append({'path':a,'device':st.st_dev,'inode':st.st_ino,'mode':stat.S_IMODE(st.st_mode),'is_nonsymlink_directory':Path(a).is_dir()and not Path(a).is_symlink()})
plan={'schema_version':1,'epoch':54,'kind':'EXACT_DUPLICATE_PUBLIC_ROOT_CLEANUP_PLAN','source_checkpoint':'6187205840a9f77db9ab80e97e30be7b222e461e','purpose':'Independent useful resource recovery after E54failure; delete only fullySHAverified duplicatepublicroots, never rerunE54 or imply a native corpus executed.','manifest':ref(O/'ALL_OLD_PUBLIC_FILES_EXACT_PRESERVED_MIRRORS.v1.json'),'independent_full_hash_verification':ref(O/'DUPLICATE_PUBLIC_ROOT_MIRROR_VERIFICATION.actual.v1.json'),'owner':ref(W/'owner.json'),'original_G19_exclusive_lock_currently_verified':True,'delete_exact_directory_targets':targets,'target_directory_identities':dirs,'deletion_targets_counts':v['counts'],'total_regular_files':v['total_regular_files'],'total_logical_bytes':v['total_logical_bytes'],'all_old_public_bytes_accounted':True,'old_control_bytes_preserved':controls,'extra_control_bytes_to_copy':[],'preserved_mirrors_include_fresh_W54_kit_project_and_old_W53_control_baselines':True,'touch_private_operational_journal_basecache_model_native_archives':False,'delete_parent_or_siblings_authorized':False,'actual_deletions':0,'cleanup_grants_scientific_or_Git_authority':False,'new_project_artifact_writes_authorized':False,'execution_requirement':'Root independently review exactmanifest+twotargetpaths andunchangedsourcepin/owner, then deleteonlythosenonsymlinkdirectories once. Do notfollowlinks/removeparent/touchotherW53paths. Record actualcleanup and post-targetabsence. No scientificretry ornativebatchauthorized.'}
pin=put('EXACT_TWO_PUBLIC_ROOT_DELETION_PLAN.v1.json',plan)
a={'schema_version':1,'epoch':54,'kind':'INDEPENDENT_EXACT_DUPLICATE_PUBLIC_ROOT_CLEANUP_APPROVAL','checks_passed':True,'approved':True,'plan':pin,'manifest':plan['manifest'],'verification':plan['independent_full_hash_verification'],'owner':plan['owner'],'exact_targets':targets,'regular_files':17384,'total_logical_bytes':1131475886,'oldcontrols3preserved_outside_targets':True,'every_file_SHA256_equal_distinct_inode_mirror':True,'no_source_or_private_mutation_by_reviewer':True,'actual_deletions':0,'no_scientific_Git_or_future_retry_authority':True,'only_root_may_execute_exact_approved_cleanup':True}
print(json.dumps({'plan':pin,'approval':put('EXACT_OLD_W53_PUBLIC_DUPLICATE_CLEANUP_INDEPENDENT_APPROVAL.v1.json',a)}))
