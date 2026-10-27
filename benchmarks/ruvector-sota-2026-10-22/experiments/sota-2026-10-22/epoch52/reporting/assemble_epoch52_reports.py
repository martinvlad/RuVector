"""Root-only metadata assembler. No science, shell, network or Git entry point.

ASSEMBLE(config_ref) adopts an explicit reviewed public inventory and writes summaries.
CLOSE(config_ref, assembly_ref, review_ref) requires independent exact-inventory review,
then writes the immutable epoch manifest and operational FINAL input. Never imports
candidate/model/custody/publication code or scans private directories.
"""
from pathlib import Path
import copy
import hashlib
import json
import math
import os
import time

W = Path('/dev/shm/ruvector-sota-2026-10-22/epoch52-1cb7b0384f3d')
R = W / 'project'
P = 'experiments/sota-2026-10-22/epoch52/'
ROOTS = (P, 'experiments/sota-2026-10-22/audit/epoch52/',
         'experiments/sota-2026-10-22/runtime/epoch52/')
BASE = '1cb7b0384f3d387672decd036a5db4bde865c017'
KIND = 'REAL_CONTRACTNLI_CONTRACT_BERT_WHOLE_SOURCE_PILOT'
DENY = {'486888de9602bbb5d817a55f707b4fcfd11c65e0',
        '3d5a61f9068acf2dabd2ae5c6bd531d9a9b464c5',
        'a68b7ba587332f176f65d0348de3e910aa16e77a'}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                       allow_nan=False) + '\n').encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def canonical(name):
    assert type(name) is str and name and not name.startswith('/') and '\\' not in name
    assert all(p not in ('', '.', '..') for p in name.split('/'))
    assert any(name.startswith(root) for root in ROOTS)
    assert not {'private', 'private-run', 'assets', '.venv'} & set(Path(name).parts)
    return R / name


def checked(row):
    assert set(row) == {'path', 'bytes', 'sha256'} and type(row['bytes']) is int
    p = Path(row['path'])
    p = p if p.is_absolute() else canonical(row['path'])
    assert not {'private', 'private-run', 'assets', '.venv'} & set(p.parts)
    assert p.is_file() and not any(q.is_symlink() for q in (p, *p.parents))
    body = p.read_bytes()
    assert len(body) == row['bytes'] and sha(body) == row['sha256']
    return body


def parsed(row):
    return json.loads(checked(row), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def ref(p, public=False):
    p = Path(p); b = p.read_bytes()
    return {'path': p.relative_to(R).as_posix() if public else str(p),
            'bytes': len(b), 'sha256': sha(b)}


def put(p, body):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    assert not any(q.is_symlink() for q in (p, *p.parents))
    if p.exists():
        assert p.read_bytes() == body, 'EXISTING_DIFFERENT_METADATA_STOP'
    else:
        with p.open('xb') as f:
            f.write(body); f.flush(); os.fsync(f.fileno())
    return ref(p, p.is_relative_to(R))


def select(value, path):
    for key in path:
        value = value[key]
    return value


def configuration(config_ref):
    c = parsed(config_ref)
    assert c['schema_version'] == 1 and c['epoch'] == 52 and c['source_checkpoint'] == BASE
    assert c['project_root'] == str(R) and c['work_root'] == str(W)
    assert c['kind'] == KIND and c['config_is_reviewed_public_metadata_only'] is True
    assert c['source_commit'] not in DENY and len(c['source_commit']) == 40
    assert all(ch in '0123456789abcdef' for ch in c['source_commit'])
    plan = parsed(c['plan']); freeze = parsed(c['source_freeze'])
    assert plan['epoch'] == freeze['epoch'] == 52 and plan['source_checkpoint'] == BASE
    assert plan['phase_roles']['dev']['document_ids'] == [64, 456, 482, 81]
    assert plan['confirmation_lineage_status'] == 'UNQUALIFIED_HOLD'
    owner = parsed(plan['owner_ref'])
    assert owner['epoch'] == 52 and owner['generation'] == 17
    assert owner['pid'] == 165898 and owner['startticks'] == 40007814
    proc = Path('/proc') / str(owner['pid'])
    parts = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    assert parts[0] not in ('Z', 'X') and int(parts[19]) == owner['startticks']
    st = os.stat(proc / 'fd/3'); lock = os.stat(owner['lock'])
    assert (st.st_dev, st.st_ino) == (lock.st_dev, lock.st_ino) == (33, 13626)
    assert 'FLOCK' in (proc / 'fdinfo/3').read_text()
    assert time.time() < owner['expires_unix'] and not (W / 'release.request').exists()
    assert c['plan']['path'] == P + 'plan.json' and c['source_freeze']['path'] == P + 'SOURCE_FREEZE.json'
    source = c['source_inventory']
    assert len(source) == len({r['path'] for r in source}) == 68
    for row in source:
        checked(row)
    sr = parsed(c['actual_SOURCE_receipt']); ind = parsed(c['independent_SOURCE_readback'])
    sm = parsed(c['baselines']['source_map'])
    assert sr['epoch'] == 52 and sr['phase'] == 'source' and sr['parent'] == BASE
    assert sr['commit'] == sm['commit'] == c['source_commit'] and sr['verified_actual_full_tree'] is True
    assert ind['checks_passed'] is True and ind['verified_actual_remote_readback'] is True
    assert ind['commit'] == c['source_commit'] and ind['tree_sha'] == sm['root']
    assert ind['source_plan_sha256'] == c['plan']['sha256']
    assert ind['source_freeze_sha256'] == c['source_freeze']['sha256']
    assert sr['root'] == sm['root'] and sr['scope'] == sm['scope_sha']
    for row in c['baselines'].values():
        checked(row)
    return c, plan, freeze


def ASSEMBLE(config_ref):
    c, plan, _ = configuration(config_ref)
    adoptions = c['public_adoptions']
    names = [row['destination']['path'] for row in adoptions]
    assert len(names) == len(set(names)) and not set(names) & {r['path'] for r in c['source_inventory']}
    bodies = {}
    for row in adoptions:
        dest = row['destination']; canonical(dest['path']); b = checked(row['source'])
        assert len(b) == dest['bytes'] and sha(b) == dest['sha256']
        bodies[dest['path']] = b
    def public(role):
        row = c['evidence'][role]
        assert row['path'] in bodies or row in c['source_inventory']
        b = bodies.get(row['path'])
        if b is None:
            b = checked(row)
        assert len(b) == row['bytes'] and sha(b) == row['sha256']
        return json.loads(b)
    raw = public('raw'); acceptance = public('independent_acceptance')
    data = public('DATA_admission'); outer = public('outer_execution')
    used = public('used_identities'); cf = public('used_confirmation')
    official = public('official_refresh')
    claims = {k: select(acceptance, p) for k, p in c['acceptance_field_paths'].items()}
    assert set(claims) == {'runtime_qualified', 'dev_passed', 'all_owned_processes_physically_closed'}
    assert all(type(v) is bool for v in claims.values())
    assert claims['all_owned_processes_physically_closed'] is True
    assert raw['epoch'] == data['epoch'] == acceptance['epoch'] == used['epoch'] == cf['epoch'] == 52
    assert raw['kind'] == KIND and raw['phase'] == 'dev'
    assert raw['plan_sha256'] == c['plan']['sha256'] and raw['source_freeze_sha256'] == c['source_freeze']['sha256']
    assert used['used_confirmation_identities'] == cf['used_confirmation_identities'] == []
    assert used['current_DEV_document_ids'] == cf['current_DEV_document_ids'] == [64, 456, 482, 81]
    assert cf['confirmation_lineage_status'] == 'UNQUALIFIED_HOLD'
    counters = copy.deepcopy(raw['counters'])
    assert all(counters[k] == 0 for k in ('paid_API_calls', 'GPU_calls', 'training_calls', 'calibration_calls', 'semantic_gold_decodes'))
    assert data['DATA_calls'] == 1
    wall = select(outer, c['outer_wall_field_path'])
    assert type(wall) in (int, float) and math.isfinite(wall) and wall >= 0
    result = None
    if claims['runtime_qualified']:
        result = public('scored_DEV_result')
        assert raw['status'] == 'FORECASTS_COMPLETE_NO_GOLD' and raw['errors'] == []
        assert result['epoch'] == 52 and result['phase'] == 'dev' and result['kind'] == KIND
        assert result['checks_passed'] is True and result['dev_passed'] is claims['dev_passed']
        assert result['EVALUATE_calls'] == 1 and result['used_confirmation_identities'] == []
        assert result['plan_sha256'] == c['plan']['sha256'] and result['source_freeze_sha256'] == c['source_freeze']['sha256']
        assert set(result['metrics']) == {'native', 'lexical', 'source_order', 'whole_source'}
        assert all(row['N'] == 12 for row in result['metrics'].values())
        assert result['raw_ref']['bytes'] == c['evidence']['raw']['bytes']
        assert result['raw_ref']['sha256'] == c['evidence']['raw']['sha256']
        assert result['actual_counters'] == counters
        assert result['actual_runtime_timing'] == raw['timing']
        assert result['actual_runtime_resources'] == raw['resources']
        assert counters['forecasts_completed'] == 48 and wall < 600
        assert counters['NLI_forwards_attempted'] == counters['NLI_forwards_completed'] == raw['expected_physical_forwards']
        assert 48 <= raw['expected_physical_forwards'] <= 228
        assert counters['reader_capacity_tokenizations'] == 48
        assert counters['reader_forward_pair_validations'] == raw['expected_physical_forwards']
        assert counters['native_corpus_batches'] == 1
        status = 'PASSED_DEV_CONFIRMATION_LINEAGE_HOLD' if claims['dev_passed'] else 'REJECTED_DEV'
    else:
        assert c['evidence'].get('scored_DEV_result') is None and claims['dev_passed'] is False
        status = 'REJECTED_RUNTIME_NOT_SCORED'
    actual = {**counters, 'DEV_DATA_calls': 1, 'DEV_Gold_calls': int(result is not None),
              'DEV_EVALUATE_calls': int(result is not None),
              'DEV_semantic_gold_decodes_after_seal': 12 if result is not None else 0,
              'semantic_gold_decodes_at_forecast_seal': counters['semantic_gold_decodes'],
              'CONF_DATA_calls': 0, 'CONF_Gold_calls': 0, 'CONF_EVALUATE_calls': 0,
              'CONF_native_batches': 0, 'allowed_further_epoch52_attempts': 0,
              'unused_second_slot_closed_for_lineage': True,
              'outer_wall_seconds_including_capture_physical_cleanup': wall}
    common = dict(schema_version=1, epoch=52, kind=KIND, source_checkpoint=BASE,
                  actual_SOURCE_commit=c['source_commit'], status=status,
                  native104_champion_preserved=True, candidate_promoted=False,
                  official_goal_verified=False, official_rank=None, new_submission=False,
                  confirmation_lineage_status='UNQUALIFIED_HOLD', used_confirmation_identities=[])
    results = dict(common, runtime_qualified=claims['runtime_qualified'], dev_passed=claims['dev_passed'],
                   actual_execution=actual, actual_runtime_timing=raw.get('timing'),
                   actual_runtime_resources=raw.get('resources'), errors=raw['errors'],
                   loading_audit=raw.get('loading_audit'), metrics=result['metrics'] if result else None,
                   gate_checks=result['gate_checks'] if result else None,
                   descriptive_uncertainty=result['descriptive_uncertainty'] if result else None,
                   all_owned_processes_physically_closed=True, evidence=c['evidence'],
                   DEV_document_groups_forever=[64, 456, 482, 81],
                   scientific_scope='Public DEV diagnostic, checkpoint-development/model-selection exposed; no fresh model holdout, full benchmark, publisher score/rank or eligibility claim.',
                   unscored_metrics_scope=None if result else 'Unavailable even if partial forecasts exist; no Gold/EVAL, never zero accuracy.',
                   official_status_scope='JevBench current leader UNVERIFIED after current header-size-cap rejection. Prior E51 observation is historical only.')
    outputs = {P + 'RESULTS.json': results,
               P + 'EXECUTION_COUNTERS.json': dict(common, actual_execution=actual,
                    raw_forecast_counter_scope='Native retrieval queries are not NLI forecasts; raw semanticGold0 is at forecastseal.'),
               P + 'LEARNINGS.json': dict(common, actual_model_quality_measured=result is not None,
                    all_DEV_groups_forever=[64, 456, 482, 81], next_research_priority=c['next_research_priority']),
               P + 'OFFICIAL_REFRESH_SUMMARY.json': dict(common, source=c['evidence']['official_refresh'],
                    JevBench_current_leader_verified=False, JevBench=official['JevBench'],
                    ClaimBench=official['ClaimBench'], publisher_status=official['publisher_status'])}
    oldledger = parsed(c['prior_rejection_ledger']); ledger = copy.deepcopy(oldledger)
    decision = dict(common, dev_passed=claims['dev_passed'], actual_execution=actual,
                    independent_acceptance=c['evidence']['independent_acceptance'],
                    results={'path': P+'RESULTS.json', 'bytes': len(encoded(results)), 'sha256': sha(encoded(results))})
    assert 'epoch52_decision' not in ledger
    ledger['epoch52_decision'] = decision
    ledger['epoch52_actual_execution'] = actual
    ledger['epoch52_next_research_priority'] = c['next_research_priority']
    ledger['rejections'] = ([*oldledger['rejections'], decision] if not claims['dev_passed']
                            else copy.deepcopy(oldledger['rejections']))
    for k, v in oldledger.items():
        assert ledger[k] == v if k != 'rejections' else ledger[k][:len(v)] == v
    outputs[P + 'REJECTION_LEDGER.json'] = ledger
    for name in outputs:
        assert name not in bodies
    for name, b in bodies.items():
        put(canonical(name), b)
    generated = [put(canonical(name), encoded(value)) for name, value in outputs.items()]
    inventory = sorted([*c['source_inventory'], *[r['destination'] for r in adoptions], *generated], key=lambda r:r['path'])
    assert len(inventory) == len({r['path'] for r in inventory})
    receipt = dict(common, config_ref=config_ref, inventory=inventory,
                   generated=generated, actual_execution=actual,
                   public_summary_review_still_required=True,
                   immutable_manifest_written=False, actual_scientific_Git_or_network_calls=0)
    return put(W / 'REPORT_ASSEMBLY.actual.v1.json', encoded(receipt))


def CLOSE(config_ref, assembly_ref, review_ref):
    c, plan, _ = configuration(config_ref)
    assembly = parsed(assembly_ref); review = parsed(review_ref)
    assert assembly['config_ref'] == config_ref and assembly['epoch'] == 52
    assert review['checks_passed'] is True and review['publication_allowed'] is True
    assert review['assembly_receipt_sha256'] == assembly_ref['sha256']
    assert review['config_sha256'] == config_ref['sha256']
    inventory = assembly['inventory']
    assert review['reviewed_files'] == inventory
    expected = {r['path'] for r in inventory}
    assert P + 'EPOCH_MANIFEST.json' not in expected
    for row in inventory:
        checked(row)
    # Only public current roots are scanned, to reject an unreviewed extra file.
    now = set()
    for root in ROOTS:
        for p in (R / root).rglob('*'):
            assert not p.is_symlink()
            if p.is_file():
                now.add(p.relative_to(R).as_posix())
    assert now == expected, 'UNREVIEWED_PUBLIC_FILE_OR_MISSING_INVENTORY'
    # Publish the independent review after its exact reviewed inventory is fixed.
    # Its own SHA is outside its body, avoiding a self-reference cycle.
    review_name = c['final_public_review_destination']
    canonical(review_name); assert review_name not in expected
    review_body = checked(review_ref)
    public_review = dict(path=review_name, bytes=len(review_body), sha256=sha(review_body))
    m = dict(schema_version=1, epoch=52, kind=KIND, source_checkpoint=BASE,
             actual_SOURCE_commit=c['source_commit'], status=assembly['status'],
             files=sorted([*inventory, public_review], key=lambda r:r['path']),
             independent_acceptance=c['evidence']['independent_acceptance'],
             public_summary_inventory_independent_review=public_review,
             results=next(r for r in inventory if r['path'] == P+'RESULTS.json'),
             no_project_additions_after_manifest=True, official_goal_verified=False,
             used_confirmation_identities=[])
    manifest_body = encoded(m)
    manifest = dict(path=P+'EPOCH_MANIFEST.json', bytes=len(manifest_body), sha256=sha(manifest_body))
    current = [*inventory, public_review, manifest]
    source_names = {r['path'] for r in c['source_inventory']}
    new = [r for r in current if r['path'] not in source_names]
    # Baseline facts remain append-only. Old champion/goal/unused-CF fields are absent from patch.
    cont = parsed(c['baselines']['current_CONT'])
    budget = copy.deepcopy(cont['cumulative_budget_ledger'])
    assert 'epoch52_actual_execution' not in budget
    budget['epoch52_actual_execution'] = assembly['actual_execution']
    exposed = copy.deepcopy(cont['exposed_development_sets'])
    assert type(exposed) is list
    exposed.append(dict(epoch=52, role='DEV_FOREVER', document_ids=[64,456,482,81],
                        all_hypotheses_and_aliases_for_entire_document_groups_permanently_DEV=True,
                        used_identities=c['evidence']['used_identities'],
                        used_confirmation=c['evidence']['used_confirmation'],
                        confirmation_consumed=False))
    official = parsed(c['evidence']['official_refresh'])
    bench = copy.deepcopy(cont['benchmark_refresh'])
    assert type(bench) is dict and 'epoch52_observation' not in bench
    bench['epoch52_observation'] = c['evidence']['official_refresh']
    lookup = {r['path']:r for r in current}
    final = dict(schema_version=1, epoch=52, kind=KIND, source_checkpoint=BASE,
                 actual_SOURCE_commit=c['source_commit'], status=assembly['status'],
                 actual_execution=assembly['actual_execution'], epoch_manifest=manifest,
                 results=lookup[P+'RESULTS.json'], learnings=lookup[P+'LEARNINGS.json'],
                 rejection_ledger=lookup[P+'REJECTION_LEDGER.json'],
                 used_identities=c['evidence']['used_identities'], used_confirmation=c['evidence']['used_confirmation'],
                 independent_acceptance=c['evidence']['independent_acceptance'],
                 official_refresh=c['evidence']['official_refresh'],
                 publisher_status_latest_observation=official['publisher_status'],
                 next_research_priority=c['next_research_priority'],
                 confirmation_lineage_status='UNQUALIFIED_HOLD', used_confirmation_identities=[],
                 official_goal_verified=False, official_rank=None, promotion_authorized=False,
                 publisher_submission_authorized=False, native104_champion_preserved=True)
    active = dict(epoch=52, phase='final', kind=KIND, source_checkpoint=BASE,
                  owner_sha256=plan['owner_ref']['sha256'], work_active=False, experiments_active=False,
                  OS_lock_observation_scope='PREPUBLICATION_SNAPSHOT_NOT_CURRENT_REMOTE_LEASE',
                  publication_is_not_scientific_authorization=True)
    x = dict(schema_version=1, epoch=52, kind=KIND, phase='final', source_checkpoint=BASE,
             parent=c['source_commit'], owner=plan['owner_ref'], plan=c['plan'], source_freeze=c['source_freeze'],
             transport_sources=plan['transport_sources'], epoch_manifest=manifest,
             actual_SOURCE_receipt=c['actual_SOURCE_receipt'], independent_SOURCE_readback=c['independent_SOURCE_readback'],
             **{k:v for k,v in c['baselines'].items() if k != 'current_ACTIVE'},
             artifacts=[dict(r, local_path=str(canonical(r['path']))) for r in new], ACTIVE=active,
             CONT_patch=dict(epoch52_final=final, rejection_ledger=lookup[P+'REJECTION_LEDGER.json'],
                             latest_learning=lookup[P+'LEARNINGS.json'], next_research_priority=c['next_research_priority'],
                             cumulative_budget_ledger=budget, benchmark_refresh=bench, exposed_development_sets=exposed),
             CP_phase_record=final, commit_message=c['commit_message'])
    # Complete every read/check/serialization before the first CLOSE write.
    input_body = encoded(x)
    assert not (W / 'FINAL_PHASE_INPUT.v1.json').exists()
    assert not canonical(manifest['path']).exists() and not canonical(review_name).exists()
    put(canonical(review_name), review_body)
    put(canonical(manifest['path']), manifest_body)
    final_input = put(W / 'FINAL_PHASE_INPUT.v1.json', input_body)
    return dict(epoch_manifest=manifest, FINAL_input=final_input, new_artifacts=len(new),
                all_source_artifacts_unchanged=len(c['source_inventory']),
                actual_scientific_Git_or_network_calls=0)
