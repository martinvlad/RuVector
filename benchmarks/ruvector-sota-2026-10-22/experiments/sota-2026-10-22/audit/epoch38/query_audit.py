"""Independent unchanged-query and fixed lexical/native group-complement replay."""
from data_common import require,digest
POLICY='unchanged-original-query-numeric-source-v1'
PREFIX='Represent this sentence for searching relevant passages: '

def policy_check(policy):
    require(policy=={'schema_version':1,'epoch':38,'kind':'ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES','policy':POLICY,'query':'Unchanged entire original hypothesis; fixed BGE search prefix only','truncation':False,'rewriting':False,'label_access':False},'Wrong unchanged-source query policy')
    return {'policy':POLICY,'configuration_count':1,'model_tokenizer_native_calls':0,'query_expansions':0}

def query_check(root,plan,hypothesis,receipt):
    required={'schema_version','epoch','policy','query_source_sha256','query_policy_sha256',
              'original_hypothesis_sha256','original_query','original_query_sha256','query','query_sha256','expansion_applied'}
    require(type(receipt)is dict and set(receipt)==required,'Exact unchanged-query receipt schema required')
    require(type(hypothesis)is str and hypothesis.strip() and '\0'not in hypothesis,'Exact whole hypothesis required')
    h=digest(hypothesis.encode())
    require(receipt['schema_version']==1 and receipt['epoch']==38 and receipt['policy']==POLICY
            and receipt['query_source_sha256']==plan['query_source_sha256']
            and receipt['query_policy_sha256']==plan['query_policy_sha256'],'Query source/policy binding differs')
    require(receipt['original_query']==receipt['query']==hypothesis and receipt['original_query_sha256']==receipt['query_sha256']==receipt['original_hypothesis_sha256']==h
            and receipt['expansion_applied']is False,'Query expansion or source-claim rewriting is forbidden')
    return {'original':hypothesis,'query':hypothesis,'expansion_applied':False}
