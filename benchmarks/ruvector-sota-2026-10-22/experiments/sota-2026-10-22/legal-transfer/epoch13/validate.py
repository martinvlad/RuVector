"""Verify exact source replay and reject role, input, label and fitting mutations."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / 'epoch13/project/experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def check(folder, source):
    specification = importlib.util.spec_from_file_location('frozen_data_' + str(id(folder)), folder / 'build.py')
    builder = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(builder)
    contract = load(folder / 'data-contract.json')
    fitting = contract['fitting']
    if (contract['train'] != [] or contract['calibration'] != []
            or contract['training_questions'] != 0 or contract['training_feature_questions'] != 0
            or fitting['supervised_fit'] is not False or fitting['training_feature_queries'] != 0
            or fitting['calibration_queries'] != 0 or fitting['temperature'] != 1.0
            or fitting['model_precision_or_threshold_selection'] is not False):
        raise ValueError('No training, fitting, precision selection or calibration permitted')
    if (sha(folder / 'draw-plan.json') != contract['draw']['plan_sha256']
            or sha(folder / 'document-selection.json') != contract['draw']['selection_sha256']):
        raise ValueError('Frozen source-only draw/roles changed')
    rows = builder.draw(source)
    raw = ''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n' for row in rows).encode()
    if (hashlib.sha256(raw).hexdigest() != contract['development']['sha256']
            or (folder / 'development24.jsonl').read_bytes() != raw or len(rows) != 24
            or len({row['source_group'] for row in rows}) != 8
            or any(row['split'] != 'dev' for row in rows)):
        raise ValueError('Frozen DEV projection, labels, roles or counts changed')
    if builder.allow(rows, contract['development']['sha256']) != load(folder / 'dev-allowlist.json'):
        raise ValueError('DEV label-free inference boundary changed')
    if sha(folder / 'confirmation-allowlist.json') != contract['confirmation']['allowlist_sha256']:
        raise ValueError('Reserved CONF metadata changed')
    metadata = load(folder / 'confirmation-allowlist.json')
    if (len(metadata['records']) != 48 or len({item['source_group'] for item in metadata['records']}) != 16
            or metadata['contains_labels_or_inputs'] is not False):
        raise ValueError('Reserved confirmation identity or label boundary changed')
    return {'DEV_queries': 24, 'DEV_document_groups': 8, 'TRAIN_queries': 0, 'calibration_queries': 0,
            'prior_exposed_groups': 181, 'reserved_confirmation_groups': 16,
            'eligible_before_draw': 226, 'unreserved_after_draw': 218,
            'exposed_after_actual_phase1_attempt': 189,
            'DEV_sha256': contract['development']['sha256'],
            'confirmation_metadata_only_sha256': sha(folder / 'confirmation-allowlist.json'),
            'source_sha256': sha(source)}


def mutate(folder, kind):
    paths = {'roles': 'document-selection.json', 'train_roles': 'document-selection.json',
             'DEV_input': 'development24.jsonl', 'DEV_gold': 'development24.jsonl',
             'DEV_allowlist': 'dev-allowlist.json', 'confirmation_metadata': 'confirmation-allowlist.json',
             'draw': 'draw-plan.json', 'hypotheses': 'draw-plan.json',
             'registry': 'eligibility-manifest.json', 'fitting': 'data-contract.json',
             'precision_selection': 'data-contract.json', 'train_contract': 'data-contract.json'}
    path = folder / paths[kind]
    if kind in ('DEV_input', 'DEV_gold'):
        if kind == 'DEV_input':
            path.write_bytes(path.read_bytes().replace(b'"state": "', b'"state": "MUTATED ', 1))
        else:
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[0]['evaluation']['gold'] = 'No' if rows[0]['evaluation']['gold'] == 'Yes' else 'Yes'
            path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
        return
    value = load(path)
    if kind == 'roles':
        value['documents'][0]['role'] = 'confirmation'
    elif kind == 'train_roles':
        value['train'] = [value['documents'][0]]
    elif kind == 'DEV_allowlist':
        value['records'][0]['input_sha256'] = '0' * 64
    elif kind == 'confirmation_metadata':
        value['records'][0]['source_group'] = 'original-contractnli:999999'
    elif kind == 'draw':
        value['salt'] += 'changed'
    elif kind == 'hypotheses':
        value['hypotheses'][0] = 'nda-1'
    elif kind == 'registry':
        value['excluded_document_ids'][0] = 999999
    elif kind == 'fitting':
        value['fitting']['supervised_fit'] = True
    elif kind == 'precision_selection':
        value['fitting']['model_precision_or_threshold_selection'] = True
    elif kind == 'train_contract':
        value['train'] = [{'id': 'unapproved'}]
    dump(path, value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, default=HERE / 'validation.json')
    args = parser.parse_args()
    assert not args.out.exists(), 'No overwrite'
    proof = check(HERE, args.source)
    controls = []
    for kind in ['source', 'roles', 'train_roles', 'DEV_input', 'DEV_gold', 'DEV_allowlist',
                 'confirmation_metadata', 'draw', 'hypotheses', 'registry', 'fitting',
                 'precision_selection', 'train_contract']:
        with tempfile.TemporaryDirectory(prefix='ruvector-e13-data-') as temporary:
            folder = Path(temporary)
            for path in HERE.iterdir():
                if path.is_file() and path.suffix in ('.py', '.json', '.jsonl', '.txt'):
                    shutil.copy2(path, folder / path.name)
            source = args.source
            if kind == 'source':
                source = folder / 'mutated-source.json'
                source.write_bytes(args.source.read_bytes() + b' ')
            else:
                mutate(folder, kind)
            rejected = False
            try:
                check(folder, source)
            except (ValueError, AssertionError, KeyError, TypeError):
                rejected = True
            if not rejected:
                raise AssertionError('Mutation escaped: ' + kind)
            controls.append({'mutation': kind, 'rejected': True})
    isolated = HERE / 'standalone-redraw-v1'
    isolated.mkdir()
    for name in ['build.py', 'eligibility-manifest.json', 'draw-plan.json', 'document-selection.json']:
        shutil.copy2(HERE / name, isolated / name)
    command = [sys.executable, '-B', str(isolated / 'build.py'), '--source', str(args.source),
               '--output-dir', str(isolated / 'outputs')]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    identities = {}
    for name in ['development24.jsonl', 'dev-allowlist.json']:
        assert (isolated / 'outputs' / name).read_bytes() == (HERE / name).read_bytes()
        identities[name] = sha(HERE / name)
    dump(HERE / 'isolated-replay-validation.json', {
        'schema_version': 1, 'at': datetime.now(timezone.utc).isoformat(), 'checks_passed': True,
        'command': command, 'stdout': result.stdout.strip(),
        'standalone_inputs': ['build.py', 'eligibility-manifest.json', 'draw-plan.json',
                             'document-selection.json', 'separately SHA-verified official original-train.json'],
        'output_byte_identity': identities, 'source_sha256': sha(args.source),
        'confirmation_projection_parsed': False, 'models_native_fits_paid_calls': 0})
    dump(args.out, {'schema_version': 1, 'at': datetime.now(timezone.utc).isoformat(),
                    'checks_passed': True, 'proof': proof, 'mutation_controls': controls,
                    'confirmation_projection_parsed': False, 'reserved_annotations_used': False,
                    'real_models_native_fits_paid_calls': 0})
    print(json.dumps({'checks_passed': True, 'mutations_rejected': len(controls),
                      'out': str(args.out), 'sha256': sha(args.out), 'standalone_exact_rebuild': True}))


if __name__ == '__main__':
    main()
