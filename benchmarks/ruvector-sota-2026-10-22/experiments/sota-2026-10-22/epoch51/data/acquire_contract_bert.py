"""Single-attempt pinned free asset acquisition; JSON/header inspection only."""
import argparse
import hashlib
import json
import math
import os
import signal
import ssl
import stat
import struct
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OWN = Path('/dev/shm/ruvector-e51-data')
ASSETS = OWN / 'assets' / 'contractnli-bert-nda-standard-ac92b6b512d7'
PLAN = OWN / 'MODEL_ACQUISITION_PLAN.v1.json'
OWNER = Path('/dev/shm/ruvector-sota-2026-10-22/epoch51-0e1f4181df1f/owner.json')
REV = 'ac92b6b512d7a4bad7abe356750c3b916fe18649'
PREFIX = 'https://huggingface.co/Agreemind/contractnli-bert-nda-standard/resolve/' + REV + '/'
WEIGHT_SHA = 'cd4f4391ab75c22e986ecea64831af47f6008a37ddce6a56a4cb5496e41ead07'
WEIGHT_BYTES = 437961724
MAX_SECONDS = 180

def require(v, code):
    if not v:
        raise ValueError(code)

def sha(b):
    return hashlib.sha256(b).hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

def unique(items):
    result = {}
    for k, v in items:
        require(k not in result, 'DUPLICATE_JSON_KEY')
        result[k] = v
    return result

def load_json_bytes(b):
    return json.loads(b, object_pairs_hook=unique,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))

def exact_ref(ref):
    p = Path(ref['path'])
    require(p.is_absolute() and p == p.resolve() and not any(x.is_symlink() for x in (p, *p.parents)), 'CANONICAL_REFERENCE')
    b = p.read_bytes()
    require(len(b) == ref['bytes'] and sha(b) == ref['sha256'], 'REFERENCE_IDENTITY')
    return b

def file_ref(p):
    b = p.read_bytes()
    return {'path': str(p), 'bytes': len(b), 'sha256': sha(b)}

def write_once(p, value):
    b = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(b)
        f.flush()
        os.fsync(f.fileno())

def owner_guard(plan):
    o = load_json_bytes(exact_ref(plan['owner_ref']))
    require(Path(plan['owner_ref']['path']) == OWNER and o['epoch'] == 51 and o['generation'] == 16
            and o['pid'] == 162664 and o['startticks'] == 39101510 and o['CPU_affinity'] == [0, 1]
            and time.time() < o['expires_unix'] and not (OWNER.parent / 'release.request').exists()
            and not (OWNER.parent / 'released.json').exists(), 'CURRENT_G16_OWNER')
    p = Path('/proc') / str(o['pid'])
    s = (p / 'stat').read_text().rsplit(')', 1)[1].split()
    require(s[0] not in ('Z', 'X') and int(s[19]) == o['startticks'], 'SAME_LIVE_GUARDIAN')
    require((p / 'ns/pid').readlink().as_posix() == o['PID_namespace']
            and Path('/proc/sys/kernel/random/boot_id').read_text().strip() == o['kernel_boot_id'], 'SAME_BOOT_NAMESPACE')
    a = os.stat(p / 'fd/3')
    b = os.stat(o['lock'])
    require((a.st_dev, a.st_ino) == (b.st_dev, b.st_ino) == (33, 13626), 'ORIGINAL_GLOBAL_LOCK')
    info = (p / 'fdinfo/3').read_text()
    require('FLOCK' in info and '162664' in info and ':13626' in info, 'GUARDIAN_ORIGINAL_FLOCK')
    require(set(os.sched_getaffinity(0)) <= {0, 1}, 'TWO_CORE_AFFINITY')

def expected_shapes():
    result = {
        'bert.embeddings.word_embeddings.weight': [30522, 768],
        'bert.embeddings.position_embeddings.weight': [512, 768],
        'bert.embeddings.token_type_embeddings.weight': [2, 768],
        'bert.embeddings.LayerNorm.weight': [768],
        'bert.embeddings.LayerNorm.bias': [768],
        'bert.pooler.dense.weight': [768, 768],
        'bert.pooler.dense.bias': [768],
        'classifier.weight': [3, 768], 'classifier.bias': [3],
    }
    for i in range(12):
        prefix = 'bert.encoder.layer.' + str(i) + '.'
        for term in ('query', 'key', 'value'):
            result[prefix + 'attention.self.' + term + '.weight'] = [768, 768]
            result[prefix + 'attention.self.' + term + '.bias'] = [768]
        for branch in ('attention.output', 'output'):
            result[prefix + branch + '.dense.weight'] = [768, 768 if branch == 'attention.output' else 3072]
            result[prefix + branch + '.dense.bias'] = [768]
            result[prefix + branch + '.LayerNorm.weight'] = [768]
            result[prefix + branch + '.LayerNorm.bias'] = [768]
        result[prefix + 'intermediate.dense.weight'] = [3072, 768]
        result[prefix + 'intermediate.dense.bias'] = [3072]
    require(len(result) == 201 and sum(math.prod(v) for v in result.values()) == 109484547, 'EXPECTED_BERT_ARCHITECTURE')
    return result

def validate_header(header, data_bytes):
    tensors = {k: v for k, v in header.items() if k != '__metadata__'}
    shapes = expected_shapes()
    require(set(tensors) == set(shapes), 'EXACT_201_TENSOR_KEYS')
    if '__metadata__' in header:
        require(type(header['__metadata__']) is dict and all(type(k) is str and type(v) is str
                for k, v in header['__metadata__'].items()), 'STRING_HEADER_METADATA')
    intervals = []
    for key, value in tensors.items():
        require(type(value) is dict and set(value) == {'dtype', 'shape', 'data_offsets'}
                and value['dtype'] == 'F32' and value['shape'] == shapes[key], 'EXACT_F32_TENSOR_SCHEMA_SHAPE')
        offsets = value['data_offsets']
        require(type(offsets) is list and len(offsets) == 2 and all(type(x) is int for x in offsets)
                and 0 <= offsets[0] <= offsets[1] <= data_bytes
                and offsets[1] - offsets[0] == 4 * math.prod(value['shape']), 'TENSOR_OFFSETS')
        intervals.append(tuple(offsets))
    intervals.sort()
    require(intervals[0][0] == 0 and intervals[-1][1] == data_bytes
            and all(a[1] == b[0] for a, b in zip(intervals, intervals[1:])), 'EXACT_CONTIGUOUS_DATA_REGION')
    return {'tensor_count': len(tensors), 'dtype': 'F32', 'elements': 109484547,
            'data_bytes': data_bytes, 'all_shapes_and_offsets_verified': True}

def inspect_header(path):
    with path.open('rb') as f:
        length_bytes = f.read(8)
        require(len(length_bytes) == 8, 'SAFETENSORS_PREFIX')
        length = struct.unpack('<Q', length_bytes)[0]
        require(2 <= length <= 2 * 1024 * 1024 and 8 + length < WEIGHT_BYTES, 'BOUNDED_HEADER_LENGTH')
        b = f.read(length)
        require(len(b) == length, 'COMPLETE_HEADER')
    return dict(validate_header(load_json_bytes(b), WEIGHT_BYTES - 8 - length),
                header_bytes=length, header_sha256=sha(b), tensor_payload_deserialized=False)

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        host = (parsed.hostname or '').lower()
        require(parsed.scheme == 'https' and (host == 'huggingface.co' or host.endswith('.huggingface.co')
                or host.endswith('.hf.co') or host.endswith('.xethub.hf.co')), 'ONLY_PUBLISHER_HTTPS_REDIRECTS')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def validate_small_assets():
    c = load_json_bytes((ASSETS / 'config.json').read_bytes())
    require(c['architectures'] == ['BertForSequenceClassification'] and c['model_type'] == 'bert'
            and c['hidden_size'] == 768 and c['intermediate_size'] == 3072 and c['num_hidden_layers'] == 12
            and c['num_attention_heads'] == 12 and c['vocab_size'] == 30522 and c['max_position_embeddings'] == 512
            and c['type_vocab_size'] == 2 and c['id2label'] == {'0': 'Entailment', '1': 'Contradiction', '2': 'NotMentioned'}
            and c['label2id'] == {'Entailment': 0, 'Contradiction': 1, 'NotMentioned': 2}
            and 'auto_map' not in c, 'EXACT_BERT_TYPED_CONFIG_NO_REMOTE_CODE')
    t = load_json_bytes((ASSETS / 'tokenizer.json').read_bytes())
    require(t['model']['type'] == 'WordPiece' and len(t['model']['vocab']) == 30522
            and t['model']['vocab']['[PAD]'] == 0 and t['model']['vocab']['[UNK]'] == 100
            and t['model']['vocab']['[CLS]'] == 101 and t['model']['vocab']['[SEP]'] == 102
            and t['model']['vocab']['[MASK]'] == 103, 'EXACT_BERT_WORDPIECE_SCHEMA')
    for name in ('tokenizer_config.json', 'special_tokens_map.json'):
        j = load_json_bytes((ASSETS / name).read_bytes())
        require(type(j) is dict and 'auto_map' not in j, 'TOKENIZER_JSON_NO_REMOTE_CODE')
    require(len((ASSETS / 'vocab.txt').read_bytes().splitlines()) == 30522, 'EXACT_BERT_VOCAB_COUNT')
    return {'config_typed_mapping_verified': True, 'wordpiece_vocabulary_verified': True,
            'tokenizer_instantiated': False, 'model_imports': 0}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit-approval', required=True)
    parser.add_argument('--audit-approval-sha256', required=True)
    parser.add_argument('--root-go', required=True)
    parser.add_argument('--root-go-sha256', required=True)
    args = parser.parse_args()
    plan_raw = PLAN.read_bytes()
    plan = load_json_bytes(plan_raw)
    script_sha = sha(Path(__file__).read_bytes())
    require(plan['source_helper']['sha256'] == script_sha and plan['model_revision'] == REV
            and plan['maximum_total_seconds'] == MAX_SECONDS and plan['maximum_GETs'] == 5, 'EXACT_ACQUISITION_PLAN')
    for path, digest, role in ((args.audit_approval, args.audit_approval_sha256, 'audit'),
                               (args.root_go, args.root_go_sha256, 'root')):
        b = Path(path).read_bytes()
        require(sha(b) == digest, 'EXACT_' + role.upper() + '_APPROVAL_REF')
        j = load_json_bytes(b)
        require(j['epoch'] == 51 and j['checks_passed'] is True and j['model_acquisition_allowed'] is True
                and j['plan_sha256'] == sha(plan_raw) and j['source_sha256'] == script_sha, 'EXACT_' + role.upper() + '_APPROVAL')
        if role == 'root':
            require(j['source_copy_storage_verified'] is True and j['storage_cleanup_verified'] is True, 'ROOT_STORAGE_GO')
    owner_guard(plan)
    require(not ASSETS.exists() and not ASSETS.is_symlink(), 'NEW_EXCLUSIVE_OWN_ASSET_DIRECTORY')
    require(os.statvfs(OWN).f_bavail * os.statvfs(OWN).f_frsize >= plan['minimum_free_storage_bytes'], 'OWN_STORAGE_HEADROOM')
    attempt = OWN / 'MODEL_ACQUISITION_ATTEMPT.v1.json'
    write_once(attempt, {'schema_version': 1, 'epoch': 51, 'started_at': now(), 'maximum_seconds': MAX_SECONDS,
                         'maximum_GETs': 5, 'plan_sha256': sha(plan_raw), 'retries': 0,
                         'model_imports_or_forwards_or_tokenizer_calls': 0})
    ASSETS.mkdir(parents=True, mode=0o700)
    created = []
    receipts = []
    started = time.monotonic()
    deadline = started + MAX_SECONDS
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('TOTAL_ACQUISITION_DEADLINE')))
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    result = {'schema_version': 1, 'epoch': 51, 'status': 'FAILED_CLOSED_NO_RETRY',
              'started_at': now(), 'plan_sha256': sha(plan_raw), 'source_sha256': script_sha,
              'model_imports_or_forwards_or_tokenizer_calls': 0, 'paid_GPU_API_calls': 0,
              'receipts': receipts, 'retries': 0, 'errors': []}
    try:
        ca = os.environ.get('SSL_CERT_FILE') or os.environ.get('REQUESTS_CA_BUNDLE')
        context = ssl.create_default_context(cafile=ca if ca else None)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(), urllib.request.HTTPSHandler(context=context), SafeRedirect())
        for item in plan['files']:
            owner_guard(plan)
            target = ASSETS / item['name']
            partial = ASSETS / (item['name'] + '.part')
            created.append(partial)
            h = hashlib.sha256()
            git_h = hashlib.sha1(b'blob ' + str(item['bytes']).encode() + b'\0')
            count = 0
            request_started = now()
            fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as f:
                if item['method'] == 'verified_local_copy':
                    b = exact_ref(item['donor_ref'])
                    f.write(b)
                    h.update(b)
                    git_h.update(b)
                    count = len(b)
                else:
                    require(item['method'] == 'HTTPS_GET' and len([r for r in receipts if r['method'] == 'HTTPS_GET']) < 5, 'ONLY_PLANNED_GETS')
                    request = urllib.request.Request(PREFIX + item['name'], headers={'User-Agent': 'RuVector-source-only-assets', 'Accept-Encoding': 'identity'})
                    with opener.open(request, timeout=max(1, min(30, deadline - time.monotonic()))) as response:
                        require(response.status == 200, 'HTTP200_REQUIRED')
                        declared = response.headers.get('Content-Length')
                        require(declared is None or int(declared) == item['bytes'], 'EXACT_DECLARED_BYTES')
                        while True:
                            require(time.monotonic() < deadline, 'TOTAL_ACQUISITION_DEADLINE')
                            chunk = response.read(min(1024 * 1024, item['bytes'] - count + 1))
                            if not chunk:
                                break
                            count += len(chunk)
                            require(count <= item['bytes'], 'HARD_BODY_BYTE_CAP')
                            f.write(chunk)
                            h.update(chunk)
                            git_h.update(chunk)
                f.flush()
                os.fsync(f.fileno())
            require(count == item['bytes'], 'COMPLETE_EXACT_BYTES')
            require(not item.get('sha256') or h.hexdigest() == item['sha256'], 'EXACT_PUBLISHER_SHA256')
            require(not item.get('git_blob_sha1') or git_h.hexdigest() == item['git_blob_sha1'], 'EXACT_PINNED_GIT_BLOB')
            os.rename(partial, target)
            created.append(target)
            os.chmod(target, 0o400)
            receipts.append({'name': item['name'], 'path': str(target), 'bytes': count, 'sha256': h.hexdigest(),
                             'method': item['method'], 'source_url': PREFIX + item['name'], 'TLS_verified': True,
                             'signed_redirect_urls_persisted': False, 'started_at': request_started, 'completed_at': now(),
                             'pinned_git_blob_verified': bool(item.get('git_blob_sha1')), 'model_deserialization': False})
        result['small_asset_checks'] = validate_small_assets()
        result['safetensors_header'] = inspect_header(ASSETS / 'model.safetensors')
        owner_guard(plan)
        result['status'] = 'ACQUIRED_HASH_AND_HEADER_VERIFIED_NO_MODEL_IMPORT_OR_MEASUREMENT'
        result['asset_directory'] = str(ASSETS)
    except Exception as error:
        result['errors'].append({'exception_type': type(error).__name__, 'message_sha256': sha(str(error).encode())})
        cleaned = []
        for path in reversed(created):
            require(path.parent == ASSETS, 'OWN_CLEANUP_ONLY')
            if path.exists() and not path.is_symlink():
                path.unlink()
                cleaned.append(path.name)
        if ASSETS.exists() and not any(ASSETS.iterdir()):
            ASSETS.rmdir()
        result['failure_cleanup_owned_new_files'] = cleaned
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    result['completed_at'] = now()
    result['elapsed_seconds'] = time.monotonic() - started
    write_once(OWN / 'MODEL_ACQUISITION_RESULT.v1.json', result)
    print(json.dumps({'status': result['status'], 'files_completed': len(receipts),
                      'GETs_completed': len([r for r in receipts if r['method'] == 'HTTPS_GET']),
                      'elapsed_seconds': result['elapsed_seconds'], 'errors': result['errors']}))
    return 0 if not result['errors'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
