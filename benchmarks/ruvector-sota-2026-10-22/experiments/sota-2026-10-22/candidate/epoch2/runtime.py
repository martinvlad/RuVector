"""Frozen104 real native engine, then epoch2 decision-preserving temperature."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def _module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


HEAD=_module("sota_epoch2_head_runtime",HERE/"head.py")
BASE=_module("sota_epoch1_runtime_base",HERE.parent/"runtime.py")


class CandidateEngine(BASE.CandidateEngine):
    attribution="Actual native RuVector BGE-small + frozen104 validators + choice/noul decision-preserving temperature; score identity"

    def __init__(self,artifact_path=None):
        artifact=json.loads(Path(artifact_path).read_text()) if artifact_path else None
        if artifact:HEAD.validate_artifact(artifact)
        super().__init__(None)
        self.artifact=artifact
        self.name="ruvector-sota-"+(artifact["config"]["id"] if artifact else "baseline104")
        self.receipt.update(architecture=self.attribution,candidate_artifact_sha256=artifact["artifact_sha256"] if artifact else None)

    def predict(self,state,questions):
        baseline=self.engine.predict(state,questions)
        self.last_usage=baseline.get("usage")
        if not self.artifact:return baseline
        response=HEAD.transform(baseline,state,questions,self.artifact)
        response["baseline104_response"]=baseline
        return response
