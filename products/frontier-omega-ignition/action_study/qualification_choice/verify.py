"""Replay both methods, adversarial controls and the separately registered successor."""
import argparse
from fractions import Fraction
from hashlib import sha256
import itertools
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

if __package__:
    from . import adapter, direct
else:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import adapter, direct

HERE = Path(__file__).resolve().parent


def json_text(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def check_controls(pool, roster):
    root = adapter.SOURCES
    repo = "psf/requests"
    group = pool["groups"][repo]
    original = direct.read(root / group["file"])

    def check_payload(alter, rejection):
        with TemporaryDirectory() as temp:
            source = Path(temp)
            data = json.loads(json.dumps(original))
            alter(data)
            path = source / group["file"]
            path.write_text(json_text(data))
            # Challenge inner scientific validation even when the bytes have
            # been rehashed. Separately test the outer source identity below.
            changed = {**group, "sha256": sha256(path.read_bytes()).hexdigest()}
            try:
                counts = adapter.witnessed_counts(source, repo, changed, roster)
            except ValueError:
                if rejection:
                    return True
                raise
            if rejection:
                raise AssertionError("Invalid source passed inner validation")
            return counts

    def duplicate(data):
        data["rows"][1] = data["rows"][0]

    def outside(data):
        data["rows"][0][0] = "outside__roster-999"

    def absent_label(data):
        data["rows"][0][1] = None

    def switch(data):
        # Swap two opposing B labels across A statuses, holding both pooled
        # pass counts fixed. Transfer full status metadata together.
        for x, y in itertools.combinations(data["rows"], 2):
            xp, yp = (direct.row_status(data["prefixes"][row[2]])["resolved"] for row in (x, y))
            if xp != yp and x[1] != y[1]:
                x[2:], y[2:] = y[2:], x[2:]
                return
        raise AssertionError("Fixture lacks a discordant switch")

    before = adapter.witnessed_counts(root, repo, group, roster)
    after = check_payload(switch, False)
    if (before["A"], before["B"]) != (after["A"], after["B"]) or before["both"] == after["both"]:
        raise AssertionError("Pairing control did not change overlap at fixed margins")
    controls = {"duplicate_record": check_payload(duplicate, True), "unknown_instance": check_payload(outside, True),
                "unknown_resolution": check_payload(absent_label, True),
                "unchanged_margins_altered_pairing": {"before": before, "after": after}}

    # A second alteration preserves the complete population overlap as well
    # as both pass totals. A source-aware checker must still distinguish
    # which repository now carries each paired success.
    second_repo = "django/django"
    second_group = pool["groups"][second_repo]
    second = direct.read(root / second_group["file"])
    changed_first = json.loads(json.dumps(original))
    candidates = ((x, y) for x in changed_first["rows"] for y in second["rows"]
                  if x[1] and y[1] and
                  (direct.row_status(changed_first["prefixes"][x[2]])["resolved"] !=
                   direct.row_status(second["prefixes"][y[2]])["resolved"]))
    x, y = next(candidates)
    x_b, y_b = changed_first["prefixes"][x[2]], second["prefixes"][y[2]]
    x[2:], y[2:] = y[2:], x[2:]
    changed_first["prefixes"].append(y_b)
    second["prefixes"].append(x_b)
    x[2], y[2] = len(changed_first["prefixes"]) - 1, len(second["prefixes"]) - 1
    old_second = adapter.witnessed_counts(root, second_repo, second_group, roster)
    with TemporaryDirectory() as folder:
        changes = []
        for repository, metadata, payload in ((repo, group, changed_first), (second_repo, second_group, second)):
            source_path = Path(folder) / metadata["file"]
            source_path.write_text(json_text(payload))
            new_meta = {**metadata, "sha256": sha256(source_path.read_bytes()).hexdigest()}
            changes.append(adapter.witnessed_counts(Path(folder), repository, new_meta, roster))
    assert all(before[k] + old_second[k] == changes[0][k] + changes[1][k] for k in before)
    assert before["both"] != changes[0]["both"]
    controls["fixed_global_overlap_changed_repository_pairing"] = {
        "repositories": [repo, second_repo], "before_both": [before["both"], old_second["both"]],
        "after_both": [changes[0]["both"], changes[1]["both"]], "full_population_margins_and_overlap_preserved": True}

    sizes = {"small": 2, "large": 8}
    observed = {"small": {"A": 0, "B": 2}, "large": {"A": 6, "B": 3}}
    low, high = adapter.interval(sizes, {"A": 6, "B": 5}, observed)
    if adapter.sign(low, high, True) != "B" or low != Fraction(-5, 16):
        raise AssertionError("Failed pooling reversal")
    controls["pooled_A_but_repository_B"] = str(low)
    if adapter.sign(Fraction(0), Fraction(0), False) is not None or adapter.sign(Fraction(0), Fraction(0), True) != "tie":
        raise AssertionError("Unjustified tie")
    controls["complete_zero_tie"] = True
    try:
        adapter.interval(sizes, {"A": 7, "B": 5}, observed)
    except ValueError:
        controls["inconsistent_margins"] = True
    else:
        raise AssertionError("A false pool was accepted")
    for cap in (True, 1.5, -1):
        if adapter.inspect_source({"max_repositories": cap}, "repository_outcomes")["finding"] is not None:
            raise AssertionError("Malformed acquisition scope passed")
    controls["invalid_caps_withheld"] = True

    with TemporaryDirectory() as temp:
        src = Path(temp)
        # Link all immutables except the first required disclosure. A pooled
        # caller must succeed without the missing group ever being read.
        for p in root.iterdir():
            if p.name != pool["groups"]["pallets/flask"]["file"]:
                (src / p.name).symlink_to(p)
        pooled_only = adapter.decide(adapter.example_scope(), "pooled", src)
        if pooled_only["state"] != "incomplete":
            raise AssertionError("Unexpected finding in pooled-only control")
        try:
            adapter.decide(adapter.example_scope(), "repository_outcomes", src)
        except FileNotFoundError:
            controls["withdrawn_required_report"] = True
        else:
            raise AssertionError("Missing required report passed")
        first_file = src / pool["groups"]["pallets/flask"]["file"]
        first_file.write_text("{}\n")
        try:
            adapter.decide(adapter.example_scope(), "repository_outcomes", src)
        except ValueError:
            controls["changed_source_identity"] = True
        else:
            raise AssertionError("Old acceptance survived changed source")
    with patch.object(adapter, "witnessed_counts", side_effect=AssertionError("Pooled route read outcomes")):
        if adapter.decide(adapter.example_scope(), "pooled")["finding"] is not None:
            raise AssertionError("Pooled route inferred a sign")
    controls["pooled_route_reads_no_repository_outcomes"] = True
    return controls


def oracle(sizes, pooled, groups, answer):
    minimum = None
    witnesses = []
    total = 0
    best_instances = sum(sizes.values()) + 1
    fewest_instances_subsets = []
    for count in range(len(sizes) + 1):
        for subset in itertools.combinations(sorted(sizes), count):
            total += 1
            known = {r: groups[r] for r in subset}
            low, high = adapter.interval(sizes, pooled, known)
            if adapter.sign(low, high, count == len(sizes)) != answer:
                continue
            cases = sum(sizes[repo] for repo in subset)
            if cases < best_instances:
                best_instances = cases
                fewest_instances_subsets.clear()
            if cases == best_instances:
                fewest_instances_subsets.append(list(subset))
            if minimum is None:
                minimum = count
            if count == minimum:
                witnesses.append((sum(sizes[r] for r in subset), subset, low, high))
    cheapest = min(witnesses)
    return {"direction": answer, "subsets_checked": total, "minimum_repository_count": minimum,
            "number_of_minimum_subsets": len(witnesses), "fewest_instances_at_minimum": cheapest[0],
            "one_minimum_subset": list(cheapest[1]), "its_interval": [str(cheapest[2]), str(cheapest[3])],
            "minimum_instances_over_all_subsets": best_instances,
            "number_of_minimum_instance_subsets": len(fewest_instances_subsets),
            "one_minimum_instance_subset": fewest_instances_subsets[0], "observed_outcomes_given_to_oracle": True}


def build():
    pool, roster = adapter.load_pool()
    sql = direct.conventional()
    plain = direct.conventional(check_prefixes=False)
    assert plain["equal_repository_rates"] == sql["equal_repository_rates"] and plain["paired"] == sql["paired"]
    stopped = direct.conventional(stop=True)
    groups = sql["repositories"]
    assert sql["paired"]["cases"] == len(roster) == 500
    assert {m: sql["paired"][m] for m in ("A", "B")} == pool["pooled"]
    sizes = {r: g["cases"] for r, g in groups.items()}
    known = {}
    for n, (left, right) in enumerate(sql["ranges"]):
        interval = adapter.interval(sizes, pool["pooled"], known)
        assert tuple(map(str, interval)) == (left, right), "Independent SQL disagrees"
        if n < len(groups):
            repo = list(groups)[n]
            checked = adapter.witnessed_counts(adapter.SOURCES, repo, pool["groups"][repo], roster)
            assert all(checked[k] == groups[repo][k] for k in checked)
            known[repo] = checked
    decisions = [adapter.decide({"max_repositories": i}, "repository_outcomes") for i in range(len(groups) + 1)]
    boundary = next(i for i, item in enumerate(decisions) if item["finding"] is not None)
    finding = decisions[boundary]["finding"]
    assert decisions[-1] == decisions[boundary]
    assert len(stopped["repositories"]) == boundary
    assert stopped["ranges"][-1] == sql["ranges"][boundary]
    assert (Fraction(sql["equal_repository_rates"]["A"]) - Fraction(sql["equal_repository_rates"]["B"])
            == Fraction(sql["ranges"][-1][0]) == Fraction(sql["ranges"][-1][1]))
    result = {"population": "SWE-bench Verified, complete historical submissions",
              "finding": finding, "pooled": pool["pooled"], "paired": sql["paired"],
              "equal_repository_rates": sql["equal_repository_rates"], "A_minus_B": sql["ranges"][-1][0],
              "first_decisive_repositories": boundary, "first_decisive_instances": stopped["paired"]["cases"],
              "qualification_input": "qualification_input.json", "complete_SQL": groups,
              "prefixes": [{"cap": cap, "interval": bounds} for cap, bounds in enumerate(sql["ranges"])],
              "retrospective_oracle": oracle(sizes, pool["pooled"], groups, finding),
              "adverse_controls": check_controls(pool, roster)}
    # Post hoc sensitivity, with no influence on the registered action.
    rates = {repo: Fraction(row["A"] - row["B"], sizes[repo]) for repo, row in groups.items()}
    leave_one_out = {repo: (sum(rates.values()) - contribution) / (len(rates) - 1)
                     for repo, contribution in rates.items()}
    result["population_sensitivity"] = {
        "post_hoc": True, "active_contract_changed": False,
        "reversed_order_when_omitted": {repo: str(value) for repo, value in leave_one_out.items() if value > 0},
        "number_of_omit_one_contracts": len(leave_one_out)}
    result["ordinary_reuse"] = {"decision": None, "reason": "The two-facility example has different populations and margins."}
    next_case = {
        "objective": "Choose the first configuration for MONTREAL.AI's next internal software-delivery qualification.",
        "action": "place_first_for_fresh_qualification" if finding != "tie" else "retain_both_for_qualification",
        "first_submission": pool["candidates"][finding]["folder"] if finding in ("A", "B") else None,
        "comparison_submission": pool["candidates"]["B" if finding == "A" else "A"]["folder"] if finding in ("A", "B") else None,
        "qualification_state": "needs_fresh_authorized_internal_tasks", "run_authorized": False,
        "evidence_scope": {"fixed_public_cases": 500, "fixed_public_repositories": len(sizes),
                           "A_minus_B": result["A_minus_B"], "denominator_roster_sha256": pool["attachments"]["roster.parquet-prefix"],
                           "pool_manifest_sha256": adapter.POOL_SHA256},
        "next_trial": {"objective": "Compare accepted outputs on a fresh internal portfolio with equal weights per repository.",
                       "task_manifest": None, "beneficiary_acceptance": None, "authorized_model_access": None,
                       "max_spend": None, "max_compute": None, "available_comparators": ["conventional specialist", "direct AI", "hybrid"],
                       "required_before_execution": ["named repository owners and permitted tasks", "frozen independent acceptance per task",
                       "matched tool and time budgets", "provider and model availability", "approved resource ceiling"]},
        "archived_parentage": {"software_study": "SWE-bench Verified", "reevaluate_if": ["source snapshot changes",
                          "repository weights change", "eligible task population changes", "target benefit changes"]}}
    return result, next_case


def profile():
    from importlib import import_module
    from platform import python_version
    from statistics import median
    from time import perf_counter, process_time
    inherited = import_module("discovery_field.decision_study.calibration_bounds")
    def prior_output():
        example = inherited.bounds(inherited.EXAMPLE)
        assert example["minimum"]["difference"] == "-5/16"
        return None
    methods = {"ordinary_reuse_illustrative_example": prior_output,
               "retained_adaptive": lambda: adapter.decide(adapter.example_scope(), "repository_outcomes"),
               "direct_sql_full": lambda: direct.conventional(check_prefixes=False),
               "direct_sql_adaptive": lambda: direct.conventional(stop=True)}
    times = {key: {"wall": [], "cpu": []} for key in methods}
    names = list(methods)
    # Balanced cyclic positions, shared process and warm OS file cache.
    for round_no in range(24):
        offset = round_no % len(names)
        for name in names[offset:] + names[:offset]:
            start, cpu = perf_counter(), process_time()
            methods[name]()
            times[name]["wall"].append(perf_counter() - start)
            times[name]["cpu"].append(process_time() - cpu)
    return {"python_version": python_version(), "repetitions": 24, "process_startup_included": False,
            "timing_scope": "Local read, original identity checks, computation and decision; first access may be warm.",
            "methods": {name: {"median_wall_seconds": median(v["wall"]), "median_cpu_seconds": median(v["cpu"]),
                               "total_wall_seconds": sum(v["wall"]), "total_cpu_seconds": sum(v["cpu"])}
                        for name, v in times.items()}}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write", action="store_true", help="Record outputs in this checkout")
    p.add_argument("--profile", action="store_true", help="Measure fresh matched, counterbalanced local route clocks")
    args = p.parse_args()
    if args.profile:
        print(json.dumps(profile(), indent=2))
        raise SystemExit
    result, next_case = build()
    for name, value in (("result.json", result), ("qualification_input.json", next_case)):
        path = HERE / name
        if args.write:
            path.write_text(json_text(value))
        elif json.loads(path.read_bytes()) != value:
            raise SystemExit(f"Fresh result differs from {name}")
    print(json.dumps({key: result[key] for key in ("finding", "A_minus_B", "first_decisive_repositories",
                     "first_decisive_instances", "equal_repository_rates", "paired", "retrospective_oracle")}, indent=2))
