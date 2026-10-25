"""Postmeasurement failure-only metadata; never an evaluator or label reader."""
import sys
sys.dont_write_bytecode = True
import argparse, copy, hashlib, json, math, os
from pathlib import Path

KIND = 'REAL_FINFACT_DEV_TRANSFER_PILOT'
BASE = '74dbbcb10508ced7e0edf53a0c736f14c19a19a1'
SOURCE = 'e06515a7dc493bfa9869d9e7a4b27c348bb32603'
PLAN_SHA = 'd7942147b0b15d47ee220d19fb05f3a5c55b977f6140e8b1acba96dbe8ee8bcc'
P = 'experiments/sota-2026-10-22/'
E = P + 'epoch39/'
A = P + 'audit/epoch39/'
ARMS = ['b354_source_order', 'b354_native', 'b354_lexical', 'xxlarge_source_order']
CONTROLS = ['b354_source_order', 'b354_lexical', 'xxlarge_source_order']
FLAGS = {'benchmark_accepted': False, 'champion_promoted': False, 'new_submission': False,
         'official_SOTA_verified': False, 'official_rank': None, 'benchmark_generalization_claim': False}
PATHS = {'plan': E+'plan.json', 'source_admission': E+'SOURCE_ADMISSION.json',
         'raw': E+'runs/dev/raw.json', 'execution': E+'runs/dev/execution.json',
         'observer': E+'SUPERVISOR_OBSERVED_CLOSURE.json',
         'physical_closure': A+'actual-physical-closure-independent-v1.json',
         'gold_admission': E+'GOLD_READ_ADMISSION.json',
         'gold_join_report': E+'runs/dev/GOLD_JOIN_REPORT.json',
         'independent_custody_failure': A+'actual-custody-failure-independent-v1.json',
         'source_representation_finding': A+'LABEL_REPRESENTATION_SOURCE_FINDING.v2.json'}
for _i in range(2):
    for _side in ('before', 'after'):
        PATHS[f'progress_{_i:02d}_{_side}'] = E+f'runs/dev/progress-{_i:02d}-{_side}.json'
OUT = A+'qualification-replay.json'


def require(value, message):
    if not value:
        raise ValueError(message)


def same(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(same(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return left == right


def loads(body):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, 'DUPLICATE_JSON_KEY'); out[key] = value
        return out
    def forbidden(_):
        raise ValueError('NONFINITE_JSON')
    value = json.loads(body, object_pairs_hook=unique, parse_constant=forbidden)
    def finite(x):
        if isinstance(x, float): require(math.isfinite(x), 'NONFINITE_JSON')
        elif isinstance(x, dict):
            for child in x.values(): finite(child)
        elif isinstance(x, list):
            for child in x: finite(child)
    finite(value)
    return value


def public_path(root, relative):
    p = Path(relative)
    require(not p.is_absolute() and '..' not in p.parts and '\\' not in relative, 'PUBLIC_RELATIVE_PATH_REQUIRED')
    result = (root/p).resolve()
    require(result.is_relative_to(root.resolve()), 'NO_EXTERNAL_ASSET_ACCESS')
    return result


def read_ref(root, row):
    require(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'} and type(row['bytes']) is int, 'EXACT_PUBLIC_REFERENCE_REQUIRED')
    body = public_path(root, row['path']).read_bytes()
    require(len(body) == row['bytes'] and hashlib.sha256(body).hexdigest() == row['sha256'], 'PUBLIC_EVIDENCE_HASH_CHANGED')
    return loads(body)


def envelope(doc):
    require(doc.get('epoch') == 39 and doc.get('kind') == KIND and doc.get('phase') == 'dev', 'E39_DEV_METADATA_REQUIRED')


def quantile(values, q):
    require(values and all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in values), 'FINITE_RECORDED_TIMINGS_REQUIRED')
    ordered = sorted(values); pos = (len(ordered)-1)*q; lo = int(pos); hi = min(lo+1, len(ordered)-1)
    return ordered[lo] + (ordered[hi]-ordered[lo])*(pos-lo)


def timing_summary(raw):
    keys = ('pair_tokenization_seconds', 'NNI_forward_seconds', 'reader_total_seconds', 'context_order_seconds', 'native_query_seconds')
    out = {}
    for arm in ARMS:
        rows = [case['readouts'][arm]['timing'] for case in raw['cases']]
        out[arm] = {key: {'N': len(rows), 'p50': quantile([r[key] for r in rows], .5),
                         'p95': quantile([r[key] for r in rows], .95)} for key in keys}
        out[arm]['retained_recorded_scope'] = sorted({r['scope'] for r in rows})
    return {'per_arm': out, 'quantile_method': 'linear interpolation at (N-1)*q',
            'scope': 'Descriptive timing metadata from public raw48 only; per-readout components exclude some initialization/cleanup and are not independent whole-batch replicates. Reused context/query components are not summed.',
            'worker_wall_seconds': raw['wall_seconds']}


def assemble(protocol, docs):
    require(protocol.get('epoch') == 39 and protocol.get('kind') == KIND and protocol.get('postmeasurement_metadata_only') is True, 'FAILURE_ONLY_PROTOCOL_REQUIRED')
    require(same(protocol.get('root_reported_EVALUATE_invocations'), 0), 'NO_EVALUATE_REPAIR_OR_REPLAY')
    require(set(docs) == set(PATHS), 'EXACT_PUBLIC_METADATA_INPUT_SET')
    plan = docs['plan']; raw = docs['raw']; execution = docs['execution']; gold = docs['gold_join_report']
    for name, doc in docs.items():
        if name != 'source_representation_finding': envelope(doc)
    finding = docs['source_representation_finding']
    require(finding.get('epoch') == 39 and finding.get('kind') == KIND and finding.get('phase') == 'source_contract_audit_after_closed_run', 'SOURCE_ONLY_REPRESENTATION_FINDING')
    custody = docs['independent_custody_failure']
    require(custody['checks_passed'] is True and custody['scientific_evaluation_executed'] is False and same(custody['semantic_label_tokens_decoded'], 2) and custody['semantic_decode_count_uncertain'] is False, 'INDEPENDENT_FAILURE_METADATA_REQUIRED')
    require(plan['source_checkpoint'] == BASE and len(plan['pins']) == 354 and plan['arms'] == ARMS, 'FROZEN_PLAN_REQUIRED')
    ids = plan['data_roles']['dev']; require(len(ids) == 12 and len(set(ids)) == 12, 'FROZEN_TWELVE_IDS_REQUIRED')
    require(docs['source_admission']['published_source_commit'] == SOURCE and docs['source_admission']['verified_actual_remote_readback'] is True, 'ACTUAL_SOURCE_REQUIRED')
    for name in ('raw', 'execution'):
        require(docs[name]['plan_sha256'] == PLAN_SHA, 'FROZEN_PLAN_MISMATCH')
    require(raw['status'] == 'DEV_FORECASTS_COMPLETE_NO_GOLD' and raw['errors'] == [] and len(raw['cases']) == 12, 'COMPLETE_NO_GOLD_FORECASTS_REQUIRED')
    require([c['id'] for c in raw['cases']] == ids, 'ALL_TWELVE_FORECAST_CASES_RETAINED')
    expected_ids = {case+'::'+arm for case in ids for arm in ARMS}
    require(len(raw['completed_readout_ids']) == 48 and set(raw['completed_readout_ids']) == expected_ids and set(raw['required_readout_ids']) == expected_ids, 'FORTY_EIGHT_UNIQUE_READOUTS_REQUIRED')
    require(all(set(case['readouts']) == set(ARMS) for case in raw['cases']), 'FOUR_PHYSICAL_ARMS_REQUIRED')
    counters = raw['counters']; expected = plan['expected_operation_counters']['dev']
    require(all(same(counters.get(k), v) for k, v in expected.items()), 'CAPTURED_FIXED_COUNTERS_REQUIRED')
    require(same(execution['raw_operation_counters'], counters) and execution['operation_counts_complete'] is True, 'ACTUAL_COMPLETE_COUNTERS_REQUIRED')
    require(execution['status'] == 'WORKER_COMPLETED' and execution['exit_code'] == 0 and execution['verified_worker_starts'] == 1 and execution['worker_popen_attempts'] == 1 and execution['uncertain_start'] is False and execution['owned_live_processes_closed'] is True, 'KNOWN_CLOSED_ONE_WORKER_REQUIRED')
    require(raw['closure_facts']['native_child_closed'] is True and raw['closure_facts']['model_profiles_disposed'] == ['xxlarge', 'b354'], 'BOTH_MODELS_AND_NATIVE_CLOSED')
    for name in ('observer', 'physical_closure'):
        require(docs[name]['physical_closure_passed'] is True and docs[name]['source_plan_sha256'] == PLAN_SHA, 'INDEPENDENT_PHYSICAL_CLOSURE_REQUIRED')
    require(docs['observer']['unknown_physical_ownership'] is False and docs['observer']['observed_supervisor_exit_wait_status'] == 0, 'KNOWN_SUCCESSFUL_SUPERVISOR_REQUIRED')
    require(docs['physical_closure']['checks_passed'] is True and docs['physical_closure']['frozen_pins_verified_unchanged'] == 354, 'FROZEN_SOURCE_INDEPENDENTLY_PRESERVED')
    require(gold['status'] == 'GOLD_JOIN_FAILED_FINAL_NO_RETRY' and gold['source_plan_sha256'] == PLAN_SHA, 'EXACT_FAILED_GOLD_CUSTODY_REQUIRED')
    require(same(gold['semantic_labels_decoded'], 2) and same(gold['decode_attempted_tokens'], 2) and gold['semantic_decode_count_uncertain'] is False and gold['label_reader_calls'] == 1, 'EXACT_TWO_CERTAIN_DECODES_REQUIRED')
    require(gold['errors'] == ['ValueError:UNSUPPORTED_OFFICIAL_LABEL_NO_REMAP'] and 'joined_labels' not in gold, 'NO_REMAP_OR_JOINED_LABELS')
    require(gold['original_archive_gold_traversals'] == 0 and gold['model_tokenizer_native_calls'] == 0 and gold['used_confirmation_identities'] == [], 'NO_ADDITIONAL_GOLD_OR_MODEL_WORK')
    for i in range(2):
        before = docs[f'progress_{i:02d}_before']; after = docs[f'progress_{i:02d}_after']
        require(set(before) == {'schema_version','epoch','kind','phase','caseid','previous_semantic_decodes','token_sha256','decode_started','decode_completed'}, 'PROGRESS_METADATA_ONLY')
        require(set(after) == {'schema_version','epoch','kind','phase','caseid','semantic_decodes_completed','decode_completed','supported_literal'}, 'PROGRESS_METADATA_ONLY')
        require(before['caseid'] == after['caseid'] == ids[i] and same(before['previous_semantic_decodes'], i) and same(after['semantic_decodes_completed'], i+1), 'ORDERED_PROGRESS_PAIR_REQUIRED')
        require(before['decode_started'] is True and before['decode_completed'] is False and after['decode_completed'] is True and after['supported_literal'] is (i == 0), 'EXACT_RECORDED_UNSUPPORTED_SECOND_TOKEN')
    gates = {k: 'NOT_EVALUATED' for k in ('integrity_complete_no_errors','all_four_full_N12','primary_gain_at_least_two_correct_vs_XXL')}
    for control in CONTROLS:
        for suffix in ('accuracy_nondecrease','official_macroF1_nondecrease','Brier_nonincrease','stable_unclipped_NLL_nonincrease'):
            gates[control+':'+suffix] = 'NOT_EVALUATED'
    actual = {'owned_live_processes_closed': True, 'worker_attempts': 1,
              'known_corpus_batches_attempted_at_last_capture': 1, 'known_corpus_batches_completed_at_last_capture': 1,
              'actual_NLI_forwards': 48, 'native_queries': 12, 'operation_counts_complete': True,
              'raw_operation_counters': copy.deepcopy(counters), 'uncertain_start': False,
              'worker_exit_code': 0, 'supervisor_exit_wait_status': 0,
              'wall_seconds_including_init_cleanup': execution['wall_seconds_including_init_cleanup'],
              'largest_child_peak_RSS_bytes': execution['largest_child_peak_RSS_bytes']}
    return {'schema_version':1,'epoch':39,'kind':KIND,'phase':'dev','source_checkpoint':BASE,'source_commit':SOURCE,
            'source_plan_sha256':PLAN_SHA,'status':'REJECTED_DEV_INTEGRITY','checks_passed':False,'dev_passed':False,
            'evaluation_executed':False,'frozen_scorer_EVALUATE_invocations':0,
            'frozen_full_input_quality_audit_executed':False,
            'failure_only_postmeasurement_metadata':True,'not_frozen_candidate_or_scoring_source':True,
            'evaluation_not_executed_reason':'Once-only gold custodian stopped after its second semantic decode on unsupported frozen literal; no joined-label artifact exists in its report. Frozen scorer pins missing joined artifact before its try block. EVALUATE was not invoked; no retries/remapping/remaining label decodes authorized.',
            'benchmark_accuracy':None,'official_eligibility':'HOLD','model_selection_lineage':'HOLD',
            'used_confirmation_identities':[],'data_roles':copy.deepcopy(plan['data_roles']),
            'actual_NLI_forwards':48,'all_cases_retained_denominator':12,'metrics':None,
            'quality_metrics':{arm:{key:None for key in ('accuracy','correct','macro_F1','Brier','NLL')} for arm in ARMS},
            'gate_checks':gates,'scoring_gates_evaluated':False,'paired_control_comparisons':None,
            'source_representation_contract':'Author anli.py retains raw gold unchanged; a canonical source-gold codec was not established before this run. No unsupported literal is inspected, exposed or remapped here.',
            'actual_execution':actual,'timing_metadata':timing_summary(raw),
            'resource_metadata':{'raw_worker':copy.deepcopy(raw['resources']),
                                 'supervisor_children_user_seconds':execution['children_user_seconds'],
                                 'supervisor_children_system_seconds':execution['children_system_seconds'],
                                 'memory_scope':'Separate recorded high-water observations; never sum as simultaneous RSS.'},
            'label_custody':{'semantic_label_decodes':2,'remaining_selected_tokens_opaque':10,
                             'semantic_decode_count_uncertain':False,'join_reader_calls':1,
                             'scorer_original_oracle_reads':0,'scorer_retained_join_reads':0,
                             'additional_decode_retry_or_remap_authorized':False},
            'errors':copy.deepcopy(gold['errors']), 'evidence':copy.deepcopy(protocol['references']),
            'limitations':['No quality score or acceptance gate was evaluated. All twelve selected cases remain DEV forever; no fresh confirmation or promotion.','Accuracy/Brier/NLL and full-benchmark/generalization claims remain unavailable. Existing E37 cumulative model/corpus unknowns are not repaired.'],**FLAGS}


def run(args):
    root = Path(args.project).resolve()
    require(root == Path('/tmp/ruvector-sota-2026-10-22/epoch39-74dbbcb10508/project'), 'EXACT_CURRENT_PROJECT_REQUIRED')
    body = Path(args.protocol).read_bytes()
    require(hashlib.sha256(body).hexdigest() == args.expected_protocol_sha256, 'REVIEWED_PROTOCOL_REQUIRED')
    protocol = loads(body); refs = protocol['references']
    require(set(refs) == set(PATHS) and all(refs[k]['path'] == v for k,v in PATHS.items()), 'EXACT_PUBLIC_PATH_ALLOWLIST')
    require(refs['plan']['sha256'] == PLAN_SHA, 'FROZEN_PLAN_HASH_REQUIRED')
    docs = {name: read_ref(root, row) for name,row in refs.items()}
    # Frozen public source rehash only; never follow external_data_assets/evidence.
    for row in docs['plan']['pins']:
        require(isinstance(row,dict) and set(row)=={'path','bytes','sha256'}, 'FROZEN_SOURCE_REFERENCE_REQUIRED')
        file = public_path(root,row['path']); data=file.read_bytes()
        require(len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'], 'FROZEN_SOURCE_CHANGED')
    require(set(p.name for p in (root/(E+'runs/dev')).glob('progress-*.json')) == {Path(PATHS[k]).name for k in PATHS if k.startswith('progress_')}, 'NO_MORE_LABEL_PROGRESS_AUTHORIZED')
    result = assemble(protocol, docs); output = public_path(root, args.out)
    require(args.out == OUT and not output.exists(), 'ONCE_ONLY_CANONICAL_NEW_REJECTION_OUTPUT')
    data = (json.dumps(result,indent=2,allow_nan=False)+'\n').encode()
    with output.open('xb') as target:
        target.write(data); target.flush(); os.fsync(target.fileno())
    fd=os.open(output.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    return {'status':result['status'],'evaluation_executed':False,'metrics':None,
            'output':{'path':args.out,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}}


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--project',required=True)
    parser.add_argument('--protocol',required=True);parser.add_argument('--expected-protocol-sha256',required=True)
    parser.add_argument('--out',default=OUT)
    print(json.dumps(run(parser.parse_args()),allow_nan=False))
