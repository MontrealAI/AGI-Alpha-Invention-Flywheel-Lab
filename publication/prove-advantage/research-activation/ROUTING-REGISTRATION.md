# Model-routing decision and replay scope

The [Routeability Audit Protocol preprint](https://arxiv.org/abs/2611.34825v1) asks whether different portfolio arms win on different cases before investing in a router. Its public inbox disposition is [TEST](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/0a9f9e0074194404eb98b02634d735fa4e4d0a4d/publication/frontier-watch-refs.json). The [AnyS1 preprint](https://arxiv.org/abs/2611.23751v1) motivates investigating cheaper accepted execution separately from acceptance improvement.

## Decision under test

Can a selector confined to the answers already produced by the frozen arms increase complete acceptance? Use the strongest single arm as the conventional quality control. A perfect selector that sees the reference gives the upper bound by counting cases where any arm succeeds. When the bounds coincide, defer work on improving acceptance by selecting among those frozen arms. When no arm accepts a case, examine source acquisition or construction that can change the answers. An upper-bound gap justifies investigating predictors when case features are available at decision time. It supplies no estimate of a realizable gain.

Holding quality constant and choosing the least-cost arm is a separate conventional decision. A comparison requires measured full workflow costs, including selection and review. Keep that decision unresolved when matched costs are missing. Always report uncovered cases against the all-accepted target.

## Frozen public inputs

Use source revision `b35f937fcb77199334e267360e9a0c9e438a74ad` and the checksum manifests in [DPP replay](../dpp-replay/SHA256SUMS) and [Game Theory](../game-theory/SHA256SUMS). Audit each panel separately, checking file identities, case IDs, equal coverage and complete acceptance.

| Panel | Cases | Arms | Complete acceptance |
| --- | ---: | --- | --- |
| DPP primary | 16 | Competent direct and integrated FRONTIER Ω | Frozen disposition, attributable source set and rationale presence |
| DPP confirmation | 6 | Competent direct and integrated FRONTIER Ω | Same scoring on the confirmation panel |
| Game Theory primary | 10 | Four SmolLM2 arms, Qwen3 4B and included Codex | Every information-access claim accepted with admissible source evidence under the primary oracle |
| Game Theory confirmation | 8 | Four SmolLM2 arms with frozen outputs | Every information-access claim accepted with admissible source evidence under the confirmation oracle |

Excluded from the DPP portfolio are the deliberately weakened scope-withdrawal arm, the adverse panel without a matched direct arm and repeat execution with identical inputs. The Game Theory primary uses the frozen oracle in the main adjudication, with the published sensitivity analysis reported separately. The developed confirmation panel has no matched Codex or Qwen3 4B control. Keep both panels distinct because the set of available arms differs.

This registration fixes the durable replay after inspecting historical reports and completing an exploratory DPP audit. Published aggregate outcomes were already known. The adaptation to the two Game Theory adjudications was fixed before calculating their case alignments. The original study registrations and limitations remain in force. The analysis uses public archived inputs, Python standard-library computation and no paid requests. Success is an inspectable, reproducible bound and a justified decision about further engineering.
