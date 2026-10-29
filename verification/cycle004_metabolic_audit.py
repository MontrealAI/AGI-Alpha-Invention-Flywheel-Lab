"""Independent matrix/witness audit of the archived metabolic probe; no candidate imports."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET

ARCHIVE_SHA256 = "2eb450d8fa4307ec384782ffc03011473c4bf9ec8513c68e1341a66d0179895d"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse(path):
    if sha(path) != ARCHIVE_SHA256:
        raise ValueError("ARCHIVE_IDENTITY_MISMATCH")
    root = ET.parse(path).getroot()
    species = [node.attrib["id"] for node in root.findall(".//{*}listOfSpecies/{*}species")]
    rows = []
    for node in root.findall(".//{*}listOfReactions/{*}reaction"):
        coefficients = {}
        for group, sign in (("listOfReactants", -1), ("listOfProducts", 1)):
            for item in node.findall("{*}" + group + "/{*}speciesReference"):
                name = item.attrib["species"]
                coefficients[name] = coefficients.get(name, 0) + sign * float(item.attrib.get("stoichiometry", 1))
        parameters = {item.attrib["id"]: float(item.attrib["value"]) for item in node.findall(".//{*}parameter")}
        bounds = [parameters["LOWER_BOUND"], parameters["UPPER_BOUND"]]
        if node.attrib["id"].startswith("EX_"):
            bounds = [0, 0]
        rows.append({"id": node.attrib["id"], "stoichiometry": coefficients, "bounds": bounds})
    return species, rows


def solve(species, rows, restrict):
    import numpy as np
    from scipy.optimize import linprog
    from scipy.sparse import coo_matrix
    diagnostic = {"id": "verifier_ATP_dissipation", "stoichiometry": {
        "cpd00002_c": -1, "cpd00001_c": -1, "cpd00008_c": 1, "cpd00009_c": 1, "cpd00067_c": 1},
        "bounds": [0, 10000]}
    records = json.loads(json.dumps(rows)) + [diagnostic]
    if restrict:
        next(row for row in records if row["id"] == "rxn10153")["bounds"][0] = 0
    lookup = {name: index for index, name in enumerate(species)}
    ri, ci, value = [], [], []
    for column, row in enumerate(records):
        for compound, coefficient in row["stoichiometry"].items():
            ri.append(lookup[compound]); ci.append(column); value.append(coefficient)
    matrix = coo_matrix((value, (ri, ci)), shape=(len(species), len(records))).tocsr()
    objective = np.zeros(len(records)); objective[-1] = -1
    bounds = [row["bounds"] for row in records]
    result = linprog(objective, A_eq=matrix, b_eq=np.zeros(len(species)), bounds=bounds, method="highs")
    if not result.success:
        raise RuntimeError(result.message)
    residual = float(np.max(np.abs(matrix @ result.x)))
    violation = max(max(low - flux, flux - high, 0) for (low, high), flux in zip(bounds, result.x))
    return {"diagnostic_flux": float(result.x[-1]), "max_steady_state_residual": residual,
            "max_bound_violation": float(violation), "solver_status": result.message,
            "witness_nonzero_fluxes": {row["id"]: float(flux) for row, flux in zip(records, result.x) if abs(flux) > 1e-8},
            "species_count": len(species), "source_reaction_count": len(rows)}


def audit(archive, builder_result, source_data, output):
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=False)
    species, reactions = parse(archive)
    reduced = json.loads(source_data.read_text())
    source_by_id = {reaction["id"]: reaction for reaction in reactions}
    extraction_equal = all(source_by_id[row["id"]]["stoichiometry"] == row["stoichiometry"]
                           and source_by_id[row["id"]]["bounds"] == row["bounds"] for row in reduced["reactions"])
    original, restricted = solve(species, reactions, False), solve(species, reactions, True)
    builder = json.loads(builder_result.read_text())
    endpoints_equal = (abs(original["diagnostic_flux"] - builder["full_model"]["original"]["diagnostic_flux"]) < 1e-7
                       and abs(restricted["diagnostic_flux"] - builder["full_model"]["single_direction_restriction"]["diagnostic_flux"]) < 1e-7)
    report = {"schema": "agi-alpha-cycle004-independent-metabolic-witness/v1", "archive_sha256": sha(archive),
              "builder_result_sha256": sha(builder_result), "subnetwork_input_sha256": sha(source_data),
              "verifier_sha256": sha(__file__), "extraction_matches_archive": extraction_equal,
              "full_model_original": original, "full_model_single_restriction": restricted,
              "matches_builder_endpoints": endpoints_equal,
              "reduced_exact_certificate": {
                  "steady_state_implications": ["v2=-v1 from malate balance", "v3=v1 from sodium balance", "d=-v1 from proton balance"],
                  "original_feasible_witness": {"rxn10153": -10000, "rxn05207": 10000, "rxn05209": -10000, "PROTON_DISSIPATION": 10000},
                  "restricted_proof": "v1>=0 and d>=0 with d=-v1 force d=0 for these three reactions. This is not a whole-model proof."},
              "scope_counterexample_established": restricted["diagnostic_flux"] > 1e-7,
              "passed": extraction_equal and endpoints_equal and max(original["max_steady_state_residual"], restricted["max_steady_state_residual"], original["max_bound_violation"], restricted["max_bound_violation"]) < 1e-7,
              "wall_seconds": time.monotonic()-started, "confirmation_alpha_spent": 0,
              "limits": ["Independent parsing, matrix assembly and witness checking, sharing scipy/HiGHS and host with builder.",
                         "All EX_ reactions fixed to zero, all source species in steady-state equations; this is a model diagnostic, not a physical experiment.",
                         "Previously published defect and repair, not new invention. Full-model residual falsifies promoting the three-reaction repair to a whole-model cure.",
                         "No whole-model corrective construction, useful accepted commercial delivery, complete economics or inherited-successor benefit established."]}
    with (output / "REPORT.json").open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False); stream.write("\n")
    print(json.dumps({"passed": report["passed"], "full_model_fluxes": [original["diagnostic_flux"], restricted["diagnostic_flux"]]}))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--builder-result", required=True, type=Path)
    parser.add_argument("--source-data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.archive, args.builder_result, args.source_data, args.output)
    raise SystemExit(0 if report["passed"] else 1)
