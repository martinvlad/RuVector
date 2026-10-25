"""One exact root-authorized asset call. No model/case/tokenizer/native import."""
from pathlib import Path
import hashlib,importlib.util,json,sys,stat
sys.dont_write_bytecode=True
W=Path("/tmp/ruvector-sota-2026-10-22/epoch39-74dbbcb10508");R=W/'project'
q=W/'ASSET_RUNTIME_REQUEST.v1.json'
assert hashlib.sha256(q.read_bytes()).hexdigest()=='afdc17afdd0a0dd988b4ebef180526a17eeba8c8a288d304caa6e18d46e41393'
p=R/'experiments/sota-2026-10-22/candidate/epoch39/runtime/materialize_assets_v3.py'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='70db96e6468198439e096835c31d0fea24cac8415eb54cae09a25a3b8cf8f2b5'
source_pins={'experiments/sota-2026-10-22/candidate/epoch39/asset_identity.py': 'f271c0077be23c34fbb29cfb5728d671371a4646ac9030072ec7b538eb819499', 'experiments/sota-2026-10-22/candidate/epoch39/MODEL_B354_ASSETS.expected.json': '30657c23de7feae478af2b951c814ff5e4be3c69c7a90c08d0f268a2172eea11', 'experiments/sota-2026-10-22/candidate/epoch39/MODEL_XXLARGE_ASSETS.expected.json': 'a65cda75fc67d2c935eac4b998fa5d3a6e375bbfbd7212dd19d998d15b016806', 'experiments/sota-2026-10-22/candidate/epoch39/runtime/model_assets_guard.py': '6e882ede6cdd849f9533add70b7a7b4a66509dd040715987e55bfca8ccebead2', 'experiments/sota-2026-10-22/candidate/epoch39/runtime/materialize_assets.py': '2598ee74d84152558d111efeac0359d2176bfab146dd27eee1de6e8b9c93c0bd', 'experiments/sota-2026-10-22/candidate/epoch39/test_asset_preparation.py': 'b4480b063b26783d3efe5ec83a41f9cf5fd2040397cf5554eb0aa1ecd806ae93'}
source_pins['experiments/sota-2026-10-22/candidate/epoch39/runtime/materialize_assets_v2.py']='83a6267174d2ee8af0e30af50bf189cf133175298e29520a023ff973e8795e15'
source_pins['experiments/sota-2026-10-22/candidate/epoch39/test_asset_snapshot_v2.py']='7ba490666cf7a4d81976dee2ea9cd7d830626717f2e771ef878926355ff14c23'
assert hashlib.sha256((W/'ASSET_REUSE_PLAN.v3.1.json').read_bytes()).hexdigest()=='87d2c38bb777c09a1111edb7d583630a8b2063058869b2385f524c464c4e17de'
source_pins['experiments/sota-2026-10-22/candidate/epoch39/runtime/materialize_assets_v3.py']='70db96e6468198439e096835c31d0fea24cac8415eb54cae09a25a3b8cf8f2b5'
source_pins['experiments/sota-2026-10-22/candidate/epoch39/test_asset_readonly_v3.py']='53e3684bf2250a9ed29d9462c807bb8d795dc2bb2329a591aab59a2ab4d8a92d'
for relative,expected in source_pins.items():
 source=R/relative
 assert stat.S_ISREG(source.stat().st_mode)and not any(x.is_symlink()for x in(source,*source.parents))
 assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
assert not list((R/'experiments/sota-2026-10-22/candidate/epoch39').rglob('__pycache__'))
s=importlib.util.spec_from_file_location('e39_one_asset_preparation_source',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
result=m.prepare_assets(W/'ASSET_REUSE_PLAN.v3.1.json',root=R,runtime_request=json.loads(q.read_text()))
assert not any(k in sys.modules for k in ('torch','transformers','tokenizers','numpy','onnxruntime','safetensors'))
print(json.dumps({'source_return':result,'ML_modules_imported':False},allow_nan=False))
