"""E34 metadata-only allocation. Never opens annotated source, input text or model code."""
from pathlib import Path
import hashlib,json,os

OUT=Path('/workspace/ruvector-e34-data-impl')
ROOT=Path('/workspace/ruvector-epoch34-047dbc740dc2/project')
PREFIX='experiments/sota-2026-10-22/'
HEAD='047dbc740dc2d4fdbdbad90ac167ebc64b31a49c'
CP_SHA='2f8babb3303401fc904d51e8806c87d9c9254fe8c2dfc19e22d6f3e58a5abe03'
SALT='epoch34-lexical-anchor-native-complement-dev-v1|'+HEAD+'|'

def identity(p):
 b=Path(p).read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def put(name,value):
 p=OUT/name
 with p.open('x',encoding='utf-8')as f:
  f.write(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 return identity(p)
cp_path=OUT/'CURRENT_CHECKPOINT_MANIFEST.json'
assert identity(cp_path)['sha256']==CP_SHA
cp=json.loads(cp_path.read_bytes());assert len(cp['project_files'])==4834
pins={r['path']:r for r in cp['project_files']};used={}
def verified(rel):
 p=ROOT/(PREFIX+rel);pin=pins[PREFIX+rel];got=identity(p)
 assert(got['bytes'],got['sha256'])==(pin['bytes'],pin['sha256'])
 used[pin['path']]=pin
 return json.loads(p.read_bytes()),pin
exposure,exposure_ref=verified('audit/epoch33/exposure-metadata.json')
selection33,selection33_ref=verified('audit/epoch33/selection.json')
ident33,ident33_ref=verified('audit/epoch33/data/dev.input-identities.json')
projection33,projection33_ref=verified('audit/epoch33/data/projection.json')
ledger,ledger_ref=verified('epoch33/REJECTION_LEDGER.json')
results33,results33_ref=verified('epoch33/RESULTS.json')
assert ledger['epoch33_decision']['status']=='REJECTED_DEV_DIAGNOSTIC'
assert results33['diagnostic_qualified']is False and results33['status']=='REJECTED_DEV_DIAGNOSTIC'
old33=selection33['roles']['dev'];assert old33==[91,427,299,439,513,268,583,402]
old=set(exposure['exposed_document_ids'])|set(old33)
reserved=set(exposure['reserved_document_ids'])
eligible=sorted(set(exposure['eligible_document_ids'])-set(old33))
norm=exposure['catalog_selected_hashes']
blocked=set(exposure['blocked_normalized_document_sha256'])|{norm[str(i)]for i in old33}
cross={x['normalized_document_sha256']for x in exposure['cross_split_documents']}
assert(len(old),len(reserved),len(eligible),len(exposure['cross_split_documents']))==(317,24,82,184)
assert not old&reserved and not set(eligible)&(old|reserved)
assert len({norm[str(i)]for i in eligible})==82
assert not{norm[str(i)]for i in eligible}&(blocked|cross)
ranked=sorted((hashlib.sha256((SALT+str(i)).encode()).hexdigest(),i)for i in eligible)
dev=[i for _,i in ranked[:8]]
roles={'train':[],'dev':dev,'calibration':[],'confirmation':[]};hyps=['nda-17','nda-7','nda-3']
metadata_pins={p['project_path']:p for p in exposure['historical_metadata_source_pins']}
for pin in [exposure_ref,selection33_ref,ident33_ref,projection33_ref,ledger_ref]:
 metadata_pins[pin['path']]={'project_path':pin['path'],'bytes':pin['bytes'],'sha256':pin['sha256']}
for pin in metadata_pins.values():
 got=identity(ROOT/pin['project_path']);assert(got['bytes'],got['sha256'])==(pin['bytes'],pin['sha256'])
old_ids=exposure['old_identity_records']+ident33['records'];assert len(old_ids)==1254
exposure_out=put('exposure-metadata.json',{'schema_version':1,'epoch':34,'all_prior_roles_preserved':True,'exposed_document_ids':sorted(old),'reserved_document_ids':sorted(reserved),'eligible_document_ids':eligible,'blocked_normalized_document_sha256':sorted(blocked),'catalog_selected_hashes':{str(i):norm[str(i)]for i in eligible},'cross_split_documents':exposure['cross_split_documents'],'old_identity_records':old_ids,'historical_metadata_source_pins':[metadata_pins[k]for k in sorted(metadata_pins)],'source_checkpoint':{'rows':4834,'bytes':identity(cp_path)['bytes'],'sha256':CP_SHA},'historical_E33_DEV_document_ids_permanently_retired':old33,'E33_DEV_completed_and_labels_exposed_retired_forever':True,'annotation_choices_accessed':0,'source_evidence_lists_accessed':0,'old_or_reserved_text_fields_traversed_this_epoch':0,'unknown_foundation_and_fuzzy_overlap':True})
allocation={'schema_version':1,'epoch':34,'status':'FIXED_METADATA_ONLY_DEV_ROLES_BEFORE_RAW_INPUTS_OR_MODELS','source_head_supplied_by_root':HEAD,'checkpoint':identity(cp_path),'roles':roles,'hypotheses':hyps,'selection':{'salt':SALT,'algorithm':'Ascending SHA256(UTF8(salt+decimalID)); first8 DEV from82 eligible canonical groups','eligible_document_ids':eligible,'redraws':0,'records':[{'rank':i,'role':'dev','document_id':did,'draw_key':h,'normalized_document_sha256':norm[str(did)]}for i,(h,did)in enumerate(ranked[:8])]},'prior_exposed_document_ids_unchanged':sorted(old),'protected_document_ids_unchanged':sorted(reserved),'eligibility':{'all82_disjoint_prior317_protected24_crosssplit184':True,'selected8_distinct_canonical_groups':True,'exposure_metadata':exposure_out},'partition_before':{'exposed':317,'unreserved':82,'reserved_confirmation':24,'total':423},'partition_after_any_fixed8_input_projection_or_failure':{'exposed':325,'unreserved':74,'reserved_confirmation':24,'total':423},'conservative_retirement':'All8 retire on any input-projection, engineering, runtime or diagnostic failure; no redraw, replacement or length/class filter','raw_source_text_length_choice_evidence_or_classcount_accesses':0,'metadata_fields_traversed':['document IDs','canonical normalized hashes','prior role registries','input identity hashes','source lineage'],'metadata_fields_used_for_selection':['document IDs','normalized hashes','prior roles'],'foundation_text_fuzzy_and_semantic_overlap_unknown':True,'runtime_authorization':False}
allocation_ref=put('selection.json',allocation)
freeze_ref=put('metadata-allocation-freeze.json',{'schema_version':1,'epoch':34,'status':'METADATA_ALLOCATION_ONLY_CANDIDATE_PROTOCOL_PENDING','files':[allocation_ref,exposure_out,identity(Path(__file__).resolve())],'source_checkpoint':identity(cp_path),'verified_source_metadata_refs':[used[k]for k in sorted(used)],'current_DEV_source_projection_authorized':False,'current_DEV_input_or_annotation_body_reads':0,'model_native_tokenizer_calls':0,'confirmation':[]})
print(json.dumps({'DEV':dev,'roles':roles,'hypotheses':hyps,'selection':allocation_ref,'metadata_freeze':freeze_ref,'exposure':exposure_out,'prior_E33_status':results33['status']},sort_keys=True))
