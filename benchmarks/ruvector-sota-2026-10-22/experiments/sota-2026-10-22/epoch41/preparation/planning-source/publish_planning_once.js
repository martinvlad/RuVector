const leaseProof=await read(S+'/planning-source-independent-v1.json');if(leaseProof.checks_passed!==true||leaseProof.scientific_authorization!==0)throw Error('Independent source-only lease review missing');
const pref='https://api.github.com/repos/'+repo,base='7a40daab6ad7caf9310f678813bfef42f907bd17',scopePrefix='benchmarks/ruvector-sota-2026-10-22/';
const approved={'CONTINUATION.json':'68cf5da10e1a6a709c3cf183e655b17f170a0bff529ea9eae2efd39038cfc21b','ACTIVE_RUN.json':'2a92db5435232bfd949e03948eaa320700b1e13dc75c919bd9d55061881ddb74'};
const baseline=await read(S+'/actual-git-map.json'),br=await read(S+'/baseline-0.json'),bb=await read(S+'/baseline-1.json');
if(baseline.source_commit!==base||baseline.files.length!==6875||br.sha!=='36db7b600f2b9dce1d29e7a3299673e43793a3d2'||bb.sha!=='f76b5b32238a4469235f201386e6a134deff33ef')throw Error('baseline drift');
if((await get(pref+'/git/ref/heads/'+branch)).object.sha!==base)throw Error('active branch advanced');
const sourceCommit=await get(pref+'/git/commits/'+base);if(sourceCommit.tree.sha!==br.sha)throw Error('parent mismatch');
const expected=new Map(baseline.files.map(x=>[x.path,Object.fromEntries(['path','mode','type','sha','size'].map(k=>[k,x[k]]))]));
const changed=[];
for(const name of ['CONTINUATION.json','ACTIVE_RUN.json']){
 const path=S+'/controls-lease/'+name,pin=await readRequestMeta(path);if(pin.sha256!==approved[name])throw Error('control drift');
 const body=await readText(path);const blob=await mutate('e41-planning-blob-'+name.replace('.json',''),'mcp__codex_apps__github_create_blob',{repository_full_name:repo,encoding:'utf-8',content:body});
 changed.push({path:scopePrefix+name,mode:'100644',type:'blob',sha:blob.sha});expected.set(name,{path:name,mode:'100644',type:'blob',sha:blob.sha,size:pin.bytes});
}
const created=await mutate('e41-planning-tree','mcp__codex_apps__github_create_tree',{repository_full_name:repo,base_tree_sha:br.sha,tree_elements:changed});
const root=await get(pref+'/git/trees/'+created.sha),benchSHA=root.tree.find(x=>x.path==='benchmarks').sha,benchTree=await get(pref+'/git/trees/'+benchSHA),scopeSHA=benchTree.tree.find(x=>x.path==='ruvector-sota-2026-10-22').sha;
for(const [actual,before,key,replacement]of[[root,br,'benchmarks',benchSHA],[benchTree,bb,'ruvector-sota-2026-10-22',scopeSHA]]){
 if(actual.truncated||actual.tree.length!==before.tree.length)throw Error('siblings length');
 for(const row of before.tree){const got=actual.tree.find(x=>x.path===row.path);if(!got||got.mode!==row.mode||got.type!==row.type||got.sha!==(row.path===key?replacement:row.sha))throw Error('sibling mutation');}
}
const full=await get(pref+'/git/trees/'+scopeSHA+'?recursive=1');if(full.truncated)throw Error('truncated');const leaves=full.tree.filter(x=>x.type!=='tree');if(leaves.length!==expected.size)throw Error('leaf count');
for(const leaf of leaves){const wanted=expected.get(leaf.path);if(!wanted||['path','mode','type','sha','size'].some(k=>leaf[k]!==wanted[k]))throw Error('tuple mismatch '+leaf.path);}
if((await get(pref+'/git/ref/heads/'+branch)).object.sha!==base)throw Error('late branch advanced');
const commit=await mutate('e41-planning-commit','mcp__codex_apps__github_create_commit',{repository_full_name:repo,parent_sha:base,tree_sha:created.sha,message:'benchmarks: reserve epoch41 context windows source review; zero scientific allowance'});
const actual=await get(pref+'/git/commits/'+commit.sha);if(actual.parents.length!==1||actual.parents[0].sha!==base||actual.tree.sha!==created.sha)throw Error('commit mismatch');
await mutate('e41-planning-ref','mcp__codex_apps__github_update_ref',{repository_full_name:repo,branch_name:branch,expected_sha:base,force:false,sha:commit.sha});
if((await get(pref+'/git/ref/heads/'+branch)).object.sha!==commit.sha)throw Error('post ref mismatch');
const result={phase:'lease',commit:commit.sha,parent:base,root:created.sha,bench:benchSHA,scope:scopeSHA,leaves:leaves.length,verified_actual_full_tree:true,approved_control_sha256:approved};
await tools.apply_patch('*** Begin Patch\n*** Add File: '+S+'/publication-lease.json\n+'+JSON.stringify(result)+'\n*** End Patch');await readRequestMeta(S+'/publication-lease.json');text(result);
