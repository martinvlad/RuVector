"""Rebuild frozen data and exercise source/role/label-boundary mutation guards."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / 'epoch12/project/experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def check(folder, source):
    spec = importlib.util.spec_from_file_location('frozen_data_' + str(id(folder)), folder / 'build.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    contract = load(folder / 'data-contract.json')
    fitting = contract['fitting']
    if (contract['calibration'] != [] or fitting['supervised_fit'] is not False
            or fitting['model_precision_or_threshold_selection'] is not False
            or fitting['training_feature_queries'] != 0 or fitting['train_sanity_queries'] != 6
            or contract['training_questions'] != 6 or contract['training_feature_questions'] != 0
            or contract['train_sanity_questions'] != 6):
        raise ValueError('No fit, feature extraction, precision selection or calibration permitted')
    if (sha(folder / 'draw-plan.json') != contract['draw']['plan_sha256']
            or sha(folder / 'document-selection.json') != contract['draw']['selection_sha256']):
        raise ValueError('Frozen draw or roles changed')
    for role, datafile, allowfile, expected_n, groups, key in [
            ('dev', 'development24.jsonl', 'dev-allowlist.json', 24, 8, 'development'),
            ('train_sanity', 'train-sanity6.jsonl', 'train-allowlist.json', 6, 2, 'train')]:
        rows = builder.draw(source, role)
        raw = ''.join(json.dumps(x, ensure_ascii=False, allow_nan=False) + '\n' for x in rows).encode()
        if (hashlib.sha256(raw).hexdigest() != contract[key]['sha256']
                or (folder / datafile).read_bytes() != raw or len(rows) != expected_n
                or len({x['source_group'] for x in rows}) != groups
                or any(x['split'] != role for x in rows)):
            raise ValueError('Frozen projection bytes, role or counts changed')
        if builder.allow(rows, contract[key]['sha256'], role) != load(folder / allowfile):
            raise ValueError('Frozen label-free boundary allowlist changed')
    if sha(folder / 'confirmation-allowlist.json') != contract['confirmation']['allowlist_sha256']:
        raise ValueError('Reserved confirmation metadata changed')
    confirmation = load(folder / 'confirmation-allowlist.json')
    if (len(confirmation['records']) != 48
            or len({x['source_group'] for x in confirmation['records']}) != 16
            or confirmation['contains_labels_or_inputs'] is not False):
        raise ValueError('Reserved confirmation identity/count boundary changed')
    return {'DEV_queries': 24, 'DEV_document_groups': 8, 'TRAIN_sanity_queries': 6,
            'TRAIN_sanity_document_groups': 2, 'TRAIN_feature_queries': 0,
            'prior_exposed_groups': 173, 'reserved_confirmation_groups': 16,
            'eligible_before_draw': 234, 'unreserved_after_draw': 226,
            'exposed_after_actual_phase1_attempt': 181,
            'DEV_sha256': contract['development']['sha256'],
            'TRAIN_sanity_sha256': contract['train']['sha256'],
            'confirmation_metadata_only_sha256': sha(folder / 'confirmation-allowlist.json'),
            'source_sha256': sha(source)}


def mutate(folder, kind):
    files = {'roles': 'document-selection.json', 'TRAIN_roles': 'document-selection.json',
             'DEV_input': 'development24.jsonl', 'TRAIN_input': 'train-sanity6.jsonl',
             'DEV_allowlist': 'dev-allowlist.json', 'TRAIN_allowlist': 'train-allowlist.json',
             'confirmation_metadata': 'confirmation-allowlist.json', 'draw': 'draw-plan.json',
             'registry': 'eligibility-manifest.json', 'fitting': 'data-contract.json',
             'precision_selection': 'data-contract.json'}
    path = folder / files[kind]
    if kind in ('DEV_input', 'TRAIN_input'):
        path.write_bytes(path.read_bytes().replace(b'"state": "', b'"state": "MUTATED ', 1))
        return
    value = load(path)
    if kind == 'roles':
        value['documents'][0]['role'] = 'confirmation'
    elif kind == 'TRAIN_roles':
        value['train_sanity_documents'][0]['role'] = 'dev'
    elif kind in ('DEV_allowlist', 'TRAIN_allowlist'):
        value['records'][0]['input_sha256'] = '0' * 64
    elif kind == 'confirmation_metadata':
        value['records'][0]['source_group'] = 'original-contractnli:999999'
    elif kind == 'draw':
        value['train_sanity_salt'] += 'changed'
    elif kind == 'registry':
        value['excluded_document_ids'][0] = 999999
    elif kind == 'fitting':
        value['fitting']['supervised_fit'] = True
    elif kind == 'precision_selection':
        value['fitting']['model_precision_or_threshold_selection'] = True
    dump(path, value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, default=HERE / 'validation.json')
    args = parser.parse_args()
    assert not args.out.exists()
    proof = check(HERE, args.source)
    controls = []
    for kind in ['source', 'roles', 'TRAIN_roles', 'DEV_input', 'TRAIN_input', 'DEV_allowlist',
                 'TRAIN_allowlist', 'confirmation_metadata', 'draw', 'registry', 'fitting', 'precision_selection']:
        with tempfile.TemporaryDirectory(prefix='ruvector-e12-data-') as temporary:
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
    result = {'schema_version': 1, 'at': datetime.now(timezone.utc).isoformat(), 'checks_passed': True,
              'proof': proof, 'mutation_controls': controls,
              'confirmation_projection_parsed': False, 'reserved_annotations_used': False,
              'real_models_native_fits_paid_calls': 0}
    dump(args.out, result)
    print(json.dumps({'checks_passed': True, 'mutations_rejected': len(controls),
                      'out': str(args.out), 'sha256': sha(args.out)}))


if __name__ == '__main__':
    main()
