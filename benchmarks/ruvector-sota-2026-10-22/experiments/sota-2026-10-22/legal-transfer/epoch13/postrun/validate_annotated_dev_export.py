"""Independent exact validation of the existing, consumed DEV-only span export.

The original-train source is hash checked, then only the eight allowed document
objects are JSON-decoded. Other document objects are scanned for boundaries and
their leading IDs, without decoding their annotations or inspecting their labels.
No reserved confirmation projection is opened.
"""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
DATA = HERE.parent
S = DATA.parents[1]
SOURCE = S / 'epoch13/project/experiments/sota-2026-10-22/legal-transfer/epoch3/sources/original-train.json'
EXPORT = S / 'audit/epoch13/dev-annotation-spans-v1.json'
ACTUAL = S / 'epoch13/runs/development/records.jsonl'
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
DEV_SHA = '4eb38bf37b98562d12433c0a2791b2122c6f62ebf597eea9c941e72bd566ec1a'
EXPORT_SHA = 'ed8178dd1aa820590f7859f755c3f3471d9f1461bb17fdf37f97405c11f40218'
GROUPS = {172, 516, 324, 419, 156, 290, 385, 525}
HYPOTHESES = {'nda-17', 'nda-7', 'nda-3'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def load(path):
    return json.loads(path.read_text())


def selected_documents(raw):
    # Source layout is pinned. Boundaries are found without decoding any excluded
    # object, so no reserved document annotations are accessed by this validator.
    if digest(raw) != SOURCE_SHA:
        raise ValueError('Original licensed train source hash mismatch')
    text = raw.decode('utf-8')
    beginning = re.match(r'\s*\{\s*"documents"\s*:\s*\[', text)
    if beginning is None:
        raise ValueError('Pinned source top-level layout changed')
    cursor = beginning.end()
    scanned = []
    selected = {}
    while True:
        while text[cursor] in ' \r\n\t,':
            cursor += 1
        if text[cursor] == ']':
            break
        if text[cursor] != '{':
            raise ValueError('Unexpected document boundary')
        start = cursor
        depth, quoted, escaped = 0, False, False
        while cursor < len(text):
            character = text[cursor]
            if quoted:
                if escaped:
                    escaped = False
                elif character == '\\':
                    escaped = True
                elif character == '"':
                    quoted = False
            elif character == '"':
                quoted = True
            elif character == '{':
                depth += 1
            elif character == '}':
                depth -= 1
                if depth == 0:
                    cursor += 1
                    break
            cursor += 1
        if depth != 0 or quoted:
            raise ValueError('Unterminated source document')
        source_object = text[start:cursor]
        identity = re.match(r'\{\s*"id"\s*:\s*([0-9]+)\s*,', source_object)
        if identity is None:
            raise ValueError('Document leading identity is not source-only inspectable')
        document_id = int(identity.group(1))
        scanned.append(document_id)
        if document_id in GROUPS:
            if document_id in selected:
                raise ValueError('Duplicate allowed source identity')
            selected[document_id] = json.loads(source_object)
    if len(scanned) != 423 or len(set(scanned)) != 423 or set(selected) != GROUPS:
        raise ValueError('Source document count or exposed DEV identity mismatch')
    return selected, len(scanned)


def verify(export, dev, actual, documents):
    if (export['queries'] != 24 or export['document_groups'] != 8
            or export['source_revision'] != 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9'
            or export['source_train_sha256'] != SOURCE_SHA or export['DEV_sha256'] != DEV_SHA
            or export['actual_records_sha256'] != sha(ACTUAL)
            or export['reserved_confirmation_annotations_accessed'] is not False
            or export['model_native_session_or_fit_calls'] != 0):
        raise ValueError('Export source, scope or exposure metadata mismatch')
    if ([row['id'] for row in export['records']] != [row['id'] for row in dev]
            or [row['id'] for row in actual] != [row['id'] for row in dev]):
        raise ValueError('Export is not exactly the completed DEV24 identity/order')
    annotation_count, character_count, no_evidence = 0, 0, 0
    slices = []
    for projected, row in zip(export['records'], dev):
        document_id = row['provenance']['document_id']
        hypothesis = row['provenance']['hypothesis_id']
        if document_id not in GROUPS or hypothesis not in HYPOTHESES:
            raise ValueError('Export reaches beyond the eight exposed DEV groups')
        document = documents[document_id]
        state = document['text']
        if state != row['input']['state'] or digest(canonical(row['input']).encode()) != row['input_sha256']:
            raise ValueError('Exact source state or inference-input hash mismatch')
        if len(document['annotation_sets']) != 1:
            raise ValueError('Ambiguous source annotation set')
        annotation = document['annotation_sets'][0]['annotations'][hypothesis]
        ids = annotation['spans']
        if len(set(ids)) != len(ids) or any(type(index) is not int for index in ids):
            raise ValueError('Invalid original source span identity')
        coordinates = [document['spans'][index] for index in ids]
        expected = {'id': row['id'], 'source_group': row['source_group'],
                    'input_sha256': row['input_sha256'], 'source_split': 'train',
                    'document_id': document_id, 'hypothesis_id': hypothesis,
                    'source_state_sha256': digest(state.encode()),
                    'original_threeway_label': annotation['choice'],
                    'original_gold_span_ids': ids, 'original_gold_character_spans': coordinates}
        if projected != expected or annotation['choice'] != row['evaluation']['original_threeway_label']:
            raise ValueError('Export differs from exact exposed DEV source annotation')
        spans = []
        for index, coordinates in zip(ids, coordinates):
            if (len(coordinates) != 2 or any(type(position) is not int for position in coordinates)
                    or not 0 <= coordinates[0] < coordinates[1] <= len(state)
                    or not 0 <= index < len(document['spans'])):
                raise ValueError('Original annotation span cannot be mapped to source state')
            start, end = coordinates
            text = state[start:end]
            if len(text) != end - start:
                raise ValueError('Source coordinate slice length mismatch')
            spans.append({'source_span_id': index, 'start': start, 'end': end,
                          'length_characters': len(text), 'source_slice_sha256': digest(text.encode())})
            annotation_count += 1
            character_count += len(text)
        no_evidence += not bool(ids)
        slices.append({'id': row['id'], 'source_state_sha256': expected['source_state_sha256'],
                       'mapped_source_spans': spans})
    return {'queries': 24, 'document_groups': 8, 'annotated_span_references': annotation_count,
            'sum_annotated_span_lengths_characters_not_union': character_count,
            'records_without_annotated_spans': no_evidence, 'records': slices}


def frozen_data_pins():
    publication = load(DATA / 'publication-files.json')
    for record in publication['files']:
        path = DATA / record['relative_path']
        if path.stat().st_size != record['bytes'] or sha(path) != record['sha256']:
            raise ValueError('Previously frozen data file changed')
    return {'manifest_sha256': sha(DATA / 'publication-files.json'),
            'verified_frozen_files_including_manifest': len(publication['files']) + 1}


if __name__ == '__main__':
    output = HERE / 'annotation-export-validation-v1.json'
    if output.exists():
        raise SystemExit('Immutable report exists; no rerun/overwrite')
    pins = frozen_data_pins()
    if sha(EXPORT) != EXPORT_SHA or sha(DATA / 'development24.jsonl') != DEV_SHA:
        raise ValueError('Frozen exported evidence or DEV projection changed')
    documents, scanned_count = selected_documents(SOURCE.read_bytes())
    dev = [json.loads(line) for line in (DATA / 'development24.jsonl').read_text().splitlines()]
    actual = [json.loads(line) for line in ACTUAL.read_text().splitlines()]
    export = load(EXPORT)
    metadata = load(DATA / 'confirmation-allowlist.json')
    if {row['source_group'] for row in dev} & {row['source_group'] for row in metadata['records']}:
        raise ValueError('DEV identities collide with reserved confirmation metadata')
    proof = verify(export, dev, actual, documents)
    mutations = []
    for kind in ['span_offset', 'span_identity', 'state_hash', 'typed_gold', 'record_identity']:
        mutated = copy.deepcopy(export)
        record = next(row for row in mutated['records'] if row['original_gold_character_spans'])
        if kind == 'span_offset':
            record['original_gold_character_spans'][0][0] += 1
        elif kind == 'span_identity':
            record['original_gold_span_ids'][0] += 1
        elif kind == 'state_hash':
            record['source_state_sha256'] = '0' * 64
        elif kind == 'typed_gold':
            record['original_threeway_label'] = 'Invalid'
        elif kind == 'record_identity':
            record['id'] += ':mutated'
        try:
            verify(mutated, dev, actual, documents)
        except ValueError:
            mutations.append({'mutation': kind, 'rejected': True})
        else:
            raise ValueError('Annotation-export mutation escaped: ' + kind)
    assert frozen_data_pins() == pins
    result = {'schema_version': 1, 'at': datetime.now(timezone.utc).isoformat(), 'accepted': True,
              'scope': 'Independent postrun exact validation of existing audited export; only 24 completed permanently exposed DEV records from 8 groups, never fresh confirmation or a new benchmark score.',
              'source_revision': 'eced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
              'source_train_sha256': sha(SOURCE), 'source_license': 'CC-BY-4.0',
              'license_sha256': sha(DATA / 'CC-BY-4.0.txt'),
              'export_path': 'experiments/sota-2026-10-22/audit/epoch13/dev-annotation-spans-v1.json',
              'export_sha256': sha(EXPORT), 'DEV_sha256': DEV_SHA, 'actual_records_sha256': sha(ACTUAL),
              'source_document_IDs_scanned_without_decoding_excluded_annotations': scanned_count,
              'source_document_objects_JSON_decoded': len(documents), 'decoded_document_IDs': sorted(documents),
              'source_span_coordinate_mapping': 'Original stored integer positions; exact Python Unicode state[start:end] slices, start-inclusive/end-exclusive, no inferred or generated evidence.',
              'mapping_failures': [], 'proof': proof, 'negative_controls': mutations,
              'frozen_data_files_unchanged': pins, 'reserved_confirmation_projection_opened': False,
              'reserved_confirmation_annotation_objects_decoded_or_accessed': False,
              'confirmation_access': 'Label-free identity metadata allowlist only.',
              'model_native_session_fit_paid_publisher_calls': 0}
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'accepted': True, 'report_sha256': sha(output),
                      'evidence_spans': proof['annotated_span_references'], 'negative_controls': len(mutations)}))
