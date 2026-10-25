"""Root-only once E40 acquisition. Source definitions do not perform any IO modes."""
from pathlib import Path
import fcntl,hashlib,importlib.util,json,os,re,shutil,signal,stat,time,traceback
HERE=Path(__file__).resolve().parent
SOURCE='2cf5aba60a050079506a5e9aa5463f44c1efcd5a'
KIND='REAL_CONTRACTNLI_HELDOUT_DEV_TRANSFER_PILOT'
SCOPE=Path('/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05')
BOOT='4632fb06-b0ef-4df5-b72b-0e875bbad810'
PID,TICKS,FD,DEVICE,INODE=120232,27979422,3,33,13626
OWNER_SHA='f18924b1456dcf51c461181c233ff4511cd3e479982f48b109a0e4126b5c3af0'
TARGET=SCOPE/'reader-assets/tasksource-212de447184b'
BASE_SOURCE=Path('/workspace/ruvector-e39-reader-assets/moritz-b3546ea6')
BASE_TARGET=Path('/workspace/ruvector-e40-reader-assets/moritz-b3546ea6')
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def load_guard():return load('e40_shared_real_asset_guard',HERE/'model_assets_guard.py')
def put(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x',encoding='utf-8')as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def guardian():
 g=load_guard();owner=SCOPE/'owner.json'
 if g.sha(owner)!=OWNER_SHA:raise ValueError('E40_ASSET_GUARDIAN_BYTES_CHANGED')
 record=g.read_metadata(owner);p=Path('/proc/'+str(PID));fields=(p/'stat').read_text().rsplit(')',1)[1].split()
 descriptor=p/'fd'/str(FD);info=descriptor.stat();lock=SCOPE.parent/'exclusive.work.lock'
 if (record.get('pid')!=PID or record.get('startticks')!=TICKS or record.get('generation')!=1
  or time.time()>=record.get('expires_unix',0)or fields[0]in('Z','X')or int(fields[19])!=TICKS
  or Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=BOOT
  or Path('/proc/self/ns/pid').stat().st_ino!=4026532200 or (p/'ns/pid').stat().st_ino!=4026532200 or info.st_dev!=DEVICE or info.st_ino!=INODE
  or os.readlink(descriptor)!=str(lock)or (SCOPE/'release.request').exists()):raise ValueError('E40_ASSET_GUARDIAN_NOT_CURRENT')
 held=False
 for line in Path('/proc/locks').read_text().splitlines():
  words=line.split()
  if len(words)>=8 and words[1:5]==['FLOCK','ADVISORY','WRITE',str(PID)]:
   a,b,c=words[5].split(':');held|=(int(a,16),int(b,16),int(c))==(os.major(DEVICE),os.minor(DEVICE),INODE)
 if not held:raise ValueError('EXACT_GUARDIAN_KERNEL_FLOCK_ABSENT')
 fd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  fcntl.flock(fd,fcntl.LOCK_UN);raise ValueError('E40_ASSET_GUARDIAN_LOCK_NOT_HELD')
 finally:os.close(fd)

def verify_source_plan(path,expected,root):
 g=load_guard()
 if not re.fullmatch('[0-9a-f]{64}',expected)or g.sha(path)!=expected:raise ValueError('EXACT_FROZEN_ACQUISITION_PLAN_REQUIRED')
 p=g.read_metadata(path)
 if p.get('epoch')!=40 or p.get('source_checkpoint')!=SOURCE:raise ValueError('ASSET_PLAN_SCOPE_CHANGED')
 caps={'paid_API_cap_USD':0,'paid_API_calls':0,'GPU_calls':0,'CPU_threads':2,'CPU_affinity':[0,1],'wall_seconds_including_download_hashes_capture_cleanup':360,'attempts':1,'retries':0,'maximum_payload_network_bytes':1751462486,'maximum_GETs_including_redirects':24,'maximum_redirects_per_file':3,'stream_chunk_bytes':1048576,'model_tokenizer_native_initializations_or_calls':0,'case_oracle_reads':0}
 if any(p.get('caps',{}).get(k)!=v for k,v in caps.items()):raise ValueError('ZERO_COST_BOUNDED_ASSET_POLICY_CHANGED')
 if p['candidate']['repository']!='sileod/deberta-v3-large-tasksource-nli'or p['candidate']['revision']!='212de447184bda8fb9415a2e5697846864ddf304'or p['candidate']['target_directory']!=str(TARGET)or p['candidate']['payload_total_bytes']!=1751462486:raise ValueError('EXACT_CANDIDATE_SOURCE_CHANGED')
 if p['baseline']['source_directory']!=str(BASE_SOURCE)or p['baseline']['target_directory']!=str(BASE_TARGET):raise ValueError('EXACT_BASELINE_CACHE_PLAN_REQUIRED')
 expected_sources={'acquisition_source':HERE/'acquire_assets.py','network_source':HERE/'acquisition_network.py','validator_source':HERE/'model_assets_guard.py','identity_helper_source':HERE.parent/'asset_identity.py','preacquisition_catalog':g.PREACQ,'baseline_catalog':HERE.parent/'MODEL_B354_ASSETS.expected.json'}
 for key,file in expected_sources.items():
  row=p['sources'][key]
  if file!=Path(root)/row['path']or file.stat().st_size!=row['bytes']or g.sha(file)!=row['sha256']:raise ValueError('REVIEWED_ACQUISITION_SOURCE_CHANGED_'+key)
 if g.sha(g.PREACQ)!=g.PREACQ_SHA or g.sha(HERE.parent/'MODEL_B354_ASSETS.expected.json')!=g.PROFILE_SPECS['b354']['catalog_sha256']:raise ValueError('SEPARATE_SOURCE_AUTHORITIES_REQUIRED')
 return p

def host_admission():
 mem={}
 for line in Path('/proc/meminfo').read_text().splitlines():
  k,v=line.split(':',1)
  if k=='MemAvailable':mem[k]=int(v.split()[0])*1024
 cg=Path('/sys/fs/cgroup');maximum=int((cg/'memory.max').read_text());current=int((cg/'memory.current').read_text());s={a:int(b)for a,b in(line.split()for line in(cg/'memory.stat').read_text().splitlines())}
 clean=max(0,min(max(0,s['file']-s['shmem']),s['active_file']+s['inactive_file'])-s['file_dirty']-s['file_writeback']);headroom=min(mem['MemAvailable'],max(0,maximum-current+clean))
 tmp=shutil.disk_usage(SCOPE).free;workspace=shutil.disk_usage('/workspace').free
 if maximum!=17179869184 or headroom<8589934592 or tmp<2825204310 or workspace<67108864:raise ValueError('ASSET_TMP_WORKSPACE_OR_NONSHMEM_MEMORY_ADMISSION_FAILED')
 return {'cgroup_max':maximum,'current':current,'stats':s,'clean_filecache_excluding_shmem':clean,'headroom':headroom,'tmp_free':tmp,'workspace_free':workspace}

def lfs_source_authority(declaration):
 """Strict helper consumes only publisher authority, not catalogue annotations."""
 row={k:declaration[k]for k in ('path','bytes','source_url','upstream_git_blob_sha1','upstream_sha256')}
 pointer=('version https://git-lfs.github.com/spec/v1\noid sha256:'+row['upstream_sha256']+'\nsize '+str(row['bytes'])+'\n').encode()
 actual=hashlib.sha1(b'blob '+str(len(pointer)).encode()+b'\0'+pointer).hexdigest()
 if actual!=row['upstream_git_blob_sha1']:raise ValueError('ORIGINAL_PUBLISHER_LFS_POINTER_AUTHORITY_CHANGED')
 if 'identity_type'in declaration and (declaration['identity_type']!='GIT_LFS_POINTER_AND_PAYLOAD_SHA256'or declaration.get('canonical_pointer_bytes')!=len(pointer)or declaration.get('canonical_pointer_git_sha1_verified')is not True):raise ValueError('PINNED_CATALOG_POINTER_ANNOTATION_MISMATCH')
 return row

def source_observation(path,declaration):
 """Full stream identity; sole pending tokenizer SHA derives only after exactGit."""
 g=load_guard();expected_bytes=declaration['bytes'];h=hashlib.sha256();gh=None if 'upstream_sha256'in declaration else hashlib.sha1(b'blob '+str(expected_bytes).encode()+b'\0');count=0
 before=g.no_symlink(path).stat()
 if not stat.S_ISREG(before.st_mode)or before.st_size!=expected_bytes:raise ValueError('SOURCE_PAYLOAD_SIZE_OR_TYPE_CHANGED')
 with path.open('rb')as f:
  opened=os.fstat(f.fileno())
  if(opened.st_dev,opened.st_ino)!=(before.st_dev,before.st_ino):raise ValueError('SOURCE_INODE_CHANGED')
  for block in iter(lambda:f.read(1048576),b''):
   count+=len(block);h.update(block)
   if gh is not None:gh.update(block)
 after=path.stat()
 if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)or count!=expected_bytes:raise ValueError('SOURCE_CHANGED_DURING_SCAN')
 sha=h.hexdigest();git=gh.hexdigest()if gh is not None else None
 if 'upstream_sha256'in declaration:
  if sha!=declaration['upstream_sha256']:raise ValueError('SOURCE_LFS_PAYLOAD_SHA_MISMATCH')
  g.identities().verify_payload_observation(lfs_source_authority(declaration),count,sha,None)
 else:
  if git!=declaration['upstream_git_blob_sha1']:raise ValueError('SOURCE_ORDINARY_GIT_BODY_MISMATCH')
  if 'metadata_body_sha256'in declaration and sha!=declaration['metadata_body_sha256']:raise ValueError('SOURCE_METADATA_SHA_MISMATCH')
 return {'bytes':count,'sha256':sha,'ordinary_git_sha1':git if 'upstream_sha256'not in declaration else None}

def header_metadata(path,expected_parameters=435064835):
 import struct
 with path.open('rb')as stream:
  length=struct.unpack('<Q',stream.read(8))[0]
  if not 2<=length<=2097152:raise ValueError('SAFETENSORS_HEADER_BOUND_FAILED')
  raw=stream.read(length)
 header=json.loads(raw,object_pairs_hook=load_guard().object_pairs);rows={k:v for k,v in header.items()if k!='__metadata__'};end=0;floating=integer=0
 for name,row in sorted(rows.items(),key=lambda item:item[1]['data_offsets'][0]):
  shape=row['shape'];dims=1
  if not isinstance(shape,list)or any(type(v)is not int or v<0 for v in shape):raise ValueError('HEADER_SHAPE_FAILED')
  for dimension in shape:dims*=dimension
  dtype=row['dtype'];width={'F32':4,'I64':8}.get(dtype)
  if width is None or row['data_offsets']!=[end,end+dims*width]:raise ValueError('EXACT_F32_HEADER_STORAGE_LAYOUT_REQUIRED')
  if dtype=='F32':floating+=dims
  elif name!='deberta.embeddings.position_ids'or dims!=512:raise ValueError('ONLY_KNOWN_I64_POSITION_BUFFER_ALLOWED')
  else:integer+=dims
  end+=dims*width
 if floating!=expected_parameters or integer!=512 or end+length+8!=path.stat().st_size or rows.get('classifier.weight',{}).get('shape')!=[3,1024]or rows.get('classifier.bias',{}).get('shape')!=[3]:raise ValueError('EXACT_THREEWAY_F32_MODEL_HEAD_GRAPH_METADATA_REQUIRED')
 return {'header_sha256':hashlib.sha256(raw).hexdigest(),'F32_parameters':floating,'I64_position_elements':integer,'source_tensors':len(rows),'classifier_weight_shape':[3,1024],'classifier_bias_shape':[3],'tensor_values_decoded':0,'model_initializations':0}

def existing_parent(path):
 while not path.exists():path=path.parent
 return path

def make_lock(tag,directory,expected,observed,root):
 g=load_guard();lock={'schema_version':1,'epoch':40,'kind':KIND,'repository':expected['repository'],'revision':expected['revision'],'model_directory':str(directory),'files':observed}
 put(directory/'asset-lock.json',lock);(directory/'asset-lock.json').chmod(0o444);directory.chmod(0o555)
 public=HERE.parent/('MODEL_'+tag.upper()+'_ASSETS.json');put(public,lock);return g.source_ref(public,root)

def prepare_assets(plan_path,expected_plan_sha,*,root,runtime_request):
 """One root-approved invocation, outer355+5 cap mandatory; no ML/case mode."""
 started=time.monotonic();root=Path(root);plan=verify_source_plan(plan_path,expected_plan_sha,root);guardian();g=load_guard()
 put(SCOPE/'ASSET_ACQUISITION_ATTEMPT.json',{'epoch':40,'kind':KIND,'plan_sha256':expected_plan_sha,'before_payload_IO':True,'attempts':1,'allowed_retries':0,'at_unix':time.time()})
 result={'epoch':40,'kind':KIND,'source_checkpoint':SOURCE,'plan_sha256':expected_plan_sha,'status':'INITIALIZING','profiles':{},'network_events':[],'errors':[],'model_tokenizer_native_calls':0,'case_oracle_reads':0,'paid_API_calls':0,'GPU_calls':0};partial=None
 old=signal.getsignal(signal.SIGALRM)
 def timed(sig,frame):raise TimeoutError('ACQUISITION350_SECOND_WORK_BOUND')
 try:
  signal.signal(signal.SIGALRM,timed);signal.setitimer(signal.ITIMER_REAL,max(.001,350-(time.monotonic()-started)));os.sched_setaffinity(0,{0,1});result['host_admission']=host_admission()
  if TARGET.exists()or BASE_TARGET.exists():raise ValueError('FRESH_ASSET_TARGET_EXISTS_NO_RETRY')
  g.no_symlink(TARGET);g.no_symlink(BASE_TARGET)
  if BASE_SOURCE.stat().st_dev!=existing_parent(BASE_TARGET.parent).stat().st_dev:raise ValueError('BASELINE_TARGET_EXDEV_STOP_NO_COPY')
  pre=g.read_metadata(g.PREACQ);network=load('e40_source_only_download',HERE/'acquisition_network.py');TARGET.mkdir(parents=True,exist_ok=False);observed=[];derived=[]
  result['profiles']['tasksource']={'target_directory':str(TARGET),'files':[]}
  for declaration in pre['files']:
   guardian();name=declaration['path'];partial=TARGET/(name+'.partial');destination=TARGET/name
   if 'metadata_body_sha256'in declaration:
    source=HERE.parent/'research/tasksource-metadata'/('gitattributes.txt'if name=='.gitattributes'else name);source_observation(source,declaration)
    with source.open('rb')as src,partial.open('xb')as dst:shutil.copyfileobj(src,dst,1048576);dst.flush();os.fsync(dst.fileno())
   else:network.stream(declaration['source_url'],partial,declaration,result['network_events'],started+350)
   actual=source_observation(partial,declaration);os.rename(partial,destination);partial=None;destination.chmod(0o444)
   row={k:declaration[k]for k in('path','bytes','source_url','upstream_git_blob_sha1')}
   if 'upstream_sha256'in declaration:row['upstream_sha256']=declaration['upstream_sha256']
   else:row['metadata_body_sha256']=actual['sha256']
   derived.append(row);observed.append({'path':name,'bytes':actual['bytes'],'sha256':actual['sha256'],'source_url':declaration['source_url'],'upstream_git_blob_sha1':declaration['upstream_git_blob_sha1']});result['profiles']['tasksource']['files'].append({'path':name,**actual,'publisher_source_identity_checked':True})
  result['tasksource_header_metadata']=header_metadata(TARGET/'model.safetensors')
  expected={'schema_version':1,'epoch':40,'repository':pre['repository'],'revision':pre['revision'],'files':derived,'source_authority':g.source_ref(g.PREACQ,root),'tokenizer_SHA_derivation':'Exact ordinaryGit18edee8d415256429ac65609c6b31df913abc06d and8,656,843B matched before deriving SHA256; separate from observedlock.'};ep=HERE.parent/'MODEL_TASKSOURCE_ASSETS.expected.json';put(ep,expected)
  result['profiles']['tasksource']['public_lock']=make_lock('tasksource',TARGET,expected,observed,root)
  baseline=g.read_metadata(HERE.parent/'MODEL_B354_ASSETS.expected.json');names={r['path']for r in baseline['files']}
  if {p.name for p in BASE_SOURCE.iterdir()}-{'asset-lock.json'}!=names:raise ValueError('BASELINE_INVENTORY_CHANGED')
  BASE_TARGET.mkdir(parents=True,exist_ok=False);observed=[];result['profiles']['b354']={'target_directory':str(BASE_TARGET),'transfers':[]}
  for declaration in baseline['files']:
   guardian();original=g.no_symlink(BASE_SOURCE/declaration['path']);before=original.stat()
   if before.st_mode&0o222:raise ValueError('BASELINE_WRITABLE_STOP_NO_CHMOD_OR_COPY')
   actual=g.scan_payload(original,declaration);os.link(original,BASE_TARGET/declaration['path']);after=original.stat()
   if(before.st_dev,before.st_ino,before.st_size,before.st_mode,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mode,after.st_mtime_ns):raise ValueError('BASELINE_SOURCE_CHANGED')
   observed.append({'path':declaration['path'],'bytes':actual['actual_payload_bytes_hashed'],'sha256':actual['actual_payload_sha256'],'source_url':declaration['source_url'],'upstream_git_blob_sha1':declaration['upstream_git_blob_sha1']});result['profiles']['b354']['transfers'].append({'path':declaration['path'],'method':'HASH_VERIFIED_READONLY_HARDLINK','nlink_before':before.st_nlink,'nlink_after':after.st_nlink,'source_bytes_mode_mtime_unchanged':True,'nlink_ctime_changes_disclosed':True})
  result['profiles']['b354']['public_lock']=make_lock('b354',BASE_TARGET,baseline,observed,root)
  profiles={}
  for tag,directory in [('b354',BASE_TARGET),('tasksource',TARGET)]:
   public=HERE.parent/('MODEL_'+tag.upper()+'_ASSETS.json');catalog=HERE.parent/('MODEL_'+tag.upper()+'_ASSETS.expected.json');profiles[tag]={'model_directory':str(directory),'public_lock_path':str(public),'public_lock_sha256':g.sha(public),'expected_catalog_path':str(catalog),'expected_catalog_sha256':g.sha(catalog)}
  result['actual_complete_validator']=g.validate_model_profiles(profiles,root=root,epoch=40,kind=KIND,source_checkpoint=SOURCE);result['runtime_closure']=g.verify_runtime_files(root=root,**runtime_request);result['status']='ALL18_MODEL_PAYLOADS_AND_RUNTIME_HASH_ADMITTED_NO_ML'
 except BaseException as error:
  result['status']='ASSET_ACQUISITION_FAILED_STOP_NO_RETRY';result['errors'].append({'type':type(error).__name__,'errno':getattr(error,'errno',None),'message_sha256':hashlib.sha256(str(error).encode()).hexdigest()});(SCOPE/'asset-acquisition-exact-error.txt').write_text(traceback.format_exc());raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
  if partial is not None and partial.exists():
   # An interrupted transfer may not have a durable inode receipt. Retain it; never delete an uncertain path.
   try:result['own_partial_retained_bytes']=partial.stat().st_size;result['partial_cleanup']='RETAINED_NO_UNVERIFIED_PATH_DELETION_NO_RETRY'
   except OSError as error:result['partial_cleanup_error']={'type':type(error).__name__,'errno':error.errno}
  result['inner_wall_seconds_before_final_capture']=time.monotonic()-started;result['outer355_plus5_required_for_total360']=True;result['CPU_affinity']=sorted(os.sched_getaffinity(0));put(SCOPE/'ASSET_ACQUISITION_RESULT.json',result)
 return result
