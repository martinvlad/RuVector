"""Three bounded official GETs; bodies exist in memory only. No raw mail input."""
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import urllib.request
import ssl
import os
import json
import re
import hashlib

OUT = Path('/workspace/ruvector-e45-official')
PRIOR = Path('/workspace/ruvector-e45-official/donor/benchmark-refresh.safe.json')
PIN = 'f41d8ba3322550244bf109fde7614eee7384d34fa8c3960928426ef5f49464c4'
raw = PRIOR.read_bytes()
assert hashlib.sha256(raw).hexdigest() == PIN
prior = json.loads(raw)


def now():
    return datetime.now(timezone.utc).isoformat()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Unexpected redirect; no extra GET authorized')


ca = os.environ.get('SSL_CERT_FILE') or os.environ.get('REQUESTS_CA_BUNDLE')
context = ssl.create_default_context(cafile=ca if ca else None)
opener = urllib.request.build_opener(urllib.request.ProxyHandler(),
    urllib.request.HTTPSHandler(context=context), NoRedirect())
receipts = []
with (OUT / 'PUBLIC_REFRESH_ATTEMPT.json').open('x') as f:
    json.dump({'epoch':45,'nonretryable_attempt':True,'started_at':datetime.now(timezone.utc).isoformat(),'max_GETs':3},f);f.flush();os.fsync(f.fileno())


def get(url, cap):
    assert len(receipts) < 3
    started = now()
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 official-source-read-only',
                                                  'Accept-Encoding': 'identity'})
    with opener.open(request, timeout=45) as response:
        assert response.status == 200 and response.url == url
        declared = response.headers.get('Content-Length')
        if declared is not None:
            assert int(declared) <= cap, 'Declared body exceeds hard cap; no retry'
        body = response.read(cap + 1)
        assert len(body) <= cap, 'Read hard cap exceeded; no retry'
        receipt = {'url': url, 'final_url': response.url, 'status': response.status,
            'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
            'content_type': response.headers.get('Content-Type'),
            'etag': response.headers.get('ETag'), 'last_modified': response.headers.get('Last-Modified'),
            'request_started_at': started, 'retrieved_at': now(), 'read_cap_bytes': cap,
            'TLS_verification_enabled': True, 'raw_body_persisted': False}
    receipts.append(receipt)
    with (OUT / ('source-receipt-%d.json' % len(receipts))).open('x') as f:
        json.dump(receipt,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    return body, receipt


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.text, self.links, self.rows = [], [], []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in ('script', 'style'):
            self.skip += 1
        if 'href' in values:
            self.links.append(values['href'])
        if 'data-bh-jev14-capability-row' in values:
            self.rows.append({'model_id': values['data-bh-jev14-capability-row'],
                              'Capability': float(values['data-bh-jev14-capability-value'])})

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, value):
        if not self.skip:
            self.text.append(value)

    def normalized(self):
        return ' '.join(' '.join(self.text).split())


def parse(body):
    page = Page()
    page.feed(body.decode('utf-8'))
    return page


def excerpts(text, pattern, limit=8):
    matches = list(re.finditer(pattern, text, re.I))[:limit]
    return [text[max(0, m.start()-100):min(len(text), m.end()+250)] for m in matches]


jev_body, jev_receipt = get(prior['JevBench']['source']['url'], 20 * 1024 * 1024)
jev = parse(jev_body)
jt = jev.normalized()
version = re.search(r'Open weights and API offerings \(board (v[\d.]+) \)', jt)
header = re.search(r'method (v[\d.]+) \(([^)]+)\) · updated (\d{4}-\d{2}-\d{2})', jt)
headline = re.search(r'Capability Score averages Intelligence and Calibration \. (.+?) leads the Jev-class systems with (\d+(?:\.\d+)?)', jt)
ranked = re.search(r'(\d+) ranked open-weights systems', jt)
assert version and header and headline and ranked and jev.rows, 'Official leader structure changed; inspect bounded evidence, no extra GET'
assert len({r['model_id'] for r in jev.rows}) == len(jev.rows)
leader = {'model': headline.group(1), **jev.rows[0]}
assert round(leader['Capability'], 1) == float(headline.group(2))
claim_body, claim_receipt = get(prior['ClaimBench']['source']['url'], 2 * 1024 * 1024)
claim = parse(claim_body)
ct = claim.normalized()
linked = sorted(set(urljoin(claim_receipt['url'], link) for link in claim.links
                    if re.search(r'/_astro/benchmark_view_claimbench\.[A-Za-z0-9_-]+\.json(?:$|\?)', link)))
assert len(linked) == 1 and urlparse(linked[0]).scheme == 'https' and urlparse(linked[0]).netloc == 'www.vals.ai'
aggregate_body, aggregate_receipt = get(linked[0], 2 * 1024 * 1024)
aggregate = json.loads(aggregate_body)
metadata, overall = aggregate['metadata'], aggregate['tasks']['overall']
decisions = sorted([{'model': name, 'accuracy_percent': values['accuracy']}
                    for name, values in overall.items() if name.startswith('decision/')],
                   key=lambda row: row['accuracy_percent'], reverse=True)
assert decisions
jeq = jev_receipt['sha256'] == prior['JevBench']['source']['sha256']
ceq = claim_receipt['sha256'] == prior['ClaimBench']['source']['sha256']
aeq = aggregate_receipt['sha256'] == prior['ClaimBench']['official_aggregate']['sha256']
facts = {'schema_version': 1, 'epoch': 45, 'kind': 'FRESH_OFFICIAL_PUBLIC_SOURCES_READ_ONLY',
 'created_at': now(), 'prior_safe_report': {'path': str(PRIOR), 'bytes': len(raw), 'sha256': PIN},
 'source_receipts': receipts,
 'JevBench': {'source': jev_receipt, 'board_version': version.group(1), 'board_updated': header.group(3),
   'method_revision': header.group(1), 'method_header': header.group(2),
   'open_weights_Capability_leader': leader, 'headline_display': float(headline.group(2)),
   'ranked_open_weights_systems': int(ranked.group(1)), 'verified_capability_rows_count': len(jev.rows),
   'first_official_capability_rows': jev.rows[:3],
   'all_capability_rows_sha256': hashlib.sha256(json.dumps(jev.rows,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
   'source_bytes_equal_epoch44': jeq, 'leader_equal_epoch44': leader == prior['JevBench']['open_weights_Capability_leader'],
   'RuVector_page_text_matches': len(re.findall('ruvector', jt, re.I)), 'submission_reference_page_matches': jt.count('7FEA2738'),
   'official_RuVector_rank': None, 'official_RuVector_score': None, 'official_RuVector_eligibility': 'UNVERIFIED',
   'scope': prior['JevBench']['scope'],
   'current_questions_scorer_license_access': 'UNVERIFIED. Current page access and source hashes do not establish exact labelled public questions, fresh sealed full-set access, current scorer package, dataset redistribution licence or submission eligibility.',
   'historical_access_probes_repeated': False,
   'rule_text_evidence': excerpts(jt, r'more than 10|10 seconds|frozen scorer', 3)},
 'ClaimBench': {'source': claim_receipt, 'official_aggregate': aggregate_receipt,
   'aggregate_URL_verified_from_current_official_page': True,
   'total_models': metadata['total_models'], 'publisher_version': metadata['version'],
   'publisher_updated': metadata['updated'], 'publisher_metadata_dataset_type': metadata['dataset_type'],
   'decision_leader': decisions[0], 'decision_runner_up': decisions[1],
   'language_models_at100': [{'model': name,'accuracy_percent': values['accuracy']} for name,values in overall.items()
                            if not name.startswith('decision/') and values['accuracy'] == 100],
   'RuVector_in_aggregate': any('ruvector' in name.lower() for name in overall), 'RuVector_score': None,
   'source_bytes_equal_epoch44': ceq, 'aggregate_bytes_equal_epoch44': aeq,
   'full_dataset_scorer_license_submission_access': 'UNVERIFIED. Public examples, public metadata and aggregate JSON do not establish full labelled cases, exact scorer, redistribution licence or submission access.',
   'verified_dataset_access_scope': 'Current official public page examples and linked aggregate only.',
   'retrieval_scope': 'ONLY supplied 10-K excerpts. A retrieval miss cannot establish insufficient evidence or NEI.',
   'pilot_executed': False,
   'access_candidate_links_on_current_page_not_followed': sorted(set(link for link in claim.links
          if re.search(r'dataset|scorer|licen[cs]e|submit|huggingface|github', link, re.I)))[:30]},
 'comparison': {'all_three_bodies_equal_epoch44': jeq and ceq and aeq,
   'Jev_body_equal': jeq, 'Claim_page_equal': ceq, 'Claim_aggregate_equal': aeq},
 'direct_public_GETs': len(receipts), 'raw_public_bodies_persisted': False,
 'inherited_proxy_preserved': True, 'TLS_verification_enabled': True,
 'model_native_gold_or_paid_GPU_calls': 0, 'project_or_Git_mutations': 0,
 'outgoing_messages_submissions_or_author_contacts': 0, 'goal_verified': False,
 'official_SOTA_verified': False}
payload = (json.dumps(facts,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
assert len(payload) < 100000 and b'@' not in payload
path = OUT / 'public-facts.json'
with path.open('xb') as stream:
    stream.write(payload);stream.flush();os.fsync(stream.fileno())
print(json.dumps({'path': str(path),'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),
 'Jev_leader':leader,'Jev_board':version.group(1),'Jev_rows':len(jev.rows),
 'Claim_leader':decisions[0],'Claim_runner_up':decisions[1],
 'all_three_bodies_equal_epoch44':jeq and ceq and aeq,'public_GETs':len(receipts)}))
