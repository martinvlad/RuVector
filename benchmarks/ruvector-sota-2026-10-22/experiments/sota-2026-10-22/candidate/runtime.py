"""Real native RuVector inference followed by an optional frozen learned head."""
from __future__ import annotations
import importlib.util
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0,str(HERE))
from head import transform, validate_artifact


class CandidateEngine:
    attribution = "Actual native RuVector BGE-small + frozen104 validators + optional generic residual head and separated public DEV calibration"

    def __init__(self, artifact_path=None):
        self.artifact = json.loads(Path(artifact_path).read_text()) if artifact_path else None
        if self.artifact:
            validate_artifact(self.artifact)
        runtime = json.loads((ROOT/"experiments/submission-2026-10-22/jevbench/runtime-manifest.json").read_text())
        plan_path = ROOT/runtime["selected_plan"]["path"]
        if hashlib.sha256(plan_path.read_bytes()).hexdigest() != runtime["selected_plan"]["sha256"]:
            raise ValueError("Baseline104 selected plan identity mismatch")
        plan = json.loads(plan_path.read_text())
        for name, expected in plan["source_sha256"].items():
            source = ROOT/name
            if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise ValueError("Baseline104 source identity mismatch: "+name)
        for item in runtime["model_assets"]:
            asset = ROOT/item["path"]
            if asset.is_symlink() or hashlib.sha256(asset.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("Baseline104 model asset identity mismatch")
        spec = importlib.util.spec_from_file_location("sota_frozen104_engine", ROOT/"experiments/submission-2026-10-22/jevbench/engine.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.engine = module.CompositeEngine(ROOT/"experiments/submission-2026-10-22/jevbench/round2-v2/rules.py")
        if self.engine.receipt["binary_sha256"] != plan["native_candidate"]["binary_sha256"]:
            self.engine.close()
            raise ValueError("Baseline104 native binary identity mismatch")
        self.native_process = self.engine.native.process
        self.native_pid = self.native_process.pid
        self.receipt = {**self.engine.receipt, "architecture":"native104 plus generic residual option head and separated public DEV calibration", "candidate_artifact_sha256":self.artifact["artifact_sha256"] if self.artifact else None}
        self.name = "ruvector-sota-" + (self.artifact["config"]["id"] if self.artifact else "baseline104")
        self.last_usage = None

    def predict(self, state, questions):
        response = self.engine.predict(state,questions)
        self.last_usage = response.get("usage")
        if self.artifact:
            baseline = response
            response = transform(response,state,questions,self.artifact)
            # Saved paired control from this exact real native call, never a
            # second invocation and never evaluation metadata.
            response["baseline104_response"] = baseline
        return response

    def close(self):
        self.engine.close()
