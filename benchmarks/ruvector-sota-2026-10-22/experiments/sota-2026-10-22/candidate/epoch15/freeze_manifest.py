"""Freeze exact public candidate15 source and role/asset identities, no inference."""
from pathlib import Path
import datetime
import hashlib
import json
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def item(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Only reviewed regular public files can be frozen')
    return {'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
            'sha256': sha(path)}


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    excluded = {'proposal-manifest.json', 'public-allowlist-v1.json'}
    sources = []
    for p in sorted(HERE.rglob('*')):
        rel = p.relative_to(HERE)
        if 'assets' in rel.parts or '__pycache__' in rel.parts or p.name in excluded:
            continue
        if p.is_file() and p.suffix in ('.py', '.json', '.md', '.txt'):
            sources.append(item(p))
    cfg = load(HERE / 'config.json')
    choice = load(HERE / 'model-choice.json')
    assert sha(HERE / 'config.json') in (HERE / 'runtime.py').read_text()
    assert sha(HERE / 'model-assets.lock.json') in (HERE / 'acquire_assets.py').read_text()
    assert sha(HERE / 'context.py') == cfg['definition_context_sha256']
    assert cfg['definition_priority']['token_cap'] == 160
    assert cfg['definition_priority']['claim_independent'] is True
    roles = [item(ROOT / cfg['data_contract_path'])]
    assert roles[0]['sha256'] == cfg['data_contract_sha256']
    static = load(HERE / 'onnx-static.json')
    assert static['external_initializers'] == [] and static['session_initialized'] is False
    assert {x['name'] for x in static['inputs']} == {'input_ids', 'attention_mask'}
    assert all(x['tensor_element_type'] == 7 for x in static['inputs'])
    assert static['outputs'][0]['name'] == 'logits' and static['outputs'][0]['dimensions'][-1] == {'value': 3}
    assert static['weight_sha256'] == choice['selected_asset_sha256']
    assets = load(HERE / 'assets.lock.json')
    assert len(assets['assets']) == 17
    acquisition = load(HERE / 'asset-acquisition.json')
    assert acquisition['status'] == 'SEVEN_EXACT_ASSETS_VERIFIED'
    assert acquisition['model_initializations'] == 0 and acquisition['model_calls'] == 0
    assert acquisition['native_calls'] == 0 and len(acquisition['files']) == 7
    old = load(HERE.parent / 'epoch13/proposal-manifest.json')
    deps = {x['path']: x for x in old['read_only_code_dependencies']}
    for name in ['runtime.py', 'context.py', 'config.json']:
        p = HERE.parent / 'epoch6' / name
        deps[str(p.relative_to(ROOT))] = item(p)
    for x in deps.values():
        assert item(ROOT / x['path']) == x
    manifest = {'schema_version': 1,
                'candidate_id': 'ruvector-native-official-deberta-definition-priority-threeway-epoch15',
                'status': 'SOURCE_FROZEN_PENDING_INDEPENDENT_FINAL_PLAN_ACCEPTANCE',
                'runtime_module': 'candidate.epoch15.runtime', 'runtime_class': 'CandidateEngine',
                'runtime_API': 'CandidateEngine(artifact_path=None); predict(state,questions); close(); execution_snapshot(); no TRAIN/fit/sanity API',
                'config': item(HERE / 'config.json'), 'sources': sources,
                'read_only_code_dependencies': [deps[k] for k in sorted(deps)],
                'assets_manifest': item(HERE / 'assets.lock.json'),
                'asset_acquisition_receipt': item(HERE / 'asset-acquisition.json'),
                'data_role_pins': roles,
                'role_freeze_scope': 'Prelabel contract binds document/query identity and role before any newDEV labels materialize; root final plan additionally binds exact materialized DEV bytes and receipt.',
                'model_identity': {'repo': choice['repo'], 'revision': choice['revision'],
                                   'onnx_sha256': choice['selected_asset_sha256'],
                                   'onnx_bytes': choice['selected_asset_bytes'],
                                   'remote_path': choice['selected_asset'],
                                   'precision': 'OFFICIAL_QUINT8_AVX2',
                                   'labels': {'0': 'contradiction', '1': 'entailment', '2': 'neutral'},
                                   'typed_order': ['Entailment', 'Contradiction', 'NotMentioned'],
                                   'mapping': 'Yes=P(E);No=P(C)+P(N);softmaxT1;exacthalfNo',
                                   'layers': 24, 'hidden_size': 1024},
                'hypothesis': choice['hypothesis'], 'configs_in_grid': 1,
                'training': [], 'calibration': [], 'training_or_calibration_fit': False,
                'training_labels_read_by_candidate': False,
                'source_frozen_before_fresh_DEV_labels': True,
                'definition_priority': cfg['definition_priority'],
                'definition_context_sha256': cfg['definition_context_sha256'],
                'exact_frozen_partition_base_sha256': cfg['frozen_context_algorithm_sha256'],
                'unchanged_epoch6_context_algorithm': False,
                'unchanged_epoch6_context_policy': False,
                'exact_epoch6_context_strings': False,
                'actual_model_tokenizer_sha256': cfg['active_context_and_model_tokenizer_sha256'],
                'ranking_anchor_cap_all_arms': 40,
                'joint_pair_token_cap': 512, 'priority_token_cap': 160,
                'final_global_source_order': True, 'literal_first_text_guaranteed': False,
                'batch_size': 1, 'temperature': 1, 'padding': False, 'truncation': False,
                'native_control': 'Native104 on exactly primary packed excerpt, not original full submitted champion',
                'same_model_retrieval_ablation': 'Native/lexical/positional, all3share exact priority IDs and actual model/tokenizer/decoder/packing. No-priority context trace is tokenization only, not a fourth inference/accuracy arm.',
                'confirmation_separation': cfg['confirmation_separation'],
                'design_revision': item(HERE / 'DESIGN_REVISION.json'),
                'engineering_failures_retained': item(HERE / 'ENGINEERING_FAILURES.json'),
                'tests': load(HERE / 'tests-result.json'),
                'static_model_check': item(HERE / 'onnx-static.json'),
                'runtime_feasibility': 'No unbudgeted session/probe/warmup; actual CPU2/600s admission inside native phase, conditionalCONF wholeprocess forecast. Higher capacity/source linkage is not proof of legal gain.',
                'new_model_forwards': 0, 'new_native_calls': 0,
                'new_evaluation_inputs_or_labels_read': 0, 'paid_calls': 0, 'GPU': 0,
                'source_frozen_at_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'execution_authority': 'Parent only after independent frozen plan acceptance, stable scopedOS/GitCAS locks; max2nonretryableCPU2/600s corpora including init/cleanup, paid/GPU0. DEV24 then conditional unchanged eligibleCONF48, no extra probes.'}
    save(HERE / 'proposal-manifest.json', manifest)
    save(HERE / 'public-allowlist-v1.json', {
        'schema_version': 1,
        'scope': 'Reviewed authored source/tests, official card/config/API metadata, static graph and actual verification receipts. Excludes all model/tokenizer/native binaries, assets/ directories and private raw payloads.',
        'files': sources + [item(HERE / 'proposal-manifest.json')]})
    print(json.dumps({'proposal_sha256': sha(HERE / 'proposal-manifest.json'),
                      'public_allowlist_sha256': sha(HERE / 'public-allowlist-v1.json'),
                      'source_files': len(sources), 'readonly_dependencies': len(deps),
                      'asset_pins': len(assets['assets']), 'model_native_calls': 0}))


if __name__ == '__main__':
    main()
