"""One unexpanded original hypothesis query shared by both readers and all native arms."""
import hashlib
from pathlib import Path

POLICY = 'unchanged-original-query-paired-readers-v1'


def query(hypothesis):
    if not isinstance(hypothesis, str) or not hypothesis.strip() or '\0' in hypothesis:
        raise ValueError('A whole nonempty original hypothesis is required')
    digest = hashlib.sha256(hypothesis.encode('utf-8', errors='strict')).hexdigest()
    return {'schema_version': 1, 'epoch': 36, 'policy': POLICY,
        'query_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'query_policy_sha256': hashlib.sha256(Path(__file__).with_name('QUERY_POLICY.json').read_bytes()).hexdigest(),
        'original_query': hypothesis,
        'original_query_sha256': digest, 'original_hypothesis_sha256': digest,
        'query': hypothesis, 'query_sha256': digest, 'expansion_applied': False}

