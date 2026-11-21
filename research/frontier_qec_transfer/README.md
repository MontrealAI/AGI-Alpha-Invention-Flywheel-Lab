# FRONTIER Ω — Recovery, then nondestructive noise identification

**Two useful computational research capabilities are implemented and independently qualified.** The second uses the retained first capability to construct a different measurement-and-inference tool. Three matched construction pairs show a mixed, descriptive latency benefit: two favorable pairs and one practical tie. **Acquisition-inclusive economic payback remains unestablished.**

Read the [complete result and limitations](REPORT.md), the [first independent verdict](evidence/first/FIRST_VERDICT.json), and the [second independent comparison](evidence/second/SECOND_VERDICT.json). This package is classical scientific software; it does not operate quantum hardware or establish commercial revenue.

## What you can use now

| Capability | Useful operation | Original independent qualification |
|---|---|---|
| [General sparse recovery](recovery.py) | Recover logical information from correctable noise, including overlapping and degenerate error spaces; preserve raw mass and report erasure. | 824/824 checks, six cohorts including the archived controlled-S15 artifact. |
| [Nondestructive noise experiment](noise_experiment.py) | Construct executable measurements, identify the physically available noise-mixture subspace, and infer a feasible mixture without disturbing logical information. | 163/163 checks for the selected source; all seven constructed routes qualified. |

The first tool expands the callable research domain beyond the existing phase-code instrument's intentional zero-moment restriction. The second goes beyond another recovery calculation: it constructs an information-gathering instrument and an estimator. Indistinguishable hypotheses are reported honestly as nonunique.

The original `inventions/phase_codes/` files and their pinned artifact are unchanged. Both tools apply established mathematics; no world-first algorithm or advantage over all conventional methods is claimed.

## Run the working example

From the repository root, use a scientific Python environment with the versions in [requirements.txt](requirements.txt):

```sh
python -m pip install -r research/frontier_qec_transfer/requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python research/frontier_qec_transfer/demo.py
```

The example encodes complex logical states, applies noise, executes recovery, then executes the second tool's exported measurement operators and estimates the available parameters. It reports the actual source hashes and numerical errors. The selected seven-qubit example recovers all 22 specified mixture probabilities subject to normalization; the nine-qubit example reports a rank-22 identifiable quotient among 28 hypotheses.

The [recorded operator demonstration](evidence/OPERATOR_DEMONSTRATION.json) is source-matched to the current entry points. The selected successor uses **484 measurement outcomes** on those fixtures. This is a mathematical instrument and classical simulation, with no compiled hardware circuit or optimal shot-cost claim.

## Reproduce every scientific construction

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python research/frontier_qec_transfer/reproduce.py --all-arms
```

The command creates a fresh temporary output directory, prints each receipt path and writes `SUMMARY.json`. Add `--output /absolute/new/directory` to choose a destination; relative paths are resolved from the calling directory. An existing receipt is refused so a stale result cannot be mistaken for a new run.

The [source manifest](SOURCE_MANIFEST.json) binds the exact project sources, retained dependencies, scientific checkers, inputs and expected recorded verdicts. Each qualification runs in a fresh process with one BLAS thread and a 10 GiB address-space ceiling. This is ordinary Linux scientific Python, not the Capability Forge seccomp sandbox. Every replay records its actual Python, NumPy, SciPy and platform versions. Third-party binaries and BLAS builds are not asserted byte-identical across hosts.

This command replays the frozen **scientific artifacts**. It does not rerun the AI constructions or reproduce their original elapsed times. Those construction observations are preserved in their original receipts.

## APIs and applicability

From this directory:

```python
from recovery import Recovery
from noise_experiment import NoiseExperiment

recovery = Recovery(n, codewords)
state = recovery.encode(logical_amplitudes)
result = recovery.recover(noisy_kraus_branches)
recovery_operators = recovery.kraus()

experiment = NoiseExperiment(n, codewords, hypotheses)
measurement_operators = experiment.measurement_operators()
response = experiment.response_matrix()
identifiability = experiment.identifiability()
estimate = experiment.estimate(observed_counts_or_probabilities)
```

Sparse states are dictionaries mapping integer physical basis indices to complex amplitudes. Physical qubit zero is the most significant bit. Exported operator rows contain **direct coefficients**: multiply them by the input amplitudes without an extra conjugation. Separate input branches are summed incoherently.

The [first contract](FIRST_CONTRACT.json) specifies the sparse, well-conditioned domain up to twenty physical qubits. The original independent frozen cohort covers seven-, nine- and fifteen-qubit codes, with logical dimensions two and four. The twenty-qubit development case and later supplemental review have separate evidence scopes.

The [second contract](SECOND_CONTRACT.json) specifies up to nine physical qubits, a two-dimensional logical code and up to 32 named local CPTP hypotheses. Each hypothesis contains `name`, `qubit`, and a list of complex 2×2 `kraus` matrices. Unknown mixture weights are nonnegative and sum to one. No arbitrary out-of-model noise guarantee is made.

`estimate` normalizes classical observations, rejects zero total observations, and reports identifiable coordinates. When the model is deficient, its returned weights are a feasible representative, not a uniquely identified underlying mixture. Finite-count results are descriptive; they do not promise universal accuracy.

## What the transfer comparison found

| Pair | With retained source | Without it | Difference |
|---|---:|---:|---:|
| 1 | 368.4 s | 479.4 s | 111.0 s lower |
| 2 | 344.0 s | 386.7 s | 42.7 s lower |
| 3 | 349.2 s | 347.3 s | 1.9 s higher |

All six sources passed the same **163 primary checks**. The mean reduction was **50.6 seconds**, or **12.51% of the control mean**. A separate ordinary-reuse construction using the independently qualified conventional first asset also passed 163/163, with a recorded interval of **373.6 seconds**. It provides a capable conventional reusable route.

These are constructor-recorded intervals, not exclusive model inference, monetary savings or a reliable general speedup. The three pairs repeat the same second objective; they are not three different productive inventions. The first asset's recorded dispatch-to-freeze interval was **348.8 seconds**, and each observed one-successor saving is smaller. Complete research, verification, integration, inference and maintenance costs remain additional or unknown.

The selected operator is the unchanged `pair2_retained` source. It uses fewer outcomes and had a lower qualification memory footprint than the initial `pair1_retained` operator. The [selection record](evidence/OPERATOR_SELECTION.json) preserves the tradeoff and the limits of conditioning and finite-sample comparisons. All alternative sources and original observations remain under [constructions](constructions/).

## Inspect the evidence

- [Opportunity selection](SELECTION.json): three different candidate directions, the installed gap and historical source identities.
- [Prospective comparison protocol](protocol/TRANSFER_PROTOCOL.json), [common constructor task](protocol/COMMON_CONSTRUCTOR_TASK.txt) and [dispatch records](protocol/DISPATCH.jsonl).
- [First frozen checker and inputs](verification/first/) and [second frozen checker and inputs](verification/second/), released after construction freezing.
- [First-stage evidence](evidence/first/) and [second-stage evidence](evidence/second/).
- [Selected successor's actual functional reuse](evidence/second/pair2_retained_functional_use_trace.json).
- [Selected successor's ambiguity-resolution witness](evidence/second/pair2_qualified_successor_ambiguity_resolution.json). This witness is specific to the recorded first readout basis and numerical environment, not an impossibility claim about other recovery measurements.
- [Independent conventional recovery](alternatives/recovery_conventional.py).
- [Complete interpretation, costs and primary references](REPORT.md).

Scientific qualification was performed by a separate assistant verifier; a different assistant reviewed code and evidence. These are not external scientific or commercial certifications. Construction used the available included-agent route; the HARNESS local-model frontend and a production release are separate, unclaimed statuses.

## Français

Deux outils de recherche fonctionnent : la correction quantique dans un domaine numérique plus général, puis la construction d'une expérience d'identification du bruit qui préserve l'information logique. Les sept constructions du second outil ont chacune réussi les **163 vérifications primaires**, y compris une solution conventionnelle réutilisable.

La conservation du premier outil réduit le temps de construction observé dans deux des trois paires; la troisième est pratiquement à égalité. Le gain moyen de **50,6 secondes** ne rembourse pas les **348,8 secondes** mesurées pour l'acquisition du premier outil, sans compter les autres coûts. Le transfert fonctionnel est établi; l'avantage économique complet, les revenus, l'amélioration de l'inventeur et l'exploitation d'un matériel quantique ne le sont pas.
