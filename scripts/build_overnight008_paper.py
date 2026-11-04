"""Build the source-bound ongoing overnight research edition."""
import argparse
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/overnight008"
REPO = "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tex(text):
    return "".join({"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}.get(c, c) for c in str(text))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-ref", default="WORKING_TREE")
    p.add_argument("--cutoff-utc")
    p.add_argument("--no-compile", action="store_true")
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    consumed = set()

    def read(path):
        consumed.add(path)
        return json.loads((ROOT / path).read_text())

    def add(path):
        if (ROOT / path).is_file():
            consumed.add(path)

    science_path = "evidence/overnight-008/science-development/PROBE_RESULT.json"
    science = read(science_path)
    crauste_path = "evidence/overnight-008/crauste-development/TRANSFER_RESULT.json"
    crauste = read(crauste_path)
    retained_path = "evidence/overnight-008/retained-crauste-development-r1/artifacts/REPORT.json"
    retained = read(retained_path)
    acceptance_path = "evidence/overnight-008/observability-accepted-r2/REVIEW.json"
    acceptance = read(acceptance_path)
    energy_path = "research/energy008/EXCITATION_RESULT.json"
    energy = read(energy_path)
    refinement_path = "research/energy008/REFINEMENT_RESULT.json"
    refinement = read(refinement_path)
    cad_path = "research/manufacturing008/DATA_READINESS.json"
    cad = read(cad_path)
    allocation_path = "campaign/overnight-008/ALLOCATION.json"
    allocation = read(allocation_path)
    econ_path = "campaign/overnight-008/economics/FRONTIER_RESULT.json"
    econ = read(econ_path)
    price_path = "campaign/overnight-008/economics/PRICE_AND_DEMAND_SOURCES.json"
    read(price_path)
    forcing_paths = {name: "evidence/overnight-008/science-forcing-r5/" + name + "-forcing-r5/TRANSFER_RESULT.json" for name in ["elowitz", "crauste", "boehm"]}
    forcing = {name: read(path) for name, path in forcing_paths.items()}
    literal_path = "research/observability008/LITERAL_QUALIFICATION.json"
    literal = read(literal_path)
    hosted_failure_path = "evidence/overnight-008/hosted-missing-dependency/FAILURE.json"
    read(hosted_failure_path)
    archive_receipt_path = "evidence/overnight-008/archive-and-isolation-sized-008/RECEIPT.json"
    read(archive_receipt_path)
    for path in [
        "scripts/build_overnight008_paper.py",
        "scripts/replay_literal_check008.py",
        "inventions/observability008/interpreter.py",
        "experiments/observability008.py",
        "verification/accept_linear_plan008.py",
        "verification/observability008_AUTHORITY.json",
        "mechanisms/mapping.py", "flywheel/sandbox.py", "flywheel/retention.py",
        "experiments/resource006.py", "vendor/alpha_claim/protected_exchange.py",
        "research/observability008/elowitz/gauge_probe.py",
        "research/observability008/compile_petab.py",
        "research/observability008/GENERAL_COMPILER_FREEZE.json",
        "research/observability008/GENERAL_TRANSFER.md",
        "research/observability008/compile_petab_forcing.py",
        "research/observability008/gauge_probe.py",
        "research/observability008/check_literals.py",
        "research/observability008/FORCING_CONSTRUCTION.md",
        "research/observability008/FORCING_FREEZE.json",
        "research/observability008/SOURCES.json",
        "research/observability008/elowitz/SOURCES.json",
        "research/observability008/elowitz/SCIENCE_SCREEN.md",
        "research/energy008/excitation_probe.py",
        "research/energy008/enumerate_controls.py",
        "research/energy008/refine_thermal_model.py",
        "research/energy008/SOURCES.json", "research/energy008/SCREEN.md",
        "research/manufacturing008/SCREEN.md",
        "campaign/overnight-008/FOUNDATIONS.md",
        "campaign/overnight-008/economics/ECONOMIC_ADMISSION.md",
        "campaign/overnight-008/economics/LEDGER_REVIEW.json",
        "evidence/overnight-008/interpreter-before-obligation-repair/REASON.json",
        "evidence/overnight-008/forged-acceptance-v1/WITNESS_R2.json",
        "evidence/overnight-008/preflight/PREFLIGHT.json",
        "evidence/overnight-008/preflight/ISOLATION_REVIEW.md",
        "evidence/overnight-008/preflight/LANDLOCK_DECISION.json",
        "evidence/overnight-008/preflight/BWRAP_AVAILABILITY.json",
        "evidence/overnight-008/preflight/SANDBOX_QUALIFICATION.json",
    ]:
        add(path)
    for folder in ["research/observability008/elowitz/source", "research/observability008/crauste/source", "research/observability008/boehm/source"]:
        for path in (ROOT / folder).glob("*"):
            if path.is_file():
                consumed.add(str(path.relative_to(ROOT)))
    for folder in [
        "evidence/overnight-008/observability-development-r2",
        "evidence/overnight-008/observability-accepted-r2",
        "evidence/overnight-008/retained-crauste-development-r1",
        "evidence/overnight-008/science-forcing-r5",
        "evidence/overnight-008/inherited-regressions-008",
        "evidence/overnight-008/inherited-regressions-008-r2",
        "evidence/overnight-008/archive-and-isolation-sized-008",
    ]:
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and path.suffix != ".lock":
                consumed.add(str(path.relative_to(ROOT)))
    files = {name: sha((ROOT / name).read_bytes()) for name in sorted(consumed)}
    exact_commit = bool(re.fullmatch(r"[0-9a-f]{40}", a.source_ref))
    if a.source_ref != "WORKING_TREE" and not exact_commit:
        raise ValueError("--source-ref must be WORKING_TREE or an exact 40-character commit")
    if exact_commit:
        for name, digest in files.items():
            got = subprocess.run(["git", "show", a.source_ref + ":" + name], cwd=ROOT, capture_output=True, check=False)
            if got.returncode or sha(got.stdout) != digest:
                raise ValueError("SOURCE_REF_DOES_NOT_MATCH_CONSUMED_BYTES " + name)
    snapshot = sha(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())
    cutoff = a.cutoff_utc or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    source_ref = a.source_ref if exact_commit else "campaign/overnight-civilization-008-20261030"
    link = lambda name: REPO + "/blob/" + source_ref + "/" + name
    manifest = {
        "schema": "agi-alpha/overnight008-paper-source-manifest/v1",
        "source_ref": a.source_ref,
        "source_ref_matches_all_consumed_files": exact_commit,
        "cutoff_utc": cutoff,
        "snapshot_sha256": snapshot,
        "files": files,
        "excludes": "All generated document outputs and this manifest are excluded, avoiding recursive identity.",
        "status": "Ongoing engineering and experimental checkpoint; not final morning accountability or mission completion.",
    }
    (OUT / "SOURCE_SHA256.json").write_text(json.dumps(manifest, indent=2) + "\n")

    sections = []
    def section(title):
        blocks = []
        sections.append((title, blocks))
        return blocks
    def paragraph(blocks, value):
        blocks.append(("p", value))
    def table(blocks, heads, rows):
        blocks.append(("table", (heads, rows)))
    def code(blocks, lines):
        blocks.append(("code", "\n".join(lines)))
    def equation(blocks, value):
        blocks.append(("equation", value))

    b = section("Purpose, public continuity and present decision")
    paragraph(b, "The goal is an invention-automation enterprise: verified productive capability must create accepted value, defensible AGI ALPHA revenue, unrestricted earned resources, a newly constructed successor and fresh useful benefit. This edition records actual constructions and their consequences during a continuing six-hour allocation. It does not redefine mission success as rejected ideas, passing tests or publication.")
    paragraph(b, "The campaign starts from main cd90c81ab757a7042bf4d0384e8e1a7e6c2a9557 and preserves the negative perturbation-construction release and PR #10. Public draft PR #12 uses a distinct branch. PR #11 retains its own migration/lifecycle and reported molecular-identity measurement work; no part of that continuation is claimed here. The prior predictor experiment is not repeated.")
    paragraph(b, "MISSION NOT COMPLETE at this snapshot. The calibrated ambiguity diagnostic is an executed, independently checked limited instrument, but it ties strong ordinary methods. No admitted same-cohort negative-to-positive complete-cost offering, positive qualified earned balance, earned-funded successor or attributable fresh advantage is established. The team is continuing substantive construction within the remaining allocation.")
    table(b, ["Mission link", "Decision", "Evidence scope"], [
        ["Enabling capability", "NOT ESTABLISHED", "A bounded diagnostic executes; consequential new attainable work is unproved."],
        ["Technical advantage", "NOT ESTABLISHED", "Ordinary complete basis methods and robust thermal design tie."],
        ["Complete-cost profitability", "NOT ESTABLISHED", "No admitted loss-making cohort; participation and lifecycle cost are unbounded."],
        ["Investment attractiveness", "NOT ESTABLISHED", "Non-entry remains an outside option; full incremental NPV is unknown."],
        ["AGI ALPHA value capture", "CONDITIONAL", "Scoped fixed-fee service is a scenario, with no observed purchase."],
        ["Unrestricted simulated earnings", "VERIFIED: ZERO", "Qualified commercial receipts and earned funds remain zero."],
        ["Earned-funded construction", "NOT ESTABLISHED", "Technical transfer uses the original authorized allocation."],
        ["Fresh successor advantage", "NOT ESTABLISHED", "Actual retrieval executes on Crauste; equal-content reuse and reset tie."],
    ])

    b = section("Opening screen and causal selection")
    paragraph(b, "Three materially different directions were screened before flagship admission: energy/infrastructure measurement, manufacturing/material production, and scientific experiment interpretation. Each was challenged against complete current alternatives. Investigation, an executable probe, admission and demonstrated advantage are separate states; none is promoted by experimental convenience.")
    table(b, ["Direction", "Constructed or executed work", "Decision"], [
        ["Energy", "Known flexible-connection and robust-envelope alternatives challenged the broad grid gap; a geothermal thermal/Joule-Thomson measurement instrument was constructed and all 64 interventions evaluated.", "Reduced-model candidate ties robust ordinary OED; no field validation."],
        ["Manufacturing", "Existing ARROWS3 failure-driven precursor selection falsifies that proposed lever. A bounded parser validates 24 real rotational CAD assemblies.", "Full rotation-capable native baseline is blocked, not replaced by a weaker translation control."],
        ["Scientific discovery", "A real SBML/PEtab oscillator is parsed, exact scale ambiguities derived, measurement programs generated and actual model trajectories executed.", "Minimum measurement count ties competent conventional methods."],
        ["Continuing manufacturing pivot", "Sparse-view X-ray feature-bound construction uses measured Walnut data and a supplied forward operator; repair is active.", "Running development lane; no industrial or commercial success admitted."],
    ])
    paragraph(b, "The scientific construction transfers gauge fixing: a latent physical scale and an unknown instrument gain can vary together while the observed readout remains unchanged. The donor analogy and typed representations were supplied by the researcher/assistant. The existing mapping engine searches role correspondences and enforces directed relations and applicability. That output changes the calibration obligation used by the actual plan constructor. This is bounded structural matching, not autonomous discovery of a new physical principle.")
    paragraph(b, "The manufacturing probe is consequential because repair/recycling requires realizable motion rather than a drawing, and geothermal development needs trustworthy thermal evidence rather than a confounded trace. Their importance does not establish a missing means: current physics-based assembly planners already support rotation; coupled thermal models already include Joule-Thomson effects. These capable routes remain the comparators.")

    b = section("Calibration-aware ambiguity instrument")
    paragraph(b, "The source-real test is the PEtab Elowitz_Nature2000 benchmark, pinned to upstream revision c44d5ede9bf979db5aa8ae4e94fc31fba9776675. It contains eight dynamical states, twenty-one estimated parameters and fifty-eight fluorescence measurements. Exact source Git-blob/SHA256 identities and the benchmark BSD license accompany the data. Individual publication/data terms remain relevant; a production licensing clearance is not inferred.")
    paragraph(b, "The reviewed parser interprets a bounded MathML grammar and converts homogeneity relations into rational linear constraints on scaling exponents. A candidate transformation x_i -> lambda^(v_i) x_i and theta_j -> lambda^(w_j) theta_j must preserve the dynamics and observation contract. Initial conditions, fixed quantities and observation/noise definitions constrain the exponent vector. The supported scale family is explicit; absence of such a symmetry is not a proof of global, local or practical identifiability.")
    equation(b, r"Cv=0,\qquad \mathcal{A}=\ker C,\qquad \mathcal{A}_{S}=\ker \begin{bmatrix}C\\H_{S}\end{bmatrix}.")
    paragraph(b, "The constructed program selects conditional calibrated observations whose rows increase rank until the supplied ambiguity space is removed. Weighted independent-row selection is the conventional vector-matroid basis problem, not a new mathematical algorithm. Strong ordinary greedy receives the same rows and method; exhaustive subset enumeration checks the minimum for this small cohort. Measurement cost units here count hypothetical observations, not money.")
    paragraph(b, "An unknown-gain channel cannot be treated as an absolute reference. The executed criticism adds a separate unknown gain for each proposed new fluorescent channel; all three original scale directions remain. The repaired instrument refuses unknown-gain measurements when the fixed task requires absolute calibration. Finite calibration uncertainty and physical acquisition are still UNMEASURED_NOT_ENFORCED; calibrated:true denotes a conditional exact instrument specification.")
    paragraph(b, "Generated measurement programs actually execute after default-deny seccomp through the inherited exact-hash interpreter boundary. Interpreter initialization also occurs after filtering. The worker denies host file, network, exec and fork effects, clears the environment and descriptors, and bounds CPU, address space, input, output and wall time. Trusted scientific parsing/numerical preparation is separately bounded ordinary reviewed code; it is not relabeled arbitrary-code confinement.")
    table(b, ["Scientific result", "Executed value", "Interpretation"], [
        ["Detected scale dimension", str(science["known_scaling_ambiguity_dimension"]), "Known scale directions only."],
        ["Constructed absolute measurements", ", ".join(science["constructed_observation_plan"]), "Unacquired calibrated assay specification."],
        ["Conventional minimum", str(science["ordinary_exhaustive_minimum_observations"]) + " observations; " + str(len(science["ordinary_optimal_sets"])) + " optimal sets", "Tied construction."],
        ["Published-trajectory check", "%.7g maximum absolute error" % science["upstream_numerical_validation"]["maximum_absolute_error"], "Passes fixed 1e-5 digital tolerance; not physical validation."],
        ["Observation-equivalent witness", "%.3g relative fluorescence discrepancy" % science["numerical_witnesses"][0]["relative_output_disagreement"], "All final witnesses obey source parameter boxes."],
        ["Virtual intervention consequence", "%.4f log10 units; %.3f fitted sigma" % (science["numerical_witnesses"][0]["virtual_intervention"]["maximum_fluorescence_log10_disagreement"], science["numerical_witnesses"][0]["virtual_intervention"]["disagreement_over_nominal_sigma"]), "No consequential response failure established."],
    ])
    paragraph(b, "The first large witness proposals crossed two parameter-box boundaries near the nominal fit. Original source, numerical output and the failed bounds flags remain in science-originals. The repair computes feasible log-scale intervals and executes only in-box witnesses. It does not silently retain the inadmissible large effect. A virtual calibrated pulse then tests response relevance; the observed separation is below the fitted single-observation noise scale and its biological attainability is untested.")
    paragraph(b, "StructuralIdentifiability.jl, STRIKE-GOLDD/AutoRepar, minimal-output selection and Data2Dynamics prediction/profile-likelihood experiment design are strong existing alternatives. Their full Julia/MATLAB workflows were researched but not executed in this environment. The executed conventional exact route already ties the limited endpoint; unexecuted mature tools are unmeasured comparators, not victories.")

    b = section("Adversarial repairs and real retained use")
    paragraph(b, "A separate verifier cannot edit the candidate. It checks the real exported program using independent Fraction arithmetic and sorted-once conventional weighted greedy, then executes the proposed plan under the qualified worker. It accepts only the supplied-linear-ambiguity-plan-only scope. It does not certify source-model completeness, physical calibration, economics or scientific superiority. All team roles share model family, host, filesystem, Python and infrastructure; this is procedural separation, not independent organizational certification.")
    table(b, ["Reproduced defect", "Executed change", "Remaining limit"], [
        ["Unknown gain absorbs scale", "Typed calibration gate refuses those observations.", "Finite assay error and actual calibration remain missing."],
        ["Unsupported global-identifiability obligation ignored", "Interpreter and driver reject unsupported fields/obligations; inert provenance is whitelisted.", "Supported linear rank is still incomplete scientific scope."],
        ["Exhaustive control returns SEARCH_LIMIT despite zero-cost full rank", "Already-complete empty plan returns immediately; strong ordinary greedy always remains available.", "No superiority from this repaired control."],
        ["Caller-forged accepted receipt self-approves memory", "Pinned verifier authority binds exact artifact, receipt and verifier-source bytes.", "Authority remains procedural role trust on a shared host."],
    ])
    paragraph(b, "After exact verifier acceptance, the connected driver writes an immutable capability record containing the interpreter identity, generative program, applicability conditions, failed-transfer constraint, source-bound receipt and unknown acquisition costs. The existing retention path actually stores, retrieves, checks source and scope, then uses the returned generative program on a different public model. A JSON description alone is not counted as use.")
    paragraph(b, "Crauste_CellSystems2017 supplies five states, twelve estimated parameters and twenty-one measurements. The generalized compiler correctly treats known zero initial states differently from known nonzero values. Its numerical interpretation differs from the published trajectory by %.3g relative to the largest reference value and passes the prospectively coded relative 1e-4 criterion. That discrepancy and the source-specific tolerances remain visible." % crauste["numeric_validation"]["relative_to_max_reference"])
    paragraph(b, "The different model has no detected scale ambiguity under its existing measured states and known nonzero initial conditions. The retained instrument, equal-content ordinary reuse, strong reset and observation-removal arm all correctly return an empty additional-measurement plan. This is a real memory-path exercise with no inheritance edge. It is a development-exposed different model, not protected confirmation or a statistical sample. Technical generalization is paid from the original allocation, not fictional earnings.")
    paragraph(b, "Complementary inheritance and improvement of invention policy are not established here. A calibration constraint plus an exact rank operator can execute together, but no matched-toolbox old/new discovery-policy experiment shows improved discovery. Acquisition, parser extension and verification must be included before any lifecycle benefit claim.")

    b = section("Constructive extension from real source counterexamples")
    paragraph(b, "A second different-model development task tests the producer itself on the public Boehm STAT5 benchmark (JProteomeRes2014): eight states, nine estimated parameters, three ratio observation formulas and forty-eight measured rows. It was selected after the correct zero-addition Crauste result, so this is an explicitly exposed extension exercise, not a protected sample. The frozen generalized compiler initially refuses its unsupported assignment-rule class before numerical execution.")
    paragraph(b, "The new producer expands only bounded acyclic parameter assignments into an inert expression AST, interprets known time and exponential forcing, and preserves the source's non-unit compartment volumes in concentration-state dynamics. Dynamic rules, events and unsupported source classes remain refused. Lexically different but exactly equal observation times are matched as rational identities without dropping rows or changing numerical thresholds.")
    paragraph(b, "A large independent trajectory failure then exposes a stronger defect: a text-only MathML number reader treats 1.25 with exponent -7 as 1.25 instead of 1.25e-7, a factor of ten million. The repaired exact decoder reads integer, real, e-notation and rational payloads, including separator elements, and rejects unsupported encodings. The source witness decodes to " + literal["decoded"] + "; " + str(literal["ordinary_cases_passed"]) + " ordinary literal cases pass and " + str(literal["unsupported_encodings_refused"]) + " unsupported encodings are refused. The original failed result and exact old source are preserved.")
    table(b, ["Failure or construction", "Executed consequence", "Scope"], [
        ["Frozen compiler refuses rule class", "Bounded acyclic assignment/known-time forcing extension.", "Original frozen general compiler unchanged."],
        ["Non-unit volume refusal", "Concentration dynamics retain known 1.4 and 0.45 compartment volumes.", "Dynamic/estimated volumes still unsupported."],
        ["Time strings 0.0 versus 0", "Exact rational time matching, same identity/order obligations.", "No source rows removed."],
        ["Scientific-number decoding defect", "Prior reference mismatch 91.5242 percentage points; repaired Boehm maximum discrepancy %.7g." % forcing["boehm"]["numeric_validation"]["maximum_absolute_error"], "Digital source fidelity; no physical validation."],
    ])
    table(b, ["Final bounded producer replay", "Detected scale directions", "Published-trajectory check"], [
        ["Elowitz", str(forcing["elowitz"]["known_scale_directions"]), "%.7g maximum absolute discrepancy" % forcing["elowitz"]["numeric_validation"]["maximum_absolute_error"]],
        ["Crauste", str(forcing["crauste"]["known_scale_directions"]), "%.7g absolute / %.7g relative to largest reference" % (forcing["crauste"]["numeric_validation"]["maximum_absolute_error"], forcing["crauste"]["numeric_validation"]["relative_to_max_reference"])],
        ["Boehm", str(forcing["boehm"]["known_scale_directions"]), "%.7g maximum absolute discrepancy" % forcing["boehm"]["numeric_validation"]["maximum_absolute_error"]],
    ])
    paragraph(b, "This is actual critic-to-construction-to-execution work: source counterexamples determine new supported semantics and hard refusals, and the repaired producer runs unchanged across all three original public inputs. It is ordinary developer-directed construction, not autonomous invention, superiority over established scientific tools or earned-funded successor creation. Boehm's fixed initial values and ratio parameter already anchor the detected scales; zero new measurements is the correct limited result.")

    b = section("Geothermal construction and manufacturing continuation")
    paragraph(b, "The energy probe constructs a local pressure-conditioned thermal observability requirement, then implements an advection/conduction/Joule-Thomson model. Source-informed parameters include a 10 m path, 3 m channel width, 0.6 mm aperture and 400 mL/min flow. Sensitivity areas, timing, pressure histories and fixed nuisance bases are declared modeling choices, not fitted field measurements. The source's global injection-production pressure difference is not silently used as a measured local isenthalpic drop.")
    paragraph(b, "All 64 six-segment temperature sequences are evaluated under equal temperature levels, flow, observation horizon and local-pressure obligations. Raw, repaired and ordinary robust OED all choose the same constant-cold sequence 111111; ordinary D-optimal selection chooses 111000 on its own criterion. Candidate gain over the robust complete alternative is zero. Adding artificial heat constraints merely to make modulation win is not an admitted repair.")
    table(b, ["Independent numerical check", "RMSE, degrees C", "Status"], [
        ["30 x 120 grid; 3600 s", "%.6f" % refinement["rows"][0]["rmse_C"], "Numerical reduction check"],
        ["60 x 240 grid; 1800 s", "%.6f" % refinement["rows"][1]["rmse_C"], "Converges downward"],
        ["120 x 480 grid; 900 s", "%.6f" % refinement["rows"][2]["rmse_C"], "Converges downward; field error unknown"],
    ])
    paragraph(b, "The independent discretization check is not field calibration. The advertised GDR circulation download returned a 195-byte SiteUnavailable HTML payload, which is preserved rather than treated as acquired ZIP data. A source report of thermistor water ingress/swollen epoxy also prevents equating catalogue resolution with valid epoch-specific measurement accuracy. Full Wu2021/TOUGH/STOMP field-model qualification is not reproduced; no thermal-production claim follows.")
    paragraph(b, "The CAD readiness parser checks %.0f two-part assemblies (%.0f meshes) from the rotation benchmark without executing downloaded code. Native RedMax/OpenGL qualification is unavailable: bubblewrap cannot create its namespace and Landlock ABI/ruleset calls return ENOSYS. Ordinary rotation-capable BFS/BK-RRT and analytic screw primitives are not weakened into a straight-translation-only control. Fusion360-derived noncommercial research data stay unredistributed; commercial customer rights are not presumed." % (cad["case_count"], cad["part_count"]))
    paragraph(b, "A further construction is testing which quantitative feature claims a sparse X-ray scan supports, using measured Walnut projection data and a supplied sparse forward operator. At this edition's source checkpoint its feature-bound repair is active. The relevant endpoint is reduction of the same feature interval after replaying an actual additional measured view, not merely separation of one conveniently selected pair of candidate images. No final XCT advantage, industrial defect qualification or commercial bridge is admitted in this snapshot.")
    equation(b, r"\mathcal{F}_{S}=\{x\geq0: |A_{S}x-y_{S}|\leq\varepsilon_{S}\},\qquad [\ell_S,u_S]=\left[\min_{x\in\mathcal{F}_S}c^\top x,\max_{x\in\mathcal{F}_S}c^\top x\right].")
    paragraph(b, "For a fixed region-of-interest feature c, eliminating one extremal image pair need not reduce u_S-l_S: replacement feasible images may attain the same endpoints. A useful feature-certainty claim therefore requires re-solving the endpoint problems after acquisition under the same constraints. The first registered XCT probe asks for a witness pair and a view that separates it; satisfying that narrow proxy does not establish the broader feature consequence. A repaired width-reduction endpoint must be registered prospectively as a new development reframing, with this objective history preserved. The feasible set is a digital forward-model/error-envelope class, not all and only physically realizable specimens.")
    paragraph(b, "Certified linear programming, validated conic bounds and independently checkable linear proof logs are established methods. SoPlex, VSDP and VIPR are relevant strong alternatives; exact dual checking is not mathematical invention. The developing XCT certificate must therefore be checked for faithful scaling, rounding and cancellation, and an unqualified numerical dual must not become a positive certificate. No positive repaired certificate is admitted by this edition.")

    b = section("Complete economics and protected funding boundary")
    paragraph(b, "The economic obligation is a useful independently accepted instrument delivery to an identifiable buyer class. Public related services establish substitute-price sensitivities: UC Davis lists external PK modeling/simulation at USD395/hour; UMass imaging modeling/protocol work lists USD500/hour; UCLA lists single-crystal determination at USD500/sample. These differing services do not establish AGI ALPHA's price, required labor duration, eliminated physical work, positive participation or a customer commitment.")
    paragraph(b, "A conditional fixed-fee service would freeze requirements before consent, verify delivery, provide refund/remedy and account separately for support. Buyers retain non-entry, free self-service, ordinary reuse and competent paid substitutes. Trust, integration, switching, correlated failure, unsold work and terminal obligations cannot be removed from the model by assuming a sale.")
    equation(b, r"\Pi=Nqap(1-r)-C_{\rm all}-F-K,\qquad q_{\min}=\frac{C_{\rm all}+F+K}{Nap(1-r)}.")
    paragraph(b, "N is the full frozen admitted cohort, q participation, a acceptance conditional on purchase, p service price, r refund/collection loss, C_all all cohort costs, F acquisition/discovery allocation and K unpriced lifecycle costs. The executed exact-rational frontier includes q=0. No justified finite upper bound on K or strictly positive participation floor is present, so complete-profit sign, economic eligibility and negative-to-positive crossing remain unknown. CPU seconds are not complete monetary costs.")
    table(b, ["Cost or financial quantity", "Treatment"], [
        ["Research, rejected attempts and inference", "Preserved as acquisition work; complete marginal monetary allocation unavailable."],
        ["Data, network, compute and storage", "Measured quantities and source identities where available; absent bills are unknown, not zero."],
        ["Construction, integration, verification and repair", "Actual command receipts and failed versions retained; acquisition recovery horizon unqualified."],
        ["Delivery, support, rework, refunds, warranty and terminal liabilities", "No commercial cohort admitted; obligations require scenario bounds before profit."],
        ["Capital, financing, taxes and outside option", "Investment NPV and complete enterprise recovery remain separate unknowns."],
        ["Accounting, cash and earned resources", "Deposits/restricted reserves are not revenue; reserve release is not new value; qualified earnings are zero."],
    ])
    paragraph(b, "The existing source-pinned Alpha ProtectedExchange is retained rather than replaced. Its reviewed accounting separates revenue/profit, cash, payables, custody/tail/working reserves and unrestrictedEarned. Its expectedNetValue remains a caller assumption; an artifact hash establishes identity, not commercial value. No favorable engineering fixture balance is used to create demand or pay unknown costs. Only unrestricted simulated earned resources may fund a successor; current technical construction is not represented as earned-funded.")
    paragraph(b, "A complete mission needs both a verified technical consequence and a negative-to-positive full-cost result for the same admitted cohort, followed by unrestricted earned funding and attributable fresh successor benefit. None can be assembled from unrelated historical passes. Real payments, customer outreach, contracts, paid API use, credentials or weakened security are outside this mandate.")

    b = section("Resource, exposure and reproduction record")
    paragraph(b, "The recorded fresh allocation runs from %s to %s: 360 minutes, with the last 90 reserved for independent verification, publication and recovery. Observed host capacity is eight CPU cores, an 8 GiB memory limit and approximately 25 GiB free disk. Experiment and verification/publication ceilings are 36,000 and 10,000 CPU-seconds, respectively; artifact and received-data ceilings are 6 and 8 GiB. This paper does not claim that the whole window has elapsed or that unused capacity proves continued unattended work." % (allocation["start_utc"], allocation["end_utc"]))
    paragraph(b, "All scientific panels described here are development-exposed or fixed-artifact engineering reviews. No claim-level protected scientific confirmation is consumed; the campaign-wide superiority error allocation remains unspent. Different cycles, source versions, holdouts or a new model do not reset it. No population-level significance or beyond-human performance is claimed.")
    paragraph(b, "Use a new output directory on every reproduction. The command wrapper is a trusted-command resource receipt, not an arbitrary-code sandbox; the exact interpreter separately confines generated inert programs. Python3.12, NumPy2.3.5 and SciPy1.17.0 were available in the execution environment. Source constraints, raw trajectories, failed witnesses, all 64 thermal designs, acceptance/authority records and exact input hashes remain in the linked evidence.")
    code(b, [
        "python3 -m experiments.observability008 construct \\",
        "  --output /tmp/alpha-observability-NEW",
        "",
        "python3 research/observability008/elowitz/gauge_probe.py \\",
        "  --output /tmp/alpha-gauge-NEW",
        "",
        "python3 -m experiments.observability008 retain-use \\",
        "  --previous /tmp/alpha-observability-NEW \\",
        "  --acceptance evidence/overnight-008/observability-accepted-r2/ACCEPTANCE.json \\",
        "  --fresh research/observability008/crauste/model_constraints.json \\",
        "  --output /tmp/alpha-retained-NEW",
    ])
    code(b, [
        "python3 research/observability008/compile_petab_forcing.py \\",
        "  --source research/observability008/boehm/source \\",
        "  --output /tmp/alpha-boehm-NEW",
        "",
        "python3 scripts/replay_literal_check008.py \\",
        "  --output /tmp/alpha-literal-NEW",
    ])
    paragraph(b, "The literal-check replay wrapper copies three exact source-pinned producer/helper files and Boehm data into a new scratch directory with the historical boehm_source layout. It preserves the frozen helper, which prints its result; the wrapper captures that output as RESULT.json and refuses an existing output directory. A missing dependency or mismatched source cannot be hidden by modifying the golden qualification artifact.")
    paragraph(b, "The existing report builder can be rerun with an exact public source commit. It verifies every consumed file against that commit before emitting LaTeX, PDF, HTML and a SHA256 manifest. A WORKING_TREE edition explicitly records uncommitted source status. Source identity is not truth, and successful regeneration does not establish a profitable offering. Released downloaded-package qualification remains a separate required execution; it is not claimed by a developer-checkout build.")
    paragraph(b, "Qualification history is also preserved. Two full local 152-test inherited-suite attempts failed under file-size ceilings of 8 MiB and 64 MiB while a historical archive needs about 160 MiB. A prospectively enlarged 256 MiB per-file bound then permits all fourteen rerun archive/isolation tests to pass. This is a targeted recovery result, not a clean full-152 rerun claim. No old test, acceptance threshold or candidate implementation was weakened to manufacture green status.")
    paragraph(b, "The first hosted new-loop check at source ff0c3f08ac41379153c2609259bcb94475fe28fa passes four focused tests, confined construction/acceptance/retention and the Elowitz numerical replay, then fails the generalized compiler with ModuleNotFoundError: gauge_probe. The integration omitted its same-directory helper. The exact helper closure is restored, and public-path Crauste/Boehm numerical replays pass without changing model or tolerance. Current exact-head hosted status and final downloaded-package execution must still be read independently; this text does not infer a complete release pass from the local repair.")
    code(b, [
        "python3 scripts/build_overnight008_paper.py \\",
        "  --source-ref EXACT_PUBLIC_SOURCE_COMMIT",
    ])
    paragraph(b, "The next executable construction is feature-bound-driven acquisition on real sparse-view X-ray inputs, preserving the original feature, data/model envelope and competent constrained-inversion controls. Separately, response-relevant biological experiment design requires independently measured attainable perturbations and finite calibration uncertainty. The current boundaries are missing evidence or qualified execution for those claims, not permission to relabel the tied diagnostics as commercial success.")

    b = section("Evidence and primary-source index")
    evidence = [
        ("E1", "Allocation and continuity", allocation_path),
        ("E2", "Actual Elowitz model execution and validation", science_path),
        ("E3", "Independent fixed-artifact engineering acceptance", acceptance_path),
        ("E4", "Connected retained-use result on Crauste", retained_path),
        ("E5", "Geothermal all-design construction result", energy_path),
        ("E6", "Independent numerical refinement", refinement_path),
        ("E7", "CAD source/readiness and execution boundary", cad_path),
        ("E8", "Exact-rational economic frontier", econ_path),
        ("E9", "Public substitute-price evidence", price_path),
        ("E10", "Executing source/provenance map", "campaign/overnight-008/FOUNDATIONS.md"),
        ("E11", "Forcing producer construction and failure history", "research/observability008/FORCING_CONSTRUCTION.md"),
        ("E12", "Final source-real Boehm numerical replay", forcing_paths["boehm"]),
        ("E13", "Inherited archive/isolation targeted recovery", archive_receipt_path),
        ("E14", "Preserved hosted missing-helper failure", hosted_failure_path),
    ]
    for ident, title, path in evidence:
        b.append(("ref", (ident, title, link(path))))
    external = [
        ("P1", "Elowitz and Leibler (2000), A synthetic oscillatory network of transcriptional regulators.", "https://doi.org/10.1038/35002125"),
        ("P2", "PEtab Benchmark Models, exact upstream source revision c44d5ede9bf979db5aa8ae4e94fc31fba9776675.", "https://github.com/Benchmarking-Initiative/Benchmark-Models-PEtab/tree/c44d5ede9bf979db5aa8ae4e94fc31fba9776675"),
        ("P3", "Villaverde and Massonis (2021), Scaling symmetries alone can give misleading identifiability conclusions.", "https://doi.org/10.1371/journal.pcbi.1009032"),
        ("P4", "Massonis et al., AutoRepar, identifiable/observable reparameterization with mechanistic meaning.", "https://doi.org/10.1002/rnc.5887"),
        ("P5", "Data2Dynamics, prediction/profile likelihood experimental design.", "https://pmc.ncbi.nlm.nih.gov/articles/PMC8906444/"),
        ("P6", "Fu et al. (2020), EGS Collab flow and thermal model source.", "https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2020/Fu.pdf"),
        ("P7", "Zhang et al. (2018), Joule-Thomson geothermal modeling source.", "https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2018/Zhang2.pdf"),
        ("P8", "Tian et al. (2022), Assemble Them All, full physics-based rotational assembly methods.", "https://assembly.csail.mit.edu/"),
        ("P9", "Sparse-view Walnut X-ray data record; source/data rights and full-forward-model documentation.", "https://zenodo.org/records/1254206"),
        ("P10", "SoPlex, exact rational linear programming and iterative refinement.", "https://soplex.zib.de/"),
        ("P11", "VSDP, verified numerical bounds for conic optimization.", "https://vsdp.github.io/"),
        ("P12", "VIPR, verification of linear integer-programming proof logs.", "https://github.com/scipopt/vipr"),
    ]
    for entry in external:
        b.append(("ref", entry))

    title = "From Ambiguous Observations to Executable Measurement Constraints"
    subtitle = "AGI ALPHA overnight civilization-scale campaign 008"
    abstract = ("This ongoing research edition documents constructed instruments and executed comparisons in a distinct public invention campaign. "
        "A source-real synthetic-biology model yields three exact scale ambiguities and a conditional calibrated measurement plan, "
        "which ties competent conventional basis methods. A separate verifier checks actual confined plan execution and source-bound acceptance. "
        "The real retention path is exercised on a different model without advantage over ordinary reuse. "
        "A geothermal thermal/pressure instrument evaluates all 64 admitted reduced-model interventions and also ties robust ordinary design. "
        "Native CAD execution is honestly blocked, and a measured-data X-ray feature-bound construction continues. "
        "Physical calibration, positive demand and complete-cost bounds are not manufactured. "
        "Qualified simulated earnings remain zero; the connected commercially successful flywheel is not demonstrated.")
    status_text = ("Exact public source commit " + a.source_ref) if exact_commit else "WORKING-TREE CHECKPOINT: public source identity pending; no old commit is claimed to contain these bytes."
    preamble = r"""\documentclass[11pt,letterpaper]{article}
\usepackage[margin=0.8in]{geometry}
\usepackage[T1]{fontenc}
\usepackage{lmodern,microtype,amsmath,amssymb,booktabs,tabularx,longtable,array,xcolor,listings}
\usepackage{xurl}
\usepackage[breaklinks=true,colorlinks=true,urlcolor=blue!55!black,linkcolor=black]{hyperref}
\usepackage{fancyhdr}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{\small AGI ALPHA / overnight construction checkpoint}\fancyfoot[C]{\thepage}
\setlength{\headheight}{14pt}
\setlength{\parindent}{0pt}\setlength{\parskip}{0.48em}
\setlength{\emergencystretch}{2em}
\renewcommand{\arraystretch}{1.18}
\lstset{basicstyle=\ttfamily\footnotesize,breaklines=true,columns=fullflexible,keepspaces=true,showstringspaces=false}
\hypersetup{pdftitle={AGI ALPHA Overnight Construction Checkpoint 008},pdfauthor={AGI ALPHA Invention Flywheel Lab}}
\begin{document}
"""
    tb = [preamble, r"{\LARGE\bfseries " + tex(title) + r"}\par",
          r"{\large " + tex(subtitle) + r"}\par", r"\vspace{0.3em}",
          tex("30 October 2026 | Ongoing source-bound research edition") + r"\par",
          r"\small " + tex("Evidence cutoff: " + cutoff) + r"\par",
          r"\small " + tex(status_text) + r"\par",
          r"\small Snapshot SHA256: \texttt{" + snapshot + r"}\par",
          r"\normalsize\vspace{0.7em}",
          r"\textbf{Abstract.} " + tex(abstract) + r"\par",
          r"\vspace{0.4em}\textbf{Public campaign:} \url{" + REPO + r"/pull/12}\par",
          r"\textbf{Status: MISSION NOT COMPLETE. Continuing construction; not a completed overnight-window claim.}\par",
          r"\vspace{0.4em}"]
    hb = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>
:root{{color-scheme:light;--ink:#17243a;--muted:#536177;--blue:#234d88;--line:#d5deea}}
body{{margin:0;background:#f3f6fa;color:var(--ink);font:17px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1080px;margin:36px auto;background:white;padding:52px 60px;box-shadow:0 4px 28px #17243a12;border-top:6px solid var(--blue)}}
h1{{font-size:2.5rem;line-height:1.14;max-width:900px;margin:0 0 16px}}h2{{font-size:1.5rem;line-height:1.25;margin-top:2.4em;border-bottom:1px solid var(--line);padding-bottom:.45em}}
p{{max-width:96ch}}.meta{{color:var(--muted);font-size:.9rem}}.status{{background:#fff2e7;border-left:4px solid #b25316;padding:14px 18px;margin:24px 0}}.abstract{{background:#edf3fa;padding:20px 24px}}
a{{color:var(--blue);overflow-wrap:anywhere}}.table-scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:.88rem;margin:24px 0}}th,td{{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:11px 12px}}th{{background:#edf3fa}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#15243a;color:#eef4ff;padding:20px;font-size:.8rem;line-height:1.5}}.equation{{background:#f5f7fa;padding:18px;font-family:ui-monospace,monospace;overflow-x:auto}}.ref{{font-size:.87rem}}nav{{display:flex;gap:16px;flex-wrap:wrap;margin:20px 0}}
@media(max-width:720px){{main{{margin:0;padding:30px 22px}}h1{{font-size:2rem}}}}
</style></head><body><main><p class="meta">AGI ALPHA Invention Flywheel Lab / 30 October 2026</p><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p><p class="meta">Evidence cutoff: {html.escape(cutoff)}<br>{html.escape(status_text)}<br>Snapshot SHA256: {snapshot}</p><nav><a href="AGI_ALPHA_Overnight_008.pdf">PDF edition</a><a href="AGI_ALPHA_Overnight_008.tex">LaTeX source</a><a href="SOURCE_SHA256.json">Source/data hashes</a><a href="{REPO}/pull/12">Public PR #12</a></nav><div class="status"><strong>MISSION NOT COMPLETE.</strong> Continuing construction. This snapshot does not claim the whole overnight window has elapsed.</div><div class="abstract"><strong>Abstract.</strong> {html.escape(abstract)}</div>"""]
    eq_html = {
        r"Cv=0,\qquad \mathcal{A}=\ker C,\qquad \mathcal{A}_{S}=\ker \begin{bmatrix}C\\H_{S}\end{bmatrix}.": "C v = 0; ambiguity A = ker(C); after observations S, A_S = ker([C; H_S]).",
        r"\mathcal{F}_{S}=\{x\geq0: |A_{S}x-y_{S}|\leq\varepsilon_{S}\},\qquad [\ell_S,u_S]=\left[\min_{x\in\mathcal{F}_S}c^\top x,\max_{x\in\mathcal{F}_S}c^\top x\right].": "F_S = {x >= 0: |A_S x - y_S| <= epsilon_S}; feature interval = [min c^T x over F_S, max c^T x over F_S].",
        r"\Pi=Nqap(1-r)-C_{\rm all}-F-K,\qquad q_{\min}=\frac{C_{\rm all}+F+K}{Nap(1-r)}.": "Profit = N q a p (1-r) - C_all - F - K. Minimum participation q_min = (C_all + F + K) / [N a p (1-r)].",
    }
    for heading, blocks in sections:
        tb.append(r"\section{" + tex(heading) + "}")
        hb.append("<h2>" + html.escape(heading) + "</h2>")
        for kind, value in blocks:
            if kind == "p":
                tb.append(tex(value) + r"\par")
                hb.append("<p>" + html.escape(value) + "</p>")
            elif kind == "code":
                tb.append("\\begin{lstlisting}\n" + value + "\n\\end{lstlisting}")
                hb.append("<pre>" + html.escape(value) + "</pre>")
            elif kind == "equation":
                tb.append(r"\[" + value + r"\]")
                hb.append('<div class="equation">' + html.escape(eq_html.get(value, value)) + "</div>")
            elif kind == "ref":
                ident, label, url = value
                tb.append(r"\small\textbf{[" + tex(ident) + "]} " + tex(label) + r" \url{" + url + "}\\par\n\\normalsize")
                hb.append('<p class="ref"><strong>[' + html.escape(ident) + "]</strong> " + html.escape(label) + ' <a href="' + html.escape(url, quote=True) + '">' + html.escape(url) + "</a></p>")
            elif kind == "table":
                heads, rows = value
                widths = [0.25, 0.22, 0.44] if len(heads)==3 else [0.31, 0.63]
                if heads[0] == "Direction":
                    widths = [0.17, 0.48, 0.26]
                elif heads[0] == "Scientific result":
                    widths = [0.28, 0.30, 0.33]
                elif heads[0] == "Reproduced defect":
                    widths = [0.28, 0.35, 0.28]
                elif heads[0] == "Independent numerical check":
                    widths = [0.40, 0.22, 0.29]
                elif heads[0] == "Failure or construction":
                    widths = [0.25, 0.43, 0.23]
                elif heads[0] == "Final bounded producer replay":
                    widths = [0.27, 0.22, 0.42]
                columns = "".join(r">{\raggedright\arraybackslash}p{" + str(w) + r"\linewidth}" for w in widths)
                tb.append(r"\begingroup\small\begin{longtable}{" + columns + r"}\toprule")
                tb.append(" & ".join(r"\textbf{" + tex(x) + "}" for x in heads) + r"\\\midrule\endhead")
                for row in rows:
                    tb.append(" & ".join(tex(x) for x in row) + r"\\")
                tb.append(r"\bottomrule\end{longtable}\endgroup")
                hb.append('<div class="table-scroll"><table><thead><tr>' + "".join("<th>"+html.escape(x)+"</th>" for x in heads) + "</tr></thead><tbody>")
                for row in rows:
                    hb.append("<tr>" + "".join("<td>"+html.escape(str(x))+"</td>" for x in row) + "</tr>")
                hb.append("</tbody></table></div>")
    tb.append(r"\end{document}")
    hb.append("</main></body></html>")
    (OUT / "AGI_ALPHA_Overnight_008.tex").write_text("\n".join(tb) + "\n")
    (OUT / "index.html").write_text("\n".join(hb) + "\n")
    if not a.no_compile:
        command = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(OUT), str(OUT / "AGI_ALPHA_Overnight_008.tex")]
        for _ in range(2):
            result = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
            (OUT / "BUILD.log").write_bytes(result.stdout + b"\n" + result.stderr)
            if result.returncode:
                raise RuntimeError("LATEX_BUILD_FAILED: see docs/overnight008/BUILD.log")
    print(json.dumps({"source_ref": a.source_ref, "source_matched": exact_commit, "snapshot_sha256": snapshot, "consumed_files": len(files), "output": str(OUT), "mission_complete": False}))


if __name__ == "__main__":
    main()
