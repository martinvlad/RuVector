"""Unexecuted-for-runtime reference: raw Git blobs and resolved LFS payloads.

Pure byte functions only. This is not the frozen E37 guard, has no filesystem,
network/model/tokenizer/native API, and does not authorize another dispatch.
Expected declarations must come from a separately pinned original catalog.
"""
import hashlib,re

HEX64=re.compile('[0-9a-f]{64}')
HEX40=re.compile('[0-9a-f]{40}')
def require(ok,message):
    if not ok:raise ValueError(message)
def git_blob(data):
    require(type(data)is bytes,'Exact byte representation required')
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def typed_declaration(original):
    require(type(original)is dict,'Original declaration required')
    require(type(original.get('bytes'))is int and original['bytes']>=0,'Original payload size required')
    raw='metadata_body_sha256'in original;lfs='upstream_sha256'in original
    require(raw!=lfs,'Exactly one explicit rawGit or LFS payload source declaration required; observed-lock sha256 alone is insufficient')
    key='metadata_body_sha256'if raw else'upstream_sha256'
    require(type(original.get(key))is str and HEX64.fullmatch(original[key]),'Exact original payload SHA256 required')
    require(type(original.get('upstream_git_blob_sha1'))is str and HEX40.fullmatch(original['upstream_git_blob_sha1']),'Original representation GitSHA1 required')
    return {'representation':'RAW_GIT_BLOB'if raw else'RESOLVED_GIT_LFS_PAYLOAD','payload_bytes':original['bytes'],'payload_sha256':original[key],'upstream_representation_git_sha1':original['upstream_git_blob_sha1']}
def canonical_lfs_pointer(typed):
    require(typed['representation']=='RESOLVED_GIT_LFS_PAYLOAD','LFS declaration required')
    return ('version https://git-lfs.github.com/spec/v1\noid sha256:'+typed['payload_sha256']+'\nsize '+str(typed['payload_bytes'])+'\n').encode('ascii')
def source_representation_check(typed):
    if typed['representation']=='RESOLVED_GIT_LFS_PAYLOAD':
        require(git_blob(canonical_lfs_pointer(typed))==typed['upstream_representation_git_sha1'],'Pinned upstream GitLFS pointer differs from declared oid/size')
    else:require(typed['representation']=='RAW_GIT_BLOB','Unknown representation')
    return True
def verify_payload(payload,original):
    t=typed_declaration(original);source_representation_check(t)
    require(type(payload)is bytes and len(payload)==t['payload_bytes'],'Payload size differs')
    require(hashlib.sha256(payload).hexdigest()==t['payload_sha256'],'Resolved payload SHA256 differs')
    if t['representation']=='RAW_GIT_BLOB':
        require(git_blob(payload)==t['upstream_representation_git_sha1'],'Original rawGit payload differs')
    return {'verified':True,**t,'pointer_and_resolved_payload_are_distinct_objects':t['representation']=='RESOLVED_GIT_LFS_PAYLOAD'}
