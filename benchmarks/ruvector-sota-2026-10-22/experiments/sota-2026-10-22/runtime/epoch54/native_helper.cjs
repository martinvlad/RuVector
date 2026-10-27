'use strict';
// Original native VectorDb API. This helper receives only exact F32 embeddings and IDs.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {performance}=require('node:perf_hooks');
const KIND='REAL_NATIVE_SOURCE_FRAGMENT_CAPACITY_QUALIFICATION';
const BINARY_SHA='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e';
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const need=(x,c)=>{if(!x)throw Error(c);};

function decode(block){
 need(block&&block.encoding==='base64'&&block.dtype==='float32le'&&Array.isArray(block.shape)
  &&block.shape.length===2&&Number.isInteger(block.shape[0])&&block.shape[0]>=1
  &&block.shape[0]<=1024&&block.shape[1]===384&&block.bytes===block.shape[0]*1536
  &&typeof block.data_base64==='string','BUNDLE_F32_SHAPE');
 const b=Buffer.from(block.data_base64,'base64');
 need(b.length===block.bytes&&b.toString('base64')===block.data_base64&&hash(b)===block.sha256,
  'BUNDLE_F32_IDENTITY');
 const vectors=[];
 for(let row=0;row<block.shape[0];row++){
  const v=new Float32Array(384);let norm=0;
  for(let col=0;col<384;col++){v[col]=b.readFloatLE(row*1536+col*4);need(Number.isFinite(v[col]),'F32_FINITE');norm+=v[col]*v[col];}
  need(Math.abs(Math.sqrt(norm)-1)<=1e-5,'F32_NORMALIZED');vectors.push(v);
 }
 return vectors;
}

function vectorBytes(v){
 need(v&&Object.keys(v).length===384&&Object.keys(v).every((k,i)=>k===String(i)),
  'NATIVE_RETURNED_VECTOR_SHAPE');
 const b=Buffer.alloc(1536);
 for(let i=0;i<384;i++){need(typeof v[i]==='number'&&Number.isFinite(v[i])
  &&Object.is(Math.fround(v[i]),v[i]),'NATIVE_RETURNED_F32');b.writeFloatLE(v[i],i*4);}
 return b;
}

function compact(hit,vectors){
 need(hit&&typeof hit.id==='string'&&/^\d+$/.test(hit.id)&&String(Number(hit.id))===hit.id,
  'NATIVE_DECIMAL_SOURCE_ID');
 const id=Number(hit.id);need(id>=0&&id<vectors.length,'NATIVE_SOURCE_ID_BOUNDS');
 const actual=vectorBytes(hit.vector),source=vectorBytes(vectors[id]);
 need(actual.equals(source),'NATIVE_SOURCE_VECTOR_BITS');
 need(!Object.prototype.hasOwnProperty.call(hit,'metadata'),'NATIVE_METADATA_ABSENT');
 need(typeof hit.score==='number'&&Number.isFinite(hit.score),'NATIVE_SCORE_FINITE');
 const out={};
 for(const k of Object.keys(hit)){if(k!=='vector'){need(typeof hit[k]!=='number'||Number.isFinite(hit[k]),'NATIVE_NONFINITE_FIELD');out[k]=hit[k];}}
 out.vector_receipt={source_vector_index:id,dimensions:384,dtype:'float32le',sha256:hash(actual),
  source_equal_before_stripping:true};out.metadata_receipt={present:false};return out;
}

module.exports={decode,vectorBytes,compact};
if(require.main===module){
 const result={schema_version:1,epoch:54,kind:KIND,documents:[],errors:[],
  native_index_initializations_attempted:0,native_index_initializations_completed:0,
  native_insertions_attempted:0,native_insertions_completed:0,native_queries_attempted:0,
  native_queries_completed:0,native_len_calls_attempted:0,native_len_calls_completed:0,
  native_hit_source_validations:0,native_binary_loads_attempted:0,native_binary_loads_completed:0,
  native_version_calls_attempted:0,native_version_calls_completed:0,Node_network_operations_attempted:0};
 let output,progressFD;
 function progress(event){result.stage=event;if(progressFD!==undefined){fs.writeSync(progressFD,
  JSON.stringify({event,monotonic_milliseconds:performance.now(),counters:Object.fromEntries(
   Object.entries(result).filter(([k,v])=>typeof v==='number'&&(k.startsWith('native_')||k==='Node_network_operations_attempted')))})+'\n');fs.fsyncSync(progressFD);}}
 (async()=>{
  need(process.argv.length===5,'NATIVE_EXACT_ARGUMENTS');
  const [configPath,bundlePath,target]=process.argv.slice(2);output=target;
  const config=JSON.parse(fs.readFileSync(configPath)),source=fs.readFileSync(bundlePath),bundle=JSON.parse(source);
  need(source.length<=67108864&&bundle.schema_version===1&&bundle.epoch===54&&bundle.kind===KIND
   &&bundle.phase==='engineering','NATIVE_EXACT_BUNDLE');
  const role=config.phase_roles[bundle.phase];need(role&&Array.isArray(bundle.documents)
   &&bundle.documents.length===4&&role.document_ids.length===4&&role.case_ids.length===12,
   'NATIVE_PHASE_IDENTITIES');result.phase=bundle.phase;
  let totalVectors=0;
  for(let i=0;i<4;i++){const d=bundle.documents[i];need(d.document_id===role.document_ids[i]
   &&Array.isArray(d.queries)&&d.queries.length===3&&d.queries.every((q,j)=>
    Object.keys(q).length===1&&q.case_id===role.case_ids[i*3+j]),'NATIVE_QUERY_IDENTITIES');
   totalVectors+=decode(d.vectors).length;need(decode(d.query_vectors).length===3,'NATIVE_THREE_QUERIES');}
  need(totalVectors<=4096,'NATIVE_PHASE_FRAGMENT_CAP_4096');
  progressFD=fs.openSync(path.join(path.dirname(output),'native-progress.jsonl'),'wx',0o600);
  const deny=()=>{result.Node_network_operations_attempted++;progress('FORBIDDEN_NETWORK');throw Error('NODE_NETWORK_FORBIDDEN');};
  const net=require('node:net'),http=require('node:http'),https=require('node:https'),dns=require('node:dns');
  net.Socket.prototype.connect=deny;net.connect=deny;net.createConnection=deny;
  http.request=deny;http.get=deny;https.request=deny;https.get=deny;globalThis.fetch=deny;
  for(const k of ['lookup','resolve','resolve4','resolve6','reverse'])dns[k]=deny;
  const binary=path.join(config.native_root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node');
  need(config.native_binary.sha256===BINARY_SHA&&config.native_binary.path===binary,
   'FROZEN_NATIVE_BINARY_PATH');need(hash(fs.readFileSync(binary))===BINARY_SHA,'FROZEN_NATIVE_BINARY_HASH');
  const originalDlopen=process.dlopen;
  process.dlopen=function(module,filename,...rest){
   need(path.resolve(filename)===binary,'ONLY_FROZEN_NATIVE_DLOPEN');
   result.native_binary_loads_attempted++;progress('NATIVE_LOAD_BEFORE');
   const value=originalDlopen.call(this,module,filename,...rest);
   result.native_binary_loads_completed++;progress('NATIVE_LOAD_COMPLETE');return value;
  };
  const core=require(path.join(config.native_root,'retrieval/node_modules/@ruvector/core'));
  need(result.native_binary_loads_attempted===1&&result.native_binary_loads_completed===1,
   'ACTUAL_SINGLE_NATIVE_BINARY_LOAD');result.native_version_calls_attempted++;progress('NATIVE_VERSION_BEFORE');
  const version=core.version();result.native_version_calls_completed++;
  need(version==='2.3.0'&&require(path.join(config.native_root,'retrieval/node_modules/@ruvector/core/package.json')).version==='0.1.33'
   &&require(path.join(config.native_root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/package.json')).version==='0.1.31',
   'EXACT_NATIVE_VERSION');
  Object.assign(result,{binary_version:version,package_version:'0.1.33',platform_package_version:'0.1.31',
   native_binary_sha256:BINARY_SHA,bundle_sha256:hash(source),helper_source_sha256:hash(fs.readFileSync(__filename)),
   helper_pid:process.pid,plan_sha256:bundle.plan_sha256});
  for(let offset=0;offset<bundle.documents.length;offset++){
   const d=bundle.documents[offset],vectors=decode(d.vectors),queries=decode(d.query_vectors);
   const folder=path.join(path.dirname(output),'document-'+offset);fs.mkdirSync(folder);
   const t0=performance.now();result.native_index_initializations_attempted++;progress('INDEX_BEFORE');
   const db=new core.VectorDb({dimensions:384,distanceMetric:core.JsDistanceMetric.Cosine,
    storagePath:path.join(folder,'ruvector.db')});result.native_index_initializations_completed++;
   result.native_len_calls_attempted++;need(await db.len()===0,'NATIVE_INDEX_NOT_EMPTY');result.native_len_calls_completed++;
   for(let j=0;j<vectors.length;j++){result.native_insertions_attempted++;progress('INSERT_BEFORE');
    await db.insert({id:String(j),vector:vectors[j]});result.native_insertions_completed++;}
   result.native_len_calls_attempted++;need(await db.len()===vectors.length,'NATIVE_INDEX_INCOMPLETE');result.native_len_calls_completed++;
   const row={document_id:d.document_id,initialized_vectors:vectors.length,initialization_seconds:(performance.now()-t0)/1000,queries:[]};result.documents.push(row);
   for(let j=0;j<3;j++){
    result.native_queries_attempted++;progress('QUERY_BEFORE');const t=performance.now();
    const hits=await db.search({vector:queries[j],k:vectors.length});result.native_queries_completed++;
    need(Array.isArray(hits)&&hits.length===vectors.length,'NATIVE_ALL_SOURCE_HITS');
    const ids=hits.map(h=>Number(h.id));need(new Set(ids).size===vectors.length,'NATIVE_UNIQUE_HITS');
    const rawHits=hits.map(h=>{const out=compact(h,vectors);result.native_hit_source_validations++;return out;});
    row.queries.push({case_id:d.queries[j].case_id,ids,raw_hits:rawHits,requested_k:vectors.length,
     elapsed_seconds:(performance.now()-t)/1000,native_order_used_without_reranking:true});progress('QUERY_COMPLETE');
   }
  }
  result.resources=process.resourceUsage();progress('COMPLETE');
  fs.writeFileSync(output,JSON.stringify(result)+'\n',{flag:'wx',mode:0o600});fs.closeSync(progressFD);
 })().catch(error=>{result.errors.push({type:error.name,code:/^[A-Z0-9_]{1,120}$/.test(error.message)?error.message:'NATIVE_HELPER_FAILED'});
  try{progress('FAILED');}catch(ignored){}
  try{fs.writeFileSync(output+'.failure.json',JSON.stringify(result)+'\n',{flag:'wx',mode:0o600});}catch(ignored){}
  console.error(error.stack||String(error));process.exitCode=2;});
}
