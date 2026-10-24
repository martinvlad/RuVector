"""Refreeze only operational owner literals after generation1 failed before execution."""
from pathlib import Path
import argparse,json,hashlib,os,copy
P='experiments/sota-2026-10-22/'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def row(root,name):
 f=root/name;assert f.resolve()==f and f.is_file();return {'path':name,'bytes':f.stat().st_size,'sha256':sha(f)}
def encoded(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def put_new(p,value):
 with p.open('xb')as f:f.write(encoded(value));f.flush();os.fsync(f.fileno())
def replace_exact(p,oldhash,value):
 assert sha(p)==oldhash;temp=p.with_name(p.name+'.generation2.pending');put_new(temp,value);os.replace(temp,p)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--publication-parent',required=True);a=ap.parse_args();root=a.project;study=root/P/'epoch23';scope=root.parent;archive=study/'recovery/generation1'
 owner=json.loads((scope/'owner.json').read_text());assert owner['pid']==66088 and owner['startticks']==12864421 and owner['original_expiry_preserved'] is True
 assert not(study/'NATIVE_ADMISSION.json').exists() and not(study/'ATTEMPT_RESERVATION.json').exists() and not(study/'runs').exists()
 oldplan=archive/'plan.json';oldfreeze=archive/'source-freeze.json';assert sha(oldplan)=='85dba296706246e401fd3e9f7cb89aac24fce056c87e49a4e5f8175e4b5e5f9c' and sha(oldfreeze)=='ab8cf0ef6cd59e30466231ddc2bf065d7ea72b8a04eded9c4df161eba2d9187a'
 plan=json.loads(oldplan.read_text());freeze=json.loads(oldfreeze.read_text());changed={P+'candidate/epoch23/worker.py':archive/'worker.py',P+'epoch23/preparation/launch_engineering_v1.py':archive/'launch_engineering_v1.py'}
 current=[];deltas=[]
 for r in freeze['source_entries']:
  now=row(root,r['path'])
  if r['path'] in changed:
   prior=changed[r['path']];assert sha(prior)==r['sha256'];before=prior.read_text();assert (root/r['path']).read_text()==before.replace('64876','66088').replace('12480585','12864421');deltas.append({'path':r['path'],'before_sha256':r['sha256'],'after_sha256':now['sha256'],'only_delta':'owner PID/startticks literals'})
  else:assert now==r
  current.append(now)
 assert len(current)==23 and len(deltas)==2
 report={'schema_version':1,'epoch':23,'plan_generation':2,'reason':'Original supervisor absent and its FLOCK independently free before native admission; cause unproven. Generation1 physical admission failed, no worker was ever admitted or reserved.','old_plan':row(root,str(oldplan.relative_to(root))),'old_freeze':row(root,str(oldfreeze.relative_to(root))),'archive_manifest':row(root,P+'epoch23/recovery/generation1/ARCHIVE_MANIFEST.json'),'source_deltas':deltas,'unchanged_prior_source_entries':21,'scientific_hypothesis_fixture_scorer_thresholds_and_benchmark_roles_unchanged':True,'native_BGE_NLI_execution_before_rebind':0,'no_attempt_budget_reset_or_increase':True,'generation2_owner':{'pid':66088,'startticks':12864421,'original_expires_at':owner['expires_at']},'published_recovery_lease':a.publication_parent,'physical_independent_review_sha256':'878edc0d9a03c9b78ee4d3b0c303bfa68b48c7eb4e81a009f5f050d8009d6fa2','runtime_reverification':'All17498CPUwheelmembers and10runtimeassets exact; reviewed source restore --verify-only passed again. No model/native/tokenizer call.'}
 reportpath=study/'recovery/SOURCE_RECOVERY.json';put_new(reportpath,report)
 current += [row(root,P+'epoch23/recovery/SOURCE_RECOVERY.json'),row(root,P+'epoch23/recovery/rebind_unexecuted_plan_v2.py')]
 newfreeze=copy.deepcopy(freeze);newfreeze['source_entries']=sorted(current,key=lambda r:r['path']);newfreeze['plan_generation']=2;newfreeze['superseded_unexecuted_generation1']=report['old_freeze'];newfreeze['operational_owner']=report['generation2_owner']
 replace_exact(study/'source-freeze.json',sha(oldfreeze),newfreeze);freezerow=row(root,P+'epoch23/source-freeze.json')
 plan['pins']=newfreeze['source_entries']+[freezerow];plan['source_freeze_sha256']=freezerow['sha256'];plan['publication_parent']=a.publication_parent;plan['plan_generation']=2;plan['operational_owner']=report['generation2_owner'];plan['supersedes_unexecuted_plan']=report['old_plan'];plan['no_measurements_existed_under_prior_generation']=True
 replace_exact(study/'plan.json',sha(oldplan),plan)
 result={'status':'UNEXECUTED_OWNER_RECOVERY_FROZEN_GENERATION2','plan':row(root,P+'epoch23/plan.json'),'freeze':freezerow,'source_entries':len(current),'plan_pins':len(plan['pins']),'native_BGE_NLI_calls':0,'source_deltas':deltas};put_new(scope/'plan-generation2-rebind-receipt.json',result);print(json.dumps(result))
if __name__=='__main__':main()
