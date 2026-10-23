// Generic metadata/provenance engineering fixtures; no model/native sessions.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {LICENSED_DATA as D} from '../epoch16/source_closure.mjs';
import {sourceClosure17 as sourceClosure} from './source_closure.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const lock='experiments/sota-2026-10-22/candidate/epoch17/model-assets.lock.json';
const helper='experiments/sota-2026-10-22/candidate/epoch17/acquire_assets.py';
const id=p=>{const b=fs.readFileSync(path.join(root,p));return{path:p,bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex')}};
const pub=[...new Set([D.provenance_manifest.path,D.acquisition_helper.path,D.license_file.path,lock,helper])].map(id);
const assets=JSON.parse(fs.readFileSync(path.join(root,lock))).assets;
const ref=p=>({path:p,sha256:pub.find(x=>x.path===p).sha256});
const rows=assets.map(x=>({path:x.path,bytes:x.bytes,sha256:x.sha256,kind:'model_asset',provenance_manifest:ref(lock),acquisition_helper:ref(helper)}));
const fresh=()=>({pins:[{path:D.path,sha256:D.sha256},...pub.map(x=>({path:x.path,sha256:x.sha256})),...assets.map(x=>({path:x.path,sha256:x.sha256}))],pubs:structuredClone(pub),reg:[structuredClone(D),...structuredClone(rows)]});
const status=x=>sourceClosure(x.pins,x.pubs,x.reg).status;
assert.equal(status(fresh()),'STRUCTURAL_CLOSURE_PASS');let n=1;
for(let i=0;i<assets.length;i++){
 for(const action of ['changed_sha','unregistered','missing_public_lock','missing_public_helper','changed_ref','duplicate','wrong_namespace','public_alias']){
  const x=fresh(),row=x.reg[i+1];
  if(action==='changed_sha')row.sha256='0'.repeat(64);
  if(action==='unregistered')x.reg.splice(i+1,1);
  if(action==='missing_public_lock')x.pubs=x.pubs.filter(r=>r.path!==lock);
  if(action==='missing_public_helper')x.pubs=x.pubs.filter(r=>r.path!==helper);
  if(action==='changed_ref')row.acquisition_helper.sha256='0'.repeat(64);
  if(action==='duplicate')x.reg.push(structuredClone(row));
  if(action==='wrong_namespace')row.path='private/weights.bin';
  if(action==='public_alias')x.pubs.push({...row,kind:undefined});
  assert.equal(status(x),'STRUCTURAL_CLOSURE_FAIL',i+':'+action);n++;
 }
}
for(const action of ['data_license','data_sha','data_missing','unpublished_pin']){
 const x=fresh();
 if(action==='data_license')x.reg[0].license='UNKNOWN';
 if(action==='data_sha')x.reg[0].sha256='0'.repeat(64);
 if(action==='data_missing')x.reg.shift();
 if(action==='unpublished_pin')x.pins.push({path:'hidden/runtime.py',sha256:'0'.repeat(64)});
 assert.equal(status(x),'STRUCTURAL_CLOSURE_FAIL',action);n++;
}
console.log(JSON.stringify({scope:'Engineering six exact official model provenance and unchanged licensed dataset closure fixtures only',tests:n,passed:n,model_native_calls:0}));
