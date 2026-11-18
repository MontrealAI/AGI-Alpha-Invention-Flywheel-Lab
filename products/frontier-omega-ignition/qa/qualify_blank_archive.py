"""Fresh archive-receiver mission over the normal signed-in blank Studio interface.

The publisher's pinned checksum inventory, operator approval policy and separate
recipient challenges are fixed before inference. The agent chooses the family
and proposes its own specification. No candidate receives the confirmation bytes.
"""
from __future__ import annotations

import base64
import binascii
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import tempfile
from zipfile import ZipFile

import qualify_live as q
from qa import qualify_blank_studio as shared
from qa.transfer import qualify as conventional

PUBLIC_COMMIT = "a44aa8535e7899aa197d6e17f567e86547792536"
ARCHIVE_NAME = "evidence/migration-artifact.zip"
ARCHIVE_SHA = "6aeed44d96b0aa72ecacd037a08179f07eed428eff7fa31c9a8659bba4626fd6"
SOURCE_URL = ("https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/"
              + PUBLIC_COMMIT + "/products/frontier-omega-ignition/" + ARCHIVE_NAME)
PURPOSE = "Check the two-file evidence handoff before our archive reviewer accepts a copy."
FILES = ("artifact.json", "example-input.json")


def publisher_data():
    path = q.PRODUCT / ARCHIVE_NAME
    if sha256(path.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError("Published evidence archive differs from the registered version")
    with ZipFile(path) as archive:
        catalog = json.loads(archive.read("SHA256SUMS.json"))
        expected = {name: catalog[name] for name in FILES}
        original = {name: archive.read(name) for name in FILES}
    if any(sha256(original[name]).hexdigest() != digest for name, digest in expected.items()):
        raise ValueError("A received published file differs from the pinned publisher's inventory")
    return expected, original


def intake(manifest):
    checksums = "\n".join(f"{manifest[name]}  {name}" for name in FILES)
    source = {"publisher": "MONTREAL.AI", "title": "Published two-file handoff inventory from SHA256SUMS.json",
              "url": SOURCE_URL, "version": PUBLIC_COMMIT, "text": checksums,
              "rights": "MONTREAL.AI public engineering artifact; operator transcribed two factual checksum "
                        "records for authorized internal evaluation. The proposed tool may use these records.",
              "retrieved_at": "2026-11-18T23:17:26Z"}
    return {"mission": {"purpose": PURPOSE, "beneficiary": "MONTREAL.AI archive reviewer (simulated)",
                        "requirements": ["Compare received file bytes by name with the two published SHA-256 records. "
                                         "Report the matching, changed, missing and unexpected filenames.",
                                         "Mark the handoff complete only if its file inventory matches exactly."],
                        "resources": {"execution_strategy": "research", "max_initial_candidates": 2,
                                      "max_model_calls": shared.CALL_CAP, "max_repairs": 1,
                                      "assets": "A recipient already has an unpacked delivery, published checksums "
                                                "and local CPU. GNU sha256sum plus a file inventory is available."},
                        "authority": {"local_model": True, "public_sources": False}},
            "sources": [source], "request_id": "blank-studio-archive-two-file-handoff"}


def encode(files):
    return {"files": {name: base64.b64encode(value).decode("ascii") for name, value in files.items()}}


def reference(manifest, payload):
    if not isinstance(payload, dict) or set(payload) != {"files"} or not isinstance(payload["files"], dict):
        return {"error": "invalid_input"}
    actual = {}
    for name, encoded in payload["files"].items():
        if not isinstance(name, str) or not 1 <= len(name) <= 240 or any(
                part in (".", "..") or not re.fullmatch(r"[A-Za-z0-9_. -]+", part) for part in name.split("/")):
            return {"error": "invalid_path"}
        if not isinstance(encoded, str):
            return {"error": "invalid_value"}
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            return {"error": "invalid_value"}
        if base64.b64encode(raw).decode("ascii") != encoded:
            return {"error": "invalid_value"}
        actual[name] = sha256(raw).hexdigest()
    return {"expected": conventional.classify(manifest, actual)}


def samples(original):
    a, b = FILES
    confirmations = [("Independent intake with one known file and a late note",
                      {a: original[a], "late-91.txt": b"late copy 91\n"}),
                     ("Independent altered input while its neighbor matches",
                      {a: original[a] + b"\nconfirmation-29", b: original[b]})]
    recipient = [("Both original files", dict(original)),
                 ("One changed file, one omitted file and an unexpected file",
                  {b: original[b] + b"\nrecipient-83", "receipt-83.txt": b"sidecar for this delivery"}),
                 ("One original file omitted", {b: original[b]})]
    return confirmations, recipient


def review(spec, manifest, reserved):
    if not isinstance(spec, dict) or spec.get("kind") != "manifest_audit" or spec.get("purpose") != PURPOSE:
        return "Proposed purpose or artifact family differs from the archive handoff"
    if spec.get("definition") != {"manifest": manifest}:
        return "Proposed reference paths or digests differ from the publisher"
    for item in spec["cases"]:
        if shared.digest(item["input"]) in reserved:
            return "A reserved archive delivery appeared in the proposed examples"
        if reference(manifest, item["input"]) != {key: item[key] for key in ("expected", "error") if key in item}:
            return "A proposed example disagrees with the independent archive reference"
    return None


def replay(work, manifest, deliveries):
    checks = []
    for i, (name, files) in enumerate(deliveries):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for label, raw in files.items():
                (root / label).write_bytes(raw)
            def candidate():
                args = [sys.executable, "-IB", str(work / "delivery/run.py"), "audit-directory", str(root)]
                return json.loads(conventional.run(args, codes=(0, 1)))
            def incumbent():
                return conventional.classify(manifest, conventional.inventory_cli(root))
            actions = [("candidate", candidate), ("sha256sum", incumbent)]
            result = {key: conventional.timed(fn) for key, fn in (actions if i % 2 == 0 else reversed(actions))}
            verdict = reference(manifest, encode(files))["expected"]
            checks.append({"condition": name, "matched": result["candidate"][0] == result["sha256sum"][0] == verdict,
                           "expected": verdict, "received": result["candidate"][0], "conventional": result["sha256sum"][0],
                           "elapsed_ms": {key: value[1] for key, value in result.items()}})
    return checks


def run(work, call, record):
    manifest, original = publisher_data()
    inputs, deliveries = samples(original)
    confirmations = [{"name": name, "input": encode(files), **reference(manifest, encode(files))}
                     for name, files in inputs]
    recipients = [encode(files) for _, files in deliveries]
    reserved = {shared.digest(row["input"]) for row in confirmations} | {shared.digest(row) for row in recipients}
    record["publisher_archive_sha256"] = ARCHIVE_SHA
    return shared.run_blank(work, call, record, request=intake(manifest), confirmations=confirmations,
                            recipient_inputs=recipients, review_draft=lambda spec: review(spec, manifest, reserved),
                            replay=lambda path: replay(path, manifest, deliveries),
                            scope="Two published checksum records and an independently assessed two-file delivery. "
                                  "Timings include invocation of each executable on the same unpacked directory. "
                                  "No beneficiary adoption, dollar benefit or new checksum algorithm is assumed.")
