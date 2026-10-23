"""Independent original safetensors, trained-key, CPU-state and pair-feed checks."""
from common import *
import struct

WEIGHT_SHA = 'c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'
HEADER_SHA = '54177dcf30939971325ccfdda856523560a0457fa66e701d6206d27f96a7d9b4'
FLOAT_ELEMENTS = 435064835
POSITION_NAME = 'deberta.embeddings.position_ids'
STORAGE_TYPES = {'F16': 'torch.float16', 'I64': 'torch.int64'}


def source_header(protocol):
    rows = {r['remote_path']: r for r in protocol['model']['assets']}
    row = rows['model.safetensors']
    demand(row['bytes'] == 870182606 and row['sha256'] == WEIGHT_SHA, 'exact original FP16 safetensors source required')
    path = member(row['path'])
    demand(path.stat().st_size == row['bytes'], 'original safetensors size changed')
    with path.open('rb') as f:
        length = struct.unpack('<Q', f.read(8))[0]
        demand(0 < length < 1048576, 'bounded valid safetensors metadata length required')
        header_bytes = f.read(length); demand(digest(header_bytes) == HEADER_SHA, 'original complete header changed')
        value = json.loads(header_bytes)
        tensors = {k: v for k, v in value.items() if k != '__metadata__'}
        demand(POSITION_NAME in tensors, 'original nonlearned position buffer required')
        position = tensors[POSITION_NAME]
        demand(position['dtype'] == 'I64' and position['shape'] == [1, 512],
               'exact original integer position buffer required')
        a, b = position['data_offsets']
        demand(b - a == 4096 and 0 <= a < b <= path.stat().st_size - 8 - length,
               'exact original position-buffer byte extent required')
        f.seek(8 + length + a); data = f.read(b - a)
        demand(struct.unpack('<512q', data) == tuple(range(512)),
               'original integer position buffer must be literal arange512')
    dtype_elements = Counter(); normalized = {}
    for name, item in tensors.items():
        shape = item['shape']; demand(type(shape) is list and all(type(x) is int and x > 0 for x in shape), 'source tensor dimensions invalid')
        elements = math.prod(shape); dtype = item['dtype']
        demand(dtype in STORAGE_TYPES, 'unexpected original storage dtype')
        dtype_elements[STORAGE_TYPES[dtype]] += elements
        normalized[name] = {'dtype': dtype, 'shape': shape, 'elements': elements}
    demand(dict(dtype_elements) == {'torch.float16': FLOAT_ELEMENTS, 'torch.int64': 512},
           'exact original half-precision source and integer buffer inventory required')
    floats = {n: r for n, r in normalized.items() if r['dtype'] == 'F16'}
    demand(set(normalized) - set(floats) == {POSITION_NAME}, 'only original nonlearned position buffer may be integer')
    demand(len(normalized) == 395 and len(floats) == 394, 'exact original tensor cardinalities required')
    return normalized, floats, digest(header_bytes)


def parameter_loading_replay(proof, source_floats, expected_elements=FLOAT_ELEMENTS):
    demand(proof['source_float_key_set_equals_all_named_parameters'] is True
           and proof['all_source_to_FP32_values_equal'] is True,
           'every original learned parameter must be present and equal after explicit FP32 conversion')
    rows = proof['per_parameter']
    demand(type(rows) is list and [r['name'] for r in rows] == sorted(source_floats),
           'all original learned keys must be compared exactly once in sorted order')
    total = 0
    for row in rows:
        src = source_floats[row['name']]
        demand(row['source_dtype'] == src['dtype'] and row['source_shape'] == src['shape']
               and type(row['source_shape']) is list and all(type(x) is int for x in row['source_shape'])
               and integer(row['elements'], 1) == src['elements'],
               'original learned tensor source metadata changed')
        demand(row['loaded_dtype'] == 'torch.float32' and row['loaded_device'] == 'cpu'
               and row['equal_after_FP32_conversion'] is True,
               'trained parameter was reinitialized, omitted, altered or downcast')
        total += row['elements']
    demand(integer(proof['compared_tensor_count']) == len(source_floats)
           and integer(proof['compared_elements']) == expected_elements == total,
           'complete original-to-loaded parameter comparison counts required')
    return len(rows), total


def model_replay(raw, protocol):
    p, state, token = raw['model_provenance'], raw['fp32_state'], raw['tokenizer']
    demand(p['repo'] == MODEL and p['revision'] == REVISION, 'selected pretrained typed reader revision changed')
    demand(p['raw_id2label'] == {'0': 'Entailment', '1': 'NotMentioned', '2': 'Contradiction'}
           and p['canonical_order'] == list(M.ORDER) and p['canonical_permutation'] == [0, 2, 1],
           'source typed label mapping changed')
    for k, value in {'local_files_only': True, 'trust_remote_code': False, 'weights_only': True,
                     'use_safetensors': True, 'torch_dtype': 'torch.float32',
                     'output_loading_info': True, 'attn_implementation': 'eager'}.items():
        actual = p['load_flags'].get(k)
        demand((actual is value) if type(value) is bool else actual == value, 'fixed loader flag changed: ' + k)
    demand(p['actual_attention_implementation'] == 'eager', 'actual attention implementation changed')
    for k in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs'):
        demand(k in p['loading_info'] and p['loading_info'][k] == [], 'trained parameter load mismatch: ' + k)
    demand(p['precision'] == 'ORIGINAL_FP16_STORAGE_EXPLICIT_FP32_CPU_INFERENCE_NO_QUANTIZATION',
           'original FP16 storage and explicit FP32 computation must be distinguished')
    demand(integer(p['initialization_model_forwards']) == 0 and integer(p['quantization_initializations']) == 0,
           'unplanned model or precision probes')
    for k, value in protocol['model']['versions'].items():
        demand(p['versions'].get(k) == value, 'exact runtime version changed: ' + k)
    demand(integer(p['pair_token_cap']) == 512 and integer(p['batch_size']) == 1
           and M.real(p['temperature']) == 1, 'reader or feed budget changed')
    source, floats, header_sha = source_header(protocol)
    demand(p['source_checkpoint_raw_header_sha256'] == header_sha, 'actual original safetensors header identity differs')
    frozen_header = protocol['model']['source_header']
    demand(identity(member(frozen_header['path']), frozen_header['path']) == frozen_header
           and p['source_checkpoint_header_path'] == frozen_header['path']
           and p['source_checkpoint_header_sha256'] == frozen_header['sha256'],
           'frozen complete original source-header proof changed')
    demand(p['source_checkpoint_dtype_elements'] == {'torch.float16': FLOAT_ELEMENTS, 'torch.int64': 512}
           and integer(p['source_checkpoint_tensors']) == len(source)
           and integer(p['source_checkpoint_elements']) == FLOAT_ELEMENTS + 512,
           'actual original storage inventory mismatch')
    n, count = parameter_loading_replay(p['parameter_loading_verification'], floats)
    pos = p['position_buffer']
    demand(pos['name'] == POSITION_NAME and pos['source_dtype'] == 'I64'
           and pos['source_shape'] == [1, 512] and all(type(x) is int for x in pos['source_shape'])
           and pos['values_equal_arange512'] is True and pos['equals_actual_buffer'] is True
           and pos['actual_persistent'] is False
           and pos['source_bytes_sha256'] == '5738153ec97595b1c1e4dc027f7b7fb4534f19ed2ce9f9ee712e6d34a384cde7',
           'exact original and stock nonpersistent position-buffer equality required')
    state_sha = sha_value(state['state_sha256'])
    demand(state_sha == p['state_sha256'], 'actual loaded state identities differ')
    demand(state['devices'] == ['cpu'] and state['all_floating_parameters_buffers_FP32'] is True
           and state['eval'] is True and state['deterministic_algorithms'] is True,
           'FP32 CPU evaluation state required')
    demand(state['parameter_dtype_element_counts'] == {'torch.float32': FLOAT_ELEMENTS}
           and integer(state['parameter_count']) == count
           and integer(state['parameter_tensor_count']) == n, 'all original learned tensors must remain active FP32')
    buffers = state['buffer_dtype_element_counts']
    demand(type(buffers) is dict and all(type(k) is str and k in
           ('torch.float32', 'torch.int64', 'torch.int32', 'torch.int16', 'torch.int8', 'torch.uint8', 'torch.bool')
           and type(v) is int and v >= 0 for k, v in buffers.items()), 'invalid or downcast floating buffer dtype')
    for k, expected in [('pooler_dense_weight_shape', [1024, 1024]), ('pooler_dense_bias_shape', [1024]),
                        ('classifier_weight_shape', [3, 1024]), ('classifier_bias_shape', [3])]:
        demand(state[k] == expected and all(type(x) is int for x in state[k]), 'trained pooler/classifier shape mismatch')
    demand(integer(state['quantized_modules']) == 0 and integer(state['threads']) == 2
           and integer(state['interop_threads']) == 1, 'precision or thread count changed')
    demand(type(state['model_instance_token']) is str and state['model_instance_token'], 'actual singleton reader identity required')
    for field in ('source_config_architecture', 'architecture'):
        expected = protocol['model'][field]
        demand(p[field] == expected and all(type(p[field][k]) is type(v) for k,v in expected.items()),
               'source or actual stock classification architecture differs from frozen source: ' + field)
    demand(type(p['actual_model_config_declared_dtype']) is str and p['actual_model_config_declared_dtype'],
           'actual config dtype must be recorded separately from source storage and proven tensor computation')
    for k, expected in [('type', 'DebertaV2TokenizerFast'), ('backend_model', 'Unigram'),
                        ('pair_format', '[CLS]P[SEP]H[SEP]'), ('cls_id', 1), ('sep_id', 2), ('pad_id', 0)]:
        demand(token[k] == expected and (type(expected) is not int or type(token[k]) is int),
               'actual source tokenizer changed: ' + k)
    demand(token['padding'] is False and token['truncation'] is False
           and token['token_type_ids_fed'] is True and token == p['tokenizer'],
           'complete source tokenizer and actual three-tensor feed provenance required')
    demand(token['original_tokenizer_json_sha256'] == protocol['tokenizer']['original_tokenizer_json_sha256'],
           'original tokenizer source changed')
    demand(type(token['type_vocab_size']) is int and token['type_vocab_size'] == 0
           and token['learned_segment_embeddings'] is False
           and token['original_asset_bytes_unchanged'] is True
           and token['original_declared_padding'] is None
           and token['original_declared_truncation'] == {'direction':'Right','max_length':512,'strategy':'LongestFirst','stride':0},
           'original tokenizer configuration and type-vocabulary policy changed')
    sha_value(token['backend_sha256'])
    demand(token['backend_sha256'] == protocol['tokenizer']['operational_backend_sha256']
           and integer(token['actual_backend_json_bytes']) == protocol['tokenizer']['operational_backend_bytes'],
           'actual backend differs from the frozen one-time parser-qualified source policy')
    demand(token['actual_backend_json_sha256'] == token['backend_sha256'], 'actual operational backend hashes differ')
    backend_path = member(token['actual_backend_json_path'])
    demand(identity(backend_path, token['actual_backend_json_path']) ==
           {'path': token['actual_backend_json_path'], 'bytes': token['actual_backend_json_bytes'],
            'sha256': token['backend_sha256']}, 'saved actual operational tokenizer backend identity changed')
    demand(token['actual_backend_json_path'] == PREFIX + 'epoch22/runs/' + raw['phase'] + '/tokenizer-backend.json',
           'exact owned phase tokenizer-backend artifact required')
    backend = read(backend_path)
    demand(backend['model']['type'] == 'Unigram' and backend['padding'] is None and backend['truncation'] is None,
           'actual operational tokenizer silently clips, pads or substitutes a model')
    assets = {row['path']: row for row in raw['asset_identities']}
    demand(len(assets) == len(raw['asset_identities']), 'duplicate actual asset receipts')
    for row in protocol['model']['assets']:
        demand(assets.get(row['path']) == {k: row[k] for k in ('path', 'bytes', 'sha256')},
               'actual selected model asset mismatch')
    return state_sha, state['model_instance_token']


def assets_replay(raw, plan):
    model = read(member(plan['model_assets_lock_path']))['assets']
    bge = read(member(plan['bge_assets_lock_path'])); bge = bge['assets'] if 'assets' in bge else bge['files']
    native = read(member(plan['native_closure_path']))
    native = [r for package in native['packages'] for r in package['files']] if 'packages' in native else native['files']
    native = [r for r in native if r['path'].startswith('retrieval/node_modules/')]
    demand(len(model) == 9 and len(native) == 8, 'exact selected model and native closures required')
    expected = [{k: r[k] for k in ('path', 'bytes', 'sha256')} for r in model + bge + native]
    demand(raw['asset_identities'] == expected, 'actual full selected reader/BGE/native asset table differs from frozen locks')
    wheels = read(member(plan['wheel_lock_path']))['wheels']; demand(len(wheels) == 31, 'exact31-wheelCPU runtime required')
    versions = {r['filename'].split('-', 2)[0]: r['filename'].split('-', 2)[1] for r in wheels}
    demand(raw['versions'] == versions, 'actual31 installed runtime versions changed')
    return {'asset_records': len(expected), 'installed_distributions': 31}


def forward_replay(row, premise, hypothesis, state_sha, instance):
    demand(row['premise'] == premise and row['hypothesis'] == hypothesis, 'literal actual model pair changed')
    demand(row['input_text_sha256'] == digest(canonical([premise, hypothesis])), 'model input text hash mismatch')
    probabilities = M.replay_forward(row)
    raw = [probabilities['Entailment'], probabilities['NotMentioned'], probabilities['Contradiction']]
    demand(type(row['raw_probabilities']) is list and len(row['raw_probabilities']) == 3
           and all(abs(M.real(x) - y) <= 1e-10 for x, y in zip(row['raw_probabilities'], raw)),
           'raw E/N/C probability permutation mismatch')
    feed = row['feed']
    demand(type(feed) is dict and set(feed) == {'input_ids', 'attention_mask', 'token_type_ids'},
           'exact official three-tensor model feed required')
    for k in feed:
        demand(type(feed[k]) is list and len(feed[k]) == 1 and type(feed[k][0]) is list,
               'singleton literal model feed arrays required')
    ids, mask, types = (feed[k][0] for k in ('input_ids', 'attention_mask', 'token_type_ids'))
    demand(3 <= len(ids) <= 512 and len(mask) == len(types) == len(ids), 'complete untruncated pair capacity required')
    demand(all(type(x) is int and 0 <= x < 128100 for x in ids)
           and ids[0] == 1 and ids[-1] == 2, 'literal original vocabulary/CLS/SEP IDs required')
    demand(all(type(x) is int and x == 1 for x in mask), 'unmasked unpadded complete pair required')
    demand(all(type(x) is int and x in (0, 1) for x in types) and types[0] == 0 and types[-1] == 1
           and types == sorted(types), 'exact ordered official pair segment IDs required')
    demand(type(row['actual_tokens']) is int and row['actual_tokens'] == len(ids), 'actual pair length mismatch')
    demand(row['feed_sha256'] == digest(canonical(feed)), 'actual tensor feed hash mismatch')
    demand(row['padding'] is False and row['truncation'] is False
           and row['inference_mode'] is True and row['cpu_autocast'] is False,
           'inference or untruncated feed flags changed')
    demand(row['feed_dtype'] == 'torch.int64' and row['feed_device'] == 'cpu'
           and row['raw_logit_dtype'] == 'torch.float32' and row['original_high_level_feed_equal'] is True,
           'actual tensor/logit dtypes or whole official high-level pair-feed comparison changed')
    demand(row['model_state_sha256'] == state_sha and row['model_instance_token'] == instance,
           'matched reader identity changed')
    return duration(row['elapsed_seconds'])

