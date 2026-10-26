"""Root-only once E42 gold join after authenticated72/36 physical closure."""
import argparse,hashlib,importlib.util,json,struct
from pathlib import Path
HERE=Path(__file__).resolve().parent
QUALIFIER_SHA='74c95282b0cfd300bdd2921cd772d4a1bb172fe27e904c9d5598114a9e03b20d'
p=HERE/'e42_qualification.py';b=p.read_bytes()
if hashlib.sha256(b).hexdigest()!=QUALIFIER_SHA:raise ValueError('PINNED_GOLD_QUALIFIER_DRIFT')
spec=importlib.util.spec_from_file_location('e42_gold_qualification',p);Q=importlib.util.module_from_spec(spec);exec(compile(b,str(p),'exec'),Q.__dict__);F=Q.F;M=Q.M

CODEC_SHA='9c63102a01576c230da94695f593fd7bd4fe2d0b20672b74e8a7f62aba426fc4'
def safe_error(e):return {'code':'GOLD_SOURCE_OR_CUSTODY_STOP_NO_RETRY','exception_type':type(e).__name__,'message_sha256':F.sha(str(e).encode())}
def join_gold(admission_ref,project,out):
 Q.public_reference(admission_ref,project);a=F.load_ref(admission_ref,project);Q.public_reference(a['evidence']['plan'],project);plan=F.load_ref(a['evidence']['plan'],project);out=Path(out);paths=plan['external_custody_evidence_paths'];F.require(set(paths)=={'joined_labels','gold_join_report'}and str(out/'joined_labels.json')==paths['joined_labels']and str(out/'GOLD_JOIN_REPORT.json')==paths['gold_join_report']and out.is_absolute()and out.resolve()==out and not out.is_relative_to(Path(project).resolve())and not out.exists(),'EXACT_NEW_PRIVATE_CUSTODY_OUTPUT_PATHS');vaults=[x for x in plan['external_data_assets']if x['role']=='dev_oracle'];F.require(len(vaults)==1,'EXACT_ONE_OPAQUE_VAULT');vault_ref={k:v for k,v in vaults[0].items()if k!='role'};marker=Path(vault_ref['path']+'.DECODE_ATTEMPT.json');F.require(not marker.exists()and not marker.is_symlink(),'EXISTING_VAULT_ATTEMPT_HARD_STOP_NO_RETRY');out.mkdir(mode=0o700);F.put(out/'GOLD_FUNCTION_ATTEMPT.json',{'schema_version':1,'epoch':42,'kind':F.KIND,'phase':'dev','admission':admission_ref,'late_custodian_function_calls':1,'semantic_gold_values_decoded':0,'automatic_retry':False});report={'schema_version':1,'epoch':42,'kind':F.KIND,'phase':'dev','source_plan_sha256':a['evidence']['plan']['sha256'],'status':'GOLD_JOIN_FAILED_FINAL_NO_RETRY','late_custodian_function_calls':1,'label_reader_calls':0,'semantic_labels_decoded':0,'decode_attempted_tokens':0,'semantic_decode_count_uncertain':False,'original_archive_gold_traversals':0,'model_tokenizer_native_calls':0,'used_confirmation_identities':[],'evidence':{'admission':admission_ref},'errors':[]};count=0
 try:
  checked=Q.checked_bundle(admission_ref,project);ids=checked['ids'];F.require(checked['objects']['plan']['external_custody_evidence_paths']==paths,'EXACT_QUALIFIED_PRIVATE_PATHS');F.put(marker,{'schema_version':1,'epoch':42,'kind':F.KIND,'phase':'dev','admission':admission_ref,'source_plan_sha256':checked['source_plan_sha256'],'semantic_decodes_so_far':0,'automatic_retry':False});report['evidence'].update(checked['references']);report['evidence']['vault']=vault_ref;report['label_reader_calls']=1
  # The following is the first possible vault-byte read, after ALL Q fences.
  b=F.read_ref(vault_ref);F.require(b.startswith(F.MAGIC),'EXACT_OPAQUE_VAULT_MAGIC');cursor=len(F.MAGIC)
  def sized():
   nonlocal cursor
   F.require(cursor+4<=len(b),'VAULT_LENGTH_HEADER');n=struct.unpack_from('<I',b,cursor)[0];cursor+=4;F.require(cursor+n<=len(b),'VAULT_TRUNCATED');v=b[cursor:cursor+n];cursor+=n;return v
  h=json.loads(sized(),object_pairs_hook=F.unique);F.require(h['schema_version']==1 and h['epoch']==42 and h['kind']==F.KIND and h['role']=='dev'and h['source_archive_sha256']==plan['data_archive_sha256']and h['ids']==ids and h['label_encoding']=='OPAQUE_RAW_JSON_STRING_TOKENS_NOT_DECODED'and h['official_codec_source_sha256']==CODEC_SHA,'EXACT_GOLD_VAULT_HEADER');labels={};hashes={}
  for i,cid in enumerate(ids):
   token=sized();F.put(out/f'progress-{i:02d}-before.json',{'schema_version':1,'epoch':42,'kind':F.KIND,'phase':'dev','case_id':cid,'previous_semantic_decodes':count,'token_sha256':F.sha(token),'decode_started':True,'decode_completed':False});report['decode_attempted_tokens']+=1;value=json.loads(token);count+=1;report['semantic_labels_decoded']=count;F.put(out/f'progress-{i:02d}-after.json',{'schema_version':1,'epoch':42,'kind':F.KIND,'phase':'dev','case_id':cid,'semantic_decodes_completed':count,'decode_completed':True,'supported_literal':type(value)is str and value in M.LABELS});F.require(type(value)is str and value in M.LABELS,'UNSUPPORTED_OFFICIAL_CHOICE_NO_REMAP');labels[cid]=value;hashes[cid]=F.sha(token)
  F.require(cursor==len(b)and count==len(labels)==12,'EXACT_TWELVE_JOINED_LABELS_NO_EXTRA_BYTES');joined={'schema_version':1,'epoch':42,'kind':F.KIND,'phase':'dev','source_plan_sha256':checked['source_plan_sha256'],'selected_ids':ids,'labels':labels,'label_token_sha256s':hashes,'semantic_labels_decoded':12,'label_reader_calls':1,'all_labels_decoded_after_forecasts_and_physical_closure':True,'source_archive_sha256':plan['data_archive_sha256'],'evidence':report['evidence'],'used_confirmation_identities':[]};report['joined_labels']=F.put(out/'joined_labels.json',joined);report['status']='GOLD_JOIN_COMPLETE_AFTER_PHYSICAL_CLOSURE'
 except Exception as e:
  report['errors'].append(safe_error(e));report['semantic_decode_count_uncertain']=len(list(out.glob('progress-*-before.json')))!=len(list(out.glob('progress-*-after.json')))
 report['semantic_labels_decoded']=count;F.put(out/'GOLD_JOIN_REPORT.json',report);return report

if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['project','admission','expected-admission-sha256','out']:p.add_argument('--'+n,required=True)
 a=p.parse_args();ap=Path(a.admission)if Path(a.admission).is_absolute()else Path(a.project)/a.admission;Q.public_reference({'path':str(ap)},a.project);r=F.ref(ap);F.require(r['sha256']==a.expected_admission_sha256,'EXACT_ROOT_ADMISSION_SHA');v=join_gold(r,a.project,a.out);print(json.dumps({'status':v['status'],'late_custodian_function_calls':v['late_custodian_function_calls'],'label_reader_calls':v['label_reader_calls'],'semantic_labels_decoded':v['semantic_labels_decoded'],'decode_attempted_tokens':v['decode_attempted_tokens'],'semantic_decode_count_uncertain':v['semantic_decode_count_uncertain'],'errors':v['errors']}))
