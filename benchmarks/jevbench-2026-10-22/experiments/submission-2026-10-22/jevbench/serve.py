"""Serve an explicitly selected frozen candidate using the measured native engine.

No benchmark dataset or expected labels are loaded. This command does not deploy
anything or open a provider resource; network exposure is the operator's choice.
"""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import threading
from engine import CompositeEngine,server

ROOT=Path(__file__).resolve().parents[3]

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--policy-directory',type=Path,required=True)
 parser.add_argument('--runtime-manifest',type=Path,required=True)
 parser.add_argument('--host',default='127.0.0.1')
 parser.add_argument('--port',type=int,default=8787)
 parser.add_argument('--audit',type=Path)
 parser.add_argument('--validate-only',action='store_true')
 args=parser.parse_args();directory=args.policy_directory.resolve()
 plan_path=directory/'plan.json';plan=json.loads(plan_path.read_text())
 runtime=json.loads(args.runtime_manifest.read_text())
 digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
 if digest(plan_path)!=runtime['selected_plan']['sha256']:raise ValueError('Selected plan identity mismatch')
 if digest(Path(__file__))!=runtime['serving_entrypoint']['sha256']:raise ValueError('Serving entrypoint identity mismatch')
 for name,expected in plan['source_sha256'].items():
  p=ROOT/name
  if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('Frozen source identity mismatch: '+name)
 for asset in runtime['model_assets']:
  p=ROOT/asset['path']
  if p.is_symlink() or not p.resolve().is_relative_to(ROOT) or digest(p)!=asset['sha256']:raise ValueError('Frozen model asset identity mismatch')
 if args.validate_only:
  print(json.dumps({'status':'source_and_model_asset_identity_valid','model':'ruvector-native-submission-'+directory.name,'source_count':len(plan['source_sha256']),'model_asset_files':len(runtime['model_assets']),'native_model_executed':False}));return
 engine=CompositeEngine(directory/'rules.py')
 if (engine.receipt['binary_sha256']!=plan['native_candidate']['binary_sha256'] or
     engine.receipt['model_manifest_sha256']!=runtime['expected_model_manifest_sha256'] or
     engine.receipt['package_version']!=runtime['package_version']):
  engine.close();raise ValueError('Frozen native binary identity mismatch')
 httpd=server.make_server(engine,args.host,args.port,args.audit)
 for sig in [signal.SIGINT,signal.SIGTERM]:signal.signal(sig,lambda *_:threading.Thread(target=httpd.shutdown,daemon=True).start())
 print(json.dumps({'status':'ready','model':engine.name,'endpoint':f'http://{args.host}:{httpd.server_port}/v1/systemone','receipt':engine.receipt}),flush=True)
 try:httpd.serve_forever()
 finally:httpd.server_close();engine.close()

if __name__=='__main__':main()
