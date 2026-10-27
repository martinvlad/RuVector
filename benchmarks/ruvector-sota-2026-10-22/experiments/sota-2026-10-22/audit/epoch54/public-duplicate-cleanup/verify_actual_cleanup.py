"""Read-only independent post-cleanup public-mirror rehash; never deletes/executes science."""
from pathlib import Path
import json,hashlib,os,time,stat
O=Path(__file__).resolve().parent;W=Path('/dev/shm/ruvector-sota-2026-10-22/epoch54-6187205840a9');OLD=Path('/dev/shm/ruvector-sota-2026-10-22/epoch53-655e7aa57e34')
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def load(p):return json.loads(p.read_bytes())
def hashstream(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
start=time.monotonic();plan=load(O/'EXACT_TWO_PUBLIC_ROOT_DELETION_PLAN.v1.json');m=load(O/'ALL_OLD_PUBLIC_FILES_EXACT_PRESERVED_MIRRORS.v1.json');actual=W/'OLD_W53_PUBLIC_DUPLICATE_CLEANUP.actual.v1.json';a=load(actual);attempt=W/'OLD_W53_PUBLIC_DUPLICATE_CLEANUP_ATTEMPT.actual.v1.json';at=load(attempt)
assert ref(actual)['sha256']=='275f1b4d8f872ed8f80e74c2172ac72e3e47a1d65daf128266d67088f0e2b0fa'
assert a['checks_passed']and a['all_E54_scientific_slots_remain_closed']and a['new_native_tokenizer_BGE_model_Git_calls']==0
assert a['exact_deleted_public_targets']==plan['delete_exact_directory_targets']==[str(OLD/'kit'),str(OLD/'project')]
assert all(not Path(p).exists()and not Path(p).is_symlink()for p in plan['delete_exact_directory_targets'])
assert at['plan']==ref(O/'EXACT_TWO_PUBLIC_ROOT_DELETION_PLAN.v1.json')and at['approval']==ref(O/'EXACT_OLD_W53_PUBLIC_DUPLICATE_CLEANUP_INDEPENDENT_APPROVAL.v1.json')
cache={};count=0;logical=0
for row in m['files']:
 r=row['preserved_mirror'];p=Path(r['path']);assert p.is_file()and all(not q.is_symlink()for q in[p,*p.parents])
 st=p.stat();sig=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns);assert sig==tuple(r[k]for k in['device','inode','bytes','mtime_ns','ctime_ns'])
 if str(p)not in cache:cache[str(p)]=hashstream(p)
 assert cache[str(p)]==r['sha256']==row['old']['sha256']and r['bytes']==row['old']['bytes']
 assert (r['device'],r['inode'])!=(row['old']['device'],row['old']['inode']);count+=1;logical+=row['old']['bytes']
assert count==a['regular_files_retired']==17384 and logical==a['logical_bytes_retired']==1131475886
owner=load(W/'owner.json');assert time.time()<owner['expires_unix']and not(W/'release.request').exists();st=Path(owner['lock']).stat();assert(st.st_dev,st.st_ino)==(owner['lock_device'],owner['lock_inode']);pp=Path('/proc')/str(owner['pid']);ss=(pp/'stat').read_text().rsplit(')',1)[1].split();assert ss[0]not in('Z','X')and int(ss[19])==owner['startticks'];assert any('FLOCK'in p.read_text()and str(st.st_ino)in p.read_text()for p in(pp/'fdinfo').iterdir())
for n in ['private','private-run','publication','base-cache','remote-current','after-source','owner.json','released.json']:
 assert(OLD/n).exists(),n
report={'schema_version':1,'epoch':54,'kind':'INDEPENDENT_ACTUAL_DUPLICATE_PUBLIC_ROOT_CLEANUP_VERIFICATION','checks_passed':True,'actual_cleanup_receipt':ref(actual),'actual_cleanup_intent':ref(attempt),'exact_plan':ref(O/'EXACT_TWO_PUBLIC_ROOT_DELETION_PLAN.v1.json'),'full_precleanup_manifest':ref(O/'ALL_OLD_PUBLIC_FILES_EXACT_PRESERVED_MIRRORS.v1.json'),'only_two_approved_old_public_targets_currently_absent':True,'targets':plan['delete_exact_directory_targets'],'independently_rehashed_all_17384_preserved_mirrors_after_deletion':True,'distinct_preserved_files_hashed':len(cache),'regular_files_accounted':count,'logical_bytes_retired':logical,'all_public_mirrors_unchanged_size_SHA256_and_stat_signature':True,'all_old_kit_control_bytes_preserved':True,'old_W53_parent_and_named_private_operational_journal_basecache_siblings_still_present':True,'scope_private_sibling_integrity':'Rootdeletecodeaddressesonlytwoapprovedrmtreetargets andchecksold-siblingentryinodes. Reviewerconfirms namedprivate/operationalroots exist; doesnotassert independentrehashofprivatedescendantcontent.','original_G19_owner_and_same_inode_FLOCK_still_held':True,'owner':ref(W/'owner.json'),'root_cleanup_source':ref(W/'cleanup_verified_public_duplicates.py'),'review_source':ref(Path(__file__)),'root_memory_before':a['before'],'root_memory_after':a['after'],'headroom_after_bytes':a['after']['memory_max_bytes']-a['after']['memory_current_bytes'],'memory_scope':'SharedsnapshotsnotcandidateincrementalRAM/solecausalityproof. CleanupdoesnotreopenE54orauthorizeanyrerun.','actual_scientific_model_tokenizer_BGE_native_Git_calls_by_this_verifier':0,'all_E54_scientific_slots_remain_closed':True,'wall_seconds':time.monotonic()-start}
p=O/'ACTUAL_OLD_W53_PUBLIC_DUPLICATE_CLEANUP_INDEPENDENT_VERIFICATION.v1.json';b=(json.dumps(report,sort_keys=True,indent=2)+'\n').encode()
with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
print(json.dumps(ref(p)))
