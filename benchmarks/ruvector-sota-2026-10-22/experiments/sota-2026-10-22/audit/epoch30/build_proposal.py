"""Freeze E30 metadata-only roles and prospective scientific requirements.

Reads pre-existing source/metadata only. Never opens the original annotated corpus.
No ML/native imports, execution, downloads or project writes.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

OUT = Path('/tmp/ruvector-e30-independent-audit')
DONOR = Path('/tmp/ruvector-sota-2026-10-22/epoch29-734329c6e9e6')
P = DONOR/'project/experiments/sota-2026-10-22'
HEAD = 'ccd765026806aa3d7e43e295238a741c874a46b8'
KIND = 'REAL_NATIVE_LEGAL_PARAMETER_ADAPTATION_DIAGNOSTIC'
BASE_SHA = 'ce253627f98f9db22af6a86efee6e905f001f7d8dc02dd14a8b4b4710c302b17'

def identity(path):
    raw = path.read_bytes()
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def put(name, value):
    path = OUT/name
    with path.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
    return identity(path)

cp_path = DONOR/'controls-final/CHECKPOINT_MANIFEST.json'
assert identity(cp_path)['sha256'] == '62542c0148abc331dc006c2291851253c9d7da66ec9f870e97d7e055a24b37dd'
cp = json.loads(cp_path.read_bytes())
assert len(cp['project_files']) == 4032
pins = {r['path']:r for r in cp['project_files']}
rels = ['epoch27/RESULTS.json','audit/epoch29/data-projection-hold.json',
        'audit/epoch29/identity/data/canonical-catalog.json','audit/epoch29/identity/protocol.json',
        'audit/epoch29/exposure-metadata.json','epoch29/RESULTS.json',
        'audit/epoch29/identity/independent-acceptance.json','candidate/epoch8/models.py',
        'candidate/epoch8/head.py','candidate/epoch10/models.py','candidate/epoch10/head.py',
        'candidate/epoch27/reader/reader-admission.json','candidate/epoch27/MODEL_ASSETS.json',
        'epoch29/REJECTION_LEDGER.json']
verified = []
for rel in rels:
    got = identity(P/rel)
    pin = pins['experiments/sota-2026-10-22/'+rel]
    assert got['bytes']==pin['bytes'] and got['sha256']==pin['sha256']
    verified.append({**got,'checkpoint_match':True})

catalog = json.loads((P/'audit/epoch29/identity/data/canonical-catalog.json').read_bytes())
prior = json.loads((P/'audit/epoch29/identity/protocol.json').read_bytes())
exposure = json.loads((P/'audit/epoch29/exposure-metadata.json').read_bytes())
# Length fields exist in the parsed old metadata but are never traversed here.
norm = {r['document_id']:r['normalized_document_sha256'] for r in catalog['records']}
old = set(prior['old_exposed_index_document_ids_before_protection']) | set(prior['retired_LoRA_fixed_document_ids'])
reserved = set(prior['protected_document_ids'])
unused = set(prior['remaining_unreserved_document_ids'])
blocked = {norm[i] for i in old|reserved}
cross = {r['normalized_document_sha256'] for r in exposure['cross_split_documents']}
eligible = sorted(i for i in unused if norm[i] not in blocked|cross)
assert (len(old),len(reserved),len(unused),len(eligible)) == (277,24,122,122)
salt = 'epoch30-bart-crossattn-r4-oneepoch-train-dev-v1|'+HEAD+'|'
ranked = sorted((hashlib.sha256((salt+str(i)).encode()).hexdigest(),i) for i in eligible)
train = [i for _,i in ranked[:8]]
dev = [i for _,i in ranked[8:16]]
assert train == [237,120,187,422,464,207,294,250]
assert dev == [594,343,394,103,403,481,154,306]
assert len({norm[i] for i in train+dev}) == 16
roles = {'train':train,'dev':dev,'calibration':[],'confirmation':[]}
hypotheses = ['nda-17','nda-7','nda-3']
allocation = {
    'schema_version':1,'epoch':30,'kind':KIND,
    'status':'FIXED_METADATA_ONLY_ROLES_BEFORE_RAW_INPUTS_OR_MODELS',
    'source_head_supplied_by_root':HEAD,'checkpoint':identity(cp_path),
    'roles':roles,'hypotheses':hypotheses,
    'selection':{'salt':salt,'algorithm':'Ascending SHA256(UTF8(salt+decimalID)); first8 TRAIN,next8 DEV',
                 'eligible_document_ids':eligible,'redraws':0,
                 'records':[{'rank':j,'role':'train' if j<8 else 'dev','document_id':i,
                             'draw_key':h,'normalized_document_sha256':norm[i]}
                            for j,(h,i) in enumerate(ranked[:16])]},
    'prior_exposed_document_ids_unchanged':sorted(old),
    'protected_document_ids_unchanged':sorted(reserved),
    'eligibility':{'all122_hashes_disjoint_prior277_protected24':True,
                   'all122_hashes_disjoint184crosssplit':True,
                   'selected16_distinct_canonical_groups':True,
                   'catalog':identity(P/'audit/epoch29/identity/data/canonical-catalog.json'),
                   'crosssplit_metadata':identity(P/'audit/epoch29/exposure-metadata.json')},
    'partition_before':{'exposed':277,'unreserved':122,'reserved_confirmation':24,'total':423},
    'partition_after_any_fixed16_input_projection_or_failure':
        {'exposed':293,'unreserved':106,'reserved_confirmation':24,'total':423},
    'conservative_retirement':'All16 fixed IDs retire on any input-projection failure; no redraw, replacement or length filter',
    'raw_source_text_length_choice_evidence_or_classcount_accesses':0,
    'metadata_fields_traversed':['document_id','normalized_document_sha256','prior role/ID registries','crosssplit hashes'],
    'metadata_source_utf8_bytes_fields_used':False,
    'foundation_text_fuzzy_and_semantic_overlap_unknown':True,
    'runtime_authorization':False}
allocation_ref = put('selection.json',allocation)

protocol = {'schema_version':1,'epoch':30,'kind':KIND,
            'status':'FIXED_PROSPECTIVE_PROTOCOL_BEFORE_RAW_INPUTS_TRAINING_INFERENCE',
            'allocation':allocation_ref,'roles':roles,'hypotheses':hypotheses}
protocol['hypothesis'] = (
    'One fixed legal LoRA+existing-classifier adaptation of original2020BART improves typed '
    'contradiction decisions versus the original model on identical native context; the adapted '
    'reader also compares native versus matched lexical/positional contexts. Net parameter '
    'adaptation is tested, not exclusive causal attribution to LoRA.')
protocol['base_model'] = {
    'repository':'facebook/bart-large-mnli','revision':'d7645e127eaf1aefc7862fd59a17a5aa8558b8ce',
    'original_bin_bytes':1629486723,'original_bin_sha256':BASE_SHA,
    'raw_C_N_E_labels':['contradiction','not_mentioned','entailment'],
    'canonical_E_C_N_permutation':[2,0,1],'temperature':1,'device':'CPU','precision':'FP32',
    'load':'Original stock safe weights_only load; exact used tensors/head; no reinitialization',
    'generation':False}
protocol['training'] = {
    'document_ids':train,'context':'NativeANN evidence only; labelblind frozen E27 source splitter/ranking/packing',
    'modules_exact':['model.decoder.layers.10.encoder_attn.q_proj','model.decoder.layers.10.encoder_attn.v_proj',
                     'model.decoder.layers.11.encoder_attn.q_proj','model.decoder.layers.11.encoder_attn.v_proj'],
    'LoRA':{'rank':4,'alpha':8,'scale':2,'dropout':0,'seed':30030,
            'initialization':'Immediately before injection reset global seed30030; dedicated CPU generator30030; moduleorder10q,10v,11q,11v; A[4,1024]uniform[-1/32,1/32],B[1024,4]zero'},
    'pretrained_trainable_head':['classification_head.dense.weight','classification_head.dense.bias',
                                'classification_head.out_proj.weight','classification_head.out_proj.bias'],
    'all_other_base_parameters_frozen':True,'trainable_tensors':12,
    'trainable_parameters':1085443,'LoRA_parameters':32768,'pretrained_head_parameters':1052675,
    'mode':'model.eval() with gradient enabled; all dropout off; no inference_mode during TRAIN',
    'optimizer':{'name':'AdamW','learning_rate':1e-4,'weight_decay':0.01,'betas':[0.9,0.999],
                 'epsilon':1e-8,'global_gradient_clip_norm':1.0,'trainable_parameters_only':True},
    'objective':'Unweighted three-way cross entropy, batch1, equal cases; no class weights/balancing',
    'epochs':1,'batch_size':1,'order':'Fixed selected doc order ×nda-17,nda-7,nda-3, once; no shuffle',
    'forward_calls':24,'backward_calls':24,'optimizer_steps':24,'extra_validation_forwards':0,
    'early_stop_bestcheckpoint_hypergrid_thresholdfit_calibration_retry':False,
    'TRAIN_choice_reads':24,'all_other_choice_or_evidence_reads':0,
    'class_counts':'Unknown until worker joins exactTRAIN24; disclose, no redraw/tuning; missingC is not C-labelled supervision'}
protocol['development'] = {
    'document_ids':dev,'context':'Frozen E27 splitter/ANNdepth40/neighbor-packing; true nativeBART pair<=512tokens; no hidden truncation',
    'order':['MODEL actualGitreadback admission before DEVinput-file read',
             'Build all labelblind native/lexical/positional contexts',
             '24 original2020BART native-context forwards, original classifier and LoRA disabled',
             'Load exact sealed factor+head artifact without training',
             '72 adapted forwards:24 native,24 lexical,24 positional'],
    'forwards':96,'original_forwards':24,'adapted_forwards':72,'model_initializations':1,
    'same_native_premise_and_tokenpair_original_adapted':True,'same_artifact_hash_all_adapted_views':True,
    'original_baseline':'Disabling LoRA with the trained head is insufficient; original classifier tensors mandatory',
    'optimizer_steps_or_fits':0,'gold_join':'Frozen independentSCORE only after all96sealed finite outputs and physicalclosure;24choicesonce',
    'evidence_list_reads':0}
protocol['model_seal'] = {
    'format':'Custom JSON12 tensor blocks, exact float32le/base64; no pickle/baseweights',
    'raw_parameter_bytes':4341772,
    'fields':['schema_version=1','epoch=30','kind','status=TRAINED_PARAMETER_ARTIFACT_SEALED',
              'base_model_sha256','parameter_artifact/ref3','train_raw/ref3','train_execution/ref3',
              'independent_training_report/ref3','source_plan/ref3','source_freeze/ref3'],
    'independent_training_report':'train_integrity_passed true; evidence.artifact/raw/execution/plan/freeze',
    'SOURCE_ADMISSION':'ActualSOURCE Gitreadback before TRAIN',
    'MODEL_ADMISSION':'Separate actualMODELcommit+sourcecommit+sameplan/freeze+sourceadmission+seal/artifact+owner before DEVinput read'}
protocol['freeze_order'] = [
    'Fix these roles/hypothesis/init/optimizer/metrics/gates before raw text, labels or model activity',
    'Root freshR30 restoration; freeze concrete builder/inputauditor/scorer/runtime/model sources before projection',
    'Project exact16 unlabelled document/hypothesis pairs; verify catalog hashes and all aliases; failure retires16/no redraw',
    'SOURCE actualGit admission; one TRAIN24choice/24update worker; close ownedgroup and independent train integrity audit',
    'Seal artifact/receipts; MODEL publication+actualGitreadback; then one DEV96forward worker',
    'Complete96outputs+rawaudit+physicalclosure before frozenSCORE exactDEV24choicejoin; finalpublication; closeallslots']
protocol['budgets'] = {
    'native_corpus_batches':2,'phases':['train','dev'],'CPU_affinity':[0,1],
    'seconds_each_including_init_BGE_native_optimization_IO_and_cleanup':600,
    'TRAIN_forward_backward_optimizer_steps':24,'DEV_forwards':96,'total_NLI_forwards':120,
    'native_document_indices_each_phase':8,'native_queries_each_phase':24,
    'dynamic_tokenizer_BGE_work':'Frozen source algorithms/caps; actualcounts recorded; no preparatory modelprobe',
    'paid_calls':0,'GPU_calls':0,'confirmation_calls':0,'full104_calls':0,'retries':0,
    'TRAIN_failure':'Retain honest complete/partial evidence; no partial-modelDEV; permanently closeDEVslot'}
protocol['TRAIN_integrity_gates'] = [
    'Exact24 authorised TRAIN choices,0DEV/CONF/otherchoices/evidence reads',
    'Exact24 finite forward/backward/AdamW updates, fixed objective/order/clipping; no train-quality checkpoint choice',
    'Exact12 learned tensor names/shapes/dtypes; nonzero effective LoRA delta and changed classifier; allother pretrained parameterbytes unchanged',
    'All source/runtime/CPU/network/budget checks; TRAIN physicallyclosed; artifact+receipt MODEL actualGitreadback beforeDEV']
protocol['DEV_integrity_gates'] = [
    'Exact24 cases with originalANN and adaptedANN/lexical/positional results; same original/adapted ANN context and pair tokens',
    'All96 finite genuine forwards, fixed learned-state identity, all3logit unit-temperature softmax replay and nativepair<=512',
    'Exact source spans/native vector evidence/pins/CPU2<=600 and allownedprocesses closed; no unexpectederrors before goldjoin',
    'DEV24choicesonce after seal; no TRAINchoice reread by scorer, no otherrolechoices or evidence lists']
protocol['diagnostic_gates'] = {
    'all_required':True,'all_three_gold_classes_present':True,'adapted_ANN_at_least_one_correct_each_class':True,
    'adaptation':'AdaptedANN correct>=originalANN+2; adaptedANN Ccorrect>=originalANN Ccorrect+1; threewayNLL/Brier nonincrease',
    'retrieval':'AdaptedANN correct>=adaptedlexical+2 and>=adaptedpositional+2; threewayNLL/Brier nonincrease vsboth',
    'nonincrease_tolerance':1e-12,'missing_class':'NOT_EVALUABLE, no redraw',
    'C_ceiling':'Strict Cgain may be impossible if original already perfect on newCcases; retain the frozen result, no expost relaxation',
    'does_not_open_confirmation_or_promotion':True}
protocol['metrics'] = {
    'typed_prediction':'First maximum in nativeC,N,E index order; reportE,C,N probabilities p2,p0,p1',
    'threeway_proper':'Mean sum(p-y)^2; mean-ln(max(pgold,1e-12)), disclose clipping and unclipped-finiteness; no renormalization',
    'softmax_replay_tolerance':1e-6,
    'binary_optional':'Yes=pE,No=pC+pN; Yes onlypE>0.5; exacthalfNo; optional uncalibratedforecast metrics separately, no tuning',
    'sampling':'8DEVdocumentgroups with3correlatedhypotheses; no24-independent-sample or population superiority claim',
    'timing':'Pair tokenizer/tensorprep/model/softmax scope; init/retrieval/train/wholephase separately; p50/p95linearinterpolation',
    'resources':'Actual perphase receipts; workerRSS versus largest-childhighwater scope; observed affinitiesCPU0,1; opaque internals UNKNOWN'}
protocol['lineage'] = {
    'base':'Exactce253 originalbin published2020-02-12 before ContractNLI2021; original training/release selection excludes later labelleddataset',
    'own_supervision':'Only exactTRAIN8×3 choices; canonical disjointness excludes DEV8 and protected24 from new supervision/calibration/selection',
    'dataset':'Koreeda and Manning(2021) ContractNLI CC BY4.0; revisioneced6528dd3c1d14d73f9a87df8f7bdbc03126f9',
    'source_bytes':7608211,'source_sha256':'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5',
    'base_license':'PinnedBART/fairseq pretrained-model MIT grant; corpus-text terms distinct; retain attribution/licence/change notice',
    'uncertainty':['Foundation contract-text/fuzzy overlap unknown','Later publisher reselection of unchanged2020weights notproved absent',
                   'Actual MNLI row hashes/selection/calibration logs unpublished; official recipe only suppliesdefaults',
                   'Fullcontract gold may not be supported by retrievedexcerpt; NotMentioned is not proof of legalabsence']}
protocol['reporting'] = {
    'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_rank':None,
    'official_SOTA_verified':False,'champion':'Native104/RRF10 unchanged','confirmation':[],'calibration':[],
    'full104':'Not run; no repeated16KiB/fullinput blocker; nochampion-improvement claim',
    'E29_HOLD':'Unchanged; all16 retired; this is a new authorised epoch, not repair/replacement of that allocation'}
protocol_ref = put('protocol-proposal.json',protocol)

res27 = json.loads((P/'epoch27/RESULTS.json').read_bytes())
p95 = max(x['p95_seconds'] for x in res27['reader_pair_latency'].values())
review = {
    'schema_version':1,'epoch':30,'kind':KIND,'at':datetime.now(timezone.utc).isoformat(),
    'status':'CONDITIONALLY_ADMISSIBLE_METADATA_ROLES_AND_HYPOTHESIS_SOURCE_RUNTIME_ADMISSION_PENDING',
    'checks_passed':True,'hypothesis_admitted_in_principle':True,'runtime_authorized':False,
    'selection':allocation_ref,'protocol':protocol_ref,
    'source':{'actualhead_supplied_by_root':HEAD,'checkpoint':identity(cp_path),'CP_rows':4032,
              'source_metadata_files_verified':len(verified),'freshR30restoration_and_actualGit_admission_required':True},
    'novelty':{'E8_E10':'Verified residual heads over frozen pretrained backbones, not attention parameter updates',
               'E27':'ActualoriginalBART native15/24,lexical12,positional14,C0/4; no reused cases',
               'E29':'SameLoRA idea nevertrained: strict548→515 dataHOLD, all16retired; E30 continues an unexecuted hypothesis',
               'claim_scope':'Net LoRA+classifier adaptation, not all400M weights trained or exclusive LoRA causality; head1,052,675parameters dominates32,768LoRA'},
    'eligibility':{'unused122_metadata_hashes_prior277_reserved24_crosssplit184_disjoint':True,
                   'selected16_distinct':True,'raw_text_lengths_choices_evidence_classcounts_accessed':0,
                   'remaining_pool_after_projection':106,'protected24unchanged':True},
    'budget':{'priorE27whole_seconds':res27['actual_execution']['wall_seconds_including_init_cleanup'],
              'priorE27NLIpairs':72,'DEV96_scaled_prior_whole_seconds':res27['actual_execution']['wall_seconds_including_init_cleanup']*96/72,
              'DEV96_largest_prior_p95_heuristic_seconds':96*p95,'TRAIN24_inference_only_p95_heuristic_seconds':24*p95,
              'backward_optimizer_memory':'UNMEASURED; no probe; frozenprefix graph helps plausibility, not runtime guarantee',
              'conclusion':'Two separately cappedCPU2/600phases plausibly feasible; TRAINfailure closesDEV without retry'},
    'risks':['8TRAINdocs/24choices may underfit or overfit; Cpresence unknown, no balancing',
             'Incomplete retrievedcontext gives document-label noise; distributed evidence may remain missing',
             'Strict DEVclasspresence/Cgain can be unevaluable or fail at ceiling; no expostgatechanges',
             'Native-only training makes retrieval contrast conditional on that training distribution',
             '8DEVgroups and unknown foundation/fuzzy overlap do not establish officialbenchmark generalization'],
    'isolation':'Metadata only thisepoch; original annotatedsource neveropened. Old metadata parsed whole but source_utf8_bytes never used. Later sourceprojection is logicalfield isolation, notOS secrecy.',
    'activity':{'ML_native_Torch_ORT_tokenizer_imports':0,'weights_deserializations':0,'downloads':0,
                'training_steps':0,'inference_calls':0,'raw_source_parses':0,'annotation_choices_or_evidence_reads':0,
                'Git_or_project_mutations':0,'paid_or_GPU_calls':0},
    'evidence':verified}
review_ref = put('hypothesis-acceptance-review.json',review)
freeze_ref = put('proposal-source-freeze.json',{
    'schema_version':1,'epoch':30,'kind':KIND,
    'status':'FIXED_METADATA_ALLOCATION_AND_SCIENCE_BEFORE_RAW_INPUTS_OR_MODELS',
    'at':datetime.now(timezone.utc).isoformat(),
    'files':[allocation_ref,protocol_ref,review_ref,identity(Path(__file__).resolve())],
    'source_checkpoint':identity(cp_path),'freshR30_and_concrete_source_runtime_freeze_required':True,
    'model_or_source_annotation_calls':0,'project_writes':0})
print(json.dumps({'selection':allocation_ref,'protocol':protocol_ref,'review':review_ref,'freeze':freeze_ref,
                  'TRAIN':train,'DEV':dev,'kind':KIND},sort_keys=True))
