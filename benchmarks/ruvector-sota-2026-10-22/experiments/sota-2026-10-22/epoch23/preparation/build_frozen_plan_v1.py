"""Freeze one engineering candidate, independently authored cases/scorer and empty benchmark roles."""
from pathlib import Path
import argparse,json,hashlib,os

PREFIX='experiments/sota-2026-10-22/'
SOURCE='99efd3517516f3089ea2c669add1c2b1fa521fb1'
def pin(root,name):
 p=root/name;assert p.resolve()==p and p.is_file() and not p.is_symlink();b=p.read_bytes();return {'path':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def put(path,value):
 b=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
 with path.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 return {'path':str(path),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--project',required=True,type=Path)
 for k in ('worker','oracle','protocol'):ap.add_argument('--expected-'+k+'-sha',required=True)
 a=ap.parse_args();root=a.project;study=root/PREFIX/'epoch23';assert root.resolve()==root
 names=[PREFIX+x for x in ['candidate/epoch23/scope.py','candidate/epoch23/worker.py','candidate/epoch23/native.cjs','candidate/epoch23/PREPARATION.json','candidate/epoch3/models.py','audit/epoch23/fixtures.json','audit/epoch23/oracle.py','audit/epoch23/protocol.json','epoch23/ENGINEERING_CONTRACT.json','epoch23/PLAN_SPEC.json','epoch23/USED_IDENTITIES.json','epoch23/research/model-admission.json','epoch23/preparation/runtime-assets.lock.json','epoch23/preparation/restore_runtime_v1.py','epoch23/preparation/runtime-restoration.json','epoch23/preparation/launch_engineering_v1.py','epoch23/preparation/build_frozen_plan_v1.py','epoch23/preparation/PREPARATION_NOTES.json','epoch17/preparation/runtime-closure.json','epoch17/preparation/python-wheel-identities.json']]+['assets.lock.json']
 names += [PREFIX+'audit/epoch23/'+x for x in ['oracle-selfcheck-v2.json','oracle-preparation-v2.json']]
 rows=[pin(root,name) for name in sorted(names)];by={r['path']:r for r in rows}
 for k in ('worker','oracle','protocol'):
  name=PREFIX+('candidate/epoch23/worker.py' if k=='worker' else 'audit/epoch23/'+k+('.py' if k=='oracle' else '.json'))
  assert by[name]['sha256']==getattr(a,'expected_'+k+'_sha')
 contract=by[PREFIX+'epoch23/ENGINEERING_CONTRACT.json'];assert contract['sha256']=='e493ce94cb47022c46669750643b87ef5c79b1da840bb2f2e6741e0cc330a502'
 fixtures=json.loads((root/PREFIX/'audit/epoch23/fixtures.json').read_text());assert fixtures['contract_sha256']==contract['sha256'] and fixtures['license']=='CC0-1.0' and len(fixtures['cases'])==25
 roles=dict.fromkeys(['train','dev','calibration','confirmation'],[]);runtime=json.loads((study/'preparation/runtime-assets.lock.json').read_text());assert len(runtime['assets'])==10
 freeze={'schema_version':1,'epoch':23,'source_checkpoint':SOURCE,'kind':'AUTHOR_ANNOTATED_SOURCE_SCOPE_ENGINEERING_ONLY','contract_sha256':contract['sha256'],'benchmark_roles':roles,'source_entries':rows,'external_runtime_assets':runtime['assets'],'data_selection':'Independently authored engineering fixture identities frozen before one actual worker; no benchmark cases or label-based selection.','no_confirmation_consumption':True,'not_benchmark_generalization':True}
 frozen=put(study/'source-freeze.json',freeze);freeze_row=pin(root,PREFIX+'epoch23/source-freeze.json')
 plan={'schema_version':1,'epoch':23,'kind':'SOURCE_SCOPE_ENGINEERING','source_checkpoint':SOURCE,'publication_parent':'eb40957109b64815cae17e98aa1f637cc7433a35','actual_project':str(root),'worker_path':PREFIX+'candidate/epoch23/worker.py','inference_python':str(root/'retrieval/.venv/bin/python'),'benchmark_roles':roles,'fixtures_path':PREFIX+'audit/epoch23/fixtures.json','fixtures_sha256':by[PREFIX+'audit/epoch23/fixtures.json']['sha256'],'source_freeze_path':freeze_row['path'],'source_freeze_sha256':freeze_row['sha256'],'runtime_assets_lock_path':PREFIX+'epoch23/preparation/runtime-assets.lock.json','runtime_assets_lock_sha256':by[PREFIX+'epoch23/preparation/runtime-assets.lock.json']['sha256'],'python_expected_versions':runtime['python_expected_versions'],'pins':rows+[freeze_row],'limits':{'worker_attempts':1,'native_corpus_batches':1,'cpu_threads':2,'seconds_per_batch':600,'paid_calls':0,'GPU_calls':0},'expected_engineering_cases':25,'expected_actual_native_queries':17,'expected_global_invalid_graphs':8,'expected_separate_source_only_guards':51,'metrics':'Engineering integrity/retention/latency/resources/errors only; accuracy,Brier,NLL are null/inapplicable.','semantic_reader':None,'champion_promotion_allowed':False,'publisher_submission_allowed':False,'confirmation_execution_allowed':False,'failure_policy':'No retry, tuning, source edit or identity/threshold replacement after actual frozen execution. All unspent slots close.'}
 plan['execution_runtime_observed_before_measurement']={'node':'v24.19.0','Python':'3.12.14','version_commands_only_no_native_model_initialization':True}
 result=put(study/'plan.json',plan);print(json.dumps({'plan':result,'freeze':frozen,'frozen_source_entries':len(rows),'benchmark_roles':roles,'native_model_calls':0}))
if __name__=='__main__':main()
