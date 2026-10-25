"""Pure future-only source declaration vs materialized payload identity checks.

No file/network/model/tokenizer/native operations. The caller must separately
compute real payload hashes and retain the exact upstream/source-declaration
catalog. An observed materialization receipt cannot replace that declaration.
"""
import hashlib
import re

HEX256=re.compile('[0-9a-f]{64}')
HEX160=re.compile('[0-9a-f]{40}')
RAW_GIT='RAW_GIT_BLOB_PAYLOAD'
LFS='CANONICAL_GIT_LFS_POINTER_WITH_SEPARATE_SHA256_PAYLOAD'


def git_blob_sha1(body):
    if type(body)is not bytes:raise ValueError('Exact byte string required')
    return hashlib.sha1(b'blob '+str(len(body)).encode('ascii')+b'\0'+body).hexdigest()


def expected_payload(declaration):
    """Admit exactly one explicitly typed reviewed source payload digest.

    Historic source declarations use upstream_sha256 for Git-LFS payloads and
    metadata_body_sha256 for ordinary Git bodies. A generic observed sha256
    field is deliberately NOT a source declaration or representation alias.
    """
    if not isinstance(declaration,dict):raise ValueError('Reviewed source declaration required')
    required={'path','bytes','source_url','upstream_git_blob_sha1'}
    typed=set(declaration)&{'upstream_sha256','metadata_body_sha256'}
    if len(typed)!=1 or set(declaration)!=required|typed:
        raise ValueError('Exactly one explicit upstream_sha256 or metadata_body_sha256 source declaration required; observed sha256 is not an alias')
    name=declaration['path'];size=declaration['bytes'];source=declaration['source_url'];upstream=declaration['upstream_git_blob_sha1']
    if (type(name)is not str or not name or name in('.','..')or '/'in name or '\\'in name
            or type(size)is not int or size<0 or type(source)is not str or not source.startswith('https://')
            or type(upstream)is not str or HEX160.fullmatch(upstream)is None):
        raise ValueError('Malformed reviewed exact source identity')
    key=next(iter(typed));payload=declaration[key]
    if type(payload)is not str or HEX256.fullmatch(payload)is None:raise ValueError('Exact source payload SHA256 required')
    result={'path':name,'bytes':size,'source_url':source,'payload_sha256':payload,
            'upstream_git_object_sha1':upstream,'representation':RAW_GIT if key=='metadata_body_sha256'else LFS,
            'raw_payload_git_blob_sha1_required':key=='metadata_body_sha256'}
    if key=='upstream_sha256':
        # The fixed reviewed sources use the exact three-line canonical pointer.
        # Noncanonical/extended pointers require their own reviewed declaration;
        # this guard never guesses or weakens the upstream identity.
        pointer=('version https://git-lfs.github.com/spec/v1\noid sha256:'+payload+'\nsize '+str(size)+'\n').encode('ascii')
        if git_blob_sha1(pointer)!=upstream:raise ValueError('Declared upstream Git object is not the exact canonical LFS pointer for payload oid/size')
        result.update(upstream_lfs_pointer_bytes=len(pointer),upstream_lfs_pointer_sha256=hashlib.sha256(pointer).hexdigest(),
                      upstream_lfs_pointer_git_sha1=git_blob_sha1(pointer))
    return result


def bind_observed_lock(declaration,observed):
    """Metadata binding only; it does not claim to have read the payload."""
    identity=expected_payload(declaration)
    if (not isinstance(observed,dict)or observed.get('path')!=identity['path']or type(observed.get('bytes'))is not int
            or observed['bytes']!=identity['bytes']or observed.get('source_url')!=identity['source_url']
            or observed.get('upstream_git_blob_sha1')!=identity['upstream_git_object_sha1']
            or observed.get('sha256')!=identity['payload_sha256']):
        raise ValueError('Observed materialization receipt differs from independently reviewed source declaration')
    return identity


def verify_payload_observation(declaration,observed_bytes,observed_sha256,observed_payload_git_sha1=None):
    """Check caller-computed payload hashes against a typed source declaration."""
    identity=expected_payload(declaration)
    if type(observed_bytes)is not int or observed_bytes!=identity['bytes']or observed_sha256!=identity['payload_sha256']:
        raise ValueError('Real payload size/SHA256 differs from reviewed source')
    if identity['raw_payload_git_blob_sha1_required']:
        if observed_payload_git_sha1!=identity['upstream_git_object_sha1']:
            raise ValueError('Real ordinary Git body differs from upstream Git blob')
    elif observed_payload_git_sha1 is not None and (type(observed_payload_git_sha1)is not str or HEX160.fullmatch(observed_payload_git_sha1)is None):
        raise ValueError('Malformed optional separately recorded LFS payload Git hash')
    return {**identity,'payload_size_and_SHA256_verified':True,
            'raw_payload_git_sha1_verified':identity['raw_payload_git_blob_sha1_required'],
            'LFS_pointer_SHA1_compared_to_payload_SHA1':False}


def bind_catalog(expected_rows,observed_rows):
    if type(expected_rows)is not list or type(observed_rows)is not list or not expected_rows:raise ValueError('Nonempty declaration and receipt catalogs required')
    names=[r.get('path')for r in expected_rows];observed_names=[r.get('path')for r in observed_rows]
    if len(set(names))!=len(names)or len(set(observed_names))!=len(observed_names)or set(names)!=set(observed_names):
        raise ValueError('Duplicate/missing/extra source or materialization catalog identities')
    observed={r['path']:r for r in observed_rows}
    return [bind_observed_lock(r,observed[r['path']])for r in expected_rows]
