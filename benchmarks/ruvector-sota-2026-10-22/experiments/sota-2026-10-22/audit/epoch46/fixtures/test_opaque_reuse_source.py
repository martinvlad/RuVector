"""Inert changed-custody fixture: dummy bytes only, no source module import."""
import ast
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


def main():
    with tempfile.TemporaryDirectory(prefix='e46-inert-opaque-') as directory:
        root = Path(directory)
        namespace = dict(hashlib=hashlib, json=json, os=os, stat=stat,
                         Path=Path, WORKDIR=root)
        names = ['require', 'sha', 'canonical', 'unique', 'read_ref', 'ref', 'put_bytes']
        exec(definitions(HERE / 'e46_features.py', names), namespace)
        features = SimpleNamespace(**{name: namespace[name] for name in names})
        features.KIND = 'INERT_FIXTURE_ONLY'
        custody = {'F': features, 're': re}
        exec(definitions(HERE / 'e46_materialize.py',
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
        slot = {'epoch': 46, 'kind': features.KIND, 'phase': 'dev',
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
    materializer = ast.parse((HERE / 'e46_materialize.py').read_text())
    calls = next(n for n in materializer.body if isinstance(n, ast.FunctionDef) and n.name == 'materialize')
    access = [n.lineno for n in ast.walk(calls) if isinstance(n, ast.Call) and
              isinstance(n.func, ast.Name) and n.func.id == 'opaque_copy']
    source_fence = [n.lineno for n in ast.walk(calls) if isinstance(n, ast.Call) and
                    isinstance(n.func, ast.Name) and n.func.id == 'verify_actual_source_before_data']
    assert access and source_fence and max(source_fence) < min(access)
    for path in HERE.glob('e46_*.py'):
        compile(path.read_text(), str(path), 'exec')
    print(json.dumps({'checks_passed': True, 'inert_fixture_cases': 17,
                      'actual_target_functions': 0, 'actual_private_assets_read': 0,
                      'actual_archive_case_label_model_native_calls': 0}))


if __name__ == '__main__':
    main()
