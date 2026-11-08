#!/usr/bin/env python3
"""Author a readable continuation report from independently checked evidence.

This is a report formatter, not another scientific scorer. It requires the full
classical verification and the separate all-field saved-neural audit, matches
their result identities, and keeps their actual scopes in the output. It never
changes the frozen producer outputs or acceptance rules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARMS = ("fixed_no_history", "ordinary_reuse", "updated_no_artifact",
        "updated_with_artifact", "same_content_empirical", "full_enumeration")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate report key: " + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("Nonfinite report value: " + value)
    def finite(value):
        if isinstance(value, float):
            require(math.isfinite(value), "Nonfinite report number")
        elif isinstance(value, dict):
            for item in value.values():
                finite(item)
        elif isinstance(value, list):
            for item in value:
                finite(item)
    value = json.loads(Path(path).read_text(), object_pairs_hook=unique,
                       parse_constant=invalid)
    finite(value)
    return value


def verification_scope(classical_check, incumbent_check):
    """Validate receipt scope without repeating any scientific computation."""
    require(classical_check["schema"] == "learning-to-build/independent-evidence-check/v1"
            and incumbent_check["schema"] == "learning-to-build/independent-incumbent-check/v1",
            "Unexpected independent verification receipt schema")
    require(classical_check["status"] == incumbent_check["status"] == "VERIFIED",
            "Full positive verification receipts are required")
    classical = classical_check["classical"]
    incumbent = incumbent_check["incumbent"]
    require(classical["status"] == "VERIFIED"
            and classical["donor_calibration_predictions_regenerated"] is True
            and classical["source_and_successor_saved_predictions_regenerated"] is True
            and classical["inventory"]["entry_and_exit_inventory_identical"] is True,
            "Incomplete or changed classical verification scope")
    require(classical_check["incumbent"] is None
            and classical_check["incumbent_coverage"] == "NOT_CHECKED",
            "The classical cost boundary must exclude the separate neural audit")
    require(incumbent["status"] == "VERIFIED_SAVED_PREDICTIONS"
            and type(incumbent["registered_fields"]) is int
            and incumbent["registered_fields"] == 116
            and incumbent["all_saved_masks_independently_rescored"] is True
            and incumbent["original_reference_archives_independently_decoded"] is True
            and incumbent["inventory"]["entry_and_exit_inventory_identical"] is True
            and incumbent["neural_predictor_reexecuted_by_this_check"] is False,
            "Unexpected or incomplete all-116-field saved-neural verification scope")
    require(incumbent_check["classical_coverage"] == "NOT_CHECKED"
            and incumbent_check["incumbent_coverage"] == "ALL_116_SAVED_PREDICTIONS"
            and type(incumbent_check["saved_prediction_fields_rescored"]) is int
            and incumbent_check["saved_prediction_fields_rescored"] == 116,
            "The neural receipt must identify its separate all-field audit boundary")
    require(classical_check["source_bindings"] == incumbent_check["source_bindings"]
            and classical_check["public_archives"] == incumbent_check["public_archives"],
            "Verification source or public-input bindings differ")
    for receipt in (classical_check, incumbent_check):
        require(receipt["scientific_confirmation"] == "EXPOSED_DATA_REPRODUCTION_NOT_NEW_CONFIRMATION",
                "Unexpected scientific confirmation scope")
        for key in ("actual_cpu_seconds", "actual_wall_seconds"):
            require(type(receipt[key]) in (int, float) and math.isfinite(receipt[key])
                    and receipt[key] >= 0, "Invalid verification cost: " + key)
    require(isinstance(incumbent_check.get("observed_invocation_receipts"), list)
            and incumbent_check["observed_invocation_receipts"],
            "Missing separately observed neural invocation receipt identities")
    require(isinstance(incumbent_check.get("observed_run_reconciliation"), dict)
            and incumbent_check["observed_run_reconciliation"],
            "Missing observed neural run reconciliation")


def accepted(value):
    require(type(value) is bool, "Expected a Boolean verdict")
    return "PASS" if value else "FAIL"


def metric_row(method, split, summary, qualified, metric):
    return (f"| {method} | {split} | {summary['fields']} | "
            f"{summary[metric]:.6f} | {summary['mean_foreground_dice']:.6f} | "
            f"{summary['mean_relative_count_error']:.6f} | {accepted(qualified)} |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path,
                        help="Extracted complete reproduction archive")
    parser.add_argument("--output", required=True, type=Path,
                        help="New report directory outside canonical source")
    args = parser.parse_args()
    evidence, output = args.evidence.resolve(), args.output.expanduser()
    require(output.is_absolute() and not output.exists(), "Choose a new absolute report directory")
    output = output.resolve()
    require(not output.is_relative_to(ROOT.parent) and not output.is_relative_to(evidence),
            "Do not write into canonical source or sealed evidence")
    paths = {
        "classical": evidence / "classical/RESULTS.json",
        "incumbent": evidence / "incumbent/RESULTS.json",
        "classical_check": evidence / "PROJECTED_CLASSICAL_INDEPENDENT_CHECK-002.json",
        "incumbent_check": evidence / "INCUMBENT_INDEPENDENT_CHECK.json",
        "provenance": evidence / "REPRODUCTION.json",
    }
    identities = {name: digest(path) for name, path in paths.items()}
    values = {name: read_json(path) for name, path in paths.items()}
    classical, incumbent = values["classical"], values["incumbent"]
    cc, nc = values["classical_check"], values["incumbent_check"]
    require(classical["status"] == incumbent["status"] == "COMPLETE", "Incomplete producer evidence")
    verification_scope(cc, nc)
    require(cc["classical"]["results_sha256"] == identities["classical"] and
            nc["incumbent"]["results_sha256"] == identities["incumbent"],
            "Verification does not bind these result bytes")
    require(cc["verifier_sha256"] == nc["verifier_sha256"] == digest(ROOT / "check.py"),
            "Verification does not bind the packaged independent checker")
    splits = incumbent["splits"]
    for split in splits.values():
        accepted(split["accepted"])
    source_neural = bool(splits["source_validation"]["accepted"] and splits["source_test"]["accepted"])
    target_neural = bool(splits["successor_calibration"]["accepted"] and splits["successor_test"]["accepted"])
    require(source_neural == nc["incumbent"]["source_qualified"] and
            target_neural == nc["incumbent"]["successor_qualified"], "Verified qualification differs")
    arms = classical["successor"]["arms"]
    require(set(arms) == set(ARMS), "Incomplete six-arm comparison")
    primary = classical["successor"]["primary_comparison"]
    source_methods = []
    if classical["source_qualified"]:
        source_methods.append("classical_r17")
    if source_neural:
        source_methods.append("fixed_pretrained_cpdino_vitb")
    successor_accepted = bool(classical["successor_any_primary_qualified"] or target_neural)
    claims = {
        "software_construction_and_operation": "Observed; see emitted instruments, predictions and separate operation receipts.",
        "source_measurement_qualified_methods": source_methods,
        "local_accepted_prefix_advantage": primary["local_accepted_prefix_advantage"],
        "candidate_evaluations_saved": primary["candidate_evaluations_saved"],
        "total_lifecycle_advantage_established": primary["total_lifecycle_advantage_established"],
        "general_constructor_improvement_established": primary["general_constructor_improvement_established"],
        "successor_measurement_qualified": successor_accepted,
        "exclusive_artifact_enabling_established": classical["successor"]["exclusive_artifact_enabling_established"],
        "external_laboratory_acceptance": False,
        "economic_activity_observed_in_this_experiment": False,
        "actual_customer_acceptance": False,
        "revenue_or_profit_established": False,
        "fresh_scientific_confirmation": False,
        "original_full_result_archive_recovered": False,
    }
    measured = {
        "classical_completed_stage_cpu_seconds": classical["completed_stage_cpu_seconds"],
        "classical_completed_stage_wall_seconds": classical["completed_stage_wall_seconds"],
        "classical_all_measured_attempt_cpu_seconds": classical["all_measured_attempt_cpu_seconds"],
        "classical_all_measured_attempt_wall_seconds": classical["all_measured_attempt_wall_seconds"],
        "classical_has_unmeasured_interrupted_work": classical["has_unmeasured_interrupted_work"],
        "classical_interruption_flag_scope": (
            "Recorded run-state attempts only. False means the retained ledger records no "
            "interrupted or orphaned attempt; it does not prove absence of unrecorded execution."
        ),
        "classical_residual_origin_additional_work": "UNKNOWN",
        "classical_residual_origin_cost": "UNKNOWN",
        "incumbent_sessions": incumbent["sessions"],
        "incumbent_fields_without_completed_session_attribution": nc["incumbent"]["fields_without_completed_session_attribution"],
        "classical_independent_full_check_cpu_seconds": cc["actual_cpu_seconds"],
        "classical_independent_full_check_wall_seconds": cc["actual_wall_seconds"],
        "incumbent_saved_mask_audit_cpu_seconds": nc["actual_cpu_seconds"],
        "incumbent_saved_mask_audit_wall_seconds": nc["actual_wall_seconds"],
        "scope": "Separate observed process boundaries. Setup, acquisition, rejected/superseded checking, operation and other receipts are retained individually. Nested command and session costs overlap; elapsed times from parallel work must not be added as project duration. Missing historical costs, additional work or cost associated with unresolved residual-file provenance, authoring, upstream training and actual host/model billing are unknown, not zero.",
    }
    report = {
        "schema": "learning-to-build/continuation-summary/v1", "edition": "1.1.0",
        "status": "REPRODUCED_WITH_EXPLICIT_CLASSICAL_CHECKPOINT_PROJECTION",
        "evidence_role": "Exposed registered comparison reproduced; not new holdout confirmation or recovery of the earlier missing full package.",
        "claim_verdicts": claims, "input_report_sha256": identities,
        "provenance": values["provenance"], "classical": classical,
        "pretrained_practical_alternative": incumbent,
        "independent_verification": {"classical": cc, "saved_neural_predictions": nc},
        "measured_cost_boundaries": measured,
        "summary_source_sha256": digest(Path(__file__)),
    }
    lines = ["# Results · Learning to Build 1.1.0", "",
             "**This is a new reproduction of an already exposed registered comparison.** "
             "The original full unpushed result package was unavailable. Source and amendments "
             "were recovered; new outputs are not presented as missing historical bytes or fresh confirmation.", "",
             "## Separate outcomes", "",
             "| Question | Observed result |", "| --- | --- |",
             "| Was an executable measurement construction operated? | Generated masks, pixel measurements, source identities and observed run receipts are retained. Packaged raw-image operation has its own separate receipt. |",
             "| Which source methods meet the complete nucleus contract? | " + (", ".join(source_methods) if source_methods else "None") + ". Both validation and test must pass. |",
             f"| Did the primary construction update demonstrate an advantage? | Local accepted-prefix advantage: {primary['local_accepted_prefix_advantage']}; saved candidate executions: {primary['candidate_evaluations_saved']}. General constructor improvement is not established. |",
             f"| Did a whole-cell successor qualify? | {'Yes' if successor_accepted else 'No'}. Classical and pretrained outcomes are separate below. No exclusive artifact-enabling effect is established. |",
             "| Was economic continuation established? | No customer acceptance, sales transaction, earned revenue, profit or measured human-worker productivity gain was established in this experiment. |", "",
             "## Nucleus measurement: official BBBC039 cohorts", "",
             "Acceptance on **both** validation and test: mean instance F1 at IoU strictly greater than 0.5 ≥ 0.70; foreground Dice ≥ 0.85; mean relative count error ≤ 0.20.", "",
             "| Method | Cohort | Fields | Instance F1 | Foreground Dice | Relative count error | Cohort gate |",
             "| --- | --- | ---: | ---: | ---: | ---: | --- |"]
    for split in ("validation", "test"):
        lines.append(metric_row("Classical r17", split, classical["source"]["cohorts"][split],
                                classical["source"][split + "_qualified"], "mean_instance_f1"))
    for split in ("source_validation", "source_test"):
        row = splits[split]
        lines.append(metric_row("Fixed pretrained specialist", split.removeprefix("source_"),
                                row["summary"], row["accepted"], "mean_instance_f1"))
    lines += ["", "The pretrained result uses established CellposeDINO weights and different learned stock. "
              "It is a practical alternative, not evidence that the local classical constructor learned that competence. "
              "Pretraining overlap is unknown. Official image partitions are retained; all 18 test plates also appear in training, so this is not unseen-plate confirmation.", "",
              "## Whole-cell successor: BBBC007", "",
              "The registered contract requires internal-boundary F1 within two pixels ≥ 0.60, both across all fields and across fields with true internal boundaries; Dice ≥ 0.80 and relative count error ≤ 0.25. It also requires at least one boundary-bearing calibration field and two test fields. All four calibration and twelve test fields are boundary-bearing in this reproduction.", "",
              "| Method | Cohort | Fields | Boundary F1 | Foreground Dice | Relative count error | Cohort gate |",
              "| --- | --- | ---: | ---: | ---: | ---: | --- |"]
    chosen = arms["fixed_no_history"]
    for split, key, verdict in (("calibration", "calibration", "calibration_qualified"),
                                 ("test", "holdout", "heldout_qualified")):
        lines.append(metric_row("All six classical selections (r12)", split, chosen[key],
                                chosen[verdict], "mean_internal_boundary_f1"))
    for split in ("successor_calibration", "successor_test"):
        row = splits[split]
        lines.append(metric_row("Fixed pretrained specialist", split.removeprefix("successor_"),
                                row["summary"], row["accepted"], "mean_internal_boundary_f1"))
    lines += ["", "## Construction comparison", "",
              "All six arms share the 24-recipe bank, target inputs and acceptance rules. Donor-history and privileged-artifact access vary by design. **The primary greedy-coverage and empirical-ranking pair receives the same donor records.** No artificially tight search limit excludes complete enumeration.", "",
              "| Arm | Calibration candidates | Calibration field evaluations | Selected recipe | Complete successor gate |",
              "| --- | ---: | ---: | --- | --- |"]
    for arm in ARMS:
        row = arms[arm]
        require(row["selected_recipe_id"] == "r12" and row["calibration"] == chosen["calibration"]
                and row["holdout"] == chosen["holdout"], "Cannot group unequal classical outcomes")
        lines.append(f"| {arm} | {row['calibration_candidates_executed']} | {row['calibration_field_evaluations']} | {row['selected_recipe_id']} | {accepted(row['complete_qualification'])} |")
    lines += ["", "The tie concerns selected recipe, quality and candidate count. Actual measured times differ; this one task does not establish statistical equivalence across a task population. The update changes an ordering parameter in a supplied finite method. It does not discover a new algorithm or learn a better update rule.", "",
              "## Failure diagnosis and next decision", "",
              "| Diagnostic on 12 successor test fields | Boundary F1 | Dice | Count error | Information boundary |",
              "| --- | ---: | ---: | ---: | --- |"]
    for label, key, info in (("Unchanged source artifact", "old_artifact", "Raw inputs; fails the target contract"),
                              ("Reference-assisted target diagnostic", "oracle_input", "Manual nuclei AND manual foreground; not a qualifying raw-input construction")):
        row = classical["successor"]["diagnostics"][key]["holdout"]
        lines.append(f"| {label} | {row['mean_internal_boundary_f1']:.6f} | {row['mean_foreground_dice']:.6f} | {row['mean_relative_count_error']:.6f} | {info} |")
    lines += ["", "Supplying both reference inputs lets the diagnostic meet heldout numerical gates. That comparison does not isolate which supplied input caused the improvement, and it does not supply an operable raw-image route. It supports investigating target-appropriate foreground and seed recovery before another frozen confirmation. The official dataset's historical oracle/precision result is not a directly comparable raw-input F1 score.", "",
              "The existing bank is exhausted. Reordering its members cannot create an acceptable candidate on this calibration set. Retain the strongest measured practical route and the negative construction result. A further claim needs a justified new observation, representation or algorithm, complete conventional alternatives, and genuinely unexposed confirmation cases. Do not relax these criteria after seeing the outcome.", "",
              "The separately frozen [order and component diagnostics](diagnostics/README.md) explain the convergence and distinguish the foreground and seed branches on the four exposed calibration fields. They retain their own registration, masks, replay checks and additional costs. Reference-assisted numerical success is not a qualified raw-input method, and none of these analyses makes the cases fresh.", "",
              "A separately frozen [practical composition](repair/README.md) used actual retained specialist foreground masks with the classical raw-image seed procedure. Its calibration boundary F1 was 0.296809, below 0.60 and below the unchanged specialist's 0.386561. The prespecified stop rule prevented test-field evaluation. This executed negative repair is distinct from the privileged diagnostic and from the unexecuted full raw-input composition command.", "",
              "## What the independent checks establish", "",
              f"The full classical check regenerated **{cc['unique_classical_predictions_regenerated']:,} unique predictions**, including all 2,400 donor predictions and target calibration searches, and independently rescored **{cc['saved_prediction_fields_rescored']} saved field outputs**. It verified all six selections and the unchanged **{cc['classical']['inventory']['files']}-file** canonical projection.", "",
              "The separate neural audit independently decodes the original references and scores every one of the 116 saved predictions. Its receipt explicitly states that it does not rerun model inference, and separately binds the observed run's invocation records. Idempotent resume and raw-image package operation are separate evidence, documented in the provenance and their own receipts; the saved-mask audit does not certify those operations. These checks share project authorship and are not external laboratory certification.", "",
              "## Provenance, recovery and retained adverse evidence", "",
              "The observed classical tree had **416 files**: **278 canonical completed-checkpoint files** and **138 byte-identical residual attempt-file copies**. Strict checking rejects the raw inventory. `classical-residuals/PROJECTION.json` maps all observed files and retains every residual so that the raw tree is reconstructable. The cause remains unknown. No numerical output or measured cost is changed. Actual resume of the projection returns complete/idempotent with unchanged bytes.", "",
              "The source package preserves the original boolean-outline and RGB-observation amendments. The evidence archive retains focused new replays of those failures, the failed ZIP-form upstream download and its exact tar.gz resolution, rejected/superseded verification records, setup logs and the receipt-generation error. A first neural audit rejected a wrong key path in the additive checker's lookup of the pinned model-loading record. The corrected checker is bound to a new full classical replay and all-field neural audit; prior checker source, audit failure and measured work are retained. No producer, criterion, prediction or model was changed for that repair. A focused replay is not recovery of the original missing full-run outputs or cost.", "",
              "## Cost boundaries", "",
              f"Completed classical stages measured **{classical['completed_stage_cpu_seconds']:.3f} CPU seconds** and **{classical['completed_stage_wall_seconds']:.3f} wall seconds**. The full projected independent check measured **{cc['actual_cpu_seconds']:.3f} CPU seconds** and **{cc['actual_wall_seconds']:.3f} wall seconds**. The pretrained sessions are recorded separately:", "",
              "| Session | New fields | CPU seconds | Wall seconds |", "| --- | ---: | ---: | ---: |"]
    for i, session in enumerate(incumbent["sessions"], 1):
        lines.append(f"| {i}: {session['status']} | {session['new_fields']} | {session['actual_cpu_seconds']:.3f} | {session['actual_wall_seconds']:.3f} |")
    lines += ["", f"The neural audit reports **{nc['incumbent']['fields_without_completed_session_attribution']} saved fields without completed-session attribution**. Any such gap is unmeasured work, not zero cost.", "",
              "The classical ledger records three completed attempts and no interrupted or orphaned attempt. Its `has_unmeasured_interrupted_work: false` is a statement about that ledger, not proof that all execution was recorded. The origin of the 138 residual files is unresolved: copying and unrecorded generating work are both compatible with byte identity. Any additional associated work and cost therefore remain unknown. The preserved producer report and measured stage totals are unchanged.", "",
              measured["scope"], "",
              "The five public input archives total 87,775,682 bytes; the fixed model is 343,599,997 bytes. These are identified research inputs, not total network traffic or a complete cost account. The actual scientific run uses a dedicated exact-version environment with selected system-package reuse. A separate installation into a fresh isolated environment verifies the published default setup without changing the experiment's environment or results.", "",
              "There are no observed customer transactions in this experiment. Research operation does not establish downstream commercial permissions, clinical utility, biological conclusions or physical productive expansion.", "",
              "## Reproduce and inspect", "",
              "Use [README.md](README.md) for commands and recovery, [INCUMBENT_SETUP.md](INCUMBENT_SETUP.md) for the fixed specialist, and [RESULTS.json](RESULTS.json) for the complete combined producer reports and exact verification/provenance bindings. `evidence.py` verifies and extracts the compact archive. Its byte-identity check is distinct from the scientific checker and actual model operation.", ""]
    require(all(digest(path) == identities[name] for name, path in paths.items()),
            "Input reports changed while formatting")
    output.mkdir(parents=True)
    (output / "RESULTS.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (output / "RESULTS.md").write_text("\n".join(lines))
    (output / "CLAIMS.json").write_text(json.dumps({"schema": "learning-to-build/claim-verdicts/v1",
        "edition": "1.1.0", "claims": claims, "report_sha256": digest(output / "RESULTS.json")},
        indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FORMATTED_FROM_VERIFIED_EVIDENCE", "output": str(output),
                      "source_methods_qualified": source_methods, "successor_qualified": successor_accepted},
                     indent=2))


if __name__ == "__main__":
    main()
