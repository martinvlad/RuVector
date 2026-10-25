const canonical=x=>Array.isArray(x)?x.map(canonical):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])])):x;
const same=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));
const keys=['path','mode','type','sha','size'];
const verifyMap=(tree,expected)=>{if(tree.truncated)throw Error('truncated actual tree');const rows=tree.tree.filter(r=>r.type!=='tree');if(rows.length!==expected.files.length)throw Error('leaf count');const m=new Map(expected.files.map(r=>[r.path,r]));for(const r of rows){const x=m.get(r.path);if(!x||keys.some(k=>r[k]!==x[k]))throw Error('actual tuple drift '+r.path);}return rows.length;};
const verifySiblings=(actual,baseline,name,replacement)=>{if(actual.truncated||actual.tree.length!==baseline.tree.length)throw Error('sibling count');for(const r of baseline.tree){const a=actual.tree.find(x=>x.path===r.path);if(!a||a.mode!==r.mode||a.type!==r.type||a.sha!==(r.path===name?replacement:r.sha))throw Error('sibling drift '+r.path);}};
const publishLease=async proofPath=>{
 if(S!=='/workspace/ruvector-epoch33-0522a2c521c9'||repo!=='ruvnet/RuVector'||branch!=='benchmarks/ruvector-sota-2026-10-22')throw Error('exact lease scope');
 const api='https://api.github.com/repos/'+repo;const raw='https://raw.githubusercontent.com/'+repo+'/';const scope='benchmarks/ruvector-sota-2026-10-22/';const parent='0522a2c521c92c55d843d21c71495a44b43977e5';
 const pin=await readRequestMeta(S+'/lease-control-identities.json');const proof=await read(proofPath);
 if(proof.checks_passed!==true||proof.stage!==S+'/controls-lease'||proof.planning_control_identities_sha256!==pin.sha256||proof.planning_control_identities_bytes!==pin.bytes)throw Error('independent planning proof identity');
 const ids=await read(S+'/lease-control-identities.json');if(ids.parent!==parent||ids.CP_rows!==4542||ids.CP_sha256!=='028946668a771ea4f9d69121b46f9e111b4213c3aded6d50c4351823744b9029')throw Error('BASE CP identity');
 const head=await get(api+'/git/ref/heads/'+branch);if(head.object.sha!==parent)throw Error('branch changed: stop without mutation');
 const mainBefore=(await get(api+'/git/ref/heads/main')).object.sha;
 const oldA=await get(raw+parent+'/'+scope+'ACTIVE_RUN.json'),oldC=await get(raw+parent+'/'+scope+'CONTINUATION.json');
 if(oldA.work_active!==false||oldA.state!=='EPOCH32_CLOSED'||!same(oldA,await read(S+'/kit/ACTIVE_RUN.json'))||!same(oldC,await read(S+'/kit/CONTINUATION.json')))throw Error('active or changed remote run');
 for(const name of ['CONTINUATION.json','ACTIVE_RUN.json','CHECKPOINT_MANIFEST.json']){const a=await readRequestMeta(S+'/controls-lease/'+name);if(a.bytes!==ids.controls[name].bytes||a.sha256!==ids.controls[name].sha256)throw Error('reviewed control drift');}
 const ac=await read(S+'/controls-lease/ACTIVE_RUN.json'),cc=await read(S+'/controls-lease/CONTINUATION.json');
 if(ac.run_id!=='epoch33-0522a2c521c9'||ac.work_active!==true||ac.native_allowed!==0||ac.confirmation_allowed!==0||!same(cc.active_run,{...ac,path:'ACTIVE_RUN.json'}))throw Error('new planning controls differ');
 const blob=await mutate('e33-lease-cont-blob','mcp__codex_apps__github_create_blob',{repository_full_name:repo,content:await readText(S+'/controls-lease/CONTINUATION.json'),encoding:'utf-8'});
 if(blob.sha!==ids.controls['CONTINUATION.json'].git_blob_sha1)throw Error('actual blob mismatch');
 const tree=await mutate('e33-lease-tree','mcp__codex_apps__github_create_tree',{repository_full_name:repo,base_tree_sha:'1bffc0fea39c8dca8d898db095ff86009d07cdaf',tree_elements:[{path:scope+'CONTINUATION.json',mode:'100644',type:'blob',sha:blob.sha},{path:scope+'ACTIVE_RUN.json',mode:'100644',type:'blob',content:await readText(S+'/controls-lease/ACTIVE_RUN.json')}]});
 const rt=await get(api+'/git/trees/'+tree.sha),bench=rt.tree.find(r=>r.path==='benchmarks').sha;
 const bt=await get(api+'/git/trees/'+bench),sc=bt.tree.find(r=>r.path==='ruvector-sota-2026-10-22').sha;
 verifySiblings(rt,await read(S+'/baseline-0.json'),'benchmarks',bench);verifySiblings(bt,await read(S+'/baseline-1.json'),'ruvector-sota-2026-10-22',sc);
 const leaves=verifyMap(await get(api+'/git/trees/'+sc+'?recursive=1'),await read(S+'/lease-expected-leaves.json'));
 const before=await get(api+'/git/ref/heads/'+branch);if(before.object.sha!==parent)throw Error('late branch change; stop');
 const commit=await mutate('e33-lease-commit','mcp__codex_apps__github_create_commit',{repository_full_name:repo,parent_sha:parent,tree_sha:tree.sha,message:'benchmarks: reserve epoch33 proof-carrying typed NLI diagnostic and fixed DEV roles'});
 const actual=await get(api+'/git/commits/'+commit.sha);if(actual.parents.length!==1||actual.parents[0].sha!==parent||actual.tree.sha!==tree.sha)throw Error('created commit identity');
 await mutate('e33-lease-ref','mcp__codex_apps__github_update_ref',{repository_full_name:repo,branch_name:branch,expected_sha:parent,force:false,sha:commit.sha});
 const after=await get(api+'/git/ref/heads/'+branch);if(after.object.sha!==commit.sha)throw Error('actual CAS ref differs: stop');
 const mainAfter=(await get(api+'/git/ref/heads/main')).object.sha;
 return{phase:'planning',commit:commit.sha,parent,root:tree.sha,bench,scope:sc,leaves,CP_rows:4542,CP_sha256:ids.CP_sha256,verified_actual_full_tree:true,read_only_main_observations:{before:mainBefore,after:mainAfter,our_main_mutations:0},native_model_gold_calls:0};
};

