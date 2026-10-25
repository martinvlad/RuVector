"""Conservative proof-carrying decisions over a declared, closed input grammar.

This module imports no model and sees no labels or case/document identities.
Incomplete retrieval, an unparsed clause, or unsupported syntax abstains to the
unchanged raw NLI distribution. Closed-input parsing is deliberately narrow.
"""
from __future__ import annotations
import hashlib
import math
import re

POLICY = 'proof-carrying-closed-legal-atoms-v1'
LABELS = ('Entailment', 'Contradiction', 'NotMentioned')
MAX_SOURCE_CHARS = 8192
MAX_CLAUSES = 16
POSITIVE = r'[1-9][0-9]{0,8}'
TERMINATION = re.compile(
    r'(?P<subject>(?:This|The) (?:Agreement|Contract)) '
    r'(?P<event>terminates|expires) exactly (?P<value>' + POSITIVE + r') '
    r'(?P<unit>days?|months?|years?) after '
    r'(?P<reference>the (?:Effective|Execution|Start) Date)\.', re.I|re.ASCII)
END_LINK = re.compile(r'The confidentiality obligations also end on that date\.', re.I|re.ASCII)
RETURN = re.compile(
    r'The (?P<party>Receiving|Disclosing) Party shall return all written '
    r'Confidential Information within (?P<delay>' + POSITIVE + r'|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve) '
    r'business days after a written request from the (?P<requester>Receiving|Disclosing) Party\.', re.I|re.ASCII)
LAW = re.compile(
    r'Disputes under (?P<subject>this (?:Agreement|Contract)) are governed by '
    r'the laws of (?P<jurisdiction>[A-Za-z]{1,64})\.', re.I|re.ASCII)
FORBIDDEN = re.compile(
    r'\b(?:if|unless|except|provided|however|subject|notwithstanding|may|might|either|neither|not|no|or|and|but|whether|approximately|when|whenever|where|while|until|because|since|despite|although)\b', re.I|re.ASCII)
WORDS = dict(zip(('one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve'),range(1,13)))


def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def norm(value):
    return ' '.join(value.lower().split())


def _termination(match):
    return {'predicate':'agreement_termination', 'subject':norm(match['subject']),
        'event':norm(match['event']), 'reference':norm(match['reference']),
        'qualifier':'exactly', 'unit':match['unit'].lower().rstrip('s'),
        'value':int(match['value'])}


def atom(text, previous=None, allow_link=False):
    """Only the literal declarative grammar below is assigned a logical atom."""
    if not isinstance(text,str) or not text.isascii() or FORBIDDEN.search(text):
        return None
    match = TERMINATION.fullmatch(text)
    if match:
        return _termination(match)
    match = RETURN.fullmatch(text)
    if match:
        literal=match['delay'].lower()
        return {'predicate':'return_obligation','party':match['party'].lower(),
            'modality':'shall','object':'all written confidential information',
            'delay_business_days':WORDS[literal] if literal in WORDS else int(literal),
            'trigger':'written request','requester':match['requester'].lower()}
    match = LAW.fullmatch(text)
    if match:
        return {'predicate':'governing_law', 'subject':norm(match['subject']),
            'event':'disputes', 'jurisdiction':norm(match['jurisdiction'])}
    if (allow_link and END_LINK.fullmatch(text) and isinstance(previous,dict)
            and previous.get('predicate')=='agreement_termination'):
        return {'predicate':'confidentiality_end_same_date',
            'subject':previous['subject'], 'parent_event':previous['event'],
            'reference':previous['reference'], 'unit':previous['unit'], 'value':previous['value']}
    return None


def parse_source(document):
    if not isinstance(document,str) or not document.isascii() or not 0<len(document)<=MAX_SOURCE_CHARS or '\0' in document:
        return None
    rows=[];at=0;previous=None
    # Decimal points, semicolons, quotes, conjunctions, missing final periods and
    # arbitrary trailing text cannot silently disappear into the grammar.
    for match in re.finditer(r'[^.!?]+[.!?]', document):
        if document[at:match.start()].strip():
            return None
        raw=match.group();left=len(raw)-len(raw.lstrip());right=len(raw.rstrip())
        text=raw[left:right]
        parsed=atom(text,previous=previous,allow_link=True)
        if parsed is None:
            return None
        rows.append({'source_char_start':match.start()+left,
            'source_char_end':match.start()+right,'text':text,
            'text_sha256':sha(text),'atom':parsed})
        if len(rows)>MAX_CLAUSES:
            return None
        previous=parsed;at=match.end()
    if not rows or document[at:].strip():
        return None
    # A source containing incompatible exclusive scalar declarations has no
    # admitted model. Do not derive arbitrary conclusions from inconsistency.
    seen={}
    for row in rows:
        value=row['atom']
        if value['predicate']!='agreement_termination':
            continue
        key=tuple(value[k] for k in ('subject','event','reference','qualifier'))
        scalar=(value['unit'],value['value'])
        if key in seen and seen[key]!=scalar:
            return None
        seen[key]=scalar
    return rows


def certificate(document,premise,hypothesis,selected_source_spans):
    """Return a source-bound logical certificate or an explicit abstention."""
    if not all(isinstance(x,str) for x in (document,premise,hypothesis)):
        return None,'invalid_input_type'
    if premise!=document or selected_source_spans!=[[0,len(document)]]:
        return None,'arm_does_not_cover_exact_full_supplied_input'
    parsed=parse_source(document)
    if parsed is None:
        return None,'unparsed_or_inconsistent_supplied_input'
    claim=atom(hypothesis)
    if claim is None:
        return None,'unparsed_claim'
    facts=[row['atom'] for row in parsed]
    common={'schema_version':1,'grammar':POLICY,
        'document_sha256':sha(document),'premise_sha256':sha(premise),
        'hypothesis_sha256':sha(hypothesis),
        'coverage':{'premise_equals_full_document':True,
            'selected_source_spans':[[0,len(document)]],
            'all_supplied_clauses_parsed':True},
        'source_clauses':parsed,'claim':claim}
    if claim in facts:
        return {**common,'rule':'EXACT_GROUND_FACT','conclusion':'Entailment',
            'witness':{'source_atom_index':facts.index(claim)}},None
    if claim['predicate']=='agreement_termination':
        identity=('predicate','subject','event','reference','qualifier','unit')
        matches=[(i,fact) for i,fact in enumerate(facts)
            if all(fact.get(k)==claim[k] for k in identity)]
        if matches and all(fact['value']!=claim['value'] for _,fact in matches):
            i,fact=matches[0]
            return {**common,'rule':'DISTINCT_EXACT_SAME_EVENT_VALUE',
                'conclusion':'Contradiction','witness':{
                    'source_atom_index':i,'identity_fields':list(identity),
                    'source_positive_exact_value':fact['value'],
                    'claim_positive_exact_value':claim['value']}},None
    # These primitive predicates are declared independent. An absent predicate
    # is neutral only after complete parsing of the exact arm/full input, and
    # because both a claim-true and a claim-false extension satisfy every atom.
    # Different values within the SAME predicate deliberately abstain unless
    # the exclusive scalar rule above is sufficient.
    if claim['predicate'] not in {fact['predicate'] for fact in facts}:
        return {**common,'rule':'OPEN_WORLD_UNRELATED_PREDICATE',
            'conclusion':'NotMentioned','witness':{
                'source_predicates':sorted({fact['predicate'] for fact in facts}),
                'extensions':[{'all_source_facts':True,'claim_atom':True},
                    {'all_source_facts':True,'claim_atom':False}],
                'predicate_relation':'independent_primitive_predicates'}},None
    return None,'no_admitted_deduction'


def decide(document,premise,hypothesis,selected_source_spans,reader,*,enabled=True):
    raw=reader['probabilities_E_C_N'];label=reader['native_typed_argmax']
    if (not isinstance(raw,list) or len(raw)!=3 or label not in LABELS
            or any(type(x)not in(int,float) or not math.isfinite(x) or not 0<=x<=1 for x in raw)
            or abs(math.fsum(raw)-1)>1e-12):
        raise ValueError('The original finite T1 readout is required before proof policy')
    if type(enabled)is not bool:raise ValueError('Explicit proof-enabled boolean required')
    cert,reason=certificate(document,premise,hypothesis,selected_source_spans) if enabled else (None,'proof_disabled_for_DEV')
    final=label if cert is None else cert['conclusion']
    p=list(raw) if cert is None else [float(name==final) for name in LABELS]
    return {'schema_version':1,'epoch':33,'raw_probabilities_E_C_N':list(raw),
        'raw_typed_argmax':label,'final_probabilities_E_C_N':p,
        'final_typed_argmax':final,'policy':POLICY,'certificate':cert,
        'fallback_reason':reason,'semantic_decision_override':cert is not None}
