"""Small, label-invariant residual option head and separated temperature fitting.

No IDs, gold labels, split names, source names, or saved answers are accepted by
the inference transform. Training consumes explicitly marked public DEV roles;
fresh confirmation labels must never enter this module's fit function.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import Counter

import numpy as np
from scipy.optimize import minimize, minimize_scalar

VERSION = "ruvector-residual-option-head-v1"
EPS = 1e-8
FEATURE_NAMES = [
    "log_native_probability", "native_probability", "option_token_coverage",
    "option_state_jaccard", "option_state_cosine", "option_instruction_coverage",
    "option_character_trigram_cosine", "state_option_number_overlap",
    "option_length_log", "score_bucket_position", "score_bucket_center_distance",
]


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def options(question):
    kind = question.get("type")
    criteria = question.get("criteria")
    if kind == "noul":
        criteria = criteria or {}
        return ["no", "yes"], [criteria.get("false", "no"), criteria.get("true", "yes")]
    if kind == "choice":
        labels = list(criteria)
        return labels, [v if isinstance(v, str) else v["what"] for v in criteria.values()]
    if kind == "score":
        return [str(i) for i in range(len(criteria))], list(criteria)
    raise ValueError("Unsupported typed question")


def tokens(text):
    return re.findall(r"[\w]+(?:[-'][\w]+)*", text.casefold())


def cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    return dot / math.sqrt(sum(v*v for v in a.values()) * sum(v*v for v in b.values()))


def trigrams(text):
    text = " ".join(tokens(text))
    return Counter(text[i:i+3] for i in range(max(0, len(text)-2)))


def probabilities(answer, labels):
    p = answer.get("probabilities")
    if isinstance(p, list):
        p = {str(i): v for i, v in enumerate(p)}
    if not isinstance(p, dict) or set(p) != set(labels):
        raise ValueError("Exact native label distribution required")
    values = np.asarray([p[label] for label in labels], dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any() or abs(values.sum()-1) > 1e-6:
        raise ValueError("Invalid native probability distribution")
    return np.maximum(values, EPS) / np.maximum(values, EPS).sum()


def features(state, question, answer):
    labels, descriptions = options(question)
    p = probabilities(answer, labels)
    text = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    state_tokens = tokens(text)
    sset, scount = set(state_tokens), Counter(state_tokens)
    istr = set(tokens(question.get("instructions", "")))
    stris = trigrams(text)
    nums = set(re.findall(r"[-+]?\d+(?:\.\d+)?", text))
    rows = []
    for i, description in enumerate(descriptions):
        otokens = tokens(description)
        oset = set(otokens)
        onums = set(re.findall(r"[-+]?\d+(?:\.\d+)?", description))
        position = i / (len(labels)-1) if question["type"] == "score" else 0.0
        rows.append([
            float(math.log(p[i])), float(p[i]),
            len(oset & sset)/max(1, len(oset)),
            len(oset & sset)/max(1, len(oset | sset)),
            cosine(Counter(otokens), scount),
            len(oset & istr)/max(1, len(oset)),
            cosine(trigrams(description), stris),
            len(onums & nums)/max(1, len(onums)),
            math.log1p(len(otokens)), position,
            abs(position-.5) if question["type"] == "score" else 0.0,
        ])
    return np.asarray(rows, dtype=float), p


def softmax(scores):
    scores = np.asarray(scores, dtype=float)
    ex = np.exp(scores - np.max(scores))
    return ex / ex.sum()


def is_proof(answer):
    return answer.get("native_fallback_used") is False or bool(answer.get("symbolic_proof"))


def candidate_configs():
    return [
        {"id":"identity104", "head":False, "temperature":False, "uniform_mix":0.0, "l2":0.0},
        {"id":"temperature", "head":False, "temperature":True, "uniform_mix":0.0, "l2":0.0},
        {"id":"mix02-temperature", "head":False, "temperature":True, "uniform_mix":0.02, "l2":0.0},
        *[{"id":f"residual-l2-{v}-temperature", "head":True, "temperature":True, "uniform_mix":0.0, "l2":float(v)} for v in (1,10,100)],
    ]


def _iter_examples(records, roles):
    for record in records:
        if record.get("split") not in roles:
            continue
        qmap = record["input"]["questions"]
        if len(qmap) != 1:
            raise ValueError("Training records require exactly one typed question")
        for key, question in qmap.items():
            labels, _ = options(question)
            gold = record["evaluation"]["gold"]
            if not isinstance(gold, str) or gold not in labels:
                raise ValueError("Training target must be exact supplied label")
            answer = record["response"]["answers"][key]
            x, p = features(record["input"]["state"], question, answer)
            yield {"x":x, "p":p, "y":labels.index(gold), "kind":question["type"], "proof":is_proof(answer), "input_hash":canonical_sha(record["input"])}


def _scores(example, artifact):
    p = example["p"]
    scores = np.log(p)
    if artifact["config"]["head"] and not example["proof"]:
        x = (example["x"] - np.asarray(artifact["feature_mean"])) / np.asarray(artifact["feature_scale"])
        scores = scores + x @ np.asarray(artifact["weights"])
    mix = artifact["config"]["uniform_mix"]
    if mix:
        p = (1-mix)*softmax(scores) + mix/len(p)
        scores = np.log(p)
    return scores


def _group(example):
    return example["kind"] + ("|proof" if example["proof"] else "|native")


def fit(records, config):
    """Fit train head, then calibration temperature. Never read DEV/confirm gold.

    Non-fitting record inputs are hashed solely for leakage rejection. Their
    evaluation dictionaries are never read; callers may omit those dictionaries.
    """
    valid = {c["id"]:c for c in candidate_configs()}
    if config.get("id") not in valid or config != valid[config["id"]]:
        raise ValueError("Configuration must match an explicitly frozen candidate")
    roles_by_input = {}
    for record in records:
        role = record.get("split")
        if role not in {"train", "dev", "calibration", "confirmation"}:
            raise ValueError("Unknown split role")
        h = canonical_sha(record["input"])
        if h in roles_by_input:
            raise ValueError("Duplicate or cross-role input")
        roles_by_input[h] = role
    if any(r.get("split") == "confirmation" for r in records):
        raise ValueError("Confirmation records must not enter trainer")
    train = list(_iter_examples(records, {"train"}))
    calibration = list(_iter_examples(records, {"calibration"}))
    if len(train) < 12 or len(calibration) < 12:
        raise ValueError("At least12 train and12 disjoint calibration records required")
    native_train = [e for e in train if not e["proof"]]
    feat = np.concatenate([e["x"] for e in native_train], axis=0) if native_train else np.zeros((1,len(FEATURE_NAMES)))
    mean = feat.mean(axis=0)
    scale = feat.std(axis=0)
    scale[scale < .01] = 1.0
    artifact = {
        "schema_version":1, "version":VERSION, "config":copy.deepcopy(config),
        "features":FEATURE_NAMES, "feature_mean":mean.tolist(), "feature_scale":scale.tolist(),
        "weights":[0.0]*len(FEATURE_NAMES), "temperatures":{},
        "fit_scope":"Old exposed public DEV records only; no fresh or official calibration claim",
        "fit_counts":{"train":len(train), "calibration":len(calibration), "native_train":len(native_train)},
        "fit_input_hashes":{"train":[e["input_hash"] for e in train], "calibration":[e["input_hash"] for e in calibration]},
        "calibration_flag":False,
    }
    if config["head"]:
        if len(native_train) < 8:
            raise ValueError("At least8 native-fallback training examples required")
        def objective(w):
            loss = 0.0
            grad = np.zeros_like(w)
            for e in native_train:
                x = (e["x"] - mean)/scale
                p = softmax(np.log(e["p"]) + x @ w)
                loss -= math.log(max(float(p[e["y"]]), EPS))
                target = np.zeros(len(p)); target[e["y"]] = 1
                grad += x.T @ (p-target)
            penalty = float(config["l2"])
            return loss/len(native_train) + .5*penalty*np.dot(w,w), grad/len(native_train)+penalty*w
        opt = minimize(objective, np.zeros(len(FEATURE_NAMES)), jac=True, method="L-BFGS-B", options={"maxiter":200,"ftol":1e-12})
        if not opt.success or not np.isfinite(opt.x).all():
            raise ValueError("Conditional option head did not converge: "+str(opt.message))
        artifact["weights"] = opt.x.tolist()
        artifact["head_fit"] = {"iterations":int(opt.nit),"objective":float(opt.fun),"success":bool(opt.success)}
    if config["temperature"]:
        groups = {"global":calibration}
        for e in calibration:
            groups.setdefault(_group(e),[]).append(e)
        for key, examples in groups.items():
            if key != "global" and len(examples) < 12:
                continue
            def nll(log_t):
                t = math.exp(log_t)
                return sum(-math.log(max(float(softmax(_scores(e,artifact)/t)[e["y"]]),EPS)) for e in examples)/len(examples)
            opt = minimize_scalar(nll, bounds=(math.log(.1),math.log(100.0)), method="bounded", options={"xatol":1e-8})
            if not opt.success:
                raise ValueError("Temperature fit did not converge")
            artifact["temperatures"][key] = {"temperature":math.exp(float(opt.x)),"n":len(examples),"calibration_nll":float(opt.fun)}
    artifact["artifact_sha256"] = canonical_sha(artifact)
    return artifact


def validate_artifact(artifact):
    d = copy.deepcopy(artifact)
    expected = d.pop("artifact_sha256", None)
    if expected != canonical_sha(d):
        raise ValueError("Candidate artifact integrity mismatch")
    if artifact["version"] != VERSION or artifact["features"] != FEATURE_NAMES:
        raise ValueError("Candidate feature identity mismatch")
    if not all(math.isfinite(x) for x in artifact["weights"]):
        raise ValueError("Nonfinite candidate weights")


def transform(response, state, questions, artifact):
    """Inference-only transform. Its arguments contain no evaluation metadata."""
    validate_artifact(artifact)
    out = copy.deepcopy(response)
    if artifact["config"]["id"] == "identity104":
        out["candidate_id"] = "identity104"
        return out
    for key, question in questions.items():
        answer = out["answers"][key]
        labels, _ = options(question)
        x,p = features(state, question, answer)
        e = {"x":x,"p":p,"proof":is_proof(answer),"kind":question["type"]}
        entry = artifact["temperatures"].get(_group(e), artifact["temperatures"].get("global"))
        t = entry["temperature"] if entry else 1.0
        p = softmax(_scores(e,artifact)/t)
        answer["pre_head_answer"] = copy.deepcopy(response["answers"][key])
        answer["probabilities"] = dict(zip(labels,map(float,p)))
        answer["confidence"] = float(max(p))
        answer["calibrated"] = False
        answer["calibration_fit"] = bool(entry)
        answer["calibration_fit_scope"] = artifact["fit_scope"]
        answer["calibration_n"] = entry["n"] if entry else 0
        answer["temperature"] = t
        answer["candidate_head"] = artifact["config"]["id"]
        if question["type"] == "noul":
            answer["noul"] = float(p[labels.index("yes")])
        elif question["type"] == "choice":
            # Stable semantic tie-breaking, independent of supplied label names.
            _, descriptions = options(question)
            i = max(range(len(labels)),key=lambda j:(p[j],descriptions[j]))
            answer["choice"] = labels[i]
        else:
            answer["score"] = float(sum(i*v for i,v in enumerate(p))/(len(labels)-1))
    out["model"] = "ruvector-native104-residual-calibration"
    out["candidate_id"] = artifact["config"]["id"]
    out["candidate_artifact_sha256"] = artifact["artifact_sha256"]
    out["attribution"] = "Actual native RuVector BGE-small + frozen104 exact-input validators + compact trainable option residual head and separated public-DEV temperature fitting; no official calibration or rank claim"
    return out
