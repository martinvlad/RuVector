"""Independent exact official tokenizer-JSON constructor; no neural framework."""
from __future__ import annotations
import importlib.metadata
import json
from pathlib import Path
import sys
from common import ROOT, PREFIX, MODEL, REVISION, demand, member, identity, digest

SOURCE_SHA = '7aa118770f066a74530d161c7d0b994d0629cc0ff3a0df213f184192773f960a'
ASSET_NAMES = ('tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json', 'added_tokens.json')
FORBIDDEN = ('torch', 'transformers', 'onnxruntime', 'sentencepiece')


def source_assets():
    lock = json.loads(member(PREFIX + 'legal-transfer/epoch22/model-assets.lock.json').read_text())
    demand(lock['repository'] == MODEL and lock['revision'] == REVISION, 'exact selected tokenizer model revision required')
    rows = lock['assets']; by_name = {r['remote_path']: r for r in rows}
    demand(len(rows) == len(by_name) == 9, 'exact nine original model assets required')
    files = {}; refs = []
    for name in ASSET_NAMES:
        row = by_name[name]; path = member(row['path']); actual = identity(path, row['path'])
        demand(actual == {k: row[k] for k in ('path', 'bytes', 'sha256')}, 'source tokenizer asset changed: ' + name)
        files[name] = path; refs.append(actual)
    demand(refs[0]['sha256'] == SOURCE_SHA, 'exact immutable original tokenizer JSON required')
    return files, refs


def validate_source(value):
    demand(value['model']['type'] == 'Unigram' and len(value['model']['vocab']) == 128000,
           'exact original Unigram source vocabulary required')
    demand(value['normalizer']['type'] == 'Sequence' and value['pre_tokenizer']['type'] == 'Sequence',
           'exact original normalization and pretokenizer pipeline required')
    demand(value['pre_tokenizer']['pretokenizers'] == [
        {'type': 'Metaspace', 'replacement': '▁', 'add_prefix_space': True}],
        'original pinned Metaspace policy changed')
    demand(value['decoder'] == {'type': 'Metaspace', 'replacement': '▁', 'add_prefix_space': True},
           'original pinned decoder policy changed')
    p = value['post_processor']
    demand(p['type'] == 'TemplateProcessing' and p['pair'] == [
        {'SpecialToken': {'id': '[CLS]', 'type_id': 0}},
        {'Sequence': {'id': 'A', 'type_id': 0}},
        {'SpecialToken': {'id': '[SEP]', 'type_id': 0}},
        {'Sequence': {'id': 'B', 'type_id': 1}},
        {'SpecialToken': {'id': '[SEP]', 'type_id': 1}}],
        'exact independent CLS/P/SEP/H/SEP segment template required')
    demand(p['special_tokens']['[CLS]']['ids'] == [1] and p['special_tokens']['[SEP]']['ids'] == [2],
           'original CLS and SEP identities changed')
    specials = {r['content']: r['id'] for r in value['added_tokens']}
    demand(specials == {'[PAD]': 0, '[CLS]': 1, '[SEP]': 2, '[UNK]': 3, '[MASK]': 128000},
           'exact five original special-token IDs required')
    demand(value['truncation'] == {'direction': 'Right', 'max_length': 512, 'strategy': 'LongestFirst', 'stride': 0}
           and value['padding'] is None, 'original source truncation/padding metadata changed')


def build_tokenizer():
    demand(not any(n in sys.modules for n in FORBIDDEN), 'independent tokenizer code must not import neural/framework conversion modules')
    demand(importlib.metadata.version('tokenizers') == '0.21.4', 'exact pinned tokenizers distribution required')
    files, refs = source_assets(); source = json.loads(files['tokenizer.json'].read_text()); validate_source(source)
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(files['tokenizer.json']))
    tokenizer.no_padding(); tokenizer.no_truncation()
    actual = tokenizer.to_str(); configured = json.loads(actual)
    demand(configured['padding'] is None and configured['truncation'] is None,
           'backend must explicitly disable both padding and truncation')
    demand(tokenizer.get_vocab_size(with_added_tokens=True) == 128001, 'effective source vocabulary changed')
    demand(not any(n in sys.modules for n in FORBIDDEN), 'unexpected framework or tokenizer conversion import')
    provenance = {'original_tokenizer_json_sha256': SOURCE_SHA,
                  'original_padding': source['padding'], 'original_truncation': source['truncation'],
                  'actual_padding': None, 'actual_truncation': None,
                  'configured_backend_sha256': digest(actual.encode()),
                  'configured_backend_bytes': len(actual.encode()),
                  'original_asset_bytes_modified': False,
                  'explicit_runtime_policy': 'Pinned tokenizers.Tokenizer.from_file(original JSON), no_padding(), no_truncation(); no manual schema edits or alternate constructor.',
                  'source_model': 'Unigram', 'source_vocab_entries': 128000,
                  'effective_vocab_with_added_tokens': 128001,
                  'source_asset_names': list(ASSET_NAMES)}
    return tokenizer, refs, provenance


def literal_feed(tokenizer, premise, hypothesis):
    p = tokenizer.encode(premise, add_special_tokens=False)
    h = tokenizer.encode(hypothesis, add_special_tokens=False)
    pair = tokenizer.encode(premise, hypothesis)
    ids = [1, *p.ids, 2, *h.ids, 2]
    types = [0] * (len(p.ids) + 2) + [1] * (len(h.ids) + 1)
    demand(pair.ids == ids and pair.type_ids == types and pair.attention_mask == [1] * len(ids),
           'actual tokenizer pair does not match literal independent source template')
    demand(3 <= len(ids) <= 512, 'complete untruncated pair exceeds frozen model capacity')
    return {'input_ids': [pair.ids], 'attention_mask': [pair.attention_mask],
            'token_type_ids': [pair.type_ids]}

