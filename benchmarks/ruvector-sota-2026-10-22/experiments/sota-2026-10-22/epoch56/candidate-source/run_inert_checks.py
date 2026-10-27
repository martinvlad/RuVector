from pathlib import Path
import ast,json,hashlib,os,subprocess,time
C=Path(__file__).resolve().parent;S=C/'source';rows=[]
for name in ['test_native_accounting.py','test_inert.py']:
 argv=['taskset','-c','0,1','python','-I','-B',str(S/name)]
 started=time.monotonic();r=subprocess.run(argv,capture_output=True,text=True,timeout=30)
 rows.append({'argv':argv,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'wall_seconds':time.monotonic()-started})
 assert r.returncode==0,(name,r.stderr)
asts=[]
for p in sorted(S.glob('*.py')):ast.parse(p.read_text());asts.append(p.name)
node='/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node'
r=subprocess.run([node,'--check',str(S/'native_helper.cjs')],capture_output=True,text=True,timeout=30);assert r.returncode==0
report={'schema_version':1,'epoch':56,'status':'INERT_SOURCE_CHECKS_PASSED','scope':'Invented scalar/token encodings and mocked transport only. No actual tokenizer/model/BGE/native/Gold/API/GPU initialization or corpus batch.','actual_runtime_model_native_imports':0,'actual_native_batches':0,'tests':rows,'Python_AST_files':asts,'Node_syntax_only':{'argv':[node,'--check',str(S/'native_helper.cjs')],'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr},'source_refs':[{'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in sorted(S.iterdir())if p.is_file()],'all_source_files_still_no_pycache':not any(S.rglob('__pycache__'))}
p=C/'INERT_TEST_REPORT.v3.json'
with p.open('x')as f:json.dump(report,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
print(json.dumps({'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'test_counts':[24,29],'AST_files':len(asts),'actual_science_calls':0}))
