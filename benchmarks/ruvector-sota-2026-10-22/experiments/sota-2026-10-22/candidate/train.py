"""Fit a frozen config from saved real-native records; no inference or network."""
import argparse
import json
from pathlib import Path
from head import candidate_configs, fit


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--records",type=Path,required=True)
    parser.add_argument("--config",required=True,choices=[c["id"] for c in candidate_configs()])
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    config=next(c for c in candidate_configs() if c["id"]==args.config)
    records=[json.loads(line) for line in args.records.read_text().splitlines() if line]
    artifact=fit(records,config)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(artifact,indent=2)+"\n")
    print(json.dumps({"status":"fitted","config":args.config,"artifact_sha256":artifact["artifact_sha256"],"fit_counts":artifact["fit_counts"]}))


if __name__=="__main__":main()
