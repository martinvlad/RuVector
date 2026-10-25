const leaseProof=await read('/workspace/ruvector-e39-independent-audit/planning-lease-independent-v1.json');if(leaseProof.checks_passed!==true||leaseProof.scientific_authorization!==0)throw Error('Independent source-only lease review missing');
const pref='https://api.github.com/repos/'+repo,base='74dbbcb10508ced7e0edf53a0c736f14c19a19a1',scopePrefix='benchmarks/ruvector-sota-2026-10-22/';
const approved={'CONTINUATION.json':'8d0dc1b40a2478ed8308fd8942bca426058f3b45474a839a2e96e88873ba33bb','ACTIVE_RUN.json':'9072e606e34644b0a74e3f9e95c81ee74c1d361aa55d319b00434f8ee78a4275'};
const baseline=await read(S+'/actual-git-map.json'),br=await read(S+'/baseline-0.json'),bb=await read(S+'/baseline-1.json');
if(baseline.source_commit!==base||baseline.files.length!==6178||br.sha!=='e856eb5546531b1a0925553a3ffaaf5cf8bfa2d6'||bb.sha!=='2aa06448efc94e69064d992a116ec0105e1cce9d')throw Error('baseline drift');
if((await get(pref+'/git/ref/heads/'+branch)).object.sha!==base)throw Error('active branch advanced');
const sourceCommit=await get(pref+'/git/commits/'+base);if(sourceCommit.tree.sha!==br.sha)throw Error('parent mismatch');
const expected=new Map(baseline.files.map(x=>[x.path,Object.fromEntries(['path','mode','type','sha','size'].map(k=>[k,x[k]]))]));
const changed=[];
for(const name of ['CONTINUATION.json','ACTIVE_RUN.json']){
 const path=S+'/controls-lease/'+name,pin=await readRequestMeta(path);if(pin.sha256!==approved[name])throw Error('control drift');
 const body=await readText(path);const blob=await mutate('e39-planning-blob-'+name.replace('.json',''),'mcp__codex_apps__github_create_blob',{repository_full_name:repo,encoding:'utf-8',content:body});
 changed.push({path:scopePrefix+name,mode:'100644',type:'blob',sha:blob.sha});expected.set(name,{path:name,mode:'100644',type:'blob',sha:blob.sha,size:pin.bytes});
}
const created=await mutate('e39-planning-tree','mcp__codex_apps__github_create_tree',{repository_full_name:repo,base_tree_sha:br.sha,tree_elements:changed});
const root=await get(pref+'/git/trees/'+created.sha),benchSHA=root.tree.find(x=>x.path==='benchmarks').sha,benchTree=await get(pref+'/git/trees/'+benchSHA),scopeSHA=benchTree.tree.find(x=>x.path==='ruvector-sota-2026-10-22').sha;
for(const [actual,before,key,replacement]of[[root,br,'benchmarks',benchSHA],[benchTree,bb,'ruvector-sota-2026-10-22',scopeSHA]]){
 if(actual.truncated||actual.tree.length!==before.tree.length)throw Error('siblings length');
 for(const row of before.tree){const got=actual.tree.find(x=>x.path===row.path);if(!got||got.mode!==row.mode||got.type!==row.type||got.sha!==(row.path===key?replacement:row.sha))throw Error('sibling mutation');}
}
const full=await get(pref+'/git/trees/'+scopeSHA+'?recursive=1');if(full.truncated)throw Error('truncated');const leaves=full.tree.filter(x=>x.type!=='tree');if(leaves.length!==expected.size)throw Error('leaf count');
for(const leaf of leaves){const wanted=expected.get(leaf.path);if(!wanted||['path','mode','type','sha','size'].some(k=>leaf[k]!==wanted[k]))throw Error('tuple mismatch '+leaf.path);}
if((await get(pref+'/git/ref/heads/'+branch)).object.sha!==base)throw Error('late branch advanced');
const commit=await mutate('e39-planning-commit','mcp__codex_apps__github_create_commit',{repository_full_name:repo,parent_sha:base,tree_sha:created.sha,message:'benchmarks: reserve epoch39 verified real financial NLI pilot source review; no scientific allowance'});
const actual=await get(pref+'/git/commits/'+commit.sha);if(actual.parents.length!==1||actual.parents[0].sha!==base||actual.tree.sha!==created.sha)throw Error('commit mismatch');
await mutate('e39-planning-ref','mcp__codex_apps__github_update_ref',{repository_full_name:repo,branch_name:branch,expected_sha:base,force:false,sha:commit.sha});
if((await get(pref+'/git/ref/heads/'+branch)).object.sha!==commit.sha)throw Error('post ref mismatch');
const result={phase:'lease',commit:commit.sha,parent:base,root:created.sha,bench:benchSHA,scope:scopeSHA,leaves:leaves.length,verified_actual_full_tree:true,approved_control_sha256:approved};
await tools.apply_patch('*** Begin Patch\n*** Add File: '+S+'/publication-lease.json\n+'+JSON.stringify(result)+'\n*** End Patch');await readRequestMeta(S+'/publication-lease.json');text(result);
