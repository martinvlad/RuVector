"""Independent exact original-tokenizer feed replay after sealed phase cleanup."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import replay as R
from tokenizer_source import build_tokenizer, literal_feed, FORBIDDEN


def replay(plan_path, raw_path, execution_path):
    plan, protocol = R.plan_replay(plan_path); raw = R.read(raw_path); execution = R.read(execution_path)
    state, instance = R.model_replay(raw, protocol)
    engineering = R.engineering_replay(raw, protocol, state, instance); R.assets_replay(raw, plan)
    complete = raw['status'] == 'COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE'
    R.demand(complete or (raw['status'] == 'REJECTED_ENGINEERING_QUALIFICATION_NO_LEGAL_INPUTS'
                         and not engineering['passed']), 'only complete sealed phase evidence may enter tokenizer replay')
    R.resources_replay(raw, execution, raw_path, raw['phase'], complete); R.counters_replay(raw, complete)
    pairs = [row['forward'] for row in raw['canary_forwards']]
    if complete:
        for document in raw['documents']:
            for question in document['questions']:
                pairs.extend(question['arms'][arm]['forward'] for arm in R.M.ARMS)
    R.demand(len(pairs) == (75 if complete else 3), 'exact saved phase feed count required')
    tokenizer, assets, provenance = build_tokenizer()
    backend_sha = provenance['configured_backend_sha256']
    R.demand(backend_sha == protocol['tokenizer']['operational_backend_sha256']
             == raw['tokenizer']['backend_sha256'], 'exact prequalified original operational backend required')
    rows = []
    for i, row in enumerate(pairs):
        feed = literal_feed(tokenizer, row['premise'], row['hypothesis'])
        R.demand(feed == row['feed'] and row['feed_sha256'] == R.digest(R.canonical(feed)),
                 'saved three-tensor feed differs from independent exact source tokenizer')
        R.demand(row['actual_tokens'] == len(feed['input_ids'][0]), 'saved untruncated token length differs')
        rows.append({'forward_index': i, 'input_text_sha256': row['input_text_sha256'],
                     'feed_sha256': row['feed_sha256'], 'tokens': row['actual_tokens']})
    R.demand(not any(n in sys.modules for n in FORBIDDEN), 'independent replay imported a forbidden framework or conversion module')
    return {'schema_version': 1, 'epoch': 21, 'phase': raw['phase'],
            'at': datetime.now(timezone.utc).isoformat(),
            'kind': 'INDEPENDENT_POSTRUN_SOURCE_TOKENIZER_JSON_FEED_REPLAY', 'checks_passed': True,
            'plan_sha256': R.identity(plan_path)['sha256'], 'raw_receipt_sha256': R.identity(raw_path)['sha256'],
            'execution_receipt': R.identity(execution_path, str(Path(execution_path).relative_to(R.ROOT))),
            'tokenizers_version': '0.21.4', 'actual_worker_backend_sha256': raw['tokenizer']['backend_sha256'],
            'independent_reconstructed_backend_sha256': backend_sha,
            'reconstructed_backend_identity_comparison_scope': 'Both exact prequalified operational backend identity and all actual pair IDs/masks/type IDs/hashes must match the original source tokenizer policy.',
            'actual_feed_pairs_replayed': len(rows), 'feeds': rows, 'assets': assets,
            'source_policy': provenance, 'model_native_forwards': 0, 'neural_framework_imports': [],
            'gold_labels_read': 0,
            'scope': 'Postrun original tokenizer/feed verification only; no new neural predictions or corpus measurement.'}


def main():
    ap = argparse.ArgumentParser()
    for key in ('plan', 'raw', 'execution', 'out'): ap.add_argument('--' + key, type=Path, required=True)
    a = ap.parse_args(); value = replay(a.plan, a.raw, a.execution); R.write_new(a.out, value)
    print(json.dumps({'checks_passed': True, 'model_native_forwards': 0,
                      'actual_feed_pairs_replayed': value['actual_feed_pairs_replayed']}))


if __name__ == '__main__': main()

