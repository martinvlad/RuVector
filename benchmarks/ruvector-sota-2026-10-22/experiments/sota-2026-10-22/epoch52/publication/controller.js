// Definitions only. Root explicitly invokes ONE reviewed phase, then persists its receipt.
// No scientific authorization, automatic execution, retry, or reconciliation bridge.
const W52='/dev/shm/ruvector-sota-2026-10-22/epoch52-1cb7b0384f3d';
const PUB52=W52+'/publication';
const REPO52='ruvnet/RuVector', BRANCH52='benchmarks/ruvector-sota-2026-10-22';
const DENY52=['486888de9602bbb5d817a55f707b4fcfd11c65e0','3d5a61f9068acf2dabd2ae5c6bd531d9a9b464c5','a68b7ba587332f176f65d0348de3e910aa16e77a'];
const q52=x=>"'"+String(x).replaceAll("'","'\\''")+"'";
const sh52=async cmd=>{const r=await tools.exec_command({cmd,max_output_tokens:100000});if(r.exit_code!==0)throw Error(r.output);return r.output;};
const un52=r=>{if(r.isError)throw Error('Git read failed');return typeof r.structuredContent?.content==='string'?JSON.parse(r.structuredContent.content):r.structuredContent;};
const get52=async url=>{if(DENY52.some(x=>url.includes(x)))throw Error('Retired object query forbidden');return un52(await tools.mcp__codex_apps__github_fetch({url}));};
const rawGet52=async url=>{if(DENY52.some(x=>url.includes(x)))throw Error('Retired object query forbidden');return tools.mcp__codex_apps__github_fetch({url});};
const readText52=async p=>{
  const n=Number((await sh52('taskset -c 0,1 python -I -B -c '+q52('from pathlib import Path;print(len(Path('+JSON.stringify(p)+').read_text()))'))).trim());
  const chunks=[];
  for(let start=0;start<n;start+=160000){
    const positions=[];for(let i=start;i<Math.min(n,start+160000);i+=20000)positions.push(i);
    const rows=await Promise.allSettled(positions.map(async i=>{const r=await tools.exec_command({cmd:'taskset -c 0,1 python -I -B -c '+q52('from pathlib import Path;print(Path('+JSON.stringify(p)+').read_text()['+i+':'+Math.min(n,i+20000)+'],end="")'),max_output_tokens:20000});if(r.exit_code!==0||r.output.startsWith('Warning:'))throw Error('Metadata chunk failed');return r.output;}));
    for(const r of rows){if(r.status!=='fulfilled')throw r.reason;chunks.push(r.value);}
  }
  const result=chunks.join('');if([...result].length!==n)throw Error('Metadata character count');return result;
};
const read52=async p=>JSON.parse(await readText52(p));
const pin52=async p=>JSON.parse(await sh52('taskset -c 0,1 python -I -B -c '+q52('from pathlib import Path;import hashlib,json;p=Path('+JSON.stringify(p)+');b=p.read_bytes();print(json.dumps(dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())))')));
let CONTEXT52=null,SUCCESS52=null;
const guard52=async(mode,extra={})=>{
  if(!CONTEXT52)throw Error('Explicit phase context required');
  let cmd='taskset -c 0,1 python -I -B '+q52(W52+'/publication-helpers/guard.py')+' '+q52(mode)+' --phase '+q52(CONTEXT52.phase)+' --approval '+q52(CONTEXT52.approval)+' --approval-sha '+q52(CONTEXT52.approvalSHA);
  for(const [k,v]of Object.entries(extra))cmd+=' --'+k+' '+q52(v);
  return JSON.parse(await sh52(cmd));
};
const payload52=async value=>(await sh52('taskset -c 0,1 python -I -B -c '+q52('import base64;print(base64.b64encode('+JSON.stringify(JSON.stringify(value))+'.encode()).decode())'))).trim();
const capture52=async(id,raw)=>guard52('capture-raw',{id,payload:await payload52(raw)});
const proof52=async(proof,raw)=>guard52('capture-proof',{proof,payload:await payload52(raw)});
const mutate52=async slot=>{
  if(!/^e52-(source|final)-g17-[a-z0-9-]+$/.test(slot.id))throw Error('Fresh E52 ID only');
  await new Promise(resolve=>setTimeout(resolve,2000));
  await guard52('reserve',{id:slot.id,kind:slot.kind});
  const args=await read52(PUB52+'/requests/'+slot.id+'.json');
  await guard52('intent',{id:slot.id,kind:slot.kind});await guard52('owner');
  let raw;
  try{raw=await tools[slot.kind](args);}
  catch(error){await capture52(slot.id,{transport_error:String(error)});throw error;}
  // This capture is awaited BEFORE un52, owner checks, fresh reads or response validation.
  await capture52(slot.id,raw);
  if(slot.kind.endsWith('github_update_ref')){
    await guard52('owner');
    await proof52('ref',await rawGet52('https://api.github.com/repos/'+REPO52+'/git/ref/heads/'+BRANCH52));
  }
  return guard52('response',{id:slot.id,kind:slot.kind});
};
const siblings52=(actual,before,key,sha)=>{
  if(actual.truncated||before.truncated||actual.tree.length!==before.tree.length)throw Error('Sibling count');
  for(const row of before.tree){const r=actual.tree.find(x=>x.path===row.path);if(!r||r.mode!==row.mode||r.type!==row.type||r.sha!==(row.path===key?sha:row.sha))throw Error('Unrelated sibling changed');}
};
const checkLeaves52=(actual,expected,scopeSHA)=>{
  if(actual.truncated||actual.sha!==scopeSHA||expected.scope!=='benchmarks/ruvector-sota-2026-10-22/')throw Error('Full exact scope required');
  const map=new Map(expected.files.map(r=>[r.path,r]));if(map.size!==expected.files.length)throw Error('Duplicate leaf');
  const rows=actual.tree.filter(r=>r.type!=='tree');if(rows.length!==map.size)throw Error('Leaf count');
  const seen=new Set();
  for(const r of rows){const e=map.get(r.path);if(seen.has(r.path)||!e||DENY52.includes(r.sha)||['path','mode','type','sha','size'].some(k=>r[k]!==e[k]))throw Error('Leaf identity differs');seen.add(r.path);}
  return rows.length;
};
const publishE52Phase=async(phase,approvalPath,approvalSHA)=>{
  if(CONTEXT52||!['source','final'].includes(phase)||!/^[0-9a-f]{64}$/.test(approvalSHA))throw Error('One explicit fresh controller phase only');
  CONTEXT52={phase,approval:approvalPath,approvalSHA};await guard52('check');
  const stage=W52+'/stage-'+phase,meta=await read52(stage+'/metadata.json'),mp=await pin52(stage+'/metadata.json');
  const leafPin=await pin52(stage+'/'+meta.expected_leaves.file);
  if(leafPin.bytes!==meta.expected_leaves.bytes||leafPin.sha256!==meta.expected_leaves.sha256)throw Error('Expected leaf map changed');
  const expected=await read52(stage+'/'+meta.expected_leaves.file),url='https://api.github.com/repos/'+REPO52;
  const head=await get52(url+'/git/ref/heads/'+BRANCH52),main0=await get52(url+'/git/ref/heads/main');
  if(head.ref!=='refs/heads/'+BRANCH52||main0.ref!=='refs/heads/main'||head.object.sha!==meta.source_parent||main0.object.sha!=='c44d7337c0c5ad2ecd2294178475387facb96516')throw Error('Actual parent/main advanced; STOP');
  const parent=await get52(url+'/git/commits/'+meta.source_parent);if(parent.tree.sha!==meta.expected_source_root)throw Error('Actual parent root');
  const r0=await get52(url+'/git/trees/'+parent.tree.sha),b0=await get52(url+'/git/trees/'+meta.expected_source_bench);
  if(r0.tree.find(r=>r.path==='benchmarks')?.sha!==meta.expected_source_bench||b0.tree.find(r=>r.path==='ruvector-sota-2026-10-22')?.sha!==meta.expected_source_scope)throw Error('Actual root/bench/scope baseline');
  for(const row of meta.blobs)await mutate52(row);
  for(const row of meta.trees)await mutate52(row);
  const r1=await get52(url+'/git/trees/'+meta.expected_final_root),b1=await get52(url+'/git/trees/'+meta.expected_final_bench);
  if(r1.sha!==meta.expected_final_root||b1.sha!==meta.expected_final_bench)throw Error('Actual desired tree SHA');
  siblings52(r1,r0,'benchmarks',meta.expected_final_bench);siblings52(b1,b0,'ruvector-sota-2026-10-22',meta.expected_final_scope);
  const leaves=checkLeaves52(await get52(url+'/git/trees/'+meta.expected_final_scope+'?recursive=1'),expected,meta.expected_final_scope);
  if(leaves!==meta.new_Git_leaves)throw Error('Expected whole-scope count');
  if((await get52(url+'/git/ref/heads/'+BRANCH52)).object.sha!==meta.source_parent)throw Error('Late parent advance; STOP');
  const commitSlot=meta.requests.find(r=>r.kind.endsWith('github_create_commit')),refSlot=meta.requests.find(r=>r.kind.endsWith('github_update_ref'));
  const commit=await mutate52(commitSlot);
  await proof52('commit',await rawGet52(url+'/git/commits/'+commit.ack_sha));await guard52('verify-commit');
  if((await get52(url+'/git/ref/heads/'+BRANCH52)).object.sha!==meta.source_parent)throw Error('Pre-CAS parent advance; STOP');
  await mutate52(refSlot);
  if((await get52(url+'/git/ref/heads/'+BRANCH52)).object.sha!==commit.ack_sha)throw Error('Fresh postCAS mismatch; STOP');
  const main1=await get52(url+'/git/ref/heads/main');if(main1.object.sha!==main0.object.sha)throw Error('Read-only main changed');
  SUCCESS52={schema_version:1,epoch:52,kind:meta.kind,phase,commit:commit.ack_sha,parent:meta.source_parent,root:meta.expected_final_root,bench:meta.expected_final_bench,scope:meta.expected_final_scope,leaves,CP_rows:meta.CP_rows,verified_actual_full_tree:true,stage_metadata_sha256:mp.sha256,source_plan_sha256:meta.plan.sha256,source_freeze_sha256:meta.source_freeze.sha256,CP_only_transport_count:70,E44_overlay55_remains_separate:true,original_blob5_execution:'UNKNOWN_PERMANENTLY',old_forbidden_Git_objects_not_queried_recreated_or_live_referenced:true,publication_only:true,scientific_authorization_granted:false,read_only_main:{before:main0.object.sha,after:main1.object.sha}};
  return SUCCESS52;
};
const persistE52Receipt=async result=>{
  if(!SUCCESS52||result!==SUCCESS52)throw Error('Only actual successful result from this controller');
  const p=PUB52+'/publication-'+result.phase+'-result.json';
  await sh52('taskset -c 0,1 python -I -B -c '+q52('from pathlib import Path;import os;p=Path('+JSON.stringify(p)+');b='+JSON.stringify(JSON.stringify(result)+'\n')+'.encode();fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);f=os.fdopen(fd,"wb");f.write(b);f.flush();os.fsync(f.fileno());f.close();d=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)'));
  return p;
};
