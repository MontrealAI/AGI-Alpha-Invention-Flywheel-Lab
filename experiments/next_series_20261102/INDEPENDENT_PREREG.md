# NEXT072 independent source and allocation verification

Status: prospective, before workbook retrieval or inspection of its numerical records. The coordinator must publish this protocol, the constructor, the independent verifier and economic screen in one source freeze before confirmation. The original Portfolio071 recovery sources and accounts are outside this verifier's ownership.

Verifier and economic adversary: included agent `/root/recovery_constructor_v2`. Constructor: included agent `/root/next_series_selector`. Coordinator: `/root`. The reviewers share a host and publicly available sources. This is procedurally separate implementation and review; it is not an external laboratory, hostile-code sandbox or independent biological replication.

## Source review before confirmation

The verifier read the pinned author transformation source and condition-mean extraction source, independently of the constructor's account of them. No workbook was downloaded or opened for this review.

- [Author R notebook, pinned commit](https://github.com/const-ae/linear_perturbation_prediction-Paper/blob/bfa6eeea2bd145a1af2ec0127a2e808cc38456a9/notebooks/double_perturbation_analysis.Rmd): lines 102–109 rank genes by control expression; lines 381–406 associate the double and constituent interventions, form `AB-(A+B-ctrl)`, retain seed 1 and control-ranked genes 1–1000; line 545 exports `filter_gt_df` directly to `source_data/suppl-qqplot.xlsx`. Its separate FDR computations are not the NEXT072 acceptance rule and are not imported into this test.
- [Author condition-mean extractor](https://github.com/const-ae/linear_perturbation_prediction-Paper/blob/bfa6eeea2bd145a1af2ec0127a2e808cc38456a9/benchmark/src/run_ground_truth_for_combinatorial_perturbations.py): lines 39–41 take the mean of the expression matrix within each recorded condition. The helper for cell-standard error is not used or validated by NEXT072. No cell-level sampling-error or independent-trial claim is permitted.
- [MIT license](https://github.com/const-ae/linear_perturbation_prediction-Paper/blob/bfa6eeea2bd145a1af2ec0127a2e808cc38456a9/LICENSE.md): copyright Constantin Ahlmann-Eltze, 2024. Attribution to the original Norman experimental authors and the Ahlmann-Eltze, Huber and Anders benchmark authors remains required. Repository licensing does not independently establish every term necessary for a later commercial or physical service.

The Git blob and expected byte length of the workbook are fixed in `PREREG_K1.md`: blob `f35c9efe3bf0f917068b2aaf2c2236b593c06e2c`, 10,905,627 bytes, author repository commit `bfa6eeea2bd145a1af2ec0127a2e808cc38456a9`. These identify the input, not its unobserved results. The manuscript's expected pair count is a contextual expectation, not permission to omit or replace a pair if the complete exported denominator differs.

Two raw-URL opens through the web lookup service returned a transport `DisabledError`. The verifier subsequently retrieved the two code files through the authorized public GitHub connector. A request for `LICENSE` returned 404; the actual license path is `LICENSE.md`. No transport outcome is treated as biological evidence.

## Independent implementation boundary

`next072/independent_verify.py` imports no NEXT072 constructor, loader, metric, policy or freeze helper. It parses the XLSX directly with Python's standard ZIP and XML libraries. The constructor uses read-only openpyxl. The verifier never changes or exports the source workbook.

Before reading any numerical input, the verifier requires a full public freeze commit and independently checks `FREEZE.json`, every mapped file's SHA256, required constructor/verifier/economic/protocol files and the preregistration hash. It then checks both the workbook byte count and its Git blob identity, recording SHA256. It binds the producer's results, compact evidence and resource receipt to the same public commit, raw freeze-document hash and exact source map. It rechecks all these identities at the end.

The workbook reader requires exactly one worksheet and resolves its relationship explicitly. It handles literal numeric cells, shared strings and inline strings. Duplicate members, headers, cell addresses or source rows, unexpected formula/error cells and unlabeled columns cause failure. Cached formula output cannot substitute for source measurements. The entire record set is streamed. Scientific record validation inspects all rows before issuing a rejection receipt, retaining the count and reasons for invalid records rather than dropping them from the denominator. A structural parse failure records the point of failure and does not imply complete source coverage.

## Independent measurement reconstruction

The verifier separately reconstructs canonical unordered pairs, readout genes, source orientation of A and B, all four mean-expression fields, the published residual column, single-intervention profiles, control profile and control ranks. It requires:

1. Seed 1 only, exactly 1,000 readout genes and the complete rank interval 1–1000.
2. Unique pair/readout records and complete pair-by-readout coverage.
3. Consistent repeated means for each single intervention and control within absolute tolerance `1e-10`.
4. Control rank order consistent with descending control expression. It does not independently reconstruct omitted genome-wide expression ranks from unavailable cell counts; the author transformation supplies that provenance.
5. Published error consistent with independently calculated `AB-A-B+ctrl` within absolute tolerance `1e-10`.

Residual sums and feature inner products use scalar `math.fsum`; pair D is the square root of the mean squared residual. The verifier recomputes all six symmetric, single-derived features. All identities and counts must match exactly. Floating values in the compact evidence and acquisition receipts must match within absolute `1e-8` and relative `1e-8`. These numerical comparison tolerances accommodate distinct correct arithmetic implementations; they are not biological error bars or tolerance to wrong observations. Source-consistency rules remain at `1e-10` absolute.

Pair selection order must agree exactly with independently recomputed acquisition order. The tolerance is not used to silently reorder a disputed selection. A numerical ranking disagreement is a failed independent check requiring disclosed exploratory adjudication; it cannot be repaired after confirmation and presented as untouched confirmation.

## Split, reference and target denominator

For N complete source pairs, the verifier independently hashes the literal prefix `NEXT072-K1-v1|` followed by the canonical pair string. The first `ceil(N/4)` pairs are references. Every other pair belongs to the confirmation pool of size M. Every policy receives budget `floor(M/4)`; the target set is the top `ceil(M/4)` candidate D values, ties resolved by canonical pair string.

The verifier checks exact reference and candidate membership, disjoint pair lineages, the complete source denominator, target membership and every full-profile count. Shared genes across reference and candidate pairs are enumerated in the verdict. Their reuse is allowed by this purpose: new combinations of measured single interventions. The result does not test unseen-gene transfer. Shared single/control means and the same enriched pair population prevent interpreting the 32 hash controls as independent biological trials.

The 25% reveal limit applies to the held-out pool. Total measured profiles include all unique constituent single profiles, one control, every initial reference pair and every revealed pair. The reference set is not free or outside the cost denominator. The output also records the number of adaptive batches; reduced profile count alone does not establish reduced laboratory cost or elapsed turnaround.

## Independent allocation reconstruction

The verifier checks all 42 registered policies. It does not merely check final precision and recall. For each policy and every batch it reconstructs the model using exactly the references and previously revealed outcomes available before that batch, computes all candidate acquisition values, applies the registered tie rule and checks the ordered commitments.

Before any public science freeze or numerical workbook access, current primary literature changed the prospective choice of primary method. The earlier UCB-first document was an unpublished draft. The registered primary is now `probability_of_hit`, credited to [Rubbi et al., ICML 2026](https://proceedings.mlr.press/v306/rubbi26a.html), specifically [Section 4.1, equation 2 and Algorithm 1](https://arxiv.org/html/2605.10196v1#S4.SS1). UCB remains `sequential_kernel`; no method will be selected as primary by its observed outcome. The final list has ten named methods and 32 fixed hash controls. `ordinary_equal_content` uses the same primary method; `constant_features` removes the primary's single-derived features; `static_probability_of_hit` removes its outcome updates. Static UCB is separately retained.

The source method ranks Gaussian posterior threshold-exceedance probabilities. This test declares its own fixed threshold as the nearest-rank 75th percentile of the initial reference D values: sorted initial references at position `ceil(3R/4)-1`, with no interpolation. The verifier obtains that rank using independent integer arithmetic. The threshold is never recomputed from queries or hidden confirmation outcomes. Each candidate's index is `z=(mean-threshold)/max(deviation,1e-12)`; its receipt also reports `erfc(-z/sqrt(2))/2`. Ranking z avoids numerical ties when extreme normal CDF values saturate. The absolute deviation floor is a numerical convention in source-expression units, not measured biological noise. The fixed initial-reference quantile, deterministic pair-string ties and held-out top-quartile evaluation are declared adaptations of the source method. Its calibration assumptions, guarantees and biological probabilities are not established by this replay.

For kernel policies, it independently derives standardization and median positive-distance bandwidth. It uses a Cholesky formulation rather than the constructor's direct solve. Identical feature vectors are evaluated with identical scalar operations, preventing a BLAS vector-tail rounding difference from becoming an arbitrary tie break. This arithmetic detail was discovered and corrected on authored synthetic fixtures before any workbook access.

For the linear control, leave-one-out losses are recomputed by explicitly refitting each omitted reference pair for each of the four registered ridge values. This is separate from the constructor's leverage/hat-diagonal shortcut. Both static methods, UCB, exploitation, additive-magnitude, diversity, constant-feature and all 32 fixed hash-order controls retain their registered permissions. Diversity may update distances within a batch using selected features; it cannot update on unrevealed outcomes.

Each receipt must have the exact pair, query number, batch, reference count, pre-reveal prediction/acquisition values, revealed D and remaining budget before and after the query. Initial and final budgets are reported explicitly. Duplicate queries, omitted controls, unexpected fields, extra queries or hidden reassignment of reference pairs fail. The verifier recomputes the sealed-selection hash from the producer's unlabelled receipt bytes, then independently checks post-seal target labels, cumulative discoveries and every final metric. Re-signing or rehashing a false acquisition receipt does not make its choice pass the independent calculation.

All probability-of-hit receipts additionally require the fixed initial-reference threshold and the normal-model exceedance score. Authored challenges distinguish PoH from UCB ordering, test the zero-deviation floor and saturated CDF ordering, and preserve the initial threshold while all non-reference outcomes change. The full traces of all 42 methods must remain unchanged when only never-revealed outcomes change. First-batch decisions and their model scores must remain unchanged when every confirmation outcome changes.

The primary and ordinary equal-content receipts must be exactly equal. This is a technical equality provided by equal permitted means. It is not a measured trial of specialist attention or autonomous-agent productivity.

## Hidden-outcome access and limits

The verifier inspects the frozen policy source and its declared five-field context: names, single-derived features, reference names, reference D values and query budget. The source review rejects undeclared imports, file/dynamic-code access and explicit introspection of the oracle. It is a bounded review of the registered code, not a proof against arbitrary hostile Python or a compromised host.

Independent deterministic reconstruction establishes that the recorded choices follow from permitted information. Synthetic counterexamples change all still-unrevealed values while holding references and actual previous reveals fixed; complete traces must remain unchanged. First-batch commitments also remain unchanged when every non-reference D value changes. Independent source/trace checks complement the constructor's oracle guards. They do not establish a secret external measurement team.

## Acceptance and public outputs

The independent verdict accepts the research replay only if source identity, measurement reconstruction, full denominators, all 42 traces, all metrics, equal-content tie and scope limits pass. It separately reports whether the PoH primary boundary of at least 50% target recall was met. It also reports exact primary-minus-control discovery counts for no-feature, static-PoH, UCB, regression, additive-magnitude, diversity and mean-hash controls. These are descriptive differences in this fixed replay, not estimates of physical causal effects or independent biological trials. A correctly executed negative result can pass the software/evidence audit while failing the proposed discovery boundary.

The verdict must leave physical/biological delivery and commercial/native financial admission `NOT_ESTABLISHED`. No missing observation, parsing error, budget failure or failed control may be turned into an accepted zero. The first registered confirmation and any failed attempt remain distinct. A later CI reproduction must be labelled as engineering reproduction from its own exact source; it does not replace the first confirmation.

Commands after the coordinator's published freeze:

```bash
python -m unittest next072.test_experiment next072.test_independent_verify -v
python -m next072.independent_verify --workbook /absolute/pinned/suppl-qqplot.xlsx --attempt /absolute/constructor-attempt --freeze experiments/next_series_20261102/FREEZE.json --public-commit PUBLIC_COMMIT_SHA --output /absolute/new-independent-verdict.json
python -m next072.economic_check --verification /absolute/new-independent-verdict.json --output /absolute/new-economic-verdict.json
```

The verifier records actual command CPU/wall time and peak memory, immutable source/artifact hashes and explicit failure detail. Included inference/host money cost remains UNKNOWN. No external specialist, laboratory operation, new paid resource or native financial account is invoked by these commands.

## Economic adversary and next decision

`ECONOMIC_ADVERSARY.md` and `next072/economic_check.py` define the finite participant, outside-option, timing and cash model. Unknown monetary and acceptance inputs remain unknown, producing HOLD unless a known violated condition establishes REFUSE. Hypothetical $100,000 and $1 billion funding cases do not become received funds. Even a fully specified authored feasible scenario remains a conditional scenario, without sale or native collection.

The complete workbook outcomes are already public. Public self-service with unknown retrieval, interpretation and verification effort is therefore an explicit sixth current outside option; retrospective oracle masking is not a customer-access obstacle. No actual new assay is avoided by this replay. A technically correct negative report and a successful budget-crossing allocation service have separate prospective acceptance gates; the former cannot substitute for a failed latter claim. All committed refund, collateral and warranty protection is retained from setup through the final modeled cash event unless a separately accepted release milestone is evidenced.

Current primary evidence rejects a generic newly missing adaptive-experiment platform claim before this test: [NAIAD](https://proceedings.mlr.press/v267/qin25g.html) already combines single-gene effects with adaptive recommendation, and [BATCHIE](https://www.nature.com/articles/s41467-024-55287-7) reports a complete prospective drug-combination workflow. Their endpoints, representations and experimental resources differ; neither framework's full performance is compared here. This rejection does not depend on any NEXT072 result.

The finite remaining question is whether this fixed six-feature representation of already measured single profiles is useful under the credited current acquisition method after charging all initial references. A failed boundary rejects this allocation contract. A passed boundary without an advantage over the fixed no-feature or simpler controls supplies no evidence for a special value of those proposed means. A useful descriptive advantage can motivate a separately designed fresh study with appropriate independent truth; it cannot by itself establish a newly feasible industry, a complete-cost specialist advantage, physical assay delivery, voluntary demand, K2 fitness rescue or the $3 billion profit milestone. No failed result triggers tuning on the exposed confirmation set.
