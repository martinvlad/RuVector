"""Build one independently accepted model seal; no fit/inference/publication."""
import sys
sys.dont_write_bytecode=True
import argparse,json
from pathlib import Path
from publication_common_v1 import directory,parse,ref,cp_rows,walk_current,sha,encoded,write,live_owner,require
from phase_schema_v1 import *
from phase_receipts_v1 import phase_evidence
from stage_publication_v1 import validate_model_seal

def build(args):
 root=directory(args.project);live_owner(root.parent);plan=parse(root/PLAN_PATH)
 require(args.report.is_absolute() and args.report.is_relative_to(root),'Copy independent label-free TRAIN audit into public root first')
 rows=cp_rows(parse(args.kit/'CHECKPOINT_MANIFEST.json'))
 for path,body in walk_current(root).items():rows[path]={'path':path,'bytes':len(body),'sha256':sha(body)}
 planref=ref(root,PLAN_PATH);train=phase_evidence(root,'train',planref,rows,required=True)
 seal={'schema_version':1,'epoch':30,'kind':KIND,'status':'TRAINED_PARAMETER_ARTIFACT_SEALED',
  'base_model_sha256':BASE_MODEL['weights_sha256'],'parameter_artifact':ref(root,ARTIFACT_PATH),
  'train_raw':train['raw'],'train_execution':train['execution'],
  'independent_training_report':ref(root,args.report.relative_to(root).as_posix()),
  'source_plan':planref,'source_freeze':ref(root,FREEZE_PATH)}
 _,_,summary=validate_model_seal(root,plan,rows,seal)
 require(not (root/MODEL_SEAL_PATH).exists(),'MODEL seal already exists; no overwrite/reselection')
 write(root/MODEL_SEAL_PATH,encoded(seal,pretty=True))
 return {'model_seal':ref(root,MODEL_SEAL_PATH),'train_integrity_passed':True,'parameter_codec_validation':summary,'native_model_Git_calls':0}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--project',type=Path,required=True);cli.add_argument('--kit',type=Path,required=True);cli.add_argument('--report',type=Path,required=True);print(json.dumps(build(cli.parse_args()),sort_keys=True))
