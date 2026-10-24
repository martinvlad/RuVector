"""Derive three epoch23 controls locally; source/final outputs never admit a run.

The single engineering worker is conditional on independently verified actual
remote source publication. The builder itself only reads project bytes and
writes an exclusive outside control directory. Benchmark roles remain empty.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import copy
import json
from pathlib import Path
import re
from publication_common_v1 import (P, CONTROLS, check_final_manifest,
    check_history, check_ledger_history, check_transport, content, cp_rows,
    directory, encoded, final_ledger, live_owner, new_output, parse, ref, require, sha,
    walk_current, write)

FROZEN = {'plan': P + 'epoch23/plan.json',
          'source_freeze': P + 'epoch23/source-freeze.json',
          'specification': P + 'epoch23/PLAN_SPEC.json',
          'audit_protocol': P + 'audit/epoch23/protocol.json'}
FINAL = {'results': P + 'epoch23/RESULTS.json',
         'manifest': P + 'epoch23/EPOCH_MANIFEST.json',
         'source_manifest': P + 'epoch23/SOURCE_MANIFEST.json',
         'used_identities': P + 'epoch23/USED_IDENTITIES.json',
         'rejection_ledger': P + 'epoch23/REJECTION_LEDGER.json',
         'acceptance_report': P + 'audit/epoch23/acceptance-rejection.json'}


def base_continuation(kit, scope):
    old = parse(kit / 'CONTINUATION.json')
    lease_path = scope / 'controls-lease/CONTINUATION.json'
    if lease_path.exists():
        lease = parse(lease_path)
        require(set(old) <= set(lease) and set(lease) - set(old) == {'epoch23_planning'},
                'Planning continuation has unrelated additions/deletions')
        require(all(lease[k] == v for k, v in old.items() if k != 'active_run'),
                'Planning continuation changed prior checkpoint fields')
        return old, copy.deepcopy(lease)
    return old, copy.deepcopy(old)


def build(args):
    project, kit, scope = map(directory, (args.project, args.kit, args.scope))
    out = new_output(args.out, (project, kit))
    require(re.fullmatch('[0-9a-f]{40}', args.parent), 'Exact parent commit required')
    owner = live_owner(scope)
    old_cont, cont = base_continuation(kit, scope)
    old_cp_bytes = content(kit / 'CHECKPOINT_MANIFEST.json')
    require(old_cont['checkpoint_manifest_sha256'] == sha(old_cp_bytes),
            'Source checkpoint hash differs from source continuation')
    cp = parse(kit / 'CHECKPOINT_MANIFEST.json')
    before = check_history(project, cp)
    current = walk_current(project)
    require(not set(before).intersection(current), 'Current roots overwrite history')
    rows = copy.deepcopy(before)
    rows.update({name: {'path': name, 'bytes': len(data), 'sha256': sha(data)}
                 for name, data in current.items()})
    refs = {name: ref(project, path) for name, path in FROZEN.items()}
    spec = parse(project / FROZEN['specification'])
    source = spec.get('source_checkpoint')
    require(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source),
            'Specification must identify immutable source_checkpoint')
    final = args.mode == 'final'
    cp['project_files'] = [rows[name] for name in sorted(rows)]
    cp['epoch23_' + ('final' if final else 'prelaunch')] = {
        'source_checkpoint': source, 'public_new23_files': len(current),
        'kind': 'SOURCE_SCOPE_ENGINEERING',
        'scope': 'Reviewed public source and engineering evidence; no benchmark generalization.'}
    cp_bytes = encoded(cp, pretty=True)
    active = {'schema_version': 1, 'run_id': owner['run_id'],
        'state': 'EPOCH23_CLOSED' if final else 'EPOCH23_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION',
        'work_active': not final, 'experiments_active': False, 'native_allowed': 0,
        'native_allowed_after_exact_remote_readback': 0 if final else 1,
        'conditional_confirmation_after_independent_DEV_runtime_gates': 0,
        'checkpoint_parent': args.parent, 'owner_pid': owner['pid'],
        'owner_startticks': owner['startticks'], 'lock_inode': owner['lock_inode'],
        'started_at': owner['started_at'], 'expires_at': owner['expires_at'],
        'OS_lock_held': True, 'OS_lock_release_pending_final_remote_readback': final,
        'limits': {'worker_attempt_cap': 1, 'CPU_threads': 2,
                   'seconds_per_process_including_init_cleanup': 600,
                   'paid_API_calls': 0, 'GPU_calls': 0},
        'instruction': ('Closed; all unspent epoch23 slots permanently closed.' if final else
            'No execution now. One frozen source-scope engineering worker only after independent actual remote source/readback and live exclusive-lock admission; no retry, benchmark/confirmation inference, fit, promotion or submission.')}
    cont['prior_published_base_commit'] = args.parent
    cont['checkpoint_manifest_sha256'] = sha(cp_bytes)
    cont['active_run'] = dict(active, path='ACTIVE_RUN.json')
    cont['epoch23_frozen_study'] = dict(refs, source_checkpoint=source,
        kind='SOURCE_SCOPE_ENGINEERING', train=[], dev=[], calibration=[], confirmation=[],
        worker_attempt_cap=1, benchmark_promotion_or_submission_allowed=False)
    refresh = P + 'legal-transfer/epoch23/benchmark-refresh.json'
    if refresh in current:
        cont['benchmark_refresh'] = ref(project, refresh)
        cont['epoch23_official_refresh'] = ref(project, refresh)
    if final:
        records = {key: ref(project, path) for key, path in FINAL.items()}
        manifest = parse(project / FINAL['manifest'])
        attempts = check_final_manifest(manifest,
            parse(project / FROZEN['plan'])['expected_actual_native_queries'])
        require(manifest['source_checkpoint'] == source
                and manifest['published_frozen_source_commit'] == args.parent,
                'Final measurement source/parent mismatch')
        for name in ('results', 'source_manifest', 'used_identities',
                     'rejection_ledger', 'acceptance_report'):
            require(manifest[name] == records[name], 'Final manifest reference changed: ' + name)
        old_ledger = parse(project / old_cont['rejection_ledger']['path'])
        check_ledger_history(old_ledger, parse(project / FINAL['rejection_ledger']))
        cont['epoch23_final'] = dict(records, status=manifest['status'],
            actual_execution=manifest['actual_execution'],
            engineering_qualified=manifest['engineering_qualified'], benchmark_accepted=False,
            all_slots_closed=True, champion_promoted=False, new_submission=False)
        cont['epoch23_data_roles'] = copy.deepcopy(manifest['data_roles'])
        require(not any(row.get('epoch') == 23 for row in cont['epochs']),
                'Epoch23 already closed; do not append a duplicate epoch')
        cont['epochs'].append({'epoch': 23, 'status': manifest['status'],
            'manifest': records['manifest']['path'], 'native_worker_attempts': attempts,
            'kind': 'SOURCE_SCOPE_ENGINEERING', 'confirmation_consumed': False})
        cont['rejection_ledger'] = records['rejection_ledger']
        cont['cumulative_budget_ledger'] = final_ledger(
            cont['cumulative_budget_ledger'], manifest, project)
        if 'cumulative_execution' in manifest:
            cont['execution_observed'] = copy.deepcopy(manifest['cumulative_execution'])
        if 'next_research_priority' in manifest:
            cont['next_research_priority'] = manifest['next_research_priority']
            cont['latest_learning'] = {'manifest': records['manifest'],
                                      'direction': manifest['next_research_priority']}
        active.update(actual_epoch23_worker_attempts=attempts,
            all_unspent_epoch23_slots_permanently_closed=True, owned_native_groups_closed=True)
        cont['active_run'] = dict(active, path='ACTIVE_RUN.json')
    require(cont['champion'] == old_cont['champion'] and cont['goal_met'] == old_cont['goal_met'] is False
            and cont['official_rank'] == old_cont['official_rank']
            and cont['used_confirmation_sets'] == old_cont['used_confirmation_sets']
            and cont['unused_confirmation_sets'] == old_cont['unused_confirmation_sets']
            and cont['exposed_development_sets'] == old_cont['exposed_development_sets'],
            'Champion, official status or historical benchmark roles changed')
    check_transport(project, old_cont, cont, rows)
    out.mkdir(mode=0o700)
    for name, data in [('CHECKPOINT_MANIFEST.json', cp_bytes),
                       ('CONTINUATION.json', encoded(cont, pretty=True)),
                       ('ACTIVE_RUN.json', encoded(active, pretty=True))]:
        write(out / name, data)
    return {'mode': args.mode, 'CP_files': len(rows), 'old_CP_files': len(before),
            'new23_files': len(current), 'checkpoint_sha256': sha(cp_bytes),
            'native_model_network_calls': 0, 'project_files_written': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('project', 'kit', 'scope', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--mode', choices=['source', 'final'], required=True)
    parser.add_argument('--parent', required=True)
    print(json.dumps(build(parser.parse_args()), sort_keys=True))


if __name__ == '__main__':
    main()
