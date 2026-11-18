"""Prospective research-led construction test on a real published instrument."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
import zipfile

from ignition.controller import Controller
from ignition.store import Store
from qa.qualify_model_dispatch import compare
import qualify_live as q

PUBLISHED = "a44aa8535e7899aa197d6e17f567e86547792536"
REPORT = "docs/frontier-omega-ignition/continuation/beneficiary-pursuit/REPORT.md"
ARCHIVE = REPORT.replace("REPORT.md", "scroll-normalizer.zip")
DIGEST = "03f8dbea716abd7108a03b2c947b21a13eb36617750c601733b85ae3b04de7e3"


def expect(reference, actual):
    files = {k: sha256(v).hexdigest() for k, v in actual.items()}
    matched = sorted(k for k in reference.keys() & files.keys() if reference[k] == files[k])
    changed = sorted(k for k in reference.keys() & files.keys() if reference[k] != files[k])
    missing = sorted(reference.keys() - files.keys())
    unexpected = sorted(files.keys() - reference.keys())
    return dict(matched=matched, changed=changed, missing=missing, unexpected=unexpected,
                ok=not (changed or missing or unexpected))


def case(label, reference, actual):
    return {"name": label, "input": {"files": {k: base64.b64encode(v).decode("ascii") for k, v in actual.items()}},
            "expected": expect(reference, actual)}


def brief():
    artifact = q.REPO / ARCHIVE
    if sha256(artifact.read_bytes()).hexdigest() != DIGEST:
        raise ValueError("Published release archive digest mismatch")
    with zipfile.ZipFile(artifact) as z:
        files = {entry.filename: z.read(entry) for entry in z.infolist() if not entry.is_dir()}
    manifest = {k: sha256(v).hexdigest() for k, v in files.items()}
    damaged = {**files, "operator.cpp": files["operator.cpp"] + b"\n", "unexpected.txt": b"extra"}
    del damaged["REGISTRATION.md"]
    purpose = ("Deliver a reusable offline receiver that audits the extracted scroll-normalizer files "
               "against the published release, including individual file discrepancies.")
    requirements = ["Classify matching, changed, missing and unexpected files against the supplied manifest.",
                    "Export a runnable receiver with a reproducible verification package."]
    contract = {"kind": "manifest_audit", "purpose": purpose, "definition": {"manifest": manifest},
                "cases": [case("Unmodified released instrument", manifest, files),
                          case("Controlled alteration, addition and removal", manifest, damaged)]}
    report = (q.REPO / REPORT).read_text()
    quote = next(line for line in report.splitlines() if DIGEST in line)
    source = {"publisher": "MONTREAL.AI", "title": "Published scroll-normalizer source and archive checksum",
              "url": f"https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/{PUBLISHED}/{REPORT}",
              "version": PUBLISHED, "text": quote, "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
    return {"mission": {"purpose": purpose, "requirements": requirements, "beneficiary": "Instrument recipient",
                        "resources": {"execution_strategy": "research", "max_initial_candidates": 2,
                                      "max_model_calls": 3, "max_repairs": 0,
                                      "assets": "Published archive and its trusted extracted-file digests; offline Python already available."},
                        "authority": {"local_model": True, "public_sources": False}, "construction_spec": contract},
            "sources": [source], "request_id": "pinned-archive-receiver-investigation"}


def exercise(folder, provider, record):
    body = brief()
    store = Store(folder / "state")
    ctrl = Controller(store, provider_factory=lambda: provider)
    rid, revision = ctrl.create(body)
    ctrl.advance(rid, revision)
    state = store.get(rid)
    calls = sorted(q.compact_calls(state), key=lambda c: c["recorded_at"])
    research = state.get("research") or {}
    chosen = research.get("selected") or {}
    build_call = next((c for c in state["calls"].values() if c["stage"] == "construct"), {})
    proposal = build_call.get("response", {})
    frozen_reference = (proposal.get("kind") == "manifest_audit"
                        and proposal.get("program") == {"use_frozen_manifest": True})
    record["construction_provenance"] = {
        "model_output_sha256": build_call.get("response_sha256"),
        "references_frozen_manifest": frozen_reference,
        "authority": "The original mission owns the reference files, digest inventory and withheld cases.",
        "scope": "Research proposes and selects a family. For a frozen manifest, an installed deterministic "
                 "compiler binds the authorized inventory and an existing evaluator checks the resulting tool. "
                 "The builder response supplies no new checksum algorithm.",
    }
    record.update(source_archive_sha256=DIGEST, source_url=body["sources"][0]["url"],
                  status=state["status"], error=state.get("error"), research_decision=research.get("decision"),
                  original_requirement_fit=research.get("fit"), reason=research.get("decision_reason"),
                  critic_recommendation=research.get("selection_recommendation"),
                  initial_favourite=research.get("initial_favourite"),
                  evaluated_candidates=[{"id": c["id"], "kind": c["kind"], "standing": c["standing"],
                                         "title": c["title"], "usable_sources": c["usable_sources"],
                                         "ineligible_sources": c["ineligible_sources"], "evidence_level": c["evidence_level"]}
                                        for c in research.get("candidates", [])],
                  selected={"id": chosen.get("id"), "kind": chosen.get("kind")},
                  route=(state.get("routing") or {}).get("route"),
                  effective_fallback=(state.get("routing") or {}).get("fallback"),
                  frozen_case_count=len((state.get("contract") or {}).get("spec", {}).get("cases", [])),
                  terminal_stage=state["stage"],
                  calls=calls, contract_sha256=state.get("contract_sha256"), artifact_sha256=(state.get("artifact") or {}).get("sha256"),
                  acceptance=(state.get("evaluation") or {}).get("status"),
                  conventional_comparator=(state.get("evaluation") or {}).get("comparison"),
                  construction_attempts=state.get("construction_attempts"))
    portable = {}
    control = []
    if state["status"] == "verified":
        spec = body["mission"]["construction_spec"]
        def conventional(payload):
            files = {k: base64.b64decode(v, validate=True) for k, v in payload["files"].items()}
            return expect(spec["definition"]["manifest"], files)
        control = compare(state["artifact"], spec["cases"], conventional)
        bundle = ctrl.deliver(rid, revision)
        portable = q.check_portable(bundle, folder)
        (folder / "recipient.zip").write_bytes(bundle)
        record.update(bundle_sha256=sha256(bundle).hexdigest(), recipient=portable, stdlib_checksum_comparison=control)
    return bool(record["route"] == "research" and research.get("decision") == "build"
                and chosen.get("id") and state["status"] == "verified" and record["acceptance"] == "pass"
                and [c["stage"] for c in calls] == ["discover", "challenge", "construct"]
                and all(c.get("application_model_calls") == 1 and c.get("reported_model") == q.MODEL_ALIAS
                        and c.get("mode") == "local" and c.get("status") == "completed" for c in calls)
                and control and all(c["both_match_expected"] for c in control)
                and portable.get("verified_exit") == portable.get("example_exit") == 0)
