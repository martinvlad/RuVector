"""Exact reader contracts and complete-forward receipts; no initialization."""

NEW_READER_REQUIRED = {
    "repo": "microsoft/deberta-v2-xlarge-mnli",
    "revision": "2b65bccdedcead4bc685988bcc30153d4922a789",
    "original_checkpoint_sha256": "cc41eeb065c6ab3f7e88f8dab756334abb1f77a1136fec8cf02442143934c253",
    "config_sha256": "617f9d0b46fe934497a5aab5b44b1b343a751c0c43fec3e56e26b21e76b77c60",
    "tokenizer_sha256": "5598d5e96f339a8d980c15f9afd405a2e5e1be7db41de3ed13b0f03fac1e8c17",
    "precision": "TORCH_DYNAMIC_QINT8_LINEAR_FP32_REMAINDER_FBGEMM",
    "quantization_recipe": "torch.ao.quantization.quantize_dynamic(model,{torch.nn.Linear},dtype=torch.qint8,inplace=True);eval;FP32 original loading;fbgemm",
    "threads": 2, "interop_threads": 1,
    "versions": {"torch": "2.7.1+cpu", "transformers": "4.52.4", "sentencepiece": "0.2.0",
                 "tokenizers": "0.21.4", "safetensors": "0.5.3", "protobuf": "5.29.5"},
    "model_initializations": 1, "quantization_initializations": 1,
    "initialization_model_forwards": 0,
}


PREVIOUS_READER_REQUIRED = {
    "repo": "cross-encoder/nli-deberta-v3-large",
    "revision": "bab4bc7178836f731dcfd18c06ca9def0a137712",
    "model_sha256": "821dc4407d10a9d25c20c57fcb742ddc20c09bc55c8093557091efb825256754",
}


def verify_reader_receipts(plan, receipt):
    if receipt.get("previous_reader") != receipt.get("nli"):
        raise ValueError("Previous-reader alias differs from actual epoch15 control")
    for plan_key, receipt_key in (("expected_new_reader_receipt", "new_reader"),
                                  ("expected_previous_reader_receipt", "previous_reader")):
        for key, expected in plan[plan_key].items():
            if receipt[receipt_key].get(key) != expected:
                raise ValueError("Actual reader receipt mismatch: " + receipt_key + "." + key)
    if (receipt["nli"]["revision"] != plan["expected_nli_revision"] or
            receipt["nli"]["model_sha256"] != plan["expected_nli_sha256"]):
        raise ValueError("Actual frozen previous DeBERTa-v3-large QUINT8 receipt mismatch")
    new = receipt["new_reader"]
    modules, count = new.get("quantized_linear_modules"), new.get("quantized_linear_count")
    state_sha = new.get("quantized_weight_state_sha256")
    if (type(count) is not int or count <= 0 or not isinstance(modules, list)
            or len(modules) != count
            or not all(isinstance(item, dict) and isinstance(item.get("name"), str)
                       and item["name"] and item.get("weight_dtype") == "torch.qint8"
                       and isinstance(item.get("shape"), list) and len(item["shape"]) == 2
                       and all(type(v) is int and v > 0 for v in item["shape"])
                       and isinstance(item.get("qscheme"), str) and item["qscheme"] for item in modules)
            or len({item["name"] for item in modules}) != count
            or not isinstance(state_sha, str) or len(state_sha) != 64
            or any(c not in "0123456789abcdef" for c in state_sha)):
        raise ValueError("Actual quantized module/state identity evidence missing")


def verify_complete_execution(engine, n):
    if n != 24:
        raise ValueError("Only a complete fixed24 phase can produce metrics")
    snapshot = engine.execution_snapshot()
    expected = {key: count*n for key, count in (
        ("nli_forward_pairs_attempted", 4), ("nli_forward_pairs_completed", 4),
        ("new_reader_forward_pairs_attempted", 3), ("new_reader_forward_pairs_completed", 3),
        ("previous_reader_forward_pairs_attempted", 1), ("previous_reader_forward_pairs_completed", 1))}
    if any(type(snapshot.get("counters", {}).get(key)) is not int or
           snapshot["counters"][key] != value for key, value in expected.items()):
        raise ValueError("Actual four-forward execution counters are incomplete or inconsistent")
    return snapshot
