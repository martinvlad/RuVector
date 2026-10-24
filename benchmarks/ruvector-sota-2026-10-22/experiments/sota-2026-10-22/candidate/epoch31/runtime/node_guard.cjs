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
function sourceAdmission(root,study,plan,expected){
  const file=path.join(root,study,'SOURCE_ADMISSION.json');noSymlink(file);
  const value=JSON.parse(fs.readFileSync(file));
  if(value.epoch!==31||value.kind!=='REAL_NATIVE_ARCHIVED_LEGAL_ADAPTATION_DIAGNOSTIC'
      ||value.scope!=='benchmarks/ruvector-sota-2026-10-22/'||value.verified_actual_remote_readback!==true
      ||value.plan_sha256!==expected||value.source_freeze_sha256!==plan.source_freeze_sha256
      ||!/^[0-9a-f]{40}$/.test(value.published_source_commit||'')
      ||value.phase!=='dev'||value.owner_pid!==87763||value.owner_startticks!==19114443
      ||value.kernel_boot_id!=='4632fb06-b0ef-4df5-b72b-0e875bbad810'||value.pid_namespace_inode!==4026532200
      ||value.owner_lock_fd!==3||value.owner_lock_device!==33||value.owner_lock_inode!==13626||value.owner_generation!==1)
    throw new Error('Actual SOURCE readback required');
  return value;
}
function archiveGate(root,study,plan,value){
  const file=verifyRef(root,value.archived_model_seal);
  if(file!==path.join(root,study,'ARCHIVED_MODEL_SEAL.json')||!sameRef(value.archived_model_seal,plan.archived_model_seal))
    throw new Error('Wrong current archived-model seal');
  const seal=JSON.parse(fs.readFileSync(file));
  const keys=['schema_version','epoch','kind','status','source_checkpoint','parameter_artifact','train_raw','train_execution','independent_training_report','original_source_plan','original_source_freeze','historical_training_epoch','historical_training_document_ids','data_roles','hypotheses'].sort().join(',');
  if(Object.keys(seal).sort().join(',')!==keys||seal.schema_version!==1||seal.epoch!==31
      ||seal.kind!=='REAL_NATIVE_ARCHIVED_LEGAL_ADAPTATION_DIAGNOSTIC'||seal.status!=='ARCHIVED_TRAINED_PARAMETER_ARTIFACT_SEALED'
      ||seal.source_checkpoint!=='b27d0c39ed3102cd16ba616b1225b7684b76851b'||seal.historical_training_epoch!==30
      ||JSON.stringify(seal.historical_training_document_ids)!=='[237,120,187,422,464,207,294,250]'
      ||JSON.stringify(seal.hypotheses)!=='["nda-17","nda-7","nda-3"]'
      ||!seal.data_roles||JSON.stringify(seal.data_roles.train)!=='[]'
      ||JSON.stringify(seal.data_roles.dev)!=='[145,597,191,620,254,160,384,571]'
      ||!Array.isArray(seal.data_roles.confirmation)||seal.data_roles.confirmation.length
      ||!Array.isArray(seal.data_roles.calibration)||seal.data_roles.calibration.length
      ||!sameRef(value.parameter_artifact,seal.parameter_artifact))throw new Error('Wrong fixed archived lineage/currentDEV');
  const old='experiments/sota-2026-10-22/epoch30';
  const exact={parameter_artifact:path.join(root,old,'runs/train/trained-parameters.public.json'),
    train_raw:path.join(root,old,'runs/train/raw.json'),train_execution:path.join(root,old,'runs/train/execution.json'),
    original_source_plan:path.join(root,old,'plan.json'),original_source_freeze:path.join(root,old,'source-freeze.json')};
  for(const key of ['parameter_artifact','train_raw','train_execution','independent_training_report','original_source_plan','original_source_freeze']){
    const target=verifyRef(root,seal[key]);
    if(exact[key]&&target!==exact[key])throw new Error('Wrong historical path');
    if(key==='independent_training_report'&&!target.startsWith(path.join(root,'experiments/sota-2026-10-22/audit/epoch30')+path.sep))throw new Error('Wrong historical TRAIN audit scope');
  }
  if(seal.parameter_artifact.bytes!==5950520||seal.parameter_artifact.sha256!=='46bcb1c9bcf7a6bd9f7491f1233f38b65b1c3672de5370f4d1e1b5db24ae796f'
      ||seal.original_source_plan.sha256!=='d6c46944bbac2cb8ef65a51e68d927e10b869123004f941d56292cef1e0bd94b'
      ||seal.original_source_freeze.sha256!=='179a0463338808f2d39925fe480a02c4eb144ee634044594a8c68ca51a35e14a'
      ||seal.parameter_artifact.path!==plan.trained_parameters_path)throw new Error('Archived model substitution/relabel refused');
  const execution=JSON.parse(fs.readFileSync(checked(root,seal.train_execution.path))),counts=execution.raw_operation_counters;
  if(execution.epoch!==30||execution.kind!=='REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC'||execution.phase!=='train'
      ||execution.status!=='WORKER_COMPLETED'||execution.worker_attempts_reserved!==1||execution.verified_worker_starts!==1
      ||execution.uncertain_start!==false||execution.owned_live_processes_closed!==true
      ||!Array.isArray(execution.owned_live_group_members)||execution.owned_live_group_members.length
      ||execution.raw_operation_counters_source!=='raw.json'||execution.operation_counts_complete!==true
      ||execution.raw_sha256!==seal.train_raw.sha256||execution.raw_bytes!==seal.train_raw.bytes||!counts
      ||['TRAIN_forward_calls_completed','backward_calls_completed','optimizer_steps_completed','training_steps'].some(key=>counts[key]!==24))
    throw new Error('Historical complete closed24-step TRAIN proof required');
  const report=JSON.parse(fs.readFileSync(checked(root,seal.independent_training_report.path)));
  if(report.epoch!==30||report.kind!=='REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC'||report.train_integrity_passed!==true)
    throw new Error('Historical independent TRAIN integrity required');
  for(const [key,sealKey] of Object.entries({artifact:'parameter_artifact',raw:'train_raw',execution:'train_execution',plan:'original_source_plan',freeze:'original_source_freeze'}))
    if(!sameRef((report.evidence||{})[key],seal[sealKey]))throw new Error('Historical independent ref chain differs');
}


function admit(){
  const root=process.env.E31_PROJECT,out=process.env.E31_OUT,planPath=process.env.E31_PLAN;
  const expected=process.env.E31_PLAN_SHA,admissionPath=process.env.E31_ADMISSION,phase=process.env.E31_PHASE;
  const study='experiments/sota-2026-10-22/epoch31';
  if(!root||!out||!planPath||!admissionPath||phase!=='dev')throw new Error('Exact phase/source environment missing');
  for(const file of [root,out,planPath,admissionPath])noSymlink(file);
  if(fs.realpathSync(root)!==root||planPath!==path.join(root,study,'plan.json')
      ||!/^[0-9a-f]{64}$/.test(expected||'')||sha(planPath)!==expected
      ||out!==path.join(root,study,'runs',phase)
      ||admissionPath!==path.join(root,study,'SOURCE_ADMISSION.json'))
    throw new Error('Exact phase external source plan required');
  const plan=JSON.parse(fs.readFileSync(planPath)),value=JSON.parse(fs.readFileSync(admissionPath));
  const source=sourceAdmission(root,study,plan,expected);
  // This gate precedes all plan-pin hashes, including DEV input byte reads.
  archiveGate(root,study,plan,value);
  const ownerPath=path.resolve(root,'../owner.json');noSymlink(ownerPath);
  const owner=JSON.parse(fs.readFileSync(ownerPath));
  const boot=fs.readFileSync('/proc/sys/kernel/random/boot_id','utf8').trim();
  const lockFD='/proc/87763/fd/3',lockInfo=fs.statSync(lockFD);
  const held=fs.readFileSync('/proc/locks','utf8').split('\n').some(line=>{
    const words=line.trim().split(/\s+/);
    if(words.slice(1,5).join(',')!=='FLOCK,ADVISORY,WRITE,87763')return false;
    const parts=(words[5]||'').split(':');return parseInt(parts[0],16)===0&&parseInt(parts[1],16)===33&&Number(parts[2])===13626;
  });
  if(boot!=='4632fb06-b0ef-4df5-b72b-0e875bbad810'||fs.statSync('/proc/self/ns/pid').ino!==4026532200
      ||fs.statSync('/proc/87763/ns/pid').ino!==4026532200||lockInfo.dev!==33||lockInfo.ino!==13626
      ||fs.readlinkSync(lockFD)!==path.resolve(root,'../../exclusive.work.lock')||!held)
    throw new Error('Actual boot/namespace/guardianFD/kernelFLOCK proof changed');
  const status=Object.fromEntries(fs.readFileSync('/proc/self/status','utf8').split('\n')
    .filter(line=>/^(NoNewPrivs|Seccomp|Seccomp_filters|Cpus_allowed_list):/.test(line))
    .map(line=>[line.split(':')[0],line.slice(line.indexOf(':')+1).trim()]));
  if(process.platform!=='linux'||process.arch!=='x64'||status.NoNewPrivs!=='1'
      ||status.Seccomp!=='2'||!['0-1','0,1'].includes(status.Cpus_allowed_list))throw new Error('Whole-worker inherited CPU/NNP/seccomp required');
  const proc=fs.readFileSync('/proc/87763/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
  const roles=plan.data_roles;
  if(plan.epoch!==31||plan.kind!=='REAL_NATIVE_ARCHIVED_LEGAL_ADAPTATION_DIAGNOSTIC'
      ||plan.actual_project!==root||plan.source_checkpoint!=='b27d0c39ed3102cd16ba616b1225b7684b76851b'
      ||!roles||Object.keys(roles).sort().join(',')!=='calibration,confirmation,dev,train'
      ||JSON.stringify(roles.train)!=='[]'
      ||JSON.stringify(roles.dev)!=='[145,597,191,620,254,160,384,571]'
      ||!Array.isArray(roles.calibration)||roles.calibration.length||!Array.isArray(roles.confirmation)||roles.confirmation.length
      ||owner.pid!==87763||owner.startticks!==19114443||owner.lock_inode!==13626
      ||owner.kernel_boot_id!==boot||owner.PID_namespace!=='pid:[4026532200]'||owner.generation!==1
      ||owner.expires_unix!==1792874642.5127344||fs.existsSync(path.join(root,'../release.request'))
      ||Date.now()/1000>=owner.expires_unix||['Z','X'].includes(proc[0])||Number(proc[19])!==19114443)
    throw new Error('Exact current source and guardian required');
  const seen=new Set();
  for(const pin of plan.pins){
    if(seen.has(pin.path))throw new Error('Duplicate source pin');seen.add(pin.path);
    verifyRef(root,pin);
  }
  const runtimePath=checked(root,plan.runtime_assets_lock_path);
  if(!seen.has(plan.runtime_assets_lock_path)||sha(runtimePath)!==plan.runtime_assets_lock_sha256)throw new Error('Unpinned runtime lock');
  const runtime=JSON.parse(fs.readFileSync(runtimePath));
  if(!Array.isArray(runtime.assets)||runtime.assets.length!==10)throw new Error('Exact10 core/BGE assets required');
  for(const row of runtime.assets)verifyRef(root,row);
  const worker=checked(root,plan.native_worker_path);
  if(plan.native_worker_path!=='experiments/sota-2026-10-22/candidate/epoch31/native_helper.cjs'
      ||!seen.has(plan.native_worker_path)||process.argv.length!==4||process.argv[1]!==worker
      ||process.argv[2]!==path.join(out,'native-bundle.json')||process.argv[3]!==path.join(out,'native-result.json'))
    throw new Error('Exact phase ANN helper/bundle/result arguments required');
  noSymlink(process.argv[2]);noSymlink(process.argv[3]);
  if(!fs.statSync(process.argv[2]).isFile()||fs.existsSync(process.argv[3]))throw new Error('Missing full vector bundle or reused native result');
  fd=fs.openSync(path.join(out,'node-progress.jsonl'),'wx',0o600);
  record('NODE_SOURCE_RUNTIME_ADMISSION_BEFORE_NATIVE_IMPORT',{phase,node_version:process.version,
    kernel_boot_id:boot,pid_namespace_inode:4026532200,guardian_lock_fd:3,
    CPU_guard_actual_proc_status:status,worker_path:worker,worker_sha256:sha(worker),
    historical_training_epoch:30,
    full_vector_bundle:{path:path.relative(root,process.argv[2]),bytes:fs.statSync(process.argv[2]).size,sha256:sha(process.argv[2])},
    process_status:fs.readFileSync('/proc/self/status','utf8').split('\n').filter(line=>/^(Threads|Cpus_allowed_list|VmRSS|VmHWM|NoNewPrivs|Seccomp|Seccomp_filters):/.test(line))});
  const binary=path.join(root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node');
  const original=Module._load;
  Module._load=function(request,parent,isMain){
    const resolved=Module._resolveFilename(request,parent,isMain);
    if(typeof resolved==='string'&&resolved.endsWith('.node')){
      if(resolved!==binary||sha(resolved)!=='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'||nativeAttempted!==0)
        throw new Error('Unexpected/repeated native addon');
      nativeAttempted++;record('NATIVE_BINARY_LOAD_BEFORE',{phase,path:resolved,sha256:sha(resolved)});
      const result=original.apply(this,arguments);nativeCompleted++;record('NATIVE_BINARY_LOAD_AFTER',{phase,path:resolved});return result;
    }
    return original.apply(this,arguments);
  };
}
module.exports={diagnostics:()=>({attempts,nativeAttempted,nativeCompleted,events:events.slice()})};
if(process.env.E31_GUARD_SYNTHETIC==='1'){
  if(process.argv[1]!==__filename)throw new Error('Synthetic guard only allowed in isolated -e preflight');
  const original=Module._load;
  Module._load=function(request,parent,isMain){
    const resolved=Module._resolveFilename(request,parent,isMain);
    if(typeof resolved==='string'&&resolved.endsWith('.node'))throw new Error('Synthetic mode forbids all native addon loads');
    return original.apply(this,arguments);
  };
}else admit();
