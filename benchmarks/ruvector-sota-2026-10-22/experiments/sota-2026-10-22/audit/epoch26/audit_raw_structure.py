"""Independent saved-raw context/retrieval/runtime replay; no source labels/ML."""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import re

ARMS = ('actual_native', 'lexical', 'positional')
IDS = [437, 614, 194, 174, 256, 490, 317, 196]
HYPOTHESES = ['nda-17', 'nda-7', 'nda-3']
NUMBER = r'(?<![\w])[-+\u2212]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?![\w])'


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def quantile(values, p):
    a = sorted(values)
    rank = (len(a)-1)*p
    low, high = math.floor(rank), math.ceil(rank)
    return a[low]+(rank-low)*(a[high]-a[low])


def audit(raw_path, input_path, execution_path):
    raw, bank, execution = read(raw_path), read(input_path), read(execution_path)
    checks, failures = [], []

    def check(name, value):
        checks.append(name)
        if not value:
            failures.append(name)

    expected = [(f'original-contractnli:train:epoch26:dev:{d}:{h}', d, h)
                for d in IDS for h in HYPOTHESES]
    cases = raw.get('cases', [])
    check('complete_fixed24case_identities',
        [(r['id'], r['document_id'], r['hypothesis_id']) for r in cases] == expected)
    check('input_fixed24identities',
        [(r['id'], r['document_id'], r['hypothesis_id']) for r in bank['records']] == expected)
    lookup = {r['id']: r for r in bank['records']}
    times = {a: [] for a in ARMS}
    omission = {a: {'numeric_literals': 0, 'numeric_literals_retained': 0,
                    'numeric_literals_omitted': 0, 'document_coverage': []} for a in ARMS}
    full_docs = set()
    for row in cases:
        prefix = row['id']+':'
        inp = lookup[row['id']]
        document, hypothesis = inp['document'], inp['hypothesis']
        check(prefix+'input_binding', row['input_sha256'] == inp['input_sha256'])
        check(prefix+'source_text_hashes', row['document_sha256'] == sha(document)
              and row['hypothesis_sha256'] == sha(hypothesis) and row['hypothesis'] == hypothesis)
        units = row['document_preparation']['units']
        full_docs.add(row['document_id'])
        cursor = 0
        for j, unit in enumerate(units):
            check(prefix+f'unit{j}:complete_contiguous', unit['id'] == j
                  and type(unit['start']) is int and type(unit['end']) is int
                  and unit['start'] == cursor < unit['end'] <= len(document))
            cursor = unit['end']
        check(prefix+'no_document_tail_clipping', cursor == len(document) and len(units) <= 192)
        chunks = [document[u['start']:u['end']] for u in units]
        q = set(re.findall(r'\w+', hypothesis.casefold()))
        words = [set(re.findall(r'\w+', c.casefold())) for c in chunks]
        scores = [len(q&w)/max(1, len(q|w)) for w in words]
        lex = sorted(range(len(chunks)), key=lambda j: (-scores[j], j))[:40]
        check(prefix+'lexical_Jaccard_scores', row['lexical_jaccard_scores'] == scores)
        native = row['native']
        check(prefix+'native_identity', native['case_id'] == row['id']
              and str(native['document_id']) == str(row['document_id']))
        check(prefix+'native_raw_order_preserved', native['ids'] == [int(h['id']) for h in native['raw_hits']]
              and len(native['ids']) == len(set(native['ids'])) == min(40, len(units))
              and native['native_order_used_without_replacement'] is True)
        rankings = {'actual_native': native['ids'], 'lexical': lex,
                    'positional': list(range(min(40, len(units))))}
        for arm in ARMS:
            item, tag = row['arms'][arm], prefix+arm+':'
            context = item['context']
            check(tag+'matched_observed_ranking', item['observed_ranking'] == rankings[arm]
                  and context['ranking_ids_considered'] == rankings[arm])
            check(tag+'same_source_only_prelude', context['definition_priority'] == row['document_preparation']['prelude'])
            selected = context['selected_chunk_ids_source_order']
            check(tag+'selected_unit_order_unique', selected == sorted(set(selected))
                  and all(type(i) is int and 0 <= i < len(units) for i in selected))
            spans = []
            for j in selected:
                start, end = units[j]['start'], units[j]['end']
                if spans and start == spans[-1][1]:
                    spans[-1][1] = end
                else:
                    spans.append([start, end])
            check(tag+'exact_selected_source_spans', context['selected_source_spans'] == spans)
            premise = '\n\n'.join(document[a:b] for a, b in spans)
            check(tag+'literal_source_rendering', item['premise'] == premise
                  and context['premise_sha256'] == sha(premise)
                  and context['hypothesis_sha256'] == sha(hypothesis))
            provenance = context['source_provenance']
            expected_prov = []
            for start, end in spans:
                expected_prov.append({'source_char_start': start, 'source_char_end': end,
                    'source_byte_start': len(document[:start].encode('utf-8')),
                    'source_byte_end': len(document[:end].encode('utf-8')),
                    'text': document[start:end], 'text_sha256': sha(document[start:end])})
            check(tag+'UTF8_literal_byte_provenance', provenance['selected_source_provenance'] == expected_prov)
            literals = []
            for m in re.finditer(NUMBER, document):
                text = m.group()
                literals.append({'source_char_start': m.start(), 'source_char_end': m.end(),
                    'source_byte_start': len(document[:m.start()].encode('utf-8')),
                    'source_byte_end': len(document[:m.end()].encode('utf-8')),
                    'text': text, 'text_sha256': sha(text),
                    'retained': any(a <= m.start() and m.end() <= b for a, b in spans),
                    'lexical_year_candidate': bool(re.fullmatch(r'\d{4}',text) and 1000 <= int(text) <= 2999)})
            check(tag+'all_frozen_grammar_numeric_literal_provenance', provenance['numeric_literal_pattern'] == NUMBER
                  and provenance['numeric_literals'] == literals)
            retained = sum(r['retained'] for r in literals)
            check(tag+'numeric_retained_omitted_counts', provenance['numeric_literals_retained'] == retained
                  and provenance['numeric_literals_omitted'] == len(literals)-retained)
            omission[arm]['numeric_literals'] += len(literals)
            omission[arm]['numeric_literals_retained'] += retained
            omission[arm]['numeric_literals_omitted'] += len(literals)-retained
            omission[arm]['document_coverage'].append(sum(b-a for a,b in spans)/len(document))
            selected_set = set(selected)
            groups = context['source_sentence_groups']
            check(tag+'complete_source_groups', all(set(g['unit_ids']) <= selected_set for g in groups
                  if g['group_id'] in context['selected_group_ids_admission_order']))
            check(tag+'omitted_units_counted', context['omitted_chunk_ids'] == [j for j in range(len(units)) if j not in selected_set])
            check(tag+'no_context_or_claim_truncation_or_override', context['selected_evidence_truncated'] is False
                  and context['claim_truncated'] is False and item['semantic_decision_override'] is False
                  and provenance['semantic_decision_override'] is False)
            reader = item['reader']
            check(tag+'actual_paired_token_count_no_hidden_truncation', item['joint_pair_tokens']
                  == context['joint_pair_tokens'] == reader['pair_tokens'] == reader['token_count']
                  and type(item['joint_pair_tokens']) is int and 0 < item['joint_pair_tokens'] <= 512)
            check(tag+'reader_literal_input_identity', reader['premise_sha256'] == sha(premise)
                  and reader['hypothesis_sha256'] == sha(hypothesis) and reader['prediction'] == item['decision'])
            component = item['context_seconds']+reader['latency_seconds']+(item['native_query_seconds'] or 0)
            check(tag+'finite_nonnegative_component_timing', math.isfinite(component) and component >= 0)
            times[arm].append(component)
    check('eight_complete_source_documents', full_docs == set(IDS))
    counters = raw.get('counters', {})
    for key, count in {'NLI_model_initializations':1,'NLI_model_initializations_completed':1,
            'NLI_forward_pairs_attempted':72,'NLI_forward_pairs_completed':72,'NLI_forwards':72,
            'NLI_forward_calls_attempted':72,'NLI_forward_calls_completed':72,
            'DEV_pairs_completed':72,'DEV_cases_completed':24,
            'native_helper_starts':1,'native_index_initializations_attempted':8,
            'native_index_initializations_completed':8,'native_queries_attempted':24,
            'native_queries_completed':24,'BGE_initializations_attempted':1,
            'BGE_initializations_completed':1,'ORT_sessions_attempted':1,'ORT_sessions_completed':1}.items():
        check('counter:'+key, counters.get(key) == count)
    for key in ['Python_network_operations_attempted','Node_network_operations_attempted',
        'benchmark_HTTP_requests','benchmark_label_reads','TRAIN_calibration_fits',
        'CONF_worker_attempts','CONF_annotation_choices','CONF_NLI_pairs','paid_API_calls',
        'GPU_calls','fits','paid_calls','confirmation_calls','generation_calls','generated_tokens',
        'training_steps','optimizer_steps','external_API_calls','train_calls','calibration_calls']:
        check('forbidden_zero:'+key, counters.get(key) == 0)
    check('no_Python_network_violations', raw.get('Python_network_violations') == [])
    events = raw.get('allowed_local_bind_events', [])
    check('local_bind_count_closure', len(events) == counters.get('Python_literal_loopback_binds_allowed'))
    for j, event in enumerate(events):
        try:
            address = ast.literal_eval(event['address'])
            shape = (type(address) is tuple and len(address) in [2,4]
                and type(address[1]) is int and 0 <= address[1] <= 65535
                and ((event['family'] == 2 and len(address) == 2 and address[0] == '127.0.0.1')
                    or (event['family'] == 10 and address[0] == '::1'
                        and (len(address) == 2 or (type(address[2]) is int and type(address[3]) is int
                                                  and address[2] == address[3] == 0)))))
        except (ValueError, SyntaxError, IndexError):
            shape = False
        check(f'allowed_bind{j}:literal_and_receipt', event['allowed'] is True
              and shape
              and event['bind_outcome'] in ['SUCCESS','ERROR'] and bool(event['stack'])
              and math.isfinite(event['monotonic_seconds']))
    check('raw_completed_without_errors', raw.get('errors') == []
          and raw.get('status') == 'COMPLETED_DEV_DIAGNOSTIC_AWAITING_INDEPENDENT_SCORER')
    check('outer_completed_cleanup', execution.get('status') == 'WORKER_COMPLETED'
          and execution.get('exit_code') == 0 and execution.get('owned_live_processes_closed') is True
          and execution.get('owned_live_group_members') == [])
    check('CPU2_wall600', execution.get('CPU_affinity') == [0,1]
          and 0 < execution.get('wall_seconds_including_init_cleanup',math.inf) <= 600)
    return {'schema_version':1,'epoch':26,'status':'PASS' if not failures else 'FAIL',
        'checks':len(checks),'failures':failures,'raw_errors':raw.get('errors',[]),
        'benchmark_accepted':False,'champion_promoted':False,'confirmation':[],
        'annotation_choices_accessed':0,'model_tokenizer_native_calls':0,
        'latency_context_plus_reader_plus_native_query':{a:{'n':len(v),
            'p50_seconds':quantile(v,.5) if v else None,'p95_seconds':quantile(v,.95) if v else None}
            for a,v in times.items()},'literal_retention_diagnostics':omission,
        'worker_resources':raw.get('resources'),'outer_execution':execution,
        'scope':'Saved source/byte/span/ID/ranking/count/arithmetic replay only. No model or tokenizer re-execution; token counts are cross-checked saved worker receipts. Numeric coverage covers the frozen lexical grammar, never numerical semantic completeness. No source choices read, legal absence proof, heldout generalization, superiority or benchmark acceptance.'}


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    for name in ['raw','inputs','execution','output']:
        p.add_argument('--'+name,required=True)
    a=p.parse_args()
    report=audit(a.raw,a.inputs,a.execution)
    with Path(a.output).open('x') as stream:
        stream.write(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({'status':report['status'],'checks':report['checks'],'failures':report['failures']}))
