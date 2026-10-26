"""Exact read-only bridge. The retired reserve WAL is never repaired or ACKed."""
import json
import publication_common as c
PARENT='fadb176e645b8ba5ba87a6caf088444bac650e67'
PROOF={'bytes':6996,'sha256':'461a8bc63222f9cc7d2685f3e73e7a77d2829743bb3d5b2524571a5db79ec8de'}
JOURNAL={'bytes':3585,'sha256':'b962a860e8ee341ad0920c44b9b59ee1f2442aee12a5bbfd7593ada0904b11d3'}
REF={'bytes':237,'sha256':'ec751a2aaf9d10a3755919f53fb5acc4c0b29d5adae1ecb7d86031bd6afec512'}

def validate_structure(proof,rows,requests):
 for k in('checks_passed','verified_actual_remote_readback','desired_reference_state_verified','reserve_desired_state_verified','bridge_to_first_distinct_SOURCE_parent_allowed_in_principle'):
  c.require(proof.get(k)is True,'Exact independent reserve reconciliation missing '+k)
 for k in('repeat_original_ref_request_authorized','write_or_repair_original_journal_authorized','bridge_is_actual_mutation_authorization','original_durable_ref_ACK_present','original_publication_receipt_present'):
  c.require(proof.get(k)is False,'Reconciliation never authorizes retry or fabricates ACK')
 c.require(proof['commit']==PARENT and proof['parent']==c.BASE and proof['original_ref_invocation_execution']=='UNKNOWN_PERMANENTLY_NO_DURABLE_ACK','Actual desired state and attribution distinct')
 c.require(type(proof['scientific_authorization'])is int and proof['scientific_authorization']==0 and proof['all_actual_reserve_scientific_slots_zero']is True,'Old reserve never admitted scientific work')
 c.require(len(rows)==9 and proof['original_journal_rows']==9 and proof['original_journal_successful_ACK_pairs']==4 and proof['original_unclosed_intent_id']=='e43-reserve-ref','Exact retired nine-row scope')
 expected=[('e43-reserve-blob-0','create_blob'),('e43-reserve-blob-1','create_blob'),('e43-reserve-tree-0','create_tree'),('e43-reserve-commit','create_commit')]
 for i,(ident,kind)in enumerate(expected):
  intent,response=rows[2*i:2*i+2];c.require(intent['id']==response['id']==ident and intent['phase']=='intent'and response['phase']=='response'and response['payload']['ok']is True,'Four exact ACK pairs only')
  c.require(intent['kind']==response['kind']=='mcp__codex_apps__github_'+kind,'Original tool kinds')
 last=rows[-1];c.require(last['id']=='e43-reserve-ref'and last['phase']=='intent'and last['kind']=='mcp__codex_apps__github_update_ref','Final original reference stays unclosed')
 for r in rows:c.require(r['owner']==130591 and r['generation']==4 and r['publication_phase']=='reserve'and r['original_blob5_execution']=='UNKNOWN_PERMANENTLY','Exact original owner/scope/old uncertainty')
 ref=requests['e43-reserve-ref'];expected_ref={'repository_full_name':c.REPO,'branch_name':c.BRANCH,'expected_sha':c.BASE,'force':False,'sha':PARENT};c.require(c.same(ref,expected_ref),'Retired exact CAS request never repeated')
 commit=requests['e43-reserve-commit'];c.require(commit['parent_sha']==c.BASE and commit['tree_sha']==proof['tree_sha']and rows[7]['payload']['result']['sha']==PARENT,'ACKcommit/request/actual desired state binding')
 c.require(rows[5]['payload']['result']['sha']==proof['tree_sha'],'Original ACKtree/full actual root binding')
 for i,(_,kind)in enumerate(expected[:2]):
  req=requests[rows[2*i]['id']];c.require(req['encoding']=='utf-8'and c.git(req['content'].encode())==rows[2*i+1]['payload']['result']['sha'],'Original blob request/ACK identity')
 return {'original_ref_invocation_execution':'UNKNOWN_PERMANENTLY_NO_DURABLE_ACK','desired_SOURCE_parent':PARENT,'original_journal_repaired':False,'original_ref_repeat_authorized':False}

def checked_bridge():
 proof=json.loads(c.checked(c.W/'reserve-reconciliation-independent-v1.json',PROOF));raw=c.checked(c.W/'e43-mutation-journal.jsonl',JOURNAL);rows=[json.loads(r)for r in raw.splitlines()];requests={}
 c.require(c.same({k:proof['original_reserve_journal'][k]for k in('bytes','sha256')},JOURNAL)and c.same({k:proof['original_reserve_ref_request'][k]for k in('bytes','sha256')},REF),'Proof exact original evidence fingerprints')
 for r in rows:
  if r['phase']=='intent':
   expected=c.W/'e43-mutation-requests'/(r['id']+'.json');c.require(r['payload']['path']==str(expected),'Original request paths fixed');requests[r['id']]=json.loads(c.checked(expected,r['payload']))
   c.validate_request(r['kind'],requests[r['id']])
 c.checked(c.W/'e43-mutation-requests/e43-reserve-ref.json',REF)
 c.require(not(c.W/'publication-reserve.json').exists(),'No synthetic original publication receipt')
 return validate_structure(proof,rows,requests)
