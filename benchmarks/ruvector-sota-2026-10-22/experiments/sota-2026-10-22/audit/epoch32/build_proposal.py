"""Epoch32 metadata-only allocation; no annotated corpus, input bodies or model code."""
from pathlib import Path
import hashlib,json

OUT=Path('/workspace/ruvector-e32-data-impl')
DONOR=Path('/tmp/ruvector-sota-2026-10-22/epoch31-de468eba3faa')
ROOT=DONOR/'project'
PREFIX='experiments/sota-2026-10-22/'
HEAD='f8bcbc4ca7ec31c6732159cad60a6e223f93c539'
CP_SHA='8662d03427f700179d3684f6afed91eb0f3e5c0fcf5a703178b1e20a325cc339'
KIND='REAL_NATIVE_TASKSOURCE_PRETRAINED_NLI_DIAGNOSTIC'

def identity(p):
 b=Path(p).read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def put(name,value):
 p=OUT/name
 with p.open('x',encoding='utf-8')as f:f.write(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
 return identity(p)
cp_path=DONOR/'controls-final/CHECKPOINT_MANIFEST.json'
assert identity(cp_path)['sha256']==CP_SHA
cp=json.loads(cp_path.read_bytes());assert len(cp['project_files'])==4350
pins={r['path']:r for r in cp['project_files']};used={}
def verified(rel):
 p=ROOT/(PREFIX+rel);pin=pins[PREFIX+rel];got=identity(p)
 assert(got['bytes'],got['sha256'])==(pin['bytes'],pin['sha256'])
 used[pin['path']]=pin
 return json.loads(p.read_bytes()),pin
exposure,exposure_ref=verified('audit/epoch31/exposure-metadata.json')
selection31,selection31_ref=verified('audit/epoch31/selection.json')
ident31,ident31_ref=verified('audit/epoch31/data/dev.input-identities.json')
projection31,projection31_ref=verified('audit/epoch31/data/projection.json')
ledger,ledger_ref=verified('epoch31/REJECTION_LEDGER.json')
results31,results31_ref=verified('epoch31/RESULTS.json')
assert ledger['epoch31_decision']['status']=='REJECTED_DEV_DIAGNOSTIC'
assert results31['diagnostic_qualified']is False
old31=selection31['roles']['dev'];assert old31==[145,597,191,620,254,160,384,571]
old=set(exposure['exposed_document_ids'])|set(old31)
reserved=set(exposure['reserved_document_ids'])
eligible=sorted(set(exposure['eligible_document_ids'])-set(old31))
norm=exposure['catalog_selected_hashes']
blocked=set(exposure['blocked_normalized_document_sha256'])|{norm[str(i)]for i in old31}
cross={x['normalized_document_sha256']for x in exposure['cross_split_documents']}
assert(len(old),len(reserved),len(eligible),len(exposure['cross_split_documents']))==(301,24,98,184)
assert len({norm[str(i)]for i in eligible})==98
assert not{norm[str(i)]for i in eligible}&(blocked|cross)
salt='epoch32-tasksource-pretrained-nli-first-dev-v1|'+HEAD+'|'
ranked=sorted((hashlib.sha256((salt+str(i)).encode()).hexdigest(),i)for i in eligible)
dev=[i for _,i in ranked[:8]];assert dev==[557,184,34,404,578,246,242,448]
roles={'train':[],'dev':dev,'calibration':[],'confirmation':[]};hyps=['nda-17','nda-7','nda-3']
metadata_pins={p['project_path']:p for p in exposure['historical_metadata_source_pins']}
for pin in [exposure_ref,selection31_ref,ident31_ref,projection31_ref,ledger_ref]:metadata_pins[pin['path']]={'project_path':pin['path'],'bytes':pin['bytes'],'sha256':pin['sha256']}
for pin in metadata_pins.values():
 got=identity(ROOT/pin['project_path']);assert(got['bytes'],got['sha256'])==(pin['bytes'],pin['sha256'])
old_ids=exposure['old_identity_records']+ident31['records'];assert len(old_ids)==1206
exposure_out=put('exposure-metadata.json',{'schema_version':1,'epoch':32,'all_prior_roles_preserved':True,'exposed_document_ids':sorted(old),'reserved_document_ids':sorted(reserved),'eligible_document_ids':eligible,'blocked_normalized_document_sha256':sorted(blocked),'catalog_selected_hashes':{str(i):norm[str(i)]for i in eligible},'cross_split_documents':exposure['cross_split_documents'],'old_identity_records':old_ids,'historical_metadata_source_pins':[metadata_pins[k]for k in sorted(metadata_pins)],'source_checkpoint':{'rows':4350,'bytes':identity(cp_path)['bytes'],'sha256':CP_SHA},'historical_E31_DEV_document_ids_permanently_retired':old31,'annotation_choices_accessed':0,'source_evidence_lists_accessed':0,'old_or_reserved_text_fields_traversed_this_epoch':0,'unknown_foundation_and_fuzzy_overlap':True})
allocation={'schema_version':1,'epoch':32,'kind':KIND,'status':'FIXED_METADATA_ONLY_DEV_ROLES_BEFORE_RAW_INPUTS_OR_MODELS','source_head_supplied_by_root':HEAD,'checkpoint':identity(cp_path),'roles':roles,'hypotheses':hyps,'selection':{'salt':salt,'algorithm':'Ascending SHA256(UTF8(salt+decimalID)); first8 DEV from98 eligible canonical groups','eligible_document_ids':eligible,'redraws':0,'records':[{'rank':i,'role':'dev','document_id':did,'draw_key':h,'normalized_document_sha256':norm[str(did)]}for i,(h,did)in enumerate(ranked[:8])]},'prior_exposed_document_ids_unchanged':sorted(old),'protected_document_ids_unchanged':sorted(reserved),'eligibility':{'all98_disjoint_prior301_protected24_crosssplit184':True,'selected8_distinct_canonical_groups':True,'exposure_metadata':exposure_out},'partition_before':{'exposed':301,'unreserved':98,'reserved_confirmation':24,'total':423},'partition_after_any_fixed8_input_projection_or_failure':{'exposed':309,'unreserved':90,'reserved_confirmation':24,'total':423},'conservative_retirement':'All8 retire on any input-projection, engineering, runtime or diagnostic failure; no redraw, replacement or length/class filter','raw_source_text_length_choice_evidence_or_classcount_accesses':0,'metadata_fields_traversed':['document IDs','canonical normalized hashes','prior role registries','input identity hashes','source lineage'],'metadata_fields_used_for_selection':['document IDs','normalized hashes','prior roles'],'foundation_text_fuzzy_and_semantic_overlap_unknown':True,'runtime_authorization':False}
allocation_ref=put('selection.json',allocation)
report=Path('/workspace/ruvector-e32-reader-impl/METADATA_ADMISSION.json');assert identity(report)['sha256']=='978b7e07c64b28c456a00a11c2ff5c278721f3f270de26be0e12701883b38669'
review={'schema_version':1,'epoch':32,'kind':KIND,'checks_passed':True,'status':'ADMISSIBLE_NEW_PRETRAINED_READER_DEV_DIAGNOSTIC_SOURCE_RUNTIME_ADMISSION_PENDING','runtime_authorized':False,'allocation':allocation_ref,'checkpoint':identity(cp_path),'model_metadata':identity(report),'material_hypothesis':'One genuinely new shared pretrained three-way Tasksource DeBERTa-v3-large head, evaluated without fitting or calibration on fresh source-frozen original legal documents. No repeated BART/adapter/threshold grid. Authored engineering checks are a first-stage correctness gate, not a generalization benchmark.','prior_E31_outcome':{'status':results31['status'],'diagnostic_qualified':False,'results':results31_ref,'decision':ledger['epoch31_decision']},'lineage_limits':['Apache2 model declaration retained; mixed upstream dataset terms not independently converted to a legal benchmark eligibility guarantee.','Reported600/514/200task training counts and exact train/dev/selection/calibration records are incomplete. Literal absence of ContractNLI from a published task list does not prove exclusion.','Foundation text, fuzzy overlap and record-level supervised overlap remain UNKNOWN; confirmation, promotion and official benchmark admission remain HOLD.'],'scope_limits':{'current_train':[],'calibration':[],'confirmation':[],'fit_or_calibration_calls':0,'full104_attempts':0,'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_SOTA_verified':False,'official_rank':None},'design':{'one_predeclared_CPU2_600s_worker':True,'engineering_authored_cases':6,'engineering_forwards':18,'conditional_real_DEV_cases':24,'conditional_real_DEV_forwards':72,'maximum_NLI_forwards':90,'no_engineering_or_DEV_retry':True,'engineering_failure':'Stop before current DEV input read or inference; DEV metrics null and DEV choices0; all8 identities remain retired.','gold_timing':'Current original source24choices only after complete90 finite predictions, successful frozen engineering gate, immutable raw and independently established physical closure.'},'statistical_limit':'8 document clusters ×3 correlated hypotheses; no24-independent-sample or population superiority claim.','selection_activity':{'annotated_source_parses':0,'raw_input_text_length_sourcechoice_evidence_classcount_accesses':0,'model_tokenizer_native_Torch_ORT_calls':0,'weight_or_parameter_payload_decodes':0,'downloads_Git_project_mutations_paid_GPU':0},'verified_source_metadata_refs':[used[k]for k in sorted(used)]}
review_ref=put('hypothesis-acceptance-review.json',review)
freeze_ref=put('proposal-source-freeze.json',{'schema_version':1,'epoch':32,'kind':KIND,'status':'FIXED_NEW_PRETRAINED_MODEL_METADATA_ALLOCATION_BEFORE_RAW_INPUTS','files':[allocation_ref,exposure_out,review_ref,identity(Path(__file__).resolve())],'source_checkpoint':identity(cp_path),'fresh_R32_and_concrete_source_runtime_freeze_required':True,'source_annotation_or_model_calls':0,'project_writes':0})
print(json.dumps({'DEV':dev,'selection':allocation_ref,'review':review_ref,'proposal_freeze':freeze_ref,'exposure':exposure_out},sort_keys=True))
