"""Qualify the installed scroll normalizer by executing its exact offline recipient."""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile

from .fixed_delivery import archive
from .store import PRODUCT, Conflict, StateError, digest, timestamp

PRESET = PRODUCT / "examples" / "scroll.json"
SOURCE = PRODUCT / "invention" / "scroll_normalization"
MEMBERS = ("scroll_tool.py", "operator.cpp", "candidate.patch", "upstream.zip", "SOURCE-LICENSE.txt",
           "REGISTRATION.md", "README.md", "result.json", "acquire.py", "benchmark.py")
FIELD_MEMBER = "mission-field.json"
FIELD_SCOPE = {"scroll_normalization": "registered-public-cohort", "data_use": "noncommercial research only"}
SCOPE = "Offline numerical compatibility of the exported CPU recipient"
INTERACTIVE_BYTES = 256 * 1024
FIELD_SECONDS = 15 * 60  # Bound of this registered public cohort only.


def _source_files():
    return {name: (SOURCE / name).read_bytes() for name in MEMBERS}


def _source_digest(files):
    inputs = {**files, "offline_preset": PRESET.read_bytes(),
              "research_preset": (PRESET.parent / "scroll_research.json").read_bytes()}
    return digest({k: hashlib.sha256(data).hexdigest() for k, data in inputs.items()})


def identity():
    return _source_digest(_source_files())


def _package(state):
    mission = state["mission"]
    expected = json.loads(PRESET.read_text())["mission"]
    if (mission["purpose"] != expected["purpose"] or mission["requirements"] != expected["requirements"]
            or mission["resources"] not in (expected["resources"], FIELD_SCOPE) or mission["construction_spec"] or state["sources"]
            or state.get("inherited") or set(mission["time"]) - {"deadline"}):
        raise StateError("Use the registered offline scroll package scope. Run authorized input locally in the recipient.")
    if mission["resources"] == FIELD_SCOPE and mission["authority"].get("public_sources") is not True:
        raise StateError("The public research cohort requires an explicit public_sources permission and research-only use.")
    files = _source_files()
    source_sha = _source_digest(files)
    if (state.get("specialist_source") != source_sha or state["input_sha256"] != digest([mission, state["sources"]])):
        raise Conflict("Scroll source or mission changed. Amend this mission before qualification.")
    if state.get("scroll_field"):
        files[FIELD_MEMBER] = json.dumps(state["scroll_field"], sort_keys=True, allow_nan=False).encode() + b"\n"
    data = archive(files)
    contract = {"acceptance_scope": SCOPE, "input_sha256": state["input_sha256"],
                "source_sha256": source_sha, "package_sha256": hashlib.sha256(data).hexdigest()}
    return data, contract


def _execute(root, command):
    # No private credentials/configuration inherited. Compilation and inputs stay in the temporary recipient.
    proc = subprocess.run([sys.executable, "-IB", str(root / "scroll_tool.py"), *command, "--cache", str(root / ".compiled")], cwd=root,
                          env={"PATH": os.defpath, "HOME": str(root), "TMPDIR": str(root)},
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode:
        lines = proc.stderr.decode(errors="replace").splitlines()
        raise StateError("Offline scroll recipient failed: " + (lines[-1][:400] if lines else f"exit {proc.returncode}"))
    return proc.stdout


def _normalize(root, pixels):
    src, out = root / "input.u8", root / "normalized.f32"
    src.write_bytes(pixels)
    _execute(root, ["normalize", "--input", str(src), "--output", str(out)])
    if not out.is_file() or out.stat().st_size != 4 * len(pixels):
        raise StateError("Recipient returned the wrong count of float32 values.")
    return out.read_bytes()


def _unpack(data, root):
    with ZipFile(io.BytesIO(data)) as z:
        if sorted(z.namelist()) not in (sorted(MEMBERS), sorted((*MEMBERS, FIELD_MEMBER))):
            raise Conflict("Unexpected member in the scroll recipient.")
        z.extractall(root)


def _qualify(data):
    with tempfile.TemporaryDirectory(prefix="ignition-scroll-") as folder:
        root = Path(folder)
        _unpack(data, root)
        checks = json.loads(_execute(root, ["self-check"]))
        if checks != {"cases": 32, "comparators": ["base", "incumbent", "candidate"], "passed": True}:
            raise StateError("The recipient did not qualify all 32 registered numerical controls.")
        # Preregistered numerical cross-check independent of the candidate and incumbent code:
        # 90 tens and 10 fourteens have median 10, MAD 0 and population standard deviation 1.2.
        pixels = bytes([10] * 90 + [14] * 10)
        actual = _normalize(root, pixels)
        expected = struct.pack("<100f", *([0.0] * 90 + [4.0 / 1.2] * 10))
        if actual != expected:
            raise StateError("The recipient failed the independent zero-MAD numerical control.")
    return {"acceptance_scope": SCOPE, "recipient_self_check": checks,
            "independent_control": "90 values of 10 and 10 values of 14",
            "control_output_sha256": hashlib.sha256(actual).hexdigest(),
            "field_measurement": "This offline recipient qualification ran numerical controls only.",
            "beneficiary_acceptance": None, "payment_received": None}


def _research(controller, state, data):
    """Acquire the fixed public cohort and time it once. Export never calls this function."""
    started = timestamp()
    clock = time.monotonic()
    result = {"observed_at": started, "research_use": "noncommercial", "receipt": None}
    with tempfile.TemporaryDirectory(prefix="ignition-scroll-field-") as folder:
        root = Path(folder)
        _unpack(data, root)
        env = {"PATH": os.defpath, "HOME": str(root), "TMPDIR": str(root)}
        # Only transport settings go to the registered public-source reader.
        env.update({k: v for k, v in os.environ.items()
                    if k.lower() in {"https_proxy", "http_proxy", "all_proxy", "no_proxy", "ssl_cert_file"}})
        def remaining():
            seconds = FIELD_SECONDS - (time.monotonic() - clock)
            if seconds <= 0:
                raise StateError("The registered field experiment exhausted its 15-minute budget.")
            return seconds

        try:
            controller._guard(state)
            fetch = subprocess.run([sys.executable, "-IB", "acquire.py"], cwd=root, env=env, capture_output=True,
                                   timeout=remaining())
            if fetch.returncode:
                raise StateError(f"Registered public acquisition exited {fetch.returncode}.")
            controller._guard(state)
            acquired = json.loads((root / "observations/manifest.json").read_bytes())
            enrolled = json.loads((root / "result.json").read_bytes())
            # Frozen original and crop digests pin all fetched bytes as well as absent members.
            tags = ("row", "col", "url", "available", "size", "sha256", "crop_sha256", "status")
            def enrollment(rows):
                return [[r.get(k) for k in tags] for r in rows]
            if (acquired["source"] != enrolled["source_zarray"] or
                    enrollment(acquired["cases"]) != enrollment(enrolled["cases"])):
                raise StateError("Retrieved observations differ from the registered source cohort.")
            bench = subprocess.run([sys.executable, "-IB", "benchmark.py", "observations", "fresh.json"],
                                   cwd=root, env={"PATH": os.defpath, "HOME": str(root), "TMPDIR": str(root)},
                                   capture_output=True, timeout=remaining())
            if bench.returncode not in (0, 2) or not (root / "fresh.json").is_file():
                raise StateError(f"Benchmark exited {bench.returncode} without a complete accepted receipt.")
            receipt = json.loads((root / "fresh.json").read_bytes())
            if (enrollment(receipt["cases"]) != enrollment(acquired["cases"])
                    or receipt["registration_sha256"] != hashlib.sha256((root / "REGISTRATION.md").read_bytes()).hexdigest()
                    or receipt["variants"] != enrolled["variants"] or receipt["summary"]["registered"] != 18
                    or (bench.returncode == 0) is not receipt["summary"]["component_gate_passed"]):
                raise StateError("Fresh benchmark receipt does not bind the registered sources, code and outcome.")
            result["receipt"] = receipt
        except Conflict:
            raise
        except subprocess.TimeoutExpired:
            result["error"] = "The registered field experiment reached its 15-minute budget."
        except (ValueError, OSError, KeyError) as exc:
            result["error"] = str(exc)[:400]
    result["elapsed_seconds_including_acquisition"] = round(time.monotonic() - clock, 6)
    result["observed_at_completion"] = timestamp()
    return result


def _field_decision(field):
    if not field or not field.get("receipt"):
        return {"disposition": "needs_evidence",
                "reason": (field or {}).get("error") or "Only numerical controls were run in this revision.",
                "next_action": "Reproduce the registered cohort under an explicit research-only source grant."}
    summary = field["receipt"]["summary"]
    if not summary["component_gate_passed"]:
        return {"disposition": "withhold", "reason": "The fresh registered field comparison failed its component gate.",
                "next_action": "Preserve the negative and compare the existing incumbent on another registered use case."}
    return {"disposition": "ready_for_beneficiary_review",
            "reason": "The fresh research-only benchmark passed for this CPU operator on its registered cohort.",
            "next_action": "Request authorization for a beneficiary's representative whole-pipeline trial and "
                           "validate distribution rights and any award criteria before an offer."}


def run(controller, state):
    reason = "Build the source-bound CPU package and run its actual recipient against numerical controls."
    state["routing"] = {"strategy": "direct", "route": "direct", "method": "specialist", "reason": reason}
    controller._step(state, "construction", reason)
    data, contract = _package(state)
    if state["mission"]["resources"] == FIELD_SCOPE and not state.get("scroll_field"):
        if state.get("scroll_field_started"):
            field = {"receipt": None, "error": "A prior field attempt was interrupted without a committed receipt. "
                     "Open a new revision to repeat the measurement."}
        else:
            state["scroll_field_started"] = timestamp()
            controller._step(state, "field_trial", "Beginning the authorized public research cohort.")
            field = _research(controller, state, data)
        state["scroll_field"] = field
        controller._step(state, "field_trial", "Saved the field outcome and released temporary scan inputs.")
        data, contract = _package(state)
    result = _qualify(data)
    state["field_decision"] = _field_decision(state.get("scroll_field"))
    if state.get("scroll_field"):
        result["field_measurement"] = {"observation_sha256": digest(state["scroll_field"]),
                                       "archive_member": FIELD_MEMBER}
    state.update(contract=contract, contract_sha256=digest(contract), scroll_result=result,
                 evaluation={"status": "pass", "scope": SCOPE, "receipt_sha256": digest(result)},
                 artifact={"kind": "scroll_normalizer", "sha256": contract["package_sha256"]})
    controller._step(state, "verification", "Exported recipient passed offline numerical checks. "
                     "Field disposition is recorded separately from acceptance and payment.", "verified")


def deliver(state, payload, trial):
    data, contract = _package(state)
    result = state.get("scroll_result")
    if (not isinstance(result, dict) or state["contract"] != contract or state["contract_sha256"] != digest(contract)
            or state["artifact"] != {"kind": "scroll_normalizer", "sha256": hashlib.sha256(data).hexdigest()}
            or state["evaluation"] != {"status": "pass", "scope": SCOPE, "receipt_sha256": digest(result)}):
        raise Conflict("The saved receipt differs from the qualified scroll package.")
    if not trial:
        recovered = _qualify(data)
        if state.get("scroll_field"):
            recovered["field_measurement"] = {"observation_sha256": digest(state["scroll_field"]),
                                              "archive_member": FIELD_MEMBER}
        if recovered != result or state.get("field_decision") != _field_decision(state.get("scroll_field")):
            raise Conflict("The exported scroll package failed independent requalification.")
        return data
    if payload == {}:
        return _qualify(data)
    if (not isinstance(payload, dict) or set(payload) != {"pixels_base64", "rights_basis"}
            or not isinstance(payload["rights_basis"], str) or not payload["rights_basis"].strip()
            or not isinstance(payload["pixels_base64"], str)
            or len(payload["pixels_base64"]) > 4 * ((INTERACTIVE_BYTES + 2) // 3)):
        raise StateError("Supply pixels_base64 and a rights_basis for the selected local test. Use the ZIP for larger patches.")
    try:
        pixels = base64.b64decode(payload["pixels_base64"], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise StateError("pixels_base64 must encode raw single-channel uint8 values.") from exc
    if not 0 < len(pixels) <= INTERACTIVE_BYTES:
        raise StateError("Interactive samples support 1–262144 pixels. Use the ZIP for larger patches.")
    with tempfile.TemporaryDirectory(prefix="ignition-scroll-input-") as folder:
        root = Path(folder)
        _unpack(data, root)
        output = _normalize(root, pixels)
    return {"format": "float32_le", "count": len(pixels), "output_sha256": hashlib.sha256(output).hexdigest(),
            "output_base64": base64.b64encode(output).decode("ascii")}
