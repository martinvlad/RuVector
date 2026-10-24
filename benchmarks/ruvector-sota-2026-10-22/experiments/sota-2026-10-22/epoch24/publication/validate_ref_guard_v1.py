"""Validate saved remote Git observations and construct a CAS intent; no Git calls.

The external mutation controller must obtain fresh observations itself, enforce
this check before mutations, and verify actual remote leaves after publication.
A saved observation or this pure helper alone is never execution admission.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path
import re
from publication_common_v1 import SCOPE, directory, encoded, new_output, parse, require, write

REPOSITORY = 'ruvnet/RuVector'
BRANCH = SCOPE.rstrip('/')

def sha40(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{40}', value),
            'Exact Git SHA required')
    return value

def siblings(tree, except_path):
    require(isinstance(tree, dict) and tree.get('truncated') is False
            and isinstance(tree.get('tree'), list), 'Complete saved tree response required')
    sha40(tree.get('sha'))
    found = {}
    for row in tree['tree']:
        require(isinstance(row, dict) and all(key in row for key in ('path','mode','type','sha')),
                'Incomplete saved tree tuple')
        path = row['path']
        require(isinstance(path, str) and path and '/' not in path and path not in found,
                'Duplicate/non-immediate sibling path')
        sha40(row['sha'])
        found[path] = tuple(row[key] for key in ('path','mode','type','sha'))
    require(except_path in found and found[except_path][2] == 'tree',
            'Expected scope ancestor tree absent')
    return {key:value for key,value in found.items() if key != except_path}

def verify(baseline, observed, expected_parent):
    sha40(expected_parent)
    for value in (baseline, observed):
        require(isinstance(value, dict) and value.get('repository') == REPOSITORY
                and value.get('branch') == BRANCH, 'Wrong repository or branch')
        sha40(value.get('main_sha'));sha40(value.get('branch_sha'))
    require(observed['branch_sha'] == expected_parent, 'Branch parent CAS changed; STOP')
    require(observed['main_sha'] == baseline['main_sha'], 'Main changed; STOP')
    for key, scope_child in (('root_tree', 'benchmarks'),
                             ('benchmarks_tree', 'ruvector-sota-2026-10-22')):
        require(siblings(baseline[key], scope_child) == siblings(observed[key], scope_child),
                'Outside-scope sibling changed; STOP: ' + key)
    for value in (baseline, observed):
        root_child = next(row for row in value['root_tree']['tree'] if row['path']=='benchmarks')
        require(root_child['sha'] == value['benchmarks_tree']['sha'],
                'Saved ancestor tree chain does not join')
    return {'checks_passed': True, 'expected_parent':expected_parent,
            'main_sha':baseline['main_sha'], 'outside_scope_unchanged': True,
            'Git_mutations':0, 'scientific_execution':0}

def cas_intent(parent, new_commit, main_sha):
    return {'repository':REPOSITORY,'branch':BRANCH,'expected_sha':sha40(parent),
            'sha':sha40(new_commit),'force':False,'main_expected':sha40(main_sha),
            'fresh_main_and_sibling_validation_required':True,
            'actual_remote_readback_required_before_admission_or_unlock':True}

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--baseline',type=Path,required=True)
    cli.add_argument('--observed',type=Path,required=True)
    cli.add_argument('--parent',required=True)
    cli.add_argument('--new-commit')
    args=cli.parse_args();base=parse(args.baseline)
    result=verify(base,parse(args.observed),args.parent)
    if args.new_commit:result['CAS_intent']=cas_intent(args.parent,args.new_commit,base['main_sha'])
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
