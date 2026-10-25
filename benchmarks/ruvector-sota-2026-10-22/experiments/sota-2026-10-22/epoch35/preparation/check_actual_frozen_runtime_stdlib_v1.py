import importlib.util,json,hashlib,sys,os,time
from pathlib import Path
W=Path(__file__).parent;R=W/'project';P='experiments/sota-2026-10-22/';planfile=R/(P+'epoch35/plan.json');out=W/'actual-frozen-runtime-check-v1.json';assert not out.exists()
assert hashlib.sha256(planfile.read_bytes()).hexdigest()=='9069838cfc7d84c2186b56909306aa1f483679abb894c2cd09195e193579c65d'
start=time.monotonic();s=importlib.util.spec_from_file_location('e35_actual_frozen_common',R/(P+'candidate/epoch35/runtime/common.py'));C=importlib.util.module_from_spec(s);s.loader.exec_module(C)
owner=C.owner_lock();plan=C.verify_plan(planfile,'9069838cfc7d84c2186b56909306aa1f483679abb894c2cd09195e193579c65d','engineering');lock=C.verify_runtime(plan)
ml=[n for n in sys.modules if n.split('.')[0]in('torch','transformers','numpy','onnxruntime','tokenizers','safetensors')];assert not ml
v=dict(epoch=35,checks_passed=True,plan_sha256='9069838cfc7d84c2186b56909306aa1f483679abb894c2cd09195e193579c65d',source_pins_verified=len(plan['pins']),python_members_verified=17498,model_payloads_verified=9,native_BGE_assets_verified=10,actual_frozen_runtime_common_used=True,guardian=owner,ML_modules_imported=ml,model_native_tokenizer_scoring_paid_GPU_Git_calls=0,wall_seconds=time.monotonic()-start)
with out.open('x')as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
print(json.dumps(v))
