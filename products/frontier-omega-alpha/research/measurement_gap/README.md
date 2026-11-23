# FRONTIER Ω ALPHA · Recovering a missing astronomical measurement

## English

**The conventional multiband Gaussian process won.** It reconstructed all **85** held-out positive ZTF difference-magnitude measurements within the preregistered **0.15 mag** experimental tolerance. The proposed cross-band adjustment selected zero weight on the separate development cases, leaving the same-band linear estimate. That route met the tolerance on **82 of 85**. Endpoint adoption remains **ABSTAIN** with indexed SQLite as its incumbent. [Frozen registration](registration.json) · [Exact signed result](evidence/confirmation.json)

### A new target after the broker tie

The first constraint was an absent measurement at an existing epoch. A second broker cannot supply a measurement that was never made. This study hid real observations and tested what the other filter and neighboring measurements could recover. ZTF measures the recorded positive-subtraction g/r difference magnitudes. Interpolation returns a retrospective estimate where nearby points bracket the epoch. The reference is a noisy held observation rather than the latent true flux. A standard multiband Matérn Gaussian process receives the same support as the proposed method. [ZTF public archive](https://www.ztf.caltech.edu/ztf-alert-stream.html) · [Multiband GP precedent](https://arxiv.org/abs/1907.04690)

The fitter compared four correction weights and nine Gaussian-process settings on 31 measurements from separate objects. It froze the selection before drawing new held IDs and selecting a fresh roster. Two prior target strata and six fresh target IDs had 430 admissible exposure records. Each chosen case removed the real detection ID and incidental same-band points at exactly its epoch. Two distinct same-band anchors were required, each within five days. Using both sides limits transfer to retrospective gap filling. The cases share objects, so the report gives object-balanced errors and descriptive counts. The registered historical and fresh cohorts are all represented.

| Target stratum | Objects | Held | Nearest | Linear | Local cubic | Multiband GP | Selected correction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Earlier, historical target IDs | 3 | 13 | 11 | 12 | 12 | 13 | 12 |
| Later, historical target IDs | 6 | 36 | 30 | 35 | 36 | 36 | 35 |
| Fresh prospectively selected IDs | 6 | 36 | 34 | 35 | 35 | 36 | 35 |
| **Total within 0.15 mag** | **15** | **85** | **75** | **82** | **83** | **85** | **82** |

The Gaussian process also had the lowest object-balanced mean absolute error in every stratum. Its errors were 0.06046, 0.04260 and 0.04880 mag, respectively. Independent NumPy linear and matrix solvers and SciPy shape-preserving cubic interpolation reproduced all 85 reference predictions to within 1e-10 mag. The signed offline replay repeats the sealed selections without fetching new data. The fit choosing zero records a prospective rejection of the proposed correction. It does not measure how unselected positive weights would generalize to confirmation.

Live acquisition took 5.50 s for development, 4.14 s for the fresh roster, and 3.62 s, 4.12 s and 3.37 s for the confirmation histories. Matched scoring took about 31 ms across the three held cohorts. The receipt preserves timestamp, bytes, exact source digests, eligible and held populations, measured uncertainty, all predictions and misses, wall time and CPU. Price, downstream operator acceptance, observational allocation and complete cost remain unknown. The study supplies a useful technical reference for a narrowly scoped estimate. It establishes no S₁ advantage, causal S₂ transfer or economic advantage. Endpoint status and production gates remain separate. [PR #566 evidence](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/566) · [Issue #550](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/550)

### Reproduce

```sh
lab=products/frontier-omega-alpha/research/measurement_gap
python3 -B "$lab/replay.py" audit "$lab/evidence/confirmation.json" \
  --key-sha256 2eaa691e4974a20aca3fb590c3b1750285970f8664ff9d4e67b2dfca3647d6f2
work=$(mktemp -d)
python3 -B "$lab/replay.py" run --state "$work/evaluator" --output "$work/public/measurement.json"
```

The `run` command uses fixed public read-only queries and selects cases once after freezing development. Matching checkpoint bytes allow resumption. New acquisitions may reflect later upstream changes. The isolated fit uses the existing Linux default-deny sandbox. The audit needs Python and OpenSSL and uses the exact archived evidence. Hosted qualification performs the offline audit and uses local non-production Endpoint tests.

## Français

**Le processus gaussien multibande conventionnel l’a emporté.** Il a estimé les **85** mesures ZTF masquées dans la tolérance expérimentale préenregistrée de **0,15 magnitude**, contre **82 sur 85** pour la méthode proposée. L’ajustement entre filtres a choisi un coefficient nul sur les données de développement. La méthode proposée s’est donc ramenée à l’interpolation linéaire sur un seul filtre. Les cas de confirmation concernent quinze objets, dont six cibles sélectionnées après le gel du code et des réglages.

L’estimation est rétrospective et requiert des mesures de part et d’autre de l’instant étudié. Aucun temps de télescope, coût complet, avantage S₁ ou transfert causal vers S₂ n’a été établi. Les reçus conservent les erreurs et les coûts mesurés. L’adoption Endpoint demeure en abstention, avec SQLite indexé comme référence et #550 comme autorité pour la production protégée. [Rapport signé](evidence/confirmation.json)
