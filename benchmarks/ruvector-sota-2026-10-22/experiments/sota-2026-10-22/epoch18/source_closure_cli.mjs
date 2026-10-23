// Actual epoch18 frozen-plan structural closure plus actual pin byte hashes.
// Pure file/metadata verification; no model, RuVector, network or inference.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { sourceClosure18 as sourceClosure } from './source_closure.mjs';
const keys=new Set(['--project','--plan','--declared-public','--external-registry','--out']);
const opts={};for(let i=2;i<process.argv.length;i+=2){const k=process.argv[i],v=process.argv[i+1];if(!keys.has(k)||!v||opts[k])throw Error('Exact flags required once');opts[k]=v;}
for(const k of keys)if(!opts[k])throw Error('Missing '+k);
const root=path.resolve(opts['--project']);
const resolve=p=>path.resolve(root,p);
const input=flag=>resolve(opts[flag]);
const planPath=input('--plan'),pubPath=input('--declared-public'),registryPath=input('--external-registry'),out=input('--out');
const safe=p=>{if(p!==root&&!p.startsWith(root+path.sep))throw Error('Path escapes isolated project');for(let q=p;q!==path.dirname(root);q=path.dirname(q)){if(fs.lstatSync(q).isSymbolicLink())throw Error('Symlink refused');if(q===root)break;}};
for(const p of [root,planPath,pubPath,registryPath])safe(p);
if(fs.existsSync(out))throw Error('Preserve existing output');safe(path.dirname(out));
const bytes=fs.readFileSync(planPath),plan=JSON.parse(bytes),pubBytes=fs.readFileSync(pubPath),regBytes=fs.readFileSync(registryPath),pub=JSON.parse(pubBytes),registry=JSON.parse(regBytes);
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
if(!Array.isArray(plan.pins)||!plan.pins.length||!Array.isArray(pub)||!Array.isArray(registry))throw Error('Expected nonempty actual plan.pins and metadata arrays');
const result=sourceClosure(plan.pins,pub,registry);
if(result.status!=='STRUCTURAL_CLOSURE_PASS')throw Error(JSON.stringify(result));
const adapter='experiments/sota-2026-10-22/epoch16/source_closure.mjs';
if(!plan.pins.some(x=>x.path===adapter))throw Error('Licensed-data adapter must be frozen');
if(!plan.pins.some(x=>x.path==='experiments/sota-2026-10-22/epoch18/source_closure.mjs'))throw Error('Epoch18 strict multiplicity adapter must be frozen');
const own=path.relative(root,fileURLToPath(import.meta.url)).split(path.sep).join('/'),guard='experiments/sota-2026-10-22/audit/epoch14/source_closure.mjs';
if(!plan.pins.some(x=>x.path===own)||!plan.pins.some(x=>x.path===guard))throw Error('Both executable CLI and reviewed structural guard must be frozen plan pins');
const outrel=path.relative(root,out).split(path.sep).join('/');if(plan.pins.some(x=>x.path===outrel))throw Error('Guard output cannot recursively pin its own plan');
const declared=new Map([...pub,...registry].map(x=>[x.path,x]));
const checked=[];
for(const r of plan.pins){const p=resolve(r.path);safe(p);const st=fs.statSync(p);if(!st.isFile())throw Error('Nonregular actual pin '+r.path);if(st.size!==declared.get(r.path)?.bytes)throw Error('Actual declared byte length mismatch '+r.path);const h=crypto.createHash('sha256');for await(const b of fs.createReadStream(p))h.update(b);const actual=h.digest('hex');if(actual!==r.sha256)throw Error('Actual pin hash mismatch '+r.path);checked.push({path:r.path,bytes:st.size,sha256:actual});}
const report={schema_version:1,at:new Date().toISOString(),status:'ACTUAL_FROZEN_PLAN_SOURCE_CLOSURE_AND_PIN_BYTES_PASS',plan_SHA256:digest(bytes),declared_public_manifest_SHA256:digest(pubBytes),external_registry_SHA256:digest(regBytes),structural_result:result,actual_pin_files_verified:checked.length,actual_pin_identities:checked,guard_SHA256:digest(fs.readFileSync(resolve(guard))),CLI_SHA256:digest(fs.readFileSync(resolve(own))),scope:'Actual frozen plan declared-public/explicit model-native-licensed-data registry coverage and real pin SHA256 verification only. Does not reconstruct missing files, execute acquisition helpers or verify ABI/provider/model inference. No benchmark generalization or official result.',model_native_session_fit_paid_GPU_calls:0,official_score:null,official_rank:null};
const raw=JSON.stringify(report,null,2)+'\n';fs.writeFileSync(out,raw,{flag:'wx'});process.stdout.write(JSON.stringify({status:report.status,plan_SHA256:report.plan_SHA256,actual_pin_files_verified:checked.length,structural_result:result,report_SHA256:digest(raw)})+'\n');
