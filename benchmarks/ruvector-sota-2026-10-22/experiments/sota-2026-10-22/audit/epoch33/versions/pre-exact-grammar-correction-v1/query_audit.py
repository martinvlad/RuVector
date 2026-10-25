"""Independent receipt replay of the fixed typed-modal retrieval query.

Manual ASCII letter scanning implements the declarative recognizers without
importing candidate query.py. No source document, labels or model outputs enter
the query transform. Actual vector/native-context provenance is checked by the
separate evidence auditor.
"""
from data_common import require,digest
from phase_audit import checked,read

POLICY='typed-modal-query-expansion-v1'
PREFIX='Represent this sentence for searching relevant passages: '
TERMS={
 'copy_permission':['copy','copies','duplicate','duplication','reproduce','reproduction','retention'],
 'disclosure_permission':['disclose','disclosure','share','third','party','consultant','agent','advisor','adviser','professional','representative'],
 'oral_information_scope':['oral','orally','verbal','verbally','spoken','unwritten','information','disclosure']}
NEGATIVE={'not','never','no','unless','except','if','provided','without','neither','nor'}
RECOGNIZERS={
 'copy_permission':{'prefixes':[['copy'],['duplicate'],['reproduce'],['create','a','copy','of']]},
 'disclosure_permission':{'prefixes':[['share'],['disclose'],['communicate'],['provide']],
                          'required_any_tail_token':['with','to']},
 'oral_information_scope':{'prefixes':[['include'],['cover'],['encompass'],['contain']],
                           'required_any_tail_token':['oral','orally','verbal','verbally','spoken']}}

def ascii_words(value):
    words=[];start=None
    for i,c in enumerate(value.lower()+' '):
        letter='a'<=c<='z'
        if letter and start is None:start=i
        if not letter and start is not None:
            words.append(value.lower()[start:i]);start=None
    return words

def derive(hypothesis):
    require(type(hypothesis)is str and hypothesis and '\0'not in hypothesis,'Original nonempty source hypothesis required')
    family=None;reason=None
    if not hypothesis.isascii():reason='non_ascii_hypothesis'
    else:
        words=ascii_words(hypothesis)
        positions=[i for i,w in enumerate(words)if w=='may']
        if len(positions)!=1:reason='not_one_positive_may_modal'
        elif set(words)&NEGATIVE:reason='negated_or_conditional_modal'
        else:
            following=words[positions[0]+1:];matches=[]
            first=following[0]if following else None
            if first in('copy','duplicate','reproduce')or following[:4]==['create','a','copy','of']:
                matches.append('copy_permission')
            if first in('share','disclose','communicate','provide')and set(following)&{'with','to'}:
                matches.append('disclosure_permission')
            if first in('include','cover','encompass','contain')and set(following)&{'oral','orally','verbal','verbally','spoken'}:
                matches.append('oral_information_scope')
            if len(matches)==1:family=matches[0]
            else:reason='unrecognized_or_ambiguous_modal_action'
    terms=[]if family is None else list(TERMS[family])
    expanded=hypothesis if not terms else hypothesis+'\nRetrieval terms: '+' '.join(terms)
    require(len(expanded)-len(hypothesis)<=256,'Fixed augmentation character cap exceeded')
    return expanded,family,terms,reason

def policy_check(policy):
    require(policy['schema_version']==1 and policy['epoch']==33
            and policy['kind']=='REAL_NATIVE_TYPED_MODAL_RETRIEVAL_NLI_DIAGNOSTIC'and policy['policy']==POLICY,
            'Wrong typed-modal query policy scope')
    require(policy['inputs']==['hypothesis only']and policy['terms']==TERMS and policy['recognizers']==RECOGNIZERS
            and set(policy['tokenization']['negation_or_condition_tokens'])==NEGATIVE,
            'Query inputs/terms/exclusions differ from fixed transformation')
    require(policy['max_added_characters']==256 and policy['BGE_query_token_cap']==256
            and policy['BGE_query_prefix']==PREFIX
            and policy['query_id_suffixes']=={'original':'::retrieval:original','expanded':'::retrieval:expanded'},
            'Query cap/prefix/variant identities differ')
    require(policy['raw_NLI_calls']=={'engineering':24,'conditional_DEV':96,'maximum_total':120}
            and policy['native_queries']=={'engineering':12,'conditional_DEV':48,'maximum_total':60}
            and policy['grid_or_postmeasurement_best_selection']is False
            and policy['confirmation']==[],'Query design budget/postselection changed')
    return {'policy':POLICY,'independent_implementation':'Manual ASCII letter scanner + fixed action predicates; candidate query.py never imported',
            'document_or_label_input_to_transform':False,'configuration_count':1}

def query_check(root,plan,hypothesis,receipt):
    required={'schema_version','epoch','policy','query_source_sha256','query_policy_sha256',
              'original_hypothesis_sha256','original_query','expanded_query','original_query_sha256',
              'expanded_query_sha256','recognized_predicate','appended_terms','expansion_applied','fallback_reason'}
    require(type(receipt)is dict and set(receipt)==required,'Exact typed-query receipt schema required')
    expanded,family,terms,reason=derive(hypothesis)
    require(receipt['schema_version']==1 and receipt['epoch']==33 and receipt['policy']==POLICY
            and receipt['query_source_sha256']==plan['query_source_sha256']
            and receipt['query_policy_sha256']==plan['query_policy_sha256'],'Query source/policy receipt binding differs')
    require(receipt['original_query']==hypothesis and receipt['expanded_query']==expanded
            and receipt['original_hypothesis_sha256']==receipt['original_query_sha256']==digest(hypothesis.encode())
            and receipt['expanded_query_sha256']==digest(expanded.encode()),'Independent original/expanded query literal replay failed')
    require(receipt['recognized_predicate']==family and receipt['appended_terms']==terms
            and type(receipt['expansion_applied'])is bool and receipt['expansion_applied']is bool(terms)
            and receipt['fallback_reason']==reason,'Fixed query recognition/augmentation discriminator differs')
    return {'original':hypothesis,'expanded':expanded,'recognized_predicate':family,
            'expansion_applied':bool(terms),'fallback_reason':reason}
