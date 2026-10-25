"""Independent exact-source context and actual native f32 receipt replay."""
import base64
import math
import re
import struct
from data_common import require,identity,digest,expected,finite,canonical
from phase_audit import checked,read,KIND
from query_audit import query_check
from source_coverage_audit import source_groups,context_check
from certificate_audit import audit_catalog
from nli_metrics import ARMS,CONTEXTS

PREFIX='Represent this sentence for searching relevant passages: '
ABSENT='{"present":false}'
NUMBER=re.compile(r'(?<![\w])[-+\u2212]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?![\w])')

def block_digests(block):
    require(block['encoding']=='base64'and block['dtype']=='float32le','Wrong numeric vector encoding')
    shape=block['shape'];require(type(shape)is list and len(shape)==2 and type(shape[0])is int
        and 0<shape[0]<=192 and shape[1]==384,'Wrong numeric vector dimensions')
    b=base64.b64decode(block['data_base64'],validate=True)
    require(base64.b64encode(b).decode()==block['data_base64']and len(b)==block['bytes']==shape[0]*1536
            and digest(b)==block['sha256'],'Lossless vector bytes/hash mismatch')
    result=[]
    for i in range(shape[0]):
        row=b[i*1536:(i+1)*1536];v=struct.unpack('<384f',row)
        require(all(math.isfinite(x)for x in v)and abs(math.sqrt(math.fsum(x*x for x in v))-1)<=1e-5,
                'Source BGE output must be finite normalized float32')
        result.append(digest(row))
    return result

def native_query_check(query,digests,units):
    k=min(40,len(units))
    require(type(query['requested_k'])is int and query['requested_k']==len(query['ids'])==len(query['raw_hits'])==k
            and all(type(i)is int for i in query['ids'])
            and len(set(query['ids']))==k and query['ids']==[int(h['id'])for h in query['raw_hits']]
            and query['native_order_used_without_replacement']is True,'Actual complete native hit list changed')
    require(finite(query['query_ms'])and query['query_ms']>=0,'Native query timing invalid')
    for hit in query['raw_hits']:
        index=int(hit['id']);require(type(hit['id'])is str and str(index)==hit['id']and 0<=index<len(units),
                'Native hit outside source index')
        require(finite(hit['score'])and {'id','score','vector'}<=set(hit['raw_keys'])and 'metadata'not in hit['raw_keys'],
                'Original native hit fields lost/nonfinite')
        require(hit['vector_receipt']=={'source_vector_index':index,'dimensions':384,'dtype':'float32le',
            'sha256':digests[index],'source_sha256':digests[index],'source_equal_before_stripping':True},
            'Native/source f32 bits mismatch')
        require(hit['metadata_receipt']=={'present':False,'canonical_json':ABSENT,'sha256':digest(ABSENT.encode()),
            'source_equal_before_stripping':True},'Native metadata absence receipt mismatch')
    return len(query['raw_hits'])

def audit_evidence(root,raw,bank,role,plan):
 require(bank['epoch']==38 and bank['role']==role and set(bank)=={'schema_version','epoch','role','records'}and bank['schema_version']==1 and role=='engineering','Only exact unlabeled engineering bank permitted')
 records=bank['records'];cases=raw['cases'];triples=lambda rr:[(r['id'],r['document_id'],r['hypothesis_id'])for r in rr]
 require(triples(cases)==triples(records)==expected(role),'Exact12 authored source identities/order required')
 for row in records:
  require(set(row)=={'id','document_id','hypothesis_id','document','hypothesis','input_sha256'},'Input bank has foreign/oracle fields')
  require(all(type(row[k])is str and row[k].strip()and '\0'not in row[k]for k in ['document','hypothesis']),'Invalid supplied source text')
  require(digest(canonical({k:row[k]for k in ['document','hypothesis']}).encode())==row['input_sha256'],'Source input SHA differs')
 require(raw['role']==role and raw['input_bank']=={**identity(root/plan['engineering_inputs_path']),'path':plan['engineering_inputs_path']}and raw['input_bank']['sha256']==plan['engineering_inputs_sha256'],'Actual source bank receipt differs')
 bundle=read(checked(root,raw['vector_bundle']));native=read(checked(root,raw['native_result']))
 require(bundle['schema_version']==3 and bundle['epoch']==38 and bundle['kind']==KIND and bundle['phase']=='engineering'and bundle['role']==role and bundle['vector_encoding']=='base64_float32le_c_order'and bundle['metadata_policy']=='insert id and vector only; metadata absent','Wrong native vector bundle')
 require(native['epoch']==38 and native['phase']=='engineering'and native['role']==role and native['kind']==KIND and native['native']is True and native['bundle_sha256']==raw['vector_bundle']['sha256']and native['errors']==[]and native['compact_schema']=='epoch38-native-context-f32le-v1','Native final result incomplete')
 require(native['package_version']=='0.1.33'and native['platform_package_version']=='0.1.31'and native['binary_version']=='2.3.0'and native['native_binary_sha256']=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e','Original native binary/version differs')
 require(native['source_sha256']==identity(root/plan['native_worker_path'])['sha256']and native['stage']=='HELPER_COMPLETED','Exact-source final native receipt required')
 dids=[str(r['document_id'])for r in records];require(len(set(dids))==12 and [d['document_id']for d in bundle['documents']]==[d['document_id']for d in native['documents']]==dids,'Exact12 native documents required')
 prep=raw['documents'];require(set(prep)==set(dids)and raw['shared_partition_model']=='xxlarge','One source/reader partition required')
 vectors=hits=0;coverage=[];contexts=[];analyses=[]
 for inp,case,matrix,observed in zip(records,cases,bundle['documents'],native['documents']):
  source=inp['document'];hyp=inp['hypothesis'];did=str(inp['document_id']);q=inp['id'];preparation=prep[did];units=preparation['units'];catalogue=source_groups(source,units)
  require(preparation['partition_model_tag']=='xxlarge'and finite(preparation['partition_seconds'])and preparation['partition_seconds']>=0,'Wrong actual single-model partition')
  chunks=[source[u['start']:u['end']]for u in units];vd=block_digests(matrix['vectors']);qd=block_digests(matrix['query_vectors']);vectors+=len(vd)
  require(len(vd)==len(units)==observed['initialized_vectors']and len(qd)==1 and matrix['queries']==[{'id':q+'::retrieval:original'}]and len(observed['queries'])==1,'Source vector/query matrix cardinality differs')
  query=observed['queries'][0];require(query['case_id']==q+'::retrieval:original','Native query identity differs');hits+=native_query_check(query,vd,units)
  expected_native=dict(query,document_id=did,initialization_ms=observed['initialization_ms'],initialized_vectors=observed['initialized_vectors'])
  require(case['native']==expected_native and set(query['ids'])==set(range(len(units)))and len(query['ids'])==len(units)and case['native_complete_unique_unitset_verified']is True,'Actual complete native unitset receipt missing')
  require(case['document_preparation_ref']==did and all(case[k]==inp[k]for k in ['id','document_id','hypothesis_id','document','hypothesis','input_sha256'])and case['document_sha256']==digest(source.encode())and case['hypothesis_sha256']==digest(hyp.encode()),'Source literal identity changed')
  require(set(preparation['retrieval_queries'])=={q}and case['retrieval_query']==preparation['retrieval_queries'][q],'Original query receipt changed');qr=query_check(root,plan,hyp,case['retrieval_query']);emb=preparation['embedding']
  require(emb['source_sha256s']==[digest(c.encode())for c in chunks]and emb['exact_query_texts']==[PREFIX+qr['query']],'BGE exact source/query input text changed')
  for f in ['document','queries']:
   # Source-bound embedding diagnostics are descriptive; byte blocks above are verified independently.
   require(isinstance(emb[f],dict),'Missing original embedding diagnostic')
  require(case['source_analysis']==preparation['source_analysis'],'Source dependency catalogue alias differs');info=audit_catalog(case['source_analysis'],source,hyp);analyses.append({'id':q,**info})
  qw=set(re.findall(r'\w+',hyp.casefold()));words=[set(re.findall(r'\w+',t.casefold()))for t in chunks];scores=[len(qw&w)/max(1,len(qw|w))for w in words];lexical=sorted(range(len(units)),key=lambda i:(-scores[i],i))
  require(case['lexical_jaccard_scores']==scores and case['lexical_ranking']==lexical,'Fixed same-query lexical ranking differs')
  require(set(case['readouts'])==set(CONTEXTS)and set(case['arms'])==set(ARMS),'All3 physical and5 derived contexts required')
  for name in CONTEXTS:
   physical=case['readouts'][name];ranking=lexical if name=='lexical_coverage'else query['ids']
   require(physical['readout_id']==q+'::NLI:'+name and physical['measured_context']==name and physical['model_tag']=='xxlarge','Physical NLI readout identity differs')
   require(finite(physical['context_seconds'])and physical['context_seconds']>=0 and physical['native_query_seconds']==query['query_ms']/1000,'Actual source packing/native timing changed')
   contexts.append({'id':q,**context_check(source,hyp,units,catalogue,ranking,physical,case['source_analysis'],name)})
  coverage.append({'id':q,'complete_actual_native_unitset':query['ids'],'source_units':len(units),'source_vector_sha256s':vd,'query_vector_sha256':qd[0]})
 counters={'native_index_initializations_attempted':12,'native_index_initializations_completed':12,'native_queries_attempted':12,'native_queries_completed':12,'native_len_calls_attempted':24,'native_len_calls_completed':24,'native_version_calls_attempted':1,'native_version_calls_completed':1,'native_insertions_attempted':vectors,'native_insertions_completed':vectors,'native_hit_source_validations':hits}
 require(all(type(native.get(k))is int and native[k]==v for k,v in counters.items()),'Native final operation totals do not close to actual source/vector/query records')
 return {'status':'PASS_SINGLE_MODEL_MATCHED_DEPENDENCY_PREFIX_NATIVE_LEXICAL_AND_F32_SOURCE_REPLAY','documents':12,'cases':12,'source_index_vectors':vectors,'source_query_vectors':12,'native_hits_verified':hits,'actual_NLI_contexts':36,'derived_forecasts':60,'complete_native_unitsets':coverage,'group_context_observations':contexts,'source_analysis_observations':analyses,'native_final_counters_replayed':counters,'model_tokenizer_native_calls':0,'source_choices_or_evidence_labels_read':0,'scope':'Only supplied source searched. Every source clause independently parsed and all constraints/witnesses checked. Native and lexical use identical coverage-complete whole-group prefix rule; null controls imply no causal native ranking gain. Actual tokenizer counts remain source-bound worker observations, not independently retokenized.'}
