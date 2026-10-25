"""Pure pre-seal fixtures; never dispatches, imports ML, or observes live processes."""
import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
CANDIDATE=HERE.parent
PROJECT=HERE.parents[4]
AUDIT=PROJECT/'experiments/sota-2026-10-22/audit/epoch36'


def run():
    parsed=[]
    for directory in(CANDIDATE,AUDIT,PROJECT/'experiments/sota-2026-10-22/epoch36/preparation'):
        for file in sorted(directory.rglob('*.py')):
            ast.parse(file.read_text());parsed.append(file.relative_to(PROJECT).as_posix())
    sys.path.insert(0,str(AUDIT))
    modules=[]
    for name,file in [('e36_source_only_fixtures',CANDIDATE/'test_source_only.py'),
            ('e36_observer_source_only_fixtures',AUDIT/'test_observe_supervisor_closure.py')]:
        spec=importlib.util.spec_from_file_location(name,file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);modules.append(module)
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m)for m in modules)
    output=io.StringIO();result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    ml=[k for k in('torch','transformers','onnxruntime','tokenizers','safetensors','numpy')if k in sys.modules]
    report={'schema_version':1,'epoch':36,'kind':'ENGINEERING_PAIRED_READER_SOURCE_COVERAGE',
        'status':'PASS'if result.wasSuccessful()and not ml else'FAIL','parsed_Python_sources':parsed,
        'fixtures_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'ML_modules_imported':ml,'actual_model_initializations':0,'actual_tokenizer_initializations':0,
        'actual_native_corpus_batches':0,'actual_native_queries':0,'actual_physical_observers':0,
        'actual_dispatches':0,'benchmark_measurements':0,'synthetic_fixture_scope':'Invented readout and stub word-counter protocol fixtures only; never empirical neural predictions or benchmark evidence.',
        'fixture_output':output.getvalue()}
    if report['status']!='PASS':raise RuntimeError(json.dumps(report))
    return report

if __name__=='__main__':print(json.dumps(run(),indent=2))
