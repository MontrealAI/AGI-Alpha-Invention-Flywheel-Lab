"""Build public decision exhibits by executing each visitor-selectable mission."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PRODUCT = HERE if (HERE / "invention").is_dir() else HERE.parents[1]
sys.path.insert(0, str(PRODUCT))


def reference_rehearsal():
    from invention.early_survey.exposures import verify
    from invention.early_survey.exposures.test_exposures import ArchiveTest

    test = ArchiveTest()
    test.test_unrelated_reference_does_not_preempt_first_witness()
    test.test_earlier_same_reference_without_packet_fails_closed()
    source = verify.calculate()
    if verify.json_bytes(source) != (verify.HERE / "RESULT.json").read_bytes():
        raise ValueError("The observed receiver differs from the registered archive")
    original = source["witnesses"]["g"]
    same = original["baseline"]["rfid"]
    other = 504120158  # Pre-registered synthetic different-reference control.
    different_ref = test._replay_with_earlier_broker_row(other)
    try:
        test._replay_with_earlier_broker_row(same)
    except ValueError as exc:
        refusal = str(exc)
        if "ambiguous or missing first alternative-broker witness" not in refusal:
            raise
    else:
        raise ValueError("Receiver accepted a first witness without its required packet")

    def display(row):
        witness = row["witness"]
        return {"kind": "record", "witness": witness["candid"], "utc": witness["utc"],
                "required_reference": same, "field": witness["field"], "readout": witness["rcid"],
                "delta": row["delta_from_baseline_mag"], "uncertainty": row["formal_error_mag"]}

    return {"archive": display(original), "other-reference": {
                **display(different_ref["witnesses"]["g"]), "kind": "synthetic", "candidate_reference": other},
            "same-missing": {"kind": "synthetic", "required_reference": same,
                             "candidate_reference": same, "witness": None, "reason": refusal}}


def editions():
    from action_study.desk import case

    def example(case_id, scope, sources):
        result = case({"profile": profile, "scope": scope, "sources": sources})
        return {"id": case_id, "receipt": json.dumps(result, ensure_ascii=False, allow_nan=False,
                                                      sort_keys=True, separators=(",", ":")) + "\n"}

    profile = "ztf-persistence"
    ztf = []
    for band in ("g", "r"):
        for route, clock, cutoff, sources in (
                ("first", "event", "2026-10-29T00:00:00Z", ["fink"]),
                ("before", "event", "2026-10-27T00:00:00Z", ["fink", "alerce"]),
                ("repeat", "event", "2026-10-29T00:00:00Z", ["fink", "alerce"]),
                ("received", "received", "2026-10-29T00:00:00Z", ["fink", "alerce"])):
            ztf.append(example(f"{band}-{route}", {"band": band, "as_of": cutoff, "clock": clock}, sources))

    profile = "gw-status"
    gw = []
    for label, cutoff, clock, sources in (
            ("first", "05:06:23", "issued", ["first_notice"]),
            ("before", "05:06:22", "issued", ["first_notice", "status_history"]),
            ("withdraw", "05:06:23", "issued", ["first_notice", "status_history"]),
            ("received", "05:06:23", "received", ["first_notice", "status_history"])):
        gw.append(example(label, {"event": "S240420aw", "as_of": "2024-04-20T" + cutoff + "Z",
                                  "clock": clock}, sources))

    profile = "engineering-qualification"
    from action_study.qualification_choice import adapter
    example_scope = adapter.example_scope()
    total = example_scope["max_repositories"]
    if not isinstance(total, int) or total < 1:
        raise ValueError("The qualification scope needs a positive repository budget")
    engineering = [example("pooled", {"max_repositories": 0}, ["pooled"])]
    for budget in range(1, total + 1):
        engineering.append(example(str(budget), {"max_repositories": budget}, ["pooled", "repository_outcomes"]))
    trial = (PRODUCT / "action_study/qualification_choice/qualification_input.json").read_text()
    plan = json.loads(trial)
    last = json.loads(engineering[-1]["receipt"])
    outcome = last["decision"]["finding"]
    if outcome not in ("A", "B") or plan["first_submission"] != last["attempts"][-1]["evidence"][0][outcome] or plan["run_authorized"]:
        raise ValueError("The engineering trial must match the observed order and its authorization")
    gw_result = json.loads((PRODUCT / "action_study/observing/result.json").read_bytes())
    comparison = json.loads((PRODUCT / "action_study/qualification_choice/economics.json").read_bytes())["captures"]
    measured = json.loads((PRODUCT / "action_study/qualification_choice/result.json").read_bytes())
    census = {key: measured[key] for key in ("paired", "first_decisive_instances", "first_decisive_repositories")}
    if comparison["stopped"]["reports"] != census["first_decisive_instances"] or comparison["complete"]["reports"] != census["paired"]["cases"]:
        raise ValueError("The two public captures do not match the benchmark census")
    economics = {route: {k: comparison[route][k] for k in ("reports", "wall_seconds", "response_body_bytes")}
                 for route in ("stopped", "complete")}
    review = {"primary": len(gw_result["consecutive"]), "checks": gw_result["total_registered_cutoffs"],
              "agreement": gw_result["total_sql_matches"], "control": gw_result["enriched_control"]}
    shadow = json.loads((PRODUCT / "action_study/shadow/PUBLIC_RESULT.json").read_bytes())["science"]
    rehearsal = {"slots": len(shadow["cases"]), "witnesses": shadow["unique_positive_witnesses"],
                 "deliveries": shadow["arms"]["C"]["correct_deliveries"], "participants": shadow["participants"],
                 "real_decisions": shadow["real_beneficiary_queue_decisions"],
                 "accepted": {k: row["accepted"] for k, row in shadow["arms"].items()}}
    return {"shadow": rehearsal, "trial": trial, "cases": {"ztf-persistence": ztf, "gw-status": gw, profile: engineering},
            "references": reference_rehearsal(), "review": review, "census": census, "costs": economics}


if __name__ == "__main__":
    print(json.dumps(reference_rehearsal(), indent=2, allow_nan=False))
