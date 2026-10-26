"""Invented-schema gate checks via AST-extracted pure validator only; no target IO."""
import ast,copy,hashlib,json
from pathlib import Path
P=Path('/workspace/ruvector-e43-engineering/implementation-v1/project/experiments/sota-2026-10-22/runtime/epoch43/common.py')
b=P.read_bytes();tree=ast.parse(b)
names={}
for n in tree.body:
 if isinstance(n,ast.Assign):
  for t in n.targets:
   if isinstance(t,ast.Name)and t.id in ['KIND','BASE','DOCS','HYPS']:names[t.id]=ast.literal_eval(n.value)
names['CASES']=[f'contractnli:eced6528:test:{d}:{h}'for d in names['DOCS']for h in names['HYPS']]
func=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in ['require','verify_post_data']]
assert len(func)==2
exec(compile(ast.Module(body=func,type_ignores=[]),str(P),'exec'),names)
sha='a'*64;freeze='b'*64;commit='c'*40;source_ref={'path':'invented/source.json','bytes':1,'sha256':'d'*64};features={'path':'/invented/features.json','bytes':2,'sha256':'e'*64}
dispatch={'source_commit':commit,'source_admission':source_ref,'private_features_ref':features,'data_admission':{'path':'invented/data.json','sha256':'f'*64,'bytes':3},'source_units_total':20}
data={'epoch':43,'kind':names['KIND'],'phase':'dev','status':'READY_LABEL_BLIND_DEV_FEATURES_AND_OPAQUE_VAULT','errors':[],'selected_ids':names['CASES'],'source_checkpoint':names['BASE'],'source_commit':commit,'source_plan_sha256':sha,'source_freeze_sha256':freeze,'semantic_gold_values_decoded':0,'selected_raw_choice_tokens_copied':12,'protected_confirmation_body_or_choice_decodes':0,'used_confirmation_identities':[],'private_features':features,'evidence':{'source_admission':source_ref,'source_plan':{'sha256':sha}},'statistics':{'unique_source_units':20,'expanded_pair_source_units':60}}
review={'epoch':43,'kind':names['KIND'],'checks_passed':True,'data_admission':dispatch['data_admission'],'private_features_ref':features,'source_commit':commit,'source_plan_sha256':sha,'semantic_gold_decodes':0,'protected_unused_body_or_choice_decodes':0}
fn=names['verify_post_data'];fn(data,review,dispatch,{},sha,freeze)
negatives=[('failed_status','data','status','DATA_ADMISSION_FAILED'),('data_errors','data','errors',[{'code':'INVENTED'}]),('wrong_ids','data','selected_ids',[]),('wrong_source','data','source_commit','0'*40),('gold_read','data','semantic_gold_values_decoded',1),('protected_read','data','protected_confirmation_body_or_choice_decodes',1),('features_changed','data','private_features',{'path':'/invented/other'}),('review_false','review','checks_passed',False),('review_wrong_commit','review','source_commit','0'*40),('review_gold_read','review','semantic_gold_decodes',1),('review_protected_read','review','protected_unused_body_or_choice_decodes',1)]
passed=[]
for label,which,key,value in negatives:
 d=copy.deepcopy(data);r=copy.deepcopy(review);(d if which=='data'else r)[key]=value
 try:fn(d,r,dispatch,{},sha,freeze)
 except (RuntimeError,KeyError):passed.append(label)
 else:raise AssertionError(label)
print(json.dumps({'source_sha256':hashlib.sha256(b).hexdigest(),'positive_invented_schema_passed':True,'negative_rejections':passed,'actual_target_calls':0}))
