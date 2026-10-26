"""E46 inert public identity metadata fixtures and static admission-order checks.

Loads only the standalone metadata validator. No common.admit, Node, native,
BGE, tokenizer, reader, model, DATA or Gold function is imported or called.
Run into a new outside-project --out path; this never modifies a frozen plan.
"""
import argparse,ast,copy,hashlib,importlib.util,json,os
from pathlib import Path
VALIDATOR_SHA='4865449fd60d0b490cd42a3f1791c08407c26ecda6385645ac3d095697bc709e'
OLD_PLAN_SHA='577b93192b06bc3123926bc80a832b9f9eefa3991bdffdd155d6c40c5b4fb176'
P='experiments/sota-2026-10-22/'

def require(value,code):
    if not value:raise AssertionError(code)
def sha(b):return hashlib.sha256(b).hexdigest()
def public_file(path):
    p=Path(path);require(p.is_absolute()and p.resolve()==p and 'private'not in p.parts and not any(q.is_symlink()for q in(p,*p.parents)),'PUBLIC_REGULAR_PATH');require(p.is_file(),'PUBLIC_FILE_REQUIRED');return p

def main(a):
    project=Path(a.public_project);require(project.is_absolute()and project.resolve()==project,'PUBLIC_PROJECT_PATH')
    file=public_file(project/P/'runtime/epoch46/native_plan_contract.py');raw=file.read_bytes();require(sha(raw)==VALIDATOR_SHA,'STANDALONE_METADATA_VALIDATOR_HASH')
    spec=importlib.util.spec_from_file_location('e46_inert_metadata_contract',file);V=importlib.util.module_from_spec(spec);exec(compile(raw,str(file),'exec'),V.__dict__)
    old_file=public_file(a.historical_plan);old_raw=old_file.read_bytes();require(len(old_raw)==23409 and sha(old_raw)==OLD_PLAN_SHA,'ACTUAL_E45_FROZEN_PUBLIC_PLAN')
    old=json.loads(old_raw);fragment=json.loads(public_file(a.interface).read_text())['plan_fields'];proposed=copy.deepcopy(old)
    proposed.update({k:copy.deepcopy(fragment[k])for k in ['dev_document_ids','dev_hypothesis_ids','data_roles','case_ids_by_document']})
    require(set(proposed)-set(old)=={'case_ids_by_document'}and all(proposed[k]==old[k]for k in old),'IDENTITY_PROPOSAL_ONLY_ONE_ADDED_FIELD')
    calls=0
    def outcome(value):
        nonlocal calls
        calls+=1
        try:return {'checks_passed':True,'result':V.validate_native_plan_contract(value)}
        except V.ContractError as error:return {'checks_passed':False,'error_code':str(error)}
    before=outcome(old);require(before=={'checks_passed':False,'error_code':'MISSING_FROZEN_CASE_IDS_BY_DOCUMENT'},'ACTUAL_OLD_MISSING_FIELD_OBSERVED')
    after=outcome(proposed);require(after['checks_passed']is True and after['result']['target_calls']==0 and after['result']['execution_authorized']is False,'CORRECTED_IDENTITY_METADATA_PASSES')
    negatives=[]
    def reject(name,edit):
        value=copy.deepcopy(proposed);edit(value);result=outcome(value);require(result['checks_passed']is False,name);negatives.append(dict(name=name,expected_rejection_observed=True,**result))
    reject('missing_map',lambda p:p.pop('case_ids_by_document'))
    reject('boolean_document_id',lambda p:p['dev_document_ids'].__setitem__(0,True))
    reject('float_document_id',lambda p:p['dev_document_ids'].__setitem__(0,357.0))
    reject('negative_document_id',lambda p:p['dev_document_ids'].__setitem__(0,-357))
    reject('unsafe_JS_document_id',lambda p:p['dev_document_ids'].__setitem__(0,2**53))
    reject('duplicate_document_id',lambda p:p['dev_document_ids'].__setitem__(1,357))
    reject('reordered_document_ids',lambda p:p['dev_document_ids'].reverse())
    reject('reordered_hypotheses',lambda p:p['dev_hypothesis_ids'].reverse())
    reject('reordered_DEV_cases',lambda p:p['data_roles']['dev'].reverse())
    reject('duplicate_DEV_case',lambda p:p['data_roles']['dev'].__setitem__(1,p['data_roles']['dev'][0]))
    reject('foreign_case_identity',lambda p:p['data_roles']['dev'].__setitem__(0,'contractnli:eced6528:test:62:nda-1'))
    reject('noncanonical_decimal_case',lambda p:p['data_roles']['dev'].__setitem__(0,'contractnli:eced6528:test:0357:nda-1'))
    reject('nonstring_case',lambda p:p['data_roles']['dev'].__setitem__(0,357))
    reject('map_has_extra_document',lambda p:p['case_ids_by_document'].__setitem__('62',[]))
    reject('map_missing_document',lambda p:p['case_ids_by_document'].pop('357'))
    reject('map_nonstring_key',lambda p:p['case_ids_by_document'].__setitem__(357,p['case_ids_by_document'].pop('357')))
    reject('map_reordered_queries',lambda p:p['case_ids_by_document']['357'].reverse())
    reject('map_wrong_document_query',lambda p:p['case_ids_by_document']['357'].__setitem__(0,p['case_ids_by_document']['227'][0]))
    reject('map_drops_one_query',lambda p:p['case_ids_by_document']['357'].pop())
    reject('protected_confirmation_role',lambda p:p['data_roles']['confirmation'].append('contractnli:eced6528:test:62:nda-1'))
    common=ast.parse(public_file(project/P/'runtime/epoch46/common.py').read_text());admit=next(n for n in common.body if isinstance(n,ast.FunctionDef)and n.name=='admit')
    raw_validate=[n for n in ast.walk(admit)if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and isinstance(n.func.value,ast.Name)and n.func.value.id=='native_contract'and n.func.attr=='validate_native_plan_contract']
    node_verify=[n for n in ast.walk(admit)if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and isinstance(n.func.value,ast.Name)and n.func.value.id=='node_guard'and n.func.attr=='verify']
    require(len(raw_validate)==len(node_verify)==1 and len(raw_validate[0].args)==1 and isinstance(raw_validate[0].args[0],ast.Name)and raw_validate[0].args[0].id=='p'and raw_validate[0].lineno<node_verify[0].lineno,'RAW_P_CONTRACT_BEFORE_NODE_GUARD')
    worker=ast.parse(public_file(project/P/'runtime/epoch46/worker.py').read_text());calls_ast=[n for n in ast.walk(worker)if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)]
    admit_line=next(n.lineno for n in calls_ast if isinstance(n.func.value,ast.Name)and n.func.value.id=='C'and n.func.attr=='admit')
    bge_line=next(n.lineno for n in calls_ast if isinstance(n.func.value,ast.Name)and n.func.value.id=='bge'and n.func.attr=='prepare_bundle')
    require(admit_line<bge_line,'FULL_ADMISSION_BEFORE_EMBEDDING_PREPARATION')
    # The Node helper reads raw frozen plan directly; no runtime-view injection is relied on.
    node_text=public_file(project/P/'runtime/epoch46/native_helper.cjs').read_text()
    require('const plan=JSON.parse(fs.readFileSync(process.env.E46_PLAN));configureIdentities(plan);'in node_text and 'plan.case_ids_by_document'in node_text,'NODE_RAW_PLAN_MAP_CONSUMER_PRESERVED')
    require(sha(old_file.read_bytes())==OLD_PLAN_SHA,'OLD_FROZEN_PLAN_UNCHANGED')
    result=dict(schema_version=1,epoch=46,kind=fragment['kind'],source_only=True,checks_passed=True,source_plan_fragment_identity_contract_only=True,actual_E45_frozen_metadata_rejection=before,proposed_identity_metadata_acceptance=after,negative_fixture_count=len(negatives),negative_fixtures=negatives,pure_metadata_validator_function_calls=calls,raw_plan_validated_before_Node_guard=True,admission_precedes_BGE=True,Node_raw_frozen_plan_consumer_preserved=True,actual_final_E46_plan_still_requires_SOURCE_freeze_preflight=True,original_E45_plan_unchanged=True,private_asset_reads=0,target_science_imports_or_calls=0,Node_native_model_tokenizer_version_or_Gold_calls=0,API_calls=0,benchmark_or_candidate_quality_evidence=False,native_ABI_reader_or_model_runtime_established=False,execution_authorized=False,scope='Inert identity metadata plus AST/text ordering checks only. Final source freezer/preflight must separately validate actual final E46 raw plan; this result grants no worker, data, model, Gold, confirmation, promotion or benchmark claim.')
    out=Path(a.out);require(out.is_absolute()and not out.exists(),'NEW_INERT_RESULT_OUTPUT')
    with out.open('x')as f:f.write(json.dumps(result,sort_keys=True,indent=2)+'\n');f.flush();os.fsync(f.fileno())
    print(json.dumps(dict(checks_passed=True,metadata_validator_calls=calls,negative_fixtures=len(negatives),target_science_calls=0),sort_keys=True))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['public-project','historical-plan','interface','out']:parser.add_argument('--'+key,required=True)
    main(parser.parse_args())
