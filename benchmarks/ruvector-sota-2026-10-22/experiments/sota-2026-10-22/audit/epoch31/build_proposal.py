"""Epoch31 metadata-only proposal; never reads original annotated corpus/input text."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

OUT=Path('/tmp/ruvector-e31-independent-audit')
DONOR=Path('/tmp/ruvector-sota-2026-10-22/epoch30-9f13c9bb6e47')
ROOT=DONOR/'project'
PREFIX='experiments/sota-2026-10-22/'
HEAD='b27d0c39ed3102cd16ba616b1225b7684b76851b'
KIND='REAL_NATIVE_ARCHIVED_LEGAL_ADAPTATION_DIAGNOSTIC'
CP_SHA='9aa57320792550e9ee3255342dbc20254ba8057dc081cbf61d472c27b4551b88'
BASE_SHA='ce253627f98f9db22af6a86efee6e905f001f7d8dc02dd14a8b4b4710c302b17'
ARTIFACT_SHA='46bcb1c9bcf7a6bd9f7491f1233f38b65b1c3672de5370f4d1e1b5db24ae796f'

def identity(path):
    b=path.read_bytes()
    return {'path':str(path),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def put(name,value):
    p=OUT/name
    with p.open('x',encoding='utf-8')as f:
        f.write(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
    return identity(p)

cp_path=DONOR/'controls-final/CHECKPOINT_MANIFEST.json'
assert identity(cp_path)['sha256']==CP_SHA
cp=json.loads(cp_path.read_bytes());assert len(cp['project_files'])==4176
pins={r['path']:r for r in cp['project_files']};used={}

def verified(rel):
    path=ROOT/(PREFIX+rel);pin=pins[PREFIX+rel];got=identity(path)
    assert got['bytes']==pin['bytes']and got['sha256']==pin['sha256']
    used[pin['path']]=pin
    return json.loads(path.read_bytes()),pin

exposure,exposure_ref=verified('audit/epoch30/exposure-metadata.json')
ledger,ledger_ref=verified('epoch30/REJECTION_LEDGER.json')
res30,res30_ref=verified('epoch30/RESULTS.json')
res27,res27_ref=verified('epoch27/RESULTS.json')
incident,incident_ref=verified('epoch30/recovery/INCIDENT.json')
train_report,train_report_ref=verified('audit/epoch30/train-integrity.json')
train_identity,train_identity_ref=verified('audit/epoch30/data/train.input-identities.json')
dev_identity,dev_identity_ref=verified('audit/epoch30/data/dev.input-identities.json')
old_selection,old_selection_ref=verified('audit/epoch30/selection.json')
old_projection,old_projection_ref=verified('audit/epoch30/data/projection.json')
artifact_ref=pins[PREFIX+'epoch30/runs/train/trained-parameters.public.json']
got=identity(ROOT/artifact_ref['path'])
assert got['bytes']==artifact_ref['bytes']==5950520 and got['sha256']==artifact_ref['sha256']==ARTIFACT_SHA
used[artifact_ref['path']]=artifact_ref
assert res30['train_integrity_passed']is True and res30['actual_execution']['dev']['status']=='NOT_STARTED'
assert res30['annotation_choices_accessed']==0 and incident['model_checkpoint_was_published']is False
assert train_report['train_integrity_passed']is True

inherited_train=ledger['epoch30_data_roles']['train']
old16=set(ledger['epoch30_data_roles']['retired_document_ids'])
old=set(exposure['exposed_document_ids'])|old16
reserved=set(exposure['reserved_document_ids'])
eligible=sorted(set(exposure['eligible_document_ids'])-old16)
norm=exposure['catalog_selected_hashes']
blocked=set(exposure['blocked_normalized_document_sha256'])|{norm[str(i)]for i in old16}
cross={x['normalized_document_sha256']for x in exposure['cross_split_documents']}
assert(len(old),len(reserved),len(eligible))==(293,24,106)
assert len({norm[str(i)]for i in eligible})==106
assert not {norm[str(i)]for i in eligible}&(blocked|cross)
salt='epoch31-archived-e30-legal-lora-first-dev-v1|'+HEAD+'|'
ranked=sorted((hashlib.sha256((salt+str(i)).encode()).hexdigest(),i)for i in eligible)
dev=[i for _,i in ranked[:8]]
assert dev==[145,597,191,620,254,160,384,571]
roles={'train':[],'dev':dev,'calibration':[],'confirmation':[]}
hyps=['nda-17','nda-7','nda-3']

metadata_pins={r['project_path']:r for r in exposure['historical_metadata_source_pins']}
for pin in [exposure_ref,old_selection_ref,old_projection_ref,train_identity_ref,dev_identity_ref,ledger_ref]:
    metadata_pins[pin['path']]={'project_path':pin['path'],'bytes':pin['bytes'],'sha256':pin['sha256']}
for p in metadata_pins.values():
    got=identity(ROOT/p['project_path'])
    assert(got['bytes'],got['sha256'])==(p['bytes'],p['sha256'])
old_identities=exposure['old_identity_records']+train_identity['records']+dev_identity['records']
assert len(old_identities)==1182
updated_exposure={
    'schema_version':1,'epoch':31,'all_prior_roles_preserved':True,
    'exposed_document_ids':sorted(old),'reserved_document_ids':sorted(reserved),
    'eligible_document_ids':eligible,'blocked_normalized_document_sha256':sorted(blocked),
    'catalog_selected_hashes':{str(i):norm[str(i)]for i in eligible},
    'cross_split_documents':exposure['cross_split_documents'],'old_identity_records':old_identities,
    'historical_metadata_source_pins':[metadata_pins[k]for k in sorted(metadata_pins)],
    'historical_E30_TRAIN_document_ids':inherited_train,
    'historical_E30_DEV_document_ids_permanently_retired':ledger['epoch30_data_roles']['dev'],
    'source_checkpoint':{'bytes':identity(cp_path)['bytes'],'sha256':CP_SHA,'rows':4176},
    'annotation_choices_accessed':0,'source_evidence_lists_accessed':0,
    'old_or_reserved_text_fields_traversed_this_epoch':0,
    'unknown_foundation_and_fuzzy_overlap':True}
exposure_out=put('exposure-metadata.json',updated_exposure)
allocation={
    'schema_version':1,'epoch':31,'kind':KIND,'status':'FIXED_METADATA_ONLY_DEV_ROLES_BEFORE_RAW_INPUTS_OR_MODELS',
    'source_head_supplied_by_root':HEAD,'checkpoint':identity(cp_path),'roles':roles,'hypotheses':hyps,
    'historical_E30_TRAIN_document_ids':inherited_train,
    'historical_E30_DEV_document_ids_unchanged_and_excluded':ledger['epoch30_data_roles']['dev'],
    'fixed_archived_parameter_artifact':artifact_ref,
    'selection':{'salt':salt,'algorithm':'Ascending SHA256(UTF8(salt+decimalID)); first8 DEV from106 eligible canonical groups',
        'eligible_document_ids':eligible,'redraws':0,'records':[{'rank':i,'role':'dev','document_id':did,'draw_key':h,
        'normalized_document_sha256':norm[str(did)]}for i,(h,did)in enumerate(ranked[:8])]},
    'prior_exposed_document_ids_unchanged':sorted(old),'protected_document_ids_unchanged':sorted(reserved),
    'eligibility':{'all106_disjoint_prior293_protected24_crosssplit184':True,'selected8_distinct_canonical_groups':True,
                   'exposure_metadata':exposure_out},
    'partition_before':{'exposed':293,'unreserved':106,'reserved_confirmation':24,'total':423},
    'partition_after_any_fixed8_input_projection_or_failure':{'exposed':301,'unreserved':98,'reserved_confirmation':24,'total':423},
    'conservative_retirement':'All8 retire on any input-projection failure; no redraw, replacement or length/class filter',
    'raw_source_text_length_choice_evidence_or_classcount_accesses':0,
    'metadata_fields_traversed':['document IDs','canonical normalized hashes','prior role registries','input identity hashes','source lineage'],
    'metadata_fields_used_for_selection':['document IDs','normalized hashes','prior roles'],
    'foundation_text_fuzzy_and_semantic_overlap_unknown':True,'runtime_authorization':False}
allocation_ref=put('selection.json',allocation)

protocol={
    'schema_version':1,'epoch':31,'kind':KIND,'status':'FIXED_PROSPECTIVE_PROTOCOL_BEFORE_NEW_INPUTS_OR_MEASUREMENT',
    'allocation':allocation_ref,'roles':roles,'hypotheses':hyps,'historical_E30_TRAIN_document_ids':inherited_train,
    'hypothesis':'First DEV measurement of the one fixed archived E30 legal LoRA+existing-classifier state versus original2020 BART on identical native context, with adapted native versus lexical/positional controls; no retraining or model reselection.',
    'base_model':{'repository':'facebook/bart-large-mnli','revision':'d7645e127eaf1aefc7862fd59a17a5aa8558b8ce',
        'original_bin_bytes':1629486723,'original_bin_sha256':BASE_SHA,'raw_C_N_E_labels':['contradiction','not_mentioned','entailment'],
        'canonical_E_C_N_permutation':[2,0,1],'temperature':1,'device':'CPU','precision':'FP32','attention':'sdpa',
        'load':'Stock safe original weights_only load; original classifier, no reinitialization','new_pretrained_backbone':False},
    'archived_model':{'parameter_artifact':artifact_ref,'source_epoch':30,'source_plan':train_report['evidence']['plan'],
        'source_freeze':train_report['evidence']['freeze'],'source_TRAIN_raw':train_report['evidence']['raw'],
        'source_TRAIN_execution':train_report['evidence']['execution'],'source_TRAIN_integrity_report':train_report_ref,
        'source_final_result':res30_ref,'source_interruption_incident':incident_ref,'original_MODEL_phase_was_published':False,
        'reuse_rule':'Exact archived epoch30 codec and bytes; do not relabel tensors, refit, calibrate, repair or choose among artifacts.',
        'trained_tensors':12,'trainable_parameters':1085443,'historical_training_steps':24,
        'LoRA':'Last2decoder cross-attention q/v, rank4 alpha8 scale2 plus original pretrained dense/out classifier',
        'TRAIN_integrity':'Existing independent24-step/frozen511/B-gradient/BA evidence must be retained and byte-bound',
        'current_TRAIN_choices_or_updates':0},
    'development':{'document_ids':dev,'context':'Unchanged E30 source splitter/ANNdepth40/neighbor packing and true BARTpair<=512; no hidden truncation',
        'order':['Publish current SOURCE and archived-model lineage seal; actual Gitreadback admission before DEV input read',
                 'Build labelblind native/lexical/positional contexts',
                 '24 fresh original2020BART native-context forwards with original classifier, no LoRA learned state loaded',
                 'Decode/apply exact archived46bcb parameter bytes without optimization',
                 '72 adapted forwards:24native,24lexical,24positional'],
        'forwards':96,'original_forwards':24,'adapted_forwards':72,'model_initializations':1,
        'same_native_premise_and_tokenpair_original_adapted':True,'same_artifact_hash_all_adapted_views':True,
        'original_baseline':'Disabling LoRA with trained classifier is insufficient; fresh original classifier mandatory',
        'gold_join':'One frozen scorer join of24DEV choices only after all96finite outputs sealed and ownedworker/nativechild closed',
        'training_optimizer_calibration_or_fit_calls':0,'evidence_list_reads':0},
    'budgets':{'native_corpus_batches':1,'owned_workers':1,'CPU_affinity':[0,1],
        'seconds_including_init_BGE_native_artifact_IO_and_cleanup':600,'DEV_forwards':96,
        'native_document_indices':8,'native_queries':24,'paid_calls':0,'GPU_calls':0,'confirmation_calls':0,
        'full104_calls':0,'retries':0,'TRAIN_calls':0,'failure':'Retain complete/partial/UNKNOWN evidence, no retry/gold join on incomplete outputs'},
    'integrity_gates':['Current source/pins/archived lineage and actual admission exact before inputs/model activity',
        '24cases each originalANN plus adaptedANN/lexical/positional; same ANN premise and tokenpair original/adapted',
        'All96genuine finite CNE logits, unit-temperature full3softmax, pair<=512, exact artifact identity, no fits',
        'Exact source spans, compact source-vector evidence, CPU2<=600, persistent forbidden-network0 and process closure',
        'Only after full96closed, join DEV24choices once, TRAIN/CONF/otherchoices/evidence0'],
    'diagnostic_gates':{'all_required':True,'all_three_gold_classes_present':True,'adapted_ANN_at_least_one_correct_each_class':True,
        'adaptation':'AdaptedANN correct>=originalANN+2; Ccorrect>=originalANN Ccorrect+1; threewayNLL/Brier nonincrease',
        'retrieval':'AdaptedANN correct>=adaptedlexical+2 and>=adaptedpositional+2; threewayNLL/Brier nonincrease vsboth',
        'nonincrease_tolerance':1e-12,'missing_class':'NOT_EVALUABLE, no redraw','C_ceiling':'Retain strict gate even if original C already perfect',
        'does_not_open_confirmation_or_promotion':True},
    'metrics':{'typed_prediction':'First maximum nativeC,N,E order; canonicalE,C,N probabilities p2,p0,p1',
        'threeway_proper':'Mean sum(p-y)^2 and mean-ln(max(pgold,1e-12)); clippingcount/unclipped-finiteness disclosed, no renormalization',
        'softmax_replay_tolerance':1e-6,'binary_decision_check_only':'Yes=pE>0.5; exacthalfNo; No=pC+pN; no threshold fit',
        'sampling':'8documentgroups×3correlatedhypotheses; diagnostic only, no24-independent-sample or population superiority claim',
        'timing':'Pairtokenizer/tensorprep/model/softmax p50/p95; initialization/artifactverification/retrieval/wholephase separate',
        'resources':'CPUaffinity0,1; wholeworker wall/RSS and childHWM scopes; opaque native internals UNKNOWN'},
    'freeze_order':['Fix single archived artifact,8DEVmetadata,source/scorer/protocol before raw projection',
        'Root durable data reservation; exact input-only projection; alias failure HOLD/retire8, no redraw',
        'Freeze whole source/runtime/scorer and archived-model seal; actual published source readback admission',
        'One96forward DEVworker, immutable raw then physicalclosure and independent structure audit',
        'One frozen24choice join, canonicalRESULTS/bind/FINAL; close allslots'],
    'lineage':{'base_chronology':'Exact2020bin precedes ContractNLI2021 superviseddataset; foundation/fuzzy overlap and laterpublisherreselection unknown',
        'own_supervision':'Only archived E30TRAIN8×3 choices; new8DEV/protected24 hashes disjoint all historical293exposed groups',
        'source':'Koreeda and Manning(2021) ContractNLI CC-BY-4.0 revisioneced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
        'source_bytes':7608211,'source_sha256':'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5',
        'base_license':'Pinned fairseq/BART MIT pretrained-model grant; retain copyright and full corpus attribution/change notice',
        'isolation':'Full annotated source JSON parsed in RAM by later authorized projection/scorer; logical field isolation, never OS-enforced label secrecy',
        'uncertainty':['Actual MNLI run row hashes/calibration/selection logs unpublished','Foundation contract-text/fuzzy overlap unknown',
                       'Excerpt NotMentioned does not prove fullcontract legalabsence','Net LoRA+classifier effect, not exclusive LoRA attribution']},
    'reporting':{'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_SOTA_verified':False,'official_rank':None,
        'champion':'Native104/RRF10 unchanged','confirmation':[],'calibration':[],
        'full104':'Not rerun; no repetition of known16KiB/blocker, no champion-improvement claim',
        'prior_outcomes':'E29 LoRA allocation HOLD unchanged; E30TRAINpassed/DEVneverstarted and all16old IDs remain retired; E31 is a new authorized first evaluation on new cases'}}
protocol_ref=put('protocol-proposal.json',protocol)
review={
    'schema_version':1,'epoch':31,'kind':KIND,'at':datetime.now(timezone.utc).isoformat(),
    'status':'ADMISSIBLE_FIRST_FIXED_ARCHIVED_LEGAL_STATE_DEV_SOURCE_RUNTIME_ADMISSION_PENDING',
    'checks_passed':True,'hypothesis_admitted_in_principle':True,'runtime_authorized':False,
    'selection':allocation_ref,'protocol':protocol_ref,'checkpoint':identity(cp_path),'CP_rows':4176,
    'fresh_R31_restore_and_actual_source_Git_readback_required':True,
    'material_usefulness':'First measurement of one trained legal-attention/classifier state whose E30DEV never ran; no exposed-question grid, retry or retrospective model choice.',
    'limitations':'Same original2020 pretrained backbone, not discovery of a new stronger pretrained reader; no quality claim before outputs; no CONF/officialbenchmark/champion promotion.',
    'reviewed_outcomes':{'E1':next(x for x in ledger['rejections']if x['epoch']==1),
        'E2':next(x for x in ledger['rejections']if x['epoch']==2),'E27':ledger['epoch27_decision'],
        'E29':ledger['epoch29_decision'],'E30':ledger['epoch30_decision']},
    'eligibility':{'unused106_metadata_groups_prior293_reserved24_cross184_disjoint':True,'selected8_distinct':True,
                   'original_source_text_length_choice_evidence_classcounts_read':0,'remaining_after_projection':98,'protected24unchanged':True},
    'budget':{'priorE27whole_seconds':res27['actual_execution']['wall_seconds_including_init_cleanup'],
        'priorE27forwards':72,'DEV96_scaled_prior_whole_seconds':res27['actual_execution']['wall_seconds_including_init_cleanup']*96/72,
        'actual_archived_TRAIN_seconds':res30['actual_execution']['wall_seconds_including_init_cleanup'],
        'conclusion':'One96forwardCPU2/600worker plausibly feasible, not guaranteed; no length filter or preparatory model probe.'},
    'risks':['24historicalTRAINchoices may underfit/overfit; no candidate selection or retraining',
             'Native-only historical training may favor native retrieval; retrieval contrasts conditional on that training',
             'Gold-class presence and original C ceiling unknown; strict frozen gates may fail or be unevaluable',
             '8groups/24correlatedcases and unknown foundation/fuzzy overlap limit generalization',
             'This diagnostic does not remove full104-comparator/CONF-admission requirements'],
    'activity':{'source_corpus_parses':0,'input_text_length_choices_evidence_or_classcounts_read':0,
                'model_native_tokenizer_Torch_ORT_calls':0,'weight_or_parameter_payload_decodes':0,
                'downloads_Git_project_mutations_paid_GPU':0},
    'verified_source_metadata_refs':[used[k]for k in sorted(used)]}
review_ref=put('hypothesis-acceptance-review.json',review)
freeze_ref=put('proposal-source-freeze.json',{'schema_version':1,'epoch':31,'kind':KIND,
    'status':'FIXED_ARCHIVED_MODEL_METADATA_ALLOCATION_AND_SCIENCE_BEFORE_RAW_INPUTS',
    'files':[allocation_ref,exposure_out,protocol_ref,review_ref,identity(Path(__file__).resolve())],
    'source_checkpoint':identity(cp_path),'fresh_R31_and_concrete_source_runtime_freeze_required':True,
    'source_annotation_or_model_calls':0,'project_writes':0})
print(json.dumps({'selection':allocation_ref,'exposure':exposure_out,'protocol':protocol_ref,'review':review_ref,'freeze':freeze_ref,'DEV':dev,'kind':KIND},sort_keys=True))
