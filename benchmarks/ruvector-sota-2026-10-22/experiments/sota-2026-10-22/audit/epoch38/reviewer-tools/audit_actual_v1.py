"""Independent retained-record arithmetic/provenance audit. No scorer imports."""
import collections
from fractions import Fraction as F
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct

ROOT = Path('/tmp/ruvector-sota-2026-10-22/epoch38-7c50ba99848f/project')
OWN = Path('/workspace/ruvector-e38-acceptance-audit')
P = 'experiments/sota-2026-10-22/'
E, A = P + 'epoch38/', P + 'audit/epoch38/'
ARMS = ['full_raw', 'native_raw', 'native_verified', 'lexical_verified', 'full_verified']
REUSE = dict(zip(ARMS, ['full_source', 'native_coverage', 'native_coverage', 'lexical_coverage', 'full_source']))
LABELS = ['Entailment', 'Contradiction', 'NotMentioned']
NATIVE = ['Contradiction', 'NotMentioned', 'Entailment']
LOWER = dict(zip(LABELS, ['entailment', 'contradiction', 'not_mentioned']))
EPS = 1e-12

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def sha(x):
    return hashlib.sha256(x.encode() if isinstance(x, str) else x).hexdigest()

def contents(rel):
    p = ROOT / rel
    assert p.is_file() and not any(z.is_symlink() for z in (p, *p.parents))
    return p.read_bytes()

def ref(rel):
    b = contents(rel)
    return dict(path=rel, bytes=len(b), sha256=sha(b))

def read(rel):
    return json.loads(contents(rel))

def checked(row):
    assert ref(row['path']) == row

def close(a, b, eps=EPS):
    assert math.isfinite(a) and math.isfinite(b) and abs(a-b) <= eps, (a, b)

def rat(x):
    assert isinstance(x, list) and len(x) == 2 and all(type(z) is int for z in x) and x[1] > 0
    q = F(*x)
    assert [q.numerator, q.denominator] == x
    return q

def qp(q):
    return [q.numerator, q.denominator]

UNITS = {'USD': (F(1), 'USD'), 'thousand USD': (F(1000), 'USD'),
    'million USD': (F(1000000), 'USD'), 'billion USD': (F(1000000000), 'USD'),
    'percent': (F(1,100), 'ratio'), 'percentage points': (F(1,100), 'ratio'),
    'basis points': (F(1,10000), 'ratio'), 'items': (F(1), 'items')}
NUM = r'[-+]?\d+(?:\.\d+)?(?:/\d+)?'
PREFIX = r'For "([^"]+)" in "([^"]+)", '

def statement(text):
    m = re.fullmatch(PREFIX + r'(.+)\.', text); assert m, text
    ent, period, tail = m.groups(); base = dict(entity=ent, period=period)
    m = re.fullmatch(r'"([^"]+)" is exactly ('+NUM+r') (.+)', tail)
    if m:
        name, n, unit = m.groups(); scale, dim = UNITS[unit]; val = F(n)*scale
        return dict(kind='exact', **base, metric=name, lower=qp(val), upper=qp(val), unit=unit, dimension=dim)
    m = re.fullmatch(r'"([^"]+)" is between ('+NUM+r') and ('+NUM+r') (.+) inclusive', tail)
    if m:
        name, lo, hi, unit = m.groups(); scale, dim = UNITS[unit]
        return dict(kind='interval', **base, metric=name, lower=qp(F(lo)*scale), upper=qp(F(hi)*scale), unit=unit, dimension=dim)
    m = re.fullmatch(r'"([^"]+)" equals "([^"]+)" (plus|minus) "([^"]+)"', tail)
    if m:
        name, left, op, right = m.groups()
        return dict(kind='binary', **base, metric=name, left=left, operator=op, right=right)
    m = re.fullmatch(r'"([^"]+)" equals ('+NUM+r') times "([^"]+)"', tail)
    if m:
        name, scalar, operand = m.groups()
        return dict(kind='scale', **base, metric=name, scalar=qp(F(scalar)), operand=operand)
    m = re.fullmatch(r'"([^"]+)" equals "([^"]+)" divided by ('+NUM+r')', tail)
    if m:
        name, operand, scalar = m.groups()
        return dict(kind='divide', **base, metric=name, scalar=qp(F(scalar)), operand=operand)
    m = re.fullmatch(r'the universe has exactly (\d+) items', tail)
    if m: return dict(kind='universe', **base, value=int(m[1]))
    m = re.fullmatch(r'"([^"]+)" contains exactly (\d+) items', tail)
    if m: return dict(kind='set', **base, value=int(m[2]), set_name=m[1])
    raise AssertionError(('Unsupported retained audit grammar', text))

def claim_parse(text):
    m = re.fullmatch(PREFIX + r'(.+)\.', text); assert m
    ent, period, tail = m.groups(); base = dict(entity=ent, period=period)
    cmp = r'(exactly|at least|at most|more than|less than)'
    m = re.fullmatch(r'"([^"]+)" is '+cmp+r' ('+NUM+r') (.+)', tail)
    if m:
        name, op, n, unit = m.groups(); scale, dim = UNITS[unit]
        return dict(kind='amount', **base, metric=name, comparison=op, value=qp(F(n)*scale), unit=unit, dimension=dim)
    m = re.fullmatch(r'the (union|overlap) of "([^"]+)" and "([^"]+)" contains '+cmp+r' ('+NUM+r') items', tail)
    assert m, tail
    op, a, b, cmp, n = m.groups()
    return dict(kind='cardinality', **base, operation=op, sets=sorted([a,b]), comparison=cmp, value=qp(F(n)), dimension='items')

def truth(value, cmp, target):
    return {'exactly': value == target, 'at least': value >= target, 'at most': value <= target,
            'more than': value > target, 'less than': value < target}[cmp]

def prove(case):
    analysis = case['source_analysis']; document = case['document']; hypothesis = case['hypothesis']
    assert analysis['document_sha256'] == case['document_sha256'] == sha(document)
    assert analysis['hypothesis_sha256'] == case['hypothesis_sha256'] == sha(hypothesis)
    assert analysis['analysis_sha256'] == sha(canonical({k:v for k,v in analysis.items() if k != 'analysis_sha256'}))
    clauses = analysis['source_clauses']; atoms = []; roots = {}; defs = {}; frames = {}; index = {}
    assert analysis['all_supplied_clauses_parsed'] is analysis['source_model_consistent'] is True
    assert analysis['status'] == 'CERTIFICATE_CANDIDATE'
    spans = [tuple(z['span']) for z in clauses]
    assert len(spans) == len(set(spans)) and spans == sorted(spans)
    cursor = 0
    for i, row in enumerate(clauses):
        start, end = row['span']; assert document[cursor:start].strip() == ''
        assert row['clause_id'] == i and document[start:end] == row['text']
        assert sha(row['text']) == row['text_sha256']; cursor = end
        atom = statement(row['text']); assert atom == row['atom']; atoms.append(atom)
        key = (atom['entity'], atom['period'])
        if atom['kind'] in ('universe', 'set'):
            f = frames.setdefault(key, {'sets': {}, 'deps': []}); f['deps'].append(i)
            if atom['kind'] == 'universe': assert 'n' not in f; f['n'] = atom['value']
            else: assert atom['set_name'] not in f['sets']; f['sets'][atom['set_name']] = atom['value']
        else:
            key += (atom['metric'],); assert key not in index; index[key] = i
            if atom['kind'] in ('exact', 'interval'):
                lo, hi = rat(atom['lower']), rat(atom['upper']); assert lo <= hi
                roots[key] = (lo, hi, atom['dimension'], atom['dimension'] == 'items')
            else: defs[key] = atom
    assert document[cursor:].strip() == ''
    cache = {}; active = set()
    def form(key):
        if key in cache: return cache[key]
        assert key not in active; active.add(key)
        if key in roots:
            lo, hi, dim, integer = roots[key]
            if integer: assert lo.denominator == hi.denominator == 1
            out = (lo, {}, dim, {index[key]}) if lo == hi else (F(0), {key:F(1)}, dim, {index[key]})
        else:
            a = defs[key]; scope = key[:2]
            if a['kind'] == 'binary':
                x, y = form(scope+(a['left'],)), form(scope+(a['right'],)); assert x[2] == y[2]
                sign = 1 if a['operator'] == 'plus' else -1; coeff = dict(x[1])
                for k,v in y[1].items(): coeff[k] = coeff.get(k,F(0)) + sign*v
                out = (x[0]+sign*y[0], {k:v for k,v in coeff.items() if v}, x[2], x[3]|y[3]|{index[key]})
            else:
                x = form(scope+(a['operand'],)); scalar = rat(a['scalar'])
                factor = scalar if a['kind'] == 'scale' else 1/scalar
                out = (x[0]*factor, {k:v*factor for k,v in x[1].items() if v*factor}, x[2], x[3]|{index[key]})
        active.remove(key); cache[key] = out; return out
    for key in defs: form(key)
    for scope, f in frames.items():
        assert set(f) == {'sets','deps','n'} and len(f['sets']) == 2
        assert all(0 <= v <= f['n'] for v in f['sets'].values())
        a,b = [f['sets'][k] for k in sorted(f['sets'])]
        f['lo'],f['hi'] = max(0,a+b-f['n']),min(a,b)
        assert f['lo'] <= f['hi']
    proof = analysis['proof']; claim = claim_parse(hypothesis); assert proof['claim'] == claim
    scope = (claim['entity'], claim['period']); target = rat(claim['value'])
    if claim['kind'] == 'amount':
        key = scope+(claim['metric'],); const, coeff, dim, deps = form(key); assert dim == claim['dimension']
        lo = const + sum(v*(roots[k][0] if v >= 0 else roots[k][1]) for k,v in coeff.items())
        hi = const + sum(v*(roots[k][1] if v >= 0 else roots[k][0]) for k,v in coeff.items())
        d = proof['derivation']; assert d['kind'] == 'AFFINE_QUANTITY' and d['binding'] == list(key)
        assert rat(d['constant']) == const and d['dimension'] == dim
        assert {tuple(x['binding']):rat(x['coefficient']) for x in d['coefficients']} == coeff
        assert {tuple(x['binding']):(rat(x['lower']),rat(x['upper']),x['integer_domain']) for x in d['independent_root_domains']} == {k:(v[0],v[1],v[3]) for k,v in roots.items()}
    else:
        f = frames[scope]; assert sorted(f['sets']) == claim['sets']; total = sum(f['sets'].values())
        lo,hi = ((F(total-f['hi']),F(total-f['lo'])) if claim['operation'] == 'union' else (F(f['lo']),F(f['hi'])))
        deps = set(f['deps']); d = proof['derivation']; family = d['family']
        assert d['kind'] == 'INTEGER_TWO_SET_CARDINALITY' and d['operation'] == claim['operation']
        assert family['universe'] == f['n'] and family['set_names'] == sorted(f['sets'])
        assert family['set_counts'] == [f['sets'][k] for k in sorted(f['sets'])]
        assert (family['overlap_lower'],family['overlap_upper']) == (f['lo'],f['hi'])
    assert rat(proof['lower']) == lo and rat(proof['upper']) == hi
    op = claim['comparison']
    if op == 'exactly': entailed = lo == hi == target; contradicted = target < lo or target > hi
    elif op == 'at least': entailed = lo >= target; contradicted = hi < target
    elif op == 'at most': entailed = hi <= target; contradicted = lo > target
    elif op == 'more than': entailed = lo > target; contradicted = hi <= target
    else: entailed = hi < target; contradicted = lo >= target
    conclusion = 'Entailment' if entailed else 'Contradiction' if contradicted else 'NotMentioned'
    assert proof['conclusion'] == conclusion
    truths = []
    assert len(proof['compatible_worlds']) == 2
    for world in proof['compatible_worlds']:
        values = {tuple(x['binding']):rat(x['value']) for x in world['amount_variables']}
        assert set(values) == set(roots) and len(values) == len(world['amount_variables'])
        for r in world['amount_variables']:
            key = tuple(r['binding']); lo0,hi0,dim,integer = roots[key]; value = values[key]
            assert lo0 <= value <= hi0 and (not integer or value.denominator == 1)
            assert r['dimension'] == dim and r['integer_domain'] is integer
        deriv = {tuple(x['binding']):x for x in world['derived_values']}; assert set(deriv) == set(defs)
        for key in defs:
            constant,coeff,dim,_ = form(key); value = constant + sum(v*values[k] for k,v in coeff.items())
            assert rat(deriv[key]['value']) == value and deriv[key]['dimension'] == dim
            assert dim != 'items' or value.denominator == 1
        tables = {tuple(x['binding']):x for x in world['set_tables']}; assert set(tables) == set(frames)
        for scope0, f in frames.items():
            table = tables[scope0]; names = sorted(f['sets']); a,b = [f['sets'][n] for n in names]; both = table['both']
            cells = [both,a-both,b-both,f['n']-a-b+both]
            assert all(type(z) is int and z >= 0 for z in cells) and sum(cells) == f['n']
            assert table['sets'] == names and table['marginals'] == [a,b] and table['universe'] == f['n']
            assert table['overlap_bounds'] == [f['lo'],f['hi']] and f['lo'] <= both <= f['hi']
            assert [table[k] for k in ('both','only_first','only_second','neither')] == cells
        if claim['kind'] == 'amount':
            constant,coeff,_,_ = form(scope+(claim['metric'],)); value = constant + sum(v*values[k] for k,v in coeff.items())
        else:
            table = tables[scope]; value = F(table['both'] if claim['operation'] == 'overlap' else sum(table['marginals'])-table['both'])
        assert value == rat(world['claim_value']) and world['all_source_constraints_satisfied'] is True
        t = truth(value, op, target); assert world['claim_truth'] is t; truths.append(t)
    assert (all(truths) if conclusion == 'Entailment' else not any(truths) if conclusion == 'Contradiction' else set(truths) == {True,False})
    needed = list(range(len(clauses))) if conclusion == 'NotMentioned' else sorted(deps)
    assert proof['required_clause_ids'] == needed
    assert analysis['required_source_spans'] == [clauses[i]['span'] for i in needed]
    return {'id':case['id'], 'conclusion':conclusion, 'exact_lower':qp(lo), 'exact_upper':qp(hi),
            'source_clauses':len(clauses), 'compatible_worlds_checked':2, 'neutral_distinct_truth_worlds':conclusion == 'NotMentioned'}

def quantile(values, q):
    values = sorted(values); position = (len(values)-1)*q; i = int(position); f = position-i
    return values[i]*(1-f)+values[min(i+1,len(values)-1)]*f

def main():
    # Authenticate actual closure before opening retained joined-label records.
    closure_ref = ref(E+'SUPERVISOR_OBSERVED_CLOSURE.json')
    assert closure_ref['sha256'] == '328ab8e4220413897153bf917d4ab33af907e155d2cb23bcb9f23dd5639da324'
    closure = read(closure_ref['path'])
    assert closure['physical_closure_passed'] is closure['physical_supervisor_closed'] is True
    assert closure['physical_supervisor_absent'] is closure['unknown_physical_ownership'] is False
    assert closure['owned_worker_group_members'] == [] and closure['observed_supervisor_state'] == 'Z'
    for key in ('execution','supervisor_completion','dispatch_attempt','dispatch_reservation'): checked(closure[key])
    result = read(E+'RESULTS.json'); evaluation = read(A+'EVALUATE.json'); binding = read(A+'INDEPENDENT_REPORT.json')
    assert ref(E+'RESULTS.json')['sha256'] == '07fce020d231e952008e87927a4dec3e494ba22e5683f686137e5957cac512d4'
    assert all(canonical(result[k]) == canonical(v) for k,v in evaluation.items())
    assert all(canonical(binding[k]) == canonical(v) for k,v in evaluation.items() if k != 'evidence')
    assert all(binding['evidence'][k] == v for k,v in evaluation['evidence'].items())
    assert binding['evaluated_integrity_checks_passed'] is binding['publication_binding_checks_passed'] is True
    raw = read(E+'runs/engineering/raw.json'); execution = read(E+'runs/engineering/execution.json')
    assert execution['raw_sha256'] == ref(E+'runs/engineering/raw.json')['sha256']
    assert execution['raw_bytes'] == ref(E+'runs/engineering/raw.json')['bytes']
    assert execution['exit_code'] == 0 and execution['worker_popen_attempts'] == execution['verified_worker_starts'] == 1
    assert execution['uncertain_start'] is False and execution['owned_live_processes_closed'] is True
    assert execution['operation_counts_complete'] is True and execution['raw_operation_counters'] == raw['counters']
    assert raw['errors'] == [] and raw['data_roles'] == dict.fromkeys(['train','dev','calibration','confirmation'], [])
    assert raw['used_confirmation_identities'] == [] and raw['confirmation'] == raw['calibration'] == []
    cases = raw['corpora']['engineering']['cases']; assert len(cases) == 12 and len({r['id'] for r in cases}) == 12
    proofs = [prove(case) for case in cases]
    records = {a:[] for a in ARMS}; timing = {a:[] for a in ARMS}; ids = set(); token_lengths = []; verified_certs = 0
    unit_total = 0; native_lexical_context_equal = []; raw_vs_derived = collections.Counter()
    golds = raw['engineering_gate']['expected_labels']; assert set(golds) == {r['id'] for r in cases}
    for case, proof in zip(cases, proofs):
        gold = golds[case['id']]; assert gold in LABELS and proof['conclusion'] == gold
        doc = raw['corpora']['engineering']['documents'][str(case['document_id'])]; units = doc['units']; unit_total += len(units)
        assert len(case['native']['ids']) == len(set(case['native']['ids'])) == len(units)
        assert case['native_complete_unique_unitset_verified'] is True
        native_lexical_context_equal.append(case['readouts']['native_coverage']['premise'] == case['readouts']['lexical_coverage']['premise'])
        physical = {}
        for context, r in case['readouts'].items():
            assert context in set(REUSE.values()) and r['readout_id'] == case['id']+'::NLI:'+context
            assert r['readout_id'] not in ids; ids.add(r['readout_id'])
            reader = r['reader']; logits = reader['raw_logits']; assert len(logits) == 3
            assert all(math.isfinite(x) and struct.unpack('<f',struct.pack('<f',x))[0] == x for x in logits)
            assert reader['actual_logits_dtype'] == 'torch.float32' and reader['actual_logits_device'] == 'cpu'
            assert reader['raw_logits_C_N_E'] == logits and reader['native_label_order'] == NATIVE
            shifted = [x-max(logits) for x in logits]; z = math.fsum(math.exp(x) for x in shifted)
            native_p = [math.exp(x)/z for x in shifted]; native_lp = [x-math.log(z) for x in shifted]
            probs = [native_p[i] for i in [2,0,1]]; logs = [native_lp[i] for i in [2,0,1]]
            for x,y in zip(probs, reader['probabilities_E_C_N']): close(x,y)
            winner = NATIVE[max(range(3),key=lambda i:logits[i])]; assert reader['native_typed_argmax'] == winner
            assert reader['premise_sha256'] == sha(r['premise']) and reader['hypothesis_sha256'] == sha(case['hypothesis'])
            ctx = r['context']; spans = ctx['selected_source_spans']
            assert spans == sorted(spans) and all(0 <= a < b <= len(case['document']) for a,b in spans)
            assert all(spans[i][1] <= spans[i+1][0] for i in range(len(spans)-1))
            assert r['premise'] == '\n\n'.join(case['document'][a:b] for a,b in spans)
            assert reader['pair_tokens'] == reader['full_pair_tokens'] == r['joint_pair_tokens'] <= 512
            assert reader['hidden_truncation'] is False and ctx['selected_evidence_truncated'] is False and ctx['claim_truncated'] is False
            token_lengths.append(r['joint_pair_tokens'])
            physical[context] = (probs,logs,winner,r)
        for arm in ARMS:
            a = case['arms'][arm]; probs,logs,winner,r = physical[REUSE[arm]]
            assert a['neural_readout_ref'] == r['readout_id'] and a['measured_context'] == REUSE[arm]
            for key in ('reader','premise','context','joint_pair_tokens','context_seconds','native_query_seconds'): assert canonical(a[key]) == canonical(r[key])
            reuse = a['readout_reuse_receipt']; assert reuse['actual_readout_id'] == r['readout_id'] and reuse['raw_reader_canonical_sha256'] == sha(canonical(r['reader']))
            assert reuse['physical_reader_unchanged'] is reuse['derived_forecast_did_not_call_model'] is True
            assert a['extra_neural_readouts'] == 0
            d = a['decision']; p,l = list(probs),list(logs); target = None
            if arm.endswith('_verified'):
                cert = d['certificate']; assert cert is not None; verified_certs += 1
                assert cert['full_source_analysis'] == case['source_analysis']
                assert cert['document_sha256'] == sha(case['document']) and cert['hypothesis_sha256'] == sha(case['hypothesis']) and cert['premise_sha256'] == sha(r['premise'])
                assert cert['selected_source_spans'] == r['context']['selected_source_spans']
                assert all(any(x <= a0 and b0 <= y for x,y in cert['selected_source_spans']) for a0,b0 in case['source_analysis']['required_source_spans'])
                target = proof['conclusion']; old,new = LABELS.index(winner),LABELS.index(target)
                p[old],p[new] = p[new],p[old]; l[old],l[new] = l[new],l[old]
            else: assert d['certificate'] is None and d['policy'] == 'RAW_T1_CONTROL_NO_CERTIFICATE'
            pred = target or winner
            for x,y in zip(d['raw_probabilities_E_C_N'],probs): close(x,y)
            for x,y in zip(d['final_probabilities_E_C_N'],p): close(x,y)
            for x,y in zip(d['final_log_probabilities_E_C_N'],l): close(x,y)
            assert d['final_typed_argmax'] == pred and d['raw_typed_argmax'] == winner
            assert d['fitting'] is d['calibrated_posterior_claim'] is False and d['extra_NLI_calls'] == 0
            g = LABELS.index(gold); brier = math.fsum((x-int(i==g))**2 for i,x in enumerate(p)); nll = -l[g]
            row = dict(id=case['id'], gold=LOWER[gold], prediction=LOWER[pred], correct=int(pred==gold), Brier=brier, NLL=nll, p_gold=p[g])
            records[arm].append(row); raw_vs_derived[(arm,winner!=pred)] += 1
            timing[arm].append(r['reader']['forward_seconds']+r['context_seconds']+a['decision_seconds'])
            reported = next(x for x in result['engineering_metrics'][arm]['scores'] if x['id'] == case['id'])
            assert all(reported[k] == row[k] for k in ('gold','prediction','correct'))
            for k in ('Brier','NLL','p_gold'): close(reported[k],row[k])
    assert len(ids) == 36 and verified_certs == 36 and unit_total == 65
    metrics = {}; checks = {}
    for arm, rows in records.items():
        m = dict(n=12,correct=sum(r['correct'] for r in rows),Brier=math.fsum(r['Brier'] for r in rows)/12,NLL=math.fsum(r['NLL'] for r in rows)/12)
        m['by_class'] = {c:dict(n=sum(r['gold']==LOWER[c] for r in rows),correct=sum(r['correct'] for r in rows if r['gold']==LOWER[c])) for c in LABELS}
        assert m['correct'] == result['engineering_metrics'][arm]['correct']
        for k in ('Brier','NLL'): close(m[k],result['engineering_metrics'][arm][k])
        metrics[arm] = m
        for q,name in [(0.5,'forward_context_decision_p50_seconds'),(.95,'forward_context_decision_p95_seconds')]: close(quantile(timing[arm],q),result['engineering_timing'][arm][name],1e-9)
    primary = metrics['native_verified']
    checks.update(primary_all12_correct=primary['correct']==12,authored_class_balance4each=all(m['n']==4 for m in primary['by_class'].values()),primary_all4_per_class_correct=all(m['correct']==4 for m in primary['by_class'].values()),accuracy_gain_at_least2_vs_full_raw=primary['correct']-metrics['full_raw']['correct']>=2,prospective_full_raw_ceiling=metrics['full_raw']['correct']<=10)
    pairs = {}
    for arm in ARMS:
        if arm == 'native_verified': continue
        for k in ('Brier','NLL'): checks[arm+':'+k+'_nonincrease'] = primary[k] <= metrics[arm][k]+EPS
        losses = []
        for p,b in zip(records['native_verified'], records[arm]):
            delta = dict(id=p['id'],primary_minus_Brier=p['Brier']-b['Brier'],primary_minus_NLL=p['NLL']-b['NLL'],primary_minus_correct=p['correct']-b['correct'])
            expected = next(x for x in result['paired_differences'][arm]['authored_case_differences'] if x['id']==p['id'])
            for k in ('primary_minus_Brier','primary_minus_NLL'): close(delta[k],expected[k])
            assert delta['primary_minus_correct'] == expected['primary_minus_correct']; losses.append(delta)
        pairs[arm] = dict(primary_minus_correct=primary['correct']-metrics[arm]['correct'],primary_minus_Brier=primary['Brier']-metrics[arm]['Brier'],primary_minus_NLL=primary['NLL']-metrics[arm]['NLL'],cases=losses)
    assert checks == result['engineering_checks']
    failed = [k for k,v in checks.items() if not v]
    assert set(failed) == set(result['failed_engineering_checks']) == {'lexical_verified:Brier_nonincrease','lexical_verified:NLL_nonincrease'}
    assert result['checks_passed'] is True and result['failed_integrity_checks'] == []
    assert result['engineering_passed'] is result['readiness_qualified'] is False and result['status'] == 'REJECTED_ENGINEERING_ADMISSION'
    lifecycle = raw['reader_lifecycle']; names = [v['event'] for v in lifecycle]
    assert names == ['MODEL_PHASE_START','MODEL_INITIALIZATION_COMPLETED','MODEL_READOUTS_COMPLETED','MODEL_UNLOAD_BEFORE','MODEL_UNLOAD_AFTER_GC','ALL_MODEL_PHASES_CLOSED_BEFORE_ORACLE','ENGINEERING_ORACLE_JOIN_BEFORE','ENGINEERING_ORACLE_JOIN_AFTER']
    assert all(lifecycle[i]['monotonic_seconds'] <= lifecycle[i+1]['monotonic_seconds'] for i in range(len(lifecycle)-1))
    assert all(lifecycle[4][k] is True for k in ('reader_weakref_dead','model_weakref_dead','tokenizer_weakref_dead'))
    assert lifecycle[-1]['joined_labels'] == 12 and all(z['global_readouts_completed']==36 for z in lifecycle[2:])
    gate = raw['engineering_gate']; assert gate['oracle_label_join_count'] == 12
    for k in ('oracle_join_after_all36_readouts_and60_forecasts','all36_predictions_completed_before_oracle_read','all60_forecasts_completed_before_oracle_read','readers_unloaded_before_oracle','single_reader_lifecycle_closed_before_oracle'): assert gate[k] is True
    counters = raw['counters']
    for k,v in dict(corpus_batches_attempted=1,corpus_batches_completed=1,native_queries_completed=12,native_index_initializations_completed=12,native_binary_loads_completed=1,NLI_readouts_completed=36,derived_forecasts_completed=60,engineering_oracle_reads=1,engineering_oracle_expected_labels_accessed=12).items(): assert counters[k]==v
    assert raw['corpora']['engineering']['validated_final_native_counters']['native_insertions_completed'] == 65
    zero = [k for k in counters if any(s in k for s in ('TRAIN_','DEV_','CONF_','paid','GPU','HTTP','network_operations','optimizer','backward','training_steps','calibration_calls','full104_requests'))]
    assert all(counters[k]==0 for k in zero)
    assert raw['wall_seconds_including_initialization_cleanup'] < execution['wall_seconds_including_init_cleanup'] <= 600
    assert execution['largest_child_peak_RSS_bytes'] == raw['resources']['largest_child_peak_RSS_bytes'] == 8014319616
    assert raw['resources']['CPU_affinity'] == [0,1]
    assert all(z['observed_affinity_within_CPU0_1'] is True for z in raw['resources']['worker']['observed_thread_affinities'])
    cumulative = result['cumulative_execution']
    assert cumulative['corpus_attempts'] is cumulative['completed_corpus_batches'] is cumulative['historical_E37_xxlarge_reader_initialization_attempts'] is None
    assert cumulative['historical_E37_corpus_tail'] == 'UNKNOWN_NO_EXECUTION_OR_RAW_RECEIPT'
    assert cumulative['verified_corpus_attempts_lower_bound'] == 34 and cumulative['verified_completed_corpus_batches_lower_bound'] == 32
    assert cumulative['bounded_native_process_attempts'] == 39 and cumulative['legacy_native_qualification_process_attempts'] == 6
    # Metadata inventory only: no actual input/oracle/case-proposal content is opened.
    banned = {'__pycache__','.git','.venv','venv','node_modules','site-packages','credentials','secrets','private','models','weights','assets'}
    inventory = []
    for root in [P+x+'/epoch38' for x in ('candidate','audit','legal-transfer')]+[E.rstrip('/')]:
        path = ROOT/root
        if not path.exists(): continue
        for base, dirs, files in os.walk(path,followlinks=False):
            for name in dirs+files:
                p = Path(base)/name; assert not p.is_symlink()
                assert not any(z.lower() in banned or z.lower().startswith('.env') for z in p.relative_to(ROOT).parts)
            inventory.extend(str((Path(base)/name).relative_to(ROOT)) for name in files)
    selected_privacy = [E+'RESULTS.json',A+'EVALUATE.json',A+'INDEPENDENT_REPORT.json',E+'runs/engineering/raw.json',E+'runs/engineering/execution.json',E+'LEARNINGS.json',E+'USED_CONFIRMATION_IDENTITIES.json',A+'actual-physical-closure-independent-v1.json',A+'generated-bytecode-cleanup-v1.json',E+'preparation/source-history/FINAL_COMMAND_PLAN.v1.json',E+'preparation/source-history/continuation-updates-final.v1.json',A+'preparation/final-command-plan-independent-v1.json']
    forbidden = [r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',r'\bgh[pousr]_[A-Za-z0-9]{30,}\b',r'\bgithub_pat_[A-Za-z0-9_]{30,}',r'\bAKIA[0-9A-Z]{16}\b',r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}',r'<(?:!DOCTYPE\s+html|html|head|body)(?:\s|>)']
    for rel in selected_privacy:
        text = contents(rel).decode(); assert '\0' not in text
        assert not any(re.search(p,text,re.I|re.M) for p in forbidden)
    learn, used = read(E+'LEARNINGS.json'),read(E+'USED_CONFIRMATION_IDENTITIES.json')
    assert ref(E+'LEARNINGS.json')['sha256'] == '34e35ebed73c0cdc3052a94e0ec08f9196d8490d364bd4c00d63c65a074998e6'
    assert ref(E+'USED_CONFIRMATION_IDENTITIES.json')['sha256'] == '0d73cd9a79aad9900fe86563a4601554a064f1c010a0e2cc169cf7143f757e8f'
    assert learn['status'] == result['status'] and learn['engineering_passed'] is False
    assert set(learn['failed_frozen_gates']) == set(failed)
    for arm in ARMS:
        assert learn['actual_measured_metrics'][arm]['correct'] == metrics[arm]['correct']
        for key in ('Brier','NLL'): close(learn['actual_measured_metrics'][arm][key],metrics[arm][key])
    assert used['new_authored_engineering_ids_exposed_forever'] == [c['id'] for c in cases]
    assert used['used_confirmation_identities'] == used['training_ids'] == used['development_ids'] == used['calibration_ids'] == used['confirmation_ids'] == []
    assert (used['benchmark_universe_count'],used['old_exposed_DEV_count'],used['unused_count_unchanged'],used['protected_count_unchanged']) == (423,325,74,24)
    assert (used['cumulative_authored_engineering_entries_exposed'],used['cumulative_unique_authored_source_hypothesis_pairs']) == (63,51)
    assert result['all_slots_closed'] is True and result['official_rank'] is result['benchmark_accuracy'] is None
    assert all(result[k] is False for k in ('benchmark_accepted','champion_promoted','new_submission','official_SOTA_verified'))
    cleanup_rel = A+'generated-bytecode-cleanup-v1.json';cleanup = read(cleanup_rel)
    assert ref(cleanup_rel)['sha256'] == '90afe92b5572a15449e54e7d109e0960a7e70bca0046f6102635aa5539aa008f'
    assert cleanup['remaining_current_generated_bytecode'] == [] and cleanup['frozen_pins_checked_unchanged'] == 157
    assert cleanup['new_scientific_or_scorer_calls'] == 0
    report = {
        'schema_version':1,'epoch':38,'kind':result['kind'],'status':'INDEPENDENT_ACTUAL_ENGINEERING_REJECTION_CONFIRMED',
        'checks_passed':True,'publication_review_checks_passed':True,'scientific_engineering_passed':False,
        'engineering_passed':False,'readiness_qualified':False,'diagnostic_qualified':False,
        'frozen_scientific_status':result['status'],'independent_metric_and_gate_replay_passed':True,
        'results':ref(E+'RESULTS.json'),'qualification_replay':ref(A+'EVALUATE.json'),'frozen_binding':ref(A+'INDEPENDENT_REPORT.json'),
        'raw':ref(E+'runs/engineering/raw.json'),'execution':ref(E+'runs/engineering/execution.json'),'physical_closure':closure_ref,
        'learnings':ref(E+'LEARNINGS.json'),'used_identities':ref(E+'USED_CONFIRMATION_IDENTITIES.json'),
        'independent_actual_physical_closure':ref(A+'actual-physical-closure-independent-v1.json'),
        'generated_bytecode_cleanup':ref(cleanup_rel),
        'raw_FP32_readouts_replayed':36,'raw_FP32_logit_values_verified':108,'derived_forecasts_replayed':60,
        'case_level_Brier_NLL_pairs_replayed':60,'applied_certificates_checked':verified_certs,
        'independent_exact_rational_source_proofs':proofs,'affine_and_set_world_checks':24,
        'proof_scope':'Own retained-record exact Fraction/source-literal parser, affine constraint propagation and explicit complete-world validation for these12 retained cases; no frozen scorer/candidate imports and no universal parser-soundness claim.',
        'metrics_by_arm':metrics,'engineering_checks':checks,'failed_engineering_checks':failed,'paired_differences':pairs,
        'native_lexical_literal_context_identical_cases':sum(native_lexical_context_equal),
        'neural_token_lengths':{'minimum':min(token_lengths),'maximum':max(token_lengths),'hidden_truncation':False,
            'scope':'Retained full/capped pair-length receipts and literal hashes checked; tokenizer/inputIDs not reexecuted.'},
        'execution_summary':{'corpus_batches':1,'queries':12,'indexes':12,'native_insertions':65,'native_binary_loads':1,
            'neural_forwards':36,'derived_forecasts':60,'one_joined_authored_labels':12,'runtime_errors':0,
            'raw_worker_seconds':raw['wall_seconds_including_initialization_cleanup'],'whole_phase_seconds':execution['wall_seconds_including_init_cleanup'],
            'largest_child_peak_RSS_bytes':8014319616,'CPU_affinity':[0,1],'observed_worker_OS_threads':raw['resources']['worker']['Threads'],
            'memory_scope':'Largest-child high-water and worker high-water are separate observations, not simultaneous summed RSS.',
            'primary_forward_context_decision_p50_seconds':quantile(timing['native_verified'],.5),'primary_forward_context_decision_p95_seconds':quantile(timing['native_verified'],.95),
            'timing_scope':'Fixed serial singleton components with reused forwards; excludes initialization/embedding/tokenizer overhead/cleanup, not end-to-end or publisher latency.'},
        'lifecycle_and_once_label_chronology_checked':True,'supervisor_state':'Z','supervisor_absent':False,
        'owned_worker_groups_closed':True,'E37_unknown_cumulative_history_preserved':True,
        'known_corpus_attempt_lower_bound':34,'known_completed_corpus_lower_bound':32,'known_bounded_outer_attempts':39,'legacy_qualification_attempts':6,
        'remaining_scientific_retry_paid_GPU_slots':0,'new_engineering_identities_exposed_forever':12,
        'cumulative_authored_engineering_entries_declared':63,'unique_authored_source_claim_pairs_declared':51,
        'used_confirmation_identities':[],'benchmark_accuracy':None,'benchmark_accepted':False,'champion_promoted':False,
        'new_submission':False,'official_SOTA_verified':False,'official_rank':None,'eligibility_and_foundation_lineage':'HOLD',
        'privacy_review':{'current_four_root_inventory_paths':len(inventory),'symlink_runtime_model_secret_directory_paths_found':0,
            'actual_artifact_content_scans':[ref(p) for p in selected_privacy],
            'source_case_inputs_or_original_oracle_payloads_reread':0,
            'scope':'Public authored CC0 retained runtime/score/metadata artifacts and current-path inventory. Original oracle/input/protected benchmark payloads are not opened; main auditor retains independent full publication-stage review.'},
        'interpretation':[
            'All verified arms answer12/12 correctly; primary gains8 answers over full_raw and9 over native_raw. This supports the narrow whole-pipeline authored engineering observation, not an improved raw model or benchmark result.',
            'The frozen primary fails both lexical proper-score comparisons. Primary-minus-lexical Brier+.009456708689806442 and stable NLL+.003224784024650318 remain losses despite tied perfect accuracy; no gate is softened.',
            'Max-mass transposition preserves each raw distribution shape while moving its raw winning mass to the certified class. Correct certificates improve the same raw readout, but do not guarantee superior probabilities against a different context. The observed lexical comparison demonstrates that limitation.',
            'Native versus lexical differences can include packing/context and raw probability variation. There is no established causal native ranking gain, calibrated posterior, general reasoning strength, LegalBench/JevBench/ClaimBench rank or eligibility promotion.',
            'The normal E38 worker completed; no actual preworker-failure branch was exercised. That failure-capture branch has source/fixture evidence only, and E37 was never retroactively repaired.'
        ],
        'next_direction':[
            'Retain the exact lexical-control loss, especially differing source contexts on cases01/08, as exposed counterexamples. Do not tune packing, confidence, gate or grammar on these12 cases or rerun this closed epoch.',
            'Any future change should be a new prospective global source/packing or probability hypothesis with separate authorized licensed development/calibration if needed and genuinely unused evaluation identities. Compare the full pipeline to matched verified lexical/full controls and keep the same proper-score gate.',
            'Require benchmark-specific eligible data/model protocol and external/publisher evidence before any generalization or established-benchmark claim. Preserve native104,74unused/24protected identities and all E37unknown counts.'
        ],
        'remaining_publication_requirements':['Root copies exact independent review/tools before immutable manifests. Main auditor then verifies sealed file map/controls/stage, exact source-parent scoped CAS/WAL and actual full remote readback before guardian release. This report is not a publication/readback/release receipt.'],
        'auditor_actions':{'new_model_tokenizer_native_or_candidate_calls':0,'frozen_scorer_EVALUATE_calls':0,'frozen_scorer_BIND_calls':0,'host_or_proc_probes':0,'Git_or_network_calls':0,'root_project_writes':0},
        'reviewer_source':{'path':str(Path(__file__)),'bytes':Path(__file__).stat().st_size,'sha256':sha(Path(__file__).read_bytes())}
    }
    out = OWN/'ACTUAL_ACCEPTANCE_REJECTION_v1.json'
    with out.open('x') as f: json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(path=str(out),bytes=out.stat().st_size,sha256=sha(out.read_bytes()))))

if __name__ == '__main__': main()
