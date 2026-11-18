"""Frozen inputs and directly inspectable measurement units."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit


HERE = Path(__file__).resolve().parent
FIXTURE_TOKENIZER = "utf8-byte-fixture-v1"
PUBLIC_WORKLOAD_SHA = "1c4cec4cfdaf847461600e0847ba48dad74ea9be988d6e56e7d6af652a1c5468"
NATIVE_TOKENIZER = "llama.cpp-/tokenize-add_special=false-parse_special=false"


def distinct(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError("duplicate JSON key")
        out[k] = v
    return out


def invalid(_):
    raise ValueError("nonfinite JSON number")


def decode(data):
    return json.loads(data, object_pairs_hook=distinct, parse_constant=invalid)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def nat(x, maximum=None):
    return type(x) is int and x > 0 and (maximum is None or x <= maximum)


def label(s):
    return isinstance(s, str) and 0 < len(s) <= 256 and s.isprintable()


def read_workload(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= 4_194_304, "workload file exceeds parser budget")
    w = decode(raw)
    require(type(w) is dict and w.get("schema") == 1 and label(w.get("mission"))
            and isinstance(w.get("population"), str) and w["population"].strip()
            and isinstance(w.get("instruction"), str) and w["instruction"].strip(), "workload identity")
    cases = w["cases"]
    require(isinstance(cases, list) and cases, "empty workload")
    exact = json.loads(raw,object_pairs_hook=distinct,parse_float=Decimal,parse_constant=invalid)
    ids = []
    for c, reference in zip(cases,exact["cases"],strict=True):
        require(isinstance(c, dict) and label(c["id"]) and isinstance(c["expected"], dict)
                and isinstance(c["prompt"], str) and c["prompt"].strip(), "invalid task")
        # Preserve decimal reference precision independently of binary floating point.
        c["expected"] = reference["expected"]
        ids.append(c["id"])
    require(len(set(ids)) == len(ids), "duplicate request")
    loads = w["concurrency"]
    require(isinstance(loads, list) and loads and all(nat(n, len(cases)) for n in loads)
            and len(set(loads)) == len(loads), "unsupported or duplicated workload concurrency")
    require(w["max_attempts_per_request"] in (1, 2) and type(w["max_attempts_per_request"]) is int,
            "this protocol supports at most one transient retry")
    for k in ("attempt_timeout_s", "max_output_tokens", "max_response_bytes"):
        require(nat(w[k]), "missing positive " + k)
    t = w["thresholds"]
    for k in ("p90_first_visible_ms", "p90_turn_ms", "p10_delivered_tokens_per_turn_second"):
        require(nat(t[k]), "invalid " + k)
    for k in ("required_quality_fraction", "required_first_attempt_completion_fraction"):
        require(type(t[k]) in (int, float) and math.isfinite(t[k]) and 0 < t[k] <= 1, "invalid " + k)
    return w, sha(raw)


def validate_authority(a, w, digest, fixture=False):
    require(a.get("schema") == 1 and a.get("locally_owned_no_forwarding") is True, "missing local authority")
    allow = {"fixture"} if fixture else {"public-synthetic-pilot", "authorized-workload-pilot"}
    require(a.get("scope") in allow and a["workload_sha256"] == digest, "authority scope/workload mismatch")
    require(a["scope"] == "authorized-workload-pilot" or digest == PUBLIC_WORKLOAD_SHA,
            "only the frozen public briefs may be labeled public or used in a public fixture package")
    u = urlsplit(a["base_url"])
    require(u.scheme == "http" and u.hostname == "127.0.0.1" and u.port and
            a["base_url"] == f"http://127.0.0.1:{u.port}", "only a literal owned loopback origin is allowed")
    require(all(label(a[k]) for k in ("model", "configuration", "target", "hardware")), "missing target identity")
    require(all(isinstance(a[k], str) and re.fullmatch("[0-9a-f]{64}", a[k])
                for k in ("model_sha256", "runtime_sha256")), "missing model/runtime hash")
    require(nat(a["max_concurrency"]) and max(w["concurrency"]) <= a["max_concurrency"],
            "not authorized for registered concurrency")
    need = len(w["cases"]) * len(w["concurrency"]) * w["max_attempts_per_request"]
    require(nat(a["max_attempts"]) and need <= a["max_attempts"], "authority has insufficient request budget")
    require(a["tokenizer"] == (FIXTURE_TOKENIZER if fixture else NATIVE_TOKENIZER), "unsupported tokenizer")
    return u.port


def accepted(text, expected):
    try:
        obj = json.loads(text,object_pairs_hook=distinct,parse_float=Decimal,parse_constant=invalid)
        # JSON true compares equal to 1 in Python. Use strict numeric/boolean types.
        def same(a, b):
            if type(a) is dict and type(b) is dict:
                return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
            if type(a) is list and type(b) is list:
                return len(a) == len(b) and all(same(i, j) for i, j in zip(a, b))
            if type(a) in (int,float,Decimal) and type(b) in (int,float,Decimal):
                return Decimal(str(a)) == Decimal(str(b))
            return type(a) is type(b) and a == b
        return same(obj, expected)
    except (ValueError, TypeError, RecursionError):
        return False
