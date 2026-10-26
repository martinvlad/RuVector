"""Write static source/metadata findings only; imports and executes no ML framework."""
import ast
import hashlib
import json
import os
from pathlib import Path

W = Path('/dev/shm/ruvector-sota-2026-10-22/epoch48-37b29244dcf5')
OWN = Path(__file__).resolve().parent


def reference(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def emit(name, value):
    p = OWN / name; b = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    f = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.write(f, b); os.fsync(f); os.close(f)
    return reference(p)


def main():
    structural_path = OWN / 'CHECKPOINT_STRUCTURAL_RESULT.v1.json'
    structural = json.loads(structural_path.read_bytes())
    assert reference(structural_path)['sha256'] == 'a4a3824fc300256d0a3cdf615805b846a8e21be5583ad999b14bceabb90abc09'
    verify_path = W / 'CURRENT_RUNTIME_ASSET_VERIFICATION.v1.json'
    assert reference(verify_path)['sha256'] == '6ccaecb9808624d216f23c939c0994877b53461030dd15e829f576ba57cb50e1'
    vr = json.loads(verify_path.read_bytes()); mr = vr['python_member_manifest']
    assert reference(Path(mr['path'])) == mr
    members = {x['path']: x for x in json.loads(Path(mr['path']).read_bytes())}
    base = Path(vr['runtime_directory'])
    selected = ['lib/python3.12/site-packages/transformers/models/roberta/modeling_roberta.py',
                'lib/python3.12/site-packages/torch/serialization.py',
                'lib/python3.12/site-packages/torch/nn/modules/module.py']
    code = {}; refs = []
    for relative in selected:
        p = base / relative; b = p.read_bytes(); x = members[relative]
        assert len(b) == x['bytes'] and hashlib.sha256(b).hexdigest() == x['sha256']
        refs.append(reference(p)); code[relative] = (b.decode(), ast.parse(b))
    roberta, rt = code[selected[0]]
    cls = next(x for x in rt.body if isinstance(x, ast.ClassDef) and x.name == 'RobertaForSequenceClassification')
    init = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == '__init__')
    forward = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == 'forward')
    init_source = ast.get_source_segment(roberta, init)
    assert 'RobertaModel(config, add_pooling_layer=False)' in init_source
    statements = [ast.get_source_segment(roberta, x) for x in forward.body
                  if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id in
                   ['sequence_output', 'logits'] for t in x.targets)]
    assert statements == ['sequence_output = outputs[0]', 'logits = self.classifier(sequence_output)']
    embeddings = next(x for x in rt.body if isinstance(x, ast.ClassDef) and x.name == 'RobertaEmbeddings')
    buffers = [ast.get_source_segment(roberta, x) for x in ast.walk(embeddings)
               if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == 'register_buffer']
    serialization, st = code[selected[1]]
    load = next(x for x in st.body if isinstance(x, ast.FunctionDef) and x.name == 'load')
    mmap_blocks = [ast.get_source_segment(serialization, x) for x in ast.walk(load)
                   if isinstance(x, ast.If) and isinstance(x.test, ast.Name) and x.test.id == 'mmap']
    assert mmap_blocks and any('UntypedStorage.from_file' in x for x in mmap_blocks)
    module_source, mt = code[selected[2]]
    module_cls = next(x for x in mt.body if isinstance(x, ast.ClassDef) and x.name == 'Module')
    state_load = next(x for x in module_cls.body if isinstance(x, ast.FunctionDef) and x.name == 'load_state_dict')
    assert any(x.arg == 'assign' for x in state_load.args.args + state_load.args.kwonlyargs)
    source_freeze = W / 'project/experiments/sota-2026-10-22/epoch48/SOURCE_FREEZE.json'
    assert reference(source_freeze)['sha256'] == 'c0638d695b8f094fceecca1b230ff4e662e06a327320aa31c18d464703da9746'
    sf = json.loads(source_freeze.read_bytes())
    reader_ref = next(x for x in sf['files'] if x['path'] == 'experiments/sota-2026-10-22/runtime/epoch48/reader.py')
    reader_path = W / 'project' / reader_ref['path']; reader = reader_path.read_text()
    assert reference(reader_path)['bytes'] == reader_ref['bytes'] and reference(reader_path)['sha256'] == reader_ref['sha256']
    assert reader.index('self.model = RobertaForSequenceClassification(cfg).float().cpu()') < reader.index('state = torch.load(')
    evidence = {'schema_version': 1, 'epoch': 48, 'method': 'AST and UTF8 source inspection only; source modules never imported',
        'runtime_current_verification': reference(verify_path), 'wheel_member_manifest': mr,
        'verified_library_source_files': refs, 'actual_frozen_reader': reference(reader_path),
        'source_freeze': reference(source_freeze),
        'RobertaForSequenceClassification_constructor': init_source,
        'classifier_forward_evidence': statements,
        'nonpersistent_embedding_buffers': buffers,
        'torch_load_signature': ast.unparse(load.args),
        'torch_load_mmap_static_blocks': mmap_blocks,
        'load_state_dict_signature': ast.unparse(state_load.args),
        'model_or_tensor_or_runtime_execution': 0}
    er = emit('FRAMEWORK_SOURCE_EVIDENCE.v1.json', evidence)
    pooler_bytes = sum(x['storage_bytes'] for x in structural['pooler_tensors'])
    original = structural['zip']['storage_payload_bytes']
    report = {'schema_version': 1, 'epoch': 48, 'status': 'STATIC_POSTMORTEM_COMPLETE_NO_RETRY_OR_INFERENCE',
        'structural_result': reference(structural_path), 'framework_source_evidence': er,
        'inspection_source': reference(OWN / 'inspect_checkpoint_metadata.py'),
        'report_builder_source': reference(Path(__file__)),
        'actual_failure_as_reported_by_Root': {'worker_exit_signal': 'SIGKILL', 'worker_exit_code': -9,
            'last_reader_stage': 'READER_INITIALIZE_BEFORE', 'worker_wall_seconds': 22.999,
            'outer_wall_seconds': 23.1486, 'worker_max_rss_kib': 2301268,
            'NLI_forecasts_completed': 0, 'NLI_forward_progress': 0,
            'native_corpora_completed': 1, 'native_indexes': 4, 'native_insertions': 207,
            'native_queries': 12, 'native_hit_vector_bit_validations': 621,
            'BGE_forwards': 31, 'BGE_texts': 219,
            'Root_sent_signal': False,
            'scope': 'Root actual process capture is the authority; this independent task inspects source/container metadata only.'},
        'failure_causation': {'status': 'UNPROVEN',
            'shared_cgroup_memory_max_bytes': 17179869184, 'observed_current_bytes': 14913155072,
            'observed_peak_bytes': 17180618752, 'observed_oom_counter': 3,
            'observed_oom_kill_counter': 1, 'pre_run_counter_baseline_available': False,
            'dmesg_available': False,
            'interpretation': 'Shared high memory and cumulative oom_kill are consistent with memory pressure, but do not attribute this SIGKILL. No counter delta or kernel victim record exists.'},
        'new_verified_findings': {'original_checkpoint_is_ZIP_STORED': True,
            'ZIP_members': 397, 'tensor_storage_members': 395,
            'all_storage_payload_offsets_64_byte_aligned': True,
            'pickle_metadata_bytes': 84919, 'pickle_opcode_count': 15151,
            'all_declared_tensor_storage_dtype': 'float32', 'tensor_count': 395,
            'parameter_numel': 356412419, 'original_storage_bytes': original,
            'all_four_classifier_tensors_present': True,
            'original_pooler_tensors_present': structural['pooler_tensors'],
            'serialized_position_ids_present': False, 'serialized_token_type_ids_present': False,
            'modern_constructor_adds_pooler': False,
            'prospective_strict_key_mismatch': 'Original checkpoint has two learned pooler tensors; modern RobertaForSequenceClassification creates RobertaModel(add_pooling_layer=False). Current strict loader would reject these unexpected keys if execution reached that check. This is discovered statically; it was not observed as the cause of the killed run.',
            'classifier_uses_sequence_output_only': True},
        'memory_analysis': {'current_reader_allocates_full_FP32_model_before_loading_state': True,
            'original_checkpoint_storage_bytes': original,
            'modern_model_storage_estimate_excluding_original_unused_pooler_bytes': original - pooler_bytes,
            'two_full_storage_copies_lower_bound_bytes': 2 * original - pooler_bytes,
            'scope': 'Tensor-storage arithmetic only, not measured simultaneous RSS or a causal OOM proof. Runtime, activations, allocators, mapped/shared pages, source-cache duplicates and shared workloads are additional or differently accounted.'},
        'prospective_faithful_loader_plan_NOT_EXECUTED': [
            'Freeze a new source epoch before any actual model/reader attempt; retain this epoch closed with zero forecasts and null quality metrics.',
            'Use only exact pinned original ZIP asset and reviewed Torch2.7.1 weights_only=True, map_location=cpu and mmap=True; no ordinary pickle fallback and no conversion to new weights.',
            'Construct architecture on the meta device so constructor initialization does not allocate a second full CPU parameter set. Explicitly retain the original pooler module and both learned pooler tensors; never silently drop them.',
            'Require all395 original learned keys, shapes, dtypes and source storage identities. Strictly assign original checkpoint state using load_state_dict(assign=True, strict=True), then assert no meta learned parameters remain.',
            'Materialize only the two known nonpersistent embedding buffers on CPU using exact configured arange and zero token-type IDs. Do not call broad to_empty, float or device conversions that allocate/copy the assigned original parameter storage.',
            'Current source classifier consumes outputs[0], not pooler output. An explicit original-pooler compatibility adapter can retain all parameters, but exact numerical equivalence and real loading/runtime remain UNQUALIFIED until a separately frozen owned engineering check.',
            'Keep mapped file immutable and present until worker physical exit. No optimizer, parameter writes, training, calibration, temperature fit or inference is authorized by this plan.',
            'Before a future attempt, capture memory.current/max/events baselines and review inode/physical-page accounting. If scoped cleanup is proposed, freeze exact unneeded public source/cache paths and preserve hash-verified reconstructability; never delete private custody/forensics or unrelated assets. No cleanup was performed here.',
            'Actual mapped loading, all-state strict checks, outputs, resource reduction and full600s budget fit must be measured once in that future owned scope; format/source compatibility alone proves none of these.'
        ],
        'scientific_scope': {'model_quality_measured': False, 'accuracy': None, 'Brier': None, 'NLL': None,
            'NLI_latency': None, 'native_query_latency_scope': 'Component-only; Root may report actual captured native query timings separately.',
            'confirmation_used': [], 'Gold_reads_by_this_task': 0,
            'native104_preserved': True, 'official_SOTA_or_rank_claim': False,
            'model_not_rejected_on_quality': True},
        'actual_operations_in_this_static_task': {'model_initializations': 0, 'torch_imports': 0,
            'torch_load_or_unsafe_pickle_calls': 0, 'tensor_payload_values_decoded': 0,
            'native_BGE_tokenizer_calls': 0, 'feature_vault_or_confirmation_reads': 0,
            'Git_mutations': 0, 'cleanup_mutations': 0, 'paid_API_GPU_calls': 0}}
    rr = emit('STATIC_POSTMORTEM_REPORT.v1.json', report)
    files = [reference(p) for p in sorted(OWN.iterdir()) if p.is_file()]
    packet = {'schema_version': 1, 'epoch': 48, 'scope': 'Independent useful static advance after closed SIGKILL; no repeated scientific mutation',
              'files': files, 'report': rr, 'benchmark_or_model_execution_by_this_packet': False}
    pr = emit('READY.v1.json', packet)
    for p in OWN.iterdir():
        if p.is_file():
            f = os.open(p, os.O_RDONLY); os.fsync(f); os.close(f)
    d = os.open(OWN, os.O_RDONLY | os.O_DIRECTORY); os.fsync(d); os.close(d)
    print(json.dumps({'READY': pr, 'report': rr, 'framework_evidence': er, 'files': files}))


if __name__ == '__main__':
    main()
