"""Hash-bound isolated launcher. No scientific logic or label repair lives here."""
import argparse,hashlib,json,os,runpy,sys
from pathlib import Path
PLAN_SHA='3083581ef07d43a4e64d635de87f9dc78cfcd444746b15215b2791340301ba31'
GOLD_SHA='37383a105cc7b1388f01cc495e7cbe147e6c348850c2abbb48431403cc7f69c7'
SCORER_SHA='693be065fb5cc4236e4f71b766f47f53e1301499008ef10f0a3e3ba425f620c8'
KIND='REAL_CONTRACTNLI_HELDOUT_DEV_TRANSFER_PILOT'
def require(v,msg):
 if not v:raise ValueError(msg)
def unique(pairs):
 out={}
 for k,v in pairs:require(k not in out,'DUPLICATE_METADATA_KEY');out[k]=v
 return out
def read_ref(ref,project=None):
 require(type(ref)is dict and set(ref)=={'path','bytes','sha256'},'EXACT_REFERENCE_REQUIRED');p=Path(ref['path']);p=p if p.is_absolute()else project/p
 require(p.is_file()and not p.is_symlink(),'REGULAR_SOURCE_METADATA_REQUIRED');b=p.read_bytes();require(type(ref['bytes'])is int and len(b)==ref['bytes']and hashlib.sha256(b).hexdigest()==ref['sha256'],'SOURCE_OR_ADMISSION_DRIFT');return b
def load_ref(ref,project=None):return json.loads(read_ref(ref,project),object_pairs_hook=unique)
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--expected-manifest-sha256',required=True);p.add_argument('--target',choices=['gold','scorer'],required=True);p.add_argument('--help-only',action='store_true');p.add_argument('cli_argv',nargs=argparse.REMAINDER);a=p.parse_args()
 require(sys.flags.isolated==1 and sys.flags.dont_write_bytecode==1,'REQUIRE_PYTHON_I_B_FLAGS');mp=Path(a.manifest);mb=mp.read_bytes();require(hashlib.sha256(mb).hexdigest()==a.expected_manifest_sha256,'BOOTSTRAP_MANIFEST_SHA_REQUIRED');m=json.loads(mb,object_pairs_hook=unique);require(m['schema_version']==1 and m['epoch']==40 and m['kind']==KIND and m['plan']['sha256']==PLAN_SHA,'EXACT_E40_MANIFEST_REQUIRED');project=Path(m['project']);require(project.is_absolute()and project.resolve()==project,'EXACT_NON_SYMLINK_PROJECT_REQUIRED');plan=load_ref(m['plan'],project);require(plan['actual_project']==str(project)and plan['source_freeze']==m['source_freeze']and plan['source_freeze_sha256']==m['source_freeze']['sha256'],'EXACT_FROZEN_PLAN_REQUIRED');freeze=load_ref(m['source_freeze'],project)
 source=load_ref(m['source_admission'],project);independent=load_ref(source['independent_actual_source_readback'],project);require(source['checks_passed']is True and source['verified_actual_remote_readback']is True and source['actual_source_commit']==source['published_source_commit']==source['source_commit']==m['actual_source_commit']and source['plan_sha256']==source['source_plan_sha256']==PLAN_SHA and source['source_freeze_sha256']==m['source_freeze']['sha256'],'ACTUAL_SOURCE_ADMISSION_REQUIRED');require(source['independent_actual_source_readback']==m['independent_source_readback']and independent['checks_passed']is True and independent['verified_actual_remote_readback']is True and independent['commit']==m['actual_source_commit']and independent['source_plan_sha256']==PLAN_SHA and independent['source_freeze_sha256']==source['source_freeze_sha256']and independent['tree_sha']==source['tree_sha'],'INDEPENDENT_SOURCE_READBACK_REQUIRED')
 audit=project/m['audit_relative_directory'];require(audit.resolve()==audit and audit.is_dir(),'EXACT_AUDIT_DIRECTORY_REQUIRED');frozen=[v for v in freeze['entries']if v['path'].startswith(m['audit_relative_directory']+'/')and v['path'].endswith('.py')];require(frozen==m['audit_python_modules']and len(frozen)==22,'EXACT_SOURCE_AUDIT_MODULE_SET_REQUIRED')
 require(type(plan['pins'])is list and len(plan['pins'])==221 and len({v['path']for v in plan['pins']})==221,'EXACT_221_SOURCE_PLAN_PINS_REQUIRED')
 for ref in plan['pins']:read_ref(ref,project)
 for ref in frozen:read_ref(ref,project)
 # -B prevents writes but can read an old cache. Refuse any such unpinned code.
 require(not any(audit.rglob('*.pyc')),'UNPINNED_BYTECODE_CACHE_FORBIDDEN');top={Path(x['path']).name for x in frozen if Path(x['path']).parent.as_posix()==m['audit_relative_directory']};require({x.name for x in audit.glob('*.py')}==top and not any(audit.glob('*.so')),'UNPINNED_TOP_LEVEL_IMPORT_SOURCE_FORBIDDEN');require(not any(x.name.startswith('contractnli_')and x.is_dir()for x in audit.iterdir()),'UNPINNED_MODULE_PACKAGE_FORBIDDEN');require(not any(n.startswith('contractnli_')for n in sys.modules),'PREEXISTING_CUSTODIAN_MODULE_FORBIDDEN')
 gold_admission=load_ref(m['gold_admission'],project);require(gold_admission['source_commit']==m['actual_source_commit']and gold_admission['source_plan_sha256']==PLAN_SHA and gold_admission['root_custodian_authorized']is True and gold_admission['approved_late_gold_read']is True and gold_admission['evidence']['plan']==m['plan']and gold_admission['evidence']['source_admission']==m['source_admission'],'EXACT_ONCE_GOLD_ADMISSION_REQUIRED')
 target=m['targets'][a.target];require(target['sha256']==(GOLD_SHA if a.target=='gold'else SCORER_SHA)and target in frozen,'FROZEN_TARGET_REQUIRED');argv=list(a.cli_argv);argv=argv[1:]if argv[:1]==['--']else argv
 if a.help_only:require(argv in[[],['--help']],'HELP_SMOKE_ONLY');argv=['--help']
 elif a.target=='gold':
  q=argparse.ArgumentParser(add_help=False)
  for k in ['project','admission','expected-admission-sha256','out']:q.add_argument('--'+k,required=True)
  g=q.parse_args(argv);require(g.project==str(project)and g.admission==m['gold_admission']['path']and g.expected_admission_sha256==m['gold_admission']['sha256'],'UNCHANGED_GOLD_CLI_ADMISSION_REQUIRED');out=Path(g.out);require(out.is_absolute()and not out.exists()and not out.is_symlink()and not out.is_relative_to(project),'NEW_EXTERNAL_GOLD_OUTPUT_REQUIRED');vaults=[x for x in plan['external_data_assets']if x['role']=='dev_oracle'];require(len(vaults)==1,'EXACT_ONE_VAULT_REFERENCE_REQUIRED');marker=Path(vaults[0]['path']+'.DECODE_ATTEMPT.json');require(not marker.exists()and not marker.is_symlink(),'EXISTING_VAULT_ATTEMPT_STOP_NO_RETRY')
 # Source hashes were verified before this sole added import directory. -I
 # retains its default trusted stdlib paths; no cwd/PYTHONPATH is appended.
 sys.path.insert(0,str(audit));sys.argv=[str(project/target['path']),*argv];runpy.run_path(str(project/target['path']),run_name='__main__')
if __name__=='__main__':main()
