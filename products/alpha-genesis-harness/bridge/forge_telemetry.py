# SPDX-License-Identifier: Apache-2.0
"""Exact estimability with sparse bad readings, plus independent trial cohorts."""
from __future__ import annotations

from fractions import Fraction
import hashlib
from itertools import combinations
import json
from math import comb, gcd
from pathlib import Path
import random
import re
import sys
import time

if __package__:
    from .forge_sandbox import SandboxError, execute
else:
    from forge_sandbox import SandboxError, execute

CONTRACT = "rational-telemetry/v1"
TASK = (
    "A is a nonempty integer matrix; y gives one integer observation per row; target is "
    "an integer row vector. State x ranges over all rational vectors. A state is compatible if "
    "at most faults rows have A[i] dot x != y[i]. Decide the exact value of target dot x over "
    "ALL compatible states. Return {\"status\":\"inconsistent\"} if none exist, "
    "{\"status\":\"ambiguous\"} if two compatible states yield different values, or "
    "{\"status\":\"determined\",\"value\":\"-5/7\"} if the value is identical across all compatible "
    "states. Encode exact rational values as a reduced numerator/denominator or integer string. "
    "Do not assume the whole state is unique, that there is a faulty channel, or that errors are small."
)
FAMILIES = ("redundancy", "free-direction", "competing", "incompatible")
RATIONAL = re.compile(r"[+-]?[0-9]+(?:/[1-9][0-9]*)?\Z")


def fingerprint(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def validate(data):
    if not isinstance(data, dict) or set(data) != {"A", "y", "target", "faults"}:
        raise ValueError("Use A, y, target and faults. Utilisez A, y, target et faults.")
    A, y, target, faults = (data[key] for key in ("A", "y", "target", "faults"))

    def vector(value, length):
        return (isinstance(value, list) and len(value) == length
                and all(type(item) is int and item.bit_length() <= 32 for item in value))

    if (not isinstance(A, list) or not 1 <= len(A) <= 32 or not isinstance(target, list)
            or not 1 <= len(target) <= 16 or not vector(target, len(target))
            or not vector(y, len(A)) or not all(vector(row, len(target)) for row in A)
            or type(faults) is not int or not 0 <= faults <= len(A) or comb(len(A), faults) > 512):
        raise ValueError("Unsupported matrix dimensions, coefficients or fault subsets. "
                         "Dimensions, coefficients ou sous-ensembles de pannes hors contrat.")
    return A, y, target, faults


def normalize(answer):
    if not isinstance(answer, dict) or not isinstance(answer.get("status"), str):
        raise ValueError("Invalid result format. Format de résultat invalide.")
    status = answer["status"]
    if status in {"inconsistent", "ambiguous"} and set(answer) == {"status"}:
        return {"status": status}
    if status == "determined" and set(answer) == {"status", "value"}:
        value = answer["value"]
        if type(value) is int:
            value = str(value)
        if isinstance(value, str) and len(value) <= 512 and RATIONAL.fullmatch(value):
            return {"status": status, "value": str(Fraction(value))}
    raise ValueError("Invalid status or exact rational value. Verdict ou valeur rationnelle invalide.")


def _elimination(rows, width):
    """Fraction-free row basis. A zero coefficient row with nonzero RHS is impossible."""
    basis = {}
    for source in rows:
        row = list(source)
        for pivot, existing in basis.items():
            scale = row[pivot]
            if scale:
                row = [existing[pivot] * a - scale * b for a, b in zip(row, existing)]
                divisor = gcd(*row)
                if divisor > 1:
                    row = [value // divisor for value in row]
        pivot = next((index for index in range(width) if row[index]), None)
        if pivot is None:
            if row[-1]:
                return None
        else:
            basis[pivot] = row
    return basis


def verify(data):
    """Independent exact augmented-rank and row-space test over every admissible omission."""
    A, y, target, faults = validate(data)
    observations = list(zip(A, y))
    values = set()
    for omitted in combinations(range(len(A)), faults):
        ignored = set(omitted)
        basis = _elimination((row + [reading] for i, (row, reading) in enumerate(observations)
                              if i not in ignored), len(target))
        if basis is None:
            continue
        residual = [Fraction(item) for item in target] + [Fraction(0)]
        for pivot, row in basis.items():
            scale = residual[pivot] / row[pivot]
            residual = [a - scale * b for a, b in zip(residual, row)]
        if any(residual[:-1]):
            return {"status": "ambiguous"}
        values.add(-residual[-1])
        if len(values) > 1:
            return {"status": "ambiguous"}
    if not values:
        return {"status": "inconsistent"}
    return {"status": "determined", "value": str(values.pop())}


def conventional(data):
    """Separate incumbent. FLINT rational RREF gives each affine solution image."""
    from flint import fmpq, fmpq_mat

    A, y, target, faults = validate(data)
    width = len(target)
    values = set()
    for remaining in combinations(range(len(A)), len(A) - faults):
        if not remaining:
            if any(target):
                return {"status": "ambiguous"}
            values.add("0")
            continue
        augmented = [A[index] + [y[index]] for index in remaining]
        rref, rank = fmpq_mat(augmented).rref()
        residual, value = list(map(fmpq, target)), fmpq(0)
        inconsistent = False
        for row in range(rank):
            pivot = next(index for index in range(width + 1) if rref[row, index])
            if pivot == width:
                inconsistent = True
                break
            scale = residual[pivot]
            residual = [coefficient - scale * rref[row, index]
                        for index, coefficient in enumerate(residual)]
            value += scale * rref[row, width]
        if inconsistent:
            continue
        if any(residual):
            return {"status": "ambiguous"}
        values.add(str(value))
        if len(values) > 1:
            return {"status": "ambiguous"}
    if not values:
        return {"status": "inconsistent"}
    return {"status": "determined", "value": values.pop()}


def candidate(source, data):
    validate(data)
    result = execute(source, data)
    result["answer"] = normalize(result["answer"])
    return result


def score(source, data):
    start = time.perf_counter()
    expected = verify(data)
    row = {"expected": expected, "verifier_wall_seconds": time.perf_counter() - start, "passed": False}
    start = time.perf_counter()
    try:
        result = candidate(source, data)
        row["actual"] = result["answer"]
        row["passed"] = expected == row["actual"]
    except (SandboxError, ValueError) as error:
        row["error"] = getattr(error, "code", "INVALID_RESULT")
        if isinstance(error, SandboxError) and error.code == "CANDIDATE_ERROR":
            row["candidate_feedback"] = str(error)
    row["application_wall_seconds"] = time.perf_counter() - start
    return row


def _sample(randomizer, family, width, faults, index):
    denominator = randomizer.randint(2, 7)
    latent = [randomizer.randint(-13, 13) for _ in range(width)]
    target = [randomizer.randint(-3, 3) for _ in range(width)]
    free = family in {"free-direction", "competing"} or (family == "redundancy" and index % 2 == 0)
    if free:
        target[-1] = 0 if family == "redundancy" else 1
    elif not any(target):
        target[0] = 1
    rows = []
    for _ in range(width + 2 * faults + 3):
        row = [denominator * randomizer.randint(-4, 4) for _ in range(width)]
        if free:
            row[-1] = 0
        rows.append([row, sum(a * b for a, b in zip(row, latent)) // denominator])
    if family == "competing":
        for position in range(2 * faults):
            row = [0] * (width - 1) + [randomizer.choice((-denominator, denominator))]
            alternative = latent[-1] + (5 if position >= faults else 0)
            rows.append([row, row[-1] * alternative // denominator])
    elif family == "incompatible":
        row = [denominator] + [0] * (width - 1)
        rows += [[row, latent[0] + change] for change in range(faults + 2)]
    else:
        for position in randomizer.sample(range(len(rows)), faults if index % 3 else 0):
            rows[position][1] += randomizer.choice((-7, -3, 5, 11))
    randomizer.shuffle(rows)
    return {"A": [row for row, _reading in rows], "y": [reading for _row, reading in rows],
            "target": target, "faults": faults}


def cohort(seed, stage):
    if stage not in {"development", "qualification", "transfer"}:
        raise ValueError("Unknown cohort. Cohorte inconnue.")
    rng = random.Random(seed)
    count, sizes, max_faults = {
        "development": (2, (2, 3), 1),
        "qualification": (6, (3, 5), 1),
        "transfer": (4, (5, 7), 2),
    }[stage]
    cases = []
    for family in FAMILIES:
        for index in range(count):
            width = rng.randint(*sizes)
            faults = rng.randint(1, max_faults) if family == "competing" else rng.randint(0, max_faults)
            if stage == "transfer" and index >= 2:
                faults = 2
            cases.append({"family": family, "input": _sample(rng, family, width, faults, index)})
    rng.shuffle(cases)
    return [{"id": f"{stage}-{index:02}", **case} for index, case in enumerate(cases, 1)]


def main():
    if len(sys.argv) != 3:
        raise SystemExit("python3 forge_telemetry.py CANDIDATE EVIDENCE.json")
    source = Path(sys.argv[1]).read_text(encoding="utf-8")
    evidence = json.loads(Path(sys.argv[2]).read_bytes())
    if hashlib.sha256(source.encode()).hexdigest() != evidence["candidate_sha256"]:
        raise SystemExit("Candidate digest mismatch. Empreinte du candidat différente.")
    rows = []
    for name, cases in evidence["cohorts"].items():
        if fingerprint(cases) != evidence["commitments"][name]:
            raise SystemExit("Cohort digest mismatch. Empreinte de la cohorte différente.")
        rows += [{"id": case["id"], **score(source, case["input"])} for case in cases]
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rows and all(row["passed"] for row in rows) else 1)


if __name__ == "__main__":
    main()
