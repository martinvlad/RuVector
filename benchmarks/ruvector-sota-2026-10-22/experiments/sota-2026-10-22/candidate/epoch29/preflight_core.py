"""Pure source/codec/cosine/failure checks; no corpus/model/native API calls."""
import argparse
import ast
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    checks = []
    owned = [here / name for name in ('worker.py', 'bge_encoder.py', 'vector_codec.py',
        'native_identity.cjs', 'RAW_SCHEMA.json', 'preflight_core.py')]
    for path in owned:
        if path.suffix == '.py':
            ast.parse(path.read_text(), filename=str(path))
    subprocess.run(['node', '--check', str(here / 'native_identity.cjs')], check=True)
    worker = load('e29_pure_worker', here / 'worker.py')
    encoder = load('e29_lazy_bge_module', here / 'bge_encoder.py')
    V = worker.V
    assert encoder.BATCH_SIZE == 8 and encoder.MAX_TOKENS == 256 and encoder.DIMENSIONS == 384
    assert not any(name in sys.modules for name in ('numpy', 'onnxruntime', 'tokenizers', 'torch', 'transformers'))
    checks.append('core_source_syntax_and_import_are_model_tokenizer_native_lazy')
    # A complete synthetic matrix tests bit preservation, not a model prediction.
    payload = bytearray(262 * 384 * 4)
    for row in range(262):
        struct.pack_into('<f', payload, row * 1536 + (row if row < 261 else 17) * 4, 1.0)
    struct.pack_into('<f', payload, 4, -0.0)
    block = V.encode_matrix(bytes(payload), 262)
    decoded, vectors = V.decode_matrix(block)
    assert decoded == payload and len(vectors) == 262
    assert struct.pack('<f', vectors[0][1]) == struct.pack('<f', -0.0)
    for mutation in ({**block, 'sha256': 'a' * 64}, {**block, 'shape': [263, 384]},
                     {**block, 'data_base64': block['data_base64'] + '!'}):
        try:
            V.decode_matrix(mutation)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError('Malformed matrix accepted')
    bad = bytearray(payload)
    struct.pack_into('<f', bad, 0, float('nan'))
    try:
        V.decode_matrix(V.encode_matrix(bytes(bad), 262))
    except ValueError:
        pass
    else:
        raise AssertionError('Nonfinite numeric evidence accepted')
    checks.append('lossless_float32le_roundtrip_signed_zero_and_malformed_nonfinite_rejections')
    source_legacy = ' '.join('ＦＵＬＬ    Contract\n'.casefold().split())
    other_legacy = ' '.join('full contract'.casefold().split())
    assert V.text_sha(source_legacy) != V.text_sha(other_legacy)
    assert V.bge_text(source_legacy) == V.bge_text(other_legacy) == 'full contract'
    assert V.bge_text('A  B\nC') == 'a  b\nc'
    checks.append('historical_alias_hash_is_separate_from_whitespace_preserving_NFKC_model_input')
    counters = {'dense_cosines_attempted': 0, 'dense_cosines_completed': 0}
    q = (1.0,) + (0.0,) * 383
    top, count = V.dense_top16(q, [10, 2, 30], [q, q, q], 30, counters)
    assert [row['document_id'] for row in top] == [2, 10] and count == 2
    assert [row['cosine'] for row in top] == [1.0, 1.0]
    assert counters == {'dense_cosines_attempted': 2, 'dense_cosines_completed': 2}
    assert 261 * 260 + 261 == worker.POSITIVE['dense_cosines_completed'] == 68121
    checks.append('dense_self_excluded_before_actual_dots_and_numeric_document_ID_tie_rule')
    with tempfile.TemporaryDirectory(prefix='e29-core-pure-', dir=args.output.parent) as temporary:
        temporary = Path(temporary)
        matrix_path = temporary / 'matrix.json'
        matrix_path.write_text(json.dumps(block))
        script = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const core=require(process.argv[1]),block=JSON.parse(fs.readFileSync(process.argv[2]));
const decoded=core.decodeMatrix(block),ids=Array.from({length:261},(_,i)=>i+1).concat(548),corpus=new Set(ids.slice(0,261));
assert.equal(decoded.vectors.length,262);assert.equal(Object.is(decoded.vectors[0][1],-0),true);
const hit={id:'1',score:0.125,distance:0.875,vector:Object.fromEntries(Array.from(decoded.vectors[0],(value,i)=>[String(i),value]))};
const compact=core.compactHit(hit,ids,decoded.vectors,corpus);
assert.equal(compact.score,hit.score);assert.equal(compact.distance,hit.distance);
assert.deepEqual(compact.raw_keys,['id','score','distance','vector']);
assert.equal(compact.vector_receipt.sha256,crypto.createHash('sha256').update(decoded.bytes.subarray(0,1536)).digest('hex'));
assert.equal('vector' in compact,false);assert.equal(compact.metadata_receipt.present,false);
assert.equal(compact.metadata_receipt.sha256,crypto.createHash('sha256').update('{"present":false}').digest('hex'));
assert.throws(()=>core.compactHit({...hit,metadata:null},ids,decoded.vectors,corpus));
assert.throws(()=>core.compactHit({...hit,id:'01'},ids,decoded.vectors,corpus));
assert.throws(()=>core.compactHit({...hit,id:'548'},ids,decoded.vectors,corpus));
const changed=structuredClone(hit);changed.vector['1']=1;assert.throws(()=>core.compactHit(changed,ids,decoded.vectors,corpus));
const missing=structuredClone(hit);delete missing.vector['383'];assert.throws(()=>core.compactHit(missing,ids,decoded.vectors,corpus));
assert.throws(()=>core.decodeMatrix({...block,sha256:'b'.repeat(64)}));
assert.equal(Object.keys(require.cache).some(name=>name.endsWith('.node')),false);
process.stdout.write(JSON.stringify({vector_sha256:compact.vector_receipt.sha256,native_addon_loads:0}));
'''
        output = json.loads(subprocess.check_output(['node', '-e', script,
            str(here / 'native_identity.cjs'), str(matrix_path)], text=True))
        assert output['native_addon_loads'] == 0
        assert output['vector_sha256'] == hashlib.sha256(payload[:1536]).hexdigest()
        original_dump, original_handler = worker.json.dump, signal.getsignal(signal.SIGALRM)
        def stopped(signum, frame):
            raise TimeoutError('synthetic checkpoint interruption')
        def interrupting_dump(value, target, **kwargs):
            original_dump(value, target, **kwargs)
            signal.raise_signal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, stopped)
        worker.json.dump = interrupting_dump
        try:
            try:
                worker.atomic_checkpoint({'counters': {'attempted': 1}, 'literal': 'Ω'}, temporary)
            except TimeoutError:
                pass
            else:
                raise AssertionError('Pending stop signal was not delivered')
        finally:
            worker.json.dump = original_dump
            signal.signal(signal.SIGALRM, original_handler)
        assert json.loads((temporary / 'raw.partial.json').read_text()) == {'counters': {'attempted': 1}, 'literal': 'Ω'}
        assert not (temporary / 'raw.partial.pending.json').exists()
    checks.append('native_compact_receipt_preserves_original_fields_and_rejects_source_or_metadata_mismatch_without_addon')
    checks.append('pending_stop_delivered_after_complete_atomic_raw_checkpoint')
    assert not any(name in sys.modules for name in ('numpy', 'onnxruntime', 'tokenizers', 'torch', 'transformers'))
    report = {'schema_version': 1, 'epoch': 29, 'kind': worker.C.KIND,
        'status': 'PURE_CORE_PREFLIGHT_PASS', 'checks': checks, 'check_count': len(checks),
        'model_tokenizer_native_initializations': 0, 'model_forwards': 0, 'native_searches': 0,
        'corpus_text_or_choice_reads': 0, 'validated_sources': [
            {'path': str(path.relative_to(worker.C.ROOT)), 'bytes': path.stat().st_size,
             'sha256': worker.C.sha(path)} for path in owned]}
    worker.C.put(args.output, report)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
