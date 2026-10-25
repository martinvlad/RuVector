"""One frozen label-free lexical anchor and distinct native-group complement."""
import hashlib
from pathlib import Path

POLICY = 'lexical-anchor-native-complement-v1'


def query(hypothesis):
    if not isinstance(hypothesis, str) or not hypothesis.strip() or '\0' in hypothesis:
        raise ValueError('A whole nonempty original hypothesis is required')
    digest = hashlib.sha256(hypothesis.encode('utf-8', errors='strict')).hexdigest()
    return {'schema_version': 1, 'epoch': 34, 'policy': POLICY,
        'query_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'query_policy_sha256': hashlib.sha256(Path(__file__).with_name('QUERY_POLICY.json').read_bytes()).hexdigest(),
        'original_query': hypothesis,
        'original_query_sha256': digest, 'original_hypothesis_sha256': digest,
        'query': hypothesis, 'query_sha256': digest, 'expansion_applied': False}


def hybrid_order(lexical, native, units):
    if not isinstance(units, list) or not units or len(units) > 192:
        raise ValueError('Bounded complete source-unit catalogue required')
    count = len(units)
    for ranking in (lexical, native):
        if (not isinstance(ranking, list) or not ranking or len(set(ranking)) != len(ranking)
                or any(type(i) is not int or not 0 <= i < count for i in ranking)):
            raise ValueError('Distinct canonical in-document ranked unit IDs required')
    if lexical != list(dict.fromkeys(lexical)) or set(lexical) != set(range(count)):
        raise ValueError('Complete lexical ranking required')
    if len(native) != min(40, count):
        raise ValueError('Exact original native top40 ranking required')
    if any(unit.get('id') != i or type(unit.get('group_id')) is not int
            or unit['group_id'] < 0 for i, unit in enumerate(units)):
        raise ValueError('Exact source-unit/group IDs required')
    anchor = lexical[0]
    anchor_group = units[anchor]['group_id']
    complement = next((i for i in native if units[i]['group_id'] != anchor_group), None)
    catalogue_groups = {unit['group_id'] for unit in units}
    if complement is None and len(catalogue_groups) != 1:
        # A native top40 confined to one group cannot justify claiming that no
        # other source group exists. No lexical-only fallback is authorized.
        raise ValueError('No distinct native complement in actual top40; no fallback')
    prefix = [anchor] + ([] if complement is None else [complement])
    ranking = (prefix + [i for i in native if i not in prefix])[:min(40, count)]
    return ranking, {'policy': POLICY, 'lexical_anchor_unit_id': anchor,
        'lexical_anchor_group_id': anchor_group,
        'native_complement_unit_id': complement,
        'native_complement_group_id': None if complement is None else units[complement]['group_id'],
        'single_group_degenerate': len(catalogue_groups) == 1,
        'hybrid_ranking': list(ranking)}
