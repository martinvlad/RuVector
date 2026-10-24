"""Build an acyclic archive provenance seal before E31 source freeze; no model calls."""
import sys
sys.dont_write_bytecode=True
import argparse,copy,json
from pathlib import Path
from publication_common_v1 import *
from phase_schema_v1 import *
from stage_publication_v1 import archive_ready

def build(args):
 root,kit=map(directory,(args.project,args.kit));live_owner(root.parent)
 cp=parse(kit/'CHECKPOINT_MANIFEST.json');require(sha(content(kit/'CHECKPOINT_MANIFEST.json'))==BASE_CP_SHA256,'Wrong actual BASE checkpoint');check_inherited_checkpoint(cp);rows=check_history(root,cp)
 seal={'schema_version':1,'epoch':31,'kind':KIND,'status':'ARCHIVED_TRAINED_PARAMETER_ARTIFACT_SEALED','source_checkpoint':BASE_COMMIT,
  'historical_training_epoch':30,'historical_training_document_ids':HISTORICAL_TRAIN_IDS,'data_roles':copy.deepcopy(ROLES),'hypotheses':HYPOTHESES,
  **{key:copy.deepcopy(rows[path])for key,path in ARCHIVED_SOURCE_PATHS.items()}}
 archive_ready(root,rows,seal);write(root/ARCHIVED_SEAL_PATH,encoded(seal,pretty=True))
 return {'archived_model_seal':ref(root,ARCHIVED_SEAL_PATH),'current_training_or_native_or_model_calls':0,'original_model_publication_claim':False}

if __name__=='__main__':
 cli=argparse.ArgumentParser();cli.add_argument('--project',type=Path,required=True);cli.add_argument('--kit',type=Path,required=True);print(json.dumps(build(cli.parse_args()),sort_keys=True))
