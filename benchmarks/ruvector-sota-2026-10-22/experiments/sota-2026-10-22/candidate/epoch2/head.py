"""Decision-preserving classification temperature; ordinal answers are identity.

The typed noul scalar is a Bernoulli probability: it changes consistently with
the distribution, while its exact argmax decision and ties are preserved. No
fresh confirmation data or labels are accepted by fitting.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np
from scipy.optimize import minimize_scalar

VERSION="ruvector-decision-preserving-temperature-v2"
EPS=1e-8


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def candidate_configs():
    return [
        {"id":"decision-preserving-temperature-global","per_type":False,"ordinal":"identity"},
        {"id":"decision-preserving-temperature-by-type","per_type":True,"ordinal":"identity"},
    ]


def options(question):
    kind=question["type"]
    if kind=="noul":return ["no","yes"]
    if kind=="choice":return list(question["criteria"])
    if kind=="score":return [str(i) for i in range(len(question["criteria"]))]
    raise ValueError("Unsupported question type")


def distribution(answer,labels,kind):
    if kind=="noul":
        value=answer["noul"]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:
            raise ValueError("Invalid native noul probability")
        p={"no":1-value,"yes":value}
        redundant=answer.get("probabilities")
        if redundant is not None and (not isinstance(redundant,dict) or set(redundant)!=set(p)
            or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in redundant.values())
            or any(abs(redundant[k]-p[k])>1e-6 for k in p)):
            raise ValueError("Inconsistent noul scalar and map")
    else:
        p=answer.get("probabilities")
        if isinstance(p,list):p={str(i):v for i,v in enumerate(p)}
    if not isinstance(p,dict) or set(p)!=set(labels):raise ValueError("Exact label distribution required")
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in p.values()):
        raise ValueError("Invalid native probabilities")
    if abs(sum(p.values())-1)>1e-3:raise ValueError("Native distribution not normalized")
    return {label:float(p[label]) for label in labels}


def argmax(p):
    return min(p,key=lambda k:(-p[k],k))


def tempered(p,temperature):
    if isinstance(temperature,bool) or not isinstance(temperature,(int,float)) or not math.isfinite(temperature) or temperature<=0:raise ValueError("Positive finite temperature required")
    labels=list(p)
    values=np.asarray([max(float(p[k]),EPS) for k in labels])
    logits=np.log(values)/temperature
    ex=np.exp(logits-max(logits));values=ex/ex.sum()
    out=dict(zip(labels,map(float,values)))
    # Float rounding close to a tie can otherwise change the decision. Identity
    # is the conservative fallback, including half-way noul and class ties.
    if argmax(out)!=argmax(p):return dict(p),"argmax_rounding_identity"
    return out,None


def fit(records,config):
    allowed={c["id"]:c for c in candidate_configs()}
    if config.get("id") not in allowed or config!=allowed[config["id"]]:raise ValueError("Unfrozen config")
    seen={};role_hashes={"train":[],"calibration":[]}
    for record in records:
        role=record.get("split")
        if role not in {"train","calibration","dev","confirmation"}:raise ValueError("Unknown split role")
        if role=="confirmation":raise ValueError("Confirmation records forbidden in fit")
        h=canonical_sha(record["input"])
        if h in seen:raise ValueError("Duplicate or cross-role input")
        seen[h]=role
        if role in role_hashes:role_hashes[role].append(h)
    examples=[]
    for record in records:
        if record["split"]!="calibration":continue
        if len(record["input"]["questions"])!=1:raise ValueError("Exactly one question per calibration record required")
        for key,q in record["input"]["questions"].items():
            if q["type"]=="score":continue
            labels=options(q);gold=record["evaluation"]["gold"]
            if not isinstance(gold,str) or gold not in labels:raise ValueError("Exact supplied target label required")
            p=distribution(record["response"]["answers"][key],labels,q["type"])
            examples.append({"kind":q["type"],"p":p,"gold":gold})
    if len(examples)<12:raise ValueError("At least12 disjoint classification calibration examples required")
    groups={"global":examples}
    if config["per_type"]:
        for kind in ("choice","noul"):
            subset=[e for e in examples if e["kind"]==kind]
            if len(subset)>=6:groups[kind]=subset
    fitted={}
    for name,items in groups.items():
        def objective(log_t):
            temperature=math.exp(log_t)
            return sum(-math.log(max(tempered(e["p"],temperature)[0][e["gold"]],1e-15)) for e in items)/len(items)
        result=minimize_scalar(objective,bounds=(math.log(.1),math.log(100)),method="bounded",options={"xatol":1e-8})
        if not result.success:raise ValueError("Temperature optimizer failed")
        fitted[name]={"temperature":math.exp(float(result.x)),"n":len(items),"calibration_nll":float(result.fun)}
    artifact={"schema_version":1,"version":VERSION,"config":copy.deepcopy(config),"temperatures":fitted,
        "fit_input_hashes":role_hashes,"fit_counts":{k:len(v) for k,v in role_hashes.items()},
        "calibration_classification_n":len(examples),
        "fit_scope":"Old exposed183 public DEV calibration role only; ordinal identity; no official or fresh calibration claim",
        "decision_invariance":"Exact legacy lexicographic argmax; floating-point tie change falls back to identity",
        "ordinal_policy":"Identity entire answer, preserving exact score field, probabilities, expected value and argmax"}
    artifact["artifact_sha256"]=canonical_sha(artifact)
    return artifact


def validate_artifact(artifact):
    d=copy.deepcopy(artifact);expected=d.pop("artifact_sha256",None)
    if expected!=canonical_sha(d) or artifact.get("version")!=VERSION:raise ValueError("Artifact integrity/version mismatch")
    allowed={c["id"]:c for c in candidate_configs()}
    if artifact.get("config")!=allowed.get(artifact.get("config",{}).get("id")):raise ValueError("Artifact config mismatch")
    for entry in artifact["temperatures"].values():
        t=entry["temperature"]
        if isinstance(t,bool) or not isinstance(t,(int,float)) or not math.isfinite(t) or not .1<=t<=100:raise ValueError("Invalid fitted temperature")


def transform(response,state,questions,artifact):
    validate_artifact(artifact)
    out=copy.deepcopy(response)
    for key,q in questions.items():
        if q["type"]=="score":continue
        answer=out["answers"][key];labels=options(q)
        p=distribution(answer,labels,q["type"])
        entry=artifact["temperatures"].get(q["type"],artifact["temperatures"]["global"])
        new,fallback=tempered(p,entry["temperature"])
        if q["type"]=="choice" and answer.get("choice") not in labels:raise ValueError("Invalid native choice field")
        answer["pre_calibration_answer"]=copy.deepcopy(response["answers"][key])
        answer["probabilities"]=new
        if q["type"]=="noul":answer["noul"]=new["yes"]
        answer["confidence"]=max(new.values())
        answer["calibrated"]=False
        answer["calibration_fit"]=True
        answer["calibration_fit_scope"]=artifact["fit_scope"]
        answer["temperature"]=entry["temperature"]
        answer["decision_preserving"]=True
        answer["calibration_fallback"]=fallback
        assert argmax(new)==argmax(p)
    out["candidate_id"]=artifact["config"]["id"]
    out["candidate_artifact_sha256"]=artifact["artifact_sha256"]
    out["model"]="ruvector-native104-decision-preserving-calibration"
    out["attribution"]="Actual native RuVector BGE-small + frozen104 exact-input validators + decision-preserving choice/noul temperature; ordinal identity; no official rank claim"
    return out
