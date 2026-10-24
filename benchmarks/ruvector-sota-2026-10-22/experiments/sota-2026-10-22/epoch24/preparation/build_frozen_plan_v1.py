"""CC0-1.0. Freeze an engineering-only raw-source candidate before one native run.

No training, benchmark annotations, model initialization, or external mutations.
The independent scorer/gold remains held outside the worker, committed by hash.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess
P='experiments/sota-2026-10-22/'
SOURCE='cbebac41850908bcb69bb7a1a7d18aa67312e8f8'
def pin(root,name):
 p=root/name;assert p.resolve()==p and p.is_file() and not p.is_symlink();b=p.read_bytes();return {'path':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def put(path,value):
 with path.open('x') as f:json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def main():
 a=argparse.ArgumentParser();a.add_argument('--project',type=Path,required=True);a.add_argument('--publication-parent',required=True)
 for k in ('worker','contract','protocol','audit-seal'):a.add_argument('--expected-'+k+'-sha',required=True)
 n=a.parse_args();root=n.project;assert root.resolve()==root;study=root/P/'epoch24';roles={k:[] for k in ('train','dev','calibration','confirmation')}
 for f in ('plan.json','source-freeze.json'):assert not (study/f).exists()
 names=[]
 for rel in ('candidate/epoch24','audit/epoch24','legal-transfer/epoch24','epoch24'):
  for f in sorted((root/P/rel).rglob('*')):
   if f.is_file():
    assert not f.is_symlink() and '__pycache__' not in f.parts and '.venv' not in f.parts;names.append(f.relative_to(root).as_posix())
 names+=[P+'candidate/epoch3/models.py',P+'epoch17/preparation/runtime-closure.json',P+'epoch17/preparation/python-wheel-identities.json']
 rows=[pin(root,name) for name in sorted(set(names))];by={r['path']:r for r in rows}
 required={'worker':P+'candidate/epoch24/worker.py','contract':P+'epoch24/ENGINEERING_CONTRACT.json','protocol':P+'audit/epoch24/protocol.json','audit_seal':P+'audit/epoch24/scorer-seal.json'}
 for k,name in required.items():assert by[name]['sha256']==getattr(n,'expected_'+k+'_sha'),name
 fixtures_path=P+'legal-transfer/epoch24/engineering-inputs.json';fixtures=json.loads((root/fixtures_path).read_text());assert fixtures['epoch']==24 and fixtures['license']=='CC0-1.0' and len(fixtures['cases'])==24 and fixtures['contract_sha256']==by[required['contract']]['sha256']
 runtime_path=P+'epoch24/preparation/runtime-assets.lock.json';runtime=json.loads((root/runtime_path).read_text());assert len(runtime['assets'])==10
 seal=json.loads((root/required['audit_seal']).read_text())
 freeze={'schema_version':1,'epoch':24,'kind':'RAW_TEXT_AUTOMATIC_STRUCTURE_ENGINEERING_ONLY','source_checkpoint':SOURCE,'benchmark_roles':roles,'source_entries':rows,'external_runtime_assets':runtime['assets'],'independent_scorer_seal':seal,'data_selection':'24 independently authored CC0 raw-text structural engineering cases; candidate held before unseen input disclosure, manual gold/scorer frozen by exact hash outside worker input.','no_confirmation_consumption':True,'not_benchmark_generalization':True}
 put(study/'source-freeze.json',freeze);frozen=pin(root,P+'epoch24/source-freeze.json')
 plan={'schema_version':1,'epoch':24,'kind':'SOURCE_SCOPE_ENGINEERING','source_checkpoint':SOURCE,'publication_parent':n.publication_parent,'actual_project':str(root),'worker_path':P+'candidate/epoch24/worker.py','inference_python':str(root/'retrieval/.venv/bin/python'),'benchmark_roles':roles,'fixtures_path':fixtures_path,'fixtures_sha256':by[fixtures_path]['sha256'],'source_freeze_path':frozen['path'],'source_freeze_sha256':frozen['sha256'],'runtime_assets_lock_path':runtime_path,'runtime_assets_lock_sha256':by[runtime_path]['sha256'],'python_expected_versions':runtime['python_expected_versions'],'pins':rows+[frozen],'limits':{'worker_attempts':1,'native_corpus_batches':1,'cpu_threads':2,'seconds_per_batch':600,'paid_calls':0,'GPU_calls':0},'expected_engineering_cases':24,'expected_actual_native_queries':24,'expected_native_query_count_scope':'Frozen upper bound: at most one native query per raw case with extracted units; exact valid count is observed, never a score.','metrics':'Exact structural extraction/closure engineering, latency, resource use, errors; benchmark accuracy/Brier/NLL null/inapplicable.','semantic_reader':None,'champion_promotion_allowed':False,'publisher_submission_allowed':False,'confirmation_execution_allowed':False,'operational_owner':{'pid':68322,'startticks':13304876,'lock_inode':13626},'failure_policy':'No retry, source edits, threshold or fixture changes after measurement; retain failures and close all unspent slots.'}
 plan['execution_runtime_observed_before_measurement']={'Python':subprocess.check_output(['python3','--version'],text=True).strip(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'version_commands_only_no_native_model_initialization':True}
 put(study/'plan.json',plan);print(json.dumps({'plan':pin(root,P+'epoch24/plan.json'),'freeze':frozen,'source_entries':len(rows),'benchmark_roles':roles,'native_or_model_initializations':0}))
if __name__=='__main__':main()
