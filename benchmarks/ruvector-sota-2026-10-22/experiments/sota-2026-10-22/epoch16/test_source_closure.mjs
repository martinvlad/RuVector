// Pure engineering metadata tests, never benchmark measurements.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {sourceClosure16,LICENSED_DATA as D} from './source_closure.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const refs=[D.provenance_manifest,D.acquisition_helper,D.license_file];
const pubs=refs.map(x=>{const b=fs.readFileSync(path.join(root,x.path));assert.equal(crypto.createHash('sha256').update(b).digest('hex'),x.sha256);return{...x,bytes:b.length};});
const fresh=()=>({pins:[{path:D.path,sha256:D.sha256},...refs],pubs:structuredClone(pubs),reg:[structuredClone(D)]});
const check=x=>sourceClosure16(x.pins,x.pubs,x.reg).status;
assert.equal(check(fresh()),'STRUCTURAL_CLOSURE_PASS');let n=1;
for(const key of ['path','sha256','bytes','kind','license','source_commit','source_url','archive_sha256','archive_member']){
 const x=fresh();x.reg[0][key]=typeof x.reg[0][key]==='number'?1:'WRONG';assert.equal(check(x),'STRUCTURAL_CLOSURE_FAIL');n++;
}
for(const key of ['provenance_manifest','acquisition_helper','license_file']){
 for(const action of ['bad_ref','missing_public','missing_pin']){
  const x=fresh();if(action==='bad_ref')x.reg[0][key].sha256='0'.repeat(64);
  if(action==='missing_public')x.pubs=x.pubs.filter(y=>y.path!==D[key].path);
  if(action==='missing_pin')x.pins=x.pins.filter(y=>y.path!==D[key].path);
  assert.equal(check(x),'STRUCTURAL_CLOSURE_FAIL');n++;
 }
}
for(const action of ['missing_data_pin','duplicate_data_pin','duplicate_data_restore','no_restore','arbitrary_data_namespace','hidden_source','public_alias']){
 const x=fresh();
 if(action==='missing_data_pin')x.pins=x.pins.slice(1);
 if(action==='duplicate_data_pin')x.pins.push(x.pins[0]);
 if(action==='duplicate_data_restore')x.reg.push(structuredClone(D));
 if(action==='no_restore')x.reg=[];
 if(action==='arbitrary_data_namespace')x.reg.push({...structuredClone(D),path:'private/other.json'});
 if(action==='hidden_source')x.pins.push({path:'unpublished/hidden.py',sha256:'0'.repeat(64)});
 if(action==='public_alias')x.pubs.push({path:D.path,sha256:D.sha256,bytes:D.bytes});
 assert.equal(check(x),'STRUCTURAL_CLOSURE_FAIL');n++;
}
console.log(JSON.stringify({scope:'Engineering source-closure regression fixtures only',tests:n,passed:n,model_native_calls:0}));
