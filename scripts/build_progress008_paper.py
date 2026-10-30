"""Build an ongoing progress paper only from an exact published Git source freeze.

The source registry, this builder and every consumed input must exist in that
commit. No experiment, network call or candidate mutation occurs in this build.
"""
import argparse
import datetime as dt
from fractions import Fraction
import hashlib
import html
import json
from pathlib import Path
import platform
import re
import resource
import subprocess
import sys
import time

REPO_URL = "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
PRIOR_PAPER_CPU_SECONDS = 10.229196
REMAINING_PAPER_CPU_CEILING = 589


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tex(value):
    return "".join({"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}.get(c, c) for c in str(value))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--source-ref", required=True)
    p.add_argument("--inputs", required=True, help="Source registry path in that public commit")
    p.add_argument("--self-path", required=True, help="This unchanged builder's path in the same commit")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--no-compile", action="store_true")
    args = p.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_ref):
        raise ValueError("An exact 40-character published source ref is required")
    resource.setrlimit(resource.RLIMIT_CPU, (REMAINING_PAPER_CPU_CEILING, REMAINING_PAPER_CPU_CEILING))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    start = time.monotonic()
    start_utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    root, out = args.repo.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    consumed = {}
    def read_bytes(path):
        result = subprocess.run(["git", "show", args.source_ref + ":" + path], cwd=root, capture_output=True)
        if result.returncode:
            raise ValueError("INPUT_ABSENT_FROM_SOURCE_FREEZE " + path)
        consumed[path] = {"sha256": sha(result.stdout), "bytes": len(result.stdout)}
        return result.stdout
    def read_json(path):
        return json.loads(read_bytes(path))
    if read_bytes(args.self_path) != Path(__file__).read_bytes():
        raise ValueError("EXECUTING_BUILDER_NOT_SOURCE_MATCHED")
    registry = read_json(args.inputs)
    paths = registry["records"]
    records = {key: read_json(path) for key, path in paths.items()}
    for path in registry.get("support", []):
        read_bytes(path)
    ref = args.source_ref
    source_time = subprocess.run(["git", "show", "-s", "--format=%cI", ref], cwd=root, capture_output=True, check=True).stdout.decode().strip()
    link = lambda path: REPO_URL + "/blob/" + ref + "/" + path
    ids = {key: "S" + str(i + 1) for i, key in enumerate(paths)}
    a = records["allocation"]
    xp, xc, xv = records["xct_protocol"], records["xct_constructor"], records["xct_verifier"]
    gap_record = xv["routes"]["ordinary_pdhg"]["exact_gap"]
    gap = Fraction(int(gap_record["numerator"]), int(gap_record["denominator"]))
    if not (xv["artifact_integrity_verified"] and xv["routes"]["ordinary_pdhg"]["both_witnesses_exactly_feasible"] and gap > Fraction(1, 200)):
        raise ValueError("XCT_PROOF_FACTS_CHANGED_REVIEW_NARRATIVE")
    nr, no, np, nc = (records[k] for k in ["nasa_refined", "nasa_ordinary", "nasa_plane", "nasa_coverage"])
    refined_max = next(r for r in nr["results"] if r["side"] == "max")
    plane_same = next(r for r in np["results"] if r["scope"] == "refined_max_overlap")
    plane_all = next(r for r in np["results"] if r["scope"] == "all_reference_valid")
    deep = next(r for r in nc["rows"] if r["version"] == "refined" and r["side"] == "max")["strata"][0]
    if not plane_same["mae_mm"] < refined_max["mae_mm"]:
        raise ValueError("NASA_COMPARATOR_FACTS_CHANGED_REVIEW_NARRATIVE")
    er, eq = records["eis_result"], records["eis_dense_check"]
    old, current = records["economics_original"], records["economics_current"]
    reserved = current.get("conservative_reserved_CPU_seconds", current.get("conservative_charged_CPU_seconds"))
    if reserved is None:
        raise ValueError("CURRENT_JOURNAL_RESERVATION_FIELDS_UNSUPPORTED")
    earned = current["qualified_simulated_commercial_earnings_microUSD"]
    if earned != 0 or old["complete_profit_USD"] is not None:
        raise ValueError("ECONOMIC_FACTS_CHANGED_REVIEW_NARRATIVE")
    sections = []
    def section(name):
        blocks = []; sections.append((name, blocks)); return blocks
    def para(blocks, value, *refs):
        blocks.append(("p", value, refs))
    def table(blocks, heads, rows):
        blocks.append(("table", (heads, rows), []))
    def equation(blocks, latex, plain):
        blocks.append(("equation", (latex, plain), []))
    def code(blocks, lines):
        blocks.append(("code", "\n".join(lines), []))

    b = section("Purpose and ongoing decision")
    para(b, "The mission is a connected invention-and-commercial flywheel: a new productive means must improve a consequential delivery, create defensible accepted value and unrestricted earned resources, then fund a constructed successor with attributable fresh benefit. This progress edition records further real construction after an execution-environment interruption. Rejected opportunities, proof checks and papers do not complete that mission. The original overnight window remains open at this source freeze; this is not its final closeout.", "allocation")
    para(b, "MISSION NOT COMPLETE. New exact finite-model XCT witnesses refute angle selection under the declared recovery model. A real NASA paired-modality implementation executes, but a featureless plane beats its primary whole-field endpoint. A real battery-data probe reproduces an ordinary drift-aware estimate already supplied by established operando methods. No new admitted useful capability, negative-to-positive complete-cost crossing, qualified earnings or earned-funded successor is established.", "xct_verifier", "nasa_plane", "eis_result", "economics_current")
    table(b, ["Mission link", "Decision", "Scope at source freeze"], [
        ["Enabling capability", "NOT ESTABLISHED", "Real instruments/controls execute; newly attainable consequential work unproved."],
        ["Technical advantage", "NOT ESTABLISHED", "Known methods tie, supply the capability, or falsify the chosen proxy."],
        ["Complete-cost profitability", "NOT ESTABLISHED", "No admitted loss cohort; complete costs and participation unknown."],
        ["Investment attractiveness", "NOT ESTABLISHED", "Complete incremental NPV unknown; non-entry remains available."],
        ["AGI ALPHA value capture", "CONDITIONAL", "Possible scoped service only; no purchase or enforceable revenue observed."],
        ["Unrestricted simulated earnings", "VERIFIED: ZERO", "No qualified commercial earned funds."],
        ["Earned-funded successor", "NOT ESTABLISHED", "Current construction uses the original allocation."],
        ["Fresh successor advantage", "NOT ESTABLISHED", "Actual biological retention ties ordinary reuse/reset; no fresh causal edge."],
    ])

    b = section("Continuity, interruption and the complete investigated set")
    para(b, "The distinct campaign remains PR #12. PR #10's negative predictor result and the separately owned PR #11 work are preserved. The integration owner reported missing private source, arrays and paper files after environment replacement. Public source and prior reviews survived. The historical 3360acaf edition is preserved separately; the new recovered calibration/proof is explicitly a different model edition, not a claim to have recreated lost bytes under old hashes.", "interruption")
    table(b, ["Investigated direction", "Actual work", "Decision or missing obligation"], [
        ["Biological measurement", "Exact scale constraints, confined plan execution, independent acceptance, actual Crauste retrieval.", "Conventional methods tie; physical calibration and consequence absent."],
        ["Geothermal measurement", "All 64 reduced-model thermal/pressure designs and refinement executed.", "Ordinary robust OED ties; field calibration missing."],
        ["Rotational manufacturing", "24 real CAD assemblies checked.", "Native strong route unqualified; no weakened translation-only control."],
        ["Walnut XCT", "New full120 ordinary direct/PDHG construction and independent exact primal check.", "Unchanged-model angle-selection target refuted."],
        ["NASA surface metrology", "Paired real modalities, four ordinary face/version outputs, plane comparator, coverage audit.", "Flat-majority endpoint falsified; physical feature qualification absent."],
        ["Operando battery EIS", "Real measured current/voltage, dynamic reference, Fourier/drift ordinary route, dense QR check.", "Broad equilibrium-removal lever already available; no new means admitted."],
    ])
    para(b, "This table accounts for the investigated set; it is not a homogeneous statistical cohort or an admitted commercial customer cohort. The six-hour window ends " + a["end_utc"] + ", with development scheduled to end " + a["development_end_utc"] + " and the last 90 minutes reserved for verification/publication/recovery. Neither interruption nor a new model resets resources, permissions or claim history. All current scientific inputs are exposed DEVELOPMENT; no protected scientific confirmation or population inference is asserted.", "allocation")

    b = section("Constructed full-view obstruction on measured XCT inputs")
    para(b, "The new edition " + xp["edition"] + " uses real Walnut projections and the supplied forward operator. The fit and empirical detector envelope consume all120 views and the1200-view reconstructed reference. The frozen model has nonnegative images, original ray residual bands and the fixed 6-by-6 ROI objective; no upper bound or prior is added. Its exact binary64 coefficients are a digital mathematical contract, not a verified physical noise or material class.", "xct_protocol", "xct_model")
    equation(b, r"\mathcal F_S=\{x\geq0:|A_Sx-y_S|\leq\varepsilon_S\},\quad w_S=\max_{x\in\mathcal F_S}c^\top x-\min_{x\in\mathcal F_S}c^\top x.", "F_S = {x >= 0: |A_S x - y_S| <= epsilon_S}; w_S = max c^T x - min c^T x over F_S.")
    para(b, "The competent cheap control moves in a constant-ROI direction to its analytically feasible step. The constructed ordinary alternative uses diagonally preconditioned primal-dual hybrid gradient (PDHG) projection around the reference toward two fixed ROI targets. Construction may use an interior tightening, but the certificate checks the unchanged original bands. Both algorithms are ordinary methods available equally to the baseline. Exact primal checking is established mathematics; no novel optimizer or autonomous invention is claimed.", "xct_protocol", "xct_constructor")
    table(b, ["Executed route", "Exact-check outcome", "ROI gap"], [
        ["Ordinary restricted direct direction", "Both nonnegative and all original inequalities feasible", "%.12g" % xv["routes"]["ordinary_direct"]["gap_float"]],
        ["Ordinary PDHG pair", "Both nonnegative and all 19,680 original inequalities feasible", "%.15g > 0.005" % float(gap)],
        ["Independent Fraction verifier", xv["verdict"], "Source/model/array identities and exact margins agree"],
    ])
    equation(b, r"\Delta=\frac{" + str(gap.numerator) + "}{" + str(gap.denominator) + r"}>\frac1{200},\qquad \mathcal F_{120}\subseteq\mathcal F_S\ \Longrightarrow\ w_S\geq\Delta.", "Exact gap = " + str(gap) + " > 1/200. Since F_120 is a subset of F_S, every subset's ROI width is at least that gap.")
    para(b, "The larger feasible pair is a constructive obstruction: it survives every subset, so further angle selection cannot achieve the authored 0.005 development target under this frozen model. The narrow direct pair's smaller gap cannot prove complete identification. The target is neither a buyer tolerance nor an industrial quality obligation. No fewer-acquisition saving follows when the fit/envelope already consumes all views and a high-view reference.", "xct_verifier")
    para(b, "The separate verifier imports no candidate helper. It reconstructs the reference from frozen affine parameters, reconstructs the detector-envelope rule, checks the fixed objective and recomputes every ray for five arrays with Fraction arithmetic. Its criteria preceded construction; verifier code was completed after the builder summary was exposed. This is deterministic development review, not protected confirmation or external organizational certification. The new proof is distinct from the older public-review-only gap and from the v1 full120 LP timeouts.", "xct_verifier", "xct_verifier_receipt")
    if "xct_package_attack" in records:
        attack = records["xct_package_attack"]
        para(b, "A separately authored package attack executes %d cases on private source-bound copies. The valid control succeeds; missing arrays/records/model dependencies, forged success with a collapsed pair, a fake verifier and an existing output directory are refused. All expected outcomes pass without changing original candidate bytes. This checks the recorded package boundary under a reviewed trust anchor, not an adversarial-host or physical claim." % len(attack["cases"]), "xct_package_attack")
    para(b, "The first verifier failed at startup by requesting hard185 CPU beneath an inherited hard180 ceiling. The repair honors inherited limits without changing the data, cohort, threshold or arithmetic. Current-host sandbox requalification is separately documented for the narrow pure JSON interpreter. Trusted numerical code with process limits is not arbitrary native confinement; the old Landlock/bubblewrap limitations are not silently waived.", "verifier_limit_repair", "sandbox_report")

    b = section("Real paired-modality construction and the plane falsifier")
    para(b, "The NASA Ti-6Al-4V disk supplies reconstructed XCT plus independent optical profilometry. That removes the narrow circular-reference problem of comparing projections with a reconstruction of the same scan, while leaving calibration, registration and internal-defect truth unresolved. The prospective delivery is a registered top-visible surface depth field and validity mask. Its primary endpoint is unchanged all-valid-overlap mean absolute height disagreement, with every finite reference pixel retained in the coverage denominator. No buyer tolerance or success threshold is invented.", "nasa_protocol", "nasa_sources")
    para(b, "The owned ordinary implementation uses Otsu segmentation, visible-ray intersection, plane detrending and rigid registration. After integer-height bands and a flat-dominated registration objective were observed, ordinary subvoxel interpolation and depression-feature registration were constructed and executed. Both CT faces and all original outputs remain. This is developer-directed conventional repair. Published 2024/2025 routes also use supervised/manual pore domains and occlusion-aware methods that were not fully reproduced here; absent labels and transforms cannot be treated as a baseline win.", "nasa_chronology", "nasa_refined")
    rows = []
    for label, result in [("Initial", no), ("Refined", nr)]:
        for row in result["results"]:
            rows.append([label + ", " + row["side"] + " face", "%.8f" % row["mae_mm"], str(row["overlap_pixels"]) + "/" + str(row["reference_valid_pixels"]) + " (%.2f%%)" % (100 * row["coverage"]), "%.8f" % row["depth_strata"][0]["mae_mm"]])
    rows += [["Zero plane, all finite reference", "%.8f" % plane_all["mae_mm"], str(plane_all["n"]) + "/" + str(plane_all["n"]) + " (100%)", "%.8f" % plane_all["depth_strata"][0]["mae_mm"]], ["Zero plane, refined-max overlap", "%.8f" % plane_same["mae_mm"], str(plane_same["n"]) + "/" + str(plane_all["n"]), "%.8f" % plane_same["depth_strata"][0]["mae_mm"]]]
    table(b, ["Ordinary method", "Whole-field MAE (mm)", "Coverage", "Deep-stratum MAE (mm)"], rows)
    para(b, "A zero-height plane identifies no pores, yet its %.8f mm MAE on the exact refined overlap beats %.8f mm from the refined reconstruction. The primary endpoint is defeated and retained as a failure. The refined method has %.2f%% overall overlap, but retains only %d/%d = %.2f%% of the original below-minus0.1 mm reference stratum. Its lower deep-region disagreement does not erase missing deep features. These depth strata are diagnostic, not new accepted pore masks or a retroactively narrowed cohort." % (plane_same["mae_mm"], refined_max["mae_mm"], 100 * refined_max["coverage"], deep["overlap_pixels"], deep["reference_finite_pixels"], 100 * deep["coverage"]), "nasa_plane", "nasa_coverage")
    para(b, "The TIFF header requires float64 despite the catalogue's single-precision wording. Exported finite heights lie on a 0.01 mm grid; nominal sampling/resolution is not a hard error bound. Fitted registration, missing profilometry, downsampled XCT and the absent original calibration prevent physical pore or internal-integrity qualification. Saved-array math.fsum checks independently recompute arithmetic but are a same-author self-check, not independent data or extraction. Threshold/registration sensitivity and the syntax failure remain preserved.", "nasa_array_check", "nasa_chronology", "nasa_resource")
    if records["nasa_independent"]:
        ni = records["nasa_independent"]
        common = ni["common_overlap_diagnostic"]["max"]
        para(b, "A separate verifier decodes the original TIFF independently, checks all frozen identities, reconstructs saved resampling/transforms/masks and recomputes the four numerical outcomes without importing builder functions. The reported arithmetic and reconstruction checks pass; segmentation and registration optimization are not rerun. On %d common max-face pixels, the conventional refinement reduces MAE from %.8f to %.8f mm, while the zero plane remains better at %.8f mm. This supports an ordinary development improvement on the same points, alongside the unchanged consequential endpoint failure." % (common["common_pixels"], common["v1_MAE_mm"], common["refined_MAE_mm"], common["zero_plane_MAE_mm"]), "nasa_independent")
        ramps = ni["coordinate_ramp_witnesses"]
        table(b, ["Executed XY ramp", "Nominal spacing (mm)", "Effective spacing (mm)", "Far-end discrepancy (mm)"], [["Axis " + str(r["axis"]), "%.7f" % r["nominal_output_spacing_mm"], "%.10f" % r["effective_zoom_center_spacing_mm"], "%.7f" % r["far_endpoint_discrepancy_mm"]] for r in ramps])
        para(b, "The physical-coordinate ramp establishes a processing defect: endpoint-preserving zoom after dimension rounding does not exactly implement the requested CT-center spacing. Rigid registration cannot generally remove scale error. Its contribution to height MAE and a physical uncertainty bound are not established. The typed repair is to define output physical coordinates/origin/spacing and interpolate at those coordinates with an explicit validity mask. Original results stay frozen, and any repaired sampling needs a separately identified development cohort because coordinates and missingness change.", "nasa_independent", "nasa_ramp")

    b = section("Operando electrochemistry: the strong baseline already supplies the lever")
    para(b, "The proposed useful activity is measuring evolving battery/fuel-cell response without waiting for equilibrium. Existing complete operando/LTV methods already provide that broad capability. A prospective single-data protocol chooses the smaller public Samsung48X 5-degree charging file before numeric inspection. The pinned source record contains %d samples, %d periods and %.1f minutes of current/voltage. The source explicitly warns that phase is affected at high frequencies; %d bins at or above10 Hz are excluded, leaving %d interpretable frequencies and %d prespecified interior period centers." % (er["samples"], er["periods"], er["duration_seconds"] / 60, er["excluded_calibration_affected_bins_ge10hz"], er["interpretable_frequency_bins_below10hz"], er["interior_period_count"]), "eis_protocol", "eis_data", "eis_result")
    para(b, "The supplied time-varying impedance is an established algorithmic estimate, not independent physical truth. Ordinary per-period Fourier ratios serve as a stationary ablation. Ordinary joint sinusoid/quadratic-drift least squares uses a Fourier/Schur formulation and retains all source excited tones as nuisance components. This natural competent baseline is compared on the same allowed frequencies; the weaker stationary estimator is not promoted to the strongest complete route.", "eis_result", "eis_sources")
    table(b, ["Executed diagnostic", "Median disagreement", "95th percentile"], [[name, "%.4f%%" % (100 * er["baseline_endpoints"][key]["median_relative_complex_disagreement_to_provided_dynamic_estimate"]), "%.4f%%" % (100 * er["baseline_endpoints"][key]["p95_relative_complex_disagreement"])] for name, key in [("Stationary per-period FFT", "stationary_period_fft"), ("Ordinary joint Fourier/quadratic drift", "joint_fourier_quadratic_drift")]])
    para(b, "A natural dense pivoted-QR least-squares control on the same first real period has %d rows and %d columns. Its relative coefficient discrepancy from the closed-form ordinary implementation is %.5g against the prespecified %.1g implementation-check tolerance. This checks numerical equivalence only. An initial validator incorrectly refused unsigned integer metadata; the repaired validator retains finite-value, shape, time and frequency requirements without changing source, cutoff or cohort." % (eq["rows"], eq["columns"], eq["relative_coefficient_disagreement"], eq["qualification_tolerance"]), "eis_dense_check", "eis_failure")
    para(b, "Agreement with a supplied dynamic estimate is reproduction, not new physical accuracy or kinetics identification. Published trend removal, stronger coupled measurements and current AI-native alternatives remain available; their full packages were researched, not all executed. The broad lever is rejected as flagship. A future fast-transition measurement instrument requires a fixed consequential obligation, independently characterized transient reference and a real perturbation inventory. Those data cannot be created by treating this estimate as truth or a favorable synthetic world as physical validation.", "eis_sources", "eis_protocol")

    b = section("Mechanism provenance and limits of retained capability")
    para(b, "The biological construction connects the existing structural mapping engine, generated exact linear plans, actual confined execution, independent acceptance authority and real retention use. The gauge analogy and typed graphs were researcher supplied; bounded matching and program search act on them. Unknown gain, unsupported obligation and forged-receipt defects generated executed repairs. Crauste returns the correct zero-addition plan in retained, ordinary equal-content reuse and reset arms. No complementary inheritance or improved discovery policy is established.", "biology", "retention")
    para(b, "The newer cycles extend the critic-to-construction path without relabeling ordinary algorithms as invention. The XCT pair-separation failure becomes a fixed feature-range constraint, and a new exact full-view pair constructs the obstruction. NASA's flat-majority failure becomes an explicit coverage/feature-obligation defect; it is not repaired by quietly changing the endpoint. The EIS baseline rejects an already available lever. These retained constraints can guide the next search, but usefulness on fresh successor construction has not been demonstrated. No earned funding pays for these constructions.", "xct_verifier", "nasa_coverage", "eis_result")
    para(b, "Builders, reviewers and integration share a model family, host, libraries and public sources. Separate roles provide procedural challenge and source-bound arithmetic, not external certification. The published model/source identities and numerical receipts establish their stated finite scope; physical coverage, buyer acceptance and complete economics remain separate obligations.", "xct_verifier")

    b = section("Complete costs, cash and the unchanged funding boundary")
    ceilings = current["original_CPU_ceilings"]
    para(b, "The latest append-only accounting snapshot reserves %d experiment CPU-seconds and %d verification/publication CPU-seconds against original ceilings of %d and %d. These are conservative reservation charges including explicit unknown-history holdbacks, not observed complete CPU, monetary expenses or new authority. Nested worker receipts are not added to their enclosing runs, and failed reservations are not refunded. Journal history, missing controller/inference/lost-private costs and the original end time remain visible." % (reserved["experiment"], reserved["verification_publication"], ceilings["experiment"], ceilings["verification_publication"]), "economics_current", "economics_original")
    table(b, ["Complete-cost category", "Monetary treatment"], [[key.replace("_", " "), "UNKNOWN; no observed finite upper bound"] for key in old["monetary_cost_categories"]])
    para(b, "Complete profit, deployment unit cost and enterprise recovery remain unknown. Posted scanner/reconstruction prices are substitute sensitivities, not AGI ALPHA demand, avoided hours, baseline losses or revenue. Rational participation requires trust-adjusted incremental value after switching/calibration/procurement costs versus free ordinary methods and non-entry. The participation frontier includes zero; no admitted same-cohort negative-to-positive result or investment NPV is established.", "economics_original", "economics_no_earnings")
    para(b, "The unchanged ProtectedExchange qualification refuses earned-funded investment from opening capital, restricted deposits and unsupported delivery. Refund and duplicate handling create no earnings. Its synthetic engineering account is not a customer transaction and bookkeeping profit0 is not complete profit0. Qualified unrestricted simulated earnings are %d microUSD; successor investment remains deferred. All actual construction uses original authorized resources, with no paid API, real commerce, outreach, credentials or weakened controls." % earned, "economics_no_earnings", "economics_current")

    b = section("Public reconstruction, qualifications and next construction")
    para(b, "Each receipt below is bound to its own downloaded archive/source revision. A later paper source freeze does not move an older qualification to a new head. Source matching proves byte identity; green CI and document regeneration do not certify experimental truth, physical feasibility or mission success.")
    qualification_rows = []
    for key in registry.get("qualification_records", []):
        q = records[key]
        identities = q.get("all_git_blobs_verified_before_execution", q.get("all_git_blobs_checked_before_first_execution", False))
        qualified = q.get("runtime_qualified", q.get("runtime_qualified_in_scope", False))
        count = q.get("source_files", q.get("complete_git_file_count", "UNKNOWN"))
        qualification_rows.append([q.get("source_ref", "NOT RECORDED")[:12], "YES" if identities else "NOT ESTABLISHED", str(count), "PASS within receipt scope" if qualified else "FAILED / NOT QUALIFIED"])
    if qualification_rows:
        table(b, ["Archive source", "Blob identity", "Source files", "Runtime qualification"], qualification_rows)
    para(b, registry["qualification_narrative"], *registry.get("qualification_records", []))
    legacy = records["legacy_ci_failure"]
    para(b, "Overall hosted qualification is red at source " + legacy["source_ref"][:12] + ". The preserved legacy cycle001 SIGINT probe interrupts STARTED-marker creation before the handler/try region and fails to write its interruption receipt; the same-directory restart refuses. Its 163 inherited tests and21 verifier tests pass, as do the separate008 actual-construction and007 reproduction workflows, but those passes do not erase the failed qualification. Frozen legacy source was not changed and this observation does not establish a new008 regression. Merge/release requires the applicable normal checks; a favorable retry or status fabrication is not used.", "legacy_ci_failure", "legacy_interruption")
    para(b, "The prior sandbox/acceptance dependency and resource failures, historical full152 archive-cap failures and targeted14-test repair are preserved in the historical paper. This edition does not infer a clean full-suite run from a targeted pass. The subsequent archive wrapper failures also remain: allocation or inherited-limit corrections are explicit and source data/claim thresholds are not weakened to produce a pass. Current-host pure-interpreter qualification and trusted numerical bounds have different scopes.", "sandbox_report")
    code(b, registry["reproduction_commands"])
    para(b, "The next consequential construction must change a missing measurement or a genuinely unavailable production outcome. Within the unchanged allocation, the integration owner continues source-grounded construction; the currently falsified angle-selection target is not repeated. New calibration, orthogonal modalities or controlled fast-transition response remain hypotheses until the strongest complete route fails a fixed useful obligation and the new means survives independent measured evidence. At a real resource/access boundary, exact restart instructions must identify that next executable gate. This paper supports that continuing work; it does not announce final morning completion.")
    if registry.get("ongoing_unvalidated"):
        para(b, registry["ongoing_unvalidated"], "economics_current")

    b = section("Source and evidence index")
    historical_path = "docs/overnight008/REPORT.md"
    read_bytes(historical_path)
    b.append(("ref", ("H1", "preserved historical checkpoint; subsequent recovery edition is distinct", link(historical_path)), []))
    for key, path in paths.items():
        b.append(("ref", (ids[key], key.replace("_", " "), link(path)), []))
    title = "Measured Constraints, Exact Obstructions and Strong Ordinary Baselines"
    subtitle = "AGI ALPHA overnight 008 / ongoing source-frozen progress edition"
    abstract = ("A continuing invention campaign constructs and checks real instruments after an execution-environment interruption. A newly frozen Walnut XCT model admits a full120-view nonnegative feasible pair with exact ROI gap %.12g, disproving an authored subset-selection target within that model. A NASA paired XCT/profilometry implementation is challenged by a zero-height plane, which beats its whole-field primary endpoint while deep-feature coverage remains incomplete. A real battery charging record supports ordinary operando drift separation already available through published methods. These are scoped construction and falsification results, not physical or commercial success. All scientific cases remain development-exposed. Complete monetary costs are unknown, qualified unrestricted simulated earnings are zero and no earned-funded successor advantage is established. The original overnight allocation continues without reset." % float(gap))
    snapshot = sha(json.dumps(consumed, sort_keys=True, separators=(",", ":")).encode())
    manifest = {"schema":"agi-alpha/progress008-source-manifest/v1", "source_ref":ref, "source_commit_time":source_time, "created_utc":start_utc, "all_inputs_read_from_exact_git_objects":True, "executing_builder_matches_source":True, "snapshot_sha256":snapshot, "files":dict(sorted(consumed.items())), "excludes":"All generated outputs, avoiding recursive identity.", "scope":"Ongoing source-bound progress checkpoint; not final overnight closeout, numerical rerun or truth certification."}
    (out / "SOURCE_SHA256.json").write_text(json.dumps(manifest, indent=2) + "\n")
    top = "Source freeze: " + ref + "; commit time: " + source_time
    md = ["# " + title, "", subtitle, "", "**MISSION NOT COMPLETE. Ongoing checkpoint; not final night closeout.**", "", top, "", "Source/data snapshot SHA256: `" + snapshot + "`", "", "[PDF](AGI_ALPHA_Progress_008.pdf) | [LaTeX](AGI_ALPHA_Progress_008.tex) | [HTML](index.html) | [Source manifest](SOURCE_SHA256.json)", "", abstract, ""]
    tb = [r"\documentclass[11pt,letterpaper]{article}", r"\usepackage[margin=0.8in]{geometry}", r"\usepackage[T1]{fontenc}", r"\usepackage{lmodern,microtype,amsmath,amssymb,booktabs,longtable,array,xcolor,listings,xurl,fancyhdr}", r"\usepackage[breaklinks=true,colorlinks=true,urlcolor=blue!55!black,linkcolor=black]{hyperref}", r"\pagestyle{fancy}\fancyhf{}\fancyhead[L]{\small AGI ALPHA / ongoing progress checkpoint 008}\fancyfoot[C]{\thepage}\setlength{\headheight}{14pt}", r"\setlength{\parindent}{0pt}\setlength{\parskip}{0.45em}\setlength{\emergencystretch}{2em}\renewcommand{\arraystretch}{1.15}", r"\lstset{basicstyle=\ttfamily\footnotesize,breaklines=true,columns=fullflexible,keepspaces=true,showstringspaces=false}", r"\begin{document}", r"{\LARGE\bfseries " + tex(title) + r"}\par", r"{\large " + tex(subtitle) + r"}\par", r"\small " + tex(top) + r"\par", r"\footnotesize Snapshot SHA256: \texttt{" + snapshot + r"}\par\normalsize", r"\textbf{MISSION NOT COMPLETE. Ongoing checkpoint; not final night closeout.}\par", r"\textbf{Abstract.} " + tex(abstract) + r"\par"]
    hb = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + '</title><style>body{margin:0;background:#f3f6fa;color:#18243a;font:17px/1.6 system-ui,sans-serif}main{max-width:1100px;margin:32px auto;background:white;padding:44px 52px;border-top:6px solid #244f84}h1{line-height:1.15}h2{margin-top:2em;border-bottom:1px solid #d8dfeb}a{color:#244f84;overflow-wrap:anywhere}.status{background:#fff0df;padding:16px}table{border-collapse:collapse;width:100%;font-size:.86rem;margin:22px 0}th,td{text-align:left;vertical-align:top;padding:9px;border-bottom:1px solid #d8dfeb}th{background:#edf2fa}.scroll{overflow-x:auto}pre,.equation{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf2fa;padding:16px;font-size:.85rem}.meta,.reference{font-size:.85rem}@media(max-width:700px){main{margin:0;padding:24px}}</style></head><body><main><h1>' + html.escape(title) + '</h1><p>' + html.escape(subtitle) + '</p><p class="meta">' + html.escape(top) + '<br>Snapshot SHA256: ' + snapshot + '</p><p class="status"><strong>MISSION NOT COMPLETE. Ongoing checkpoint; not final night closeout.</strong></p><nav><a href="AGI_ALPHA_Progress_008.pdf">PDF</a> | <a href="AGI_ALPHA_Progress_008.tex">LaTeX</a> | <a href="REPORT.md">GitHub-readable report</a> | <a href="SOURCE_SHA256.json">Source hashes</a></nav><p><strong>Abstract.</strong> ' + html.escape(abstract) + '</p>']
    for heading, blocks in sections:
        md += ["## " + heading, ""]
        tb.append(r"\section{" + tex(heading) + "}")
        hb.append("<h2>" + html.escape(heading) + "</h2>")
        for kind, value, refs in blocks:
            if kind == "p":
                md += [value + (" " + " ".join("[" + ids[k] + "](" + link(paths[k]) + ")" for k in refs) if refs else ""), ""]
                tb.append(tex(value) + " " + " ".join(r"\href{" + link(paths[k]) + "}{[" + ids[k] + "]}" for k in refs) + r"\par")
                hb.append("<p>" + html.escape(value) + " " + " ".join('<a href="' + html.escape(link(paths[k]), quote=True) + '">[' + ids[k] + ']</a>' for k in refs) + "</p>")
            elif kind == "equation":
                latex, plain = value
                md += [plain, ""]
                tb.append(r"\[" + latex + r"\]")
                hb.append('<div class="equation">' + html.escape(plain) + '</div>')
            elif kind == "code":
                md += ["```sh", value, "```", ""]
                tb += ["\\begin{lstlisting}\n" + value + "\n\\end{lstlisting}"]
                hb.append("<pre>" + html.escape(value) + "</pre>")
            elif kind == "ref":
                ident, label, url = value
                md += ["- **[" + ident + "] " + label + ":** [public source](" + url + ")", ""]
                tb += [r"\begin{samepage}\small\textbf{[" + ident + "] " + tex(label) + r"} \url{" + url + r"}\par\normalsize\end{samepage}"]
                hb.append('<p class="reference"><strong>[' + ident + '] ' + html.escape(label) + '</strong> <a href="' + html.escape(url, quote=True) + '">' + html.escape(url) + '</a></p>')
            elif kind == "table":
                heads, rows = value
                md += ["| " + " | ".join(heads) + " |", "| " + " | ".join("---" for _ in heads) + " |"]
                md += ["| " + " | ".join(str(v).replace("|", "\\|") for v in row) + " |" for row in rows]
                md.append("")
                widths = {2:[.32,.61],3:[.29,.25,.37],4:[.29,.19,.23,.17]}[len(heads)]
                columns = "".join(r">{\raggedright\arraybackslash}p{" + str(w) + r"\linewidth}" for w in widths)
                tb += [r"\begingroup\small\begin{longtable}{" + columns + r"}\toprule", " & ".join(r"\textbf{" + tex(x) + "}" for x in heads) + r"\\\midrule\endhead"]
                tb += [" & ".join(tex(x) for x in row) + r"\\" for row in rows]
                tb += [r"\bottomrule\end{longtable}\endgroup"]
                hb.append('<div class="scroll"><table><thead><tr>' + "".join("<th>" + html.escape(x) + "</th>" for x in heads) + '</tr></thead><tbody>' + "".join("<tr>" + "".join("<td>" + html.escape(str(x)) + "</td>" for x in row) + "</tr>" for row in rows) + '</tbody></table></div>')
    tb.append(r"\end{document}"); hb.append("</main></body></html>")
    tex_path = out / "AGI_ALPHA_Progress_008.tex"
    tex_path.write_text("\n".join(tb) + "\n")
    (out / "REPORT.md").write_text("\n".join(md) + "\n")
    (out / "index.html").write_text("\n".join(hb) + "\n")
    if not args.no_compile:
        command = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(out), str(tex_path)]
        for i in range(2):
            result = subprocess.run(command, cwd=out, capture_output=True)
            (out / ("BUILD_PASS_" + str(i + 1) + ".log")).write_bytes(result.stdout + b"\n" + result.stderr)
            if result.returncode:
                raise RuntimeError("LATEX_BUILD_FAILED")
    own, child = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {"operation":"SOURCE_FROZEN_PROGRESS_PAPER_NOT_EXPERIMENT", "source_ref":ref, "start_utc":start_utc, "end_utc":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "wall_seconds":time.monotonic()-start, "cpu_seconds_self_plus_waited_children":own.ru_utime+own.ru_stime+child.ru_utime+child.ru_stime, "peak_self_rss_kib":own.ru_maxrss, "peak_waited_child_rss_kib":child.ru_maxrss, "prior_paper_measured_build_renderer_cpu_seconds":PRIOR_PAPER_CPU_SECONDS, "original_paper_reservation_cpu_seconds":600, "remaining_process_cpu_ceiling_seconds":REMAINING_PAPER_CPU_CEILING, "memory_bytes_per_process":2*1024**3, "python":platform.python_version(), "complete_monetary_cost":"UNKNOWN", "scope":"Document generation only; rendering, inference, prior campaign and lost costs remain separate or unknown."}
    (out / "BUILD_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"source_ref":ref,"consumed_source_files":len(consumed),"snapshot_sha256":snapshot,"output":str(out),"receipt":receipt,"mission_complete":False}))


if __name__ == "__main__":
    main()
