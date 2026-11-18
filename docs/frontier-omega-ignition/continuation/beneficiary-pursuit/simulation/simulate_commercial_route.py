#!/usr/bin/env python3
"""Scenario analysis for the scroll receiver. All adoption and payment events are hypothetical."""
import argparse
from decimal import Decimal as D
import json
from pathlib import Path

CANDIDATE = "a44aa8535e7899aa197d6e17f567e86547792536"
STUDY = "products/frontier-omega-ignition/invention/scroll_normalization/production_window/sample"
PUBLIC = "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/" + CANDIDATE
COMPARATOR = "https://github.com/ScrollPrize/villa/pull/2521"


def as_number(value):
    return float(round(value, 6))


def decimal(text):
    value = D(text)
    if not value.is_finite() or value < 0:
        raise argparse.ArgumentTypeError("Use a finite nonnegative value")
    return value


def compare(share, overhead, fraction, args, *, name):
    predicted = D("41.2") - D("3.7") * share * fraction + overhead
    saved = D("41.2") - predicted
    marginal_saving = saved / 3600 * args.hourly_value
    enough = saved / D("41.2") >= args.adoption_threshold / 100
    return {"label": name, "wait_share_assumption":as_number(share),
            "overhead_seconds_assumption":as_number(overhead),
            "modeled_reader_seconds":as_number(predicted), "modeled_seconds_saved":as_number(saved),
            "modeled_percent_reduction":as_number(100 * saved / D("41.2")),
            "meets_assumed_time_threshold_if_outputs_match":enough,
            "modeled_machine_value_usd_at_assumed_usage":as_number(marginal_saving * args.runs),
            "runs_to_recover_assumed_adoption_cost": (
                int((args.adoption_cost / marginal_saving).to_integral_value(rounding="ROUND_CEILING"))
                if marginal_saving > 0 else None)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("study", type=Path, help="pinned schedule sample directory from the release candidate")
    p.add_argument("--exposed-share", type=decimal, default=D(".25"))
    p.add_argument("--overhead-seconds", type=decimal, default=D("0"))
    p.add_argument("--adoption-threshold", type=decimal, default=D("3"), help="assumed full-run percent")
    p.add_argument("--runs", type=int, default=10000)
    p.add_argument("--hourly-value", type=decimal, default=D("1"), help="assumed avoidable USD per machine-hour")
    p.add_argument("--adoption-cost", type=decimal, default=D("250"), help="illustrative USD barrier")
    args = p.parse_args()
    if args.exposed_share > 1 or args.adoption_threshold > 100 or args.runs < 0:
        p.error("Fraction, threshold or volume is outside its domain")
    manifest = json.loads((args.study / "sample_summary.json").read_text(), parse_float=D)
    measurements = json.loads((args.study / "sample_receipt.json").read_text(), parse_float=D)
    inc, cand = (manifest[k] for k in ("incumbent_sum_window_medians_ms", "candidate_sum_window_medians_ms"))
    if manifest["tested"] != 24 or measurements["recipient_sha256"] != manifest["recipient_sha256"]:
        raise ValueError("Unexpected study or mismatched receiver")
    rows = measurements["tests"]
    sparse = [r for r in rows if r["mad"] == 0]
    sparse_delta = sum(r["median_cpu_ms"]["incumbent"]-r["median_cpu_ms"]["candidate"] for r in sparse)
    fraction = 1 - cand / inc
    rows = [compare(D(share), args.overhead_seconds, fraction, args, name=label)
            for share, label in (("0","fully hidden"),(".25","one-quarter exposed"),(".5","half exposed"),("1","all exposed"))]
    central = compare(args.exposed_share, args.overhead_seconds, fraction, args, name="selected assumptions")
    state = "request_real_paired_trial" if central["meets_assumed_time_threshold_if_outputs_match"] else "retain_incumbent"
    print(json.dumps({"status":"SIMULATION_ONLY","code_candidate":CANDIDATE,
          "measured":{"source":PUBLIC + "/" + STUDY,"tested":manifest["tested"],
                      "component_ms":[as_number(inc),as_number(cand)],"sparse_window_indices":[r["ordinal"] for r in sparse],
                      "sparse_share_of_observed_savings":as_number(sparse_delta / (inc-cand))},
          "upstream_observed":{"source":COMPARATOR,"reader_wall_s":41.2,"input_wait_s":3.7,
                               "hardware":"RTX 3080, PHerc0139 w054, batch size 32"},
          "assumptions":{"trial_full_output_parity":"assumed for adoption sensitivity; full recipient workload untested",
                         "sample_component_gain_transports_to_exposed_wait":True,
                         "required_full_run_percent":as_number(args.adoption_threshold),
                         "assumed_uses":args.runs,"assumed_avoidable_USD_per_hour":as_number(args.hourly_value),
                         "assumed_adoption_cost_USD":as_number(args.adoption_cost),
                         "nonlinear_batch_stalls":"unmodeled","beneficiary_response_observed":False},
          "sensitivity":rows,"selected":central,"selected_hypothetical_disposition":state,
          "illustrative_regression":compare(D(0),D(".25"),fraction,args,name="hidden gain and added quarter-second cost"),
          "economic_state":{"real_recipient_stage":"identified","simulated_commercial_outcome":"no payment assumed",
                            "simulated_receipts_usd":0,"simulated_award_probability":None,
                            "real_transaction_reference":None,"whole_run_executed_by_simulator":False}},
          indent=2,allow_nan=False))


if __name__ == "__main__":
    main()
