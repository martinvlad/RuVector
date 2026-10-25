"""One label-free typed-modal query expansion; no document or identity input.

The original hypothesis remains the NLI hypothesis. Only retrieval query text
is augmented. Original and augmented native queries use the same vector index.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re

POLICY='typed-modal-query-expansion-v1'
TERMS={
    'copy_permission':('copy','copies','duplicate','duplication','reproduce','reproduction','retention'),
    'disclosure_permission':('disclose','disclosure','share','third','party','consultant','agent','advisor','adviser','professional','representative'),
    'oral_information_scope':('oral','orally','verbal','verbally','spoken','unwritten','information','disclosure')}
NEGATION_OR_CONDITION={'not','never','no','unless','except','if','provided','without','neither','nor'}
MAX_ADDED_CHARACTERS=256


def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def expand(hypothesis):
    if not isinstance(hypothesis,str) or not hypothesis or '\0' in hypothesis:
        raise ValueError('The original nonempty source hypothesis is required')
    reason=None;recognized=None
    if not hypothesis.isascii():
        reason='non_ascii_hypothesis'
    else:
        tokens=re.findall(r'[a-z]+',hypothesis.lower(),flags=re.ASCII)
        if tokens.count('may')!=1:
            reason='not_one_positive_may_modal'
        elif set(tokens)&NEGATION_OR_CONDITION:
            reason='negated_or_conditional_modal'
        else:
            tail=tokens[tokens.index('may')+1:]
            actions=[]
            if (tail[:1] in (['copy'],['duplicate'],['reproduce'])
                    or tail[:4]==['create','a','copy','of']):
                actions.append('copy_permission')
            if tail[:1] in (['share'],['disclose'],['communicate'],['provide']) and any(x in tail for x in ('with','to')):
                actions.append('disclosure_permission')
            if tail[:1] in (['include'],['cover'],['encompass'],['contain']) and any(x in tail for x in ('oral','orally','verbal','verbally','spoken')):
                actions.append('oral_information_scope')
            if len(actions)==1:
                recognized=actions[0]
            else:
                reason='unrecognized_or_ambiguous_modal_action'
    terms=list(TERMS[recognized]) if recognized else []
    expanded=hypothesis+('\nRetrieval terms: '+' '.join(terms) if terms else '')
    if len(expanded)-len(hypothesis)>MAX_ADDED_CHARACTERS:
        raise ValueError('Frozen retrieval augmentation character cap exceeded')
    here=Path(__file__).resolve()
    return {'schema_version':1,'epoch':33,'policy':POLICY,
        'query_source_sha256':hashlib.sha256(here.read_bytes()).hexdigest(),
        'query_policy_sha256':hashlib.sha256(here.with_name('QUERY_POLICY.json').read_bytes()).hexdigest(),
        'original_hypothesis_sha256':sha(hypothesis),'original_query':hypothesis,
        'expanded_query':expanded,'original_query_sha256':sha(hypothesis),
        'expanded_query_sha256':sha(expanded),'recognized_predicate':recognized,
        'appended_terms':terms,'expansion_applied':bool(terms),'fallback_reason':reason}
