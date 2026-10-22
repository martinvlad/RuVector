"""Fit epoch2 temperature from explicitly separate saved calibration records."""
import argparse
import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location("epoch2_train_head",Path(__file__).parent/"head.py")
head=importlib.util.module_from_spec(spec);spec.loader.exec_module(head)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--records",type=Path,required=True)
    parser.add_argument("--config",required=True,choices=[c["id"] for c in head.candidate_configs()])
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    records=[json.loads(line) for line in args.records.read_text().splitlines() if line]
    config=next(c for c in head.candidate_configs() if c["id"]==args.config)
    artifact=head.fit(records,config)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(artifact,indent=2)+"\n")
    print(json.dumps({"status":"fitted","config":args.config,"artifact_sha256":artifact["artifact_sha256"]}))


if __name__=="__main__":main()
