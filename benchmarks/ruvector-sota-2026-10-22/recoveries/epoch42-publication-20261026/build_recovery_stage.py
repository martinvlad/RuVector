"""NEW archive recovery controls/stage only; no Git/science execution."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,copy,json,zipfile,base64
import recovery_common as c

def leaf(p,b):return {'path':p,'mode':'100644','type':'blob','sha':c.git(b),'size':len(b)}
def build(a):
 owner=c.held_owner();out=c.canonical(a.out);c.need(out==c.W/'prepared'and not out.exists(),'Exact exclusive new-generation prepared stage required');kit=c.canonical(a.source_kit)
 oldcp=c.parse(kit/'CHECKPOINT_MANIFEST.json');oldcont=c.parse(kit/'CONTINUATION.json');oldactive=c.parse(kit/'ACTIVE_RUN.json');c.need(len(oldcp['project_files'])==7180,'Exact current SOURCE CP7180')
 mapraw=c.body(a.source_map);c.need(c.sha(mapraw)==a.expected_source_map_sha256,'Independent fresh source-map bytes drift');sm=json.loads(mapraw);c.need(sm.get('source_commit')==c.PARENT or sm.get('sha')=='de27f1bc72951c0baf28568c223e32b27cb35079','Source-map commit/scope authority');rows=sm.get('files',sm.get('tree'));rows=[r for r in rows if r.get('type')!='tree'];before={r['path']:{k:r[k]for k in('path','mode','type','sha','size')}for r in rows};c.need(len(before)==7254 and c.tree_sha(before)=='de27f1bc72951c0baf28568c223e32b27cb35079','Exact current7254Git map/scopeSHA')
 for name in('CONTINUATION.json','ACTIVE_RUN.json','CHECKPOINT_MANIFEST.json'):c.need(before[name]==leaf(name,c.body(kit/name)),'Current source controls mismatch')
 zipbody=c.body(c.ARCHIVE);c.need((len(zipbody),c.sha(zipbody),c.git(zipbody))==(4531795,c.ARCHIVE_SHA,c.ARCHIVE_GIT),'Archive identity')
 with zipfile.ZipFile(c.ARCHIVE)as z:
  cp=json.loads(z.read('unpublished-desired-controls/CHECKPOINT_MANIFEST.json'));desired=json.loads(z.read('unpublished-desired-controls/CONTINUATION.json'));epoch=json.loads(z.read('public-project/experiments/sota-2026-10-22/epoch42/EPOCH_MANIFEST.json'))
 c.need(len(cp['project_files'])==7247 and epoch['status']=='REJECTED_DEV_PILOT'and epoch['dev_passed']is False,'Original scientific reject only')
 oldrows={r['path']:r for r in oldcp['project_files']};allrows={r['path']:r for r in cp['project_files']};c.need(all(c.same(allrows.get(p),r)for p,r in oldrows.items()),'All7180 source CP rows preserved')
 assets={};table=c.parse(a.files)['files']
 for row in table:
  p=c.relative(row['path']);c.need(p.startswith(c.NEW),'Only new recovery namespace');b=c.body(row['local_path']);c.need((len(b),c.sha(b))==(row['bytes'],row['sha256']),'Reviewed artifact drift');c.need(c.git(b)!=c.FORBIDDEN,'Forbidden complete blob');c.need(p not in assets,'Duplicate recovery artifact');
  if p.endswith('.zip'):c.need((p,len(b),c.sha(b))in((c.NEW+'immutable-e42-artifacts.zip',4531795,c.ARCHIVE_SHA),(c.NEW+'public-provenance-supplement.zip',181734,'a1b9281b8e9db12e0daa46da26f7e662e768c7e47df17326a76cdeb7822828e4')),'Only exact two reviewed binary ZIPs permitted')
  assets[p]=b
 c.need(c.NEW+'immutable-e42-artifacts.zip'in assets and assets[c.NEW+'immutable-e42-artifacts.zip']==zipbody,'Exact original ZIP required')
 proj=json.loads(assets[c.NEW+'ARCHIVE_PROJECTED_FILES.v1.json']);c.need(len(proj['project_files'])==287 and len(proj['additional_archive_backed_CP_only_paths'])==67,'Exact projection287/67')
 ledgerpath=c.NEW+'REJECTION_LEDGER.recovery.v1.json';ledger=json.loads(assets[ledgerpath]);c.need(len(ledger['rejections'])==35 and len(ledger['preparation_blocks'])==6,'Preserve35/6')
 def aref(p):return {'path':p,'bytes':len(assets[p]),'sha256':c.sha(assets[p])}
 manifestpath=c.NEW+'RECOVERY_CHECKPOINT_MANIFEST.json'
 manifest={'schema_version':1,'epoch':42,'publication_kind':'NEW_ARCHIVE_PROJECTED_RECOVERY_NOT_ORIGINAL_FINAL','original_FINAL_published':False,'status':'REJECTED_DEV_PILOT','dev_passed':False,'source_commit':c.PARENT,'archive':aref(c.NEW+'immutable-e42-artifacts.zip'),'archive_Git_blob_sha1':c.ARCHIVE_GIT,'projection':aref(c.NEW+'ARCHIVE_PROJECTED_FILES.v1.json'),'restoration_adapter':aref(c.NEW+'restore_epoch42_archive.py'),'current_rejection_ledger':aref(ledgerpath),'original_frozen_EPOCH':{'path':'experiments/sota-2026-10-22/epoch42/EPOCH_MANIFEST.json','bytes':80681,'sha256':'59defa2997b255453f8804c35975818c5fd4e221e4ad149a7a85e04c7df9bc4b','transport':'archive-projected'},'original_source_pins':223,'original_actual_execution':epoch['actual_execution'],'cumulative_execution':epoch['cumulative_execution'],'used_confirmation_identities':[],'all_slots_closed':True,'phase_remaining':epoch['phase_remaining'],'official_goal_verified':False,'champion_native104_unchanged':True,'original_blob5_invocation':'UNKNOWN_PERMANENTLY_NEVER_REPLAYED','new_transaction_limit':1,'files':[aref(p)for p in sorted(assets)]}
 assets[manifestpath]=c.pretty(manifest)
 for p,b in assets.items():c.need(p not in allrows,'Recovery namespace collision');allrows[p]={'path':p,'bytes':len(b),'sha256':c.sha(b)}
 cp['project_files']=[allrows[p]for p in sorted(allrows)];cp['epoch42_archive_recovery']={'archive':aref(c.NEW+'immutable-e42-artifacts.zip'),'projection':aref(c.NEW+'ARCHIVE_PROJECTED_FILES.v1.json'),'extractor':aref(c.NEW+'restore_epoch42_archive.py'),'required_before_bootstrap':True,'materialize_to_KIT_and_project':True,'archive_backed_project_files':67,'legacy_CP_only_originals':3}
 active={'schema_version':1,'epoch':42,'run_id':owner['run_id'],'state':'EPOCH42_ARCHIVE_RECOVERY_CLOSED','publication_recovery_only':True,'original_scientific_run_id':'epoch42-222874558c0b','work_active':False,'experiments_active':False,'all_slots_closed':True,'phase_remaining':epoch['phase_remaining'],'checkpoint_parent':c.PARENT,'scope':owner['scope'],'physical_owner':owner,'physical_guardian_directory':str(c.W),'OS_lock_held':True,'OS_lock_release_pending':True,'OS_lock_observation_scope':'PREPUBLICATION_SNAPSHOT_NOT_CURRENT_REMOTE_LEASE'}
 for k in('native_allowed','conditional_train_allowed','conditional_dev_allowed','conditional_calibration_allowed','conditional_engineering_allowed','confirmation_allowed','conditional_confirmation_allowed','paid_calls_allowed','GPU_calls_allowed'):active[k]=0
 cont=copy.deepcopy(desired);original_final=cont.pop('epoch42_final',None);cont['epoch42_scientific_outcome']=original_final;cont['active_run']=dict(active,path='ACTIVE_RUN.json');cont['prior_published_base_commit']=c.PARENT;cont['checkpoint_manifest_sha256']=c.sha(c.pretty(cp));cont['rejection_ledger']=aref(ledgerpath)
 cont['epoch42_archive_recovery']={'manifest':aref(manifestpath),'status':'SCIENTIFIC_REJECT_CHECKPOINT_ARCHIVE_PROJECTED','original_FINAL_published':False,'original_blob5_execution':'UNKNOWN_PERMANENTLY','original_WAL_sha256':c.OLD_WAL_SHA,'forbidden_Git_object_sha1_forensic_string':c.FORBIDDEN,'never_create_or_tree_reference_forbidden_object':True,'archive_transport':cp['epoch42_archive_recovery'],'all_scientific_slots_closed':True,'publication_only_generation':3}
 if cont.get('epochs')and cont['epochs'][-1].get('epoch')==42:cont['epochs'][-1]['publication_kind']='NEW_ARCHIVE_PROJECTED_RECOVERY';cont['epochs'][-1]['original_FINAL_published']=False;cont['epochs'][-1]['recovery_manifest']=aref(manifestpath)
 for k in('champion','used_confirmation_sets','epoch27_data_roles','artifact_transport','epoch26_artifact_transports','epoch26_restore'):c.need(c.same(cont.get(k),oldcont.get(k)),'Protected history changed: '+k)
 controls={'CONTINUATION.json':c.pretty(cont),'ACTIVE_RUN.json':c.pretty(active),'CHECKPOINT_MANIFEST.json':c.pretty(cp)}
 expected=copy.deepcopy(before)
 for p,b in {**assets,**controls}.items():c.need(c.git(b)!=c.FORBIDDEN,'Forbidden tree object');expected[p]=leaf(p,b)
 changed={**assets,**controls};c.need(all(expected.get(p)==r for p,r in before.items()if p not in controls),'Old source Git tuple changed')
 out.mkdir(mode=0o700);public=out/'public-files';public.mkdir();ctr=out/'controls';ctr.mkdir();stage=out/'stage';stage.mkdir();(stage/'transport').mkdir()
 source_table=[]
 for p,b in sorted(assets.items()):
  if p==c.NEW+'immutable-e42-artifacts.zip':local=c.ARCHIVE
  else:local=public/p;c.write(local,b)
  source_table.append({'path':p,'local_path':str(local),'bytes':len(b),'sha256':c.sha(b),'GitSHA':c.git(b)})
 for p,b in controls.items():c.write(ctr/p,b)
 entries=[];blobs=[]
 for p,b in sorted(changed.items()):
  entry={'path':c.SCOPE+p,'mode':'100644','type':'blob'}
  if len(b)>32768:
   args={'repository_full_name':'ruvnet/RuVector','content':base64.b64encode(b).decode()if p.endswith('.zip')else b.decode(),'encoding':'base64'if p.endswith('.zip')else'utf-8'};raw=c.encoded(args);c.need(len(raw)<c.BLOB_CAP,'Blob cap');file='transport/blob-%03d.json'%len(blobs);c.write(stage/file,raw);blobs.append({'id':'e42-archive-recovery-g3-v1-blob-'+str(len(blobs)),'path':p,'file':file,'bytes':len(raw),'sha256':c.sha(raw),'body_bytes':len(b),'body_sha256':c.sha(b),'GitSHA':c.git(b)});entry['sha']=c.git(b)
  else:entry['content']=b.decode()
  entries.append(entry)
 groups=[];batch=[]
 for entry in entries:
  if len(batch)>=32 or len(c.encoded({'tree_elements':batch+[entry]}))>=c.TREE_CAP:groups.append(batch);batch=[]
  batch.append(entry)
 if batch:groups.append(batch)
 trees=[]
 for i,group in enumerate(groups):
  raw=c.encoded({'tree_elements':group});c.need(len(raw)<c.TREE_CAP,'Tree cap');file='transport/tree-%03d.json'%i;c.write(stage/file,raw);trees.append({'id':'e42-archive-recovery-g3-v1-tree-'+str(i),'file':file,'bytes':len(raw),'sha256':c.sha(raw),'entries':len(group)})
 leaves=c.encoded({'scope':c.SCOPE,'files':[expected[p]for p in sorted(expected)]});c.write(stage/'expected-leaves.json',leaves)
 meta={'schema_version':1,'kind':'ONE_DISTINCT_E42_ARCHIVE_RECOVERY_TRANSACTION','original_FINAL_completed':False,'original_blob5_execution':'UNKNOWN_PERMANENTLY','forbidden_object':c.FORBIDDEN,'source_parent':c.PARENT,'expected_source_root':'6df9bc196bfd9d24273e657422c1e4d8adb5be02','expected_source_bench':'b12c05ac9dc0144f0b9014ec98301d4c3f12100b','expected_source_scope':'de27f1bc72951c0baf28568c223e32b27cb35079','old_Git_leaves':7254,'new_Git_leaves':len(expected),'old_CP_rows':7180,'new_CP_rows':len(allrows),'old_noncontrol_tuples_preserved':True,'new_namespace':c.NEW,'blobs':blobs,'trees':trees,'expected_leaves':{'file':'expected-leaves.json','bytes':len(leaves),'sha256':c.sha(leaves)},'archive_Git_sha1':c.ARCHIVE_GIT,'remote_archive_body_SHA256_downloaded':False,'request_decoded_bytes_and_ACK_plus_tree_identity_binding_required':True,'mutation_ID_order':[r['id']for r in blobs+trees]+['e42-archive-recovery-g3-v1-commit','e42-archive-recovery-g3-v1-ref'],'root_caller_receipt_O_EXCL_fsync_required':True}
 c.write(stage/'metadata.json',c.pretty(meta));c.write(out/'source-table.json',c.pretty({'files':source_table}));c.write(out/'overlay-manifest.json',c.pretty({'files':[{'path':p,'bytes':len(b),'sha256':c.sha(b)}for p,b in sorted(changed.items())]}));return {'out':str(out),'new_CP_rows':len(allrows),'new_Git_leaves':len(expected),'metadata_sha256':c.sha(c.pretty(meta))}
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for name in('source-kit','source-map','files','out'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--expected-source-map-sha256',required=True)
 print(json.dumps(build(p.parse_args()),sort_keys=True))
