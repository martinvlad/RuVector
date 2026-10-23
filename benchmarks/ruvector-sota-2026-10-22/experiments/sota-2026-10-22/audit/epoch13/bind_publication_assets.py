"""Explicit offline cold asset/data reconstruction and cached replay; zero inference."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,subprocess,sys
O=Path(__file__).resolve().parent;S=O.parents[1];E=S/'epoch13';COLD=O/'publication-cold-project-v1';P=E/'project';PUB=E/'publication'
def obj(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(name,value):
 p=O/name
 with p.open('x')as f:json.dump(value,f,indent=2);f.write('\n')
 return sha(p)
ap=argparse.ArgumentParser();ap.add_argument('--expected-map',required=True);a=ap.parse_args();assert sha(PUB/'publication-map.json')==a.expected_map
review=obj(O/'publication-cold-review-v1.json');assert review['checks_passed'] and review['reviewed_map_sha256']==a.expected_map
plan=obj(E/'plan.json');assert sha(E/'plan.json')=='6aba06f350bb077c604ce2931bf95e302ea91cfac05c9990185d868ec6e82ac3' and len(plan['pins'])==196
assets=obj(S/'candidate/epoch13/assets.lock.json')['assets'];assert len(assets)==22;bindings=[];verified=[]
for x in assets:
 src=P/x['path'];dst=COLD/x['path'];assert src.is_file() and not src.is_symlink() and src.stat().st_size==x['bytes'] and sha(src)==x['sha256']
 if not dst.exists():
  dst.parent.mkdir(parents=True,exist_ok=True);os.link(src,dst);bindings.append({**x,'method':'Explicit offline regular-file hardlink from exact hashverified actual project asset; no model/native initialization or forward'})
 assert not dst.is_symlink() and dst.resolve().is_relative_to(COLD.resolve()) and dst.stat().st_size==x['bytes'] and sha(dst)==x['sha256'];verified.append({'path':x['path'],'bytes':x['bytes'],'sha256':x['sha256']})
receipts=[];stage=PUB/'stage';helper=stage/'restore_epoch3_data.py'
for flags in [['--archive-local',str(P/'experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-contractnli.zip')],['--verify-only']]:
 r=subprocess.run([sys.executable,'-B',str(helper),'--dest',str(COLD),*flags],capture_output=True,text=True,timeout=30,check=True);receipt=json.loads(r.stdout);assert receipt['network_requests']==receipt['model_calls']==0;receipts.append(receipt)
for x in plan['pins']:assert sha(COLD/x['path'])==x['sha256'],x['path']
assert sha(PUB/'publication-map.json')==a.expected_map
bindinghash=save('publication-asset-bindings-v1.json',{'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'source_cold_review_sha256':sha(O/'publication-cold-review-v1.json'),'reviewed_map_sha256':a.expected_map,'all196actual_planpins_verified_after_explicit_bindings':True,'all22active_assetpins_verified_cold':verified,'assetbindings':bindings,'source_data_restore_receipts':receipts,'archive_and_members_pinned_by_reviewed_spec':True,'older_nonactive_models_not_restored':'Historical epoch9/11/12 assets remain explicitly omitted; no claim their archived controllers run. Active196pins/22assetpins+native22+originaldata restore only.','model_session_native_forwards_fit_paid_or_network_calls':0})
local=O/'cold-local-only-v1';local.mkdir(exist_ok=False);output=local/'cached-actual-complete.json';environment=dict(os.environ,OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1')
r=subprocess.run([sys.executable,'-B',str(COLD/'experiments/sota-2026-10-22/audit/epoch13/replay_actual_v1.py'),'--project',str(COLD),'--out',str(output),'--expected-plan-sha',sha(E/'plan.json')],capture_output=True,text=True,timeout=60,check=True,env=environment)
original=obj(O/'actual-independent-v1.json');replayed=obj(output);assert replayed['checks_passed'];left=dict(original);right=dict(replayed);left.pop('at');right.pop('at');assert left==right
compacthash=save('cold-cached-replay-independent-v1.json',{'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'reviewed_map_sha256':a.expected_map,'asset_bindings_sha256':bindinghash,'frozen_replay_source_sha256':sha(COLD/'experiments/sota-2026-10-22/audit/epoch13/replay_actual_v1.py'),'original_actual_independent_sha256':sha(O/'actual-independent-v1.json'),'local_only_full_replay_sha256':sha(output),'every_original_report_field_except_top_timestamp_identical':True,'all196scientificpins_verified_cold':True,'strict_DEV_gate_passed':False,'CONF_consumed':False,'status':replayed['status'],'metrics':replayed['metrics'],'source_only_reconstruction':'Reviewed bootstrap+restore source/data, native22, exact22active assetpins verified; unknown historical model assets not claimed restored.','model_native_session_fit_paid_or_network_calls':0,'scope':'Pure cached saved-output replay; no archived controller/model execution or quality/SOTA claim.'})
print(json.dumps({'checks_passed':True,'asset_bindings_sha256':bindinghash,'compact_cached_replay_sha256':compacthash,'new_explicit_bindings':len(bindings),'active_assets_verified':len(verified)}))
