"""Frozen raw-plan identity contract validation; no target imports or execution.

This validates the fixed, permanently exposed twelve-case DEV identity contract.
It does not admit execution, establish ABI/model compatibility or modify a plan.
"""
import argparse
import json
from pathlib import Path
import re

DOCS=(357,227,46,212)
HYPS=('nda-1','nda-10','nda-16')
KIND='REAL_CONTRACTNLI_QWEN_JOINT_CONTEXT_DEV_PILOT'
CASE=re.compile(r'contractnli:eced6528:test:([1-9][0-9]*):(nda-(?:1|10|16))\Z')

class ContractError(ValueError):pass

def require(value,code):
    if not value:raise ContractError(code)

def unique(items):
    out={}
    for key,value in items:
        require(key not in out,'DUPLICATE_JSON_KEY');out[key]=value
    return out

def derive_case_ids_by_document(plan):
    require(type(plan)is dict,'PLAN_OBJECT_REQUIRED')
    docs=plan.get('dev_document_ids');hyps=plan.get('dev_hypothesis_ids')
    require(type(docs)is list and len(docs)==4 and all(type(x)is int and 0<x<2**53 for x in docs)and len(set(docs))==4,'FOUR_UNIQUE_POSITIVE_SAFE_INTEGER_DOCUMENT_IDS')
    require(tuple(docs)==DOCS,'FROZEN_DOCUMENT_ORDER_MISMATCH')
    require(type(hyps)is list and all(type(x)is str for x in hyps)and tuple(hyps)==HYPS,'FROZEN_HYPOTHESIS_ORDER_MISMATCH')
    roles=plan.get('data_roles')
    require(type(roles)is dict and set(roles)=={'train','dev','calibration','confirmation'},'EXACT_DATA_ROLE_KEYS_REQUIRED')
    require(all(type(roles[k])is list and roles[k]==[]for k in ['train','calibration','confirmation']),'ONLY_EXPOSED_DEV_ROLE_ALLOWED')
    cases=roles['dev']
    require(type(cases)is list and len(cases)==12 and all(type(x)is str for x in cases)and len(set(cases))==12,'TWELVE_UNIQUE_ORDERED_CASE_STRINGS_REQUIRED')
    groups={str(doc):[]for doc in docs}
    for case_id in cases:
        match=CASE.fullmatch(case_id)
        require(match is not None,'CANONICAL_CASE_ID_REQUIRED')
        doc,hyp=match.groups()
        require(doc in groups and hyp in hyps,'CASE_ID_OUTSIDE_FIXED_COHORT')
        groups[doc].append(case_id)
    for doc in docs:
        expected=[f'contractnli:eced6528:test:{doc}:{hyp}'for hyp in hyps]
        require(groups[str(doc)]==expected,'THREE_ORDERED_HYPOTHESIS_CASES_PER_DOCUMENT_REQUIRED')
    flattened=[case_id for doc in docs for case_id in groups[str(doc)]]
    require(flattened==cases,'DOCUMENT_MAJOR_TWELVE_CASE_ORDER_REQUIRED')
    return groups

def validate_native_plan_contract(plan):
    expected=derive_case_ids_by_document(plan)
    require('case_ids_by_document'in plan,'MISSING_FROZEN_CASE_IDS_BY_DOCUMENT')
    actual=plan['case_ids_by_document']
    require(type(actual)is dict and all(type(key)is str for key in actual)and set(actual)==set(expected),'EXACT_FOUR_CANONICAL_DOCUMENT_MAP_KEYS_REQUIRED')
    for doc,ids in expected.items():
        require(type(actual[doc])is list and len(actual[doc])==3 and all(type(x)is str for x in actual[doc])and actual[doc]==ids,'EXACT_ORDERED_DOCUMENT_CASE_MAP_REQUIRED')
    flattened=[case_id for doc in plan['dev_document_ids']for case_id in actual[str(doc)]]
    require(len(flattened)==len(set(flattened))==12 and flattened==plan['data_roles']['dev'],'EXACT_NATIVE_HELPER_TWELVE_CASE_IDENTITY_CONTRACT')
    return {'checks_passed':True,'documents':4,'cases':12,'case_ids_by_document':expected,'target_calls':0,'execution_authorized':False}

def proposed_future_plan_fields(plan):
    """Return only the missing derived field. Caller creates a new future SOURCE."""
    return {'case_ids_by_document':derive_case_ids_by_document(plan)}

def load_public_plan(path):
    p=Path(path)
    require('private'not in p.parts and p.suffix=='.json','PUBLIC_JSON_PLAN_ONLY')
    require(p.absolute()==p.resolve()and not any(q.is_symlink()for q in(p,*p.parents)),'CANONICAL_PUBLIC_PLAN_REQUIRED')
    b=p.read_bytes();require(len(b)<=1048576,'PUBLIC_PLAN_SIZE_CAP')
    return json.loads(b,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in()).throw(ContractError('NONFINITE_JSON')))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);args=parser.parse_args()
    try:value=validate_native_plan_contract(load_public_plan(args.plan))
    except (ContractError,KeyError,TypeError)as error:
        print(json.dumps({'checks_passed':False,'error':str(error),'target_calls':0,'execution_authorized':False},sort_keys=True));raise SystemExit(1)
    print(json.dumps(value,sort_keys=True))
