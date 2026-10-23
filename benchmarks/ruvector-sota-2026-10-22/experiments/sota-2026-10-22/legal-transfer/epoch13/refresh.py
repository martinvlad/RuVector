"""At most three non-retried official GETs; publish receipts and aggregates only."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
import argparse
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
RAW = HERE / 'benchmark-sources'


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def get(url, name):
    save(RAW / (name + '.request.json'), {'started_at_UTC': now(), 'url': url, 'retry_permitted': False})
    with urlopen(Request(url, headers={'User-Agent': 'RuVector-benchmark-source-refresh/epoch13'}), timeout=30) as response:
        if response.status != 200:
            raise ValueError('Official response status: ' + str(response.status))
        body = response.read()
        final = response.url
    with (RAW / name).open('xb') as stream:
        stream.write(body)
    receipt = {'url': url, 'final_url': final, 'HTTP_status': 200,
               'local_path': 'benchmark-sources/' + name, 'bytes': len(body),
               'sha256': hashlib.sha256(body).hexdigest(), 'observed_at_UTC': now()}
    save(RAW / (name + '.receipt.json'), receipt)
    return receipt, body


def extract(receipts):
    jev, page, aggregate = receipts
    jraw = (RAW / 'jev-board.html').read_text()
    data = json.loads((RAW / 'claimbench-aggregate.json').read_text())
    plain = re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', jraw))
    match = re.search(r'Capability Score averages Intelligence and Calibration \. (.*?) leads the Jev-class systems with ([0-9.]+) \.', plain)
    if not match:
        raise ValueError('Fresh official Jev-class leader summary not located')
    board = re.search(r'JevBench · board (v[0-9.]+) · updated ([0-9-]+)', plain)
    overall = data['tasks']['overall']
    if not overall or not all(isinstance(v['accuracy'], (int, float)) and 0 <= v['accuracy'] <= 100 for v in overall.values()):
        raise ValueError('Invalid official aggregate accuracy scale')
    decisions = {key: value['accuracy'] for key, value in overall.items() if key.startswith('decision/')}
    if not decisions:
        raise ValueError('No official decision-model entries')
    top = max(decisions.values())
    leaders = sorted(key for key, score in decisions.items() if score == top)
    out = {'schema_version': 1, 'recorded_at_UTC': now(),
           'JevBench': {'source': jev, 'board_version': board.group(1) if board else None,
                        'board_updated': board.group(2) if board else None,
                        'track': 'Official Jev-class open-weights Capability under publisher cost/latency caps',
                        'leader': match.group(1), 'Capability': float(match.group(2)), 'source_quote': match.group(0),
                        'RuVector_rendered_row_present': bool(re.search('ruvector', jraw, re.I)),
                        'RuVector_official_score': None, 'RuVector_official_rank': None,
                        'submission_reference': '7FEA2738', 'queue_position_is_rank': False,
                        'publisher_submission_status': 'Public board only; root separately checks private publisher notice. Original115 was a queue position, never rank.',
                        'current300_questions_scorer': 'Not verified publicly available; sealed evaluation belongs to publisher.'},
           'ClaimBench': {'page_source': page, 'aggregate_source': aggregate,
                          'aggregate_updated': data['metadata']['updated'],
                          'decision_model_leader': leaders[0] if len(leaders) == 1 else leaders,
                          'decision_model_leaders': leaders, 'decision_model_accuracy_percent': top,
                          'all_models_at100_percent': [key for key, value in overall.items() if value['accuracy'] == 100],
                          'language_models_at100_percent': [key for key, value in overall.items() if not key.startswith('decision/') and value['accuracy'] == 100],
                          'total_models': data['metadata']['total_models'],
                          'prior_public_observations': {'claims': 1960, 'public_examples': 10,
                                                        'labels': ['contradicted', 'insufficient_evidence', 'supported'],
                                                        'scope': 'Previously verified official examples/description only; no full dataset/scorer/license/submission access established.'},
                          'access_evidence': {'aggregate_metadata_dataset_type': data['metadata'].get('dataset_type'),
                                              'aggregate_runner': data['metadata'].get('runner'),
                                              'full_question_dataset_scorer_license_submission_access': 'Still unverified; no repeated access-blocker probe, outreach or access attempt.'},
                          'prior_decision_leader_observation': {'model': 'decision/decider-v1.2', 'accuracy_percent': 99.694,
                                                               'current_accuracy_percent': decisions.get('decision/decider-v1.2'),
                                                               'currently_top_decision_model': 'decision/decider-v1.2' in leaders},
                          'RuVector_aggregate_row_present': any('ruvector' in key.casefold() for key in overall),
                          'RuVector_score': None, 'RuVector_rank': None,
                          'pilot_status': 'No pilot executed: full data/scoring/license/access are not verified.',
                          'retrieval_policy': 'ONLY supplied10-K excerpts; retrieval miss cannot establish insufficient evidence.'},
           'public_GETs': 3, 'native_model_paid_calls': 0, 'emails_submissions_external_mutations': 0,
           'publication_allowlist': ['benchmark-refresh.json', 'benchmark-source-receipts.json', 'refresh-attempt.json'],
           'raw_HTML_and_full_public_example_text_publication': False, 'official_sota_established': False,
           'extraction_validation': 'Fresh official Jev-class leader summary and ClaimBench overall aggregate parsed. Aggregate URL discovered in fresh official page. Exactly3GETs; no stale leaderboard fallback or repeated full-access blocker probe.'}
    save(HERE / 'benchmark-refresh.json', out)
    print(json.dumps({'fresh_HTTP200_GETs': 3, 'Jev_openweights_leader': out['JevBench']['leader'],
                      'Capability': out['JevBench']['Capability'], 'Claim_decision_leader': leaders,
                      'accuracy': top, 'language_models_at100': len(out['ClaimBench']['language_models_at100_percent'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--extract-saved', action='store_true')
    args = parser.parse_args()
    if (HERE / 'benchmark-refresh.json').exists():
        raise SystemExit('Already refreshed; no repeated GETs')
    if args.extract_saved:
        receipts = json.loads((HERE / 'benchmark-source-receipts.json').read_text())
        for item in receipts:
            body = (HERE / item['local_path']).read_bytes()
            assert len(body) == item['bytes'] and hashlib.sha256(body).hexdigest() == item['sha256']
    else:
        RAW.mkdir(exist_ok=True)
        save(HERE / 'refresh-attempt.json', {'started_at_UTC': now(), 'max_official_GETs': 3,
                                           'automatic_retries': 0, 'model_native_paid_calls': 0})
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(get, 'https://benchmarkheaven.com/jev-models', 'jev-board.html'),
                       pool.submit(get, 'https://www.vals.ai/benchmarks/claimbench', 'claimbench.html')]
            results, errors = [], []
            for future in futures:
                try:
                    results.append(future.result())
                except Exception as error:
                    errors.append(type(error).__name__)
            if errors:
                save(HERE / 'refresh-blocker.json', {'at': now(), 'response_errors': errors,
                                                    'retry_attempted': False, 'scope': 'Official source read failed; do not repeat this epoch.'})
                raise SystemExit('Official source GET failed; no retry')
        jev, page = results
        matches = sorted(set(re.findall(r'/_astro/benchmark_view_claimbench\.[A-Za-z0-9_-]+\.json', page[1].decode())))
        if len(matches) != 1:
            raise ValueError('Ambiguous current official aggregate URL; no retry')
        aggregate = get('https://www.vals.ai' + matches[0], 'claimbench-aggregate.json')
        receipts = [jev[0], page[0], aggregate[0]]
        save(HERE / 'benchmark-source-receipts.json', receipts)
    extract(receipts)
