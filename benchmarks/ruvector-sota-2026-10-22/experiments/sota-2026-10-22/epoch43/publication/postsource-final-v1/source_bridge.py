"""FINAL-only read-only actual SOURCE reconciliation; never repairs its WAL."""
import json
import publication_common as c
PARENT='ac9c5f367120d02458121a2c366bcc8118468159'
PROOF={'bytes':7985,'sha256':'4031c441dd56386742b7b94c7f0007f86115621ce295f7da9595a60975b122eb'}
JOURNAL={'bytes':151506,'sha256':'24500064562669fabc137a391e43d669b573f4a685f9a74ba038f3be0401ff0d'}
RAW={'bytes':37,'sha256':'3b422897e742bbb9ed66e23f8153fcb64716ad1fd16694756cb67b554ce016a3'}
REF={'bytes':237,'sha256':'261479f1eabec8bcf4628176b04365e5b7e20e4ec3bb204b409d0d26f3b486d5'}

def validate_structure(proof,rows,request,raw):
 for k in('checks_passed','verified_actual_remote_readback','desired_reference_state_verified','source_desired_state_verified','raw_non_identifying_success_retained','bridge_to_first_distinct_FINAL_parent_allowed_in_principle'):c.require(proof.get(k)is True,'Actual SOURCE reconciliation '+k)
 for k in('repeat_original_SOURCE_ref_request_authorized','write_or_repair_original_SOURCE_journal_authorized','source_durable_identifying_ref_ACK_present','source_controller_publication_receipt_present','bridge_is_actual_mutation_authorization'):c.require(proof.get(k)is False,'No SOURCE retry/repair/synthetic ACK')
 c.require(proof['commit']==proof['source_commit']==PARENT and proof['parent']=='fadb176e645b8ba5ba87a6caf088444bac650e67','Actual SOURCE parent/state')
 c.require(proof['original_ref_invocation_execution']=='NON_IDENTIFYING_SUCCESS_REPORTED_DESIRED_STATE_KNOWN','Nonidentifying reply is not a fabricated identity ACK')
 c.require(len(rows)==proof['source_journal_rows']==311 and proof['source_journal_successful_ACK_pairs']==155 and proof['source_unclosed_intent_id']=='e43-source-g6-ref','Exact unclosed SOURCE journal')
 for i in range(155):
  a,b=rows[2*i:2*i+2];c.require(a['phase']=='intent'and b['phase']=='response'and a['id']==b['id']and a['kind']==b['kind']and b['payload']['ok']is True,'Exact155 prior success pairs')
 for r in rows:c.require(r['generation']==6 and r['owner']==133450 and r['publication_phase']=='source','Historical SOURCE owner/scope')
 c.require(rows[-1]['id']=='e43-source-g6-ref'and rows[-1]['phase']=='intent'and rows[-1]['kind']=='mcp__codex_apps__github_update_ref','Original SOURCE ref remains intent only')
 c.require(rows[-2]['id']=='e43-source-g6-commit'and rows[-2]['payload']['result']['sha']==PARENT,'Prior sole ACKcommit matches observed desired state')
 c.require(c.same(request,{'repository_full_name':c.REPO,'branch_name':c.BRANCH,'expected_sha':'fadb176e645b8ba5ba87a6caf088444bac650e67','force':False,'sha':PARENT}),'Retired SOURCE CAS exact')
 c.require(c.same(raw,{'ok':True,'result':{'success':True}}),'Exact retained nonidentifying success only')
 return {'source_reply_scope':'NON_IDENTIFYING_SUCCESS','source_identifying_ACK_fabricated':False,'actual_FINAL_parent':PARENT}

def checked_source_bridge():
 p=c.W/'project/experiments/sota-2026-10-22/audit/epoch43/preparation/reviews/ACTUAL_SOURCE_READBACK.v1.json';proof=json.loads(c.checked(p,PROOF));base=c.W/'lease-generation6';rows=[json.loads(v)for v in c.checked(base/'source-final-journal.jsonl',JOURNAL).splitlines()];request=json.loads(c.checked(base/'source-final-requests/e43-source-g6-ref.json',REF));raw=json.loads(c.checked(base/'source-final-requests/e43-source-g6-ref.returned-response.json',RAW))
 c.require(c.same({k:proof['source_journal'][k]for k in('bytes','sha256')},JOURNAL)and c.same({k:proof['source_ref_raw_return'][k]for k in('bytes','sha256')},RAW)and c.same({k:proof['source_ref_request'][k]for k in('bytes','sha256')},REF),'Exact proof/evidence fingerprints')
 return validate_structure(proof,rows,request,raw)
