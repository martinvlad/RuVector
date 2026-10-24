'use strict';
// Source-admitted helper: original core2.3 API,8 indexes and24 genuine searches.
// Runtime preload supplies phase admission, inherited CPU policy and network API guards.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {performance}=require('node:perf_hooks');
const KIND='REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC';
const BINARY_SHA='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e';
const IDS={train:['237','120','187','422','464','207','294','250'],dev:['594','343','394','103','403','481','154','306']};
const HYPOTHESES=['nda-17','nda-7','nda-3'];
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const absent='{"present":false}',absentHash=hash(Buffer.from(absent,'utf8'));

function vectorBytes(vector){
  if(!vector||typeof vector!=='object')throw new Error('Actual vector object required');
  const keys=Object.keys(vector);
  if(keys.length!==384||keys.some((key,index)=>key!==String(index)))throw new Error('Exact384 source/native vector keys required');
  const out=Buffer.alloc(1536);
  for(let i=0;i<384;i++){
    if(typeof vector[i]!=='number'||!Number.isFinite(vector[i])||!Object.is(Math.fround(vector[i]),vector[i]))
      throw new Error('Nonfinite or non-float32 actual vector');
    out.writeFloatLE(vector[i],i*4);
  }
  return out;
}

function decode(block,rows=null){
  if(!block||block.encoding!=='base64'||block.dtype!=='float32le'||!Array.isArray(block.shape)
      ||block.shape.length!==2||!Number.isInteger(block.shape[0])||block.shape[0]<1||block.shape[0]>192
      ||block.shape[1]!==384||(rows!==null&&block.shape[0]!==rows)
      ||block.bytes!==block.shape[0]*1536||typeof block.data_base64!=='string'
      ||!/^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(block.data_base64))
    throw new Error('Exact bounded lossless float32le block required');
  const bytes=Buffer.from(block.data_base64,'base64');
  if(bytes.length!==block.bytes||bytes.toString('base64')!==block.data_base64||hash(bytes)!==block.sha256)
    throw new Error('Lossless block bytes/base64/hash differ');
  const result=[];
  for(let row=0;row<block.shape[0];row++){
    const vector=new Float32Array(384);
    for(let col=0;col<384;col++)vector[col]=bytes.readFloatLE(row*1536+col*4);
    if(!vectorBytes(vector).equals(bytes.subarray(row*1536,(row+1)*1536)))throw new Error('Source float32 bits changed during decode');
    result.push(vector);
  }
  return result;
}

function compact(hit,vectors){
  if(!hit||typeof hit.id!=='string'||!/^\d+$/.test(hit.id)||String(Number(hit.id))!==hit.id)
    throw new Error('Canonical decimal native source ID required');
  const index=Number(hit.id);
  if(index<0||index>=vectors.length)throw new Error('Native hit outside exact document index');
  const actual=vectorBytes(hit.vector),source=vectorBytes(vectors[index]);
  if(!actual.equals(source))throw new Error('Actual returned vector differs from indexed source bytes');
  if(Object.prototype.hasOwnProperty.call(hit,'metadata'))throw new Error('Indexed metadata was absent');
  if(typeof hit.score!=='number'||!Number.isFinite(hit.score))throw new Error('Actual raw native score missing/nonfinite');
  const out={};
  for(const key of Object.keys(hit)){
    if(key==='vector')continue;
    if(typeof hit[key]==='number'&&!Number.isFinite(hit[key]))throw new Error('Nonfinite raw native field');
    out[key]=hit[key];
  }
  out.raw_keys=Object.keys(hit);
  out.vector_receipt={source_vector_index:index,dimensions:384,dtype:'float32le',sha256:hash(actual),
    source_sha256:hash(source),source_equal_before_stripping:true};
  out.metadata_receipt={present:false,canonical_json:absent,sha256:absentHash,source_equal_before_stripping:true};
  return out;
}

module.exports={vectorBytes,decode,compact};
if(require.main===module){
  const partial={schema_version:1,epoch:30,kind:KIND,phase:process.env.E30_PHASE,native:true,
    documents:[],errors:[],compact_schema:'epoch30-native-context-f32le-v1',
    native_index_initializations_attempted:0,native_index_initializations_completed:0,
    native_queries_attempted:0,native_queries_completed:0,native_insertions_attempted:0,native_insertions_completed:0,
    native_len_calls_attempted:0,native_len_calls_completed:0,native_version_calls_attempted:0,native_version_calls_completed:0,
    native_hit_source_validations:0};
  let fd=null;
  function progress(event){
    partial.stage=event;
    if(fd!==null){const counts=Object.fromEntries(Object.entries(partial).filter(([key,value])=>key.startsWith('native_')&&typeof value==='number'));
      fs.writeSync(fd,JSON.stringify({event,at_unix:Date.now()/1000,helper_pid:process.pid,...counts})+'\n');fs.fsyncSync(fd);}
  }
  (async()=>{
    if(process.argv.length!==4||!IDS[partial.phase])throw new Error('Exact phase bundle/output arguments required');
    const root=process.env.E30_PROJECT,source=fs.readFileSync(process.argv[2]);
    const bundle=JSON.parse(source),output=process.argv[3];
    if(!root||bundle.schema_version!==3||bundle.epoch!==30||bundle.phase!==partial.phase||bundle.kind!==KIND
        ||bundle.vector_encoding!=='base64_float32le_c_order'||bundle.documents.length!==8
        ||bundle.metadata_policy!=='insert id and vector only; metadata absent')throw new Error('Wrong exact phase/source bundle');
    for(const [offset,document] of bundle.documents.entries()){
      if(document.document_id!==IDS[partial.phase][offset]||document.queries.length!==3
          ||document.queries.some((query,h)=>Object.keys(query).join(',')!=='id'
            ||query.id!==`original-contractnli:train:epoch30:${partial.phase}:${document.document_id}:${HYPOTHESES[h]}`))
        throw new Error('Fixed exact phase document/query identity order differs');
    }
    fd=fs.openSync(path.join(path.dirname(output),'native-progress.jsonl'),'wx',0o600);
    const binary=path.join(root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node');
    if(hash(fs.readFileSync(binary))!==BINARY_SHA)throw new Error('Original core binary hash changed');
    const core=require(path.join(root,'retrieval/node_modules/@ruvector/core'));
    partial.native_version_calls_attempted++;progress('CORE_VERSION_BEFORE');
    const version=core.version();partial.native_version_calls_completed++;
    Object.assign(partial,{package_version:require(path.join(root,'retrieval/node_modules/@ruvector/core/package.json')).version,
      platform_package_version:require(path.join(root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/package.json')).version,
      binary_version:version,native_binary_sha256:BINARY_SHA,helper_pid:process.pid,
      source_sha256:hash(fs.readFileSync(__filename)),bundle_sha256:hash(source),
      vector_receipt_method:'SHA256 exact1536 little-endian float32 bytes, source equality before stripping',
      metadata_receipt_method:'SHA256 UTF8 {"present":false}, no newline; metadata absent atinsert'});
    if(partial.package_version!=='0.1.33'||partial.platform_package_version!=='0.1.31'||version!=='2.3.0')
      throw new Error('Exact original wrapper/platform/core version changed');
    for(const [offset,item] of bundle.documents.entries()){
      const vectors=decode(item.vectors),queries=decode(item.query_vectors,3);
      const storage=path.join(process.cwd(),'document-'+offset);fs.mkdirSync(storage);
      const started=performance.now();partial.native_index_initializations_attempted++;progress('INDEX_BEFORE');
      const db=new core.VectorDb({dimensions:384,distanceMetric:core.JsDistanceMetric.Cosine,storagePath:path.join(storage,'ruvector.db')});
      partial.native_index_initializations_completed++;
      partial.native_len_calls_attempted++;progress('EMPTY_LEN_BEFORE');
      const empty=await db.len();partial.native_len_calls_completed++;
      if(empty!==0)throw new Error('Actual native index did not start empty');
      for(let j=0;j<vectors.length;j++){
        partial.native_insertions_attempted++;progress('INSERT_BEFORE');
        await db.insert({id:String(j),vector:vectors[j]});partial.native_insertions_completed++;
      }
      partial.native_len_calls_attempted++;progress('COMPLETE_LEN_BEFORE');
      const length=await db.len();partial.native_len_calls_completed++;
      if(length!==vectors.length)throw new Error('Actual native index incomplete');
      const row={document_id:item.document_id,initialized_vectors:length,initialization_ms:performance.now()-started,queries:[]};
      partial.documents.push(row);
      for(let queryIndex=0;queryIndex<3;queryIndex++){
        const query=item.queries[queryIndex],k=Math.min(40,vectors.length);
        partial.active_query={case_id:query.id,document_id:item.document_id,requested_k:k};
        partial.native_queries_attempted++;progress('QUERY_BEFORE');
        const t=performance.now(),hits=await db.search({vector:queries[queryIndex],k});
        const queryMs=performance.now()-t;partial.native_queries_completed++;
        partial.active_query.actual_raw_hits_unvalidated=hits;progress('QUERY_RETURNED');
        if(!Array.isArray(hits)||hits.length!==k)throw new Error('Actual native hit count differs');
        const ids=hits.map(hit=>Number(hit.id));
        if(new Set(ids).size!==k)throw new Error('Duplicate actual native source IDs');
        const rawHits=hits.map(hit=>{const out=compact(hit,vectors);partial.native_hit_source_validations++;return out;});
        row.queries.push({case_id:query.id,ids,raw_hits:rawHits,requested_k:k,query_ms:queryMs,
          native_order_used_without_replacement:true,
          score_semantics:'Actual native score field preserved without reinterpretation or reranking.'});
        delete partial.active_query;progress('QUERY_COMPLETED');
      }
    }
    partial.helper_resources=process.resourceUsage();progress('HELPER_COMPLETED');
    fs.writeFileSync(output,JSON.stringify(partial)+'\n',{flag:'wx'});fs.closeSync(fd);
  })().catch(error=>{
    partial.errors.push({type:error.name,message:String(error.message||error),stack:error.stack});
    try{progress('HELPER_FAILED');}catch(ignored){}
    try{fs.writeFileSync(process.argv[3]+'.failure.json',JSON.stringify(partial,(_key,value)=>
      typeof value==='number'&&!Number.isFinite(value)?{nonfinite_number:String(value)}:value)+'\n',{flag:'wx'});}catch(ignored){}
    console.error(error.stack||String(error));process.exitCode=2;
  });
}
