# SPDX-License-Identifier: Apache-2.0
"""Compare unchanged portable SQL and independently authored ordinary Python."""

from argparse import ArgumentParser
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from statistics import median
from time import perf_counter, process_time

from operate import AllocationInstrument, ARTIFACT_NAME, HERE, REPO
from ordinary import solve as ordinary


NATIVE_ARTIFACT = "006666c263b61367c16bb2d479a25c8fc661552a95cdbe24c2a9692180c125f3"
DIRECT_SOURCE = "3eb06ebd7a5d1ce9a810ae4f69ec71a8e24c5a8d3feaf2a570fe9cedd80db480"
HELD_DIGEST = "7cf9aee809f9440ff9f777606037b72a42824d9d9c00c60b13d8945deedb95d4"
SOURCE_SHA256 = "ab33a8e7037ec7188806fd6cc496cdda9370d524978b6442c44c8df9a22b2a4b"


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return sha256(value).hexdigest()


def cases(held):
    example = json.loads((HERE / "EXAMPLE.json").read_bytes())
    yield "public-example", example
    for key, dataset in held.items():
        yield "separately-authored-" + key, dataset
    variations = {
        "missing-cell": ("forecasts", example["forecasts"][:-1]),
        "null-forecast": ("forecasts", [{**item, "demand": None} if idx == 0 else item
                                          for idx, item in enumerate(example["forecasts"])]),
        "duplicate-forecast": ("forecasts", example["forecasts"] + [example["forecasts"][0]]),
        "unknown-group": ("forecasts", example["forecasts"] + [
            {"scenario_id": "choir-demand", "group_id": "unlisted", "demand": 2}]),
        "negative-demand": ("forecasts", [{**example["forecasts"][0], "demand": -1}] + example["forecasts"][1:]),
        "empty-budget": ("budget", []),
        "infeasible-minima": ("budget", [{"total_slots": 1}]),
        "null-budget-row": ("budget", example["budget"] + [{"total_slots": None}]),
        "max-capacity-count": ("groups", [{**group, "min_slots": 0, "max_slots": 8} for group in example["groups"]]),
    }
    for key, (table, rows) in variations.items():
        yield key, {**example, table: rows}
    yield "all-unconstrained-max-work", {
        "groups": [{**group, "min_slots": 0, "max_slots": 8} for group in example["groups"]],
        "scenarios": example["scenarios"] + [{"scenario_id": "zero"}],
        "forecasts": example["forecasts"] + [
            {"scenario_id": "zero", "group_id": group["group_id"], "demand": 0}
            for group in example["groups"]],
        "budget": [{"total_slots": 8}],
    }
    yield "row-order-invariance", {table: list(reversed(rows)) for table, rows in example.items()}
    generator = Random(6319)
    for i in range(32):
        group_ids = ["cercle", "orchestre", "étoiles"][:generator.randint(1, 3)]
        scenario_ids = ["aucun", "complet", "demi", "élevé"][:generator.randint(1, 4)]
        maxima = {name: generator.randint(0, 8) for name in group_ids}
        yield f"permutation-{i+1:02d}", {
            "groups": [{"group_id": name, "min_slots": generator.randint(0, maximum), "max_slots": maximum}
                       for name, maximum in maxima.items()],
            "scenarios": [{"scenario_id": name} for name in reversed(scenario_ids)],
            "forecasts": [{"scenario_id": scenario, "group_id": name, "demand": generator.randint(0, 15)}
                          for scenario in scenario_ids for name in reversed(group_ids)],
            "budget": [{"total_slots": generator.randint(0, 8)}],
        }


def independent_controls(results):
    expected_dispositions = {
        "missing-cell": "MISSING_FORECAST", "null-forecast": "MISSING_FORECAST",
        "duplicate-forecast": "INVALID_INPUT", "unknown-group": "INVALID_INPUT",
        "negative-demand": "INVALID_INPUT", "empty-budget": "INVALID_INPUT",
        "null-budget-row": "INVALID_INPUT", "infeasible-minima": "INFEASIBLE_MINIMA",
    }
    control_checks = {case: bool(results[case]) and all(row[0] == state for row in results[case])
                      for case, state in expected_dispositions.items()}
    control_checks["row-order-invariance"] = results["row-order-invariance"] == results["public-example"]
    held = results["separately-authored-allocation_a"]
    control_checks["blind-ordinary-certificate"] = (
        len(held) == 12 and {row[2]: row[3] for row in held} == {"chamber": 1, "percussion": 2, "spoken": 2}
        and {(row[11], row[12]) for row in held} == {(1, 16)}
        and {name: sum(row[5] for row in held if row[1] == name)
             for name in ("matinee", "evening", "weekend", "returning")} == {
                 "matinee": 5, "evening": 4, "weekend": 2, "returning": 5,
             }
    )
    incomplete = results["separately-authored-incomplete_scenario"]
    control_checks["blind-absence"] = sorted(row[:3] for row in incomplete) == [
        ["MISSING_FORECAST", "returning", name] for name in ("chamber", "percussion", "spoken")
    ] and all(all(value is None for value in row[3:]) for row in incomplete)
    control_checks["opportunity-loss-conserved"] = all(
        all(sum(item[9] for item in rows if item[1] == scenario) == regret
            for scenario, regret in {(item[1], item[10]) for item in rows})
        for rows in results.values() if rows and rows[0][0] == "OK"
    )
    return control_checks


def assess(harness, held):
    if digest((HERE / "allocation.sql").read_bytes()) != SOURCE_SHA256 or digest((HERE / "ordinary.py").read_bytes()) != DIRECT_SOURCE:
        raise ValueError("One comparison source differs from its frozen bytes.")
    if digest(held) != HELD_DIGEST:
        raise ValueError("The independently frozen fixture differs from its declared digest.")
    tool = AllocationInstrument(harness)
    started = perf_counter()
    constructed = tool.construct()
    construction_wall = perf_counter() - started
    if constructed["sha256"] != NATIVE_ARTIFACT:
        raise ValueError("The constructed portable artifact differs from its freeze.")
    from bridge.mission_tools import _replay

    times = {arm: [] for arm in ("assisted_harness", "ordinary_direct", "portable_replay")}
    agreement, outputs = {}, {}
    local_cpu_start = process_time()
    started = perf_counter()
    for position, (case_id, tables) in enumerate(cases(json.loads(held))):
        independent_data = deepcopy(tables)
        runners = {
            "assisted_harness": lambda: tool.run(tables),
            "ordinary_direct": lambda: ordinary(independent_data),
            "portable_replay": lambda: _replay(tool.artifacts[ARTIFACT_NAME], tables),
        }
        observations = {}
        arms = list(runners)
        for arm in (arms if position % 2 == 0 else list(reversed(arms))):
            begin = perf_counter()
            try:
                observations[arm] = runners[arm]()
            except ValueError as error:
                observations[arm] = {"error": str(error)}
            times[arm].append(perf_counter() - begin)
        candidate = observations["assisted_harness"]
        reference = observations["ordinary_direct"]
        portable = observations["portable_replay"]
        actual = candidate.get("rows", [])
        outputs[case_id] = actual
        matches = bool(actual) and actual == reference == portable.get("rows") and (
            candidate.get("input_sha256") == portable.get("input_sha256") == digest(encode(tables))
            and candidate.get("output_sha256") == digest(encode(actual))
            and candidate.get("artifact_sha256") == NATIVE_ARTIFACT
            and candidate.get("input_origin") == "MODEL_DEVELOPMENT_FIXTURE"
        )
        agreement[case_id] = {
            "pass": matches, "input_sha256": digest(encode(tables)),
            "output_sha256": digest(encode(actual)), "disposition": actual[0][0] if actual else "ERROR",
        }
        if not matches:
            agreement[case_id]["disagreement"] = observations
    runtime = perf_counter() - started
    local_cpu = process_time() - local_cpu_start
    controls = independent_controls(outputs)
    accepted = sum(item["pass"] for item in agreement.values())
    positive = accepted == len(agreement) and all(controls.values())
    return {
        "schema": "frontier/assisted-allocation-assessment-v1",
        "scope": "Two included-Codex assisted authoring arms, isolated native SQLite, and public synthetic inputs. One separate fixture author and one separate comparison author under shared administration. No live model dispatch, governance admission, or real scheduling execution.",
        "verdict": "GO_SCOPED_PUBLIC_FIXTURES" if positive else "NO_GO",
        "intelligence": "Included Codex operating in separate agent contexts. Hosted inference model revision, tokens, infrastructure costs and all human attention remain unmeasured.",
        "artifact": constructed, "sql_source_sha256": SOURCE_SHA256, "ordinary_source_sha256": DIRECT_SOURCE,
        "independent_fixture_sha256": HELD_DIGEST, "assessor_sha256": digest(Path(__file__).read_bytes()),
        "registration_sha256": digest((HERE / "REGISTRATION.json").read_bytes()),
        "first_construction": {"status": "TABLE_READ_ONLY", "reason": "COUNT(*) uses an implicit SQLite table record; the unchanged read-only authorizer requires an explicit approved column.",
                               "sql_source_sha256": "bb4a8385b5222aa4161e850d926b6d0397299058351df012cdabc46ece9901de"},
        "held_acceptance": {"matches": accepted, "denominator": len(agreement), "cases": agreement, "controls": controls},
        "public_example": outputs["public-example"], "independent_positive": outputs["separately-authored-allocation_a"],
        "independent_missing": outputs["separately-authored-incomplete_scenario"],
        "cost": {"harness_agent_registration_to_valid_example_utc_s_approx": 122,
                 "ordinary_agent_authoring_s_approx": 38, "construction_worker_wall_seconds": construction_wall,
                 "assay_wall_seconds": runtime, "assay_parent_cpu_seconds_excludes_worker_children": local_cpu,
                 "median_wall_seconds": {arm: median(values) for arm, values in times.items()},
                 "paid_requests": 0, "runtime_inference_requests": 0, "external_eval_custody": False},
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--held", type=Path, default=HERE / "INDEPENDENT-INPUTS.json")
    parser.add_argument("--harness", type=Path, default=REPO / "products" / "alpha-genesis-harness")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.output.open("x", encoding="utf-8") as stream:
        result = assess(args.harness, args.held.read_bytes())
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(result["verdict"], result["held_acceptance"]["matches"], result["held_acceptance"]["denominator"])


if __name__ == "__main__":
    main()
