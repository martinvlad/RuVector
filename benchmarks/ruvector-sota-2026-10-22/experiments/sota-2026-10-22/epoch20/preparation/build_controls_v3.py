"""Render the three scoped Git controls from immutable public source/results."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timezone

P = 'experiments/sota-2026-10-22/'
SOURCE = '01c42365b8d79c968ea4f49120a5c1d71b9e0687'
OLD_CP = '278b03ea97c6600455455fb145ab4ef2a238e0f4a720833c6ee95ad749411a25'


def encoded(v): return (json.dumps(v, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
def sha(b): return hashlib.sha256(b).hexdigest()


def directory(p):
    p = Path(p).absolute()
    assert p == p.resolve() and p.is_dir()
    assert not any(x.is_symlink() for x in [p, *p.parents])
    return p


def body(p):
    p = Path(p).absolute()
    assert p == p.resolve() and p.is_file()
    assert not any(x.is_symlink() for x in [p, *p.parents])
    return p.read_bytes()


def read(p): return json.loads(body(p))


def ref(root, n):
    p = root / n
    assert p.resolve().is_relative_to(root)
    b = body(p)
    return {'path': n, 'bytes': len(b), 'sha256': sha(b)}


def build(args):
    root, kit, scope = map(directory, (args.project, args.kit, args.scope))
    out = args.out.absolute()
    assert out == out.resolve() and not os.path.lexists(out)
    assert not out.is_relative_to(root) and not out.is_relative_to(kit)
    assert not any(x.is_symlink() for x in [out, *out.parents])
    owner = read(scope / 'owner.json'); os.kill(owner['pid'], 0)
    assert Path('/proc/' + str(owner['pid']) + '/stat').read_text().split()[2] != 'Z'
    spec = read(root / (P + 'epoch20/PLAN_SPEC.json'))
    row = spec['publication_helper']; assert ref(root, row['path']) == row
    ms = importlib.util.spec_from_file_location('reviewed20publiccontrols', root / row['path'])
    helper = importlib.util.module_from_spec(ms); ms.loader.exec_module(helper)
    current = helper.walk_current(root)
    assert sha(body(kit / 'CHECKPOINT_MANIFEST.json')) == OLD_CP
    cp = read(kit / 'CHECKPOINT_MANIFEST.json')
    old = {r['path']: r for r in cp['project_files']}
    assert len(old) == len(cp['project_files']) == 2813 and not set(old).intersection(current)
    for n, b in current.items(): old[n] = {'path': n, 'bytes': len(b), 'sha256': sha(b)}
    cp['project_files'] = [old[n] for n in sorted(old)]
    final = args.mode == 'final'
    manifest = read(root / (P + 'epoch20/EPOCH_MANIFEST.json')) if final else None
    actual = manifest['actual_execution'] if final else None
    attempts = actual['worker_attempts'] if final else 0
    assert type(attempts) is int and 0 <= attempts <= 2
    if final: assert actual['owned_live_processes_closed'] is True and manifest['all_slots_closed'] is True
    cp['epoch20_' + ('final' if final else 'prelaunch')] = {
        'source_checkpoint': SOURCE, 'public_new20_files': len(current),
        'kind': 'ORIGINAL_FP32_TYPED_ANLI_READER_NATIVE_RETRIEVAL',
        'scope': 'Exact reviewed public source/evidence only; external weights/runtime and raw pages/mail excluded.'}
    cp_bytes = encoded(cp); cont = read(kit / 'CONTINUATION.json')
    cont.update(prior_published_base_commit=args.parent, checkpoint_manifest_sha256=sha(cp_bytes),
                goal_met=False, official_rank=None, champion='SubmittedNative104/RRF10 unchanged')
    state = 'EPOCH20_CLOSED' if final else 'EPOCH20_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION'
    active = {'schema_version': 1, 'run_id': owner['run_id'], 'state': state,
        'experiments_active': not final, 'native_allowed': 0,
        'native_allowed_after_exact_remote_readback': 0 if final else 1,
        'conditional_confirmation_after_independent_DEV_runtime_gates': 0 if final else 1,
        'checkpoint_parent': args.parent, 'started_at': owner['started_at'],
        'expires_at': datetime.fromtimestamp(owner['expires_unix'], timezone.utc).isoformat(),
        'OS_lock_held': True, 'OS_lock_release_pending_final_remote_readback': final,
        'limits': {'worker_attempt_cap': 2, 'CPU_threads': 2, 'seconds_per_process_including_init_cleanup': 600, 'paid_GPU_calls': 0},
        'instruction': 'Closed; no further epoch20 execution.' if final else
            'Source-only publication. Exact independent remote readback plus live exclusive-lock proof admits DEV once. CONF additionally requires independent frozen DEV and full-cost runtime gates. Engineering canaries precede all new legal parsing; no retries or promotion/submission.'}
    cont['active_run'] = {k: active[k] for k in ('run_id', 'state', 'experiments_active', 'native_allowed')}
    cont['active_run']['path'] = 'ACTIVE_RUN.json'
    cont['epoch20_frozen_study'] = {'source_checkpoint': SOURCE, 'plan': ref(root, P + 'epoch20/plan.json'),
        'source_freeze': ref(root, P + 'epoch20/candidate-source-freeze.json'),
        'audit_protocol': ref(root, spec['references']['audit_protocol']),
        'input_recipe': ref(root, P + 'legal-transfer/epoch20/input-recipe.json'),
        'model_assets_lock': ref(root, P + 'legal-transfer/epoch20/model-assets.lock.json'),
        'train': [], 'calibration': [], 'DEV': {'documents': 8, 'questions': 24, 'lazy_after_semantic_gate': True},
        'CONF': {'documents': 8, 'questions': 24, 'exact_unused_epoch16_bank': True, 'conditional_after_DEV_runtime_gates': True},
        'promotion_or_submission_allowed': False}
    refresh = read(root / (P + 'legal-transfer/epoch20/benchmark-refresh.json'))
    pub = read(root / (P + 'epoch20/preparation/publisher-status.json'))
    j, c = refresh['JevBench'], refresh['ClaimBench']
    cont['benchmark_targets']['JevBench'].update(leader_observed=j['leader'], capability_observed=j['Capability'],
        headline_display=j['headline_display'], last_observed_at_UTC=j['source']['at'], latest_refresh_attempt=j, refresh_required=True)
    cont['benchmark_targets']['ClaimBench'].update(decision_leader_observed=c['decision_leader']['model'],
        accuracy_percent_observed=c['decision_leader']['accuracy_percent'], overall_language_models_at100=len(c['language_models_at100']),
        RuVector_measured=False, last_observed_at_UTC=c['official_aggregate']['at'], latest_refresh_attempt=c, full_access_verified=False)
    cont['benchmark_refresh'] = ref(root, P + 'legal-transfer/epoch20/benchmark-refresh.json')
    cont['publisher_status'] = ref(root, P + 'epoch20/preparation/publisher-status.json')
    cont['publisher_status_refresh_scope'] = pub['official_result']['scope']
    cont['official_result_status'] = dict(pub['official_result'], original115_is_queue_position_never_rank=True)
    cont['restoration_epoch20'] = {'fresh_source_commit': SOURCE, 'source_Git_blobs': 2890,
        'CP_files': 2813, 'KIT_files': 61, 'BASE_files': 48, 'unique_project_files': 2892,
        'public_runtime_assets': 25, 'selected_reader_assets': 7, 'official_CPU_wheels': 31,
        'verified_wheel_members': 17498, 'reviewed_bootstrap_restore_used': True, 'no_prior_filesystem_trust': True}
    ledger = cont['cumulative_budget_ledger']
    ledger.update(new_study_id='native-anli-roberta-fp32-typed-e20', new_study_attempt_cap=2,
        new_study_attempts_used=attempts, new_study_attempts_remaining=0, new_study_unspent_phase_slots=0 if final else 2,
        current_epoch_closed=final, publication_period_native_calls_allowed=0,
        conditional_DEV_after_exact_remote_readback=0 if final else 1,
        conditional_CONF_after_independent_DEV_runtime_gates=0 if final else 1,
        scope='ALL_EPOCHS_CLOSED_THROUGH20' if final else 'PRIOR19_CLOSED_EPOCH20_SOURCE_PENDING_ADMISSION')
    if final:
        records = {key: ref(root, P + 'epoch20/' + name) for key, name in
            [('manifest', 'EPOCH_MANIFEST.json'), ('results', 'RESULTS.json'), ('used_identities', 'USED_IDENTITIES.json'),
             ('source_manifest', 'SOURCE_MANIFEST.json'), ('rejection_ledger', 'REJECTION_LEDGER.json')]}
        cont['epoch20_final'] = dict(records, status=manifest['status'], actual_execution=actual,
            engineering_qualified=manifest['engineering_qualified'], benchmark_accepted=manifest['benchmark_accepted'],
            all_slots_closed=True, champion_promoted=False, new_submission=False)
        cont['epochs'].append({'epoch': 20, 'status': manifest['status'], 'manifest': records['manifest']['path'],
            'native_worker_attempts': attempts, 'confirmation_consumed': manifest['data_roles']['confirmation_retired']})
        cont['epoch20_data_roles'] = manifest['data_roles']
        cont['execution_observed'] = manifest['cumulative_execution']
        ledger['epoch20_closed_study'] = dict(actual, allowed_further=0)
        ledger['cumulative_native_process_attempts_including_qualification'] = 20 + attempts
        corpus_attempts = manifest['cumulative_execution']['native_corpus_attempts_including_failed_request']
        assert type(corpus_attempts) is int and 19 <= corpus_attempts <= 21
        ledger.update(cumulative_native_attempts=corpus_attempts, total_historical_attempts=corpus_attempts,
            cumulative_corpus_attempts_preserved_through19=19, cumulative_corpus_attempts_current=corpus_attempts,
            count_scope='Legacy native attempt fields count corpus attempts; current bounded-process total separately includes engineering qualifications. HTTP counters remain separate.')
        cont['next_research_priority'] = manifest['next_research_priority']
        cont['latest_learning'] = {'manifest': records['manifest'], 'direction': manifest['next_research_priority']}
        cont['rejection_ledger'] = records['rejection_ledger']
        if manifest['data_roles']['DEV_inputs_projected']:
            cont['exposed_development_sets'].append(manifest['data_roles']['DEV_retirement_statement'])
        if manifest['data_roles']['confirmation_retired']:
            for bank in cont['unused_confirmation_sets']:
                if bank.get('document_ids') == [308, 159, 284, 501, 267, 494, 261, 313]:
                    bank.update(globally_retired=True, epoch20_model_unused=not manifest['data_roles']['confirmation_model_consumed'],
                                epoch20_annotation_choices_used=manifest['data_roles']['confirmation_annotation_choices_used'],
                                epoch20_NLI_forward_pairs=manifest['data_roles']['confirmation_NLI_forward_pairs'],
                                status='CONSUMED_EPOCH20_PERMANENT_DEV_NEVER_FRESH_CONFIRMATION')
        active.update(actual_epoch20_worker_attempts=attempts, all_unspent_epoch20_slots_permanently_closed=True,
                      owned_native_groups_closed=True, closed_at=manifest['finished_at'])
    else:
        cont['epoch20_planning'] = {'source_checkpoint': SOURCE, 'actual_native_attempts': 0,
            'planned_max_worker_attempts': 2, 'new_legal_case_or_annotation_choices_parsed': 0,
            'confirmation_calls': 0, 'promotion_allowed': False}
    out.mkdir(mode=0o700)
    for name, b in [('CHECKPOINT_MANIFEST.json', cp_bytes), ('CONTINUATION.json', encoded(cont)), ('ACTIVE_RUN.json', encoded(active))]:
        with (out / name).open('xb') as f: f.write(b); f.flush(); os.fsync(f.fileno())
    return {'mode': args.mode, 'CP_files': len(old), 'new20_files': len(current), 'checkpoint_sha256': sha(cp_bytes), 'native_calls_by_builder': 0}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    for name in ('project', 'kit', 'scope', 'out'): ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--mode', choices=('source', 'final'), required=True); ap.add_argument('--parent', required=True)
    print(json.dumps(build(ap.parse_args())))
