"""Stage reviewed UTF8 epoch23 Git payloads outside the project; no Git calls.

All historical source tuples and checkpoint rows are verified, not inferred
from counts. The inherited decoded RAW22 remains a checkpoint-only artifact,
with its already-published lossless archive/extractor/helper unchanged.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import copy
import json
from pathlib import Path
import re
from publication_common_v1 import (P, SCOPE, CONTROLS, check_final_manifest,
    check_history, check_ledger_history, check_transport, content, cp_rows,
    directory, encoded, final_ledger, gitsha, new_output, parse, public_text, ref, relative,
    require, sha, walk_current, write)

MAX_BLOB_JSON = 8 * 1024 * 1024 - 4096
MAX_TREE_JSON = 180000
LARGE_FILE_BYTES = 80000
TUPLE_KEYS = ('path', 'mode', 'type', 'sha', 'size')
MUTABLE_CONT = {'prior_published_base_commit', 'checkpoint_manifest_sha256',
    'active_run', 'benchmark_refresh', 'cumulative_budget_ledger',
    'execution_observed', 'epochs', 'next_research_priority', 'latest_learning',
    'rejection_ledger'}


def leaf(path, data):
    return {'path': path, 'mode': '100644', 'type': 'blob',
            'sha': gitsha(data), 'size': len(data)}


def tuple_row(row):
    require(isinstance(row, dict) and set(TUPLE_KEYS) <= set(row), 'Incomplete Git tuple')
    row = {key: row[key] for key in TUPLE_KEYS}
    path = row['path']
    require(isinstance(path, str), 'Git path must be text')
    if path.startswith(SCOPE):
        path = path[len(SCOPE):]
    row['path'] = relative(path)
    require(row['mode'] == '100644' and row['type'] == 'blob'
            and re.fullmatch('[0-9a-f]{40}', row['sha'] or '')
            and type(row['size']) is int and row['size'] >= 0,
            'Nonregular/invalid Git tuple')
    return row


def tuple_map(document):
    if isinstance(document, dict) and isinstance(document.get('files'), list):
        if 'scope' in document:
            require(document['scope'] == SCOPE, 'Expected-leaf scope differs')
        rows = document['files']
    elif isinstance(document, dict):
        rows = []
        for key, value in document.items():
            item = tuple_row(value)
            normalized = key[len(SCOPE):] if key.startswith(SCOPE) else key
            require(item['path'] == relative(normalized), 'Expected-map key/path differs')
            rows.append(item)
    else:
        raise ValueError('Expected-leaf document must contain files or a tuple map')
    answer = {}
    for item in rows:
        row = tuple_row(item)
        require(row['path'] not in answer, 'Duplicate expected Git leaf')
        answer[row['path']] = row
    require(CONTROLS <= set(answer), 'Three historical controls required')
    return answer


def verify_baseline(kit, index):
    require(isinstance(index, dict) and re.fullmatch('[0-9a-f]{40}',
            index.get('source_commit', '') or ''), 'Immutable source-filemap commit required')
    baseline = tuple_map({'files': index['files']})
    for path, row in baseline.items():
        require(leaf(path, content(kit / path)) == row, 'Historical Git bytes changed: ' + path)
    return baseline


def checked_review(document, current):
    rows = document['files'] if isinstance(document, dict) else document
    require(isinstance(rows, list), 'Reviewed exact file allowlist required')
    allowed = {}
    for row in rows:
        path = relative(row['path'])
        require(path not in allowed, 'Duplicate reviewed path')
        allowed[path] = row
    require(set(allowed) == set(current), 'Allowlist must cover all and only current epoch23 files')
    for path, data in current.items():
        row = allowed[path]
        require(type(row.get('bytes')) is int and row['bytes'] == len(data)
                and row.get('sha256') == sha(data), 'Reviewed bytes changed: ' + path)


def checked_controls(controls, kit, project, current):
    require({p.name for p in controls.iterdir()} == CONTROLS,
            'Controls directory must contain exactly three files')
    data = {name: content(controls / name) for name in sorted(CONTROLS)}
    for name, body in data.items():
        public_text(name, body)
    old_cp = parse(kit / 'CHECKPOINT_MANIFEST.json')
    old_cont = parse(kit / 'CONTINUATION.json')
    require(sha(content(kit / 'CHECKPOINT_MANIFEST.json')) == old_cont['checkpoint_manifest_sha256'],
            'Historical checkpoint hash differs from source continuation')
    before = check_history(project, old_cp)
    cp = json.loads(data['CHECKPOINT_MANIFEST.json'])
    after = cp_rows(cp)
    require(all(after.get(path) == row for path, row in before.items()),
            'Historical checkpoint identity changed')
    require(all(cp.get(key) == value for key, value in old_cp.items() if key != 'project_files'),
            'Historical checkpoint metadata changed')
    extra = {path: {'path': path, 'bytes': len(body), 'sha256': sha(body)}
             for path, body in current.items()}
    require(not set(before).intersection(extra)
            and set(after) == set(before) | set(extra)
            and all(after[path] == row for path, row in extra.items()),
            'New checkpoint must append exactly reviewed current identities')
    cont = json.loads(data['CONTINUATION.json']); active = json.loads(data['ACTIVE_RUN.json'])
    require(cont.get('checkpoint_manifest_sha256') == sha(data['CHECKPOINT_MANIFEST.json']),
            'New continuation checkpoint hash differs')
    require(all(cont.get(key) == value for key, value in old_cont.items()
                if key not in MUTABLE_CONT), 'Unrelated historical continuation field changed')
    for key in ('champion', 'goal_met', 'official_rank', 'used_confirmation_sets',
                'unused_confirmation_sets', 'exposed_development_sets'):
        require(cont.get(key) == old_cont[key], 'Historical champion/role/status changed: ' + key)
    require(cont.get('goal_met') is False and cont.get('active_run') == dict(active, path='ACTIVE_RUN.json')
            and active.get('native_allowed') == 0 and type(active.get('native_allowed')) is int
            and active.get('experiments_active') is False
            and active.get('conditional_confirmation_after_independent_DEV_runtime_gates') == 0,
            'Control ownership/admission/confirmation scope invalid')
    require(isinstance(active.get('run_id'), str) and active['run_id']
            and active.get('OS_lock_held') is True
            and re.fullmatch('[0-9a-f]{40}', active.get('checkpoint_parent', '') or '')
            and cont.get('prior_published_base_commit') == active['checkpoint_parent'],
            'Exact active owner and publication parent required')
    frozen = cont['epoch23_frozen_study']
    for key, path in [('plan', P + 'epoch23/plan.json'),
            ('source_freeze', P + 'epoch23/source-freeze.json'),
            ('specification', P + 'epoch23/PLAN_SPEC.json'),
            ('audit_protocol', P + 'audit/epoch23/protocol.json')]:
        require(frozen.get(key) == ref(project, path), 'Frozen source reference differs: ' + key)
    require(all(frozen.get(key) == [] for key in ('train', 'dev', 'calibration', 'confirmation'))
            and frozen.get('worker_attempt_cap') == 1
            and frozen.get('benchmark_promotion_or_submission_allowed') is False,
            'Frozen study must be one engineering attempt without benchmark roles')
    if active.get('state') == 'EPOCH23_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION':
        mode = 'source'
        require(active.get('work_active') is True
                and active.get('native_allowed_after_exact_remote_readback') == 1,
                'Source engineering allowance must be conditional only')
        require(P + 'epoch23/EPOCH_MANIFEST.json' not in current
                and P + 'epoch23/launch.json' not in current
                and not any(path.startswith(P + 'epoch23/runs/') for path in current),
                'Source stage contains scientific invocation/results')
    else:
        mode = 'final'
        require(active.get('state') == 'EPOCH23_CLOSED'
                and active.get('work_active') is False
                and active.get('native_allowed_after_exact_remote_readback') == 0
                and active.get('all_unspent_epoch23_slots_permanently_closed') is True,
                'Final engineering slots are not all closed')
        manifest = parse(project / (P + 'epoch23/EPOCH_MANIFEST.json'))
        check_final_manifest(manifest,
            parse(project / (P + 'epoch23/plan.json'))['expected_actual_native_queries'])
        require(cont['cumulative_budget_ledger'] == final_ledger(
            old_cont['cumulative_budget_ledger'], manifest, project),
            'Final current ledger is not the explicit fully closed ledger')
        require(manifest['published_frozen_source_commit'] == active['checkpoint_parent'],
                'Final parent is not measured frozen source')
        check_ledger_history(parse(project / old_cont['rejection_ledger']['path']),
                             parse(project / (P + 'epoch23/REJECTION_LEDGER.json')))
    transport = check_transport(project, old_cont, cont, after)
    return data, mode, old_cp, cp, cont, active, transport


def verify_prior(prior, baseline, expected):
    require(set(baseline) <= set(prior), 'Published prior dropped a historical Git leaf')
    for path, row in baseline.items():
        if path not in CONTROLS:
            require(prior[path] == row, 'Prior historical tuple differs: ' + path)
    for path, row in prior.items():
        if path not in CONTROLS:
            require(expected.get(path) == row, 'Published source changed/disappeared: ' + path)


def transport_groups(changed):
    entries, blobs, groups = [], [], []
    for path, body in sorted(changed.items()):
        text = public_text(path, body)
        entry = {'path': SCOPE + path, 'mode': '100644', 'type': 'blob'}
        if len(body) > LARGE_FILE_BYTES:
            payload = {'content': text, 'encoding': 'utf-8'}
            require(len(encoded(payload)) < MAX_BLOB_JSON,
                    'Blob JSON plus4096 reserve must be strictly below8MiB')
            blobs.append((path, body, payload)); entry['sha'] = gitsha(body)
        else:
            entry['content'] = text
        require(len(encoded({'tree_elements': [entry]})) < MAX_TREE_JSON,
                'One tree entry exceeds180000-byte request bound')
        entries.append(entry)
    batch = []
    for entry in entries:
        if len(encoded({'tree_elements': batch + [entry]})) >= MAX_TREE_JSON:
            require(batch, 'Empty group cannot accommodate one tree entry')
            groups.append(batch); batch = []
        batch.append(entry)
    if batch:
        groups.append(batch)
    return blobs, groups


def prepare(args):
    project, kit, controls = map(directory, (args.project, args.kit, args.controls_dir))
    out = new_output(args.out, (project, kit, controls))
    source_bytes = content(args.source_filemap); index = json.loads(source_bytes)
    baseline = verify_baseline(kit, index)
    current = walk_current(project)
    checked_review(parse(args.reviewed_files), current)
    derived, mode, old_cp, cp, cont, active, reconstruction = checked_controls(
        controls, kit, project, current)
    require(cont['epoch23_frozen_study']['source_checkpoint'] == index['source_commit']
            and parse(project / (P + 'epoch23/PLAN_SPEC.json'))['source_checkpoint']
                == index['source_commit'], 'Frozen study is not the actual baseline source commit')
    if args.mode is not None:
        require(args.mode == mode, 'CLI mode differs from derived controls')
    expected = copy.deepcopy(baseline)
    for path, body in {**current, **derived}.items():
        require(path not in baseline or path in CONTROLS, 'Historical Git overwrite: ' + path)
        expected[path] = leaf(path, body)
    prior_bytes = content(args.prior_expected)
    prior = tuple_map(json.loads(prior_bytes))
    verify_prior(prior, baseline, expected)
    check_transport(project, parse(kit / 'CONTINUATION.json'), cont,
                    cp_rows(cp), set(expected))
    changed = {path: body for path, body in {**current, **derived}.items()
               if prior.get(path) != expected[path]}
    require(changed, 'No branch changes; do not create duplicate publication')
    blobs, groups = transport_groups(changed)
    meta = {'schema_version': 1, 'stage': mode, 'scope': SCOPE,
        'source_checkpoint': index['source_commit'], 'publication_parent': active['checkpoint_parent'],
        'source_filemap_sha256': sha(source_bytes),
        'source_checkpoint_manifest_sha256': sha(content(kit / 'CHECKPOINT_MANIFEST.json')),
        'prior_expected_sha256': sha(prior_bytes), 'historical_leaf_count': len(baseline),
        'historical_unchanged_except_controls': len(baseline) - len(CONTROLS),
        'published_prior_leaves': len(prior), 'prior_noncontrol_tuples_preserved': True,
        'new_public23_leaves': len(current), 'old_CP_rows': len(cp_rows(old_cp)),
        'new_CP_rows': len(cp_rows(cp)), 'controls_replaced': sorted(CONTROLS),
        'old_Git_leaf_drops': 0, 'old_archived_raw_Git_payloads': 0,
        'reconstruction_refs_unchanged': reconstruction,
        'benchmark_roles': {key: [] for key in ('train', 'dev', 'calibration', 'confirmation')},
        'native_or_model_calls': 0, 'Git_mutations': 0, 'all_payloads_UTF8': True,
        'transport_limits': {'blob_JSON_bytes_exclusive': MAX_BLOB_JSON,
            'request_metadata_reserve_bytes': 4096, 'tree_JSON_bytes_exclusive': MAX_TREE_JSON},
        'new_and_control_files': [], 'large_blob_requests': [], 'create_tree_groups': []}
    out.mkdir(mode=0o700); (out / 'transport').mkdir(mode=0o700); (out / 'changed').mkdir(mode=0o700)
    for path, body in sorted(changed.items()):
        target = out / 'changed' / path; target.parent.mkdir(parents=True, exist_ok=True)
        write(target, body)
        meta['new_and_control_files'].append({'path': path, 'bytes': len(body),
            'sha256': sha(body), 'git_blob_sha1': gitsha(body)})
    for number, (path, body, payload) in enumerate(blobs):
        name = 'transport/blob-%03d.json' % number; data = encoded(payload)
        write(out / name, data)
        meta['large_blob_requests'].append({'path': path, 'file': name, 'bytes': len(data),
            'sha256': sha(data), 'expected_blob_sha1': gitsha(body),
            'must_create_and_verify_before_tree': True})
    for number, group in enumerate(groups):
        name = 'transport/tree-%03d.json' % number; data = encoded({'tree_elements': group})
        require(len(data) < MAX_TREE_JSON, 'Tree request byte cap exceeded')
        write(out / name, data)
        meta['create_tree_groups'].append({'file': name, 'bytes': len(data),
            'sha256': sha(data), 'entries': len(group)})
    document = {'schema_version': 1, 'scope': SCOPE, 'source_checkpoint': index['source_commit'],
                'files': [expected[path] for path in sorted(expected)]}
    for name, value in [('expected-leaves.json', document), ('expected-map.json', expected)]:
        data = encoded(value); write(out / name, data)
        meta[name.removesuffix('.json').replace('-', '_')] = {'file': name,
            'bytes': len(data), 'sha256': sha(data), 'count': len(expected)}
    write(out / 'manifest.json', encoded(meta))
    return {key: value for key, value in meta.items() if key not in
            ('new_and_control_files', 'large_blob_requests', 'create_tree_groups')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('project', 'kit', 'source-filemap', 'controls-dir', 'out',
                 'reviewed-files', 'prior-expected'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--mode', choices=['source', 'final'])
    print(json.dumps(prepare(parser.parse_args()), sort_keys=True))


if __name__ == '__main__':
    main()
