"""Disjoint tiny byte/metadata fixtures; never opens real model payloads."""
from pathlib import Path
import hashlib,json,time
from copy import deepcopy
from future_asset_identity_reference_v1 import *

payload=b'independent tiny public unit fixture\n';oid=hashlib.sha256(payload).hexdigest()
raw={'bytes':len(payload),'metadata_body_sha256':oid,'upstream_git_blob_sha1':git_blob(payload)}
lfs={'bytes':len(payload),'upstream_sha256':oid,'upstream_git_blob_sha1':'0'*40}
tmp=typed_declaration(lfs);lfs['upstream_git_blob_sha1']=git_blob(canonical_lfs_pointer(tmp))
assert verify_payload(payload,raw)['representation']=='RAW_GIT_BLOB'
assert verify_payload(payload,lfs)['representation']=='RESOLVED_GIT_LFS_PAYLOAD'
assert git_blob(payload)!=lfs['upstream_git_blob_sha1']
failures=[]
def rejected(name,data,declaration):
    try:verify_payload(data,declaration)
    except ValueError as e:failures.append(dict(name=name,rejected=True,reason=str(e)))
    else:raise AssertionError('Unsound identity accepted: '+name)
rejected('changed_LFS_payload',payload+b'x',lfs)
rejected('changed_raw_payload',payload+b'x',raw)
for kind,source in [('raw',raw),('LFS',lfs)]:
    bad=deepcopy(source);bad['bytes']+=1;rejected(kind+'_wrong_size',payload,bad)
    bad=deepcopy(source);bad['upstream_git_blob_sha1']='f'*40;rejected(kind+'_wrong_upstream_representation',payload,bad)
    bad=deepcopy(source);key='metadata_body_sha256'if kind=='raw'else'upstream_sha256';bad[key]='0'*64;rejected(kind+'_wrong_payload_oid',payload,bad)
    bad=deepcopy(source);bad['bytes']=True;rejected(kind+'_bool_size',payload,bad)
observed={'bytes':len(payload),'sha256':oid,'upstream_git_blob_sha1':lfs['upstream_git_blob_sha1']}
rejected('materialized_lock_cannot_self_declare_original_LFS_identity',payload,observed)
ambiguous={**raw,'upstream_sha256':oid};rejected('ambiguous_raw_plus_LFS_declaration',payload,ambiguous)
bad=deepcopy(lfs);bad['upstream_git_blob_sha1']=git_blob(payload);rejected('LFS_pointer_must_not_be_payload_GitSHA1',payload,bad)
bad=deepcopy(raw);bad['upstream_git_blob_sha1']=lfs['upstream_git_blob_sha1'];rejected('raw_payload_must_not_be_LFS_pointer_GitSHA1',payload,bad)
real_metadata=[
 {'name':'spm.model','bytes':2447305,'upstream_sha256':'5598d5e96f339a8d980c15f9afd405a2e5e1be7db41de3ed13b0f03fac1e8c17','upstream_git_blob_sha1':'c146a1df1f80d26596bbb4d0fadc43bca9a8145c'},
 {'name':'pytorch_model.bin','bytes':3133958098,'upstream_sha256':'5b2d8ddf6c80e4e6105b27cdb9fa346a8ba1f0c0dfd410b0007be894567cb4db','upstream_git_blob_sha1':'aba315cb1d255ada5671f0de52bcbc5148771376'}]
for original in real_metadata:assert source_representation_check(typed_declaration(original))
A=Path('/workspace/ruvector-e37-independent-audit')
def ref(p):b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
report={'schema_version':1,'epoch':37,'status':'PASS_FUTURE_ONLY_PURE_ASSET_REPRESENTATION_REFERENCE','source':ref(A/'future_asset_identity_reference_v1.py'),'tests':ref(Path(__file__).resolve()),'tiny_positive_payload_cases':2,'negative_mutation_cases':failures,'exact_original_LFS_pointer_metadata_checks':2,'deployment_status':'UNDEPLOYED_REFERENCE_ONLY; frozenE37guard/plan/a93source unchanged, no dispatch or runtime verification on actual assets.','scientific_scope':'Representation unit checks only; no benchmark question, actual12case classifier, model/tokenizer/native call or generalization score.','required_future_change':'Use a separately pinned original-source expected catalog retaining explicit rawGit metadata_body_sha256 versus LFS upstream_sha256 identities. Always verify resolved payload SHA256+size, compare rawGit SHA1 only for rawGit, validate LFS pointer SHA1 from its declared oid+size. Never make the observed materialization lock its own expected authority.','original_large_weight_payload_reads':0,'actual_model_tokenizer_native_or_EVALUATE_BIND_calls':0,'external_mutations':0,'checked_at_unix':time.time()}
p=A/'future-asset-identity-reference-unit-checks-v1.json';p.write_text(json.dumps(report,indent=2)+'\n');print(p,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
