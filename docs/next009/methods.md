# From an information obstruction to an executable measurement instrument

## Objective and evidence standard

The civilization-scale objective is to make difficult discovery work executable by a machine that can recognize missing information, construct an instrument that supplies it, verify a useful delivery, and use earned surplus to finance the next instrument. This campaign implements a small, inspectable instance of the first part: **a compiler for calibrated, failure-tolerant source-identification measurement plans**. It also executes an artifact-bound commercial simulation. It does not infer the larger mission from a working compiler, a positive authored cashflow, or publication.

The beneficiary is a utility modeling team or consultancy preparing an auditable observation plan. The complete executed delivery is a numerical model, an executable plan, explicit ambiguity witnesses, an outage certificate, source identities and a verifier receipt. A future physical service would additionally require calibrated instruments, suitable reference samples, measured drift, registration, maintenance, engineering review and an operational service obligation. Those tasks have not been performed or priced as if they were eliminated. No emergency water-safety decision is authorized by these simulated examples.

The important constraint is informational. If two source hypotheses can produce exactly the same readings under the allowed nuisance parameters, selecting a subset of those readings cannot identify the source. This is the same logical obstruction that defeated the earlier all-view XCT formulation: further search inside an information-insufficient family does not create information. Here the construction changes the available measurement by adding a same-sensor reference with a known signal, then tests whether that change removes the obstruction while preserving noise, cohort and outage requirements.

The resulting formal capability is reusable across model-based observation-design tasks. Its practical range remains conditional on the signal model and justified reference assumptions. No market-size narrative, field impact, scientific novelty or beyond-human foresight is inferred from this transfer path.

## Opportunity selection and existing alternatives

Three materially different possibilities were investigated before selection. Their detailed source docket and falsifiers are preserved in [OPPORTUNITIES.md](../../campaign/next-009/OPPORTUNITIES.md).

| Possibility | Important unavailable outcome | Missing means and decisive constraint | Selection |
|---|---|---|---|
| Water-network observation planning | Identify modeled source hypotheses despite offsets and failed sensors | Additional valid information is needed when all existing channels admit the same two truths; executable public models and exact controls are available | Construct a bounded instrument |
| Metabolic flux measurement | Identify internal fluxes well enough to change production pathways | External fluxes underdetermine internal behavior; isotope measurements and established optimal-design methods must be included | Do not repeat an existing SBML lane; physical new measurements unavailable |
| Active spectral mixture identification | Identify constituents from scarce measurements | Library gaps, instrument mismatch and confounded spectra require calibrated discriminatory measurements; active wavelength methods already exist | No qualified calibrated data and complete baseline within this allocation |

The search is bounded. It includes government and laboratory software, executable examples and relevant primary methods; it is not proof that every imaginable alternative fails. Relevant water alternatives include EPA EPANET/WNTR, Sandia Chama, source inversion, minimum test cover, robust sensor placement and ordinary calibration. The initial executable probe reproduced the Sandia example's three-sensor mean-detection objective: sensors 12, 23 and 32, mean 7,600 seconds across the relevant source cases. An idealized two-sensor identification problem was already solvable by ordinary exhaustive selection. These results reject an unearned algorithmic novelty claim and make calibrated conventional optimization a required control.

The first construction therefore asks a functional question: can an auditable system turn a reproduced ambiguity into a new valid observation program? It does not ask whether it can rename familiar calibration or multicover mathematics. The model is source-pinned to [USEPA/WNTR commit 11eec7d5](https://github.com/USEPA/WNTR/tree/11eec7d5bf0a9367ffe04d75707918f0c0a890a1). Prior art includes [Sandia's executable example](https://github.com/sandialabs/chama/blob/main/examples/water_network_example.py) and [minimum-test-cover sensor placement](https://arxiv.org/abs/1507.07134). Matched service times, an independently constructed frontier-AI competitor and calibrated physical outcomes remain residual comparisons, not assumed failures.

## Signal model, complete cohort and acceptance rule

Let $s^a_{kt}$ be the source-contribution percentage predicted for source hypothesis $a$, sensor $k$ and time $t$. Each corpus includes every junction as a source and candidate sensor and every hourly timestamp in the declared first 24 hours. The simulator uses EPANET TRACE through the pinned official Linux library. The authored 24-hour horizon is recorded alongside the upstream model's native duration; it is not represented as a field contamination event.

For the primary model, an uncalibrated observation is

$$y_{kt}=s^a_{kt}+b_k+u_{kt},\qquad |u_{kt}|\leq\epsilon,$$

where $b_k$ is an arbitrary offset constant across the reference and trace. A known-zero reference is

$$r_k=b_k+w_k,\qquad |w_k|\leq\epsilon.$$

The generated readout is $z_{kt}=y_{kt}-r_k$. Its reference error $w_k$ is shared over time. Treating that error as independently resampled at every timestamp would change the feasible observation set; both compiler and separate checker instead preserve the common variable.

For two hypotheses, define $d_t=s^a_{kt}-s^b_{kt}$. Without the reference, their readings at one sensor can coincide if and only if

$$\max_t d_t-\min_t d_t\leq4\epsilon.$$

With a reference and bounded arbitrary reference-to-sample drift $D$, the two corrected traces are compatible if and only if

$$[-2\epsilon,2\epsilon]\ \cap\ \bigcap_t[d_t-2(\epsilon+D),\ d_t+2(\epsilon+D)]\neq\varnothing.$$

This follows by taking the difference of the two latent reference errors as one shared variable, while differences of sample errors and drift lie in the stated intervals. The primary construction fixes $D=0$ and $\epsilon=1$ percentage point. The successor reports the entire prospective grid $D\in\{0,1,5,10,25\}$.

An empty intersection means that sensor separates the two hypotheses. To tolerate one **known erasure**, every pair must be separated by at least two selected sensors. This is a conventional set-multicover problem. An unflagged adversarial sensor error is a different obligation and is not covered. All selected-sensor outage states are separately checked, even though the multiplicity condition implies their feasibility in this model.

An exact two-truth witness consists of both source identities and admissible offsets, reference errors, sample errors and, where relevant, drift components yielding identical observations. It is a constructive impossibility certificate for the unchanged information family. No timeout is interpreted as an impossibility proof.

## What the four mechanisms actually did

**Structural mapping.** The implementation maps signal-plus-nuisance relations to invariant contrasts, then maps pairwise distinguishability to robust multicover. Units remain source-contribution percentage points throughout. The nuisance and reference structures are manually proposed, source-grounded model assumptions. Runtime code derives relations from the actual simulator arrays and checks applicability. This is an executable cross-domain mapping between measurement theory and combinatorial design; it is not autonomous discovery of the original structural analogy.

**Executable strategy generation.** A bounded typed coefficient enumerator checks candidate expressions and constructs the arithmetic program `subtract(read(sensor,time), zero_reference(sensor))`. The chosen program is interpreted during actual diagnosis, so it changes acceptance rather than appearing only in a report. The zero-reference primitive is developer-proposed; signed coefficient enumeration and multicover are known methods. The drift extension is a developer-authored rule generator that composes interval constraints and emits new plans, with ancestry and source hashes retained. These facts limit any meta-invention claim.

**Adversarial verification.** A separate worker received sources and artifacts, implemented exact interval arithmetic without importing candidate decision arithmetic, generated observations after the public freeze, and executed the actual candidate in a separate process without truth labels. It found a consequential parent-authority defect in the early successor: replacement compiler bytes could inherit an old acceptance receipt. The repaired candidate binds the live parent source, external frozen hash and acceptance receipt, and checks receipt scope. The original witness is refused after repair and three fresh regressions pass. Shared host, model family and orchestration mean procedural independence, not outside certification.

**Retention.** The successor invokes the repository's real `flywheel.retention.store` and `retrieve` paths. Its instrument record includes verified parent identities, scope, generative rule and negative applicability constraints. Retrieval refuses to transfer approval to drift or invalid-reference obligations. The accepted parent content becomes input to a newly verified construction; approval is not inherited. Equal-content ordinary reuse receives the same record and solver. Reset reconstructs the expression algorithmically with the full toolbox; it is not an independent generalist model rediscovering the method. These controls distinguish possession of useful content from a claim that a particular memory system improves discovery.

The parent-authority failure and repaired witness are preserved separately. The original defective successor was recovered by reversing two later text patches; its SHA-256 matches the one recorded by the original probe. This recovery is explicitly labeled and does not pretend an untouched snapshot survived.

## Primary frozen experiment: Net1

The candidate, target corpus, protocol, verifier and thresholds were publicly frozen at commit [5e486d711](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/5e486d711acdd07aba3db13df38e5f57744851d0) before protected perturbations. The primary denominator is nine sources, nine candidate sensors, 24 timestamps and 36 unordered source pairs. The final four-sensor plan uses **13, 23, 31 and 32**.

| Test | Executed result | Interpretation |
|---|---|---|
| Every uncalibrated sensor available | Sources 23 and 32 admit identical observations | Subset selection cannot remove this modeled ambiguity |
| Generated reference plan | All 36 pairs survive each of five outage states | Causal measurement benefit within the frozen assumptions |
| Independent exhaustive subset control | Minimum cardinality four | Candidate ties strong ordinary calibration and selection |
| Greedy control | Four sensors | No optimization advantage on this cohort |
| Fresh independent decoder cases | 72 of 72 pass | Finite protected perturbation validation |
| Actual candidate subprocess | 72 of 72 pass | Executable program agrees with independent acceptance |

The final receipt is [ACCEPTANCE.json](../../evidence/next009/verification/primary-confirmation/artifacts/ACCEPTANCE.json), SHA-256 `58da3c195b1d7b22e91601d33f1434a16cfc92339db7ac6074314e6c15e60824`. There was one final protected primary execution. The 72 cases are now exposed and any reproduction reuses an exposed seed or explicitly labeled development cases. No new confidence, population success rate or statistical novelty claim is created by replay. The campaign records zero additional statistical alpha spent for these finite engineering checks; older evidence and decisions remain intact.

The advantage is the additional valid reference information relative to the uncalibrated information family. Giving a conventional solver the same information yields the same result. This tie does not invalidate the technical information change or, by itself, any possible commercial advantage over human service. It does preclude claiming a superior discovery algorithm from these results.

## Numerical semantics, disagreement and the separate Net3 edition

The primary numerical contract interprets canonical JSON decimal renderings of finite simulator binary64 values as exact rational decimals. It does not equate arbitrary JSON lexemes with exact binary fractions or certify physical simulator accuracy. An early checker used exact binary fractions and disagreed with the candidate on 19 of 72 exposed development cases. Before confirmation, that specification disagreement was resolved prospectively. All 19 original latent observations lie outside the resolved decimal error envelope; all 19 canonical counterparts under that envelope pass. Original code, cases and disagreements remain available.

The original Net3 corpus has 92 sources, 92 sensors and 24 timestamps, giving 203,136 signal coordinates and 4,186 source pairs. Its unchanged strict $[0,100]$ gate **failed**: 1,211 values exceed 100, with maximum 100.00000000000006. Builder runtime checks before independent admission do not reverse that failure.

A separately identified edition applies ties-to-even rounding at 12 decimal places to **every coordinate**, retaining the original raw corpus. Each change must be at most $5\times10^{-13}$ percentage points and the transformed value must satisfy the original range gate. A separate exact-integer implementation recomputes every transform; it imports neither the adapter's Decimal operation nor its claimed result. All 203,136 transformations passed, 50,324 coordinates changed, and the maximum exact representation change is $5\times10^{-13}$. No source, sensor or timestamp was removed. This is a representation-change bound, not a simulator-error or physical accuracy guarantee.

The unchanged compiler produced a 25-sensor plan; ordinary MILP also produced 25 and greedy produced 26. A builder-authored composition driver uses frozen independent arithmetic across disjoint 46-sensor slices for each source pair. Composition is valid because the permitted nuisance/reference constraints factor by sensor, without asserting probabilistic independence. All 4,186 pairs, 92 channels, 24 times and 26 outage states were retained: **108,836 pair/outage obligations passed**. Sixty-six source pairs remain ambiguous in the full uncalibrated information family; a complete 92-sensor witness is preserved for sources 15 and 35.

The derivative receipt is [NET3_NUMERIC_FEASIBILITY.json](../../evidence/next009/numeric-edition/verification-v1/artifacts/NET3_NUMERIC_FEASIBILITY.json). It establishes exposed development feasibility, not a second protected runtime confirmation, independently proved global optimum, physical validation or a repaired original admission result. The 25-sensor optimum is solver-reported. These obligations are never pooled with the 72 primary protected cases as a larger confirmation cohort.
