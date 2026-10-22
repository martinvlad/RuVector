"""Read-only metadata and saved TRAIN/DEV analysis consistency review."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json

O = Path(__file__).resolve().parent
S = O.parents[1]
P = S.parents[1]
def obj(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p): return [json.loads(x) for x in p.read_text().splitlines() if x]
r = obj(O/'actual-independent-v1.json')
e = obj(S/'epoch8/EPOCH_MANIFEST.json')
u = obj(S/'epoch8/USED_IDENTITIES.json')
l = obj(S/'epoch8/REJECTION_LEDGER.json')
old = obj(S/'epoch7/REJECTION_LEDGER.json')
assert r['checks_passed'] and r['DEV_gate_passed'] and r['confirmation_consumed']
assert not r['internal_confirmation_gate_passed']
assert e['status'] == 'REJECTED_CONFIRMATION_GATE'
assert e['actual_results']['metrics'] == r['metrics']
for key in ('resources','completion'):
    assert e['actual_results'][key] == r[key]
for phase in ('development','confirmation'):
    engine=obj(S/'epoch8/project/experiments/sota-2026-10-22/epoch8/runs'/phase/'final-engine.json')
    assert e['actual_results']['actual_execution_counters'][phase] == engine['execution_after_close']['counters']
assert e['actual_results']['successful_HTTP'] == 192
assert e['actual_results']['training_feature_HTTP'] == 72
assert e['actual_results']['DEV_n'] == 24
assert e['confirmation_requests_completed'] == e['confirmation_requests_started'] == 96
assert e['confirmation_consumed'] and not e['internal_confirmation_gate_passed']
assert e['runtime_admission'] == r['runtime_admission']
assert e['budget']['lifetime_native_attempts'] == 11
assert e['budget']['this_epoch_native_attempts'] == 2
assert e['budget']['allowed_further_attempts_in_closed_study'] == 0
assert e['budget']['paid_calls'] == e['budget']['GPU_calls'] == 0
assert e['official_rank'] is None and e['official_score'] is None and not e['SOTA_established']
assert l['rejections'][:-1] == old['rejections']
assert l['rejections'][-1]['epoch'] == 8
assert l['rejections'][-1]['status'] == e['status']
assert l['epoch8_budget'] == e['budget']
assert sha(S/'epoch8/USED_IDENTITIES.json') == e['used_identities_sha256']
for role, expected in [('train',72),('development',24)]:
    v = u['source_frozen_joint_roles'][role]
    source = P/v['path']
    assert sha(source) == v['sha256']
    data = rows(source)
    assert len(data) == expected == v['declared_queries'] == v['requests_started'] == v['requests_completed']
    assert v['ids'] == [x['id'] for x in data]
    assert v['input_sha256'] == [x['input_sha256'] for x in data]
    assert v['source_groups'] == sorted({x['source_group'] for x in data})
    assert len(v['source_groups']) == v['document_groups'] == expected//3
cf = u['confirmation']
assert cf['queries'] == cf['requests_started'] == cf['requests_completed'] == 96
assert cf['document_groups'] == 32 and cf['retired_conservatively']
assert cf['model_consumed_per_independent_report']
assert u['fresh_officialtrain_groups_remaining'] == 274
assert u['joint32groups_retired_even_ifpartial']
checked=[]
def check_refs(value):
    if isinstance(value, dict):
        if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):
            target=P/value['path']
            if target.is_file():
                assert sha(target)==value['sha256'],str(target)
                checked.append(value['path'])
        for child in value.values(): check_refs(child)
    elif isinstance(value,list):
        for child in value: check_refs(child)
check_refs(e)
base=S/'candidate/epoch8/postrun'
assert (O/'postrun-diagnostic-replay-v1.json').read_bytes() == (base/'dev-diagnostic-v1.json').read_bytes()
a=obj(O/'postrun-findings-replay-v1.json');b=obj(base/'dev-findings-v1.json')
a['diagnostic_input']['filename']=b['diagnostic_input']['filename']
assert a == b
d=obj(base/'dev-diagnostic-v1.json')
assert d['train_completed']==72 and d['DEV_completed']==24
assert d['new_model_calls']==d['new_native_calls']==d['new_optimizer_fits']==0
assert not d['frozen_sources_modified']
assert not d['unused_confirmation_labels_inspected']
assert len(d['DEV_cases'])==24 and len(d['train_cases'])==72
assert all(x['id'].startswith('original-contractnli:train:epoch8:') for x in d['DEV_cases']+d['train_cases'])
proof={
 'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,
 'epoch_manifest_sha256':sha(S/'epoch8/EPOCH_MANIFEST.json'),
 'used_identities_sha256':sha(S/'epoch8/USED_IDENTITIES.json'),
 'rejection_ledger_sha256':sha(S/'epoch8/REJECTION_LEDGER.json'),
 'actual_independent_sha256':sha(O/'actual-independent-v1.json'),
 'prior_ledger_rows_preserved':len(old['rejections']),
 'metadata_file_references_verified':sorted(set(checked)),
 'actual_HTTP':{'TRAIN':72,'DEV':24,'CONF':96,'total':192},
 'actual_attempts':{'prior_closed':9,'epoch8':2,'lifetime':11,'remaining_closed_study':0},
 'source_exposure':{'TRAIN_groups_retired':24,'DEV_groups_retired':8,'CONF_groups_retired':32,
                    'confirmation96_now_exposed_forever':True,'verified_unused_confirmation_remaining':False,
                    'official_train_source_pool_remaining':274},
 'postrun_candidate_review':{'diagnostic_sha256':sha(base/'dev-diagnostic-v1.json'),
  'findings_sha256':sha(base/'dev-findings-v1.json'),'diagnostic_rebuilt_byte_identical':True,
  'findings_rebuilt_equal_except_audited_input_basename':True,
  'inputs_only_completed_TRAIN_DEV_and_terminal_aggregate':True,
  'annotation_numeric_coverage_is_mechanical_not_sufficiency':True,
  'one_future_hypothesis_is_unimplemented_unmeasured':True,
  'raw_readout_references_predeclared_nongating':True},
 'result':'REJECTED_CONFIRMATION_GATE; DEV gain did not transfer to stronger matched/Native104 controls',
 'promotion':False,'official_score':None,'official_rank':None,'SOTA_established':False,
 'model_native_paid_calls':0}
out=O/'metadata-independent-v1.json'
with out.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'output':str(out),'sha256':sha(out)}))
