'use strict';
// Exact dynamic operational owner and source-frozen native helper preload.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),Module=require('node:module');
const KIND='REAL_CONTRACTNLI_QWEN_COMPACT_EVIDENCE_DEV_PILOT',BASE='143d1a78ea730e030ff5255a20b047d856f6305f';
const BINARY='retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node';
const BINARY_SHA='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e';
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let fd=null;const counts={Node_network_operations_attempted:0,native_binary_loads_attempted:0,native_binary_loads_completed:0};
function noLink(file){let p=path.resolve(file);for(;;){if(fs.existsSync(p)&&fs.lstatSync(p).isSymbolicLink())throw Error('NODE_SYMLINK');let q=path.dirname(p);if(q===p)break;p=q;}}
function relative(root,r){if(typeof r!=='string'||path.isAbsolute(r)||r.split('/').some(x=>['','.','..'].includes(x)))throw Error('NODE_UNSAFE_REFERENCE');const p=path.join(root,r);noLink(p);return p;}
function record(event){if(fd!==null){fs.writeSync(fd,JSON.stringify({event,pid:process.pid,phase:'dev',role:'dev',...counts})+'\n');fs.fsyncSync(fd);}}
function deny(){counts.Node_network_operations_attempted++;record('NODE_NETWORK_DENIED');throw Error('NODE_NETWORK_FORBIDDEN');}
for(const name of ['node:http','node:https','node:net','node:tls','node:dgram','node:dns']){const m=require(name);for(const k of ['request','get','connect','createConnection','createServer','createSocket','lookup','resolve','resolve4','resolve6','resolveAny'])if(typeof m[k]==='function')m[k]=deny;if(m.Socket&&m.Socket.prototype)m.Socket.prototype.connect=deny;}
if(typeof global.fetch==='function')global.fetch=deny;
const root=process.env.E47_PROJECT,external=process.env.E47_EXTERNAL_RUN,nativeRoot=process.env.E47_NATIVE_ROOT;
const planPath=process.env.E47_PLAN,planSHA=process.env.E47_PLAN_SHA,admissionPath=process.env.E47_ADMISSION;
if(!root||!external||!nativeRoot||!planPath||!admissionPath||process.env.E47_ROLE!=='dev')throw Error('NODE_ADMISSION_ENV');
for(const p of [root,external,nativeRoot,planPath,admissionPath])noLink(p);
if(planPath!==path.join(root,'experiments/sota-2026-10-22/epoch47/plan.json')||sha(planPath)!==planSHA)throw Error('NODE_PLAN_BYTES');
const p=JSON.parse(fs.readFileSync(planPath)),d=JSON.parse(fs.readFileSync(admissionPath));
if(p.epoch!==47||p.kind!==KIND||p.source_checkpoint!==BASE||d.source_plan_sha256!==planSHA||d.dispatch_authorized!==true)throw Error('NODE_SCOPE');
const sa=relative(root,d.source_admission.path);if(sha(sa)!==d.source_admission.sha256)throw Error('NODE_SOURCE_ADMISSION_BYTES');
const a=JSON.parse(fs.readFileSync(sa));
if(a.epoch!==47||a.kind!==KIND||a.phase!=='dev'||a.plan_sha256!==planSHA||a.source_freeze_sha256!==p.source_freeze.sha256||a.verified_actual_remote_readback!==true||d.source_commit!==a.actual_source_commit||a.actual_source_commit!==a.published_source_commit||a.checks_passed!==true)throw Error('NODE_ACTUAL_SOURCE_REQUIRED');
const canonical=x=>JSON.stringify(Object.fromEntries(Object.entries(x).sort(([a],[b])=>a.localeCompare(b))));
if(canonical(d.worker_slot_reservation)!==canonical(p.worker_slot_reservation)||canonical(a.worker_slot_reservation)!==canonical(p.worker_slot_reservation))throw Error('NODE_BURNED_SLOT');
const work='/tmp/ruvector-sota-2026-10-22/epoch47-143d1a78ea73',op=relative(work,p.owner_ref.path);
if(fs.statSync(op).size!==p.owner_ref.bytes||sha(op)!==p.owner_ref.sha256)throw Error('NODE_OWNER_BYTES');
const owner=JSON.parse(fs.readFileSync(op)),slot=p.worker_slot_reservation;
if(owner.pid!==slot.pid||owner.startticks!==slot.startticks||owner.generation!==slot.generation||slot.owner_sha256!==p.owner_ref.sha256||slot.permanently_burned_at_SOURCE_publication!==true)throw Error('NODE_OWNER_SLOT');
const words=fs.readFileSync('/proc/'+owner.pid+'/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
if(['Z','X'].includes(words[0])||Number(words[19])!==owner.startticks||Date.now()/1000>=owner.expires_unix||fs.existsSync(path.join(path.dirname(op),'release.request')))throw Error('NODE_OWNER_LOST');
if(fs.readFileSync('/proc/sys/kernel/random/boot_id','utf8').trim()!==owner.kernel_boot_id||fs.readlinkSync('/proc/self/ns/pid')!==owner.PID_namespace||fs.readlinkSync('/proc/'+owner.pid+'/ns/pid')!==owner.PID_namespace)throw Error('NODE_BOOT_NS');
const lf=fs.statSync('/proc/'+owner.pid+'/fd/3');if(lf.dev!==owner.lock_device||lf.ino!==owner.lock_inode)throw Error('NODE_LOCK_FD');
const held=fs.readFileSync('/proc/locks','utf8').split('\n').some(line=>{const w=line.trim().split(/\s+/);if(w.slice(1,5).join(',')!==('FLOCK,ADVISORY,WRITE,'+owner.pid))return false;const v=(w[5]||'').split(':');return Number(v[2])===owner.lock_inode&&parseInt(v[0],16)===0&&parseInt(v[1],16)===owner.lock_device;});if(!held)throw Error('NODE_FLOCK');
const status=Object.fromEntries(fs.readFileSync('/proc/self/status','utf8').split('\n').filter(l=>/^(NoNewPrivs|Seccomp|Cpus_allowed_list):/.test(l)).map(l=>[l.split(':')[0],l.slice(l.indexOf(':')+1).trim()]));
if(status.NoNewPrivs!=='1'||status.Seccomp!=='2'||!['0-1','0,1'].includes(status.Cpus_allowed_list))throw Error('NODE_INHERITED_GUARD');
const freezePath=relative(root,p.source_freeze.path);if(sha(freezePath)!==p.source_freeze.sha256)throw Error('NODE_FREEZE_BYTES');
for(const row of JSON.parse(fs.readFileSync(freezePath)).files){const file=relative(root,row.path);if(fs.statSync(file).size!==row.bytes||sha(file)!==row.sha256)throw Error('NODE_SOURCE_CHANGED');}
const helper=path.join(root,p.native_worker_path);
if(process.argv.length!==4||process.argv[1]!==helper||process.argv[2]!==path.join(external,'dev-native-bundle.json')||process.argv[3]!==path.join(external,'dev-native-result.json'))throw Error('NODE_PRIVATE_IO');
const parent=fs.readFileSync('/proc/'+process.ppid+'/stat','utf8').split(')').slice(1).join(')').trim().split(/\s+/);
const attempt=JSON.parse(fs.readFileSync(path.join(root,'experiments/sota-2026-10-22/epoch47/runs/dev/attempt.json')));
if(attempt.pid!==process.ppid||attempt.startticks!==Number(parent[19])||attempt.pgid!==process.ppid||attempt.sid!==process.ppid)throw Error('NODE_WORKER_IDENTITY');
fd=fs.openSync(path.join(external,'dev-node-progress.jsonl'),'wx',0o600);record('NODE_SOURCE_ADMISSION_BEFORE_NATIVE');
const binary=path.join(nativeRoot,BINARY);noLink(binary);if(sha(binary)!==BINARY_SHA)throw Error('NODE_BINARY_CHANGED');
const original=Module._load;
Module._load=function(request,parent,isMain){const resolved=Module._resolveFilename(request,parent,isMain);if(typeof resolved==='string'&&resolved.endsWith('.node')){if(resolved!==binary)throw Error('NODE_ALTERNATE_BINARY');counts.native_binary_loads_attempted++;record('NATIVE_BINARY_LOAD_BEFORE');const value=original.apply(this,arguments);counts.native_binary_loads_completed++;record('NATIVE_BINARY_LOAD_AFTER');return value;}return original.apply(this,arguments);};
