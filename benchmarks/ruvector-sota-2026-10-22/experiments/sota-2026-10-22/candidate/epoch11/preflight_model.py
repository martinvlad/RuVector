"""Static exact-file/ONNX schema check only. No sessions, providers or forwards."""
from pathlib import Path
import hashlib,importlib.util,json
HERE=Path(__file__).resolve().parent
PARSER=HERE.parent/'epoch5/preflight.py'
assert hashlib.sha256(PARSER.read_bytes()).hexdigest()=='835a9e86c4f6983cab5531ee44c2d530738b7c55d61e9b8d9aa2ad6b24487a35'
spec=importlib.util.spec_from_file_location('reviewed_epoch5_static_onnx_parser',PARSER);parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
def inspect():
 model=HERE/'assets/nli-large-threeway/onnx/model_quantized.onnx'
 assert model.stat().st_size==642587600 and hashlib.sha256(model.read_bytes()).hexdigest()=='f28cc7e69eb2834597c5ef2336f2adb7398b7bcb019282fb3f11d0130a3c0010'
 value=parser.inspect_onnx(model)
 value.update(weight_sha256='f28cc7e69eb2834597c5ef2336f2adb7398b7bcb019282fb3f11d0130a3c0010',session_initialized=False,forwards=0,scope='Static protobuf metadata; no ABI/provider/execution or performance claim')
 return value
if __name__=='__main__':
 p=HERE/'onnx-static.json';assert not p.exists();p.write_text(json.dumps(inspect(),indent=2)+'\n');print('Exact large typedONNX static schema verified,0sessions/forwards')
