"""Immutable exact100 fallback plus new supplied-record relation joins."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
BASE=Path(__file__).resolve().parent

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

baseline=load('submission_immutable100_rules',ROOT/'experiments/compounding/jevbench/cycle3/round2/rules.py')
relations=load('submission_pure_relations',BASE/'typed_relations.py')
def baseline_proof(state,question):return baseline.solve(state,question)
def solve(state,question):return baseline.solve(state,question) or relations.solve(state,question)
