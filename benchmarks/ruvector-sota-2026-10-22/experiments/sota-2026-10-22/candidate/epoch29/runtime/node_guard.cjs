'use strict';
// Preload only: source-admitted candidate ANN helper and unchanged core package.
// Public API interposition is not an operating-system syscall sandbox.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const Module=require('node:module');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const events=[];
let fd=null,attempts=0,nativeAttempted=0,nativeCompleted=0;
function record(event,extra={}){
  const row={event,at_unix:Date.now()/1000,pid:process.pid,
    Node_network_operations_attempted:attempts,native_binary_loads_attempted:nativeAttempted,
    native_binary_loads_completed:nativeCompleted,...extra};
  events.push(row);
  if(fd!==null){fs.writeSync(fd,JSON.stringify(row)+'\n');fs.fsyncSync(fd);}
}
function refuse(event,args){
  attempts++;record('OFFLINE_FATAL_VIOLATION',{operation:event,address:String(args&&args[0]),stack:new Error().stack});
  process.exitCode=70;throw new Error('Persistent offline native policy violation: '+event);
}
for(const [name,methods] of Object.entries({'node:net':['connect','createConnection'],
  'node:http':['request','get'],'node:https':['request','get'],'node:dgram':['createSocket']})){
  const mod=require(name);for(const method of methods)mod[method]=(...args)=>refuse(name+'.'+method,args);
}
const dgram=require('node:dgram'),originalDgramSocket=dgram.Socket;
for(const method of Object.getOwnPropertyNames(originalDgramSocket.prototype))
  if(!['constructor','close','ref','unref'].includes(method)
      &&typeof Object.getOwnPropertyDescriptor(originalDgramSocket.prototype,method).value==='function')
    originalDgramSocket.prototype[method]=function(...args){return refuse('dgram.Socket.'+method,args);};
function deniedDgramSocket(...args){return refuse('dgram.Socket',args);}
deniedDgramSocket.prototype=originalDgramSocket.prototype;
originalDgramSocket.prototype.constructor=deniedDgramSocket;dgram.Socket=deniedDgramSocket;
for(const type of [require('node:net').Socket,require('node:net').Server])
  for(const method of ['connect','listen'])if(type.prototype[method])
    type.prototype[method]=function(...args){return refuse(type.name+'.'+method,args);};
function patchDns(target,label,walk=false){
  for(let current=target;current&&current!==Object.prototype;current=walk?Object.getPrototypeOf(current):null)
    for(const method of Object.getOwnPropertyNames(current))
      if((/^(lookup|resolve)/.test(method)||method==='reverse')&&typeof current[method]==='function')
        current[method]=(...args)=>refuse(label+'.'+method,args);
}
const dns=require('node:dns');patchDns(dns,'dns');patchDns(dns.promises,'dns.promises');
patchDns(dns.Resolver.prototype,'dns.Resolver',true);patchDns(dns.promises.Resolver.prototype,'dns.promises.Resolver',true);
// Exact stdin/stdout/stderr pipes are the required transport. Other Socket
// read/write paths have no legitimate role in this qualification.
for(const method of ['write','end','read','send','sendto','sendmsg','recv','recvfrom','recvmsg','accept']){
  const prototype=require('node:net').Socket.prototype,original=prototype[method];
  if(typeof original==='function')prototype[method]=function(...args){
    if(this===process.stdin||this===process.stdout||this===process.stderr)return original.apply(this,args);
    return refuse('Socket.'+method,args);
  };
}
globalThis.fetch=(...args)=>refuse('fetch',args);
function noSymlink(file){
  if(!path.isAbsolute(file)||path.normalize(file)!==file)throw new Error('Noncanonical absolute source path');
  let at=path.parse(file).root;
  for(const part of file.slice(at.length).split(path.sep)){
    at=path.join(at,part);
    if(fs.existsSync(at)&&fs.lstatSync(at).isSymbolicLink())throw new Error('Symlink component refused');
  }
}
function checked(root,relative){
  if(typeof relative!=='string'||!relative||path.isAbsolute(relative)||relative.includes('\\')
      ||relative.split('/').some(x=>!x||x==='.'||x==='..'))throw new Error('Unsafe pinned relative path');
  const file=path.join(root,relative);noSymlink(file);
  if(!fs.statSync(file).isFile())throw new Error('Nonregular source file');
  return file;
}
function admit(){
  const root=process.env.E29_PROJECT,out=process.env.E29_OUT,planPath=process.env.E29_PLAN;
  const expected=process.env.E29_PLAN_SHA,admissionPath=process.env.E29_ADMISSION;
  const study='experiments/sota-2026-10-22/epoch29';
  if(!root||!out||!planPath||!admissionPath)throw new Error('External source gate environment missing');
  for(const file of [root,out,planPath,admissionPath])noSymlink(file);
  if(fs.realpathSync(root)!==root||planPath!==path.join(root,study,'plan.json')
      ||!/^[0-9a-f]{64}$/.test(expected||'')||sha(planPath)!==expected
      ||out!==path.join(root,study,'runs/engineering')
      ||admissionPath!==path.join(root,study,'NATIVE_ADMISSION.json'))
    throw new Error('Exact external source plan gate required');
  const plan=JSON.parse(fs.readFileSync(planPath)),admission=JSON.parse(fs.readFileSync(admissionPath));
  const ownerPath=path.join(root,'../owner.json');noSymlink(path.resolve(ownerPath));
  const owner=JSON.parse(fs.readFileSync(ownerPath));
  const status=Object.fromEntries(fs.readFileSync('/proc/self/status','utf8').split('\n')
    .filter(line=>/^(NoNewPrivs|Seccomp|Seccomp_filters|Cpus_allowed_list):/.test(line))
    .map(line=>[line.split(':')[0],line.slice(line.indexOf(':')+1).trim()]));
  if(process.platform!=='linux'||process.arch!=='x64'||status.NoNewPrivs!=='1'
      ||status.Seccomp!=='2'||!['0-1','0,1'].includes(status.Cpus_allowed_list))
    throw new Error('Whole-worker inherited NNP/seccomp/CPU0,1 required before native import');
  const proc=fs.readFileSync('/proc/80007/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
  const roles=plan.data_roles;
  const emptyRoles=roles&&Object.keys(roles).sort().join(',')==='calibration,confirmation,dev,train'
    &&Object.values(roles).every(x=>Array.isArray(x)&&x.length===0);
  if(admission.epoch!==29||admission.kind!=='REAL_NATIVE_DOCUMENT_IDENTITY_QUALIFICATION'
      ||admission.scope!=='benchmarks/ruvector-sota-2026-10-22/'
      ||admission.verified_actual_remote_readback!==true||admission.plan_sha256!==expected
      ||admission.source_freeze_sha256!==plan.source_freeze_sha256
      ||!/^[0-9a-f]{40}$/.test(admission.published_source_commit||'')
      ||admission.owner_pid!==80007||admission.owner_startticks!==17161777
      ||plan.epoch!==29||plan.kind!=='REAL_NATIVE_DOCUMENT_IDENTITY_QUALIFICATION'
      ||plan.actual_project!==root||plan.source_checkpoint!=='07a2cbe78fdee78a8c9bca2aeb64bc9746481ba0'
      ||!emptyRoles
      ||owner.pid!==80007||owner.startticks!==17161777||owner.lock_inode!==13626
      ||owner.expires_unix!==1792858715.860032||fs.existsSync(path.join(root,'../release.request'))
      ||Date.now()/1000>=owner.expires_unix||['Z','X'].includes(proc[0])||Number(proc[19])!==17161777)
    throw new Error('Exact actual-source and unexpired guardian admission required');
  const seen=new Set();
  for(const pin of plan.pins){
    if(seen.has(pin.path))throw new Error('Duplicate source pin');seen.add(pin.path);
    const file=checked(root,pin.path);
    if(fs.statSync(file).size!==pin.bytes||sha(file)!==pin.sha256)throw new Error('Frozen source changed: '+pin.path);
  }
  const runtimePath=checked(root,plan.runtime_assets_lock_path);
  if(!seen.has(plan.runtime_assets_lock_path)||sha(runtimePath)!==plan.runtime_assets_lock_sha256)
    throw new Error('Exact runtime lock not source pinned');
  const runtime=JSON.parse(fs.readFileSync(runtimePath));
  if(!Array.isArray(runtime.assets)||runtime.assets.length!==10)throw new Error('Exact10 core/BGE assets required');
  for(const row of runtime.assets){const file=checked(root,row.path);
    if(fs.statSync(file).size!==row.bytes||sha(file)!==row.sha256)throw new Error('Original runtime changed: '+row.path);}
  const worker=checked(root,plan.native_worker_path);
  if(!seen.has(plan.native_worker_path)||process.argv.length!==4||process.argv[1]!==worker
      ||process.argv[2]!==path.join(out,'native-bundle.json')||process.argv[3]!==path.join(out,'native-result.json'))
    throw new Error('Exact frozen ANN worker and full-vector argument paths required');
  noSymlink(process.argv[2]);noSymlink(process.argv[3]);
  if(!fs.statSync(process.argv[2]).isFile()||fs.existsSync(process.argv[3]))
    throw new Error('Missing full vector input or existing native output');
  fd=fs.openSync(path.join(out,'node-progress.jsonl'),'wx',0o600);
  record('NODE_SOURCE_RUNTIME_ADMISSION_BEFORE_NATIVE_IMPORT',{node_version:process.version,
    CPU_guard_actual_proc_status:status,worker_path:worker,worker_sha256:sha(worker),
    full_vector_bundle:{path:path.relative(root,process.argv[2]),bytes:fs.statSync(process.argv[2]).size,sha256:sha(process.argv[2])},
    process_status:fs.readFileSync('/proc/self/status','utf8').split('\n').filter(line=>/^(Threads|Cpus_allowed_list|VmRSS|VmHWM|NoNewPrivs|Seccomp|Seccomp_filters):/.test(line))});
  const binary=path.join(root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node');
  const original=Module._load;
  Module._load=function(request,parent,isMain){
    const resolved=Module._resolveFilename(request,parent,isMain);
    if(typeof resolved==='string'&&resolved.endsWith('.node')){
      if(resolved!==binary||sha(resolved)!=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
          ||nativeAttempted!==0)throw new Error('Unexpected/repeated native addon load');
      nativeAttempted++;record('NATIVE_BINARY_LOAD_BEFORE',{path:resolved,sha256:sha(resolved)});
      const value=original.apply(this,arguments);
      nativeCompleted++;record('NATIVE_BINARY_LOAD_AFTER',{path:resolved});return value;
    }
    return original.apply(this,arguments);
  };
}
module.exports={diagnostics:()=>({attempts,nativeAttempted,nativeCompleted,events:events.slice()})};
if(process.env.E29_GUARD_SYNTHETIC==='1'){
  if(process.argv[1]!==__filename)throw new Error('Synthetic guard allowed only in isolated -e preflight');
  const original=Module._load;
  Module._load=function(request,parent,isMain){
    const resolved=Module._resolveFilename(request,parent,isMain);
    if(typeof resolved==='string'&&resolved.endsWith('.node'))throw new Error('Synthetic preflight forbids all native addon loads');
    return original.apply(this,arguments);
  };
}else admit();
