// Strict registry multiplicity plus unchanged licensed-data/model provenance guard.
// Metadata only; no native/model/network operations.
import {sourceClosure16} from '../epoch16/source_closure.mjs';
export function sourceClosure18(pins,published,registry) {
  const base=sourceClosure16(pins,published,registry);
  const extra=[];
  if(Array.isArray(registry)) {
    const seen=new Set();
    const publicPaths=new Set(Array.isArray(published)?published.map(x=>x?.path):[]);
    for(const row of registry) {
      if(seen.has(row?.path))extra.push({code:'DUPLICATE_EXTERNAL_REGISTRY_PATH',path:row?.path,detail:'Even identical duplicate restore entries are refused'});
      if(publicPaths.has(row?.path))extra.push({code:'EXTERNAL_PUBLIC_PATH_ALIAS',path:row?.path,detail:'Restored external assets cannot alias published source'});
      seen.add(row?.path);
    }
  }
  return {...base,status:base.issues.length+extra.length?'STRUCTURAL_CLOSURE_FAIL':'STRUCTURAL_CLOSURE_PASS',issues:[...base.issues,...extra]};
}
