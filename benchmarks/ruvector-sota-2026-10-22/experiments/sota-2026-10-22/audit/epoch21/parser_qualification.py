"""One owned parser-only qualification on three already-exposed CC0 strings."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
from common import ROOT, PREFIX, demand, member, identity, read
from tokenizer_source import build_tokenizer, literal_feed, source_assets, FORBIDDEN

CANARY = PREFIX + 'legal-transfer/epoch19/canaries.json'
CANARY_SHA = '4bd2e363117600603d6f215813bd77ea0f62acedb8c399700e8ae210161c7820'
PAIRS = [('semantic-e-v1', 'The lamp is on.', 'The lamp is on.'),
         ('semantic-c-v1', 'The lamp is not on.', 'The lamp is on.'),
         ('semantic-n-v1', 'The box is blue.', 'The lamp is on.')]


def qualify():
    start = time.monotonic(); os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
    demand(not any(n in sys.modules for n in FORBIDDEN), 'no neural/conversion modules may be imported')
    files, before = source_assets()
    canary = member(CANARY); demand(identity(canary)['sha256'] == CANARY_SHA, 'exact exposed canary source required')
    original = read(canary)
    fixtures = original['fixtures'] if 'fixtures' in original else original['records']
    triples = [(r['id'], r['premise'], r['hypothesis']) for r in fixtures]
    demand(triples == PAIRS, 'only the three fixed exposed literal engineering pairs may be tokenized')
    report = {'schema_version': 1, 'epoch': 21, 'at': datetime.now(timezone.utc).isoformat(),
              'kind': 'TOKENIZER_ONLY_PUBLIC_ENGINEERING_FORMAT_PREFLIGHT',
              'checks_passed': False, 'tokenizers_version': importlib.metadata.version('tokenizers'),
              'assets': before, 'fixtures': [], 'model_native_forwards': 0,
              'legal_DEV_or_CONF_texts_read': 0, 'original_annotations_read': 0,
              'neural_framework_imports': [], 'automatic_retry': False,
              'scope': 'Exactly one parser/format qualification on three already-exposed CC0 strings; no semantic predictions or benchmark measurement.'}
    try:
        tokenizer, assets, provenance = build_tokenizer()
        report['tokenizer_policy'] = provenance
        for fixture_id, premise, hypothesis in PAIRS:
            feed = literal_feed(tokenizer, premise, hypothesis)
            report['fixtures'].append({'fixture_id': fixture_id, 'premise': premise,
                                       'hypothesis': hypothesis, 'feed': feed})
        report['checks_passed'] = True; report['status'] = 'EXACT_SOURCE_TOKENIZER_JSON_PARSER_AND_PAIR_FORMAT_PASS'
    except Exception as exc:
        report['status'] = 'SOURCE_TOKENIZER_JSON_PARSER_OR_FORMAT_BLOCKED'
        report['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
    _, after = source_assets(); demand(after == before, 'original assets changed during qualification')
    demand(not any(n in sys.modules for n in FORBIDDEN), 'no neural/conversion modules may be imported')
    report['original_assets_unchanged'] = True
    report['elapsed_seconds'] = time.monotonic() - start
    return report


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); args = ap.parse_args()
    out = args.out.absolute(); expected = ROOT / (PREFIX + 'audit/epoch21/tokenizer-format-preflight-v1.json')
    demand(out == expected and not any(p.is_symlink() for p in [out, *out.parents]), 'exact exclusive qualification receipt path required')
    demand(not out.exists(), 'qualification must run once; retain failure instead of retrying')
    value = qualify()
    with out.open('x') as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
    print(json.dumps({k: value[k] for k in ('status', 'checks_passed', 'elapsed_seconds', 'model_native_forwards')}))
    raise SystemExit(0 if value['checks_passed'] else 2)


if __name__ == '__main__': main()

