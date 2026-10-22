"""Static ONNX protobuf metadata; no model-library import or initialization."""
from __future__ import annotations
import importlib.util
import mmap
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch7_static_proto', HERE.parent / 'epoch5/preflight.py')
PROTO = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PROTO)


def inspect(path):
    output = {'inputs': [], 'outputs': [], 'opsets': [], 'operators': {},
              'external_initializers': [], 'session_initialized': False, 'forwards': 0}
    with Path(path).open('rb') as file, mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as buffer:
        graph = None
        for number, wire, a, b, value in PROTO.fields(buffer, 0, len(buffer)):
            if number == 1 and wire == 0:
                output['ir_version'] = value
            elif number == 7 and wire == 2:
                graph = a, b
            elif number == 8 and wire == 2:
                item = {'domain': ''}
                for key, kind, start, end, item_value in PROTO.fields(buffer, a, b):
                    if key == 1 and kind == 2:
                        item['domain'] = buffer[start:end].decode()
                    if key == 2 and kind == 0:
                        item['version'] = item_value
                output['opsets'].append(item)
        if graph is None:
            raise ValueError('ONNX graph missing')
        for number, wire, a, b, value in PROTO.fields(buffer, *graph):
            if wire != 2:
                continue
            if number in (11, 12):
                output['inputs' if number == 11 else 'outputs'].append(PROTO.value_info(buffer, a, b))
            elif number == 5:
                name, external = '', False
                for key, kind, start, end, item_value in PROTO.fields(buffer, a, b):
                    if key == 8 and kind == 2:
                        name = buffer[start:end].decode()
                    if key == 13 and kind == 2 or key == 14 and kind == 0 and item_value == 1:
                        external = True
                if external:
                    output['external_initializers'].append(name)
            elif number == 1:
                domain, operation = '', ''
                for key, kind, start, end, item_value in PROTO.fields(buffer, a, b):
                    if key == 4 and kind == 2:
                        operation = buffer[start:end].decode()
                    if key == 7 and kind == 2:
                        domain = buffer[start:end].decode()
                key = domain + '::' + operation
                output['operators'][key] = output['operators'].get(key, 0) + 1
    inputs = {item['name']: item for item in output['inputs']}
    if not {'input_ids', 'attention_mask'} <= set(inputs) <= {'input_ids', 'attention_mask', 'token_type_ids'}:
        raise ValueError('Unsupported binary NLI feeds')
    if any(item.get('tensor_element_type') != 7 or len(item.get('dimensions', [])) != 2 for item in inputs.values()):
        raise ValueError('Expected rank-two int64 inputs')
    if len(output['outputs']) != 1 or output['outputs'][0].get('tensor_element_type') != 1:
        raise ValueError('Expected one float32 logits output')
    dimensions = output['outputs'][0].get('dimensions', [])
    if len(dimensions) != 2 or dimensions[1].get('value') != 2:
        raise ValueError('Expected binary logits dimension2')
    if output['external_initializers']:
        raise ValueError('ONNX requires assets beyond the frozen six-file closure')
    return output
