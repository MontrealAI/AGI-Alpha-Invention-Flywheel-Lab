# Which inference configuration earns a field test?

**FRONTIER Ω IGNITION · MONTREAL.AI × QUEBEC.AI · November 17, 2026**

MONTREAL.AI faces a practical choice before it commits infrastructure or engineering time. At what measured load has an inference system kept an interactive user waiting less than the lab’s specified limit while delivering enough tokens per second? An impressive system-wide throughput number cannot answer that question on its own. The answer depends on which measurements occurred together, which workload produced them, and exactly what “tokens per second per user” means.

[Open the bilingual exhibition](../FRONTIER_LAB.html) · [Five-minute presenter script in English and French](../../../../products/frontier-omega-ignition/showcase/decision/PRESENT.md) · [Reproduce the endpoint study](../../../../products/frontier-omega-ignition/endpoint_study/README.md) · [Inspect five opportunities and the overlooked alternative](../../../../products/frontier-omega-ignition/opportunity_field/RESEARCH.md)

## The decision

We used a proposed operating requirement of at most **500 ms P90 time to first token** and at least **100 reported output tokens per second per user**. Those thresholds are design choices for the experiment. The unit of evaluation is a complete observed run. Every measurement used to select an operating point has to belong to that same run. No interpolation is allowed.

| Public report and workload | Highest observed concurrency meeting both requirements | P90 first token | Reported tokens/s/user | What happens at the peak system-throughput point |
| --- | ---: | ---: | ---: | --- |
| Google GPT-OSS 120B, perf | 140 | 147.6 ms | 294.4 | At 22,528 concurrent queries, 509.0 ms and 42.1 tokens/s/user miss both requirements. |
| Google DeepSeek, MLPerf agentic dataset | 128 | 165.1 ms | 106.9 | At 2,048 concurrent queries, 20,722.4 ms and 26.5 tokens/s/user miss both requirements. |

These two reports cover different systems and workloads. The GPT report describes its configuration as “submission.” Requiring an explicitly online GPT result yields an abstention. The Google DeepSeek report identifies an online configuration. A third, provisional NVIDIA report contributes eleven observed load points to the review-status control and zero admissible points. Source status was inspected November 17.

The most consequential discovery was a difference between the displayed per-user rate and the reciprocal of P90 time per output token. A requirements author might reasonably specify either quantity. At 110 tokens/s, the verified DeepSeek measurements support 64 concurrent queries using the displayed field and 128 using the reciprocal. At 200 tokens/s, the displayed field supports no point and the reciprocal supports 24. Across the 400 prespecified integer thresholds the selected point changed **109 times**. The instrument exposes the choice explicitly and retains the original run and both fields. The percentage of thresholds affected is specific to this grid. It gives no deployment error probability.

The measured action is a change in which pilot load qualifies for investigation. The physical systems, customer traffic and service prices have not been tested by MONTREAL.AI. For a deployment decision, record a representative prompt and output distribution, establish the required accuracy and service access, then measure the incumbent and proposed system under the same traffic. For GPT-OSS, the next published load above 140 is 272, where the report records 610.9 ms P90. Testing that boundary is a concrete experiment an operator with suitable infrastructure could perform.

## Evidence, alternatives and economics

Two independently implemented routes used separate projections of the three reports. The first applied explicit eligibility rules to 28 operating points. The second read all displayed run tables into SQLite and used exact arithmetic for threshold comparisons. The programs agreed on all nine registered contracts and 800 additional comparisons. Seven altered receipts were rejected. Six primary contracts withheld recommendations when the requested status, mode, workload, price, quality or access evidence was absent. A complete official table or short SQL query remains a sufficient alternative for a one-off decision. The instrument adds a repeatable way to change a requirement, inspect exclusions, deliver the witness and reproduce the answer offline.

The two routes are independently authored within this engineering effort and rely on the same public submissions. They do not independently reproduce the submitters’ hardware results. The first scoring run took 0.469 seconds including nine separate candidate processes. Independent SQL query times excluded source loading. These measurements do not support an end-to-end speedup claim. Engineering, negative experiments, independent review, source upkeep, field infrastructure, support and labor have incomplete monetary accounting. Incremental paid inference for this endpoint decision was zero. No pricing, revenue, willingness to pay, profitable operation or external customer commitment was observed.

The field investigation considered endpoint measurement, scientific table verification, scheduling, provable inference and cross-laboratory experiment transfer. The strongest overlooked alternative is to measure the existing system on the lab’s actual traffic. We chose a question that can be decided with accessible evidence now, with an explicit handoff to that stronger field test. The external IGNITION campaign is selective. This result primarily serves the lab’s internal allocation of research time.

[Published measurements and methodology](../../../../products/frontier-omega-ignition/endpoint_lab/README.md) · [Frozen registration and actual scorer receipt](../../../../products/frontier-omega-ignition/endpoint_study/OBSERVATION.json) · [Opportunity evidence and alternatives](../../../../products/frontier-omega-ignition/opportunity_field/RESEARCH.md)

## Two controlled studies behind the exhibition

**Reader performance.** The new English and French study compares original HTML/PDF, a conventional searchable page index, the existing Reading Room, and a new contextual concordance. Eight executable language/workflow packets cover 21 English and 29 French physical pages. Independent PDF text extraction located all eight task references. The publisher HTML guides map uniquely for only 1/30 English blocks and 9/72 French blocks. This identifies a real limit to passage linking on publications whose full text lives in the PDF. The new concordance searches those physical pages directly. Its first implementation passed just 2/15 scientific navigation cases. A repair preserved signs, decimal precision, percent units, scientific notation and directional relations, and passed 15/15. All four one-byte source changes were rejected.

The registered target is 64 participants, with counterbalanced task order and allocation across language, reading workflow and assistive-technology strata. The coordinator must obtain participation authority and individual consent before enrollment. Responses support abandonment and withdrawal, blinded independent adjudication and cost accounting. **Zero participants have been enrolled.** Reader time, consequential human error, assistive-technology benefit, and cost per accepted reader outcome remain open. Technical packet generation and browser timing cannot answer them.

[Study operator guide](../../../../products/frontier-omega-ignition/reader_trial/README.md) · [Pre-enrollment qualification](../../../../products/frontier-omega-ignition/reader_trial/QUALIFICATION.json) · [Original and repaired search results](../../../../products/frontier-omega-ignition/reader_trial/NAVIGATION_RESULT.json)

**Numerical Table Desk.** A fresh printed table of simulated research outcomes has 20 cells, including 12 numerical entries. Direct author export, native PDF extraction, segmented Tesseract with supplied geometry, and an actual local NVIDIA Nemotron-3.5-Parse run all recovered the 20 cells in their declared projection. An independently authored checker read the printing TeX. The physical table omits a column present in the author HTML, so a literal export of every HTML column would answer a different question.

A second, deliberately controlled two-page calibration table contains 25 cells and two scoped footnotes. Direct and native extraction recovered both pages. OCR withheld on a conflicting row-span anchor. The initial model receiver withheld on an inert empty LaTeX box. Under a separately frozen repair protocol, the original model generations recovered all 25 cells and both footnotes with zero additional inference. The original outcomes remain visible. Three original CPU model calls took 68.2773 seconds in total. The complete cost also includes source preparation, checking, failed routes and maintenance. The simpler direct route ties the accepted output. This work does not establish a population-level numerical accuracy rate.

A second registered comparison executed both delivery routes on the identical calibration images. Rechecking the archived generations took 0.354 seconds and zero new model calls. Regenerating them on CPU took 58.570 seconds and two new calls. Both yielded the identical CSV and scoped footnotes. Both also incurred 0.277 seconds of shared preparation. The prior calibration inference alone had already cost 51.882 seconds. This measures the marginal value of retaining those exact observations for a new check on the same table. Transfer to an unseen publication remains open. [Matched successor experiment](../../../../products/frontier-omega-ignition/numeric_study/successor/README.md)

[Methods, specimen CSV and receipts](../../../../products/frontier-omega-ignition/numeric_study/README.md) · [Separate recovery observation](../../../../products/frontier-omega-ignition/numeric_study/RECOVERY.json)

## The construction and its authority

The private operator specifies the workload and evidence requirements, then creates or amends a durable mission. Direct and adaptive strategies both choose the installed evaluator when the stated purpose matches. Additional unsupported purposes or unrepresented requirements block that route. A source or contract change invalidates prior delivery. A scientifically withheld decision can still be a successfully verified artifact. The downloadable private receipt includes the eligible and excluded evidence, an independent SQL result, and a local replay. The endpoint study uses the three fixed public source reports. No endpoint credentials or private traffic are needed.

The public exhibition shows the evidence in English and French, provides bounded offline calculations, and includes an independently executable recipient. Private missions run through the separate loopback workbench. A recorded model call, a fresh local calculation and an unavailable field observation have different statuses in the exhibition.

The previous integrated exhibition remains at [PR #446](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/446), head `a0fc6e1fc617c965f004d6977c051b2f226fa96a`. Its predecessor included #436, #439, #440 and #441, the #443 and #444 construction/presentation branches, and independent review #445. Main was `172ea7a9b96ad123a879dde76101b944aa9cf131` when reconciled. This successor branches from the reviewed integration head.

The [earlier red workflow](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44198902856) measured **three routes on one synthetic migration mission**. The Qwen research route deferred after two calls and five candidates. The direct route failed the nine-case contract. Live discovery reported a provider connection failure after approximately 600 seconds. A separate source feed also failed. The connection failure did not establish its own cause. The six-cell adaptive experiment was a different study, with four passing primary cells and seven successes across eleven total cells. Prior passes, failures and original records are preserved.

A prospective llama.cpp streaming route uses the existing HARNESS transport, checks the model identifier in each streamed frame against the requested name, requires a complete terminal text response and records incomplete attempts. An actual small-model CPU probe stopped at its 96-token allowance on discovery and later completed an admissible abstention on a different bounded choice. The two observations do not qualify the historical Qwen mission. A current exact-commit model experiment reports its own outcome in Actions.

[Source-bound transport observation](../../../../products/frontier-omega-ignition/evidence/local-stream-transport.json) · [Private model routes](../../../../products/frontier-omega-ignition/docs/MODEL-ROUTES.md)

## Reproduction

From the repository root, use a fresh directory for each output. Endpoint decision and ZIP replay require Python 3.11+ with its standard library. The document studies also use the pinned dependencies in the [qualification workflow](../../../../.github/workflows/frontier-ignition-evidence-decision.yml).

```sh
cd products/frontier-omega-ignition
work=$(mktemp -d)
python3 -B endpoint_study/score.py --output "$work/endpoint-study.json"
python3 -B -m ignition --state "$work/private" start examples/endpoint.json > "$work/mission.json"
rid=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$work/mission.json")
python3 -B -m ignition --state "$work/private" export "$rid" "$work/endpoint.zip" --version 1
python3 -m zipfile -e "$work/endpoint.zip" "$work/instrument"
python3 -IB "$work/instrument/endpoint_lab/replay_delivery.py"
python3 -B reader_trial/qualify.py --output "$work/reader-packets"
python3 -B numeric_study/receive.py --output "$work/numeric"
python3 -B numeric_study/audit.py "$work/numeric"
python3 -B numeric_study/recover.py --output "$work/repaired"
python3 -B -m ignition --state "$work/private" serve --port 8784
```

Open `http://127.0.0.1:8784/frontier` for the exhibition and `http://127.0.0.1:8784/` for the private workspace. The local HTTP server is optional for the downloaded exhibition and recipients. New experiments involving people, customer data or running client infrastructure each require their own authority.
