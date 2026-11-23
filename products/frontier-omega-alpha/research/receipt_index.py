"""Reusable projection of exact statement and axiom attestations."""

from collections import Counter, defaultdict
import re

PROFILE = {
    "statement": r"^theorem (\w+) :",
    "match": r"^(con-leche|con-ron): theorem (\w+) justified by the solution$",
    "audit": r"^'(\w+)' depends on axioms: \[([^\]]+)\]$",
    "exit": r"^\s*Exit status: (\d+)$",
    "aggregate": r"^(con-leche|con-ron): accepted (\d+) declarations, (\d+) axioms justified by the solution .+ "
                 r"\((\d+) declarations accepted\) \(--verified\)$",
    "schema": "frontier-omega-alpha/lean-receipt-index-v1",
}


def assess(profile, stage, logs, allowed, requested):
    if not requested or not set(requested) <= set(stage["theorems"]):
        return False
    results = []
    for checker in ("con-leche", "con-ron"):
        log = logs[checker]
        expected = (checker, str(stage["challenge_declarations"]), str(len(stage["theorems"])),
                    str(stage["solution_declarations"]))
        summary = re.findall(profile["aggregate"], log, re.MULTILINE)
        exits = re.findall(profile["exit"], log, re.MULTILINE)
        witnesses = Counter(name for engine, name in re.findall(profile["match"], log, re.MULTILINE) if engine == checker)
        results.append(summary == [expected] and exits == ["0"] and all(witnesses[name] == 1 for name in requested))
    audits = defaultdict(list)
    for name, axioms in re.findall(profile["audit"], logs["audit"], re.MULTILINE):
        audits[name].append({word.strip() for word in axioms.split(",")})
    results.append(all(audits[name] == [set(allowed)] for name in requested))
    if "statement" in logs:
        labels = Counter(re.findall(profile["statement"], logs["statement"], re.MULTILINE))
        results.append(all(labels[name] == 1 for name in requested))
    return all(results)
