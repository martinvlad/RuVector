'use strict';
// One source-admitted helper, eight document indexes and exactly 24 real queries.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {performance}=require('node:perf_hooks');
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const partial={schema_version:1,epoch:26,native:true,documents:[],
  native_index_initializations_attempted:0,native_index_initializations_completed:0,
  native_queries_attempted:0,native_queries_completed:0,
  Node_network_operations_attempted:0,network_violations:[]};
let progressFd=null;
function progress(stage) {
  partial.stage=stage;
  if(progressFd!==null){
    fs.writeSync(progressFd,JSON.stringify({stage,at_unix:Date.now()/1000,helper_pid:process.pid,
      native_index_initializations_attempted:partial.native_index_initializations_attempted,
      native_index_initializations_completed:partial.native_index_initializations_completed,
      native_queries_attempted:partial.native_queries_attempted,native_queries_completed:partial.native_queries_completed,
      Node_network_operations_attempted:partial.Node_network_operations_attempted})+'\n');
    fs.fsyncSync(progressFd);
  }
}
function refuse(event,args) {
  const record={event,address:String(args&&args[0]),stack:new Error().stack};
  partial.Node_network_operations_attempted++;partial.network_violations.push(record);
  progress('OFFLINE_FATAL_VIOLATION');throw new Error('Offline native helper refuses '+event);
}
for(const [name,methods] of Object.entries({
  'node:net':['connect','createConnection'],
  'node:dns':['lookup','lookupService','resolve','resolve4','resolve6','resolveAny','reverse'],
  'node:http':['request','get'], 'node:https':['request','get'],
  'node:dgram':['createSocket']})){
  const mod=require(name);for(const method of methods)mod[method]=(...args)=>refuse(name+'.'+method,args);
}
for(const type of [require('node:net').Socket,require('node:net').Server])
  for(const method of ['connect','listen'])if(type.prototype[method])
    type.prototype[method]=function(...args){return refuse(type.name+'.'+method,args);};
for(const method of Object.keys(require('node:dns').promises))
  if(typeof require('node:dns').promises[method]==='function')
    require('node:dns').promises[method]=(...args)=>refuse('dns.promises.'+method,args);
globalThis.fetch=(...args)=>refuse('fetch',args);

(async()=>{
  const root=fs.realpathSync(process.argv[2]),source=fs.readFileSync(process.argv[3]);
  const bundle=JSON.parse(source),output=process.argv[4];
  const planPath=process.argv[5],expected=process.argv[6],admissionPath=process.argv[7];
  if(planPath!==path.join(root,'experiments/sota-2026-10-22/epoch26/plan.json')||hash(planPath)!==expected)
    throw new Error('Exact native plan gate failed');
  const plan=JSON.parse(fs.readFileSync(planPath)),admission=JSON.parse(fs.readFileSync(admissionPath));
  const owner=JSON.parse(fs.readFileSync(path.join(root,'../owner.json')));
  const ownerStat=fs.readFileSync('/proc/72224/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
  if(admissionPath!==path.join(root,'experiments/sota-2026-10-22/epoch26/NATIVE_ADMISSION.json')
      ||admission.epoch!==26||admission.phase!=='dev'||admission.verified_actual_remote_readback!==true
      ||admission.plan_sha256!==expected||admission.source_freeze_sha256!==plan.source_freeze_sha256
      ||admission.owner_pid!==72224||admission.owner_startticks!==14702559
      ||plan.epoch!==26||plan.phase!=='dev'||plan.diagnostic_only!==true||plan.actual_project!==root
      ||plan.source_checkpoint!=='5acc487d6f968319a95a211fb7b3287900ca4a22'
      ||owner.pid!==72224||owner.startticks!==14702559||Date.now()/1000>=owner.expires_unix
      ||['Z','X'].includes(ownerStat[0])||Number(ownerStat[19])!==14702559)
    throw new Error('Late remote source/exact owner admission failed');
  const ownPath='experiments/sota-2026-10-22/candidate/epoch26/native.cjs';
  const ownPin=plan.pins.find(row=>row.path===ownPath);
  if(!ownPin||hash(path.join(root,ownPath))!==ownPin.sha256)throw new Error('Native helper source changed');
  progressFd=fs.openSync(process.argv[8],'wx',0o600);progress('ADMISSION_VERIFIED_BEFORE_NATIVE_IMPORT');
  if(bundle.documents.length!==8||bundle.documents.reduce((n,d)=>n+d.queries.length,0)!==24)
    throw new Error('Eight indexes and 24 native queries required');
  const corePath=path.join(root,'retrieval/node_modules/@ruvector/core');
  const binary=path.join(root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node');
  if(hash(binary)!=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e')
    throw new Error('Exact native binary changed');
  const core=require(corePath);
  Object.assign(partial,{package_version:require(path.join(corePath,'package.json')).version,
    platform_package_version:require(path.join(root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/package.json')).version,
    binary_version:core.version(),native_binary_sha256:hash(binary),helper_pid:process.pid});
  if(partial.package_version!=='0.1.33'||partial.platform_package_version!=='0.1.31'||partial.binary_version!=='2.3.0')
    throw new Error('Exact native package versions changed');
  const working=process.cwd();
  for(let i=0;i<bundle.documents.length;i++){
    const item=bundle.documents[i],vectors=item.vectors;
    if(!vectors.length||vectors.length>192||item.queries.length!==3
        ||vectors.some(v=>v.length!==384||v.some(x=>!Number.isFinite(x)))
        ||item.queries.some(q=>q.vector.length!==384||q.vector.some(x=>!Number.isFinite(x))))
      throw new Error('Finite real BGE384 exact-document vectors required');
    const storage=path.join(working,'index-'+i);fs.mkdirSync(storage);process.chdir(storage);
    const started=performance.now();partial.native_index_initializations_attempted++;progress('BEFORE_NATIVE_INDEX');
    const db=new core.VectorDb({dimensions:384,distanceMetric:core.JsDistanceMetric.Cosine,
      storagePath:path.join(storage,'ruvector.db')});
    if(await db.len()!==0)throw new Error('Native index must start empty');
    for(let j=0;j<vectors.length;j++)await db.insert({id:String(j),vector:new Float32Array(vectors[j])});
    if(await db.len()!==vectors.length)throw new Error('Native index incomplete');
    partial.native_index_initializations_completed++;progress('AFTER_NATIVE_INDEX');
    const row={document_id:item.document_id,initialized_vectors:await db.len(),
      initialization_ms:performance.now()-started,queries:[]};partial.documents.push(row);
    for(const query of item.queries){
      const k=Math.min(40,vectors.length);partial.native_queries_attempted++;progress('BEFORE_NATIVE_SEARCH');
      const t=performance.now(),hits=await db.search({vector:new Float32Array(query.vector),k});
      const queryMs=performance.now()-t;partial.native_queries_completed++;progress('AFTER_NATIVE_SEARCH');
      const ids=hits.map(hit=>Number(hit.id));
      if(ids.length!==k||new Set(ids).size!==k||ids.some(id=>!Number.isInteger(id)||id<0||id>=vectors.length))
        throw new Error('Invalid actual native result IDs');
      const rawHits=hits.map(hit=>{
        const out={};for(const key of Object.keys(hit)){
          if(typeof hit[key]==='number'&&!Number.isFinite(hit[key]))throw new Error('Nonfinite native field');
          out[key]=hit[key];
        }
        for(const key of ['score','distance'])if(key in hit){
          if(typeof hit[key]!=='number'||!Number.isFinite(hit[key]))throw new Error('Invalid raw native score/distance');
          out[key]=hit[key];
        }
        return out;
      });
      row.queries.push({case_id:query.id,ids,raw_hits:rawHits,requested_k:k,query_ms:queryMs,
        native_order_used_without_replacement:true,
        score_semantics:'Raw native fields retained without reinterpretation or reranking.'});
    }
    process.chdir(working);progress('DOCUMENT_COMPLETED');
  }
  if(partial.Node_network_operations_attempted||partial.network_violations.length)
    throw new Error('Persistent offline violation flag set');
  Object.assign(partial,{bundle_sha256:crypto.createHash('sha256').update(source).digest('hex'),
    helper_peak_RSS_bytes:process.resourceUsage().maxRSS*1024,
    helper_user_CPU_microseconds:process.resourceUsage().userCPUTime,
    helper_system_CPU_microseconds:process.resourceUsage().systemCPUTime});
  progress('HELPER_COMPLETED');fs.writeFileSync(output,JSON.stringify(partial)+'\n',{flag:'wx'});
  fs.closeSync(progressFd);
})().catch(error=>{
  partial.error={name:error.name,message:String(error.message||error)};
  try{progress('HELPER_FAILED');}catch(ignored){}
  try{fs.writeFileSync(process.argv[4]+'.failure.json',JSON.stringify(partial)+'\n',{flag:'wx'});}catch(ignored){}
  console.error(error.stack||String(error));process.exitCode=1;
});
