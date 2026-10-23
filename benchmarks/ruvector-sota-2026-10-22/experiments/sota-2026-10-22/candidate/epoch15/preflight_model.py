"""Static exact-file/ONNX schema check only. No sessions, providers or forwards."""
from pathlib import Path
import hashlib,importlib.util,json
HERE=Path(__file__).resolve().parent
PARSER=HERE.parent/'epoch5/preflight.py'
assert hashlib.sha256(PARSER.read_bytes()).hexdigest()=='835a9e86c4f6983cab5531ee44c2d530738b7c55d61e9b8d9aa2ad6b24487a35'
spec=importlib.util.spec_from_file_location('reviewed_epoch5_static_onnx_parser',PARSER);parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
def inspect():
 model=HERE/'assets/official-deberta-v3-large/onnx/model_quint8_avx2.onnx'
 assert model.stat().st_size==642857089 and hashlib.sha256(model.read_bytes()).hexdigest()=='821dc4407d10a9d25c20c57fcb742ddc20c09bc55c8093557091efb825256754'
 value=parser.inspect_onnx(model)
 value.update(weight_sha256='821dc4407d10a9d25c20c57fcb742ddc20c09bc55c8093557091efb825256754',session_initialized=False,forwards=0,scope='Static protobuf metadata; no ABI/provider/execution or performance claim')
 return value
if __name__=='__main__':
 p=HERE/'onnx-static.json';assert not p.exists();p.write_text(json.dumps(inspect(),indent=2)+'\n');print('Exact official DeBERTa-v3-large QUINT8AVX2 typedONNX static schema verified,0sessions/forwards')
