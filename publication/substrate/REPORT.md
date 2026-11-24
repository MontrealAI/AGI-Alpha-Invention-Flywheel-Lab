# FRONTIER Ω · Intelligence Substrate study

## The decision now supported

The workbench audits whether a published linear transit ephemeris satisfies the source's one-twelfth-of-duration timing target across all correlations compatible with its reported marginal standard deviations. Its intended use at MONTREAL.AI is to prioritize requests for covariance and timing records before committing measurement effort. No observing time, membership data, payments or workflow authority were used.

The publication is Kokori et al. (2026), *The ExoClock Project. IV.*, ApJS 283, 5, [DOI 10.3847/1538-4365/ae3238](https://doi.org/10.3847/1538-4365/ae3238). The workbench uses the signed fitted epoch offset, a common BJD TDB basis, source-day timing errors, source-hour duration and one cited record per decision. A favorable result refers to a modeled standard deviation under a linear ephemeris. It cannot provide a calibrated observing interval or establish that a planet follows a linear timing model. [Registered sources and scope](REGISTRATION.json)

If the first transit model center at or after the anchor has epoch `n`, its timing variance is `s0² + n²sP² + 2nρs0sP`. The uncertainty range spans the extrema at `ρ = −1` and `ρ = +1`. The exact acceptance decision uses unrounded values. Integer seconds in the report are rounded outward. For GJ 1252 b at 2462502.5 BJD TDB, the reported marginals imply **175–267 s** across the possible correlations. The target is **220.602 s**, so the decision depends on covariance. [Source-bound case](CASE.json)

## Full source comparison

| Original input | BJD TDB anchor | Within for all correlations | Covariance-sensitive | Exceeds for all correlations | Zero-covariance-only passes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Publication Table 8 | 2462502.5 | 558 | 13 | 49 | 5 |
| Publication Table 8 | 2464328.5 | 527 | 12 | 81 | 4 |
| ExoClock JSON snapshot | 2462502.5 | 604 | 23 | 149 | 9 |
| ExoClock JSON snapshot | 2464328.5 | 564 | 19 | 193 | 4 |

“Zero-covariance-only” means the planning threshold passes when the covariance term is set to zero but is not robust over the allowed range. The separate Decimal implementation verifies the neighboring epochs, computes squared extrema and checks the bound. It agreed with the rational implementation on **2,792** original-record and horizon combinations. These calculations share source semantics and scientific assumptions. The published JSON uses a different format and held targets. It belongs to the same research domain and cannot establish independent astronomical observations or cross-domain generalization. [Survey receipts](SURVEYS.json) · [Frozen subsets and digests](BINDINGS.json)

## How the construction comparison works

Each model's conditions receive the same objective, output specification, four examples, tool and evidence values. The direct condition uses positional fields with descriptions. The HARNESS condition adds its existing process framing to the same position-based task. The typed condition exposes exactly those quantities with named roles, units and time basis. A sealed artifact runs in the same isolated Python worker on one case at a time. The candidate has no access to held case files or answers. A separate program scores exact decisions, epochs, rounded uncertainties and provenance witnesses. One administrator operated both sides.

The strongest accessible construction was the included Codex session using the reviewed manual export/import. It accepted **4/4 development cases** and **28/28 held cases** (12 paper, 12 fresh archive-format cases, 4 boundary cases). Both numerical references also accepted all 28. A successful handoff and a useful exact tool therefore share the best observed correctness. A construction-speed or complete-cost advantage was not measured. The experiment does not authenticate an independent frontier-model account or independent evaluator administrator. [Manual packet](MANUAL-PACKET.json) · [Returned artifact](MANUAL-RESPONSE.json)

Local model evidence records failure, measured token use when reported, time, checkpoint reservations and individual held outcomes. Absence of a runnable candidate is scored separately from an incorrect calculation. The materiality gate needs at least two additional accepted cases versus both matched model conditions, typed representation shown to be necessary for a correct execution, fresh-source acceptance and no additional unsupported decisions. A model-based improvement cannot be attributed to the representation if the matched comparisons could not complete. [Comparison and scope](RESULTS.json) · [Raw run and evaluation receipts](model-evidence.json)

## Retained capability and operating scope

Run the three scientific environments through `science_workbench.py`. The original Endpoint replay returns a concurrency floor of **256**, witnessed by `e045` and `e072`, with operational adoption in abstention. The calibration replay returns the exact fractional slack `154525728350382 / 1892645562643243` certified by `row-07` and `row-02`. The retained representations and source adapters were applied to the two ephemeris formats. That proves software reuse and source-format qualification for this problem. Inventor improvement, new parameter training, causal transfer to invention, later generations and recursive compounding require separate qualifying results.

The workbench records the public inputs, mathematical assumptions, exact references, source lineage, portable outputs and follow-on research in the same release. The published browser example does integer arithmetic on the device. The workbench does offline standard Python calculations independently of model inference. Candidate execution remains opt-in and isolated. The software never executes candidate code in the browser or serves an inference endpoint. Independent evaluator custody and confidential delivery remain tracked under [#565](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/565) and [#550](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/550).

Costs are recorded at the layer where they were observed. CPU inference issued no paid provider requests. Per-attempt wall time and reported usage are in the receipts. Unreported use is distinct from a zero measurement. Human work, power, maintenance, opportunity cost, cost of replacing missing records, and realized economic return were unmeasured. Software operation on public workloads provides no evidence of consented member benefit or continuing autonomous invention. [Follow-on investigation and interruption evidence](NEXT.json) · [Replay commands](../../products/frontier-member-tools/activation/SUBSTRATE.md)

## Résumé en français

L’atelier audite un seuil d’incertitude de datation à partir d’éphémérides publiées. Deux calculs indépendants concordent sur **2 792** combinaisons d’enregistrements et d’horizons. Au premier horizon, **5 des 620** éphémérides de l’article satisferaient le seuil en supposant une covariance nulle alors que les données publiées ne suffisent pas à garantir cette conclusion. Pour GJ 1252 b, la plage admissible est de **175 à 267 s** pour un seuil de **220,602 s**. La qualification porte sur le modèle linéaire et sur le transfert vers un second format de données. La planification d’observations demeure en abstention.

L’artefact construit par transfert manuel dans la session Codex a réussi **28 cas sur 28** en vérification, tout comme la référence exacte. L’atelier regroupe aussi le rejeu des capacités d’inférence et le contrôle des intervalles d’étalonnage. [Résultats comparatifs](RESULTS.json) · [Commandes pour l’atelier](../../products/frontier-member-tools/activation/SUBSTRATE.md)
