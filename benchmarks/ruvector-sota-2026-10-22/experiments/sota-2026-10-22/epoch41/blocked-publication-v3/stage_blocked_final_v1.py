"""Outside-project, one direct planning-parent FINAL transport; no Git calls."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,copy,json,re
import blocked_common_v1 as c
import blocked_transport_v1 as t
import build_blocked_checkpoint_v1 as b

def prepare(a):
 root,kit,inputs,docs,oldcp=b.setup(a.project,a.kit);m,current=b.sealed(root);result=b.validate_outputs(root,inputs);c.require(c.same_fact(result,b.assemble_facts(inputs,docs)),'Exact actual metadata result projection')
 controls,prior=map(c.directory,(a.controls,a.priorcontrols));out=c.new_output(a.out,(root,kit,controls,prior))
 c.require(out==root.parent/'stage-final' and controls==root.parent/'controls-final' and prior==root.parent/'controls-lease','Exact final/control placements')
 c.require(a.parent==b.PARENT and dict(zip(('root','bench','scope'),(a.expected_root,a.expected_bench,a.expected_scope)))==b.TREES and re.fullmatch('[0-9a-f]{40}',a.expected_main or ''),'Exact actual planning parent/trees, read-only main')
 proofbytes=c.content(a.parent_readback);proof=c.loads(proofbytes)
 c.require((len(proofbytes),c.sha(proofbytes))==b.PINNED['planning_readback'] and proof.get('commit')==b.PARENT and all(proof.get(k)==v for k,v in b.TREES.items()) and proof.get('checks_passed') is True,'Exact independent actual planning readback')
 baseline=t.verify_baseline(kit,c.parse(a.source_filemap));t.checked_review(c.parse(a.reviewed_files),current)
 bodies=t.controls_at(controls);beforeb=t.controls_at(prior);oldcont=c.parse(kit/'CONTINUATION.json');pcont=c.loads(beforeb['CONTINUATION.json']);pactive=c.loads(beforeb['ACTIVE_RUN.json'])
 cp,cont,active=(c.loads(bodies[k]) for k in ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'))
 c.require(beforeb['CHECKPOINT_MANIFEST.json']==c.content(kit/'CHECKPOINT_MANIFEST.json'),'No prior data/scientific SOURCE CP')
 _,rows=t.checkpoint_extension(oldcp,cp,current)
 mutable={'active_run','checkpoint_manifest_sha256','prior_published_base_commit','epochs','execution_observed','rejection_ledger','latest_learning','next_research_priority','benchmark_refresh'}
 t.preserve_history(pcont,cont,mutable)
 c.require(c.same_fact(cont['active_run'],dict(active,path='ACTIVE_RUN.json')) and cont['checkpoint_manifest_sha256']==c.sha(bodies['CHECKPOINT_MANIFEST.json']) and cont['prior_published_base_commit']==b.PARENT,'Owned controls/hash/parent')
 c.require(pactive.get('state')=='EPOCH41_PLANNING_LEASE' and active.get('state')=='EPOCH41_BLOCKED_PRE_DATA_ADMISSION_CLOSED' and active.get('work_active') is False and active.get('experiments_active') is False and active.get('OS_lock_held') is True and active.get('checkpoint_parent')==b.PARENT,'Direct planning-to-blocked closure only')
 c.check_owner_identity(active.get('physical_owner',{}),root.parent)
 for k in ('native_allowed','conditional_train_allowed','conditional_dev_allowed','conditional_calibration_allowed','conditional_engineering_allowed','confirmation_allowed','conditional_confirmation_allowed'):c.require(c.same_fact(active.get(k),0),'Every allowance zero')
 c.require(c.same_fact(active.get('phase_remaining'),b.REMAINING),'All remaining slots zero')
 for k,v in pcont.get('execution_observed',{}).items():c.require(c.same_fact(cont['execution_observed'].get(k),v),'Old observed counters changed')
 c.require(set(cont['execution_observed'])==set(pcont.get('execution_observed',{}))|{'epoch41_blocked_predata'} and c.same_fact(cont['execution_observed']['epoch41_blocked_predata'],{'actual_execution':m['actual_execution'],'cumulative_execution':m['cumulative_execution']}),'Only actual blocked record appended')
 c.require(c.same_fact(cont['epochs'][:-1],pcont.get('epochs',[])) and cont['epochs'][-1]=={'epoch':41,'status':b.STATUS,'manifest':c.ref(root,b.E+'EPOCH_MANIFEST.json'),'experiment_executed':False},'Exactly one admission-blocked epoch')
 oldledger=c.parse(root/pcont['rejection_ledger']['path']);ledger=c.parse(root/m['rejection_ledger']['path'])
 for k,v in oldledger.items():
  if k=='preparation_blocks':c.require(c.same_fact(ledger.get(k,[])[:len(v)],v),'Old preparation-block prefix changed')
  else:c.require(c.same_fact(ledger.get(k),v),'Scientific rejection/history changed')
 c.require(set(ledger)==set(oldledger)|{'preparation_blocks','epoch41_blocked_admission_record'} and len(ledger['preparation_blocks'])==len(oldledger.get('preparation_blocks',[]))+1 and ledger['preparation_blocks'][-1]['status']==b.STATUS,'One new preparation block; no measured rejection')
 c.require(cont['epoch41_final']=={'status':b.STATUS,'manifest':c.ref(root,b.E+'EPOCH_MANIFEST.json'),'all_slots_closed':True,'no_scientific_SOURCE_or_evaluator':True},'Exact final pointer')
 before=copy.deepcopy(baseline)
 for name,body in beforeb.items():before[name]=t.leaf(name,body)
 c.require(t.scope_tree_sha(before)==b.TREES['scope'],'Actual prior planning fulltree identity')
 expected=copy.deepcopy(baseline)
 for name,body in {**current,**bodies}.items():
  c.require(name not in baseline or name in c.CONTROLS,'Historical Git overwrite refused');expected[name]=t.leaf(name,body)
 c.require(all(expected.get(p)==row for p,row in before.items() if p not in c.CONTROLS),'All historical source tuples preserved')
 c.check_transport(root,oldcont,cont,rows,set(expected),kit=kit)
 changed={p:body for p,body in {**current,**bodies}.items() if before.get(p)!=expected[p]};c.require(c.CONTROLS<=set(changed),'All three final controls changed')
 blobs,groups=t.transport_groups(changed)
 meta={'schema_version':1,'stage':'blocked-final','prior_controls_name':'controls-lease','scope':c.SCOPE,'source_checkpoint':c.BASE_COMMIT,'blocked_inputs_sha256':c.ref(root,b.INPUTS)['sha256'],'epoch_manifest':c.ref(root,b.E+'EPOCH_MANIFEST.json'),'publication_parent':b.PARENT,'read_only_main_observation':a.expected_main,'CAS_guards':{'expected_root_tree':b.TREES['root'],'expected_benchmarks_tree':b.TREES['bench'],'expected_scope_tree':b.TREES['scope'],'expected_branch_sha':b.PARENT,'force':False},'prior_Git_leaves':len(before),'expected_Git_leaves':len(expected),'old_CP_rows':len(c.cp_rows(oldcp)),'new_CP_rows':len(rows),'historical_Git_leaves':len(baseline),'reviewed_files_sha256':c.sha(c.content(a.reviewed_files)),'parent_readback_sha256':c.sha(proofbytes),'old_noncontrol_tuples_preserved':True,'Git_mutations':0,'native_or_model_or_corpus_calls':0,'large_blob_requests':[],'create_tree_groups':[],'changed_files':[{'path':p,'bytes':len(body),'sha256':c.sha(body),'git_blob_sha1':c.gitsha(body)} for p,body in sorted(changed.items())]}
 out.mkdir(mode=0o700);(out/'transport').mkdir(mode=0o700)
 for i,(name,body,payload) in enumerate(blobs):
  file='transport/blob-%03d.json'%i;data=c.encoded(payload);c.write(out/file,data);meta['large_blob_requests'].append({'path':name,'file':file,'bytes':len(data),'sha256':c.sha(data),'expected_blob_sha1':c.gitsha(body)})
 for i,group in enumerate(groups):
  file='transport/tree-%03d.json'%i;data=c.encoded({'tree_elements':group});c.require(len(data)<t.MAX_TREE_JSON,'Strict tree cap');c.write(out/file,data);meta['create_tree_groups'].append({'file':file,'bytes':len(data),'sha256':c.sha(data),'entries':len(group)})
 leaves=c.encoded({'schema_version':1,'scope':c.SCOPE,'source_checkpoint':c.BASE_COMMIT,'files':[expected[p] for p in sorted(expected)]});c.write(out/'expected-leaves.json',leaves);meta['expected_leaves']={'file':'expected-leaves.json','bytes':len(leaves),'sha256':c.sha(leaves),'count':len(expected)};c.write(out/'metadata.json',c.encoded(meta,pretty=True));return meta

if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ('project','kit','controls','priorcontrols','source-filemap','reviewed-files','parent-readback','out'):p.add_argument('--'+n,type=Path,required=True)
 for n in ('parent','expected-main','expected-root','expected-bench','expected-scope'):p.add_argument('--'+n,required=True)
 r=prepare(p.parse_args());print(json.dumps({k:r[k] for k in ('stage','publication_parent','expected_Git_leaves','new_CP_rows')},sort_keys=True))
