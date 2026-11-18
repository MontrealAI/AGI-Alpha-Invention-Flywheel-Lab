"""Independently match a narrow factual premise to a source, its scope and an operator's purpose.

The registry encodes reviewed interpretations of specified fragments. It is not
a general entailment model. The model remains free to invent outcomes, actions,
alternatives and tests; their scientific validity is never inferred from a citation.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
PAIR_URL = "https://doi.org/10.6084/m9.figshare.34744362.v1"
PAIR_TEXT = ("Figshare v1 provides 1,800 completed run records, issue-level outcomes, per-run token aggregates "
             "and failure labels. Reported prompt and completion tokens include repeated or cached context at "
             "full weight. Missing usage was not imputed. These are public benchmark observations.")

# Each predicate is a claim about a particular population and measurement.
# Vocabulary is used only to refuse unrelated purposes. It cannot certify an
# open-ended inference or turn an operator's public excerpt into a measurement.
PREDICATES = {
    "nomai": ("recovered_fraction", "active_labeled_upper_limit",
              r"recovered (\d+) of the (\d+) active SLSNe.*upper limit",
              ("transient", "supernova", "supernovae", "telescope", "slsn", "observing", "astronomical", "astronomique")),
    "cadbench": ("mean_reward", "benchmark_graded_score",
                 r"(\d+(?:\.\d+)?)% mean reward across the benchmark.*rather than a binary task-success rate",
                 ("cad", "freecad", "parametric", "fixture", "metrology", "cao", "paramétrique")),
    "flash": ("proof_prefill_tokens_per_second", "reported_single_h100_prefill",
              r"single H100 GPU generates proofs at around (\d+) tokens/second.*integer arithmetic in prefill",
              ("proof", "proofs", "verifier", "cryptographic", "committed", "preuve", "preuves")),
    "ecmwf": ("initialisation", "experimental_realtime_case",
              r"initialised directly from the latest observations.*without an atmospheric analysis.*single case",
              ("weather", "forecast", "forecasting", "forecasts", "meteorological", "météo", "météorologique")),
    "evolve-source": ("parallel_evaluation", "cloud_recipe",
                      r"Candidates are evaluated for correctness and performance in parallel as Cloud Batch jobs",
                      ("kernel", "kernels", "optimization", "optimisation", "solver", "simulation", "simulations", "noyau")),
    "pairing": ("issue_level_outcomes", "published_run_records",
                r"1,800 completed run records, issue-level outcomes, per-run token aggregates",
                ("issue", "issues", "coding", "agent", "agents", "pairing", "ticket")),
}
FIXED_VALUES = {"ecmwf": "observations", "evolve-source": "cloud_batch", "pairing": "present"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sources():
    return _decode_sources((HERE / "catalog.json").read_bytes())


@lru_cache(maxsize=1)
def _decode_sources(raw):
    catalog = json.loads(raw)
    indexed = {}
    for item in catalog["sources"]:
        text = " | ".join(item["fragments"])
        if digest(text.encode()) != item["excerpt_sha256"] or item["id"] in indexed:
            raise ValueError("Registered discovery excerpt identity changed")
        indexed[item["id"]] = item
    return indexed


def inputs():
    """Private workspace source imports containing only public, attributed, verified fragments."""
    return [{"publisher": s["publisher"], "url": s["url"], "title": s["title"],
             "published_at": s["published_at"], "retrieved_at": s["observed_at"],
             "version": s["version"], "text": " | ".join(s["fragments"]),
             "sha256": s["excerpt_sha256"], "source_response_sha256": s["source_response_sha256"]}
            for s in sources().values()]


def record_key(url):
    if url == PAIR_URL:
        return "pairing"
    return next((key for key, row in sources().items() if url in {row["url"], row["publication"]}), None)


def release_premise(signal):
    """General open-publisher path. Only the exact reported change can be attributed.

    The caller checks actual acquisition separately. Imported provenance fields
    alone cannot qualify a live-source observation.
    """
    url = signal.get("url", "")
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/releases/tag/[^\s?#]+", url)
    if not match or signal.get("role") != "Published release":
        return None
    origin = f"https://api.github.com/repos/{match[1]}/{match[2]}/releases?per_page=3"
    text = signal.get("text", "")
    if (not isinstance(text, str) or signal.get("origin") != origin
            or not re.fullmatch(r"[0-9a-f]{64}", str(signal.get("source_response_sha256", "")))):
        return None
    sha = digest(text.encode())
    if signal.get("sha256", sha) != sha:
        return None
    for line in text.splitlines():
        line = line.strip().lstrip("-* ").strip()
        # Preserve a whole publisher statement. Exclude headings, URLs,
        # truncated last lines and generic version announcements.
        if (16 <= len(line) <= 200 and not line.startswith("#") and "://" not in line
                and not (signal.get("excerpt_truncated") and text.endswith(line))
                and re.search(r"\b(add(?:ed|s)?|support(?:ed|s)?|fix(?:ed|es)?|introduc(?:ed|es)|remov(?:ed|es))\b",
                              line, re.I)):
            return {"source": signal.get("id"), "metric": "release_note", "value": line,
                    "scope": "publisher_reported_change", "polarity": "asserted", "excerpt_sha256": sha}
    return None


def observe(signal):
    """Bind an acquired excerpt to the reviewed source URL, bytes, predicate and scope."""
    key = record_key(signal.get("url"))
    if key is None:
        return release_premise(signal)
    text = signal.get("text")
    if not isinstance(text, str):
        return None
    if key == "pairing":
        expected = digest(PAIR_TEXT.encode())
    else:
        record = sources()[key]
        expected = record["excerpt_sha256"]
        raw_hash = signal.get("source_response_sha256")
        if raw_hash is not None and raw_hash != record["source_response_sha256"]:
            return None
    if digest(text.encode()) != expected or signal.get("sha256", expected) != expected:
        return None
    metric, scope, pattern, _ = PREDICATES[key]
    match = re.search(pattern, text)
    if not match:
        return None
    value = "/".join(match.groups()) if match.groups() else FIXED_VALUES[key]
    return {"source": signal.get("id", key), "metric": metric, "value": value, "scope": scope,
            "polarity": "asserted", "excerpt_sha256": expected}


def statement(premise):
    return f"{premise['metric']} = {premise['value']} ({premise['scope']})"


def relevant(url, purpose):
    key = record_key(url)
    words = set(re.findall(r"[^\W_]+", purpose.casefold()))
    if key:
        return bool(words.intersection(PREDICATES[key][3]))
    path = urlsplit(url).path.strip("/").split("/")
    if len(path) >= 5 and urlsplit(url).hostname == "github.com" and path[2:4] == ["releases", "tag"]:
        # No automatic generalization from a software version to a generic
        # research objective. A mission naming the project can test its claim.
        name = path[1].casefold()
        return bool(re.search(r"(?<![\w.-])" + re.escape(name) + r"(?![\w.-])", purpose.casefold()))
    return False


def qualified(signal):
    return (signal.get("status", "active") == "active" and signal.get("access", "available") == "available"
            and signal.get("current_observation", True) and not signal.get("event_pending", False))


def adjudicate(claim, signal, purpose):
    if not isinstance(claim, dict) or not signal or not qualified(signal):
        return "ineligible"
    premise = observe(signal)
    if not premise:
        return "unregistered_or_changed"
    if claim.get("source") != premise["source"] or claim.get("metric") != premise["metric"]:
        return "wrong_attribution"
    if not relevant(signal["url"], purpose):
        return "immaterial"
    keys = ("value", "scope", "polarity")
    if any(claim.get(key) != premise[key] for key in keys):
        return "contradicted"
    return "supported"


def denies_available_issues(value):
    """Recognize the registered denial in free prose; other prose remains unadjudicated."""
    noun = r"(?:issue[- ]level|per[- ]issue) (?:data|measurements?|results?|outcomes?|records?)"
    negative = r"(?:unavailable|absent|missing|not (?:available|provided|reported|present))"
    return bool(re.search(noun + r" (?:are |were |is |was )?" + negative + r"\b|"
                          + r"\b(?:no|without) (?:eligible |available )?" + noun, value, re.I))


def review(candidate, signals, purpose, eligible_refs):
    """Review the change and its citations without certifying the proposed productive arrangement."""
    indexed = {s["id"]: s for s in signals}
    bindings = candidate.get("evidence", [])
    if not isinstance(bindings, list) or len(bindings) > 32 or any(not isinstance(c, dict) for c in bindings):
        raise ValueError("Supply at most 32 factual premises")
    checks = []
    for claim in bindings:
        ref = claim.get("source")
        if not isinstance(ref, str):
            raise ValueError("Each factual premise must name its source ID")
        status = adjudicate(claim, indexed.get(ref), purpose) if ref in eligible_refs else "ineligible"
        if status == "supported":
            # A source-grounded factual change uses exactly this reviewed statement.
            # Unsupported free prose cannot ride on an otherwise true typed citation.
            source_claim = statement(claim)
            if source_claim not in candidate.get("change", "").split("\n"):
                status = "change_not_bound"
        checks.append({"claim": claim, "status": status})
    asserted = {statement(c["claim"]) for c in checks if c["status"] == "supported"}
    if asserted and set(candidate.get("change", "").splitlines()) != asserted:
        for item in checks:
            if item["status"] == "supported":
                item["status"] = "change_not_bound"
    denial = any(denies_available_issues(candidate.get(k, "")) for k in ("change", "obstruction", "outcome", "route"))
    if denial:
        for signal in signals:
            if (qualified(signal) and record_key(signal["url"]) == "pairing" and observe(signal)
                    and relevant(signal["url"], purpose)):
                checks.append({"claim": {"source": signal["id"], "metric": "issue_level_outcomes",
                                         "value": "absent"}, "status": "contradicted"})
    supported = {c["claim"]["source"] for c in checks if c["status"] == "supported"}
    return {"checks": checks, "supported_sources": sorted(supported),
            "unbound_sources": sorted(set(candidate.get("sources", [])) - supported),
            "open_proposal": "hypothesis pending independent action and decisive test"}
