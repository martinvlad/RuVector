"""Once-only root custodian: after authenticated closure decode selected12 labels.

The worker never imports/invokes this module. The final scorer uses the retained
join and never opens the original corpus or opaque vault. Progress is durable
per token; a partial failure is final, cannot be retried or reported as12.
"""
import argparse,json,struct
from pathlib import Path
import finfact_io as I
import finfact_closure as C
import finfact_data as D

def join_gold(admission_ref,project,out_directory):
 checked=C.checked_bundle(admission_ref,project);ids=checked['ids'];plan=checked['objects']['plan'];assets=plan['external_data_assets'];vaults=[x for x in assets if x['role']=='dev_oracle'];I.require(len(vaults)==1,'EXACT_OPAQUE_VAULT_REFERENCE_REQUIRED');vault_ref={k:v for k,v in vaults[0].items()if k!='role'};out=Path(out_directory)
 I.require(out.is_absolute()and not out.exists()and not out.is_relative_to(Path(project)),'NEW_EXTERNAL_GOLD_JOIN_DIRECTORY_REQUIRED');out.mkdir(mode=0o700);marker=Path(str(vault_ref['path'])+'.DECODE_ATTEMPT.json');I.put(marker,{'schema_version':1,'epoch':39,'kind':I.KIND,'phase':'dev','admission':admission_ref,'source_plan_sha256':checked['source_plan_sha256'],'semantic_labels_decoded_so_far':0,'automatic_retry':False});labels={};token_hashes={};count=0;report={'schema_version':1,'epoch':39,'kind':I.KIND,'phase':'dev','source_plan_sha256':checked['source_plan_sha256'],'status':'GOLD_JOIN_FAILED_FINAL_NO_RETRY','semantic_labels_decoded':0,'decode_attempted_tokens':0,'semantic_decode_count_uncertain':False,'label_reader_calls':1,'original_archive_gold_traversals':0,'model_tokenizer_native_calls':0,'used_confirmation_identities':[],'evidence':{'admission':admission_ref,'vault':vault_ref,**checked['references']},'errors':[]}
 try:
  b=I.read_ref(vault_ref);I.require(b.startswith(D.MAGIC),'OPAQUE_VAULT_MAGIC');cursor=len(D.MAGIC)
  def sized():
   nonlocal cursor
   I.require(cursor+4<=len(b),'VAULT_LENGTH_HEADER');n=struct.unpack_from('<I',b,cursor)[0];cursor+=4;I.require(cursor+n<=len(b),'VAULT_TRUNCATED');r=b[cursor:cursor+n];cursor+=n;return r
  header=json.loads(sized(),object_pairs_hook=I.unique);I.require(header['schema_version']==1 and header['epoch']==39 and header['kind']==I.KIND and header['role']=='dev'and header['source_archive_sha256']==D.ARCHIVE_SHA and header['ids']==ids and header['label_encoding']=='OPAQUE_RAW_JSON_STRING_TOKENS_NOT_DECODED','GOLD_VAULT_HEADER_MISMATCH')
  for i,caseid in enumerate(ids):
   token=sized();I.put(out/f'progress-{i:02d}-before.json',{'schema_version':1,'epoch':39,'kind':I.KIND,'phase':'dev','caseid':caseid,'previous_semantic_decodes':count,'token_sha256':I.sha(token),'decode_started':True,'decode_completed':False});report['decode_attempted_tokens']+=1
   # If the process dies between this decode and its durable completion, the
   # unmatched before marker records uncertainty. No second call is authorized.
   value=json.loads(token);count+=1;report['semantic_labels_decoded']=count;I.put(out/f'progress-{i:02d}-after.json',{'schema_version':1,'epoch':39,'kind':I.KIND,'phase':'dev','caseid':caseid,'semantic_decodes_completed':count,'decode_completed':True,'supported_literal':type(value)is str and value in M_LABELS})
   I.require(type(value)is str and value in M_LABELS,'UNSUPPORTED_OFFICIAL_LABEL_NO_REMAP');labels[caseid]=value;token_hashes[caseid]=I.sha(token)
  I.require(cursor==len(b),'EXTRA_GOLD_VAULT_DATA');I.require(count==12 and len(labels)==12,'EXACT_TWELVE_JOINED_LABELS_REQUIRED');joined={'schema_version':1,'epoch':39,'kind':I.KIND,'phase':'dev','source_plan_sha256':checked['source_plan_sha256'],'selected_ids':ids,'labels':labels,'label_token_sha256s':token_hashes,'semantic_labels_decoded':12,'label_reader_calls':1,'all_labels_decoded_after_forecasts_and_physical_closure':True,'source_archive_sha256':D.ARCHIVE_SHA,'evidence':report['evidence'],'used_confirmation_identities':[]};report['joined_labels']=I.put(out/'joined_labels.json',joined);report['status']='GOLD_JOIN_COMPLETE_AFTER_PHYSICAL_CLOSURE'
 except Exception as error:
  report['errors'].append(type(error).__name__+':'+str(error));report['semantic_decode_count_uncertain']=len(list(out.glob('progress-*-before.json')))!=len(list(out.glob('progress-*-after.json')))
 report['semantic_labels_decoded']=count;I.put(out/'GOLD_JOIN_REPORT.json',report);return report
M_LABELS=['true','false','neutral']
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--admission',required=True);p.add_argument('--expected-admission-sha256',required=True);p.add_argument('--out',required=True);a=p.parse_args();r=I.command_ref(a.admission,a.project);I.require(r['sha256']==a.expected_admission_sha256,'ROOT_AUTHORIZED_ADMISSION_SHA_REQUIRED');v=join_gold(r,a.project,a.out);print(json.dumps({'status':v['status'],'semantic_labels_decoded':v['semantic_labels_decoded'],'semantic_decode_count_uncertain':v['semantic_decode_count_uncertain'],'errors':v['errors']}))
