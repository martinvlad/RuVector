// Actual20-entry declaration metadata and adversarial closure fixtures only.
// No model/native imports, binary reads, original cases, labels or networking.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {sourceClosure17} from '../source_closure.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../../../..');
const s=path.join(root,'experiments/sota-2026-10-22');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const old=read(path.join(s,'epoch16/external-registry.json'));
const lockRel='experiments/sota-2026-10-22/candidate/epoch17/model-assets.lock.json';
const helperRel='experiments/sota-2026-10-22/candidate/epoch17/acquire_assets.py';
const lock=read(path.join(root,lockRel));
const reference=relative=>({path:relative,sha256:hash(fs.readFileSync(path.join(root,relative)))});
const registry=[...old,...lock.assets.map(a=>({path:a.path,bytes:a.bytes,sha256:a.sha256,
    kind:'model_asset',repo:lock.repo,revision:lock.revision,
    provenance_manifest:reference(lockRel),acquisition_helper:reference(helperRel)}))];
assert.equal(registry.length,20);
const refs=new Map();
for(const row of registry)for(const key of ['provenance_manifest','acquisition_helper','license_file']){
  const ref=row[key];if(!ref)continue;
  const b=fs.readFileSync(path.join(root,ref.path));
  assert.equal(hash(b),ref.sha256);
  refs.set(ref.path,{...ref,bytes:b.length});
}
const pubs=[...refs.values()];
const pins=[...registry.map(({path,sha256})=>({path,sha256})),...pubs.map(({path,sha256})=>({path,sha256}))];
const fresh=()=>structuredClone({pins,pubs,registry});
const check=x=>sourceClosure17(x.pins,x.pubs,x.registry);
assert.equal(check(fresh()).status,'STRUCTURAL_CLOSURE_PASS');
assert.equal(check(fresh()).covered_external,20);
let tests=1;
for(const action of ['missing_weight','wrong_weight_hash','wrong_weight_namespace','missing_manifest',
    'wrong_helper_hash','missing_helper','duplicate_restore','public_external_alias','duplicate_pin',
    'wrong_data_license','wrong_data_archive','unregistered_source','arbitrary_dataset']){
  const x=fresh(),weight=x.registry.findIndex(r=>r.path.endsWith('/pytorch_model.bin'));
  if(action==='missing_weight')x.registry.splice(weight,1);
  if(action==='wrong_weight_hash')x.registry[weight].sha256='0'.repeat(64);
  if(action==='wrong_weight_namespace')x.registry[weight].path='unpublished/weights.bin';
  if(action==='missing_manifest')x.pubs=x.pubs.filter(r=>r.path!==lockRel);
  if(action==='wrong_helper_hash')x.registry[weight].acquisition_helper.sha256='0'.repeat(64);
  if(action==='missing_helper')x.pubs=x.pubs.filter(r=>r.path!==helperRel);
  if(action==='duplicate_restore')x.registry.push(structuredClone(x.registry[weight]));
  if(action==='public_external_alias')x.pubs.push({...x.registry[weight]});
  if(action==='duplicate_pin')x.pins.push(structuredClone(x.pins[0]));
  if(action==='wrong_data_license')x.registry.find(r=>r.kind==='licensed_dataset_asset').license='OTHER';
  if(action==='wrong_data_archive')x.registry.find(r=>r.kind==='licensed_dataset_asset').archive_sha256='0'.repeat(64);
  if(action==='unregistered_source')x.pins.push({path:'unpublished/hidden.py',sha256:'0'.repeat(64)});
  if(action==='arbitrary_dataset')x.registry.push({...structuredClone(x.registry.find(r=>r.kind==='licensed_dataset_asset')),path:'other/data.json'});
  assert.equal(check(x).status,'STRUCTURAL_CLOSURE_FAIL',action);tests++;
}
console.log(JSON.stringify({status:'INDEPENDENT20_ENTRY_REGISTRY_METADATA_FIXTURES_PASS',tests,external_assets:20,
  native_model_fit_paid_GPU_calls:0,annotation_choices:0}));
