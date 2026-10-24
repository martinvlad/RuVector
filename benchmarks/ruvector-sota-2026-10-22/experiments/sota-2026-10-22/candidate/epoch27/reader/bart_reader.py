"""DEV-only BART MNLI reader. Module import uses the standard library only.

Construct only inside the root-admitted single bounded worker. All ML imports,
tokenizer construction, safe checkpoint loading and parameter checks occur there.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

MODEL_REPOSITORY = "facebook/bart-large-mnli"
MODEL_REVISION = "d7645e127eaf1aefc7862fd59a17a5aa8558b8ce"
WEIGHT_NAME = "pytorch_model.bin"
WEIGHT_BYTES = 1629486723
WEIGHT_SHA256 = "ce253627f98f9db22af6a86efee6e905f001f7d8dc02dd14a8b4b4710c302b17"
CONFIG_SHA256 = "a0f9bcb245b680a96ccae0ad8d155f267ec3e3c971ef4a4937e52ea9ba368a86"
RAW_LABELS = ("contradiction", "neutral", "entailment")
RAW_TYPED_LABELS = ("Contradiction", "NotMentioned", "Entailment")
CANONICAL_LABELS = ("Entailment", "Contradiction", "NotMentioned")
EXPECTED_PARAMETER_COUNT = 407344131
ATTENTION = "sdpa"
REQUIRED_ASSETS = frozenset({
    "README.md", "LICENSE.fairseq", "config.json", WEIGHT_NAME,
    "tokenizer.json", "tokenizer_config.json", "merges.txt", "vocab.json",
})


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_probabilities(raw_logits: Iterable[float]) -> list[float]:
    """All-head T=1 softmax: native C,N,E -> canonical E,C,N."""
    logits = [float(value) for value in raw_logits]
    if len(logits) != 3 or not all(math.isfinite(value) for value in logits):
        raise ValueError("Expected exactly three finite native C/N/E logits")
    offset = max(logits)
    values = [math.exp(value - offset) for value in logits]
    total = sum(values)
    raw_probabilities = [value / total for value in values]
    return [raw_probabilities[2], raw_probabilities[0], raw_probabilities[1]]


def decisions(raw_logits: Iterable[float]) -> dict:
    logits = [float(value) for value in raw_logits]
    probabilities = canonical_probabilities(logits)
    return {
        "raw_logits_C_N_E": logits,
        "probabilities_E_C_N": probabilities,
        # Native index order is the explicit tie rule: C, then N, then E.
        "typed_prediction": RAW_TYPED_LABELS[max(range(3), key=logits.__getitem__)],
        "binary_yes_probability": probabilities[0],
        "binary_no_probability": probabilities[1] + probabilities[2],
        "binary_prediction": "Yes" if probabilities[0] > 0.5 else "No",
    }


def canonical_path(path: str | Path, *, directory: bool = False) -> Path:
    """Reject symlinks in every component before resolving a canonical path."""
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ValueError("Runtime paths must be absolute and canonical")
    if any(part.is_symlink() for part in (candidate, *candidate.parents)):
        raise ValueError("Symlink path components are forbidden")
    resolved = candidate.resolve(strict=True)
    if resolved != candidate:
        raise ValueError("Runtime paths must already be canonical")
    if directory and not resolved.is_dir():
        raise ValueError("Model directory is absent")
    if not directory and not resolved.is_file():
        raise ValueError("Runtime metadata/assets must be regular files")
    return resolved


def read_canonical_asset_lock(model_directory: str | Path, asset_lock: str | Path) -> tuple[Path, dict]:
    """Read direct lock or an exact public copy; inspect no asset contents."""
    directory = canonical_path(model_directory, directory=True)
    actual_lock = canonical_path(directory / "asset-lock.json")
    supplied_lock = canonical_path(asset_lock)
    actual_names = {path.name for path in directory.iterdir()}
    if actual_names != REQUIRED_ASSETS | {"asset-lock.json"}:
        raise ValueError("Unfrozen additional files exist in the model directory")
    for name in REQUIRED_ASSETS:
        canonical_path(directory / name)
    size = actual_lock.stat().st_size
    if not 0 < size <= 1024 * 1024 or supplied_lock.stat().st_size != size:
        raise ValueError("Public metadata copy differs from the bounded actual asset lock")
    actual_bytes = actual_lock.read_bytes()
    supplied_bytes = actual_bytes if supplied_lock == actual_lock else supplied_lock.read_bytes()
    if (supplied_bytes != actual_bytes or
            hashlib.sha256(supplied_bytes).digest() != hashlib.sha256(actual_bytes).digest()):
        raise ValueError("Public metadata copy differs from the actual asset lock bytes/SHA256")
    lock = json.loads(actual_bytes)
    if not isinstance(lock, dict):
        raise ValueError("Expected an actual asset-lock JSON object")
    return directory, lock


def verify_runtime_assets(model_directory: str | Path, asset_lock: str | Path) -> dict:
    """Read/hash only. Tensor contents are checked after safe load in the worker."""
    directory, lock = read_canonical_asset_lock(model_directory, asset_lock)
    if lock.get("repository") != MODEL_REPOSITORY or lock.get("revision") != MODEL_REVISION:
        raise ValueError("Asset lock checkpoint mismatch")
    if lock.get("diagnostic_only") is not True or any(
        lock.get(key) != [] for key in ("confirmation_ids", "training_ids", "calibration_ids")
    ):
        raise ValueError("Only DEV-only work with empty CONF/TRAIN/CALIB is admitted")
    files = lock.get("files", [])
    names = [item["path"] for item in files]
    if len(names) != len(REQUIRED_ASSETS) or set(names) != REQUIRED_ASSETS:
        raise ValueError("Runtime asset closure is incomplete, duplicated or unexpected")
    for item in files:
        path = directory / item["path"]
        if path.is_symlink() or not path.is_file() or path.resolve().parent != directory:
            raise ValueError("Assets must be direct regular files")
        if path.stat().st_size != item["bytes"] or file_sha256(path) != item["sha256"]:
            raise ValueError("Runtime asset identity mismatch: " + item["path"])
    weights = next(item for item in files if item["path"] == WEIGHT_NAME)
    config = next(item for item in files if item["path"] == "config.json")
    if weights["bytes"] != WEIGHT_BYTES or weights["sha256"] != WEIGHT_SHA256:
        raise ValueError("Original 2020 weight identity differs from publisher pin")
    if config["sha256"] != CONFIG_SHA256:
        raise ValueError("Pinned BART config changed")
    contract = lock.get("reader_contract", {})
    expected = {
        "max_pair_tokens": 512, "attention": ATTENTION, "batch_size": 1,
        "truncation": "only_first", "require_no_truncation": True,
        "precision": "FP32", "cpu_threads": 2, "interop_threads": 1,
        "raw_labels": ["C", "N", "E"], "canonical_permutation": [2, 0, 1],
        "temperature": 1, "use_safetensors": False, "weights_only": True,
    }
    if any(contract.get(key) != value for key, value in expected.items()):
        raise ValueError("Runtime asset lock does not bind the frozen reader contract")
    header = lock.get("static_file_header", {})
    if header.get("bytes_read") != 16 or header.get("tensor_metadata_parsed") is not False:
        raise ValueError("Original-bin bounded static header record is absent")
    with (directory / WEIGHT_NAME).open("rb") as handle:
        if handle.read(16).hex() != header.get("first_16_bytes_hex"):
            raise ValueError("Original-bin file header changed")
    return lock


class FrozenBartReader:
    """Batch-one true-pair NLI with exact safe load, no generation or calibration."""

    def __init__(self, model_directory: str | Path, asset_lock: str | Path,
                 *, max_pair_tokens: int = 512, attention: str = ATTENTION):
        if max_pair_tokens != 512 or attention != ATTENTION:
            raise ValueError("Paired budget512 and stock CPU SDPA are frozen")
        self.asset_lock = verify_runtime_assets(model_directory, asset_lock)
        self.model_directory = str(Path(model_directory).resolve(strict=True))
        self.max_pair_tokens = max_pair_tokens
        self.attention = attention

        # Deliberately lazy: no ML module import occurs until admitted construction.
        import torch
        from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

        if torch.get_num_threads() != 2:
            torch.set_num_threads(2)
        if torch.get_num_interop_threads() != 1:
            torch.set_num_interop_threads(1)
        if torch.get_num_threads() != 2 or torch.get_num_interop_threads() != 1:
            raise RuntimeError("CPU thread limits were not established")
        config = AutoConfig.from_pretrained(
            self.model_directory, local_files_only=True, trust_remote_code=False,
        )
        if config.architectures != ["BartForSequenceClassification"] or config.model_type != "bart":
            raise ValueError("Unexpected checkpoint architecture")
        if config.num_labels != 3 or tuple(config.id2label[i] for i in range(3)) != RAW_LABELS:
            raise ValueError("Unexpected native C/N/E label mapping")
        if (config.d_model, config.encoder_layers, config.decoder_layers,
                config.max_position_embeddings, config.vocab_size) != (1024, 12, 12, 1024, 50265):
            raise ValueError("Pinned BART architecture dimensions changed")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_directory, local_files_only=True, trust_remote_code=False,
            use_fast=True,
        )
        if not self.tokenizer.is_fast or type(self.tokenizer).__name__ != "BartTokenizerFast":
            raise ValueError("Frozen BartTokenizerFast is required")
        if (self.tokenizer.bos_token_id, self.tokenizer.eos_token_id,
                self.tokenizer.pad_token_id, len(self.tokenizer)) != (0, 2, 1, 50265):
            raise ValueError("Tokenizer special IDs or vocabulary changed")
        if self.tokenizer.build_inputs_with_special_tokens([17], [19]) != [0, 17, 2, 2, 19, 2]:
            raise ValueError("Native BART true-pair special-token construction changed")
        self.model, loading = AutoModelForSequenceClassification.from_pretrained(
            self.model_directory, config=config, local_files_only=True,
            trust_remote_code=False, use_safetensors=False, weights_only=True,
            torch_dtype=torch.float32, attn_implementation=attention,
            output_loading_info=True,
        )
        if any(loading.get(key) for key in (
                "missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")):
            raise RuntimeError("Original checkpoint did not load exactly: " + json.dumps(loading, sort_keys=True))
        if type(self.model).__name__ != "BartForSequenceClassification":
            raise RuntimeError("Stock native BartForSequenceClassification is required")
        if self.model.config._attn_implementation != attention:
            raise RuntimeError("Attention implementation differs from the frozen contract")
        self.model.eval()
        self.model.config.use_cache = False
        parameters = list(self.model.parameters())
        if sum(parameter.numel() for parameter in parameters) != EXPECTED_PARAMETER_COUNT:
            raise RuntimeError("Unique native parameter count differs from pinned BART architecture")
        if any(parameter.device.type != "cpu" or parameter.dtype != torch.float32 for parameter in parameters):
            raise RuntimeError("Original checkpoint must load directly as CPU FP32")
        head = self.model.classification_head
        if (tuple(head.dense.weight.shape), tuple(head.dense.bias.shape),
                tuple(head.out_proj.weight.shape), tuple(head.out_proj.bias.shape)) != (
                (1024, 1024), (1024,), (3, 1024), (3,)):
            raise RuntimeError("Native trained three-way classification head is absent")
        if self.model.training:
            raise RuntimeError("Evaluation mode was not established")
        self.torch = torch
        self.runtime_checks = {
            "parameter_count": EXPECTED_PARAMETER_COUNT, "floating_dtype": "float32",
            "device": "cpu", "classifier_shape": [3, 1024],
            "loading_info_empty": True, "weights_only": True,
            "use_safetensors": False, "tokenizer_class": type(self.tokenizer).__name__,
            "attention": attention, "cpu_threads": 2, "interop_threads": 1,
        }

    def score_pair(self, premise: str, hypothesis: str) -> dict:
        if not isinstance(premise, str) or not premise.strip():
            raise ValueError("An explicit nonempty premise is required")
        if not isinstance(hypothesis, str) or not hypothesis.strip():
            raise ValueError("An explicit nonempty hypothesis is required")
        # Count the complete native pair first. Packing is the caller's frozen
        # responsibility; reject an oversized pair before any forward call.
        full = self.tokenizer(
            premise, hypothesis, add_special_tokens=True, padding=False,
            truncation=False, return_attention_mask=False, return_token_type_ids=False,
        )
        full_ids = full["input_ids"]
        if not isinstance(full_ids, list) or not full_ids or len(full_ids) > self.max_pair_tokens:
            raise ValueError("Packed true pair exceeds512 tokens; hidden truncation is forbidden")
        features = self.tokenizer(
            premise, hypothesis, add_special_tokens=True, padding=False,
            truncation="only_first", max_length=self.max_pair_tokens,
            return_tensors="pt", return_attention_mask=True, return_token_type_ids=False,
        )
        if set(features) != {"input_ids", "attention_mask"}:
            raise ValueError("Unexpected tokenizer feature schema")
        if tuple(features["input_ids"].shape) != (1, len(full_ids)):
            raise ValueError("Only one complete untruncated native pair is permitted")
        if features["input_ids"][0].tolist() != full_ids:
            raise ValueError("Tokenizer silently truncated or altered the packed pair")
        if features["attention_mask"][0].tolist() != [1] * len(full_ids):
            raise ValueError("Unexpected padding or attention masking")
        features = {key: value.to(device="cpu") for key, value in features.items()}
        with self.torch.inference_mode():
            logits_tensor = self.model(**features, use_cache=False).logits
        if tuple(logits_tensor.shape) != (1, 3):
            raise RuntimeError("Expected exactly one native three-way output")
        result = decisions(logits_tensor[0].cpu().tolist())
        result.update({
            "pair_tokens": len(full_ids), "full_pair_tokens": len(full_ids),
            "max_pair_tokens": self.max_pair_tokens, "truncation": "only_first",
            "premise_truncated": False, "require_no_truncation": True,
            "diagnostic_only": True,
        })
        return result

    def score_pairs(self, pairs: Iterable[tuple[str, str]]) -> list[dict]:
        return [self.score_pair(premise, hypothesis) for premise, hypothesis in pairs]
