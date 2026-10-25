"""Generic E40 source freeze; never parses cases/vault or calls scientific code."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,copy,hashlib,json,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'publication'))
import publication_common_v1 as c
from phase_contract_v1 import *
W=Path('/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05')

def checked(root,row):
 c.require(isinstance(row,dict)and set(row)=={'path','bytes','sha256'}and type(row.get('bytes'))is int,'Canonical source reference required')
 c.require(c.ref(root,row['path'])==row,'Source reference mismatch: '+str(row.get('path')));return row

def write_new(path,value):
 data=c.encoded(value,pretty=True)
 with path.open('xb')as target:target.write(data);target.flush();os.fsync(target.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)

def roles_ready(fields):
 roles=fields.get('data_roles');c.require(isinstance(roles,dict)and set(roles)=={'train','dev','calibration','confirmation'},'Exact explicit DEV roles required')
 c.require(all(roles[k]==[]for k in ('train','calibration','confirmation'))and isinstance(roles['dev'],list)and len(roles['dev'])==12 and len({c.encoded(v)for v in roles['dev']})==12,'Twelve distinct DEV identities, no other role')
 c.require(fields.get('arms')==ARMS and type(fields.get('actual_NLI_forwards'))is int and fields['actual_NLI_forwards']==48,'Four measured arms/48readouts; no numeric certificate or derivedforecast layer')
 return roles

def external_ready(fields):
 assets=fields.get('external_data_assets');c.require(isinstance(assets,list)and len(assets)==2 and {r.get('role')for r in assets}=={'dev_features','dev_oracle'},'Two external prepared assets; oracle is opaque vault')
 c.require(len({r['path']for r in assets})==2,'Distinct external features/vault paths')
 for row in assets:
  c.require(set(row)=={'path','bytes','sha256','role'}and type(row['bytes'])is int and row['bytes']>0,'Exact external asset descriptor')
  file=c.canonical(row['path']);c.require(file.is_relative_to(W/'data-source')and not file.is_relative_to(W/'project'),'Data outside public project and under fixed data-source directory')
  # Byte hashing only. No decoding/JSON/vault parsing or case inspection.
  h=hashlib.sha256();count=0
  with file.open('rb')as stream:
   for block in iter(lambda:stream.read(1048576),b''):h.update(block);count+=len(block)
  c.require(count==row['bytes']and h.hexdigest()==row['sha256'],'Prepared external asset changed')
 return copy.deepcopy(assets)

def review_ready(root,path,current):
 row=c.ref(root,path);review=c.parse(root/path)
 required={'checks_passed':True,'data_source_license_scoring_access_verified':True,'label_blind_policy_frozen_before_materialization':True,'actual_full_model_assets_guard_verified':True,'no_raw_third_party_text_in_public_files':True,'scientific_measurements_started':False,'authoritative_label_codec_source_and_external_structure_verified':True,'private_input_publication_boundary_verified':True,'frozen_missing_or_partial_gold_failure_path_verified':True}
 c.require(all(type(review.get(k))is type(v)and review[k]==v for k,v in required.items()),'Independent integrated source/data/license/blindpolicy/realguard/privacy review required')
 indexed={r['path']:r for r in review.get('files',[])}
 c.require(len(indexed)==len(review.get('files',[]))and set(indexed)==set(current)-{path},'Review covers all current public sources except its own nonrecursive metadata')
 for name,body in current.items():
  if name!=path:c.require(indexed[name]=={'path':name,'bytes':len(body),'sha256':c.sha(body)},'Integrated source review bytes changed: '+name)
 return row

def build(args):
 c.require(args.scope.absolute()==W,'Exact E40 isolated scope');root=c.directory(W/'project');c.live_owner(W)
 c.require(not(root/PLAN_PATH).exists()and not(root/FREEZE_PATH).exists(),'No master overwrite/replay')
 specification=c.parse(root/args.inputs);c.require(specification.get('epoch')==40 and specification.get('kind')==KIND,'Current reviewed PLAN_INPUTS required')
 fields=copy.deepcopy(specification.get('plan_fields'));c.require(isinstance(fields,dict),'Reviewed plan_fields dictionary required');roles=roles_ready(fields);external_ready(fields)
 contract=checked(root,specification.get('root_contract'));rootdoc=c.parse(root/contract['path']);c.require(rootdoc.get('epoch')==40 and rootdoc.get('kind')==KIND,'Exact E40 ROOT contract')
 required=specification.get('required_refs');c.require(isinstance(required,dict)and REQUIRED_REFS<=set(required),'Explicit required scientific/source references')
 for row in required.values():checked(root,row)
 inherited=specification.get('inherited_source_refs',[]);c.require(isinstance(inherited,list),'Explicit inherited dependencies')
 for row in inherited:checked(root,row)
 current=c.walk_current(root);review=review_ready(root,args.review,current)
 c.require(not any('/runs/'in name or name.endswith('/SOURCE_ADMISSION.json')or name.endswith('/DISPATCH_RESERVATION.json')or name.endswith('/EPOCH_MANIFEST.json')for name in current),'No scientific execution/admission/results before source freeze')
 for value in (args.source_parent,args.source_root,args.source_bench,args.source_scope):c.require(isinstance(value,str)and c.re.fullmatch('[0-9a-f]{40}',value),'Actual source parent/tree identity required')
 source_stage=args.source_stage.absolute();final_stage=args.final_stage.absolute();c.require(source_stage==W/'stage-source'and final_stage==W/'stage-final','Exact isolated stages')
 fixed={'schema_version':1,'epoch':40,'kind':KIND,'phase':PHASE,'source_checkpoint':c.BASE_COMMIT,'actual_project':str(root),'guardian_scope':str(W),'publication_parent':args.source_parent,'publication_parent_trees':dict(zip(('root','bench','scope'),(args.source_root,args.source_bench,args.source_scope))),'publication_stage_paths':{'source':str(source_stage),'final':str(final_stage)},'limits':LIMITS,'used_confirmation_identities':[],'confirmation':[],'benchmark_accuracy':None,'promotion_allowed':False,'official_eligibility':'HOLD',**FLAGS}
 for key,value in fixed.items():c.require(key not in fields or type(fields[key])is type(value)and fields[key]==value,'Protected plan override: '+key)
 fields.update(fixed);fields.update(root_contract=contract,plan_inputs=c.ref(root,args.inputs),source_review=review,required_refs=required,inherited_source_refs=inherited,scorer=required['scorer'],protocol=required['protocol'])
 entries=[{'path':name,'bytes':len(body),'sha256':c.sha(body)}for name,body in sorted(current.items())]
 freeze={'schema_version':1,'epoch':40,'kind':KIND,'phase':PHASE,'source_checkpoint':c.BASE_COMMIT,'entries':entries,'inherited_source_dependencies':inherited,'data_roles':roles,'root_contract':contract,'external_data_assets':fields['external_data_assets'],'exclusions':[PLAN_PATH,FREEZE_PATH],'rule':'All reviewed current source and public data/license/blind-ID descriptors freeze before any tokenizer/native/NNI. Features and opaque gold vault remain outside project; hash-only here. Gold semantic decode only after48readouts and model/native closure. DEV-only transfer pilot; no fullbenchmark placement/confirmation/promotion.'}
 coverage={row['path']:row for row in entries+inherited}
 c.require(all(coverage.get(row['path'])==row for row in list(required.values())+[contract,fields['plan_inputs'],review]),'Every required/source/ROOT/input reference must be in frozen closure before any write')
 if args.check_only:return {'status':'SOURCE_PREPARATION_CHECK_PASS','current_files':len(entries),'actual_NLI_forwards':48,'DEV_identities':12,'writes':0,'science_Git_calls':0}
 write_new(root/FREEZE_PATH,freeze);fr=c.ref(root,FREEZE_PATH);pins={row['path']:row for row in entries+inherited+[fr]}
 c.require(all(pins.get(row['path'])==row for row in required.values()),'Every required source reference must be frozen')
 fields.update(source_freeze=fr,source_freeze_path=fr['path'],source_freeze_sha256=fr['sha256'],pins=[pins[k]for k in sorted(pins)])
 write_new(root/PLAN_PATH,fields)
 return {'status':'E40_MASTER_SOURCE_FROZEN','plan':c.ref(root,PLAN_PATH),'source_freeze':fr,'source_files':len(entries),'pins':len(pins),'science_Git_calls':0}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--scope',type=Path,default=W);parser.add_argument('--inputs',required=True);parser.add_argument('--review',required=True);parser.add_argument('--check-only',action='store_true')
 for name in ('source-parent','source-root','source-bench','source-scope'):parser.add_argument('--'+name,required=True)
 for name in ('source-stage','final-stage'):parser.add_argument('--'+name,type=Path,required=True)
 print(json.dumps(build(parser.parse_args()),sort_keys=True))
