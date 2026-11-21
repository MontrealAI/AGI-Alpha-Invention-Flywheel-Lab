"""Construct a diagnostic substrate panel using the frozen first cover asset.

This adapter changes the useful objective from preserving substrate yield to
preserving recorded pairwise ligand distinctions. It introduces no new optimizer.
Decimal comparisons preserve the recorded CSV values without clipping. A panel
is retrospective reference-library evidence, not prospective assay validation.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import io
import itertools
import json
from pathlib import Path
import platform
import time

from cover import canonical_problem, problem_digest, solve_cover


HERE = Path(__file__).resolve().parent
FROZEN_COVER_SHA256 = "786867bdffc2502ecd816b043b4a974f86faf7dba8a3a3bdcd7de89a965c95d7"
SOURCE_COMMIT = "ae3e910dcea27cfd1631a28b793b6c63607baedd"
SOURCE_REPOSITORY = "doyle-lab-ucla/bandit-optimization"
SOURCE_FILES = {
    "nib-etoh.csv": {
        "solvent": "ethanol",
        "sha256": "d5216a673eefbaacc4ae961f4ff6acb73dbc1c83e37d0548fa7eaf84bbe5607c",
        "git_blob_sha1": "85ab353d601ab33192a62bf4d31c9cf64e812c27",
    },
    "nib-meoh.csv": {
        "solvent": "methanol",
        "sha256": "be9fccf4c4bee7fa2b868cbbf5e813d2a29765e4ffc1f92c84b450c8381d5f99",
        "git_blob_sha1": "1cccdd52f969415e59ee19579542469749d6da63",
    },
}
GAPS = (10, 15, 20, 25, 30)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_retained_asset():
    """Fail closed if first capability bytes no longer match their freeze."""
    actual = sha256((HERE / "cover.py").read_bytes())
    if actual != FROZEN_COVER_SHA256:
        raise ValueError("FIRST_ASSET_CHANGED: retained cover bytes differ")
    freeze = json.loads((HERE / "evidence/FIRST_ASSET_FREEZE.json").read_text())
    if freeze["files"]["cover.py"]["sha256"] != actual:
        raise ValueError("FIRST_ASSET_FREEZE_MISMATCH")
    return actual


def load_matrix(path, expected_sha256=None):
    """Parse one complete, finite substrate-by-ligand CSV without transforms."""
    path = Path(path)
    data = path.read_bytes()
    digest = sha256(data)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("SOURCE_HASH_MISMATCH")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
    required = ["", "electrophile_id", "ligand_name", "yield"]
    if reader.fieldnames != required:
        raise ValueError("INVALID_CSV_COLUMNS")
    cells, source_indices = {}, set()
    precision = 28
    for row in reader:
        if None in row or any(row.get(k) is None for k in required):
            raise ValueError("MALFORMED_CSV_ROW")
        substrate, ligand, value = row["electrophile_id"], row["ligand_name"], row["yield"]
        if not substrate or substrate != substrate.strip() or not ligand or ligand != ligand.strip():
            raise ValueError("EMPTY_OR_UNNORMALIZED_IDENTIFIER")
        if row[""] in source_indices:
            raise ValueError("DUPLICATE_SOURCE_INDEX")
        source_indices.add(row[""])
        key = (substrate, ligand)
        if key in cells:
            raise ValueError("DUPLICATE_MATRIX_CELL")
        try:
            y = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("NONNUMERIC_YIELD") from error
        if not y.is_finite():
            raise ValueError("NONFINITE_YIELD")
        precision = max(precision, len(y.as_tuple().digits) + abs(y.as_tuple().exponent) + 10)
        cells[key] = {"value": y, "source_row": {
            "csv_line": reader.line_num, "source_index": row[""],
            "electrophile_id": substrate, "ligand_name": ligand, "yield": value,
        }}
    if not cells:
        raise ValueError("EMPTY_MATRIX")
    substrates = sorted({key[0] for key in cells})
    ligands = sorted({key[1] for key in cells})
    if len(cells) != len(substrates) * len(ligands):
        raise ValueError("INCOMPLETE_MATRIX")
    if any((s, ligand) not in cells for s in substrates for ligand in ligands):
        raise ValueError("INCOMPLETE_MATRIX")
    return {"sha256": digest, "bytes": len(data), "substrates": substrates,
            "ligands": ligands, "cells": cells, "decimal_precision": precision}


def diagnostic_instance(matrix, gap):
    """Reduce all full-table-distinguishable ligand pairs to minimum cover."""
    if isinstance(gap, bool):
        raise ValueError("INVALID_GAP")
    gap = Decimal(str(gap))
    if not gap.is_finite() or gap <= 0:
        raise ValueError("GAP_MUST_BE_FINITE_AND_POSITIVE")
    requirements, pairs, indistinguishable = [], [], []
    with localcontext() as context:
        context.prec = matrix["decimal_precision"]
        for a, b in itertools.combinations(matrix["ligands"], 2):
            witnesses = []
            largest, largest_substrate = Decimal("-1"), None
            for i, substrate in enumerate(matrix["substrates"]):
                difference = abs(matrix["cells"][substrate, a]["value"] - matrix["cells"][substrate, b]["value"])
                if difference > largest:
                    largest, largest_substrate = difference, substrate
                if difference >= gap:
                    witnesses.append(i)
            if witnesses:
                requirements.append(witnesses)
                pairs.append([a, b])
            else:
                indistinguishable.append({"ligands": [a, b], "maximum_recorded_gap": str(largest),
                    "max_gap_substrate": largest_substrate,
                    "source_rows_at_maximum": [matrix["cells"][largest_substrate, ligand]["source_row"] for ligand in (a, b)]})
    problem = canonical_problem(matrix["substrates"], requirements)
    return {"problem": problem, "pairs": pairs, "indistinguishable_pairs": indistinguishable,
            "gap_percentage_points": str(gap),
            "full_pair_denominator": len(matrix["ligands"]) * (len(matrix["ligands"]) - 1) // 2}


def local_feasible_witness(matrix, instance, result):
    """Independently recompute incidence and source-linked selected witnesses.

    This adapter's check is NOT the separately authored optimality verifier.
    It checks feasibility, original source rows, and exact declared distinctions.
    """
    if result.get("status") != "OPTIMAL":
        raise ValueError("NO_OPTIMAL_RESULT")
    selected = result.get("selected")
    options = instance["problem"]["option_ids"]
    if not isinstance(selected, list) or any(type(i) is not int or not 0 <= i < len(options) for i in selected):
        raise ValueError("INVALID_SELECTED_INDICES")
    if len(set(selected)) != len(selected) or len(selected) != result["cardinality"]:
        raise ValueError("INVALID_SELECTED_CARDINALITY")
    rebuilt = diagnostic_instance(matrix, instance["gap_percentage_points"])
    if rebuilt != instance:
        raise ValueError("INCIDENCE_RECONSTRUCTION_FAILED")
    if result["certificate"]["problem_sha256"] != problem_digest(instance["problem"]):
        raise ValueError("PROBLEM_CERTIFICATE_MISMATCH")
    witnesses = []
    gap = Decimal(instance["gap_percentage_points"])
    with localcontext() as context:
        context.prec = matrix["decimal_precision"]
        for requirement, pair in zip(instance["problem"]["requirements"], instance["pairs"]):
            valid = [i for i in selected if i in requirement]
            if not valid:
                raise ValueError("UNCOVERED_LIGAND_PAIR")
            substrate = options[valid[0]]
            cells = [matrix["cells"][substrate, ligand] for ligand in pair]
            delta = abs(cells[0]["value"] - cells[1]["value"])
            if delta < gap:
                raise ValueError("WITNESS_DOES_NOT_MEET_GAP")
            witnesses.append({"ligands": pair, "substrate": substrate,
                              "absolute_gap_percentage_points": str(delta),
                              "source_rows": [cell["source_row"] for cell in cells]})
    return witnesses


def run_case(path, gap, *, node_limit=1_000_000):
    """Run complete input-read → reduction → solve → source-witness pipeline."""
    wall, cpu = time.perf_counter(), time.process_time()
    asset_hash = verify_retained_asset()
    filename = Path(path).name
    if filename not in SOURCE_FILES:
        raise ValueError("UNREGISTERED_SOURCE_FILE")
    source = SOURCE_FILES[filename]
    stage_wall, stage_cpu = time.perf_counter(), time.process_time()
    matrix = load_matrix(path, source["sha256"])
    if len(matrix["substrates"]) != 33 or len(matrix["ligands"]) != 23:
        raise ValueError("REGISTERED_SOURCE_SHAPE_CHANGED")
    instance = diagnostic_instance(matrix, gap)
    preparation = {"wall_seconds": time.perf_counter() - stage_wall, "cpu_seconds": time.process_time() - stage_cpu}
    stage_wall, stage_cpu = time.perf_counter(), time.process_time()
    answer = solve_cover(instance["problem"]["option_ids"], instance["problem"]["requirements"], node_limit=node_limit)
    solving = {"wall_seconds": time.perf_counter() - stage_wall, "cpu_seconds": time.process_time() - stage_cpu}
    stage_wall, stage_cpu = time.perf_counter(), time.process_time()
    witnesses = local_feasible_witness(matrix, instance, answer)
    verification = {"wall_seconds": time.perf_counter() - stage_wall, "cpu_seconds": time.process_time() - stage_cpu,
                    "scope": "Same-adapter exact source/incidence/feasibility check; independent certificate qualification reported separately."}
    result = {"schema": "frontier-diagnostic-panel-result/v1", "case_id": f"{filename}:{gap}",
        "source": {"filename": filename, "sha256": matrix["sha256"], "bytes": matrix["bytes"],
                   "git_blob_sha1": source["git_blob_sha1"], "repository": SOURCE_REPOSITORY,
                   "commit": SOURCE_COMMIT, "path": "datasets/" + filename,
                   "url": f"https://raw.githubusercontent.com/{SOURCE_REPOSITORY}/{SOURCE_COMMIT}/datasets/{filename}",
                   "solvent": source["solvent"], "original_paper_doi": "10.1021/acs.organomet.2c00089"},
        "retained_asset_sha256": asset_hash, "adapter_sha256": sha256(Path(__file__).read_bytes()),
        "objective": "Minimum recorded-substrate panel preserving every full-table-distinguishable ligand pair at the declared absolute yield gap.",
        "gap_percentage_points": str(gap), "primary": filename == "nib-etoh.csv" and gap == 20,
        "substrate_count": len(matrix["substrates"]), "ligand_count": len(matrix["ligands"]),
        "full_pair_denominator": instance["full_pair_denominator"],
        "distinguishable_pair_count": len(instance["pairs"]),
        "indistinguishable_pair_count": len(instance["indistinguishable_pairs"]),
        "indistinguishable_pairs": instance["indistinguishable_pairs"],
        "problem": instance["problem"], "requirement_ligand_pairs": instance["pairs"],
        "answer": answer, "selected_substrates": [matrix["substrates"][i] for i in answer["selected"]],
        "source_linked_pair_witnesses": witnesses, "local_feasibility": "PASSED",
        "timings": {"preparation": preparation, "solve": solving, "local_verification": verification},
        "limitations": ["Complete 33-substrate, 23-ligand subset of a larger publication; ethanol and methanol are separate cases.",
            "Declared gap is a design criterion, not calibrated assay uncertainty or significance.",
            "No clipping or rounding of recorded yields; Decimal arithmetic used.",
            "All source outcomes were already measured; no prospective assay saving, unknown-ligand identification or future reproducibility established.",
            "Known mathematical reduction and ordinary artifact reuse; no improved invention procedure, autonomous local-model discovery or revenue claim."]}
    # Include a full serialization in measured resources; exclude only adding
    # the final timing fields and the final report file write, disclosed below.
    json.dumps(result, sort_keys=True, separators=(",", ":"))
    result["timings"]["input_to_serialized_output"] = {
        "wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
        "scope": "Asset/source reads and hashing, CSV parsing, full reduction, solving, local incidence/feasibility replay, witnesses and serialization. Excludes interpreter imports, final file write and separate independent verification."}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node-limit", type=int, default=1_000_000)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite a prior execution receipt")
    wall, cpu = time.perf_counter(), time.process_time()
    results, failures = [], []
    for filename in SOURCE_FILES:
        for gap in GAPS:
            case_wall, case_cpu = time.perf_counter(), time.process_time()
            try:
                result = run_case(args.data_dir / filename, gap, node_limit=args.node_limit)
                results.append(result)
                print(json.dumps({"case": result["case_id"], "cardinality": result["answer"]["cardinality"],
                    "panel": result["selected_substrates"], "distinguishable_pairs": result["distinguishable_pair_count"],
                    "indistinguishable_pairs": result["indistinguishable_pair_count"],
                    "cpu_seconds": result["timings"]["input_to_serialized_output"]["cpu_seconds"]}), flush=True)
            except Exception as error:
                failures.append({"case_id": f"{filename}:{gap}", "error_type": type(error).__name__,
                    "message": str(error), "wall_seconds": time.perf_counter() - case_wall,
                    "cpu_seconds": time.process_time() - case_cpu})
                print(json.dumps(failures[-1]), flush=True)
    report = {"schema": "frontier-retained-successor-experiment/v1", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "machine": platform.machine(),
        "adapter_sha256": sha256(Path(__file__).read_bytes()), "retained_cover_sha256": verify_retained_asset(),
        "protocol_sha256": sha256((HERE / "independent/PROTOCOL.json").read_bytes()),
        "registered_denominator": 10, "completed_case_count": len(results), "failures": failures,
        "outcome_scope": "Retrospective computational diagnostic panels; certificate acceptance by independent reviewer remains separate.",
        "construction_route": "Included assistant wrote a new adapter using unchanged first generic capability; anticipated structural transfer.",
        "results": results,
        "complete_suite_resources": {"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
            "scope": "All ten repeated source-read pipelines and console summaries, excluding interpreter import and final report file write."},
        "actual_complete_monetary_cost": None,
        "unmeasured_costs": ["model token costs", "host billing", "research labor valuation", "first asset acquisition valuation", "maintenance", "beneficiary adoption"],
        "claims": {"local_feasible_panels": len(results) == 10 and not failures,
                   "independent_optimality": "PENDING_SEPARATE_REVIEW", "prospective_assay_savings": "NOT_ESTABLISHED",
                   "causal_invention_method_advantage": "NOT_ESTABLISHED", "economic_value": "NOT_ESTABLISHED"}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
