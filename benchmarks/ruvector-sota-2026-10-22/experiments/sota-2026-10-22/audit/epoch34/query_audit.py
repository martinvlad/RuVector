"""Independent unchanged-query and fixed lexical/native group-complement replay."""
from data_common import require,digest
POLICY='lexical-anchor-native-complement-v1'
PREFIX='Represent this sentence for searching relevant passages: '

def policy_check(policy):
    require(policy['schema_version']==1 and policy['epoch']==34 and policy['policy']==POLICY,
            'Wrong fixed hybrid policy scope')
    # The exact source/JSON bytes are separately pinned. These defining fields
    # must also explicitly deny a query rewrite or postmeasurement choice.
    require(policy['kind']=='REAL_NATIVE_LEXICAL_ANCHOR_NATIVE_COMPLEMENT_NLI_DIAGNOSTIC',
            'Wrong hybrid kind')
    require(policy['arms']==['actual_native','native_original','lexical','positional']
            and policy['native_queries_per_case']==1 and policy['shared_native_query_receipt_between_primary_and_control']is True
            and policy['selection_labels_or_evidence_annotations']is False and policy['fitting_or_calibration']is False
            and policy['new_term_grid']is False and policy['train']==policy['calibration']==policy['confirmation']==[]
            and policy['official_eligibility']=='HOLD'and policy['promotion_allowed']is False,
            'Hybrid query count/selection/eligibility policy differs')
    shared=policy['shared_context']
    require(shared['policy']=='mandatory-two-groups-before-optional-definitions-v1'
            and shared['joint_pair_token_cap']==512 and shared['mandatory_ranked_distinct_complete_groups']==2
            and shared['optional_definition_preselection_cap']==160 and shared['additional_ranked_groups_or_neighbors']is False,
            'Shared group packing budget changed')
    return {'policy':POLICY,'independent_implementation':'Original-string/hash equality plus independently derived full lexical order and distinct-group native complement; candidate query.py never imported','configuration_count':1,'model_tokenizer_native_calls':0}

def query_check(root,plan,hypothesis,receipt):
    required={'schema_version','epoch','policy','query_source_sha256','query_policy_sha256',
              'original_hypothesis_sha256','original_query','original_query_sha256','query','query_sha256','expansion_applied'}
    require(type(receipt)is dict and set(receipt)==required,'Exact unchanged-query receipt schema required')
    require(type(hypothesis)is str and hypothesis.strip() and '\0'not in hypothesis,'Exact whole hypothesis required')
    h=digest(hypothesis.encode())
    require(receipt['schema_version']==1 and receipt['epoch']==34 and receipt['policy']==POLICY
            and receipt['query_source_sha256']==plan['query_source_sha256']
            and receipt['query_policy_sha256']==plan['query_policy_sha256'],'Query source/policy binding differs')
    require(receipt['original_query']==receipt['query']==hypothesis and receipt['original_query_sha256']==receipt['query_sha256']==receipt['original_hypothesis_sha256']==h
            and receipt['expansion_applied']is False,'Query expansion or source-claim rewriting is forbidden')
    return {'original':hypothesis,'query':hypothesis,'expansion_applied':False}

def hybrid_check(lexical,native,units,receipt):
    require(type(lexical)is list and set(lexical)==set(range(len(units))) and len(lexical)==len(units),
            'Full independently computed lexical order required')
    require(type(native)is list and len(native)==len(set(native))==min(40,len(units))
            and all(type(i)is int and 0<=i<len(units)for i in native),'Exact actual native top40 required')
    anchor=lexical[0];group=units[anchor]['group_id'];different=[i for i in native if units[i]['group_id']!=group]
    complement=different[0]if different else None;catalogue={u['group_id']for u in units}
    require(complement is not None or len(catalogue)==1,'Native complement absent in multigroup source; no fallback')
    prefix=[anchor]+([]if complement is None else[complement])
    ranking=(prefix+[i for i in native if i not in prefix])[:min(40,len(units))]
    expect={'policy':POLICY,'lexical_anchor_unit_id':anchor,'lexical_anchor_group_id':group,
            'native_complement_unit_id':complement,'native_complement_group_id':None if complement is None else units[complement]['group_id'],
            'single_group_degenerate':len(catalogue)==1,'hybrid_ranking':ranking}
    require(receipt==expect,'Fixed lexical anchor/native complement selection receipt differs')
    return ranking,expect
