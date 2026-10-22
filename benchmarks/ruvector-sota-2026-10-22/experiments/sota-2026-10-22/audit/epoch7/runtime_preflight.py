"""Actual isolated22-file native closure, Python metadata and resolve-only; never loads addon."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.metadata,json,os,subprocess,sys
O=Path(__file__).resolve().parent;S=O.parents[1];P=S/'epoch7/project'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
core=json.loads((S/'epoch4/runtime-repair/official-package-closure.json').read_text());ts=json.loads((S/'epoch5/typesafe-runtime-closure.json').read_text())
files=[x for package in core['packages'] for x in package['files']]+ts['files']
for x in files:
 p=P/x['path'];current=p
 while current!=P:
  assert not current.is_symlink(),str(current)
  current=current.parent
 assert p.is_file() and p.stat().st_size==x['bytes'] and sha(p)==x['sha256'],x['path']
assert len(files)==22
entries=['retrieval/node_modules/@ruvector/core/index.js','retrieval/node_modules/ruvector-core-linux-x64-gnu/index.js','retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node','node_modules/@ruvector/typesafe/index.js','node_modules/@ruvector/typesafe/native/linux-x64-gnu/typesafe.linux-x64-gnu.node']
script='const fs=require("fs");const xs=JSON.parse(process.argv[1]);process.stdout.write(JSON.stringify(xs.map(p=>require.resolve(p))));'
r=subprocess.run(['node','--no-addons','--no-global-search-paths','-e',script,json.dumps([str(P/x) for x in entries])],text=True,capture_output=True,check=True)
assert json.loads(r.stdout)==[str(P/x) for x in entries]
versions={k:importlib.metadata.version(k) for k in ['numpy','onnxruntime','tokenizers']};assert versions=={'numpy':'2.2.6','onnxruntime':'1.22.1','tokenizers':'0.21.4'}
result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'actual_project':str(P),'complete_native_files_checked':22,'native_closure':[dict(x) for x in files],'resolve_only_entrypoints':entries,'resolve_only_node_arguments':['--no-addons','--no-global-search-paths'],'resolved_exact_project_paths':json.loads(r.stdout),'Python_versions':versions,'Python_executable':sys.executable,'scope':'Read-only hashes/materialized path closure and Node require.resolve only. No import/require of package entrypoint/addon, ABI-load or ONNX provider/session compatibility claim.','actual_addon_or_model_or_native_forwards':0}
p=O/'runtime-independent-v1.json';p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks_passed':True,'sha256':sha(p),'files':22,'entrypoints':5}))
