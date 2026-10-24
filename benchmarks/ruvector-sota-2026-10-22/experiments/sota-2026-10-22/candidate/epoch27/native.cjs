'use strict';
// One source-admitted helper, eight document indexes and exactly 24 real queries.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {performance}=require('node:perf_hooks');
const DOCUMENT_IDS=['609','380','592','454','559','515','349','223'];
const HYPOTHESIS_IDS=['nda-17','nda-7','nda-3'];
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const bytesHash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const compactSpec={schema:'epoch27-native-compact-f32le-v2',
  vector_dtype:'IEEE754 float32',vector_byte_order:'little-endian',vector_dimensions:384,
  vector_hash:'SHA256 of exactly 384 consecutive Buffer.writeFloatLE values, no prefix',
  source_vector_validation:'Every observed native hit vector must have exactly numeric keys 0..383, finite float32 values, and byte-equal float32le bytes to the indexed source vector before stripping.',
  metadata_hash:'SHA256 of UTF8 canonical JSON {"present":false}; no newline; insert has id+vector only and native metadata must be absent.',
  source_numeric_storage:'native-bundle.json once; query and index vector matrices are lossless canonical base64 of actual C-order float32le input bytes, with shape/length/SHA256',
  retained_fields:'All original nonvector fields, original Object.keys as raw_keys, exact ordered IDs and score semantics retained; only source-validated vector numeric array removed.'};
function vectorBytes(vector){
  if(vector===null||typeof vector!=='object')throw new Error('Native/source vector is not numeric array/object');
  const keys=Object.keys(vector);
  if(keys.length!==384||keys.some((key,index)=>key!==String(index)))
    throw new Error('Vector must have exactly numeric keys0..383 in order');
  const bytes=Buffer.alloc(384*4);
  for(let i=0;i<384;i++){
    const value=vector[i];
    if(typeof value!=='number'||!Number.isFinite(value)||!Object.is(Math.fround(value),value))
      throw new Error('Vector contains nonfinite or non-float32 value');
    bytes.writeFloatLE(value,i*4);
  }
  return bytes;
}
function decodeBlock(block,expectedRows=null){
  if(block===null||typeof block!=='object'||block.encoding!=='base64'||block.dtype!=='float32le'
      ||!Array.isArray(block.shape)||block.shape.length!==2||!Number.isInteger(block.shape[0])
      ||block.shape[0]<1||block.shape[0]>192||block.shape[1]!==384
      ||(expectedRows!==null&&block.shape[0]!==expectedRows)
      ||block.bytes!==block.shape[0]*384*4||typeof block.data_base64!=='string'
      ||!/^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(block.data_base64)
      ||!/^[0-9a-f]{64}$/.test(block.sha256))throw new Error('Invalid exact base64 float32le source block');
  const bytes=Buffer.from(block.data_base64,'base64');
  if(bytes.length!==block.bytes||bytes.toString('base64')!==block.data_base64||bytesHash(bytes)!==block.sha256)
    throw new Error('Source block base64/length/SHA256 mismatch');
  const rows=[];
  for(let row=0;row<block.shape[0];row++){
    const vector=new Float32Array(384);
    for(let col=0;col<384;col++){
      const value=bytes.readFloatLE((row*384+col)*4);
      if(!Number.isFinite(value))throw new Error('Nonfinite source float32 value');
      vector[col]=value;
    }
    if(!vectorBytes(vector).equals(bytes.subarray(row*1536,(row+1)*1536)))
      throw new Error('Float32 core source bits changed during decode');
    rows.push(vector);
  }
  return rows;
}
const metadataAbsentHash=bytesHash(Buffer.from('{"present":false}','utf8'));
function compactHit(hit,vectors){
  if(hit===null||typeof hit!=='object'||typeof hit.id!=='string'||!/^\d+$/.test(hit.id))
    throw new Error('Actual native hit ID must be exact decimal string');
  const index=Number(hit.id);
  if(!Number.isInteger(index)||index<0||index>=vectors.length||String(index)!==hit.id)
    throw new Error('Actual native hit is outside exact indexed source');
  if(!Object.prototype.hasOwnProperty.call(hit,'vector'))throw new Error('Actual native vector absent');
  const observed=vectorBytes(hit.vector),source=vectorBytes(vectors[index]);
  if(!observed.equals(source))throw new Error('Actual native hit vector differs from indexed source');
  if(Object.prototype.hasOwnProperty.call(hit,'metadata'))
    throw new Error('Actual native metadata present but indexed source metadata was absent');
  const out={};
  for(const key of Object.keys(hit)){
    if(key==='vector')continue;
    if(typeof hit[key]==='number'&&!Number.isFinite(hit[key]))throw new Error('Nonfinite native field');
    out[key]=hit[key];
  }
  if(typeof hit.score!=='number'||!Number.isFinite(hit.score))throw new Error('Invalid actual native score');
  if('distance' in hit&&(typeof hit.distance!=='number'||!Number.isFinite(hit.distance)))
    throw new Error('Invalid actual native distance');
  out.raw_keys=Object.keys(hit);
  out.vector_receipt={source_vector_index:index,dimensions:384,dtype:'float32le',
    sha256:bytesHash(observed),source_sha256:bytesHash(source),source_equal_before_stripping:true};
  out.metadata_receipt={present:false,canonical_json:'{"present":false}',sha256:metadataAbsentHash,
    source_equal_before_stripping:true};
  return out;
}
const partial={schema_version:1,epoch:27,native:true,documents:[],
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
  'node:http':['request','get'], 'node:https':['request','get'],
  'node:dgram':['createSocket']})){
  const mod=require(name);for(const method of methods)mod[method]=(...args)=>refuse(name+'.'+method,args);
}
for(const type of [require('node:net').Socket,require('node:net').Server])
  for(const method of ['connect','listen'])if(type.prototype[method])
    type.prototype[method]=function(...args){return refuse(type.name+'.'+method,args);};
// Resolver classes have additional callback/promise resolve methods beyond the
// module's common lookup functions. Cover every currently exposed network name.
function patchDns(target,label,walkPrototype=false){
  for(let current=target;current&&current!==Object.prototype;current=walkPrototype?Object.getPrototypeOf(current):null){
    for(const method of Object.getOwnPropertyNames(current))
      if(/^(lookup|resolve)/.test(method)||method==='reverse')
        if(typeof current[method]==='function')
          current[method]=(...args)=>refuse(label+'.'+method,args);
  }
}
const dns=require('node:dns');
patchDns(dns,'dns');patchDns(dns.promises,'dns.promises');
patchDns(dns.Resolver.prototype,'dns.Resolver',true);
patchDns(dns.promises.Resolver.prototype,'dns.promises.Resolver',true);
// Keep stdout/stderr pipe logging functional; connected Socket read/write paths
// have no legitimate use in this helper and must remain fatal if reached.
for(const method of ['write','end','read','send','sendto','sendmsg','recv','recvfrom','recvmsg','accept']){
  const prototype=require('node:net').Socket.prototype,original=prototype[method];
  if(typeof original==='function')prototype[method]=function(...args){
    if(this===process.stdout||this===process.stderr)return original.apply(this,args);
    return refuse('Socket.'+method,args);
  };
}
globalThis.fetch=(...args)=>refuse('fetch',args);

module.exports={vectorBytes,decodeBlock,compactHit,compactSpec,
  offlineDiagnostics:()=>({attempts:partial.Node_network_operations_attempted,
    violations:partial.network_violations.slice()})};
if(require.main===module)(async()=>{
  const root=fs.realpathSync(process.argv[2]),source=fs.readFileSync(process.argv[3]);
  const bundle=JSON.parse(source),output=process.argv[4];
  if(bundle.schema_version!==3||bundle.vector_encoding!=='base64_float32le_c_order'
      ||bundle.metadata_policy!=='insert id and vector only; metadata absent')
    throw new Error('Exact source bundle vector/metadata schema required');
  const planPath=process.argv[5],expected=process.argv[6],admissionPath=process.argv[7];
  if(planPath!==path.join(root,'experiments/sota-2026-10-22/epoch27/plan.json')||hash(planPath)!==expected)
    throw new Error('Exact native plan gate failed');
  const plan=JSON.parse(fs.readFileSync(planPath)),admission=JSON.parse(fs.readFileSync(admissionPath));
  const owner=JSON.parse(fs.readFileSync(path.join(root,'../owner.json')));
  const ownerStat=fs.readFileSync('/proc/75591/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
  if(admissionPath!==path.join(root,'experiments/sota-2026-10-22/epoch27/NATIVE_ADMISSION.json')
      ||admission.epoch!==27||admission.phase!=='dev'||admission.verified_actual_remote_readback!==true
      ||admission.plan_sha256!==expected||admission.source_freeze_sha256!==plan.source_freeze_sha256
      ||admission.owner_pid!==75591||admission.owner_startticks!==15190845
      ||plan.epoch!==27||plan.phase!=='dev'||plan.diagnostic_only!==true||plan.actual_project!==root
      ||plan.source_checkpoint!=='6e4ad4ab0b6a09a6a1083335ed0401637227d17f'
      ||owner.pid!==75591||owner.startticks!==15190845||Date.now()/1000>=owner.expires_unix
      ||['Z','X'].includes(ownerStat[0])||Number(ownerStat[19])!==15190845)
    throw new Error('Late remote source/exact owner admission failed');
  const ownPath='experiments/sota-2026-10-22/candidate/epoch27/native.cjs';
  const ownPin=plan.pins.find(row=>row.path===ownPath);
  if(!ownPin||hash(path.join(root,ownPath))!==ownPin.sha256)throw new Error('Native helper source changed');
  progressFd=fs.openSync(process.argv[8],'wx',0o600);progress('ADMISSION_VERIFIED_BEFORE_NATIVE_IMPORT');
  if(bundle.documents.length!==8||bundle.documents.reduce((n,d)=>n+d.queries.length,0)!==24)
    throw new Error('Eight indexes and 24 native queries required');
  if(bundle.documents.some((item,index)=>item.document_id!==DOCUMENT_IDS[index]
      ||item.queries.length!==3||item.queries.some((query,h)=>Object.keys(query).join(',')!=='id'
        ||query.id!=='original-contractnli:train:epoch27:dev:'+DOCUMENT_IDS[index]+':'+HYPOTHESIS_IDS[h])))
    throw new Error('Exact prospective eight-document and24case identity/order closure failed');
  const corePath=path.join(root,'retrieval/node_modules/@ruvector/core');
  const binary=path.join(root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node');
  if(hash(binary)!=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e')
    throw new Error('Exact native binary changed');
  const core=require(corePath);
  Object.assign(partial,{package_version:require(path.join(corePath,'package.json')).version,
    platform_package_version:require(path.join(root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/package.json')).version,
    binary_version:core.version(),native_binary_sha256:hash(binary),helper_pid:process.pid,
    compact_schema:compactSpec.schema,compact_receipt_spec:compactSpec});
  if(partial.package_version!=='0.1.33'||partial.platform_package_version!=='0.1.31'||partial.binary_version!=='2.3.0')
    throw new Error('Exact native package versions changed');
  const working=process.cwd();
  for(let i=0;i<bundle.documents.length;i++){
    const item=bundle.documents[i],vectors=decodeBlock(item.vectors),queryVectors=decodeBlock(item.query_vectors,3);
    if(!vectors.length||vectors.length>192||item.queries.length!==3
        ||vectors.some(v=>v.length!==384||v.some(x=>!Number.isFinite(x)))
        ||queryVectors.some(v=>v.length!==384||v.some(x=>!Number.isFinite(x))))
      throw new Error('Finite real BGE384 exact-document vectors required');
    for(const vector of vectors)vectorBytes(vector);
    for(const vector of queryVectors)vectorBytes(vector);
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
    for(const [queryIndex,query] of item.queries.entries()){
      const k=Math.min(40,vectors.length);partial.native_queries_attempted++;progress('BEFORE_NATIVE_SEARCH');
      const t=performance.now(),hits=await db.search({vector:queryVectors[queryIndex],k});
      const queryMs=performance.now()-t;partial.native_queries_completed++;progress('AFTER_NATIVE_SEARCH');
      const ids=hits.map(hit=>Number(hit.id));
      if(ids.length!==k||new Set(ids).size!==k||ids.some(id=>!Number.isInteger(id)||id<0||id>=vectors.length))
        throw new Error('Invalid actual native result IDs');
      const rawHits=hits.map(hit=>compactHit(hit,vectors));
      row.queries.push({case_id:query.id,ids,raw_hits:rawHits,requested_k:k,query_ms:queryMs,
        native_order_used_without_replacement:true,
        score_semantics:'Actual native score field retained without reinterpretation or reranking; vector stripped only after exact indexed-source equality.'});
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
