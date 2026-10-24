"""Publish the exact failed epoch25 incident as a rejection, with no retroacceptance.

The frozen publisher correctly rejects a nonzero offline-operation counter. This
new postmeasurement procedural version preserves that counter and the failed
receipts. It permits their publication only with the original negative oracle
verdict. It neither changes the frozen study nor authorizes another attempt.

Private function clones reuse the frozen guard bytecode and every historical,
source, final-reference, payload and control check. Their private globals remove
only the incident counter from the forbidden-zero tuple. Original modules and
their globals stay unchanged. No counter or result is replaced or normalized.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import hashlib
import json
from pathlib import Path
import types

DIRECTORY = Path(__file__).resolve().parent
FROZEN_HELPERS = {
    'publication_common_v1.py': '02e6c1c616f9344dfd93ada63c239d18edab3a48ce0062e0281ed6debb9b06c1',
    'stage_publication_v1.py': '64c097a62fcea7fc0d3aae2a04e14e9585c101a33ab4e0c1fa001f90261f395b',
}


def verify_frozen_helpers():
    for name, expected in FROZEN_HELPERS.items():
        path = DIRECTORY / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen publisher bytes changed: ' + name)


verify_frozen_helpers()
import publication_common_v1 as common
import stage_publication_v1 as frozen_stage

P = common.P
NETWORK = 'Python_network_operations_attempted'
PUBLICATION_SCOPE = 'REJECTION_ONLY_NOT_AUTHORIZED_SUCCESS'
INCIDENT_REFS = {
    'raw_receipt': {'path': P+'epoch25/runs/engineering/raw.json', 'bytes': 200277,
        'sha256': 'c51adfd0c94368a514695fcb9c8f9c3d7863c73f03800a061c09ce0ea887ec83'},
    'outer_receipt': {'path': P+'epoch25/execution.json', 'bytes': 1259,
        'sha256': 'd3f8bd79e82c9855edf4144107ca9e38a2c22df624bad9590e5da51329d29b9e'},
    'progress_receipt': {'path': P+'epoch25/runs/engineering/progress.jsonl', 'bytes': 256901,
        'sha256': 'd9683b391c24cf6ca62e3de885bea1d6b3bcd84ac6edf70b6960d8f5bbd96b35'},
}
ACCEPTANCE_REF = {'path': P+'audit/epoch25/acceptance-rejection.json', 'bytes': 15321,
    'sha256': '80b11b77692c70a873ca08204776b8fb3a52936138d7ae2e40f11ba06158c047'}
RAW_ALIASES = {
    'BGE_initializations': 'BGE_initializations_completed',
    'BGE_forwards': 'BGE_forwards_completed',
    'BGE_texts': 'BGE_texts_completed',
    'native_index_initializations': 'native_indexes_completed',
    'native_searches_completed': 'native_queries_completed',
    'native_engineering_batches': 'native_helper_starts',
    **{key: key for key in common.AUTHOR_NLI_COUNTERS},
    **{key: key for key in common.ZERO_COUNTERS},
}
EXTRA_RAW_ZERO_COUNTERS = ('Node_network_operations_attempted', 'external_API_calls',
    'benchmark_corpus_reads', 'benchmark_label_reads', 'train_calls', 'dev_calls',
    'calibration_calls')
REJECTION_ZERO_COUNTERS = tuple(key for key in common.ZERO_COUNTERS if key != NETWORK)


def _clone(function, substitutions):
    globals_copy = dict(function.__globals__)
    globals_copy.update(substitutions)
    answer = types.FunctionType(function.__code__, globals_copy, function.__name__,
                                function.__defaults__, function.__closure__)
    answer.__kwdefaults__ = function.__kwdefaults__
    return answer


_frozen_manifest_checks = _clone(common.check_final_manifest,
    {'ZERO_COUNTERS': REJECTION_ZERO_COUNTERS})


def check_rejected_manifest(manifest, plan):
    common.require(manifest.get('engineering_qualified') is False,
                   'Rejection publisher cannot publish a qualified engineering run')
    actual = manifest.get('actual_execution', {})
    common.require(type(actual.get(NETWORK)) is int and actual[NETWORK] == 1,
                   'Rejection publisher must preserve the exact observed offline attempt=1')
    common.require(type(actual.get('errors')) is int and actual['errors'] >= 1,
                   'Rejected process errors must remain explicit and nonzero')
    return _frozen_manifest_checks(manifest, plan)


def validate_rejected_documents(raw, outer, progress, actual, acceptance):
    """Validate measured documents without interpreting or recomputing scores."""
    require = common.require
    require(raw.get('epoch') == 25 and raw.get('status') == 'FAILED_ENGINEERING_PROCESS'
            and raw.get('accuracy') is None and raw.get('proper_scores') is None
            and raw.get('benchmark_results') is None
            and raw.get('roles_used') == frozen_stage.ROLES,
            'Exact failed raw status and empty benchmark scope required')
    require(outer.get('epoch') == 25 and outer.get('phase') == 'engineering'
            and outer.get('status') == 'WORKER_FAILED_OR_TIMEOUT'
            and type(outer.get('exit_code')) is int and outer['exit_code'] == 2
            and outer.get('uncertain_start') is False
            and outer.get('owned_live_processes_closed') is True
            and outer.get('owned_live_group_members') == []
            and outer.get('cleanup_errors') == []
            and outer.get('allowed_further_epoch25_workers') == 0,
            'Exact failed outer receipt/exit2/process closure required')
    require(acceptance.get('engineering_qualified') is False
            and acceptance.get('status') == 'REJECTED_AUTHORED_ENGINEERING_QUALIFICATION'
            and acceptance.get('benchmark_accepted') is False
            and acceptance.get('champion_promoted') is False,
            'Unchanged independent rejection verdict required')
    counters = raw.get('counters')
    require(isinstance(counters, dict), 'Raw explicit counter object required')
    for name in common.ZERO_COUNTERS + EXTRA_RAW_ZERO_COUNTERS:
        expected = 1 if name == NETWORK else 0
        require(type(counters.get(name)) is int and counters[name] == expected,
                'Raw forbidden counter differs: ' + name)
    for name, source in RAW_ALIASES.items():
        require(type(actual.get(name)) is int and type(counters.get(source)) is int
                and actual[name] == counters[source],
                'Actual counter is not its unchanged raw source: ' + name)
    for key, expected in (('NLI_model_initializations', 1),
                          ('NLI_forward_pairs_attempted', 18),
                          ('NLI_forward_pairs_completed', 18),
                          ('NLI_forwards', 18), ('native_queries_completed', 6)):
        require(type(counters.get(key)) is int and counters[key] == expected,
                'This rejection publisher covers only the measured incident: ' + key)
    for name, source in (('NLI_model_initializations_completed','NLI_model_initializations'),
                         ('NLI_forward_calls_attempted','NLI_forward_pairs_attempted'),
                         ('NLI_forward_calls_completed','NLI_forward_pairs_completed')):
        require(type(counters.get(name)) is int and counters[name] == counters[source],
                'Raw decoder attempt/completion alias differs: ' + name)
    errors = raw.get('errors')
    require(isinstance(errors, list) and errors
            and any(row.get('type') == 'ValueError'
                    and row.get('message') == 'Forbidden operation counter nonzero'
                    for row in errors)
            and type(actual.get('errors')) is int and actual['errors'] == len(errors),
            'Raw process failure and exact error count required')
    for actual_key, outer_key in (('worker_attempts','worker_attempts_reserved'),
                                 ('verified_worker_starts','verified_worker_starts')):
        require(type(actual.get(actual_key)) is int
                and type(outer.get(outer_key)) is int
                and actual[actual_key] == outer[outer_key] == 1,
                'Worker observation differs from the unchanged outer receipt')
    require(actual.get('owned_live_processes_closed') is outer['owned_live_processes_closed']
            and actual.get('CPU_affinity') == outer.get('CPU_affinity') == [0, 1]
            and actual.get('wall_seconds_including_init_cleanup')
                == outer.get('wall_seconds_including_init_cleanup'),
            'Actual process resources differ from the unchanged outer receipt')
    refusals = [row for row in progress
                if isinstance(row.get('event'), dict)
                and row['event'].get('event') == 'OFFLINE_NETWORK_REFUSAL']
    require(len(refusals) == 1 and refusals[0]['event'] ==
            {'event':'OFFLINE_NETWORK_REFUSAL','audit_event':'socket.bind'}
            and type(refusals[0].get('counters',{}).get(NETWORK)) is int
            and refusals[0]['counters'][NETWORK] == 1
            and refusals[0].get('worker_pid') == raw.get('worker_pid')
                == outer.get('Popen_returned_pid'),
            'Exactly one matching nested socket.bind offline refusal required')
    return True


def validate_rejected_provenance(project, manifest, checkpoint):
    require = common.require
    provenance = manifest.get('rejected_execution_provenance')
    fields = set(INCIDENT_REFS) | {'reason','publication_scope','audit_event',
                                  'attempted_operations','destination_and_initiator'}
    require(isinstance(provenance, dict) and set(provenance) == fields
            and isinstance(provenance.get('reason'), str) and provenance['reason'].strip()
            and provenance.get('publication_scope') == PUBLICATION_SCOPE
            and provenance.get('audit_event') == 'socket.bind'
            and type(provenance.get('attempted_operations')) is int
            and provenance['attempted_operations'] == 1
            and provenance.get('destination_and_initiator') == 'NOT_RECORDED',
            'Explicit adverse rejection-only publication provenance required')
    for key, identity in INCIDENT_REFS.items():
        require(provenance[key] == identity, 'Measured incident receipt identity changed: ' + key)
        frozen_stage.checked_ref(project, provenance[key], checkpoint, identity['path'])
    raw = common.parse(project / INCIDENT_REFS['raw_receipt']['path'])
    outer = common.parse(project / INCIDENT_REFS['outer_receipt']['path'])
    progress = [json.loads(line) for line in common.content(
        project / INCIDENT_REFS['progress_receipt']['path']).decode('utf-8').splitlines()]
    require(outer.get('raw_bytes') == INCIDENT_REFS['raw_receipt']['bytes']
            and outer.get('raw_sha256') == INCIDENT_REFS['raw_receipt']['sha256'],
            'Outer receipt does not bind the unchanged failed raw bytes')
    acceptance_ref = manifest.get('acceptance_report')
    require(acceptance_ref == ACCEPTANCE_REF,
            'Original independent rejection-report identity changed')
    frozen_stage.checked_ref(project, acceptance_ref, checkpoint,
                             frozen_stage.FINAL_REFS['acceptance_report'])
    acceptance = common.parse(project / acceptance_ref['path'])
    validate_rejected_documents(raw, outer, progress, manifest['actual_execution'], acceptance)
    return provenance


_frozen_final_evidence = _clone(frozen_stage.checked_final_evidence,
    {'check_final_manifest': check_rejected_manifest})


def _checked_rejected_final_evidence(project, cont, old_cont, checkpoint, parent, plan):
    manifest = common.parse(project / (P+'epoch25/EPOCH_MANIFEST.json'))
    validate_rejected_provenance(project, manifest, checkpoint)
    return _frozen_final_evidence(project, cont, old_cont, checkpoint, parent, plan)


_checked_controls = _clone(frozen_stage.checked_controls,
    {'checked_final_evidence': _checked_rejected_final_evidence})
_prepare = _clone(frozen_stage.prepare, {'checked_controls': _checked_controls})


def prepare_rejected(args):
    common.require(args.mode == 'final', 'Rejection v2 permits only a final rejected publication')
    verify_frozen_helpers()
    answer = _prepare(args)
    answer['publication_scope'] = PUBLICATION_SCOPE
    answer['offline_attempts_preserved'] = 1
    answer['qualification_retroactively_changed'] = False
    return answer
