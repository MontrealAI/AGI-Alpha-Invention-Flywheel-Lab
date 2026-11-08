# Construction brief · From nuclei to cell bodies

**The useful outcome:** a researcher can run a defined image-analysis instrument locally, inspect the objects it found, obtain pixel-based measurements, and see exactly where it meets or misses a previously declared reference standard.

**The next question:** does experience constructing that instrument improve the construction of a different instrument, after giving a conventional builder the same experience?

## Purpose, means and acceptance

| Element | This construction |
| --- | --- |
| Beneficiary | Researchers evaluating reproducible offline image measurements. No laboratory has been recruited and no external acceptance is claimed. |
| First outcome | Nucleus instance masks, counts and segmentation-derived pixel-area estimates on BBBC039v1. |
| Successor | Whole-cell instance masks from DNA and actin channels in BBBC007v1, a different assay and measurement requirement. |
| Knowledge | Published dataset descriptions, supplied expert pipeline, standard morphology/watershed methods and the explicit finite recipe grammar. |
| Instruments | Pinned image loaders, recipe interpreter, retained construction order, runnable emitted recipes, independent checker and diagnostic outputs. |
| Process | Fetch and verify data; construct on the declared calibration fields; freeze the selected recipe; evaluate withheld fields; inspect failures; resume safely if interrupted. |
| Resources | Existing CPU environment, pinned Python dependencies, 87.8 MB of compressed public inputs and transient output space. Measured run costs are reported separately from unknown total authoring/model costs. |
| Arrangements | Public-data terms and the repository's existing research-publication authority. No customer, laboratory agreement, payment or real-world deployment is assumed. |
| First acceptance | Mean instance F1 at IoU > 0.5 at least 0.70, mean relative count error at most 0.20, and mean foreground Dice at least 0.85 on both official validation and test. |
| Successor acceptance | On the four calibration and twelve test fields, the registered gates require internal-boundary F1 at two pixels at least 0.60 both overall and on fields with true internal boundaries, mean relative count error at most 0.25, and foreground Dice at least 0.80; calibration needs at least one and test at least two reference fields with internal boundaries. |
| Remaining obligations | Preserve versions, inspect new-domain applicability, retain adverse results, verify changed inputs and maintain dependency compatibility. New assay use needs its own calibration and acceptance. |

These are research qualification thresholds authored before scores were observed. They do not establish clinical utility, biological conclusions or laboratory certification. Areas are pixel estimates derived from the segmentation; matched-instance area error is reported as a diagnostic, not a guarantee of accurate physical areas.

## What the six builders receive

All builders use the same 24 classical recipes and raw target channels, the same four calibration fields and the same verification standard. There is no artificially tight search allowance: each may examine every recipe. Ranked builders stop only when a candidate meets all calibration gates. Full enumeration always evaluates the entire bank.

| Builder | What changes |
| --- | --- |
| Fixed, no history | Uses the frozen expert-informed order without donor history or privileged donor placement. |
| Ordinary reuse | Tries the donor recipe first, then the fixed order. |
| Updated, no privileged artifact | Uses a greedy coverage order learned from the donor's construction records. The donor recipe remains an eligible member of the common bank. |
| Updated with artifact | Tries the donor recipe first, then the learned order. |
| Same-content empirical control | Uses the identical donor records with ordinary aggregate empirical ranking. |
| Full enumeration | Tests all 24 candidates and chooses by the common target-calibration quality rule. |

The decisive local contrast is **greedy coverage versus same-content empirical ranking**. Both use experience. It tests an update to the ordering parameter of a supplied finite constructor, not autonomous invention of new algorithms. The primary work measure is calibration candidate executions. CPU, elapsed time, verification and complete donor costs remain separate; a shorter prefix is not automatically a cheaper complete route.

## A practical entry point

Start with the [operator README](README.md), then read the frozen [protocol](PROTOCOL.json) and [opportunity comparison](OPPORTUNITY.md). The tiny offline fixture checks installation and the command interface. The full public-data operation produces the actual scientific evidence. Keep those two results distinct.

An emitted instrument accepts raw image channels and a recipe. Its masks and measurements are inspectable outputs, not an instruction to trust an agent's account of its work. The independent checker reconstructs the important metrics from the original reference data and the saved masks.

## What would justify the next step?

If an instrument qualifies, retain the simplest effective route and test it on another independently sourced assay with a declared purpose. If the learned ordering does not beat ordinary construction, keep the conventional method. If whole-cell delineation fails, investigate the observed failure mechanism before expanding the framework. If the reference representation is inadequate, obtain a supported reference or change the proposed measurement; do not improve the story by changing the denominator.

No commercial arrangement is tested here. A future service would require evidence of a beneficiary's actual need, current complete alternatives, agreed acceptance, delivery and support costs, voluntary participation and permitted operation. It would use the repository's existing financial authority rather than a new ledger.
