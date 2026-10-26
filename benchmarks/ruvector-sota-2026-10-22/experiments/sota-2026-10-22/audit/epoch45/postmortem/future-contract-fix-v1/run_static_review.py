"""Static public-source contract audit and inert identity metadata fixtures only."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

O=Path(__file__).parent
R=Path('/tmp/ruvector-sota-2026-10-22/epoch45-c5608a638ecd/project')
PLAN='experiments/sota-2026-10-22/epoch45/plan.json'
PLAN_SHA='577b93192b06bc3123926bc80a832b9f9eefa3991bdffdd155d6c40c5b4fb176'
FREEZE_SHA='1339ca7a93ddc64a67f00c3323063b79814793d58fab455a38f4f6ba2f372135'
KIND='REAL_CONTRACTNLI_QWEN_JOINT_CONTEXT_DEV_PILOT'

def sha(b):return hashlib.sha256(b).hexdigest()
def ref(p,root=None):
    b=p.read_bytes();return {'path':str(p.relative_to(root))if root else str(p),'bytes':len(b),'sha256':sha(b)}
def emit(name,value):(O/name).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
def require(v,code):
    if not v:raise AssertionError(code)

# Import only this newly authored independent metadata validator, never target code.
spec=importlib.util.spec_from_file_location('future_identity_contract',O/'validate_native_plan_contract.py')
V=importlib.util.module_from_spec(spec);spec.loader.exec_module(V)
plan_bytes=(R/PLAN).read_bytes();require(len(plan_bytes)==23409 and sha(plan_bytes)==PLAN_SHA,'FROZEN_PLAN_IDENTITY')
plan=json.loads(plan_bytes);freeze_bytes=(R/plan['source_freeze']['path']).read_bytes()
require(len(freeze_bytes)==21659 and sha(freeze_bytes)==FREEZE_SHA,'FROZEN_SOURCE_IDENTITY')
freeze=json.loads(freeze_bytes);pins={r['path']:r for r in freeze['files']}
require(len(pins)==101,'SOURCE101')

def outcome(p):
    try:return {'checks_passed':True,'result':V.validate_native_plan_contract(p)}
    except V.ContractError as error:return {'checks_passed':False,'error_code':str(error)}

original=outcome(plan)
require(original=={'checks_passed':False,'error_code':'MISSING_FROZEN_CASE_IDS_BY_DOCUMENT'},'ACTUAL_FROZEN_PLAN_REPRODUCES_MISSING_FIELD')
fragment=V.proposed_future_plan_fields(plan)
proposed=copy.deepcopy(plan);proposed.update(fragment)
require(set(proposed)-set(plan)=={'case_ids_by_document'}and all(proposed[k]==plan[k]for k in plan),'ONLY_ONE_FUTURE_FIELD_ADDED_IN_MEMORY')
corrected=outcome(proposed);require(corrected['checks_passed'],'PROPOSED_NATIVE_CONTRACT_PASSES')
emit('FUTURE_PLAN_FIELDS.fragment.v1.json',fragment)
emit('FUTURE_PLAN_ADD.rfc6902.json',[{'op':'add','path':'/case_ids_by_document','value':fragment['case_ids_by_document']}])
emit('FUTURE_INTERFACE_ADD.rfc6902.json',[{'op':'add','path':'/plan_fields/case_ids_by_document','value':fragment['case_ids_by_document']}])

fixtures=[]
def reject(name,edit):
    value=copy.deepcopy(proposed);edit(value);result=outcome(value)
    require(result['checks_passed']is False,name)
    fixtures.append({'name':name,**result,'expected_rejection_observed':True})
reject('missing_map',lambda p:p.pop('case_ids_by_document'))
reject('boolean_document_id',lambda p:p['dev_document_ids'].__setitem__(0,True))
reject('float_document_id',lambda p:p['dev_document_ids'].__setitem__(0,357.0))
reject('negative_document_id',lambda p:p['dev_document_ids'].__setitem__(0,-357))
reject('unsafe_JS_document_id',lambda p:p['dev_document_ids'].__setitem__(0,2**53))
reject('duplicate_document_id',lambda p:p['dev_document_ids'].__setitem__(1,357))
reject('reordered_document_ids',lambda p:p['dev_document_ids'].reverse())
reject('reordered_hypotheses',lambda p:p['dev_hypothesis_ids'].reverse())
reject('reordered_DEV_cases',lambda p:p['data_roles']['dev'].reverse())
reject('duplicate_DEV_case',lambda p:p['data_roles']['dev'].__setitem__(1,p['data_roles']['dev'][0]))
reject('foreign_case_identity',lambda p:p['data_roles']['dev'].__setitem__(0,'contractnli:eced6528:test:62:nda-1'))
reject('noncanonical_decimal_case',lambda p:p['data_roles']['dev'].__setitem__(0,'contractnli:eced6528:test:0357:nda-1'))
reject('nonstring_case',lambda p:p['data_roles']['dev'].__setitem__(0,357))
reject('map_has_extra_document',lambda p:p['case_ids_by_document'].__setitem__('62',[]))
reject('map_missing_document',lambda p:p['case_ids_by_document'].pop('357'))
reject('map_nonstring_key',lambda p:p['case_ids_by_document'].__setitem__(357,p['case_ids_by_document'].pop('357')))
reject('map_reordered_queries',lambda p:p['case_ids_by_document']['357'].reverse())
reject('map_wrong_document_query',lambda p:p['case_ids_by_document']['357'].__setitem__(0,p['case_ids_by_document']['227'][0]))
reject('map_drops_one_query',lambda p:p['case_ids_by_document']['357'].pop())
reject('protected_confirmation_role',lambda p:p['data_roles']['confirmation'].append('contractnli:eced6528:test:62:nda-1'))
require(sha((R/PLAN).read_bytes())==PLAN_SHA,'ORIGINAL_FROZEN_PLAN_UNCHANGED_AFTER_INERT_METADATA_FIXTURES')

runtime_added={'_plan_sha','_dispatch_admission_path','node_runtime_receipt','private_features','source_units_per_document','source_units_total'}
qualified_added={'expected_operation_counters'}
enriched=copy.deepcopy(plan)
enriched.update(_plan_sha=PLAN_SHA,_dispatch_admission_path=str(R/plan['dispatch_admission_path']),node_runtime_receipt={},private_features={'path':plan['private_features_path'],'bytes':73969,'sha256':'73443811bc58206012d6abbb1d1e738418d99a691706f19e9e1966722abdd21f'},source_units_per_document={'357':25,'227':53,'46':56,'212':42},source_units_total=176)
# Counter values are not executed here; only fields consumed by qualifier are inspected.
qualified=copy.deepcopy(enriched);qualified['expected_operation_counters']={'dev':{}}
future_enriched=copy.deepcopy(enriched);future_enriched.update(fragment)
future_qualified=copy.deepcopy(qualified);future_qualified.update(fragment)

class ConsumerVisitor(ast.NodeVisitor):
    def __init__(self,path):self.path=path;self.function='<module>';self.rows=[]
    def visit_FunctionDef(self,node):
        before=self.function;self.function=node.name;self.generic_visit(node);self.function=before
    visit_AsyncFunctionDef=visit_FunctionDef
    def access(self,node):
        if isinstance(node,ast.Name)and node.id in {'plan','runtime_plan','bound'}:return []
        if isinstance(node,ast.Name)and node.id=='p'and self.path.endswith('/common.py')and self.function in {'admit','owner_fence'}:return []
        if isinstance(node,ast.Attribute)and isinstance(node.value,ast.Name)and node.value.id=='self'and node.attr=='plan':return []
        if isinstance(node,ast.Subscript):
            before=self.access(node.value)
            if before is not None:return before+[node.slice.value if isinstance(node.slice,ast.Constant)and type(node.slice.value)in(str,int)else '*']
        return None
    def visit_Subscript(self,node):
        parts=self.access(node)
        if parts:self.rows.append({'source_path':self.path,'line':node.lineno,'function':self.function,'access_path':parts,'syntax':'Python AST literal subscript chain','dynamic_index': '*'in parts})
        self.generic_visit(node)

consumers=[];source_refs=[]
for path,row in pins.items():
    is_core=('/runtime/epoch45/'in path or '/epoch45/preparation/'in path or path.endswith('/epoch45/observer.py')or path.endswith('/epoch45/closure_metadata.py'))
    is_data=('/audit/epoch45/e45_'in path)
    if not((is_core or is_data)and Path(path).suffix in {'.py','.cjs'}):continue
    b=(R/path).read_bytes();require(len(b)==row['bytes']and sha(b)==row['sha256'],'FROZEN_CONSUMER_SOURCE_HASH_'+path);source_refs.append(row)
    if path.endswith('.py'):
        visitor=ConsumerVisitor(path);visitor.visit(ast.parse(b,filename=path));consumers.extend(visitor.rows)
    elif Path(path).name in {'native_helper.cjs','node_guard.cjs'}:
        text=b.decode();variable='plan'if path.endswith('/native_helper.cjs')else'p'
        for match in re.finditer(r'\b'+variable+r'((?:\.[A-Za-z_$][A-Za-z0-9_$]*)+)',text):
            parts=match.group(1)[1:].split('.')
            consumers.append({'source_path':path,'line':text.count('\n',0,match.start())+1,'function':'configureIdentities'if variable=='plan'else'preload admission','access_path':parts,'syntax':'JavaScript source dot chain; no JS execution','dynamic_index':text[match.end():].lstrip().startswith('[')})

def resolve(value,parts):
    for part in parts:
        if part=='*':return 'PRESENT_DYNAMIC_INDEX_REQUIRES_DOMAIN_CONTRACT'
        if type(value)is list and part in {'length','some'}:return 'PRESENT_ARRAY_BUILTIN_PROPERTY'
        if type(value)is dict and part in value:value=value[part]
        elif type(value)is list and type(part)is int and 0<=part<len(value):value=value[part]
        else:return 'MISSING'
    return 'PRESENT'

rows=[];seen=set()
for row in consumers:
    key=(row['source_path'],row['function'],tuple(row['access_path']))
    if key in seen:continue
    seen.add(key);parts=row['access_path'];top=parts[0]
    phase='frozen_plan';before=plan;after=proposed
    if top in runtime_added:phase='common.admit runtime view after independent DATA';before=enriched;after=future_enriched
    if top in qualified_added:phase='qualification runtime_plan from authenticated dispatch';before=qualified;after=future_qualified
    rows.append(dict(row,required_at=phase,current_status=resolve(before,parts),proposed_status=resolve(after,parts)))
missing={r['access_path'][0]for r in rows if r['current_status']=='MISSING'}
future_missing=[r for r in rows if r['proposed_status']=='MISSING']
require(missing=={'case_ids_by_document'},'ONLY_MISSING_REQUIRED_FROZEN_TOP_LEVEL_FIELD_IS_NATIVE_ID_MAP')
require(future_missing==[],'NO_UNRESOLVED_LITERAL_PLAN_CONSUMER_FIELDS_AFTER_FUTURE_FRAGMENT')
native=[r for r in rows if r['source_path'].endswith('/native_helper.cjs')]
require({r['access_path'][0]for r in native}=={'dev_document_ids','case_ids_by_document','data_roles'},'ALL_NATIVE_HELPER_PLAN_DOT_ROOTS_COVERED')
inventory={
    'schema_version':1,'epoch':45,'kind':KIND,'source_only':True,
    'source_plan':ref(R/PLAN,R),'source_freeze':plan['source_freeze'],'reviewed_source_files':source_refs,
    'consumer_count':len(rows),'consumers':rows,'native_helper_consumers':native,
    'missing_current_frozen_top_level_fields':sorted(missing),'missing_after_future_fragment':future_missing,
    'runtime_enrichment_contract':{'common.admit':sorted(runtime_added),'qualification runtime_plan':sorted(qualified_added)},
    'scope':'All direct plan/self.plan/bound/runtime_plan literal Python subscript chains, common admit/owner p aliases, and all native helper/Node preload direct plan dot chains. Computed dictionary keys are recorded and bounded by specific identity/count/reference contracts. This inventory is not a whole-program type/alias proof, target invocation, ABI or scientific execution proof.'
}
emit('PLAN_FIELD_CONSUMERS.v1.json',inventory)
results={
    'schema_version':1,'epoch':45,'kind':KIND,'source_only':True,'checks_passed':True,
    'current_frozen_plan':ref(R/PLAN,R),'current_frozen_plan_validation':original,
    'proposed_fragment':ref(O/'FUTURE_PLAN_FIELDS.fragment.v1.json'),
    'proposed_in_memory_validation':corrected,'only_added_field':'case_ids_by_document',
    'negative_fixture_count':len(fixtures),'negative_fixtures':fixtures,
    'all_native_helper_plan_dot_consumers_checked':True,'other_literal_runtime_plan_fields_checked':True,
    'other_unresolved_required_plan_fields':[],
    'frozen_plan_bytes_unchanged':True,'native_helper_bytes_unchanged':True,
    'target_source_imports_or_calls':0,'Node_native_model_tokenizer_version_or_Gold_calls':0,'private_asset_reads_or_parses':0,'API_calls':0,'R_writes':0,
    'no_current_epoch_rerun_or_source_edit_authorized':True,'benchmark_or_candidate_quality_evidence':False
}
emit('STATIC_CONTRACT_RESULTS.v1.json',results)
emit('FUTURE_FIX_SCOPE.v1.json',{
    'schema_version':1,'epoch':45,'kind':KIND,'source_only':True,'future_only':True,
    'problem':'Frozen E45 plan and CORE plan interface omitted case_ids_by_document, required before native binary load by native_helper.configureIdentities.',
    'minimal_change':'Add the exact derived document-to-ordered-case map to a future plan interface and final frozen plan. Run independent public JSON validation before SOURCE publication and DATA/worker admission.',
    'current_failure_preserved':'Actual E45 frozen plan remains unchanged and fails MISSING_FROZEN_CASE_IDS_BY_DOCUMENT. No current retry or source amendment is proposed.',
    'adoption_constraints':['Only a separately authorized future epoch and fresh complete SOURCE/readback/owner/nonce may adopt this fragment.','Derive groups from the final frozen data_roles.dev, dev_document_ids and dev_hypothesis_ids, then validate exact types, cohort and ordering before freeze.','Include validator and source contract review in future public source artifacts; metadata fixture pass does not establish native ABI, reader compatibility, runtime completion, quality or benchmark generalization.','Preserve all twelve inputs as exposed DEV forever, protected62/321/2 unused HOLD, scientific protocol and all asset hashes.','Future source namespaces/bindings and slot must be newly frozen; the RFC6902 examples add only the missing identity field and do not perform operational rebinding.'],
    'public_only_reproduction':['python -I -B run_static_review.py','python -I -B validate_native_plan_contract.py --plan <future-public-plan.json>'],
    'publication_destination_suggestion':'experiments/sota-2026-10-22/audit/epoch45/postmortem/future-contract-fix-v1/'
})
names=['validate_native_plan_contract.py','run_static_review.py','FUTURE_PLAN_FIELDS.fragment.v1.json','FUTURE_PLAN_ADD.rfc6902.json','FUTURE_INTERFACE_ADD.rfc6902.json','PLAN_FIELD_CONSUMERS.v1.json','STATIC_CONTRACT_RESULTS.v1.json','FUTURE_FIX_SCOPE.v1.json']
emit('PUBLIC_COPY_ALLOWLIST.v1.json',{'schema_version':1,'epoch':45,'kind':KIND,'source_only':True,'future_only':True,'public_copy_allowlist':[dict(ref(O/name,O),source=str(O/name))for name in names],'file_count':len(names),'no_current_epoch_source_edits_or_reruns':True})
print(json.dumps({'allowlist':ref(O/'PUBLIC_COPY_ALLOWLIST.v1.json'),'results':ref(O/'STATIC_CONTRACT_RESULTS.v1.json'),'native_helper_consumers':len(native),'all_consumers':len(rows),'source_files':len(source_refs),'negative_fixtures':len(fixtures)},sort_keys=True))
