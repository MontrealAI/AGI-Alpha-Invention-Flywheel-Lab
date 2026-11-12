# N3: physical process interface and inverse-mask construction

## Result
The registered single run completed, and independent replay reproduced 1,818 metric/choice checks exactly. This is useful measured engineering evidence and a reusable mask-generation instrument, **not an accepted manufacturing capability or a qualified Blue Sky business**.

Frozen source, fitted models, independent target requests, nine generated mask recipes and checker were public at commit `0efb91e4e477339e171cfdb1123a739b7590667b` before confirmation. The run used 300 patches from one separately printed physical slide in [NIST mds2-2950](https://data.nist.gov/od/id/mds2-2950). It took 41.46 seconds, excluding development, source acquisition and historical physical experiments. There was no refitting or target revision.

| Frozen method | Mean per-patch active RMSE, µm (all 300) |
|---|---:|
| Ordinary single-blur cubic | 20.075 |
| Constructed multiscale spatial polynomial | 20.897 |
| Archived L1 U-Net | 22.052 |
| Archived MSE U-Net | 22.388 |
| Archived pix2pix | 22.460 |
| Pointwise cubic | 27.124 |

All three archived comparators bind all 300 source-index inputs: 14 raw identities and 286 exact source-derived float32 normalization identities each. This compares saved outputs, not independently reproduced neural-network training. No favorable permutation, case dropping or approximate input matching was used.

The multiscale model performs better than blur on the 286 random-mask patches (17.991 versus 18.969 µm), but much worse on the 14 white fiducials (80.275 versus 42.672 µm). The prespecified full denominator remains 300; the subgroup does not overturn the overall result. No test mask exactly or dihedrally duplicates training, and none exactly duplicates development. The single-slide limitation remains.

## Different successor task: inverse recipes
Independent requests specified a 50 µm ridge, a 100 µm closed wall, and a 50/100 µm terrace. Frozen predictions selected historical masks before their measured heights were used for scoring. The multiscale selections achieve active-region physical target RMSE of **24.841 / 48.190 / 34.489 µm**, respectively. Existing archived models improve the ridge to 23.400 µm and wall to 47.623 µm and tie the terrace at 34.489 µm. This is retrospective selection of already manufactured recipes, not newly printed geometry. There was no physical acceptance tolerance and therefore no claim that these errors meet a manufacturing contract.

Nine actual quantized PNG/SVG exposure-mask recipes were also constructed. All differ from the archived masks; independent numerical prediction replay agrees within 9.95e-14 µm. **Five remain MODEL ONLY and four retain COMPUTATIONAL HOLD** from the fixed optimization budget. None was printed. Accurate forward predictions on random masks do not protect inverse optimization against model error. Dimensional RMSE does not certify wall continuity or functional performance.

## Learning and next discriminating evidence
1. Spatial paired truth supports a more meaningful interface than a scalar cure-depth summary; it still does not make inverse artifacts physically validated.
2. A compact ordinary blur model is a strong overall outside option. Additional complexity is not automatically valuable. This does not disprove a profitable autonomous execution arrangement; comparative lifecycle labor/cost and paid acceptance have not been measured.
3. The next decisive *physical* evidence would be independently specified functional tolerances and blinded measured prints of the frozen new masks, with incumbent recipes and multiple batches. That is outside this offline authorization. Repeated tuning on this slide is not a substitute.
4. No commercial account, customer collection, financing receipt or projected $3B result is claimed. Production qualification, demand, liability, revalidation and full lifecycle cost remain open.

## Preserve unsuccessful work
N3A stopped during development after 30 of 42 calibration acquisitions, with zero of 52 validation acquisitions opened. Its scalar observable cannot identify spatial geometry; committed source retrieval was about 201.9 MB, with in-flight bytes unknown. N3B is an explicitly different source-bound test, not a renamed N3A success. Battery and geothermal arrangements were compared in `ARRANGEMENT_COMPARISON.md`; source conditioning and incumbent/physical-output limits were retained rather than invented away.
