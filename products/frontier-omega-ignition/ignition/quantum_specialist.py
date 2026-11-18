"""Construct and qualify an offline reversible multiplier under a frozen mission contract."""

import hashlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

from .fixed_delivery import archive
from .store import PRODUCT, Conflict, StateError, canonical, digest

SOURCE = PRODUCT / "invention" / "quantum_multiplier"
PRESET = PRODUCT / "examples" / "quantum.json"
MEMBERS = (
    "LICENSE.tensor",
    "PROTOCOL.md",
    "SENSITIVITY.md",
    "README.md",
    "RECEIPT.json",
    "compile_multiplier.py",
    "check_rotations.py",
    "verify_multiplier.py",
    "test_kickmix.py",
    "truth_table.py",
    "replay.py",
    "multiplier.kmx",
    "scheme42.txt",
)
KIND = "quantum_multiplier"
SCOPE = "Offline field arithmetic and gate counts of a source-bound recipient"


def _files():
    return {name: (SOURCE / name).read_bytes() for name in MEMBERS}


def _identity(files, preset):
    return digest(
        {
            key: hashlib.sha256(value).hexdigest()
            for key, value in {**files, "preset": preset}.items()
        }
    )


def identity():
    return _identity(_files(), PRESET.read_bytes())


def _package(state):
    public = _files()
    preset = PRESET.read_bytes()
    mission = state["mission"]
    expected = json.loads(preset)["mission"]
    resources = mission["resources"]
    if (
        mission["purpose"] != expected["purpose"]
        or mission["requirements"] != expected["requirements"]
        or set(resources) != {KIND}
        or mission["construction_spec"]
        or state["sources"]
        or state.get("inherited")
        or set(mission["time"]) - {"deadline"}
    ):
        raise StateError(
            "Use the registered local quantum multiplier purpose, requirements and resources."
        )
    request = resources[KIND]
    if (
        not isinstance(request, dict)
        or set(request) != {"minimum_cnot_improvement_bps"}
        or type(request["minimum_cnot_improvement_bps"]) is not int
        or not 1 <= request["minimum_cnot_improvement_bps"] <= 10000
    ):
        raise StateError(
            "Specify a CNOT improvement threshold between 1 and 10000 basis points."
        )
    if state.get("specialist_source") != _identity(public, preset) or state[
        "input_sha256"
    ] != digest([mission, state["sources"]]):
        raise Conflict(
            "Source or mission changed. Amend the quantum study before replay."
        )
    public["REQUEST.json"] = (canonical(request) + "\n").encode()
    packed = archive(public)
    contract = {
        "acceptance_scope": SCOPE,
        "input_sha256": state["input_sha256"],
        "source_sha256": state["specialist_source"],
        "minimum_cnot_improvement_bps": request["minimum_cnot_improvement_bps"],
        "package_sha256": hashlib.sha256(packed).hexdigest(),
    }
    return packed, contract


def _execute(root, script, *args):
    proc = subprocess.run(
        [sys.executable, "-IB", str(root / script), *args],
        cwd=root,
        check=False,
        env={},
        capture_output=True,
        text=True,
    )
    if proc.returncode:
        lines = proc.stderr.splitlines()
        raise StateError(
            "Offline arithmetic verification failed. "
            + (lines[-1][:360] if lines else f"exit {proc.returncode}")
        )
    return json.loads(proc.stdout)


def _qualify(package, contract):
    with tempfile.TemporaryDirectory(prefix="ignition-quantum-") as tmp:
        root = Path(tmp)
        with ZipFile(io.BytesIO(package)) as z:
            if sorted(z.namelist()) != sorted((*MEMBERS, "REQUEST.json")):
                raise Conflict("Unexpected quantum recipient files.")
            z.extractall(root)
        result = _execute(root, "replay.py")
        truth = _execute(root, "truth_table.py", "multiplier.kmx")
        candidate = result["circuits"]["flexible_on_stronger_order.kmx"]
        if (
            truth["circuit_sha256"] != candidate["sha256"]
            or truth["gates"] != candidate["gates_checked"]
            or truth["assignments_covered"] != candidate["assignments_covered"]
            or not truth["arbitrary_target_identity_proved"]
        ):
            raise Conflict(
                "The independent truth table disagrees with the delivered circuit."
            )
    minimum = contract["minimum_cnot_improvement_bps"]
    conventional = result["strongest_conventional_cnot"]
    achieved = (
        conventional - result["followup_cnot"]
    ) * 10000 >= minimum * conventional
    if (
        result["requested_cnot_threshold_met"] != achieved
        or result["minimum_cnot_improvement_bps"] != minimum
    ):
        raise Conflict("The recipient did not use the frozen CNOT threshold.")
    return {
        **result,
        "independent_truth_table": truth,
        "beneficiary_acceptance": None,
        "payment_received": None,
    }


def _decision(result):
    return {
        "disposition": "withhold",
        "reason": f"The strongest conventional circuit and this multiplier both use {result['qubits']} qubits and {result['toffolis']} Toffolis. CNOT reductions alone earn no contest score.",
        "next_action": "Retain the verified multiplier and evaluate the next candidate. Reopen entry if a full decoder reduces a scored resource and can be qualified under authorized rules.",
    }


def run(controller, state):
    data, contract = _package(state)
    state.update(
        routing={
            "strategy": "direct",
            "route": "direct",
            "method": "specialist",
            "reason": "Construct reversible arithmetic from the pinned rank decomposition and compare full gate lists.",
        },
        contract=contract,
        contract_sha256=digest(contract),
    )
    controller._step(
        state,
        "construction",
        "Froze the arithmetic contract. Executing its independent recipient and conventional controls.",
    )
    result = _qualify(data, contract)
    state.update(
        quantum_result=result,
        field_decision=_decision(result),
        evaluation={"status": "pass", "scope": SCOPE, "receipt_sha256": digest(result)},
        artifact={"kind": KIND, "sha256": contract["package_sha256"]},
    )
    controller._step(
        state,
        "verification",
        "Recipient verified. Withhold the competition entry on measured resource counts.",
        "verified",
    )


def deliver(state, payload, trial):
    if trial and payload != {}:
        raise StateError(
            "Pass {} to rerun the exact frozen recipient or amend its threshold."
        )
    data, contract = _package(state)
    saved = state.get("quantum_result")
    if (
        not isinstance(saved, dict)
        or state.get("contract") != contract
        or state["contract_sha256"] != digest(contract)
        or state.get("artifact") != {"kind": KIND, "sha256": contract["package_sha256"]}
        or state.get("evaluation")
        != {"status": "pass", "scope": SCOPE, "receipt_sha256": digest(saved)}
    ):
        raise Conflict("Quantum receipt differs from the source-bound revision.")
    result = _qualify(data, contract)
    if result != saved or state.get("field_decision") != _decision(result):
        raise Conflict(
            "Quantum recipient or previously recorded decision failed requalification."
        )
    return result if trial else data
