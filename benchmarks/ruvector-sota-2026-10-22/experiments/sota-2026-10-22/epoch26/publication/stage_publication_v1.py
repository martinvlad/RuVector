"""Stage reviewed epoch26 public source or honest closed DEV evidence, locally.

No Git, network, mail, inference, or control-building actions are performed.
The caller supplies exact controls and an exhaustive public file review.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import copy
import math
from pathlib import Path
import re
from publication_common_v1 import (P, SCOPE, ROOTS, CONTROLS, BASE_COMMIT,
    OWNER_PIN, OWNER_RUN_ID, OWNER_EXPIRES_UNIX, check_inherited_checkpoint,
    check_history, check_transport, content, cp_rows, directory, encoded, gitsha,
    live_owner, loads, new_output, parse, public_text, ref, relative, require,
    sha, walk_current, write)

MAX_BLOB_JSON = 8384512
MAX_TREE_JSON = 175904
LARGE_FILE_BYTES = 80000
BASE_GIT_LEAVES = 3617
LEASE_COMMIT = 'b7f8285206189ba1ee0de95057957585ac097874'
MAIN_COMMIT = '46d816ddc4c2a8a06cd3613534a79b1d557d858b'
LEASE_TREES = ('c876728f53e5860cdbae31822558c3fc126e7e17',
    '7cce374cc3996a27c3c58b657ab69049c253c5ad',
    '2b1c607dc100364a39543ae23ec31eef49b36a82')
KIND = 'REAL_DEV_ONLY_TYPED_NLI_DIAGNOSTIC'
E = P + 'epoch26/'
FROZEN_REFS = {'plan': E+'plan.json', 'source_freeze': E+'source-freeze.json',
               'PLAN_SPEC': E+'PLAN_SPEC.json'}
ORACLE_REFS = {'independent_protocol': P+'audit/epoch26/protocol.json',
    'independent_scorer': P+'audit/epoch26/score_dev.py',
    'network_policy': P+'audit/epoch26/network-policy-amendment-v2.json'}
TUPLE_KEYS = ('path', 'mode', 'type', 'sha', 'size')
MUTABLE_FINAL = {'active_run', 'checkpoint_manifest_sha256',
    'prior_published_base_commit', 'benchmark_refresh', 'execution_observed',
    'cumulative_budget_ledger', 'epochs', 'latest_learning', 'rejection_ledger',
    'next_research_priority', 'exposed_development_sets'}


def leaf(path, body):
    return {'path': path, 'mode': '100644', 'type': 'blob',
            'sha': gitsha(body), 'size': len(body)}


def tuple_map(document):
    require(isinstance(document, dict), 'Expected tuple document required')
    if 'files' in document:
        require(document.get('scope', SCOPE) == SCOPE
                and isinstance(document['files'], list), 'Wrong expected tuple scope')
        values = document['files']
    else:
        values = []
        for key, value in document.items():
            require(isinstance(value, dict), 'Tuple map value required')
            normalized = key[len(SCOPE):] if key.startswith(SCOPE) else key
            path = value.get('path', '')
            path = path[len(SCOPE):] if path.startswith(SCOPE) else path
            require(path == normalized, 'Tuple map key/path mismatch')
            values.append(value)
    answer = {}
    for value in values:
        require(isinstance(value, dict) and set(TUPLE_KEYS) <= set(value), 'Incomplete Git tuple')
        row = {k: value[k] for k in TUPLE_KEYS}
        path = row['path']
        require(isinstance(path, str), 'Git tuple path must be text')
        path = path[len(SCOPE):] if path.startswith(SCOPE) else path
        row['path'] = relative(path)
        require(row['mode'] == '100644' and row['type'] == 'blob'
                and re.fullmatch('[0-9a-f]{40}', row['sha'] or '')
                and type(row['size']) is int and row['size'] >= 0
                and path not in answer, 'Invalid or duplicate Git tuple')
        answer[path] = row
    require(CONTROLS <= set(answer), 'Three original control tuples required')
    return answer


def verify_baseline(kit, index):
    require(isinstance(index, dict) and set(index) <= {'scope', 'files', 'source_commit'},
            'Canonical source-filemap structure required')
    require(index.get('source_commit', BASE_COMMIT) == BASE_COMMIT,
            'Wrong original source commit')
    baseline = tuple_map(index)
    require(len(baseline) == BASE_GIT_LEAVES, 'Original3617 Git tuples required')
    for path, row in baseline.items():
        require(leaf(path, content(kit/path)) == row, 'Original Git bytes changed: '+path)
    return baseline


def checked_review(document, current):
    require(isinstance(document, dict) and isinstance(document.get('files'), list),
            'Explicit exhaustive files review required')
    allowed = {}
    for row in document['files']:
        require(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'},
                'Review must use canonical three-key references')
        path = relative(row['path'])
        require(path not in allowed, 'Duplicate reviewed path')
        allowed[path] = row
    require(set(allowed) == set(current), 'Review must cover all and only four-root current files')
    for path, body in current.items():
        require(allowed[path] == {'path': path, 'bytes': len(body), 'sha256': sha(body)},
                'Reviewed file bytes changed: '+path)


def checked_ref(project, row, checkpoint, expected_path=None):
    require(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'},
            'Canonical three-key source reference required')
    path = relative(row['path'])
    require(expected_path is None or path == expected_path, 'Unexpected source reference')
    require(checkpoint.get(path) == row and ref(project, path) == row,
            'Actual/checkpoint source reference differs: '+path)
    return path


def exact_alias(mapping, names, wanted, label):
    present = [mapping[name] for name in names if name in mapping]
    require(present and all(type(v) is type(wanted) and v == wanted for v in present),
            'Missing/conflicting exact '+label)


def checked_plan(project, cont, checkpoint, current, phase):
    frozen = cont.get('epoch26_frozen_study')
    require(isinstance(frozen, dict) and set(frozen) == set(FROZEN_REFS),
            'Exact frozen plan/source-freeze/PLAN_SPEC refs required')
    for key, path in FROZEN_REFS.items(): checked_ref(project, frozen[key], checkpoint, path)
    plan, spec, freeze = (parse(project/FROZEN_REFS[k]) for k in ('plan', 'PLAN_SPEC', 'source_freeze'))
    require(plan.get('epoch') == spec.get('epoch') == freeze.get('epoch') == 26
            and plan.get('kind') == KIND
            and plan.get('source_checkpoint') == BASE_COMMIT,
            'Wrong frozen diagnostic epoch/kind/checkpoint')
    if 'source_checkpoint' in spec: require(spec['source_checkpoint'] == BASE_COMMIT, 'Wrong spec checkpoint')
    if 'source_checkpoint' in freeze: require(freeze['source_checkpoint'] == BASE_COMMIT, 'Wrong freeze checkpoint')
    roles = plan.get('data_roles', plan.get('benchmark_roles'))
    require(isinstance(roles, dict) and set(roles) == {'train', 'dev', 'calibration', 'confirmation'}
            and roles['train'] == roles['calibration'] == roles['confirmation'] == []
            and isinstance(roles['dev'], list) and len(roles['dev']) in (8, 24),
            'Only fixed real DEV identities may be populated')
    require(len({encoded(v) for v in roles['dev']}) == len(roles['dev']), 'Duplicate DEV identity')
    if 'data_roles' in spec: require(spec['data_roles'] == roles, 'Spec roles differ')
    limits = plan.get('limits', {})
    exact_alias(limits, ('owned_workers', 'worker_attempts'), 1, 'one worker')
    exact_alias(limits, ('CPU_threads', 'cpu_threads'), 2, 'CPU threads')
    require(limits.get('CPU_affinity') == [0, 1], 'Explicit frozen CPU affinity required')
    exact_alias(limits, ('seconds_per_batch',), 600, 'whole-worker seconds')
    exact_alias(limits, ('NLI_forward_pairs',), 72, 'NLI pair cap')
    exact_alias(limits, ('native_queries', 'native_searches'), 24, 'native query cap')
    for key in ('paid_calls', 'GPU_calls'):
        require(type(limits.get(key)) is int and limits[key] == 0, 'Frozen zero spend required: '+key)
    for key in ('training_steps', 'optimizer_steps', 'calibration_calls', 'generation_calls', 'CONF_worker_attempts'):
        if key in limits: require(type(limits[key]) is int and limits[key] == 0, 'Nonzero forbidden plan allowance')
    for key in ('benchmark_accepted', 'champion_promotion_allowed', 'confirmation_execution_allowed', 'publisher_submission_allowed'):
        if key in plan: require(plan[key] is False, 'Diagnostic plan grants promotion/CONF/submission')
    pins = plan.get('pins'); entries = freeze.get('source_entries', freeze.get('entries'))
    require(isinstance(pins, list) and pins and isinstance(entries, list) and entries,
            'Nonempty frozen pins and source entries required')
    maps = []
    for name, rows in [('pins', pins), ('entries', entries)]:
        paths = {}
        for row in rows:
            path = checked_ref(project, row, checkpoint)
            require(path not in paths, 'Duplicate frozen '+name+' identity')
            paths[path] = row
        maps.append(paths)
    pinmap, entrymap = maps
    require(FROZEN_REFS['plan'] not in entrymap and FROZEN_REFS['source_freeze'] not in entrymap,
            'Recursive plan/freeze entry refused')
    require(frozen['source_freeze'] in pins and set(entrymap) <= set(pinmap),
            'Plan must pin exact source-freeze and every frozen source entry')
    if phase == 'source':
        require(set(entrymap) == set(current) - {FROZEN_REFS['plan'], FROZEN_REFS['source_freeze']},
                'Source freeze must cover every reviewed source file')
    for key, path in ORACLE_REFS.items():
        checked_ref(project, plan.get(key), checkpoint, path)
        require(path in pinmap and path in entrymap, 'Independent oracle/policy was not frozen')
    require(plan.get('source_freeze_path', FROZEN_REFS['source_freeze']) == FROZEN_REFS['source_freeze']
            and plan.get('source_freeze_sha256', frozen['source_freeze']['sha256']) == frozen['source_freeze']['sha256'],
            'Plan/freeze SHA binding differs')
    external = freeze.get('external_runtime_assets')
    require(isinstance(external, (list, dict)) and external, 'External runtime asset pins required')
    if 'external_runtime_assets' in plan: require(plan['external_runtime_assets'] == external, 'Plan runtime pins differ')
    require(not any(path in current for path in checkpoint if '/models/' in path or '/.venv/' in path),
            'Model/runtime binaries cannot be checkpoint additions')
    return plan, frozen


def checkpoint_extension(old, new, current):
    before, after = cp_rows(old), cp_rows(new)
    require(set(old) <= set(new)
            and all(k.startswith('epoch26_') for k in set(new)-set(old))
            and all(new[k] == v for k, v in old.items() if k != 'project_files'),
            'Historical checkpoint metadata changed or dropped')
    additions = {p: {'path': p, 'bytes': len(b), 'sha256': sha(b)} for p, b in current.items()}
    require(not set(before).intersection(additions)
            and after == {**before, **additions},
            'Checkpoint must preserve old rows and append exactly reviewed current files')
    return before, after


def control_bodies(path):
    directory(path)
    require({p.name for p in path.iterdir()} in (CONTROLS, CONTROLS | {'hashes.json'}),
            'Controls must be exactly three files plus optional unpublished hash sidecar')
    bodies = {name: content(path/name) for name in sorted(CONTROLS)}
    for name, body in bodies.items(): public_text(name, body)
    return bodies


def check_readback(readback, phase, parent, guards):
    require(readback.get('commit') == parent
            and (readback.get('verified') is True or readback.get('verified_actual_full_tree') is True),
            'Parent must be an actual verified publication readback')
    for field, expected in zip(('root', 'bench', 'scope'), guards):
        require(readback.get(field) == expected, 'Parent readback/tree guard differs: '+field)
    if phase == 'source':
        require(parent == LEASE_COMMIT and tuple(guards) == LEASE_TREES
                and readback.get('parent') == BASE_COMMIT,
                'Source must extend exact epoch26 planning lease')
    else:
        require(parent not in (BASE_COMMIT, LEASE_COMMIT), 'Final must extend actual source commit')


def checked_controls(controls, priorcontrols, kit, project, current, phase, parent):
    bodies, prior_bodies = control_bodies(controls), control_bodies(priorcontrols)
    old_cp, old_cont = parse(kit/'CHECKPOINT_MANIFEST.json'), parse(kit/'CONTINUATION.json')
    check_inherited_checkpoint(old_cp); check_history(project, old_cp)
    require(sha(content(kit/'CHECKPOINT_MANIFEST.json')) == old_cont['checkpoint_manifest_sha256'],
            'Original checkpoint hash binding differs')
    cp, cont, active = (loads(bodies[n]) for n in ('CHECKPOINT_MANIFEST.json', 'CONTINUATION.json', 'ACTIVE_RUN.json'))
    _, after = checkpoint_extension(old_cp, cp, current)
    prior_cp, prior_cont, prior_active = (loads(prior_bodies[n]) for n in ('CHECKPOINT_MANIFEST.json', 'CONTINUATION.json', 'ACTIVE_RUN.json'))
    require(prior_cont.get('checkpoint_manifest_sha256') == sha(prior_bodies['CHECKPOINT_MANIFEST.json']),
            'Prior actual control checkpoint binding differs')
    mutable = MUTABLE_FINAL if phase == 'final' else {'active_run', 'checkpoint_manifest_sha256', 'prior_published_base_commit', 'benchmark_refresh', 'exposed_development_sets'}
    require(set(old_cont) <= set(cont) and all(k in old_cont or k.startswith('epoch26_') for k in cont),
            'Continuation dropped old metadata or added outside epoch26 namespace')
    require(all(cont[k] == v for k, v in old_cont.items() if k not in mutable),
            'Historical continuation field changed')
    before_exposure, after_exposure = old_cont.get('exposed_development_sets'), cont.get('exposed_development_sets')
    if isinstance(before_exposure, list):
        require(isinstance(after_exposure, list) and after_exposure[:len(before_exposure)] == before_exposure,
                'Historical DEV exposure records changed')
    elif isinstance(before_exposure, dict):
        require(isinstance(after_exposure, dict) and all(after_exposure.get(k) == v for k, v in before_exposure.items()),
                'Historical DEV exposure records changed')
    require(cont.get('checkpoint_manifest_sha256') == sha(bodies['CHECKPOINT_MANIFEST.json'])
            and cont.get('active_run') == dict(active, path='ACTIVE_RUN.json')
            and cont.get('goal_met') is False and cont.get('official_rank') is None
            and cont.get('prior_published_base_commit') == parent,
            'Current control/hash/status/parent binding differs')
    physical = active.get('physical_owner', active)
    identity = (physical.get('pid', physical.get('owner_pid')), physical.get('startticks', physical.get('owner_startticks')), physical.get('lock_inode'))
    require(active.get('run_id') == OWNER_RUN_ID and identity == OWNER_PIN
            and active.get('checkpoint_parent') == parent and active.get('OS_lock_held') is True
            and type(active.get('native_allowed')) is int and active['native_allowed'] == 0
            and active.get('experiments_active') is False,
            'Current controls differ from pinned owner/parent/immediate zero allowance')
    if 'expires_unix' in physical: require(physical['expires_unix'] == OWNER_EXPIRES_UNIX, 'Owner expiry changed')
    for key, value in active.items():
        if 'confirmation' in key.lower() or 'CONF' in key:
            require(type(value) is int and value == 0, 'Confirmation allowance must remain zero')
    state = active.get('state', '')
    if phase == 'source':
        require(prior_cp == old_cp and prior_active.get('state') == 'EPOCH26_EXCLUSIVE_PLANNING'
                and active.get('work_active') is True
                and state == 'EPOCH26_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION',
                'Source must extend untouched planning checkpoint into pending admission')
        require(not any(p.startswith(E+'runs/') or p in {E+'EPOCH_MANIFEST.json', E+'RESULTS.json', E+'execution.json', E+'NATIVE_ADMISSION.json'} for p in current),
                'Source publication contains execution or result evidence')
    else:
        require(prior_active.get('state') == 'EPOCH26_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION'
                and active.get('work_active') is False and state == 'EPOCH26_CLOSED',
                'Final must close the actually published source stage')
        require(set(cp) == set(prior_cp)
                and all(cp[k] == v for k, v in prior_cp.items() if k != 'project_files')
                and all(after.get(p) == r for p, r in cp_rows(prior_cp).items()),
                'Final changed source checkpoint metadata or frozen rows')
        for key, value in active.items():
            if any(part in key.lower() for part in ('allowed', 'allowance', 'remaining')) and type(value) is int:
                require(value == 0, 'Final allowance is not closed')
    require(cont.get('epoch26_planning') == prior_cont.get('epoch26_planning')
            and isinstance(cont.get('epoch26_planning'), dict), 'Planning lease record changed')
    if phase == 'final':
        for k in ('epoch26_frozen_study', 'epoch26_official_refresh'):
            require(cont.get(k) == prior_cont.get(k), 'Published frozen continuation record changed: '+k)
    plan, frozen = checked_plan(project, cont, after, current, phase)
    refresh = cont.get('epoch26_official_refresh')
    checked_ref(project, refresh, after, P+'legal-transfer/epoch26/benchmark-refresh.json')
    require(cont.get('benchmark_refresh') == refresh, 'Official refresh references differ')
    transport = check_transport(project, old_cont, cont, after)
    return bodies, prior_bodies, old_cp, cp, cont, active, plan, frozen, transport


ZERO_COUNTERS = ('Python_network_operations_attempted', 'Node_network_operations_attempted',
    'benchmark_HTTP_requests', 'benchmark_label_reads', 'TRAIN_calibration_fits',
    'CONF_worker_attempts', 'CONF_annotation_choices', 'CONF_NLI_pairs',
    'paid_API_calls', 'GPU_calls', 'fits', 'paid_calls', 'confirmation_calls',
    'generation_calls', 'generated_tokens', 'training_steps', 'optimizer_steps',
    'external_API_calls', 'train_calls', 'calibration_calls')
COUNT_COUNTERS = ('Python_literal_loopback_binds_allowed', 'BGE_initializations_attempted',
    'BGE_initializations_completed', 'ORT_sessions_attempted', 'ORT_sessions_completed',
    'BGE_forwards_attempted', 'BGE_forwards_completed', 'BGE_texts_attempted',
    'BGE_texts_completed', 'native_helper_starts', 'native_index_initializations_attempted',
    'native_index_initializations_completed', 'native_queries_attempted', 'native_queries_completed',
    'NLI_model_initializations', 'NLI_model_initializations_completed',
    'NLI_forward_pairs_attempted', 'NLI_forward_pairs_completed', 'NLI_forwards',
    'NLI_forward_calls_attempted', 'NLI_forward_calls_completed',
    'DEV_input_bank_reads', 'DEV_corpora', 'DEV_questions', 'DEV_pairs_completed',
    'DEV_cases_completed', 'automatically_extracted_units')
ALIASES = {'BGE_initializations': 'BGE_initializations_completed',
    'BGE_forwards': 'BGE_forwards_completed', 'BGE_texts': 'BGE_texts_completed',
    'native_index_initializations': 'native_index_initializations_completed',
    'native_searches_completed': 'native_queries_completed'}


def final_refs(project, manifest, checkpoint):
    refs = {}
    aliases = {'results': ('results',), 'execution': ('execution',), 'raw': ('raw',),
        'independent_report': ('independent_report', 'acceptance_report', 'independent_acceptance_report')}
    for key, names in aliases.items():
        found = [manifest[n] for n in names if n in manifest]
        require(found and all(v == found[0] for v in found), 'Missing/conflicting final '+key+' ref')
        refs[key] = found[0]
        if key == 'raw' and found[0] is None:
            continue
        checked_ref(project, found[0], checkpoint)
        path = found[0]['path']
        require(any(path.startswith(root+'/') for root in ROOTS), 'Final evidence outside epoch26 roots')
    require(refs['results']['path'] == E+'RESULTS.json'
            and refs['execution']['path'] == E+'execution.json', 'Unexpected final result/execution path')
    return refs


def check_actual(actual, raw, execution, qualified):
    require(isinstance(actual, dict) and isinstance(execution, dict), 'Explicit actual and outer execution required')
    exact_alias(actual, ('worker_attempts',), 1, 'reserved actual worker')
    require(execution.get('worker_attempts_reserved') == actual['worker_attempts']
            and type(actual.get('verified_worker_starts')) is int
            and actual['verified_worker_starts'] == execution.get('verified_worker_starts')
            and 0 <= actual['verified_worker_starts'] <= 1,
            'Actual worker reservation/start differs from outer execution')
    for key in ('owned_live_processes_closed', 'CPU_affinity', 'wall_seconds_including_init_cleanup'):
        require(actual.get(key) == execution.get(key), 'Outer actual resource/closure differs: '+key)
    require(type(actual.get('owned_live_processes_closed')) is bool
            and actual.get('CPU_affinity') == [0, 1]
            and all(type(x) is int for x in actual['CPU_affinity']), 'Actual CPU2/closure types invalid')
    wall = actual.get('wall_seconds_including_init_cleanup')
    require(type(wall) in (int, float) and math.isfinite(wall) and wall >= 0,
            'Actual wall time must be explicit, finite and nonnegative')
    require(type(actual.get('errors')) is int and actual['errors'] >= 0, 'Explicit actual error count required')
    if raw is None:
        require(not qualified and execution.get('raw_bytes') is None and execution.get('raw_sha256') is None
                and actual.get('counter_observation_scope') == 'NO_RAW_COUNTER_RECEIPT',
                'Missing raw cannot establish counters or qualification')
        require(not any(k in actual for k in COUNT_COUNTERS+ZERO_COUNTERS+tuple(ALIASES)),
                'Missing raw counters must remain unknown rather than invented')
        return False
    require(raw.get('epoch') == 26 and raw.get('phase') == 'dev', 'Wrong raw diagnostic epoch/phase')
    counters = raw.get('counters')
    require(isinstance(counters, dict), 'Raw counters required')
    for key in COUNT_COUNTERS+ZERO_COUNTERS:
        require(type(counters.get(key)) is int and counters[key] >= 0,
                'Missing/noninteger raw counter: '+key)
    require(all(key in actual and type(actual[key]) is type(value) and actual[key] == value
                for key, value in counters.items()), 'Actual execution rewrote or dropped raw counters')
    for alias, key in ALIASES.items():
        require(type(actual.get(alias)) is int and actual[alias] == counters[key], 'Actual counter alias differs: '+alias)
    require(isinstance(raw.get('errors'), list) and actual['errors'] == len(raw['errors']),
            'Raw error list and actual error count differ')
    for completed, attempted in (
        ('BGE_initializations_completed', 'BGE_initializations_attempted'),
        ('BGE_forwards_completed', 'BGE_forwards_attempted'),
        ('BGE_texts_completed', 'BGE_texts_attempted'),
        ('native_index_initializations_completed', 'native_index_initializations_attempted'),
        ('native_queries_completed', 'native_queries_attempted'),
        ('NLI_model_initializations_completed', 'NLI_model_initializations'),
        ('NLI_forward_pairs_completed', 'NLI_forward_pairs_attempted')):
        require(counters[completed] <= counters[attempted], 'Completed count exceeds attempted count')
    within_caps = (counters['NLI_model_initializations'] <= 1
        and counters['NLI_forward_pairs_attempted'] <= 72
        and counters['native_index_initializations_attempted'] <= 8
        and counters['native_queries_attempted'] <= 24
        and counters['DEV_cases_completed'] <= 24 and counters['DEV_pairs_completed'] <= 72)
    successful = (execution.get('status') == 'WORKER_COMPLETED' and execution.get('exit_code') == 0
        and execution.get('owned_live_processes_closed') is True
        and execution.get('owned_live_group_members') == []
        and execution.get('cleanup_errors', []) == [] and execution.get('launcher_error') is None
        and execution.get('uncertain_start', False) is False
        and actual['verified_worker_starts'] == 1 and wall <= 600 and within_caps
        and not raw['errors'] and all(counters[k] == 0 for k in ZERO_COUNTERS)
        and counters['NLI_forward_pairs_completed'] == counters['NLI_forward_pairs_attempted'] == counters['NLI_forwards'] == 72
        and counters['native_index_initializations_completed'] == 8
        and counters['native_queries_completed'] == 24
        and counters['DEV_cases_completed'] == 24 and counters['DEV_pairs_completed'] == 72
        and counters['BGE_initializations_completed'] == counters['NLI_model_initializations_completed'] == 1
        and counters['BGE_forwards_completed'] > 0 and counters['BGE_texts_completed'] > 0
        and isinstance(raw.get('cases'), list) and len(raw['cases']) == 24)
    require(not qualified or successful, 'Failed/partial/overbudget/forbidden-network worker cannot qualify')
    if not successful:
        require(not qualified, 'Unsuccessful runtime cannot qualify')
    return successful


def check_execution_history(old, new, actual):
    require(isinstance(old, dict) and isinstance(new, dict) and set(old) <= set(new),
            'Observed cumulative execution dropped historical fields')
    increment = {'cumulative_bounded_native_process_attempts_including_qualification'}
    for key, value in old.items():
        if key in increment:
            require(type(value) is int and type(new[key]) is int
                    and new[key] == value+actual['worker_attempts'], 'Actual cumulative worker count differs')
        else: require(new[key] == value, 'Historical execution field changed: '+key)
    require(all(k.startswith('epoch26_') for k in set(new)-set(old)), 'New execution counters outside epoch26 namespace')
    require(new.get('epoch26_actual_execution') == actual, 'Cumulative epoch26 actual counters differ')


def checked_final(project, manifest, checkpoint, cont, old_cont, parent, plan, frozen):
    require(manifest.get('epoch') == 26 and manifest.get('kind') == KIND
            and manifest.get('source_checkpoint') == BASE_COMMIT
            and manifest.get('published_frozen_source_commit') == parent
            and manifest.get('all_slots_closed') is True
            and manifest.get('benchmark_accepted') is False
            and manifest.get('champion_promoted') is False
            and manifest.get('new_submission') is False
            and type(manifest.get('diagnostic_qualified')) is bool,
            'Final diagnostic scope/closure/promotion flags invalid')
    require(manifest.get('official_rank') is None
            and manifest.get('official_SOTA_verified', False) is False
            and manifest.get('official_SOTA_established', False) is False,
            'DEV diagnostic cannot assert official placement')
    for key in ('plan', 'source_freeze'):
        require(manifest.get(key) == frozen[key], 'Final changed frozen '+key+' ref')
    refs = final_refs(project, manifest, checkpoint)
    results, execution, report = (parse(project/refs[k]['path']) for k in ('results', 'execution', 'independent_report'))
    raw = parse(project/refs['raw']['path']) if refs['raw'] else None
    actual = manifest.get('actual_execution')
    require(results.get('actual_execution') == actual, 'Manifest and exact RESULTS actual counters differ')
    if refs['raw']:
        require(execution.get('raw_bytes') == refs['raw']['bytes']
                and execution.get('raw_sha256') == refs['raw']['sha256'], 'Outer execution/raw identity differs')
    success = check_actual(actual, raw, execution, manifest['diagnostic_qualified'])
    require(report.get('epoch') == 26 and report.get('checks_passed') is True
            and report.get('benchmark_accepted') is False
            and report.get('diagnostic_qualified') == manifest['diagnostic_qualified'],
            'Independent diagnostic audit verdict differs')
    evidence = report.get('evidence', report)
    for key in ('raw', 'execution', 'results'):
        require(evidence.get(key) == refs[key], 'Independent audit does not bind exact '+key)
    if not success:
        require(any(word in manifest.get('status', '').upper() for word in ('FAILED', 'REJECTED', 'BLOCKED'))
                and not results.get('metrics')
                and not results.get('class_metrics')
                and not results.get('annotation_choices_accessed', 0),
                'Failed run must retain rejection without complete-corpus metrics or gold projection')
    roles = manifest.get('data_roles', plan.get('data_roles', plan.get('benchmark_roles')))
    require(roles == plan.get('data_roles', plan.get('benchmark_roles')), 'Final data roles changed')
    check_execution_history(old_cont['execution_observed'], cont.get('execution_observed'), actual)
    epochs = cont.get('epochs')
    require(isinstance(epochs, list) and epochs[:-1] == old_cont['epochs']
            and len(epochs) == len(old_cont['epochs'])+1
            and epochs[-1].get('epoch') == 26
            and epochs[-1].get('native_worker_attempts') == actual['worker_attempts'],
            'Continuation must append exactly one actual epoch26 record')
    old_ledger, ledger = old_cont['cumulative_budget_ledger'], cont.get('cumulative_budget_ledger')
    require(isinstance(ledger, dict) and set(old_ledger) <= set(ledger), 'Budget ledger dropped historical fields')
    mutable = {'current_epoch_closed', 'scope', 'new_study_id', 'new_study_attempt_cap',
        'new_study_attempts_used', 'new_study_attempts_remaining',
        'cumulative_native_process_attempts_including_qualification',
        'cumulative_corpus_attempts_current', 'count_scope'}
    require(all(ledger[k] == v for k, v in old_ledger.items() if k not in mutable),
            'Historical closed budget changed')
    require(all(k in old_ledger or k.startswith('epoch26_') for k in ledger), 'New budget metadata outside epoch26 namespace')
    require(ledger.get('current_epoch_closed') is True and ledger.get('scope') == 'ALL_EPOCHS_CLOSED_THROUGH26',
            'Final cumulative ledger did not close epoch26')
    for key in ('publication_period_native_calls_allowed', 'new_study_attempts_remaining',
        'new_study_unspent_phase_slots', 'allowed_further_attempts_in_closed_study',
        'conditional_DEV_after_exact_remote_readback', 'conditional_CONF_after_independent_DEV_runtime_gates'):
        require(type(ledger.get(key)) is int and ledger[key] == 0, 'Final allowance not closed: '+key)
    require(ledger.get('cumulative_native_process_attempts_including_qualification')
            == old_ledger['cumulative_native_process_attempts_including_qualification']+actual['worker_attempts'],
            'Cumulative process effort increment differs')
    require(ledger.get('epoch26_actual_execution') == actual, 'Ledger actual effort differs')
    if ledger.get('cumulative_corpus_attempts_current') != old_ledger.get('cumulative_corpus_attempts_current'):
        require(ledger['cumulative_corpus_attempts_current'] == old_ledger['cumulative_corpus_attempts_current']+actual['worker_attempts'],
                'Cumulative corpus increment differs from actual reserved effort')
    if 'cumulative_budget_ledger' in manifest:
        require(manifest['cumulative_budget_ledger'] == ledger, 'Manifest/continuation budget differs')
    return manifest


def verify_prior(prior, baseline, expected):
    require(set(baseline) <= set(prior), 'Prior publication dropped historical Git tuples')
    for path, row in baseline.items():
        if path not in CONTROLS: require(prior[path] == row, 'Prior historical tuple differs: '+path)
    for path, row in prior.items():
        if path not in CONTROLS: require(expected.get(path) == row, 'Published source changed/disappeared: '+path)


def transport_groups(changed):
    entries, blobs, groups = [], [], []
    for path, body in sorted(changed.items()):
        text = public_text(path, body)
        entry = {'path': SCOPE+path, 'mode': '100644', 'type': 'blob'}
        if len(body) > LARGE_FILE_BYTES:
            payload = {'content': text, 'encoding': 'utf-8'}
            require(len(encoded(payload)) < MAX_BLOB_JSON, 'Blob JSON must remain strictly below8384512 bytes')
            blobs.append((path, body, payload)); entry['sha'] = gitsha(body)
        else: entry['content'] = text
        require(len(encoded({'tree_elements': [entry]})) < MAX_TREE_JSON, 'Single tree entry exceeds strict175904 cap')
        entries.append(entry)
    batch = []
    for entry in entries:
        if len(encoded({'tree_elements': batch+[entry]})) >= MAX_TREE_JSON:
            require(batch, 'Tree grouping cannot fit entry')
            groups.append(batch); batch = []
        batch.append(entry)
    if batch: groups.append(batch)
    return blobs, groups


def prepare(args):
    project, kit, controls, priorcontrols = map(directory,
        (args.project, args.kit, args.controls, args.priorcontrols))
    scope = directory(project.parent)
    live_owner(scope)
    out = new_output(args.out, (project, kit, controls, priorcontrols))
    for name in ('parent', 'expected_main', 'expected_root', 'expected_bench', 'expected_scope'):
        require(re.fullmatch('[0-9a-f]{40}', getattr(args, name) or ''), 'Exact Git SHA required: '+name)
    require(args.expected_main == MAIN_COMMIT, 'Pinned original main guard required')
    readback_bytes = content(args.parent_readback)
    check_readback(loads(readback_bytes), args.phase, args.parent,
                   (args.expected_root, args.expected_bench, args.expected_scope))
    source_bytes = content(args.source_filemap)
    baseline = verify_baseline(kit, loads(source_bytes))
    current = walk_current(project)
    review_bytes = content(args.reviewed_files)
    checked_review(loads(review_bytes), current)
    bodies, prior_bodies, old_cp, cp, cont, active, plan, frozen, reconstruction = checked_controls(
        controls, priorcontrols, kit, project, current, args.phase, args.parent)
    if args.prior_expected:
        prior_bytes = content(args.prior_expected); prior = tuple_map(loads(prior_bytes))
    else:
        require(args.phase == 'source', 'Final requires actual source expected-leaves input')
        prior = copy.deepcopy(baseline)
        for name, body in prior_bodies.items(): prior[name] = leaf(name, body)
        prior_bytes = encoded({'scope': SCOPE, 'files': [prior[k] for k in sorted(prior)]})
    for name, body in prior_bodies.items():
        require(prior.get(name) == leaf(name, body), 'Prior controls differ from actual prior expected tuples: '+name)
    if args.phase == 'final':
        # Every tuple newly published at source must also be a preserved CP row.
        source_rows = cp_rows(loads(prior_bodies['CHECKPOINT_MANIFEST.json']))
        require(set(prior)-set(baseline) <= set(source_rows), 'Source expected tuple lacks checkpoint identity')
        for path in set(prior)-set(baseline):
            require(ref(project, path) == source_rows[path] and leaf(path, content(project/path)) == prior[path],
                    'Frozen source tuple/checkpoint bytes changed: '+path)
    expected = copy.deepcopy(baseline)
    for path, body in {**current, **bodies}.items():
        require(path not in baseline or path in CONTROLS, 'Original Git leaf overwrite: '+path)
        expected[path] = leaf(path, body)
    verify_prior(prior, baseline, expected)
    check_transport(project, parse(kit/'CONTINUATION.json'), cont, cp_rows(cp), set(expected))
    if args.phase == 'final':
        manifest = parse(project/(E+'EPOCH_MANIFEST.json'))
        checked_final(project, manifest, cp_rows(cp), cont, parse(kit/'CONTINUATION.json'),
                      args.parent, plan, frozen)
    changed = {p: b for p, b in {**current, **bodies}.items() if prior.get(p) != expected[p]}
    require(changed and CONTROLS <= set(changed), 'All three control updates and nonduplicate stage required')
    blobs, groups = transport_groups(changed)
    metadata = {'schema_version': 1, 'stage': args.phase, 'scope': SCOPE,
        'source_checkpoint': BASE_COMMIT, 'publication_parent': args.parent,
        'CAS_guards': {'expected_main': args.expected_main, 'expected_root_tree': args.expected_root,
            'expected_benchmarks_tree': args.expected_bench, 'expected_scope_tree': args.expected_scope,
            'expected_branch_sha': args.parent, 'force': False},
        'source_filemap_sha256': sha(source_bytes), 'prior_expected_sha256': sha(prior_bytes),
        'reviewed_files_sha256': sha(review_bytes), 'parent_readback_sha256': sha(readback_bytes),
        'historical_Git_leaves': len(baseline), 'prior_Git_leaves': len(prior),
        'old_CP_rows': len(cp_rows(old_cp)), 'new_CP_rows': len(cp_rows(cp)),
        'new_epoch26_public_files': len(current), 'expected_Git_leaves': len(expected),
        'changed_files': [], 'old_noncontrol_tuples_preserved': True,
        'old_CP_metadata_preserved': True, 'frozen_source_tuples_preserved': True,
        'inherited_archive_transport_unchanged': reconstruction,
        'Git_mutations': 0, 'native_or_model_or_corpus_calls': 0,
        'large_blob_requests': [], 'create_tree_groups': [],
        'transport_limits': {'large_file_bytes': LARGE_FILE_BYTES,
            'blob_JSON_exclusive_bytes': MAX_BLOB_JSON, 'tree_JSON_exclusive_bytes': MAX_TREE_JSON,
            'tool_metadata_reserve_bytes': 4096},
        'controller_requirements': {'fresh_exact_guardian_and_FLOCK_before_every_mutation': True,
            'fresh_main_and_root_bench_siblings_invariance': True, 'nonforce_parent_CAS': True,
            'actual_remote_readback_before_execution_admission_or_unlock': True}}
    out.mkdir(mode=0o700); (out/'transport').mkdir(mode=0o700)
    for path, body in sorted(changed.items()):
        metadata['changed_files'].append({'path': path, 'bytes': len(body),
            'sha256': sha(body), 'git_blob_sha1': gitsha(body)})
    for number, (path, body, payload) in enumerate(blobs):
        filename = 'transport/blob-%03d.json'%number; data = encoded(payload); write(out/filename, data)
        metadata['large_blob_requests'].append({'path': path, 'file': filename, 'bytes': len(data),
            'sha256': sha(data), 'expected_blob_sha1': gitsha(body), 'must_verify_before_tree': True})
    for number, group in enumerate(groups):
        filename = 'transport/tree-%03d.json'%number; data = encoded({'tree_elements': group})
        require(len(data) < MAX_TREE_JSON, 'Serialized tree request cap exceeded'); write(out/filename, data)
        metadata['create_tree_groups'].append({'file': filename, 'bytes': len(data), 'sha256': sha(data), 'entries': len(group)})
    leaves = encoded({'schema_version': 1, 'scope': SCOPE, 'source_checkpoint': BASE_COMMIT,
        'files': [expected[path] for path in sorted(expected)]})
    write(out/'expected-leaves.json', leaves)
    metadata['expected_leaves'] = {'file': 'expected-leaves.json', 'bytes': len(leaves), 'sha256': sha(leaves), 'count': len(expected)}
    write(out/'metadata.json', encoded(metadata, pretty=True))
    return {key: metadata[key] for key in ('stage', 'publication_parent', 'old_CP_rows',
        'new_CP_rows', 'new_epoch26_public_files', 'expected_Git_leaves', 'expected_leaves', 'Git_mutations')}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ('project', 'kit', 'source-filemap', 'reviewed-files', 'parent-readback', 'out'):
        cli.add_argument('--'+name, type=Path, required=True)
    cli.add_argument('--controls', '--controls-dir', dest='controls', type=Path, required=True)
    cli.add_argument('--priorcontrols', '--prior-controls-dir', dest='priorcontrols', type=Path, required=True)
    cli.add_argument('--phase', '--mode', dest='phase', choices=['source', 'final'], required=True)
    cli.add_argument('--prior-expected', type=Path)
    for name in ('parent', 'expected-main', 'expected-root', 'expected-bench', 'expected-scope'):
        cli.add_argument('--'+name, required=True)
    import json
    print(json.dumps(prepare(cli.parse_args()), sort_keys=True))


if __name__ == '__main__': main()
