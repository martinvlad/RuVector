"""Frozen, local-only native three-way NLI reader for a DEV-only diagnostic.

Importing this module does not import torch/transformers or initialize a tokenizer.
Construct a reader only inside the root-admitted bounded worker attempt.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

MODEL_REPOSITORY = "mrm8488/ModernBERT-large-ft-all-nli"
MODEL_REVISION = "afa5e4b89a8a23d3b19da2ed0fa7daf2496c7c47"
WEIGHT_SHA256 = "a00110cace66b50896ea585c3aa4385812c5cd201d7fd948b1b04239d9b68af4"
WEIGHT_BYTES = 1583355740
RAW_LABELS = ("ENTAILMENT", "NEUTRAL", "CONTRADICTION")
CANONICAL_LABELS = ("Entailment", "Contradiction", "NotMentioned")
RAW_TYPED_LABELS = ("Entailment", "NotMentioned", "Contradiction")
REQUIRED_ASSETS = frozenset({
    "README.md", "config.json", "model.safetensors", "special_tokens_map.json",
    "tokenizer.json", "tokenizer_config.json",
})


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_probabilities(raw_logits: Iterable[float]) -> list[float]:
    """Full-head, temperature-one softmax, permuted E/N/C -> E/C/N."""
    logits = [float(value) for value in raw_logits]
    if len(logits) != 3 or not all(math.isfinite(value) for value in logits):
        raise ValueError("Expected exactly three finite native E/N/C logits")
    offset = max(logits)
    values = [math.exp(value - offset) for value in logits]
    denominator = sum(values)
    probabilities = [value / denominator for value in values]
    return [probabilities[0], probabilities[2], probabilities[1]]


def verify_runtime_assets(model_directory: str | Path, asset_lock: str | Path) -> dict:
    """Read/hash files only; never import an ML runtime or execute model code."""
    directory = Path(model_directory).resolve(strict=True)
    lock = json.loads(Path(asset_lock).read_text())
    if lock.get("repository") != MODEL_REPOSITORY or lock.get("revision") != MODEL_REVISION:
        raise ValueError("Asset lock is for a different checkpoint")
    if lock.get("diagnostic_only") is not True or lock.get("confirmation_ids") != []:
        raise ValueError("This reader is admitted only for a diagnostic with empty CONF")
    files = lock.get("files", [])
    if len(files) != len(REQUIRED_ASSETS) or {item["path"] for item in files} != REQUIRED_ASSETS:
        raise ValueError("Incomplete or unexpected executable/runtime asset closure")
    for item in files:
        path = directory / item["path"]
        if path.is_symlink() or not path.is_file() or path.resolve().parent != directory:
            raise ValueError("Runtime assets must be regular direct child files")
        if path.stat().st_size != item["bytes"] or file_sha256(path) != item["sha256"]:
            raise ValueError("Runtime asset identity mismatch: " + item["path"])
    weights = next(item for item in files if item["path"] == "model.safetensors")
    if weights["sha256"] != WEIGHT_SHA256 or weights["bytes"] != WEIGHT_BYTES:
        raise ValueError("Checkpoint weights differ from publisher pin")
    if lock.get("static_tensor_check", {}).get("native_classifier_shape") != [3, 1024]:
        raise ValueError("Static native three-way classifier check is missing")
    if lock.get("static_tensor_check", {}).get("floating_dtypes") != ["F32"]:
        raise ValueError("Frozen diagnostic requires original FP32 weights")
    if lock.get("reader_contract", {}).get("max_pair_tokens") != 512:
        raise ValueError("Runtime asset lock does not bind the frozen paired-token budget")
    return lock


class FrozenModernBertReader:
    """Batch-one true-pair NLI; no prompt, generation, fitting or calibration."""

    def __init__(self, model_directory: str | Path, asset_lock: str | Path,
                 *, max_pair_tokens: int = 512, attention: str = "sdpa"):
        if max_pair_tokens != 512:
            raise ValueError("This source version freezes the paired-token budget at 512")
        if attention not in ("sdpa", "eager"):
            raise ValueError("Only the stock CPU sdpa/eager implementations are permitted")
        self.asset_lock = verify_runtime_assets(model_directory, asset_lock)
        if self.asset_lock.get("reader_contract", {}).get("attention") != attention:
            raise ValueError("Attention implementation differs from the frozen asset contract")
        self.model_directory = str(Path(model_directory).resolve(strict=True))
        self.max_pair_tokens = max_pair_tokens
        self.attention = attention

        # Deliberately lazy: these lines execute only in an admitted worker.
        import torch
        from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

        if torch.get_num_threads() != 2:
            torch.set_num_threads(2)
        if torch.get_num_interop_threads() != 1:
            # A second attempt to set interop after parallel work fails explicitly.
            # If a root worker already set it to one, do not call the setter again.
            torch.set_num_interop_threads(1)
        if torch.get_num_threads() != 2 or torch.get_num_interop_threads() != 1:
            raise RuntimeError("CPU thread limits were not established")

        config = AutoConfig.from_pretrained(
            self.model_directory, local_files_only=True, trust_remote_code=False,
        )
        if config.architectures != ["ModernBertForSequenceClassification"]:
            raise ValueError("Unexpected model architecture")
        labels = tuple(config.id2label[index] for index in range(3))
        if labels != RAW_LABELS or config.num_labels != 3:
            raise ValueError("Unexpected native label permutation")
        config.reference_compile = False
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_directory, local_files_only=True, trust_remote_code=False,
            use_fast=True,
        )
        if not self.tokenizer.is_fast:
            raise ValueError("The frozen fast tokenizer is required")
        self.model, loading = AutoModelForSequenceClassification.from_pretrained(
            self.model_directory, config=config, local_files_only=True,
            trust_remote_code=False, use_safetensors=True, torch_dtype=torch.float32,
            attn_implementation=attention, output_loading_info=True,
        )
        if any(loading.get(key) for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")):
            raise RuntimeError("Checkpoint did not load exactly: " + json.dumps(loading, sort_keys=True))
        self.model.to(device="cpu", dtype=torch.float32)
        self.model.eval()
        if self.model.config.reference_compile is not False:
            raise RuntimeError("Reference compilation must remain disabled")
        self.torch = torch

    def score_pair(self, premise: str, hypothesis: str) -> dict:
        if not isinstance(premise, str) or not premise.strip():
            raise ValueError("An explicit nonempty source premise is required")
        if not isinstance(hypothesis, str) or not hypothesis.strip():
            raise ValueError("An explicit nonempty hypothesis is required")
        # True pair, with truncation allowed only on the source-premise side.
        # No concatenated instruction, hypothesis rewriting or causal vocabulary.
        features = self.tokenizer(
            premise, hypothesis, add_special_tokens=True, padding=False,
            truncation="only_first", max_length=self.max_pair_tokens,
            return_tensors="pt", return_attention_mask=True,
            return_token_type_ids=False,
        )
        if set(features) != {"input_ids", "attention_mask"}:
            raise ValueError("Unexpected tokenizer feature schema")
        pair_tokens = int(features["input_ids"].shape[1])
        if features["input_ids"].shape[0] != 1 or pair_tokens > self.max_pair_tokens:
            raise ValueError("Only batch-one bounded paired inputs are permitted")
        features = {key: value.to(device="cpu") for key, value in features.items()}
        with self.torch.inference_mode():
            logits_tensor = self.model(**features).logits
        if tuple(logits_tensor.shape) != (1, 3):
            raise RuntimeError("Expected one native three-way output")
        raw_logits = [float(value) for value in logits_tensor[0].cpu().tolist()]
        probabilities = canonical_probabilities(raw_logits)
        return {
            "raw_logits_E_N_C": raw_logits,
            "probabilities_E_C_N": probabilities,
            # Native argmax retains E,N,C tie order; probability storage is E,C,N.
            "typed_prediction": RAW_TYPED_LABELS[max(range(3), key=raw_logits.__getitem__)],
            "binary_yes_probability": probabilities[0],
            "binary_no_probability": probabilities[1] + probabilities[2],
            "binary_prediction": "Yes" if probabilities[0] > 0.5 else "No",
            "pair_tokens": pair_tokens,
            "max_pair_tokens": self.max_pair_tokens,
            "truncation": "only_first",
            "diagnostic_only": True,
        }

    def score_pairs(self, pairs: Iterable[tuple[str, str]]) -> list[dict]:
        return [self.score_pair(premise, hypothesis) for premise, hypothesis in pairs]
