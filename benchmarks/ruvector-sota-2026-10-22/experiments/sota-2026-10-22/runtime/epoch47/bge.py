"""Exact inherited BGE encoding preparation; one4doc corpus/12queries."""
import hashlib
import time
BGE_SOURCE='experiments/sota-2026-10-22/candidate/epoch3/models.py'


BGE_SHA='c5cf3500a89837e71adc754f0dc96d090e172068031545fc55ee349e80210716'


PREFIX='Represent this sentence for searching relevant passages: '


def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()


def embed(bge,texts,counters,progress):
 """Explicit256-token embedding truncation, never the old hidden-overflow guard."""
 import numpy as np
 output=[];audits=[];started=time.perf_counter()
 for start in range(0,len(texts),8):
  batch=texts[start:start+8];full=bge.raw_tokenizer.encode_batch(batch);used=bge.tokenizer.encode_batch(batch)
  feed={'input_ids':np.asarray([x.ids for x in used],dtype=np.int64),
   'attention_mask':np.asarray([x.attention_mask for x in used],dtype=np.int64),
   'token_type_ids':np.asarray([x.type_ids for x in used],dtype=np.int64)}
  counters['BGE_forward_calls_attempted']+=1;counters['BGE_texts_attempted']+=len(batch);progress({'event':'BGE_FORWARD_BEFORE','texts':len(batch)})
  result=bge.session.run(None,{k:v for k,v in feed.items()if k in bge.inputs})[0][:,0,:]
  counters['BGE_forward_calls_completed']+=1;counters['BGE_texts_completed']+=len(batch)
  if result.shape!=(len(batch),384)or not np.isfinite(result).all():raise ValueError('BGE_REAL_OUTPUT_SHAPE_FINITE_FAILED')
  norms=np.linalg.norm(result,axis=1,keepdims=True)
  if np.any(norms<=0):raise ValueError('BGE_ZERO_VECTOR')
  output.append((result/norms).astype(np.float32))
  for text,a,b in zip(batch,full,used):
   ids=[i for i,m in zip(b.ids,b.attention_mask)if m]
   if len(ids)>256:raise ValueError('BGE_EXPLICIT256_LIMIT_FAILED')
   audits.append({'text_sha256':digest(text),'full_tokens':len(a.ids),'consumed_tokens':len(ids),
    'truncated':len(a.ids)>len(ids),'consumed_tokens_sha256':hashlib.sha256(__import__('json').dumps(ids,separators=(',',':')).encode()).hexdigest()})
  progress({'event':'BGE_FORWARD_AFTER','texts':len(batch)})
 return np.concatenate(output),audits,time.perf_counter()-started


def prepare_bundle(C,records,counters,progress,codec):
 if C.sha(C.checked(BGE_SOURCE))!=BGE_SHA:raise ValueError('BGE_SOURCE_CHANGED')
 module=C.load_module('e47_exact_BGE_source',C.checked(BGE_SOURCE));counters['BGE_initializations_attempted']+=1;counters['ORT_sessions_attempted']+=1
 started=time.perf_counter();progress({'event':'BGE_INITIALIZATION_BEFORE'});bge=module.BgeEncoder(C.NATIVE_ROOT)
 counters['BGE_initializations_completed']+=1;counters['ORT_sessions_completed']+=1
 receipt={**bge.receipt,'initialization_seconds':time.perf_counter()-started,'source_sha256':BGE_SHA,'explicit_embedding_cap':256,'query_encoding_cache':False,'actual_query_encodings':12}
 bundle={'schema_version':1,'epoch':47,'kind':C.KIND,'phase':'dev','vector_encoding':'base64_float32le_c_order',
  'metadata_policy':'insert id and vector only; metadata absent','documents':[]};prepared={};documents={}
 for record in records:documents.setdefault(record['document_id'],[]).append(record)
 if len(documents)!=4 or any(len(group)!=3 for group in documents.values()):raise ValueError('FOUR_DOCUMENTS_THREE_HYPOTHESES_EACH_REQUIRED')
 import numpy as np
 block=lambda matrix:codec.encode(matrix.astype('<f4',copy=False).tobytes(order='C'),int(matrix.shape[0]))
 for document_id,group in documents.items():
  case_started=time.perf_counter();texts=[r['sentence']for r in group[0]['evidence']]
  if not 0<len(texts)<=1024 or any(r['evidence']!=group[0]['evidence']for r in group):raise ValueError('SOURCE_DOC_CATALOG_IDENTITY_OR_CAP_FAILED')
  vectors,units,embedding_seconds=embed(bge,texts,counters,progress);query_vectors=[];queries=[]
  for record in group:
   query,query_audit,query_seconds=embed(bge,[PREFIX+record['claim']],counters,progress)
   query_vectors.append(query);queries.append({'id':record['id']+'::retrieval:original'})
   prepared[record['id']]={'source_preparation_started_monotonic_seconds':case_started,'units':units,'query':query_audit[0],
    'unit_embedding_seconds_shared_three_hypotheses':embedding_seconds,'query_embedding_seconds':query_seconds,
    'unit_embedding_shared_document_id':document_id,'units_count':len(texts),'source_unit_ids':list(range(len(texts)))}
  bundle['documents'].append({'document_id':document_id,'vectors':block(vectors),'query_vectors':block(np.concatenate(query_vectors)),
   'queries':queries})
 progress({'event':'BGE_ALL_UNIT_AND_QUERY_FEATURES_COMPLETE'});return bundle,prepared,receipt


