from pathlib import Path
import hashlib,json,shutil,subprocess,os,urllib.request
from datetime import datetime,timezone
r=Path('/workspace/ruvector-eval');s=r/'experiments/sota-2026-10-22';e=s/'epoch13';kit=e/'durable-kit';kit.mkdir(exist_ok=False);mapping=json.loads((e/'durable-files.json').read_text());cache=s/'epoch12/publication/stage';network=0
for x in mapping['files']:
 src=cache/x['path'];dst=kit/x['path'];assert src.is_file(),'Missing verified cache; obtain only with connectedGitHub:'+x['path'];b=src.read_bytes();assert len(b)==x['bytes'];assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==x['git_blob_sha1'],x['path'];dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
c=json.loads((kit/'CONTINUATION.json').read_text());assert hashlib.sha256((kit/'CHECKPOINT_MANIFEST.json').read_bytes()).hexdigest()==c['checkpoint_manifest_sha256'];project=e/'project';cmd=['python','-B',str(kit/'restore_checkpoint.py'),'--dest',str(project),'--base-local-directory',str(s/'epoch12/project')];result=subprocess.run(cmd,check=True,capture_output=True,text=True);(e/'reconstruction.log').write_text(result.stdout+result.stderr);receipt=json.loads(result.stdout);(e/'reconstruction.json').write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'source_commit':mapping['commit'],'remote_gitblobs_verified':len(mapping['files']),'source_manifest_SHA256':c['checkpoint_manifest_sha256'],'kit_network_GETs':network,'receipt':receipt,'native_or_model_calls':0},indent=2)+'\n')
# Exact reviewed optional source-data restoration.
a=subprocess.run(['python','-B',str(kit/'restore_epoch3_data.py'),'--dest',str(project),'--archive-local',str(s/'legal-transfer/epoch3/sources/original-contractnli.zip')],check=True,capture_output=True,text=True);(e/'data-restoration.json').write_text(a.stdout)
# Restore all pinned candidate4 assets from verified cache; no inference.
lock=json.loads((kit/'experiments/sota-2026-10-22/candidate/epoch4/assets.lock.json').read_text());assets=[]
for x in lock['assets']:
 src=r/x['path'];dst=project/x['path'];assert src.stat().st_size==x['bytes'];assert hashlib.sha256(src.read_bytes()).hexdigest()==x['sha256'];dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():os.link(src,dst)
 assert hashlib.sha256(dst.read_bytes()).hexdigest()==x['sha256'];assets.append(x)
# Complete actual8+14 runtime closure, no package imports.
helper=kit/'experiments/sota-2026-10-22/candidate/epoch5/reconstruction/restore_runtime.py'
a=subprocess.run(['python','-B',str(helper),'--project-root',str(project),'--core-cache-root',str(s/'epoch12/project'),'--typesafe-cache-root',str(s/'epoch12/project'),'--receipt',str(e/'native-runtime-restoration.json')],check=True,capture_output=True,text=True)
(project/'retrieval/.venv').symlink_to(r/'retrieval/.venv',target_is_directory=True)
(e/'cache-bindings.json').write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'assets':assets,'runtime_helper_stdout':a.stdout,'source_only':True,'model_native_calls':0,'dependency_installs':0,'Python_cache':'retrieval/.venv exact versions checked separately'},indent=2)+'\n');print(json.dumps({'restored_source':receipt,'complete_runtime22':True,'assets':len(assets),'allhashes_verified':True,'model_native_calls':0}))

