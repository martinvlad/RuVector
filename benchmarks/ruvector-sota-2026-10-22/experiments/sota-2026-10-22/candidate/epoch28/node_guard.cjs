'use strict';
// Preload only: original native-worker, baseline-server and package stay byte-exact.
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
function admit(){
  const root=process.env.E28_PROJECT,out=process.env.E28_OUT,planPath=process.env.E28_PLAN;
  const expected=process.env.E28_PLAN_SHA,admissionPath=process.env.E28_ADMISSION;
  if(!root||fs.realpathSync(root)!==root||planPath!==path.join(root,'experiments/sota-2026-10-22/epoch28/plan.json')
      ||sha(planPath)!==expected||out!==path.join(root,'experiments/sota-2026-10-22/epoch28/runs/engineering'))
    throw new Error('Exact external source plan gate required');
  const plan=JSON.parse(fs.readFileSync(planPath)),admission=JSON.parse(fs.readFileSync(admissionPath));
  const owner=JSON.parse(fs.readFileSync(path.join(root,'../owner.json')));
  const actualStatus=Object.fromEntries(fs.readFileSync('/proc/self/status','utf8').split('\n')
    .filter(line=>/^(NoNewPrivs|Seccomp|Seccomp_filters|Cpus_allowed_list):/.test(line))
    .map(line=>[line.split(':')[0],line.slice(line.indexOf(':')+1).trim()]));
  if(process.platform!=='linux'||process.arch!=='x64'||actualStatus.NoNewPrivs!=='1'
      ||actualStatus.Seccomp!=='2'||!['0-1','0,1'].includes(actualStatus.Cpus_allowed_list))
    throw new Error('Before-native inherited seccomp/NNP and CPU0,1 enforcement required');
  const proc=fs.readFileSync('/proc/77846/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
  if(admissionPath!==path.join(root,'experiments/sota-2026-10-22/epoch28/NATIVE_ADMISSION.json')
      ||admission.epoch!==28||admission.kind!=='REAL_ENGINEERING_FULL104_QUALIFICATION'
      ||admission.scope!=='benchmarks/ruvector-sota-2026-10-22/'
      ||admission.verified_actual_remote_readback!==true||admission.plan_sha256!==expected
      ||admission.source_freeze_sha256!==plan.source_freeze_sha256
      ||admission.owner_pid!==77846||admission.owner_startticks!==16105893
      ||plan.epoch!==28||plan.kind!=='REAL_ENGINEERING_FULL104_QUALIFICATION'||plan.actual_project!==root
      ||plan.source_checkpoint!=='585c476cec6011b1db9c79147e3b0ff80124a6a3'
      ||owner.pid!==77846||owner.startticks!==16105893||owner.lock_inode!==13626
      ||fs.existsSync(path.join(root,'../release.request'))||Date.now()/1000>=owner.expires_unix
      ||['Z','X'].includes(proc[0])||Number(proc[19])!==16105893)
    throw new Error('Actual remote source and exact unexpired guardian admission required');
  for(const pin of plan.pins){
    const file=path.join(root,pin.path);
    if(fs.realpathSync(file)!==file||fs.statSync(file).size!==pin.bytes||sha(file)!==pin.sha256)
      throw new Error('Frozen exact source changed: '+pin.path);
  }
  const runtime=JSON.parse(fs.readFileSync(path.join(root,plan.runtime_assets_lock_path)));
  for(const row of runtime.files){const file=path.join(root,row.path);
    if(fs.realpathSync(file)!==file||fs.statSync(file).size!==row.bytes||sha(file)!==row.sha256)
      throw new Error('Original runtime identity changed: '+row.path);}
  fd=fs.openSync(path.join(out,'node-progress.jsonl'),'wx',0o600);
  record('NODE_SOURCE_RUNTIME_ADMISSION_BEFORE_NATIVE_IMPORT',{node_version:process.version,
    CPU_guard_actual_proc_status:actualStatus,
    process_status:fs.readFileSync('/proc/self/status','utf8').split('\n').filter(line=>/^(Threads|Cpus_allowed_list|VmRSS|VmHWM|NoNewPrivs|Seccomp|Seccomp_filters):/.test(line))});
  const binary=path.join(root,'node_modules/@ruvector/typesafe/native/linux-x64-gnu/typesafe.linux-x64-gnu.node');
  const original=Module._load;
  Module._load=function(request,parent,isMain){
    const resolved=Module._resolveFilename(request,parent,isMain);
    if(typeof resolved==='string'&&resolved.endsWith('.node')){
      if(resolved!==binary||sha(resolved)!=='e4db4b945a91b5cb8937765236e180763e8a3f4866b791e0f71a98d0018c289d'
          ||nativeAttempted!==0)throw new Error('Unexpected or repeated native addon load');
      nativeAttempted++;record('NATIVE_BINARY_LOAD_BEFORE',{path:resolved,sha256:sha(resolved)});
      const value=original.apply(this,arguments);
      nativeCompleted++;record('NATIVE_BINARY_LOAD_AFTER',{path:resolved});
      return value;
    }
    return original.apply(this,arguments);
  };
}
module.exports={diagnostics:()=>({attempts,nativeAttempted,nativeCompleted,events:events.slice()})};
if(process.env.E28_GUARD_SYNTHETIC==='1'){
  if(process.argv[1]&&process.argv[1].endsWith('native-worker.cjs'))
    throw new Error('Synthetic mode cannot bypass admission for the original native worker');
}else admit();
