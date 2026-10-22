"""Exact immutable97 fallback plus supported input-only probability proofs."""
import importlib.util
from pathlib import Path

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

BASE=Path(__file__).resolve().parent
baseline=load('immutable97_prediction_source',BASE.parents[1]/'cycle2/round2/rules.py')
probability=load('cycle3_pure_probability',BASE/'probability.py')

def solve(state,question):return baseline.solve(state,question) or probability.solve(state,question)
def baseline_proof(state,question):return baseline.solve(state,question)
