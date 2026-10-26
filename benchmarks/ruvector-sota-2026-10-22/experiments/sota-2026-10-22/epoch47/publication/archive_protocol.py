"""E47 archive-aware metadata/transport guards; no data/model/API execution."""
import copy,hashlib,json,stat
from pathlib import Path,PurePosixPath
FORBIDDEN='486888de9602bbb5d817a55f707b4fcfd11c65e0'
FORBIDDEN_OBJECTS={FORBIDDEN,'3d5a61f9068acf2dabd2ae5c6bd531d9a9b464c5'}
SCOPE='benchmarks/ruvector-sota-2026-10-22/'
BASE='143d1a78ea730e030ff5255a20b047d856f6305f'
CP_SHA=None
ROOTS=tuple('experiments/sota-2026-10-22/'+s for s in('epoch47','audit/epoch47','runtime/epoch47'))

def require(ok,message):
 if not ok:raise ValueError(message)
def sha(b):return hashlib.sha256(b).hexdigest()
def git(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def same(a,b):
 if type(a)is not type(b):return False
 if isinstance(a,dict):return set(a)==set(b)and all(same(a[k],b[k])for k in a)
 if isinstance(a,list):return len(a)==len(b)and all(same(x,y)for x,y in zip(a,b))
 return a==b

def relative(p):
 require(isinstance(p,str)and p and '\\'not in p and not PurePosixPath(p).is_absolute()and all(x not in('','.','..')for x in p.split('/')),'Unsafe project path');return p

def verify_70_projection(current_cont,current_cp,git_paths,projection):
 """Validate existing explicit3+67 omissions; never upload/project via Git."""
 rows={r['path']:r for r in current_cp['project_files']};require(len(rows)>=7872,'Fresh E47 base CP7872 and append-only rows required')
 archive=current_cont['epoch42_archive_recovery']['archive_transport']
 require(archive==current_cp['epoch42_archive_recovery'],'CONT/CP inherited archive descriptor differs')
 require(archive['archive']=={'path':'recoveries/epoch42-publication-20261026/immutable-e42-artifacts.zip','bytes':4531795,'sha256':'b1563d4bd7b8ea54e69f6a2d1047130b95a94748d58e83fabcf465431c64cbca'},'Exact immutable archive required')
 require(projection['archive']['Git_blob_sha1']=='22669777496cdcb3d957bbe237bb8e5b70f5fde5'and len(projection['project_files'])==287,'Typed archive/projection identities')
 projected={r['path']:r for r in projection['project_files']};require(len(projected)==287,'Duplicate projection')
 for p,r in projected.items():require(rows.get(p)=={k:r[k]for k in('path','bytes','sha256')},'ProjectedCP row changed')
 old3=set(projection['historical_CP_only_paths_restored_by_unchanged_legacy_transports']);new67=set(projection['additional_archive_backed_CP_only_paths']);require(len(old3)==3 and len(new67)==67 and not old3&new67,'Separate legacy3/archive67')
 require(set(rows)-set(git_paths)==old3|new67,'All70 CP-only omissions explicitly covered')
 require(all(p in projected for p in new67),'Archive-only member unaccounted')
 require(current_cont['epoch42_archive_recovery']['original_blob5_execution']=='UNKNOWN_PERMANENTLY'and current_cont['epoch42_archive_recovery']['never_create_or_tree_reference_forbidden_object']is True,'Old invocation uncertainty/deny rule changed')
 return {'CP_only':70,'legacy':sorted(old3),'archive_backed':sorted(new67),'decode_order':'E42 exact287 projection intoKIT+project BEFORE legacy26/globalCPverify, then unchanged bootstrap/restore/verify','never_upload_projected_ledger_Git_object':FORBIDDEN}

def deny_old_object(kind,args):
 def refs(v):
  if isinstance(v,dict):
   for k,x in v.items():
    if k in('sha','base_tree_sha','parent_sha','tree_sha','expected_sha'):require(x not in FORBIDDEN_OBJECTS,'Forbidden old live Git object reference')
    refs(x)
  elif isinstance(v,list):
   for x in v:refs(x)
 refs(args)
 if kind=='create_blob':
  import base64
  require(args.get('encoding')in('utf-8','base64'),'Explicit blob encoding')
  b=args['content'].encode()if args['encoding']=='utf-8'else base64.b64decode(args['content'],validate=True);require(git(b)not in FORBIDDEN_OBJECTS,'Forbidden decoded old object recreation')
 if kind=='create_tree':
  for e in args['tree_elements']:
   p=relative(e['path']);require(p.startswith(SCOPE),'Scope escape')
   if 'content'in e:require(git(e['content'].encode())not in FORBIDDEN_OBJECTS,'Forbidden inline old object recreation')

def preserve_replay(replay,metadata):
 require('publication_checkpoint'not in replay,'Already publication-bound');out=copy.deepcopy(replay);out['publication_checkpoint']=copy.deepcopy(metadata)
 require(all(same(out[k],v)for k,v in replay.items()),'Every actual field/type must remain exact');return out
