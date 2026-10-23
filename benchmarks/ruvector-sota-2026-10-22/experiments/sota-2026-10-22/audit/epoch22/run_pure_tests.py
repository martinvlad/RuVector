"""Run only synthetic audit tests with explicit import/source-open guards."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import time
import unittest

HERE = Path(__file__).resolve().parent
FORBIDDEN = {'torch', 'transformers', 'tokenizers', 'onnxruntime', 'sentencepiece', 'safetensors'}
violations = []


def guard(event, args):
    if event == 'import' and args and str(args[0]).split('.')[0] in FORBIDDEN:
        violations.append({'event': event, 'module': str(args[0])})
        raise RuntimeError('Synthetic tests forbid model, tokenizer and runtime imports')
    if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = Path(os.fsdecode(args[0])); name = p.name
        forbidden = (name == 'original-train.json' or name.startswith(('inputs.', 'gold.'))
                     or p.suffix in {'.safetensors', '.onnx', '.bin', '.model', '.whl'}
                     or '/assets/' in p.as_posix())
        if forbidden:
            violations.append({'event': event, 'name': name})
            raise RuntimeError('Synthetic tests forbid corpus labels/cases, weights and parser assets')


class Result(unittest.TestResult):
    def __init__(self): super().__init__(); self.rows = []
    def addSuccess(self, test): super().addSuccess(test); self.rows.append({'test': test.id(), 'status': 'PASS'})
    def addFailure(self, test, err): super().addFailure(test, err); self.rows.append({'test': test.id(), 'status': 'FAIL', 'failure': self._exc_info_to_string(err, test)})
    def addError(self, test, err): super().addError(test, err); self.rows.append({'test': test.id(), 'status': 'ERROR', 'failure': self._exc_info_to_string(err, test)})


def main():
    if len(sys.argv) != 2: raise SystemExit('Pass a new exclusive receipt path')
    target = Path(sys.argv[1]).absolute()
    assert target.parent == HERE and not target.exists()
    started = time.perf_counter(); sys.addaudithook(guard)
    suite = unittest.defaultTestLoader.loadTestsFromNames(['test_metrics', 'test_replay', 'test_model', 'test_sentence'])
    result = Result(); suite.run(result)
    sources = []
    for f in sorted(HERE.glob('*.py')):
        data = f.read_bytes(); compile(data, str(f), 'exec')
        assert len(data.splitlines()) < 500
        sources.append({'path': str(f.relative_to(HERE.parents[3])), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    value = {'schema_version': 1, 'epoch': 22, 'at': datetime.now(timezone.utc).isoformat(),
        'kind': 'PURE_SYNTHETIC_ARITHMETIC_SOURCE_GROUP_AND_RECEIPT_FAULT_TESTS',
        'checks_passed': result.wasSuccessful() and not violations, 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'elapsed_seconds': time.perf_counter() - started, 'test_results': result.rows,
        'source_identities': sources, 'guard_violations': violations,
        'model_native_tokenizer_parser_original_case_or_annotation_calls': 0,
        'scope': 'Authored synthetic fixtures only, not benchmark competence, capacity or generalization.'}
    with target.open('x') as f:
        json.dump(value, f, sort_keys=True, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    print(json.dumps({k: value[k] for k in ('checks_passed', 'tests', 'failures', 'errors', 'elapsed_seconds')}))
    if not value['checks_passed']: raise SystemExit(1)


if __name__ == '__main__': main()
