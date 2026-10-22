"""Cycle2 H1 solver, with exact frozen93 fallback. Pure normalized wire inputs."""
import importlib.util
from pathlib import Path

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

BASE=Path(__file__).resolve().parent
baseline=load('frozen93_rule_source',BASE.parent/'frozen-baseline/rules.py')
numeric=load('cycle2_H1_pure_numeric',BASE/'typed_numeric.py')

def solve(state,question):
    return baseline.solve(state,question) or numeric.solve(state,question)

def baseline_proof(state,question):return baseline.solve(state,question)
