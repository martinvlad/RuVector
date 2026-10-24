"""Pure stdlib algebra/codec/source checks. Never constructs an ML/native object."""
import argparse
import ast
import base64
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rejects(function, *args):
    try:
        function(*args)
    except (ValueError, TypeError):
        return
    raise AssertionError('Malformed synthetic input was accepted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    checks = []
    before = {str(path.relative_to(HERE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in HERE.iterdir() if path.is_file() and path.name not in ('SOURCE_READY.json', 'SOURCE_MANIFEST.json')}
    modules_before = set(sys.modules)
    A, P, V = load('e30_source_only_algorithm', 'algorithm.py'), load('e30_source_only_codec', 'parameter_codec.py'), load('e30_source_only_vector', 'vector_codec.py')
    load('e30_source_only_lazy_model', 'model.py')
    load('e30_source_only_evidence', 'evidence.py')
    load('e30_source_only_context', 'context_engine.py')
    if any(name.split('.')[0] in {'torch', 'transformers', 'numpy', 'onnxruntime', 'tokenizers'} for name in set(sys.modules) - modules_before):
        raise AssertionError('Source-only imports initialized an ML package')
    checks.append('lazy imports use stdlib only, with no model/tokenizer/native object')

    for path in HERE.glob('*.py'):
        ast.parse(path.read_text())
    worker = ast.parse((HERE / 'worker.py').read_text())
    function = next(node for node in worker.body if isinstance(node, ast.FunctionDef) and node.name == 'expected_counters')
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), 'source-only-counter-projection', 'exec'), scope)
    expected = json.loads((HERE / 'EXPECTED_COUNTERS.json').read_text())['expected_operation_counters']
    if any(scope['expected_counters'](phase) != expected[phase] for phase in ('train', 'dev')):
        raise AssertionError('Plan counter projection differs from literal worker source')
    if (expected['train']['NLI_forward_calls_attempted'], expected['dev']['NLI_forward_calls_attempted'],
            expected['train']['optimizer_steps_attempted'], expected['dev']['optimizer_steps_attempted']) != (24, 96, 24, 0):
        raise AssertionError('Frozen phase operation budget differs')
    checks.append('all core ASTs and literal phase-counter projections agree with24+96 budget')

    counts = [math.prod(shape) for _name, shape in A.EXPECTED_TENSORS]
    if (len(counts), sum(counts), sum(counts) * 4, sum(4 * math.ceil(count * 4 / 3) for count in counts)) != (12, 1085443, 4341772, 5789056):
        raise AssertionError('Exact learned closure or per-tensor base64 padding differs')
    if len(set(name for name, _shape in A.EXPECTED_TENSORS)) != 12 or sum(counts[:8]) != 32768 or sum(counts[8:]) != 1052675:
        raise AssertionError('Head/body trainable closure differs')
    if A.TRAINABLE_COUNT - 32768 + A.FROZEN_COUNT != 407344131:
        raise AssertionError('Frozen/original head parameter accounting differs')
    checks.append('exact four-rank4 plus existing-head shapes/count/bytes/base64 closure')

    # Non-square orientation catches A/B reversal; zero-B proves initial delta
    # without running the transformer. dL/dB can be nonzero while dL/dA=0.
    x, a = [2.0, -1.0, 3.0], [[0.25, -0.5, 0.125], [-0.25, 0.125, 0.5]]
    b, gradient = [[0.0, 0.0] for _ in range(4)], [1.0, -2.0, 0.5, 3.0]
    ax = [math.fsum(row[i] * x[i] for i in range(3)) for row in a]
    delta = [2 * math.fsum(row[r] * ax[r] for r in range(2)) for row in b]
    grad_b = [[2 * gradient[o] * ax[r] for r in range(2)] for o in range(4)]
    grad_a = [[2 * math.fsum(gradient[o] * b[o][r] for o in range(4)) * x[i] for i in range(3)] for r in range(2)]
    if any(delta) or any(value for row in grad_a for value in row) or not any(value for row in grad_b for value in row):
        raise AssertionError('Zero-initialized LoRA algebra/gradient proof differs')
    b[1][0], b[3][1] = 0.75, -0.5
    nested = [2 * math.fsum(row[r] * ax[r] for r in range(2)) for row in b]
    composed = [math.fsum(2 * math.fsum(b[o][r] * a[r][i] for r in range(2)) * x[i] for i in range(3)) for o in range(4)]
    if nested != composed or not any(nested):
        raise AssertionError('Scaled B@A geometry differs from nested F.linear')
    checks.append('non-square A-then-B algebra, initial zero delta and possible nonzero first B gradient')

    payload = struct.pack('<4I', 0, 0x80000000, 1, 0x3F800000)
    encoded = P.encode_tensor('synthetic', (4,), payload)
    if P.decode_tensor(encoded, 'synthetic', (4,)) != payload:
        raise AssertionError('Signed-zero/subnormal parameter bits changed')
    for key, value in [('sha256', '0' * 64), ('shape', [2, 2]), ('data_base64', encoded['data_base64'] + '\n')]:
        bad = {**encoded, key: value}
        rejects(P.decode_tensor, bad, 'synthetic', (4,))
    rejects(P.encode_tensor, 'synthetic', (1,), struct.pack('<f', float('nan')))
    vector = struct.pack('<384f', 1, -0.0, *([0] * 382))
    block = V.encode(vector, 1)
    if V.decode(block) != vector:
        raise AssertionError('Lossless normalized BGE source bytes changed')
    bad = copy.deepcopy(block); bad['data_base64'] = base64.b64encode(bytes(1536)).decode('ascii'); bad['sha256'] = hashlib.sha256(bytes(1536)).hexdigest()
    rejects(V.decode, bad)
    checks.append('lossless f32LE parameter/vector bits and malformed hash/base64/nonfinite/norm rejection')

    node_source = r"""
const assert=require('node:assert/strict');
const h=require(process.argv[1]);
const v=new Float32Array(384);v[0]=1;v[1]=-0;
const hit={id:'0',score:0.75,vector:v};
const compact=h.compact(hit,[v]);
assert.equal(compact.score,0.75);assert.deepEqual(compact.raw_keys,['id','score','vector']);
assert.equal(compact.vector_receipt.sha256,compact.vector_receipt.source_sha256);
assert.equal(compact.metadata_receipt.present,false);assert.equal(Object.hasOwn(compact,'vector'),false);
assert.throws(()=>h.compact({...hit,metadata:null},[v]));
assert.throws(()=>h.compact({...hit,id:'00'},[v]));
const wrong=new Float32Array(v);wrong[1]=0;
assert.throws(()=>h.compact({...hit,vector:wrong},[v]));
assert.throws(()=>h.compact({...hit,score:NaN},[v]));
assert.equal(Object.keys(require.cache).filter(p=>p.endsWith('.node')).length,0);
process.stdout.write(JSON.stringify({checks:7,native_addon_loads:0})+'\n');
"""
    subprocess.run(['node', '--check', str(HERE / 'native_helper.cjs')], check=True, capture_output=True, timeout=10)
    node = subprocess.run(['node', '-e', node_source, str(HERE / 'native_helper.cjs')], check=True, text=True, capture_output=True, timeout=10)
    node_receipt = json.loads(node.stdout)
    checks.append('native helper syntax and seven pure compact-hit mutations, no addon load')

    after = {str(path.relative_to(HERE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in HERE.iterdir() if path.is_file() and path.name not in ('SOURCE_READY.json', 'SOURCE_MANIFEST.json')}
    if before != after:
        raise AssertionError('Preflight mutated candidate source')
    result = {'schema_version': 1, 'epoch': 30, 'status': 'PASS_SOURCE_ONLY', 'checks': checks,
        'check_count': len(checks), 'source_sha256': before, 'node_synthetic_receipt': node_receipt,
        'actual_model_initializations': 0, 'actual_tokenizer_initializations': 0,
        'actual_native_addon_loads': 0, 'actual_NLI_calls': 0, 'actual_BGE_calls': 0,
        'actual_annotation_choice_reads': 0, 'source_bytes_unchanged': True}
    with args.out.open('x', encoding='utf-8') as output:
        json.dump(result, output, sort_keys=True, indent=2); output.write('\n')
    print(json.dumps({'status': result['status'], 'checks': len(checks), 'path': str(args.out)}))


if __name__ == '__main__':
    main()
