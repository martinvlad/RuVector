'use strict';
// Source-admitted native helper preload: no network capability, inherited CPU0,1.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),Module=require('node:module');
const KIND='REAL_CONTRACTNLI_HELDOUT_DEV_TRANSFER_PILOT',SOURCE='2cf5aba60a050079506a5e9aa5463f44c1efcd5a';
const BINARY='retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node';
const BINARY_SHA='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e';
let fd=null;const counts={Node_network_operations_attempted:0,native_binary_loads_attempted:0,native_binary_loads_completed:0};
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
function noSymlink(file){let p=path.resolve(file);for(;;){if(fs.existsSync(p)&&fs.lstatSync(p).isSymbolicLink())throw new Error('NODE_SYMLINK_REFUSED');const q=path.dirname(p);if(q===p)break;p=q;}}
function record(event){if(fd!==null){fs.writeSync(fd,JSON.stringify({event,pid:process.pid,phase:'dev',role:'dev',...counts})+'\n');fs.fsyncSync(fd);}}
function deny(){counts.Node_network_operations_attempted++;record('NODE_NETWORK_DENIED');throw new Error('NODE_NETWORK_FORBIDDEN');}
for(const name of ['node:http','node:https','node:net','node:tls','node:dgram','node:dns']){
 const m=require(name);for(const key of ['request','get','connect','createConnection','createServer','createSocket','lookup','resolve','resolve4','resolve6','resolveAny'])if(typeof m[key]==='function')m[key]=deny;
 if(m.Socket&&m.Socket.prototype)m.Socket.prototype.connect=deny;
}
if(typeof global.fetch==='function')global.fetch=deny;
function admit(){
 const root=process.env.E40_PROJECT,external=process.env.E40_EXTERNAL_RUN,nativeRoot=process.env.E40_NATIVE_ROOT;
 const planPath=process.env.E40_PLAN,expected=process.env.E40_PLAN_SHA,admissionPath=process.env.E40_ADMISSION;
 if(!root||!external||!nativeRoot||!planPath||!admissionPath||process.env.E40_ROLE!=='dev')throw new Error('NODE_SOURCE_ENV_MISSING');
 for(const file of [root,external,nativeRoot,planPath,admissionPath])noSymlink(file);
 if(sha(planPath)!==expected||planPath!==path.join(root,'experiments/sota-2026-10-22/epoch40/plan.json'))throw new Error('NODE_EXACT_PLAN_REQUIRED');
 const p=JSON.parse(fs.readFileSync(planPath)),a=JSON.parse(fs.readFileSync(admissionPath));
 if(p.epoch!==40||p.kind!==KIND||p.source_checkpoint!==SOURCE||p.external_run_directory!==external||p.native_asset_root!==nativeRoot
  ||a.epoch!==40||a.kind!==KIND||a.phase!=='dev'||a.plan_sha256!==expected||a.source_freeze_sha256!==p.source_freeze_sha256||a.verified_actual_remote_readback!==true
  ||a.owner_pid!==120232||a.owner_startticks!==27979422||a.kernel_boot_id!=='4632fb06-b0ef-4df5-b72b-0e875bbad810'||a.pid_namespace_inode!==4026532200)throw new Error('NODE_SOURCE_ADMISSION_CHANGED');
 if(fs.readFileSync('/proc/sys/kernel/random/boot_id','utf8').trim()!=='4632fb06-b0ef-4df5-b72b-0e875bbad810'||fs.statSync('/proc/self/ns/pid').ino!==4026532200||fs.statSync('/proc/120232/ns/pid').ino!==4026532200)throw new Error('NODE_BOOT_NAMESPACE_CHANGED');
 const scope='/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05',owner=JSON.parse(fs.readFileSync(path.join(scope,'owner.json')));
 const statWords=fs.readFileSync('/proc/120232/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
 if(owner.pid!==120232||owner.startticks!==27979422||owner.expires_unix!==1792966892.306817||Date.now()/1000>=owner.expires_unix
  ||['Z','X'].includes(statWords[0])||Number(statWords[19])!==27979422||fs.existsSync(path.join(scope,'release.request')))throw new Error('NODE_GUARDIAN_EXPIRED');
 const lockFD='/proc/120232/fd/3',li=fs.statSync(lockFD);
 if(li.dev!==33||li.ino!==13626||fs.readlinkSync(lockFD)!=='/tmp/ruvector-sota-2026-10-22/exclusive.work.lock')throw new Error('NODE_GUARDIAN_FD_CHANGED');
 const held=fs.readFileSync('/proc/locks','utf8').split('\n').some(line=>{const w=line.trim().split(/\s+/);if(w.slice(1,5).join(',')!=='FLOCK,ADVISORY,WRITE,120232')return false;const v=(w[5]||'').split(':');return parseInt(v[0],16)===0&&parseInt(v[1],16)===33&&Number(v[2])===13626;});
 if(!held)throw new Error('NODE_GUARDIAN_FLOCK_MISSING');
 const status=Object.fromEntries(fs.readFileSync('/proc/self/status','utf8').split('\n').filter(l=>/^(NoNewPrivs|Seccomp|Cpus_allowed_list):/.test(l)).map(l=>[l.split(':')[0],l.slice(l.indexOf(':')+1).trim()]));
 if(status.NoNewPrivs!=='1'||status.Seccomp!=='2'||!['0-1','0,1'].includes(status.Cpus_allowed_list))throw new Error('NODE_INHERITED_CPU_GUARD_REQUIRED');
 for(const row of p.pins){const file=path.join(root,row.path);noSymlink(file);if(fs.statSync(file).size!==row.bytes||sha(file)!==row.sha256)throw new Error('NODE_FROZEN_SOURCE_CHANGED');}
 const helper=path.join(root,p.native_worker_path);
 if(process.argv.length!==4||process.argv[1]!==helper||process.argv[2]!==path.join(external,'dev-native-bundle.json')||process.argv[3]!==path.join(external,'dev-native-result.json'))throw new Error('NODE_EXACT_PRIVATE_IO_REQUIRED');
 for(const file of process.argv.slice(2))noSymlink(file);
 if(fs.statSync(process.argv[2]).size>67108864)throw new Error('NATIVE_SOURCE_FRAME_EXCEEDS64MIB');
 const parent=fs.readFileSync('/proc/'+process.ppid+'/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
 const attempt=JSON.parse(fs.readFileSync(path.join(root,'experiments/sota-2026-10-22/epoch40/runs/dev/attempt.json')));
 if(attempt.pid!==process.ppid||attempt.startticks!==Number(parent[19])||attempt.pgid!==process.ppid||attempt.sid!==process.ppid)throw new Error('NODE_WORKER_IDENTITY_MISMATCH');
 fd=fs.openSync(path.join(external,'dev-node-progress.jsonl'),'wx',0o600);record('NODE_SOURCE_ADMISSION_BEFORE_NATIVE');
 const binary=path.join(nativeRoot,BINARY);noSymlink(binary);if(sha(binary)!==BINARY_SHA)throw new Error('NODE_NATIVE_BINARY_CHANGED');
 const original=Module._load;
 Module._load=function(request,parent,isMain){const resolved=Module._resolveFilename(request,parent,isMain);
  if(typeof resolved==='string'&&resolved.endsWith('.node')){
   if(resolved!==binary)throw new Error('NODE_ALTERNATE_BINARY_FORBIDDEN');counts.native_binary_loads_attempted++;record('NATIVE_BINARY_LOAD_BEFORE');
   const result=original.apply(this,arguments);counts.native_binary_loads_completed++;record('NATIVE_BINARY_LOAD_AFTER');return result;
  }
  return original.apply(this,arguments);
 };
}
admit();
