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
  if(!path.isAbsolute(file)||path.normalize(file)!==file)throw new Error('Noncanonical absolute path');
  let at=path.parse(file).root;
  for(const part of file.slice(at.length).split(path.sep)){
    at=path.join(at,part);
    if(fs.existsSync(at)&&fs.lstatSync(at).isSymbolicLink())throw new Error('Symlink component refused');
  }
}
function checked(root,relative){
  if(typeof relative!=='string'||!relative||path.isAbsolute(relative)||relative.includes('\\')
      ||relative.split('/').some(x=>!x||x==='.'||x==='..'))throw new Error('Unsafe relative path');
  const file=path.join(root,relative);noSymlink(file);
  if(!fs.statSync(file).isFile())throw new Error('Nonregular source');return file;
}
function sameRef(a,b){return a&&b&&Object.keys(a).sort().join(',')==='bytes,path,sha256'
  &&Object.keys(b).sort().join(',')==='bytes,path,sha256'&&a.path===b.path&&a.bytes===b.bytes&&a.sha256===b.sha256;}
function verifyRef(root,row,defer=false){
  if(!row||!Number.isSafeInteger(row.bytes)||row.bytes<0||!/^[0-9a-f]{64}$/.test(row.sha256||''))throw new Error('Invalid byte reference');
  const file=checked(root,row.path);
  if(fs.statSync(file).size!==row.bytes||(!defer&&sha(file)!==row.sha256))throw new Error('Changed frozen bytes: '+row.path);
  return file;
}
function admit(){
  const root=process.env.E34_PROJECT,out=process.env.E34_OUT,planPath=process.env.E34_PLAN;
  const expected=process.env.E34_PLAN_SHA,admissionPath=process.env.E34_ADMISSION,role=process.env.E34_ROLE;
  const study='experiments/sota-2026-10-22/epoch34',kind='REAL_NATIVE_LEXICAL_ANCHOR_NATIVE_COMPLEMENT_NLI_DIAGNOSTIC';
  const scope='/tmp/ruvector-sota-2026-10-22/epoch34-047dbc740dc2';
  if(!root||!out||!planPath||!admissionPath||!['engineering','dev'].includes(role))throw new Error('Exact phase/source environment missing');
  for(const file of [root,out,planPath,admissionPath])noSymlink(file);
  if(fs.realpathSync(root)!==root||planPath!==path.join(root,study,'plan.json')||!/^[0-9a-f]{64}$/.test(expected||'')
      ||sha(planPath)!==expected||out!==path.join(root,study,'runs/dev')||admissionPath!==path.join(root,study,'SOURCE_ADMISSION.json'))throw new Error('Exact outside source admission required');
  const plan=JSON.parse(fs.readFileSync(planPath)),value=JSON.parse(fs.readFileSync(admissionPath));
  if(value.epoch!==34||value.kind!==kind||value.phase!=='dev'||value.scope!=='benchmarks/ruvector-sota-2026-10-22/'
      ||value.verified_actual_remote_readback!==true||value.plan_sha256!==expected||value.source_freeze_sha256!==plan.source_freeze_sha256
      ||!/^[0-9a-f]{40}$/.test(value.published_source_commit||'')||value.owner_pid!==100799||value.owner_startticks!==22293151
      ||value.kernel_boot_id!=='4632fb06-b0ef-4df5-b72b-0e875bbad810'||value.pid_namespace_inode!==4026532200
      ||value.owner_lock_fd!==3||value.owner_lock_device!==33||value.owner_lock_inode!==13626||value.owner_generation!==1
      ||!sameRef(value.pretrained_model_source,plan.pretrained_model_source)||value.model_assets_lock_sha256!==plan.model_assets_lock_sha256)throw new Error('Actual SOURCE/head/asset admission missing');
  const sourceFile=verifyRef(root,plan.pretrained_model_source),source=JSON.parse(fs.readFileSync(sourceFile));
  if(source.epoch!==34||source.kind!==kind||source.repository!=='MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
      ||source.revision!=='b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7'||source.weights_file!=='model.safetensors'
      ||source.weights_bytes!==870182606||source.weights_sha256!=='c03cd208bf920b4fbbb182a0535859a566e8acc3477d2b536bf87b769978524b'
      ||source.source_parameter_dtype!=='F16'||source.compute_dtype!=='F32'||source.training_lineage_complete!==false||source.official_eligibility!=='HOLD')throw new Error('Different pretrained source or overstated eligibility');
  const roles=plan.data_roles;
  if(plan.epoch!==34||plan.kind!==kind||plan.source_checkpoint!=='047dbc740dc2d4fdbdbad90ac167ebc64b31a49c'
      ||plan.actual_project!==root||plan.guardian_scope!==scope||plan.model_directory!=='/workspace/ruvector-e34-reader-assets/moritz-b3546ea6'
      ||!roles||Object.keys(roles).sort().join(',')!=='calibration,confirmation,dev,train'
      ||JSON.stringify(roles.train)!=='[]'||JSON.stringify(roles.dev)!=='[434,367,247,377,220,457,169,449]'
      ||JSON.stringify(roles.calibration)!=='[]'||JSON.stringify(roles.confirmation)!=='[]')throw new Error('Different frozen source/current roles');
  const owner=JSON.parse(fs.readFileSync(path.join(scope,'owner.json'))),boot=fs.readFileSync('/proc/sys/kernel/random/boot_id','utf8').trim();
  const lockFD='/proc/100799/fd/3',lockInfo=fs.statSync(lockFD),lock='/tmp/ruvector-sota-2026-10-22/exclusive.work.lock';
  const proc=fs.readFileSync('/proc/100799/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
  const held=fs.readFileSync('/proc/locks','utf8').split('\n').some(line=>{
    const w=line.trim().split(/\s+/);if(w.slice(1,5).join(',')!=='FLOCK,ADVISORY,WRITE,100799')return false;
    const a=(w[5]||'').split(':');return parseInt(a[0],16)===0&&parseInt(a[1],16)===33&&Number(a[2])===13626;});
  if(boot!=='4632fb06-b0ef-4df5-b72b-0e875bbad810'||fs.statSync('/proc/self/ns/pid').ino!==4026532200
      ||fs.statSync('/proc/100799/ns/pid').ino!==4026532200||lockInfo.dev!==33||lockInfo.ino!==13626||fs.readlinkSync(lockFD)!==lock||!held
      ||owner.pid!==100799||owner.startticks!==22293151||owner.lock_inode!==13626||owner.generation!==1||owner.kernel_boot_id!==boot
      ||owner.PID_namespace!=='pid:[4026532200]'||owner.expires_unix!==1792910029.5943027||Date.now()/1000>=owner.expires_unix
      ||fs.existsSync(path.join(scope,'release.request'))||['Z','X'].includes(proc[0])||Number(proc[19])!==22293151)throw new Error('Actual guardian/boot/FD/FLOCK authority changed');
  const status=Object.fromEntries(fs.readFileSync('/proc/self/status','utf8').split('\n').filter(l=>/^(NoNewPrivs|Seccomp|Seccomp_filters|Cpus_allowed_list):/.test(l)).map(l=>[l.split(':')[0],l.slice(l.indexOf(':')+1).trim()]));
  if(process.platform!=='linux'||process.arch!=='x64'||status.NoNewPrivs!=='1'||status.Seccomp!=='2'||!['0-1','0,1'].includes(status.Cpus_allowed_list))throw new Error('Inherited whole-worker CPU guard required');
  const seen=new Set();for(const pin of plan.pins){if(seen.has(pin.path))throw new Error('Duplicate source pin');seen.add(pin.path);verifyRef(root,pin,role==='engineering'&&pin.path===plan.dev_inputs_path);}
  if(role==='dev'){
    const checkpoint=JSON.parse(fs.readFileSync(path.join(out,'raw.partial.json')));
    if(!checkpoint.engineering_gate||checkpoint.engineering_gate.passed!==true||checkpoint.counters.ENGINEERING_forward_calls_completed!==24)throw new Error('DEV native work requires sealed engineering24 pass');
  }
  const runtimeFile=checked(root,plan.runtime_assets_lock_path);
  if(!seen.has(plan.runtime_assets_lock_path)||sha(runtimeFile)!==plan.runtime_assets_lock_sha256)throw new Error('Missing runtime lock');
  const runtime=JSON.parse(fs.readFileSync(runtimeFile));if(!Array.isArray(runtime.assets)||runtime.assets.length!==10)throw new Error('Exact10 native/BGE assets required');
  for(const row of runtime.assets)verifyRef(root,row);
  const worker=checked(root,plan.native_worker_path);
  if(plan.native_worker_path!=='experiments/sota-2026-10-22/candidate/epoch34/native_helper.cjs'||!seen.has(plan.native_worker_path)
      ||process.argv.length!==4||process.argv[1]!==worker||process.argv[2]!==path.join(out,role+'-native-bundle.json')||process.argv[3]!==path.join(out,role+'-native-result.json'))throw new Error('Exact role helper arguments required');
  noSymlink(process.argv[2]);noSymlink(process.argv[3]);if(!fs.statSync(process.argv[2]).isFile()||fs.existsSync(process.argv[3]))throw new Error('Reused/missing native bundle or result');
  const parent=fs.readFileSync('/proc/'+process.ppid+'/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
  const attempt=JSON.parse(fs.readFileSync(path.join(out,'attempt.json')));
  if(attempt.pid!==process.ppid||attempt.startticks!==Number(parent[19])||attempt.pgid!==process.ppid||attempt.sid!==process.ppid)throw new Error('Native parent worker identity mismatch');
  fd=fs.openSync(path.join(out,role+'-node-progress.jsonl'),'wx',0o600);
  record('NODE_SOURCE_RUNTIME_ADMISSION_BEFORE_NATIVE_IMPORT',{phase:'dev',role,node_version:process.version,kernel_boot_id:boot,pid_namespace_inode:4026532200,guardian_lock_fd:3,
    CPU_guard_actual_proc_status:status,worker_path:worker,worker_sha256:sha(worker),
    full_vector_bundle:{path:path.relative(root,process.argv[2]),bytes:fs.statSync(process.argv[2]).size,sha256:sha(process.argv[2])}});
  const binary=path.join(root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node'),original=Module._load;
  Module._load=function(request,parent,isMain){
    const resolved=Module._resolveFilename(request,parent,isMain);
    if(typeof resolved==='string'&&resolved.endsWith('.node')){
      if(resolved!==binary||sha(resolved)!=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'||nativeAttempted!==0)throw new Error('Unexpected/repeated native addon');
      nativeAttempted++;record('NATIVE_BINARY_LOAD_BEFORE',{phase:'dev',role,path:resolved,sha256:sha(resolved)});
      const result=original.apply(this,arguments);nativeCompleted++;record('NATIVE_BINARY_LOAD_AFTER',{phase:'dev',role,path:resolved});return result;
    }return original.apply(this,arguments);
  };
}
module.exports={diagnostics:()=>({attempts,nativeAttempted,nativeCompleted,events:events.slice()})};
if(process.env.E34_GUARD_SYNTHETIC==='1'){
  if(process.argv[1]!==__filename)throw new Error('Synthetic guard only allowed in isolated -e preflight');
  const original=Module._load;
  Module._load=function(request,parent,isMain){
    const resolved=Module._resolveFilename(request,parent,isMain);
    if(typeof resolved==='string'&&resolved.endsWith('.node'))throw new Error('Synthetic mode forbids all native addon loads');
    return original.apply(this,arguments);
  };
}else admit();
