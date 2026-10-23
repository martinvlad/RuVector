"""Static FP32 ONNX schema inspection. No sessions, native initialization or forwards."""
from pathlib import Path
import hashlib,importlib.util,json
HERE=Path(__file__).resolve().parent
PARSER=HERE.parent/'epoch5/preflight.py'
assert hashlib.sha256(PARSER.read_bytes()).hexdigest()=='835a9e86c4f6983cab5531ee44c2d530738b7c55d61e9b8d9aa2ad6b24487a35'
spec=importlib.util.spec_from_file_location('reviewed_epoch5_static_onnx_parser',PARSER)
parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def inspect():
 model=HERE/'assets/fp32/onnx/model.onnx'
 assert model.stat().st_size==1741989392 and sha(model)=='9fbf57959bd9143720289cd1eab1aaaa00fc99459fd25ffeff8eba1ccf955d2b'
 value=parser.inspect_onnx(model)
 assert not any(value['operators'].get('::'+op,0) for op in ('QuantizeLinear','DynamicQuantizeLinear','MatMulInteger','QLinearMatMul'))
 value.update(weight_sha256='9fbf57959bd9143720289cd1eab1aaaa00fc99459fd25ffeff8eba1ccf955d2b',weight_bytes=1741989392,session_initialized=False,forwards=0,scope='Static protobuf graph metadata. No ABI/provider/execution/performance or exact-original-weight fidelity claim.')
 return value
if __name__=='__main__':
 with (HERE/'onnx-static.json').open('x') as stream:json.dump(inspect(),stream,indent=2);stream.write('\n')
 print('Exact FP32 ONNX graph schema verified; zero sessions/forwards')
