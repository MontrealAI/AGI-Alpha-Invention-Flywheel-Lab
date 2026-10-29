# Three productive possibilities and an executed falsifier

This comparison is a rapid development screen. It admits no commercial cohort and makes no novelty, superiority or confirmatory claim. The new owner instruction supplies a finite allocation; previous stopped campaigns and negative evidence remain unchanged. The comparison selected a **real-model scientific falsification probe**, not a commercially qualified flagship. Its aim is to prevent a local repair from being inherited beyond its verified scope.

| Productive possibility | Beneficiary and inaccessible outcome | Binding limitation and missing means hypothesis | Strong complete alternatives | Cheapest discriminating test and access decision |
| --- | --- | --- | --- | --- |
| Reliable transfer of metabolic pathways between computational organism models | Strain designers need predictions that survive reaction transplantation, rather than fictitious energy and inflated growth | Cross-model reactions can combine inconsistent transport stoichiometry/reversibility. Hypothesis: a generative applicability check can construct a scoped repair while preserving productive obligations | MEMOTE's energy-dissipation FBA test; Fritzemeier et al.'s GlobalFit simultaneous EGC elimination and growth preservation; domain curation and thermodynamic constraints | Obtain a real erroneous model; run closed-input energy-production LP before and after a proposed local repair. **Executed below.** A known method can win. Finding an EGC alone is not new means of production. |
| Causal intervention maps for cellular engineering | Experimentalists need reliable effects of previously unperformed perturbations, rather than observational association | Partial observability, off-target/partial interventions and poor scaling break standard causal assumptions. A new representation or experiment-selection policy would need to reduce consequential uncertainty | CausalBench baselines and challenge methods; BetterBoost, PSGRN and inverse sparse regression; held-out interventions and measured biological validation | Reproduce strongest complete baseline on an independently selected held-out intervention family. Public CausalBench code exists; two curated data sets exceed 200,000 training examples. No complete runtime/data download was qualified in this cycle. **Bounded alternative, not admitted.** |
| Constitutive-law discovery from sparse indirect physical measurements | Materials/process investigators need a material law that predicts outside the measured field, with defensible uncertainty | PDE propagation plus sparse observation can suppress information about the constitutive law; more observations of the same kind may remain prior dominated. Missing-means hypothesis: construct direct-measurement interventions from an identifiability certificate | Existing adjoint/Bayesian inverse methods, physics-informed/ODIL fitting, the 2026 PNAS Nexus direct-measurement/OED framework | Reproduce a real field-data residual under the strongest full inverse workflow, then test added *physical* direct measurements. The 2026 primary paper already develops this direction; no independent physical data/measurement allocation was recovered. **Bounded alternative, not admitted.** |

The latter two possibilities require additional qualification; missing data/runtime is a finding about this allocation, not a claim of global inaccessibility. These are different scientific tasks with different intervention semantics and validation requirements. None supplies independently evidenced buyer price, participation, negative baseline complete-cost profit or unrestricted earnings.

## What actually ran

`flywheel/metabolic_probe.py` extracted the exact three relevant reaction equations and bounds from a public, pinned SBML archive of `Seed272620.3`, the model name identified in Fritzemeier et al. (2017), Figure 6A. The archive contains 1,609 reactions and 1,464 species. Its SHA256 is `2eb450d8fa4307ec384782ffc03011473c4bf9ec8513c68e1341a66d0179895d`. The archive is a mirror, and byte-for-byte identity with the paper's original full-model input has not been established. The equations agree with the paper's described transport mechanism.

In source directions, the reactions are:

- `rxn10153`: two external protons plus external malate become two internal protons plus internal malate.
- `rxn05207`: external malate plus external sodium become their internal counterparts.
- `rxn05209`: internal proton plus external sodium become external proton plus internal sodium.

All three source reactions are reversible, with bounds ±10,000 mmol/gDW/hour. Reversing `rxn10153` and `rxn05209`, while running `rxn05207` forward, produces a proton gradient at steady state without a modeled external input. This is a **known published non-seeded defect**, not a new finding by the Lab. The model is computational; this result does not measure a physical violation of thermodynamics.

The LP maximizes an explicitly added proton-dissipation diagnostic. It yields 10,000 source-unit diagnostic flux before repair and zero after the published restriction `rxn10153` lower bound = 0. The number 10,000 is the supplied finite flux bound, not a measured ATP-production rate. The method is conventional FBA using SciPy HiGHS. There is no candidate advantage over the established diagnostic and repair.

The important scope falsifier then ran the **entire archived model**, fixed every `EX_` exchange to zero, and added ATP hydrolysis as the diagnostic. It yielded 10,000 before and **10,000 after the same single direction restriction**. A local remedy cannot be promoted to a whole-model cure. Other energy-generating cycles remain. The paper's stronger GlobalFit method explicitly considers all cycles while preserving growth; that full algorithm was inspected in the paper but not installed/executed here. We therefore claim neither superiority nor equivalence to it.

`metabolic_RESULT.json` preserves original/repaired results, actual nonzero flux witnesses, residuals, exact identities, timings and resource unknowns. All cases were exposed during development. No statistical confirmation was attempted, and no campaign error budget was replenished. The primary source already contains both the defect and a direction-restriction remedy. This probe is a useful applicability counterexample and scientific falsification, **not** the requested new productive boundary crossing.

## Reproduce

The reduced three-reaction input is included as `metabolic_subnetwork.json`; it is an attributed factual extraction of the paper-described equations, not redistributed full-model software. No imported MEMOTE code is present. SciPy is an optional scientific-probe dependency, separate from the core mechanism runtime.

```sh
python -m pip install scipy==1.17.0
python -m flywheel.metabolic_probe --output /tmp/alpha-metabolic-NEW
```

For the actual full-model scope test, obtain the pinned archival source and verify its hash before the parser executes the LP:

```sh
curl -L --fail -o /tmp/Seed272620.3.xml https://raw.githubusercontent.com/yipingwang12/SEED/cdc38aeaee810db7089264256f4e3141142be8f4/input/SEEDModels/Seed272620.3.xml
python -m flywheel.metabolic_probe --sbml /tmp/Seed272620.3.xml --output /tmp/alpha-metabolic-FULL-NEW
```

The raw 1.88 MB SBML remains outside the published source because redistribution terms for the mirror were not independently established. The exact URL/hash makes the full experiment reproducible; availability of that third-party URL is a dependency. The parser refuses a changed archive. Generated strategies are not executed by this module; this is fixed trusted scientific code. An interrupted output directory must be preserved, with the rerun directed to a new path.

## Decision and next action

**RETAIN_INCUMBENT / NO_COMMERCIAL_ADMISSION.** Retain the scoped failure: a verified local repair must be rechecked after composition with a larger model. The next useful biological construction must jointly eliminate *all* energy-generating cycles and retain independently specified growth, transport and production obligations on a fresh model, against GlobalFit and equally informed domain curation. Those obligations and the scope of physiological validation cannot be inferred from this three-reaction pass. A commercial or scientific superiority claim needs that residual and a usable buyer/assay route first.
