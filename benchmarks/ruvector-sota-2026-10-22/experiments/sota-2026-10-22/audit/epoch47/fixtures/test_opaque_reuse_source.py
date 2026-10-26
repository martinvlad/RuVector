"""Inert changed-custody fixture: dummy bytes only, no source module import."""
import ast
import copy
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from types import SimpleNamespace


HERE = Path(__file__).resolve().parents[1]


def definitions(path, names):
    tree = ast.parse(path.read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    return compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec')


def rejected(function, *args):
    try:
        function(*args)
    except (ValueError, FileExistsError):
        return
    raise AssertionError('Fixture expected rejection')


def compact_fixtures(features):
    """Invented retained-token metadata tests; no tokenizer, body bank or model."""
    source = HERE / 'e47_input_audit.py'
    tree = ast.parse(source.read_text())
    system = next(ast.literal_eval(n.value) for n in tree.body if
                  isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and
                  t.id == 'SYSTEM' for t in n.targets))
    namespace = {'F': features, 'SYSTEM': system}
    exec(definitions(source, ['same', 'digest', 'render', 'replay_packing']), namespace)
    replay = namespace['replay_packing']
    render = namespace['render']
    digest = namespace['digest']
    sentences = ['INVENTED fixture source unit zero. ',
                 'INVENTED fixture source unit one. ',
                 'INVENTED fixture source unit two. ']
    spans = []
    offset = 0
    for i, sentence in enumerate(sentences):
        spans.append(dict(unit_id=i, sentence=sentence, start=offset,
                          end=offset+len(sentence)))
        offset += len(sentence)
    record = {'id': 'INVENTED_COMPACT_FIXTURE', 'claim': 'INVENTED claim only.',
              'evidence': spans}
    arm = 'INVENTED_ARM'

    def bundle(layout, choices):
        proposals = []
        entries = {}
        for stage, index, first, second, count in layout:
            ordinal = len(proposals)+1
            prompt = render(record['claim'], *['\n\n'.join(spans[i]['sentence']
                            for i in ids) for ids in [first, second]])
            tokens = [100+ordinal]*count  # Invented observations, never tokenization.
            receipt = {'request_ordinal': ordinal, 'category': 'prompt_tokenize'}
            row = dict(ordinal=ordinal, case_id=record['id'], arm=arm,
                       stage=stage, window_index=index,
                       selected_unit_ids=[first, second],
                       prompt_sha256=features.sha(prompt.encode()),
                       claim_sha256=features.sha(record['claim'].encode()),
                       prompt_token_count=count, token_ids_sha256=digest(tokens),
                       token_ids=tokens, http_exchange=receipt)
            proposals.append(row)
            entries[ordinal] = {'receipt': receipt,
                'request': {'content': prompt, 'add_special': False,
                            'parse_special': True, 'with_pieces': False},
                'response': {'tokens': tokens}}
        windows = []
        for index, anchor, scans in choices:
            decisions = [{'anchor': a, 'group_unit_ids': [a],
                'proposed_unit_ids': [a], 'marginal_tokens': length-100,
                'accepted': length-100 <= 110, 'journal_ordinal': ordinal}
                for a, ordinal, length in scans]
            span = spans[anchor]
            windows.append({'window_index': index, 'source_unit_ids': [anchor],
                'duplicate_first': False, 'equal_marginal_budget': 110,
                'selection_decisions': decisions,
                'source_spans': [{'unit_id': anchor, 'start': span['start'],
                    'end': span['end'], 'sha256': features.sha(span['sentence'].encode())}],
                'text_sha256': features.sha(span['sentence'].encode())})
        last = proposals[-1]
        forecast = dict(windows=windows, packing_final_journal_ordinal=last['ordinal'],
                        base_prompt_tokens=100, equal_window_budget=110,
                        prompt_sha256=last['prompt_sha256'],
                        token_ids_sha256=last['token_ids_sha256'],
                        fullprompttoken_count=last['prompt_token_count'])
        return proposals, entries, forecast

    base_layout = [('EMPTY_WINDOWS_BASE', None, [], [], 100),
        ('WHOLE_UNIT_PROPOSAL', 0, [0], [], 150),
        ('WHOLE_UNIT_PROPOSAL', 1, [], [1], 160),
        ('FINAL_COMBINED_PROMPT', None, [0], [1], 210)]
    base_choices = [(0, 0, [(0, 2, 150)]), (1, 1, [(1, 3, 160)])]
    good = bundle(base_layout, base_choices)
    assert replay(record, arm, [0, 1, 2], *good)[1] == [0, 1]
    names = ['valid_two_disjoint_singletons']
    cap_layout = list(base_layout);cap_layout[-1] = ('FINAL_COMBINED_PROMPT', None, [0], [1], 320)
    assert len(replay(record, arm, [0, 1, 2], *bundle(cap_layout, base_choices))[0]) == 320
    names.append('exact_320_boundary_allowed')
    skip_layout = [('EMPTY_WINDOWS_BASE', None, [], [], 100),
        ('WHOLE_UNIT_PROPOSAL', 0, [0], [], 230),
        ('WHOLE_UNIT_PROPOSAL', 0, [1], [], 160),
        ('WHOLE_UNIT_PROPOSAL', 1, [], [0], 230),
        ('WHOLE_UNIT_PROPOSAL', 1, [], [2], 170),
        ('FINAL_COMBINED_PROMPT', None, [1], [2], 220)]
    skip_choices = [(0, 1, [(0, 2, 230), (1, 3, 160)]),
                    (1, 2, [(0, 4, 230), (2, 5, 170)])]
    assert replay(record, arm, [0, 1, 2], *bundle(skip_layout, skip_choices))[1] == [1, 2]
    names.append('first_admissible_skips_whole_oversize_units')

    def reject(name, data, ranking=None, changed_record=None):
        rejected(replay, changed_record or record, arm,
                 [0, 1, 2] if ranking is None else ranking, *data)
        names.append(name)
    bad_layout = list(base_layout);bad_layout[-1] = ('FINAL_COMBINED_PROMPT', None, [0], [1], 321)
    reject('final_321_rejected', bundle(bad_layout, base_choices))
    bad = copy.deepcopy(good);bad[0][1]['selected_unit_ids'][0] = [0, 1]
    reject('neighbor_group_rejected', bad)
    bad = copy.deepcopy(good);bad[2]['windows'][1]['source_unit_ids'] = [0]
    bad[2]['windows'][1]['duplicate_first'] = True
    reject('duplicate_first_fallback_rejected', bad)
    bad = copy.deepcopy(good);bad[2]['windows'][0]['source_spans'][0]['end'] -= 1
    reject('partial_unit_span_rejected', bad)
    bad = copy.deepcopy(good);bad[2]['windows'][1]['text_sha256'] = '0'*64
    reject('semantic_rewrite_or_truncated_text_rejected', bad)
    bad = copy.deepcopy(good);bad[2]['windows'][0]['equal_marginal_budget'] = 111
    reject('unequal_marginal_budget_rejected', bad)
    bad = copy.deepcopy(good);bad[0][2]['stage'] = 'WHOLE_GROUP_PROPOSAL'
    reject('old_whole_neighbor_stage_rejected', bad)
    bad = copy.deepcopy(good);bad[0].append(copy.deepcopy(bad[0][-1]))
    reject('extra_packing_proposal_rejected', bad)
    bad = copy.deepcopy(good);bad[0][1]['http_exchange'] = {'request_ordinal': 1, 'category':'prompt_tokenize'}
    reject('proposal_exchange_reuse_rejected', bad)
    bad = copy.deepcopy(good);bad[1][2]['request']['content'] += ' changed'
    reject('retained_prompt_body_mismatch_rejected', bad)
    bad = copy.deepcopy(good);bad[2]['windows'][0]['selection_decisions'][0]['accepted'] = False
    reject('forged_first_admissible_decision_rejected', bad)
    reject('changed_ranking_rejected', copy.deepcopy(good), ranking=[1, 0, 2])
    changed = copy.deepcopy(record);changed['claim'] += ' changed'
    reject('claim_truncation_or_rewrite_rejected', copy.deepcopy(good), changed_record=changed)
    missing_second_layout = [('EMPTY_WINDOWS_BASE', None, [], [], 100),
        ('WHOLE_UNIT_PROPOSAL', 0, [0], [], 150),
        ('WHOLE_UNIT_PROPOSAL', 1, [], [1], 230),
        ('WHOLE_UNIT_PROPOSAL', 1, [], [2], 240)]
    reject('no_second_admissible_unit_rejected', bundle(missing_second_layout, base_choices))
    missing_first_layout = [('EMPTY_WINDOWS_BASE', None, [], [], 100),
        ('WHOLE_UNIT_PROPOSAL', 0, [0], [], 230),
        ('WHOLE_UNIT_PROPOSAL', 0, [1], [], 240),
        ('WHOLE_UNIT_PROPOSAL', 0, [2], [], 250)]
    reject('no_first_admissible_unit_rejected', bundle(missing_first_layout, base_choices))
    bad_layout = list(base_layout);bad_layout[0] = ('EMPTY_WINDOWS_BASE', None, [], [], 320)
    reject('no_evidence_budget_rejected', bundle(bad_layout, base_choices))
    assert len(names) == len(set(names)) == 19
    return names


def main():
    with tempfile.TemporaryDirectory(prefix='e46-inert-opaque-') as directory:
        root = Path(directory)
        namespace = dict(hashlib=hashlib, json=json, os=os, stat=stat,
                         Path=Path, WORKDIR=root)
        names = ['require', 'sha', 'canonical', 'unique', 'read_ref', 'ref', 'put_bytes']
        exec(definitions(HERE / 'e47_features.py', names), namespace)
        features = SimpleNamespace(**{name: namespace[name] for name in names})
        features.KIND = 'INERT_FIXTURE_ONLY'
        custody = {'F': features, 're': re}
        exec(definitions(HERE / 'e47_materialize.py',
                         ['same', 'opaque_copy', 'verify_slot_binding']), custody)
        source = root / 'dummy.bin'
        source.write_bytes(b'opaque fixture bytes\x00\x80\xff')
        ref = features.ref(source)
        target = root / 'copy.bin'
        result = custody['opaque_copy'](ref, target)
        assert target.read_bytes() == source.read_bytes()
        assert result['bytes'] == ref['bytes'] and result['sha256'] == ref['sha256']
        rejected(custody['opaque_copy'], ref, target)
        rejected(features.read_ref, dict(ref, sha256='0' * 64))
        rejected(features.read_ref, dict(ref, bytes=True))
        rejected(features.read_ref, dict(ref, bytes=ref['bytes'] + 1))
        rejected(features.read_ref, dict(ref, actual_git_blob_sha1='0' * 40))
        link = root / 'link.bin'
        link.symlink_to(source)
        rejected(features.read_ref, dict(ref, path=str(link)))
        assert custody['same']({'x': [0, True]}, {'x': [0, True]})
        assert not custody['same']({'x': 0}, {'x': False})
        # Synthetic slot dictionaries only: source metadata is never constructed or read.
        slot = {'epoch': 47, 'kind': features.KIND, 'phase': 'dev',
                'generation': 1, 'pid': 1, 'startticks': 1, 'reserved_worker_slots': 1,
                'owner_sha256': 'a' * 64, 'reservation_token': 'b' * 64,
                'permanently_burned_at_SOURCE_publication': True}
        plan = {'worker_slot_reservation': slot,
                'owner_ref': {'path': 'owner.json', 'bytes': 10, 'sha256': 'a' * 64}}
        peer = {'worker_slot_reservation': dict(slot)}
        assert custody['verify_slot_binding'](plan, peer, peer, peer) == slot
        for field, value in [('epoch', 44), ('reserved_worker_slots', True),
                             ('permanently_burned_at_SOURCE_publication', False),
                             ('reservation_token', 'invalid'), ('owner_sha256', 'c' * 64)]:
            changed = dict(slot, **{field: value})
            wrong = {'worker_slot_reservation': changed}
            rejected(custody['verify_slot_binding'], plan, wrong, peer, peer)
        invalid = dict(plan, worker_slot_reservation=dict(slot, reserved_worker_slots=True))
        peer_invalid = {'worker_slot_reservation': invalid['worker_slot_reservation']}
        rejected(custody['verify_slot_binding'], invalid, peer_invalid, peer_invalid, peer_invalid)
    materializer = ast.parse((HERE / 'e47_materialize.py').read_text())
    calls = next(n for n in materializer.body if isinstance(n, ast.FunctionDef) and n.name == 'materialize')
    access = [n.lineno for n in ast.walk(calls) if isinstance(n, ast.Call) and
              isinstance(n.func, ast.Name) and n.func.id == 'opaque_copy']
    source_fence = [n.lineno for n in ast.walk(calls) if isinstance(n, ast.Call) and
                    isinstance(n.func, ast.Name) and n.func.id == 'verify_actual_source_before_data']
    assert access and source_fence and max(source_fence) < min(access)
    for path in HERE.glob('e47_*.py'):
        compile(path.read_text(), str(path), 'exec')
    compact = compact_fixtures(features)
    print(json.dumps({'checks_passed': True, 'inert_fixture_cases': 17,
                      'compact_metadata_fixture_cases': len(compact),
                      'compact_metadata_fixture_names': compact,
                      'fixture_scope': 'Invented source strings and retained-token metadata; not measured tokenization or benchmark generalization.',
                      'actual_target_functions': 0, 'actual_private_assets_read': 0,
                      'actual_archive_case_label_model_native_calls': 0}))


if __name__ == '__main__':
    main()
