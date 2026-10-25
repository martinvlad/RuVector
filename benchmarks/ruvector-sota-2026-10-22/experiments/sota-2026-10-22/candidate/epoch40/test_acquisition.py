"""Disjoint invented bytes/HTTP mocks; never actual cache/network/model/cases."""
from pathlib import Path
import hashlib,importlib.util,json,struct,tempfile,unittest
from unittest.mock import patch
H=Path(__file__).resolve().parent

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A=load('invented_acquirer',H/'runtime/acquire_assets.py');G=A.load_guard();N=load('invented_network',H/'runtime/acquisition_network.py')
def git(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def declaration(raw,lfs=False):
 h=hashlib.sha256(raw).hexdigest();row={'path':'invented.bin','bytes':len(raw),'source_url':'https://huggingface.co/fixture/repo/resolve/'+'a'*40+'/invented.bin'}
 if lfs:
  row.update(upstream_sha256=h,upstream_git_blob_sha1=git(('version https://git-lfs.github.com/spec/v1\noid sha256:'+h+'\nsize '+str(len(raw))+'\n').encode()))
 else:row['upstream_git_blob_sha1']=git(raw)
 return row
class Response:
 def __init__(self,status,body=b'',headers=None):self.status=status;self.body=body;self.headers=headers or{};self.offset=0
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n):v=self.body[self.offset:self.offset+n];self.offset+=len(v);return v
class AcquisitionFixtures(unittest.TestCase):
 def test_ordinary_git_grounded_sha_derivation(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'invented';raw=b'Unrelated tokenizer-format fixture bytes';p.write_bytes(raw);row=declaration(raw);actual=A.source_observation(p,row);self.assertEqual(actual['sha256'],hashlib.sha256(raw).hexdigest());row['upstream_git_blob_sha1']='f'*40
   with self.assertRaises(ValueError):A.source_observation(p,row)
 def test_lfs_pointer_and_expanded_body_git_are_distinct(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'invented';raw=b'Unrelated synthetic safetensors payload';p.write_bytes(raw);row=declaration(raw,True);self.assertNotEqual(git(raw),row['upstream_git_blob_sha1']);self.assertEqual(A.source_observation(p,row)['sha256'],row['upstream_sha256']);row['upstream_git_blob_sha1']=git(raw)
   with self.assertRaises(ValueError):A.source_observation(p,row)
 def test_actual_full_catalog_lfs_rows_normalize_exact_publisher_five_tuple(self):
  catalog=json.loads((H/'research/CLASSIC_PREACQUISITION_CATALOG.json').read_text());rows={r['path']:r for r in catalog['files']}
  expected={'model.safetensors':(1740312738,'534780ea5d1f76d22be966d10de67cf2690ec25010aeb4b607d4aadcd2649ebc','e0d97fd1797dd01450c14d09c55bb23e833d6ca5'),'spm.model':(2464616,'c679fbf93643d19aab7ee10c0b99e460bdbc02fedf34b92b05af343b4af586fd','b1b95e5b0fef33623979511f423eaeee465c46f0')}
  for name,(size,sha,pointergit)in expected.items():
   row=rows[name];self.assertTrue({'identity_type','canonical_pointer_bytes','canonical_pointer_git_sha1_verified'}<=set(row))
   with self.assertRaises(ValueError):G.identities().expected_payload(row)
   normalized=A.lfs_source_authority(row);self.assertEqual(set(normalized),{'path','bytes','source_url','upstream_git_blob_sha1','upstream_sha256'});self.assertEqual((normalized['bytes'],normalized['upstream_sha256'],normalized['upstream_git_blob_sha1']),(size,sha,pointergit));self.assertEqual(G.identities().expected_payload(normalized)['payload_sha256'],sha)
 def test_catalog_annotation_shape_reaches_stream_verifier_without_schema_failure(self):
  with tempfile.TemporaryDirectory()as d:
   raw=b'Unrelated bytes, full LFS catalogue-shaped integration fixture';p=Path(d)/'invented';p.write_bytes(raw);row=declaration(raw,True);pointer=('version https://git-lfs.github.com/spec/v1\noid sha256:'+row['upstream_sha256']+'\nsize '+str(len(raw))+'\n').encode();row.update(identity_type='GIT_LFS_POINTER_AND_PAYLOAD_SHA256',canonical_pointer_bytes=len(pointer),canonical_pointer_git_sha1_verified=True)
   self.assertEqual(A.source_observation(p,row)['sha256'],row['upstream_sha256'])
 def test_synthetic_threeway_header_positive_and_dtype_refusal(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'invented';header={'classifier.weight':{'dtype':'F32','shape':[3,1024],'data_offsets':[0,12288]},'classifier.bias':{'dtype':'F32','shape':[3],'data_offsets':[12288,12300]},'deberta.embeddings.position_ids':{'dtype':'I64','shape':[1,512],'data_offsets':[12300,16396]}};raw=json.dumps(header,separators=(',',':')).encode();p.write_bytes(struct.pack('<Q',len(raw))+raw+bytes(16396));self.assertEqual(A.header_metadata(p,3075)['classifier_weight_shape'],[3,1024]);header['classifier.weight']['dtype']='F16';raw=json.dumps(header).encode();p.write_bytes(struct.pack('<Q',len(raw))+raw+bytes(16396))
   with self.assertRaises(ValueError):A.header_metadata(p,3075)
 def test_redirect_stream_is_exact_and_logs_no_signed_query(self):
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory()as d:
   raw=b'invented public bytes';events=[];responses=[Response(302,headers={'Location':'https://cas-bridge.xethub.hf.co/fixture?Signature=DO_NOT_PUBLISH'}),Response(200,raw)];opener=SimpleNamespace(open=lambda *a,**k:responses.pop(0))
   with patch.object(N.urllib.request,'build_opener',return_value=opener):N.stream('https://huggingface.co/fixture',Path(d)/'partial',declaration(raw),events,10**30)
   self.assertEqual(len(events),2);self.assertNotIn('DO_NOT_PUBLISH',json.dumps(events));self.assertEqual((Path(d)/'partial').read_bytes(),raw)
 def test_http_failure_is_one_get_without_retry(self):
  from types import SimpleNamespace
  events=[];opener=SimpleNamespace(open=lambda *a,**k:Response(429))
  with tempfile.TemporaryDirectory()as d,patch.object(N.urllib.request,'build_opener',return_value=opener):
   with self.assertRaisesRegex(ValueError,'HTTP_STATUS_429'):N.stream('https://huggingface.co/fixture',Path(d)/'partial',declaration(b'x'),events,10**30)
  self.assertEqual(len(events),1)
 def test_unapproved_redirect_host_never_receives_get(self):
  from types import SimpleNamespace
  events=[];opener=SimpleNamespace(open=lambda *a,**k:Response(302,headers={'Location':'https://example.invalid/no'}))
  with tempfile.TemporaryDirectory()as d,patch.object(N.urllib.request,'build_opener',return_value=opener):
   with self.assertRaisesRegex(ValueError,'UNREVIEWED_DOWNLOAD_ROUTE'):N.stream('https://huggingface.co/fixture',Path(d)/'partial',declaration(b'x'),events,10**30)
  self.assertEqual(len(events),1)
 def test_full18_tiny_actual_typed_guard_separate_catalogs_and_locks(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);profiles={};specs={};pre=None
   for tag in('b354','tasksource'):
    directory=root/tag;directory.mkdir();declared=[];observed=[]
    for i in range(9):
     name='tiny'+str(i);raw=('Unrelated eighteenfile fixture '+tag+str(i)).encode();row=declaration(raw,i>=7);row['path']=name
     if i<7:row['metadata_body_sha256']=hashlib.sha256(raw).hexdigest()
     (directory/name).write_bytes(raw);(directory/name).chmod(0o444);declared.append(row);observed.append({k:v for k,v in row.items()if k in('path','bytes','source_url','upstream_git_blob_sha1')}|{'sha256':hashlib.sha256(raw).hexdigest()})
    expected={'repository':'fixture/'+tag,'revision':'a'*40,'files':declared};catalog=root/(tag+'-expected.json');catalog.write_text(json.dumps(expected));lock={'epoch':40,'kind':'INVENTED_ONLY','repository':expected['repository'],'revision':expected['revision'],'model_directory':str(directory),'files':observed};public=root/(tag+'-observed.json');public.write_text(json.dumps(lock));(directory/'asset-lock.json').write_bytes(public.read_bytes());profiles[tag]={'model_directory':str(directory),'public_lock_path':str(public),'public_lock_sha256':G.sha(public),'expected_catalog_path':str(catalog),'expected_catalog_sha256':G.sha(catalog)};specs[tag]={'repository':expected['repository'],'revision':expected['revision'],'catalog_sha256':G.sha(catalog)if tag=='b354'else None,'files':9}
    if tag=='tasksource':pre=catalog
   with patch.object(G,'PROFILE_SPECS',specs),patch.object(G,'PREACQ',pre),patch.object(G,'PREACQ_SHA',G.sha(pre)):
    result=G.validate_model_profiles(profiles,root=Path('/'),epoch=40,kind='INVENTED_ONLY',source_checkpoint='a'*40)
   self.assertEqual(result['actual_payload_files_verified'],18);self.assertEqual(result['ordinary_Git_payloads_verified'],14);self.assertEqual(result['canonical_LFS_pointers_verified'],4)
if __name__=='__main__':unittest.main()
