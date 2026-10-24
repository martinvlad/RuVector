"""Pure stdlib identity/source tests; no corpus parse, source labels or model imports."""
from pathlib import Path
import importlib.util,json,hashlib,tempfile,os
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('data_common',HERE/'data_common.py');C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
checks=[]
def check(name,fun):
 fun();checks.append({'name':name,'passed':True})
def req(v):
 if not v:raise AssertionError('fixture failed')
check('fixed24_case_order',lambda:req(len(C.expected('dev'))==24 and C.expected('dev')[0]==('original-contractnli:train:epoch32:dev:557:nda-17',557,'nda-17') and C.expected('dev')[-1][1:]==(448,'nda-3')))
check('current_TRAIN_calibration_CONF_empty',lambda:req(C.TRAIN_IDS==[] and json.loads((HERE/'selection.json').read_text())['roles']=={'train':[],'dev':C.DEV_IDS,'calibration':[],'confirmation':[]}))
check('canonical_normalizer_casefold_whitespace',lambda:req(C.norm(' Stra\u00dfe\n A\tB ')== 'strasse a b'))
check('canonical_source_pair_utf8_stable',lambda:req(C.canonical({'hypothesis':'\u00e9','document':'x'})=='{"document":"x","hypothesis":"\u00e9"}'))
def duplicates():
 try:json.loads('{"x":1,"x":2}',object_pairs_hook=C.unique_object)
 except ValueError:return
 raise AssertionError('duplicate accepted')
check('duplicate_JSON_rejected',duplicates)
def selection():
 v=json.loads((HERE/'selection.json').read_text());salt=v['selection']['salt'];ids=v['selection']['eligible_document_ids'];ranked=sorted((hashlib.sha256((salt+str(i)).encode()).hexdigest(),i)for i in ids);req([i for _,i in ranked[:8]]==C.DEV_IDS);req(len(ids)==98 and len(set(ids))==98);req(not set(ids)&set(v['prior_exposed_document_ids_unchanged']));req(not set(ids)&set(v['protected_document_ids_unchanged']))
check('metadata_salt_rank_replay_disjoint_roles',selection)
check('native_ENC_permutation',lambda:req(C.NATIVE_ORDER==['entailment','not_mentioned','contradiction'] and C.SOURCE_MAP=={'Entailment':0,'NotMentioned':1,'Contradiction':2}))
for name in ['build_inputs.py','audit_input_identity.py','build_proposal.py']:
 compile((HERE/name).read_text(),str(HERE/name),'exec')
check('all_projection_sources_compile_no_execution',lambda:None)
result={'schema_version':1,'epoch':32,'checks_passed':True,'checks':checks,'counts':{'tests':len(checks),'source_corpus_parses':0,'choice_or_evidence_reads':0,'ML_native_tokenizer_import_or_calls':0,'input_projection_executions':0},'scope':'Pure source/identity/unit fixtures only. No original annotated corpus, official DEV choices, weights or models accessed.'}
p=HERE/'input-source-preflight.json'
with p.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'tests':len(checks)}))
