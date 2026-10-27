"""Two separately Root-admitted parser-only stages. Never decode qrels document IDs or relevance values.

ids: project only query IDs and first TSV column; freeze exact16 before features.
features: full suppliedcorpus +selectedquerytexts, no qrels file opened.
"""
from pathlib import Path
import argparse,hashlib,json,os,sys,time
A=Path('/tmp/ruvector-sota-2026-10-22/epoch56-parser-cp312-ffdd0699f325')
OWNER=Path('/dev/shm/ruvector-sota-2026-10-22/epoch56-ffdd0699f325/owner.json');OWNER_SHA='1cd0cb9c7ac46476cba887ef0e9ef751daebea307fc8eb0678531af2a7799086'
IDENTITY_NAMESPACE='BeIR/scifact@b3b5335604bf5ee3c4447671af975ea25143d4f5:qrels@2938d17dc3b09882fdb8c12bbbe2e2dc0e75a029:test:PROJECT_DEV'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ref(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def readref(r):
 p=Path(r['path']);assert p.is_file()and not p.is_symlink()and ref(p)==r;return json.loads(p.read_bytes())
def put(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);b=(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()
 with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 return ref(p)
def fence():
 assert sha(OWNER)==OWNER_SHA;o=json.loads(OWNER.read_bytes());assert time.time()<o['expires_unix'] and not(OWNER.parent/'release.request').exists();p=Path('/proc')/str(o['pid']);assert int((p/'stat').read_text().rsplit(')',1)[1].split()[19])==o['startticks'];s=(p/'fd/3').stat();assert(s.st_dev,s.st_ino)==(o['lock_device'],o['lock_inode']);assert 'FLOCK'in(p/'fdinfo/3').read_text()
def main():
 if sys.flags.optimize!=0:raise ValueError('NONOPTIMIZED_PYTHON_REQUIRED')
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['ids','features'],required=True);p.add_argument('--admission',required=True);p.add_argument('--admission-sha256',required=True);a=p.parse_args();assert sorted(os.sched_getaffinity(0))==[0,1];fence();assert sha(Path(a.admission))==a.admission_sha256;ad=json.loads(Path(a.admission).read_bytes());assert ad['epoch']==56 and ad['mode']==a.mode and ad['checks_passed']is True and ad['compiled_parser_import_allowed']is True and ad['source_sha256']==sha(Path(__file__))
 att=readref(ad['parser_independent_attestation']);assert att['checks_passed']is True and att['compiled_parser_import_allowed']is True and att['python_ABI_qualified']is True and att['wheel_licence_and_notices_qualified']is True and att['parser_member_closure_qualified']is True
 manifest=readref(ad['parser_assets_manifest']);assert att['parser_assets_manifest_sha256']==ad['parser_assets_manifest']['sha256']
 A=Path(ad['parser_assets_manifest']['path']).parent;assert A.parent==Path('/tmp/ruvector-sota-2026-10-22') and A.name.startswith('epoch56-parser-cp312') and 'ffdd0699f325'in A.name and not any(p.is_symlink()for p in[A,*A.parents])
 for r in manifest['assets']+manifest['parser_members']:assert ref(Path(r['path']))=={k:r[k]for k in('path','bytes','sha256')}
 parser=A/'parser';assert not parser.is_symlink();assets={Path(r['path']).name:Path(r['path'])for r in manifest['assets']};corpus=assets['scifact-corpus.parquet'];queries=assets['scifact-queries.parquet'];qrels=assets['scifact-test-qrels.tsv'];base=A/'features';base.mkdir(exist_ok=True)
 attempt=base/(a.mode.upper()+'_PREPARATION_ATTEMPT.actual.v1.json');put(attempt,{'epoch':56,'mode':a.mode,'source_sha256':ad['source_sha256'],'admission_sha256':a.admission_sha256,'semantic_gold_decodes':0,'native_corpus_batches':0,'time_unix':time.time()});started=time.monotonic();network={'attempted':0,'successful_observed':0}
 def no_network(event,args):
  if event.startswith('socket.'):
   network['attempted']+=1;raise RuntimeError('PARSER_PREPARATION_NETWORK_FORBIDDEN')
 def no_qrels(event,args):
  if event=='open'and args and isinstance(args[0],(str,bytes,os.PathLike))and os.fsdecode(args[0])==str(qrels)and a.mode!='ids':raise RuntimeError('FEATURE_PREPARATION_QRELS_FORBIDDEN')
 sys.addaudithook(no_network);sys.addaudithook(no_qrels);sys.path.insert(0,str(parser));import pyarrow;import pyarrow.parquet as pq
 pyarrow.set_cpu_count(2);pyarrow.set_io_thread_count(1)
 assert pyarrow.cpu_count()<=2 and pyarrow.io_thread_count()<=1
 assert pyarrow.__version__=='20.0.0' and not any(n in sys.modules for n in ['transformers','onnxruntime','torch'])
 common={'schema_version':1,'epoch':56,'identity_namespace':IDENTITY_NAMESPACE,'mode':a.mode,'compiled_parser_imports':1,'parser_CPU_thread_cap':2,'parser_IO_thread_cap':1,'Parquet_use_threads':False,'parser_version':pyarrow.__version__,'numpy_parser_dependency_imported':'numpy'in sys.modules,'model_tokenizer_BGE_RuVector_imports':0,'native_corpus_batches':0,'semantic_gold_decodes':0,'qrels_documentID_or_relevance_field_decodes':0,'paid_API_GPU_calls':0,'network_audit':network,'source_sha256':ad['source_sha256'],'assets_manifest_ref':ad['parser_assets_manifest'],'source_official_split':'BeIR/scifact-qrels/test','train':[],'calibration':[],'fresh_confirmation':[]}
 assert time.monotonic()-started<55
 if a.mode=='ids':
  with queries.open('rb')as f:t=pq.read_table(f,columns=['_id'],use_threads=False)
  assert time.monotonic()-started<55;ids=t.column('_id').to_pylist();assert len(ids)==1109 and len(set(ids))==1109 and all(type(x)is str and x and len(x)<=128 for x in ids);query_ids=set(ids);official=[]
  with qrels.open('rb')as f:
   assert f.readline().rstrip(b'\r\n')==b'query-id\tcorpus-id\tscore'
   for line in f:
    first,sep,opaque_remainder=line.rstrip(b'\r\n').partition(b'\t');assert sep and first
    # Do not split, decode, inspect or select on any byte in the remainder.
    qid=first.decode('utf8');assert qid in query_ids;official.append(qid)
  selected=sorted(set(official))[:16];assert len(selected)==16
  v={**common,'status':'EXACT_16_DEV_IDENTITIES_METADATA_FROZEN_BEFORE_FEATURE_TEXT_OR_GOLD','selected_ids':selected,'selected_query_ids':selected,'selection_rule':'First16 lexicographicallysorted distinctofficialtestqueryIDs, independentoftext,documentIDs,relevancevalues,ranks ormetrics.','source_all_query_ids':sorted(ids),'all_official_test_query_ids':sorted(set(official)),'official_test_qrel_rows_metadata_only':len(official),'query_ID_projection_rows':len(ids),'query_text_feature_decodes':0,'corpus_feature_decodes':0,'labels_decoded':0,'query_id_metadata_source':ref(qrels),'query_id_parquet_source':ref(queries),'used_confirmation_identities':[],'project_development_query_ids_reserved':selected,'wall_seconds':time.monotonic()-started};result=put(base/'DEV_IDENTITIES_METADATA_FROZEN.actual.v1.json',v)
 else:
  identity=readref(ad['development_identity_manifest']);selected=identity['selected_ids'];assert selected==ad['selected_query_ids']and selected==sorted(set(selected))and len(selected)==16 and identity['identity_namespace']==IDENTITY_NAMESPACE
  with corpus.open('rb')as f:table=pq.read_table(f,columns=['_id','title','text'],use_threads=False)
  assert time.monotonic()-started<55;docs=table.to_pylist();assert len(docs)==5183 and len({d['_id']for d in docs})==5183;dest=base/'prepared-corpus.jsonl'
  with dest.open('xb')as out:
   for d in docs:
    assert set(d)=={'_id','title','text'}and all(type(d[k])is str for k in d)and d['_id']and d['text'];out.write((json.dumps(d,sort_keys=True,ensure_ascii=False)+'\n').encode())
   out.flush();os.fsync(out.fileno())
  with queries.open('rb')as f:table=pq.read_table(f,columns=['_id','text'],filters=[('_id','in',selected)],use_threads=False)
  assert time.monotonic()-started<55;rows=table.to_pylist();by={x['_id']:x for x in rows};assert len(rows)==16 and set(by)==set(selected);rows=[by[i]for i in selected];assert all(set(x)=={'_id','text'}and type(x['text'])is str and x['text']for x in rows)
  qr=put(base/'prepared-dev-queries.json',{'epoch':56,'selected_ids':selected,'queries':rows,'identity_namespace':IDENTITY_NAMESPACE,'source_official_split':'test','project_role':'development'});v={**common,'status':'FULL_CORPUS_AND_FIXED16_DEV_FEATURES_PREPARED_NO_GOLD','corpus_ref':ref(dest),'queries_ref':qr,'development_identity_manifest':ad['development_identity_manifest'],'selected_query_ids':selected,'corpus_documents':5183,'query_text_rows_returned':16,'query_text_internal_decode_upper_bound':1109,'other_query_text_internal_decode_unknown':True,'no_other_source_query_may_be_claimed_fresh_confirmation':True,'query_feature_exposure_scope':'Onlyselected16featuretexts returnedtoPython/modelinputs;Arrowfiltermayinternallydecodeadditionaltextpages. Preserveuncertainty/conservativelyexcludeentiresourcequerypoolfromfreshconfirmation.','used_confirmation_identities':[],'wall_seconds':time.monotonic()-started};result=put(base/'PREPARED_FEATURES_NO_GOLD.actual.v1.json',v)
 assert network['attempted']==0 and time.monotonic()-started<55;fence();print(json.dumps({'mode':a.mode,'result':result,'native_corpus_batches':0,'semantic_gold_decodes':0,'parser_imports':1}))
if __name__=='__main__':main()
