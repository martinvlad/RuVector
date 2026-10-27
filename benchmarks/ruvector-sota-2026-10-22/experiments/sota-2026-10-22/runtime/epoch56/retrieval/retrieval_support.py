"""E56 retrieval DEV support. Stdlib-only at import; no scoring or gold access."""
import base64
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

KIND='REAL_NATIVE_SCIFACT_RETRIEVAL_DEV_PILOT'
PHASE='retrieval_development'
BGE_PREFIX='Represent this sentence for searching relevant passages: '
BGE_SHA='828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35'
TOK_SHA='d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66'

def need(x,code):
 if not x:raise ValueError(code)

def verify(r):
 need(type(r)is dict and set(r)=={'path','bytes','sha256'},'CANONICAL_ASSET_REFERENCE')
 p=Path(r['path']);need(p.is_absolute()and p.is_file()and not any(q.is_symlink()for q in[p,*p.parents]),'REGULAR_NONSYMLINK_ASSET')
 h=hashlib.sha256();fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  b=os.fstat(fd);count=0
  while True:
   block=os.read(fd,1048576)
   if not block:break
   count+=len(block);h.update(block)
  a=os.fstat(fd)
  need((b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns)==(a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns),'UNCHANGED_ASSET_DURING_HASH')
 finally:os.close(fd)
 need(count==r['bytes']and h.hexdigest()==r['sha256'],'EXACT_ASSET_SIZE_SHA256');return p

def put(p,value):
 p=Path(p);need(p.is_absolute()and p.parent.is_dir()and not p.is_symlink(),'SAFE_NEW_OUTPUT')
 b=(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 try:
  need(os.write(fd,b)==len(b),'COMPLETE_OUTPUT_WRITE');os.fsync(fd)
 finally:os.close(fd)
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def proc(pid):
 try:
  f=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
  return {'pid':pid,'startticks':int(f[19]),'pgid':int(f[2]),'sid':int(f[3]),'state':f[0]}
 except(FileNotFoundError,ProcessLookupError):return None

def features(plan,state=None):
 if state is None:state={}
 corpus=[];seen=set()
 with verify(plan['corpus_features']).open()as f:
  for line in f:
   d=json.loads(line);need(set(d)=={'_id','title','text'}and all(type(d[k])is str for k in d),'EXACT_CORPUS_ROW_SCHEMA')
   need(d['_id']and d['_id']not in seen and d['text'].strip(),'CORPUS_ID_TEXT_VALID')
   seen.add(d['_id']);corpus.append(d)
 need(len(corpus)==plan['corpus_document_count']==5183,'FULL_5183_CORPUS')
 qbytes=verify(plan['query_features']).read_bytes();state['query_asset_opened']=True;state['actual_feature_query_ids_uncertain']=True
 q=json.loads(qbytes);rows=q['queries']
 if type(rows)is list:state['actual_feature_query_ids']=list(dict.fromkeys(r.get('_id')for r in rows if type(r)is dict and type(r.get('_id'))is str))
 state['actual_feature_query_ids_uncertain']=False
 need(q['epoch']==56 and q['selected_ids']==plan['selected_query_ids']and len(rows)==16,'FROZEN_SIXTEEN_DEV_IDENTITIES')
 need([r['_id']for r in rows]==plan['selected_query_ids']and len(set(plan['selected_query_ids']))==16,'EXACT_QUERY_ID_ORDER')
 need(all(set(r)=={'_id','text'}and type(r['_id'])is str and type(r['text'])is str and r['text'].strip()for r in rows),'EXACT_QUERY_FEATURES_NO_LABELS')
 return corpus,rows

def block(matrix):
 need(matrix.ndim==2 and matrix.shape[1]==384 and 1<=matrix.shape[0]<=5183,'REAL_BGE_BLOCK_SHAPE')
 b=matrix.astype('<f4',copy=False).tobytes(order='C')
 return {'encoding':'base64','dtype':'float32le','shape':list(matrix.shape),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'data_base64':base64.b64encode(b).decode('ascii')}

def embed(plan,texts,counters,deadline,progress,network):
 need(plan['bge_model']['sha256']==BGE_SHA and plan['bge_tokenizer']['sha256']==TOK_SHA,'FROZEN_BGE_MODEL_TOKENIZER')
 for key in ['bge_model','bge_tokenizer']:verify(plan[key])
 network.set_stage('bge_runtime_import')
 import importlib.metadata
 for name in ['numpy','onnxruntime','tokenizers']:need(importlib.metadata.version(name)==plan['runtime_versions'][name],'EXACT_BGE_RUNTIME_VERSION')
 import numpy as np
 import onnxruntime as ort
 from tokenizers import Tokenizer
 opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
 deadline();counters['BGE_initializations_attempted']+=1;need(counters['BGE_initializations_attempted']==1,'ONE_BGE_INITIALIZATION')
 init=time.monotonic();rawtok=Tokenizer.from_file(plan['bge_tokenizer']['path']);rawtok.no_padding();rawtok.no_truncation()
 tok=Tokenizer.from_file(plan['bge_tokenizer']['path']);tok.enable_truncation(max_length=256,strategy='longest_first');tok.enable_padding(pad_id=0,pad_token='[PAD]')
 sess=ort.InferenceSession(plan['bge_model']['path'],sess_options=opts,providers=['CPUExecutionProvider'])
 need(sess.get_providers()==['CPUExecutionProvider'],'CPU_ONLY_PROVIDER');inputs={x.name for x in sess.get_inputs()};counters['BGE_initializations_completed']+=1
 receipt={'model_sha256':BGE_SHA,'tokenizer_sha256':TOK_SHA,'provider':'CPUExecutionProvider','intra_op_threads':2,'inter_op_threads':1,'embedding_only_truncation_cap':256,'initialization_seconds':time.monotonic()-init}
 vectors=[];audit=[]
 need(len(texts)==5199 and plan['BGE_batch_size']==16 and plan['BGE_forward_cap']==325 and plan['BGE_texts_cap']==5199,'FROZEN_FULL_CORPUS_EMBEDDING_CAPS')
 network.set_stage('bge_embedding')
 for start in range(0,len(texts),16):
  deadline();batch=texts[start:start+16];full=rawtok.encode_batch(batch);used=tok.encode_batch(batch)
  feed={'input_ids':np.asarray([e.ids for e in used],dtype=np.int64),'attention_mask':np.asarray([e.attention_mask for e in used],dtype=np.int64),'token_type_ids':np.asarray([e.type_ids for e in used],dtype=np.int64)}
  need(counters['BGE_forward_calls_attempted']<325 and counters['BGE_texts_attempted']+len(batch)<=5199,'BGE_CAP_BEFORE_FORWARD')
  counters['BGE_forward_calls_attempted']+=1;counters['BGE_texts_attempted']+=len(batch);progress('BGE_FORWARD_BEFORE')
  v=sess.run(None,{k:x for k,x in feed.items()if k in inputs})[0][:,0,:]
  need(v.shape==(len(batch),384)and bool(np.isfinite(v).all()),'FINITE_REAL_BGE_OUTPUT')
  norm=np.linalg.norm(v,axis=1,keepdims=True);need(bool((norm>0).all()),'NONZERO_BGE_NORM');vectors.append((v/norm).astype(np.float32))
  counters['BGE_forward_calls_completed']+=1;counters['BGE_texts_completed']+=len(batch)
  for text,f,u in zip(batch,full,used):
   consumed=sum(u.attention_mask);need(0<consumed<=256,'EMBEDDING_TOKEN_CAP')
   audit.append({'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'full_token_count':len(f.ids),'consumed_token_count':consumed,'embedding_only_truncation':len(f.ids)>consumed})
  progress('BGE_FORWARD_COMPLETE')
 need(counters['BGE_forward_calls_completed']==325 and counters['BGE_texts_completed']==5199,'COMPLETE_FULL_CORPUS_EMBEDDINGS')
 matrix=np.concatenate(vectors);need(matrix.shape==(5199,384),'FULL_MATRIX_SHAPE')
 del sess,tok,rawtok
 import gc;gc.collect();deadline();return matrix,audit,receipt

def expected_native():
 from native_accounting import KEYS
 return dict(zip(KEYS,(1,1,5183,5183,16,16,2,2,160,1,1,1,1,0)))

def native(plan,bundle,external,counters,deadline,progress,state):
 from native_accounting import NativeSnapshotLedger
 ledger=NativeSnapshotLedger(counters,expected_native());state['accounting']=ledger.receipt();source=put(external/'native-bundle.json',bundle);output=external/'native-result.json';command=[plan['node']['path'],plan['native_helper_source']['path'],plan['path'],str(external/'native-bundle.json'),str(output)]
 for k in ['node','native_binary','native_helper_source']:verify(plan[k])
 need(counters['native_corpus_batches_attempted']==0,'ONE_RETRIEVAL_NATIVE_BATCH');counters['native_corpus_batches_attempted']+=1
 child=None;identity=None;stdout=stderr=b'';started=time.monotonic();state.update(command=command,child_closed=None,exit_code=None)
 try:
  deadline();progress('NATIVE_HELPER_START_BEFORE');child=subprocess.Popen(command,cwd=external,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True)
  identity=proc(child.pid);need(identity and identity['pgid']==os.getpgrp()and identity['sid']==os.getsid(0),'NATIVE_CHILD_SESSION');state['identity']=identity
  stdout,stderr=child.communicate(timeout=min(120,deadline()))
 finally:
  if child is not None and child.poll()is None:
   now=proc(child.pid);need(now and identity and now['startticks']==identity['startticks'],'OWNED_NATIVE_CLEANUP')
   child.terminate()
   try:stdout,stderr=child.communicate(timeout=3)
   except subprocess.TimeoutExpired:child.kill();stdout,stderr=child.communicate(timeout=2)
  if child is not None:state.update(child_closed=child.poll()is not None,exit_code=child.returncode)
  (external/'native.stdout').write_bytes(stdout);(external/'native.stderr').write_bytes(stderr)
  try:ledger.capture(external/'native-progress.jsonl')
  finally:state['accounting']=ledger.receipt();state['wall_seconds']=time.monotonic()-started;put(external/'native-process-closure.json',state)
 need(child is not None and child.returncode==0,'NATIVE_HELPER_COMPLETED')
 value=json.loads(output.read_bytes());need(value['schema_version']==1 and value['epoch']==56 and value['kind']==KIND and value['phase']==PHASE and value['plan_sha256']==plan['_sha256']and value['bundle_sha256']==source['sha256']and value['helper_source_sha256']==plan['native_helper_source']['sha256']and value['helper_pid']==identity['pid'],'NATIVE_COMPLETE_SOURCE_BINDING')
 need(value['native_binary_sha256']==plan['native_binary']['sha256']and value['binary_version']=='2.3.0','NATIVE_BINARY_VERSION_AND_HASH');ledger.finalize(value);state['accounting']=ledger.receipt();put(external/'native-accounting-final.json',state['accounting']);need(state['accounting']['qualified'],'NATIVE_SNAPSHOT_ACCOUNTING_QUALIFIED')
 counters['native_corpus_batches_completed']+=1;counters['native_corpus_batches']+=1;progress('NATIVE_HELPER_COMPLETE');return value

WORD=re.compile(r'\w+',re.UNICODE)

def bm25_index(texts):
 rows=[Counter(WORD.findall(t.lower()))for t in texts];df=Counter()
 for row in rows:df.update(row.keys())
 lengths=[sum(r.values())for r in rows];avg=sum(lengths)/len(rows);need(avg>0,'NONEMPTY_BM25_CORPUS');return rows,df,lengths,avg

def bm25_query(query,index,ids):
 rows,df,lengths,avg=index;terms=Counter(WORD.findall(query.lower()));n=len(rows);scores=[]
 for row,dl in zip(rows,lengths):
  score=0.0
  for term,qf in terms.items():
   tf=row.get(term,0)
   if tf:score+=qf*math.log(1+(n-df[term]+.5)/(df[term]+.5))*tf*2.5/(tf+1.5*(1-.75+.75*dl/avg))
  scores.append(score)
 order=sorted(range(n),key=lambda i:(-scores[i],ids[i]))[:10];return order,[scores[i]for i in order]

def cosine_query(query,corpus,ids):
 import numpy as np
 scores=(corpus.astype(np.float64)@query.astype(np.float64))/(np.linalg.norm(corpus.astype(np.float64),axis=1)*np.linalg.norm(query.astype(np.float64)))
 need(bool(np.isfinite(scores).all()),'FINITE_EXACT_COSINE');order=sorted(range(len(ids)),key=lambda i:(-float(scores[i]),ids[i]))[:10];return order,[float(scores[i])for i in order]
