"""CC0-1.0 implementation-owned source-only smoke cases; no auditor fixtures."""
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location('implementation_owned_scope', Path(__file__).with_name('scope.py'))
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


def case(text):
    return {'id': 'implementation_smoke', 'query': 'alpha delivery',
        'excerpts': [{'id': 'own', 'text': text}],
        'budget': {'max_nodes': 32, 'max_utf8_bytes': 4096}, 'seed_limit': 1}


def main():
    text = ('1. Café controls, subject to Section 3:\r\n'
        '(a) Deliver alpha.\r\n  Continue with π.\r\n'
        '2. Beta.\r\n3. Archive.')
    raw = case(text); parsed = scope.parse_case(raw)
    assert parsed['valid'] and not parsed['unknowns']
    assert list(parsed['units']) == ['own::1', 'own::1(a)', 'own::2', 'own::3']
    assert parsed['units']['own::1']['requires'] == ['own::3']
    assert parsed['units']['own::1(a)']['requires'] == ['own::1']
    assert parsed['units']['own::1(a)']['heading_spans'][0]['text'].endswith(':')
    assert '\r\n  Continue with π.' in parsed['units']['own::1(a)']['whole_span']['text']
    for unit in parsed['units'].values():
        for field in ('whole_span', 'marker_span', 'content_span'):
            value = unit[field]
            assert text[value['start']:value['end']] == value['text']
            assert text.encode()[value['source_byte_start']:value['source_byte_end']].decode() == value['text']
    baseline = scope.pack_scope(raw, parsed, ['own::1(a)'], False)
    closed = scope.pack_scope(raw, parsed, ['own::1(a)'], True)
    assert baseline['observed_effective_seed_ids'] == closed['observed_effective_seed_ids']
    assert baseline['unknown'] and closed['selected_unit_ids'] == ['own::1', 'own::1(a)', 'own::3']
    assert not closed['unknown'] and closed['entailment_or_insufficiency_decision'] == 'NOT_EVALUATED'
    for bad in (dict(raw, units=[]), dict(raw, edges=[]), dict(raw, dependencies=[])):
        assert not scope.parse_case(bad)['valid']
    missing = scope.parse_case(case('1. Subject to Section 9.'))
    assert missing['references'][0]['status'] == 'unresolved_reference'
    ranged = scope.parse_case(case('1. Subject to Sections 2-3.\n2. Beta.\n3. Gamma.'))
    assert not ranged['units']['own::1']['requires']
    assert ranged['unknowns'][0]['reason'] == 'unsupported_reference_syntax'
    cycle = scope.parse_case(case('1. Subject to Section 2.\n2. Subject to Section 1.'))
    assert cycle['cycles'] == [['own::1', 'own::2']]
    assert len(scope.pack_scope(case('1. Subject to Section 2.\n2. Subject to Section 1.'), cycle, ['own::1'], True)['selected_unit_ids']) == 2
    print('7 implementation-owned structural smoke checks passed; BGE/native/NLI calls=0')


if __name__ == '__main__':
    main()
