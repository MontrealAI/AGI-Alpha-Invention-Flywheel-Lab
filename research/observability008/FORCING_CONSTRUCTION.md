# Time-forced ratio observations: constructive repair from real failures

This is a separately labeled **development** extension of the frozen generalized PEtab compiler. Boehm was selected after Crauste returned a correct empty measurement plan. No protected confirmation, population-generalization or error-budget-reset claim applies. Scientific acceptance thresholds, original source bytes and observed data were unchanged throughout the extension.

The original public Boehm model is a STAT5 phosphorylation/dimerization model with eight states, nine estimated parameters, three ratio observation formulas and forty-eight measurements. Its source includes a time-dependent Epo assignment, known cytoplasmic/nuclear volumes and scientific-notation MathML literals. The fixed initial concentrations and ratio parameter already anchor all detected multiplicative scale directions. The final output therefore reports zero required added measurements in this scope; it does not invent missing observations or establish full identifiability.

| Attempt | Actual result | Consequential requirement constructed next |
| --- | --- | --- |
| `boehm-frozen-r1` | Frozen generic compiler refuses unsupported rule/event/function class before evaluation. | Expand acyclic parameter assignment rules into an inert expression AST; interpret a known time symbol and exponential forcing. Keep dynamic rules/events unsupported. |
| `boehm-forcing-r1` | Refuses non-unit compartment volumes. | Preserve concentration semantics: each reaction amount-flux contribution divides by the affected state's known fixed compartment volume. Do not change the source's volumes to one. |
| `boehm-forcing-r2` | Refuses reference alignment because strings `0.0` and `0` differ. | Compare exact rational time identities while retaining all rows and observable identity/order checks. |
| `boehm-forcing-r3` | Independent published trajectory comparison fails by91.5242 percentage points. | Parse the entire MathML number encoding, including scientific/rational separator payloads; refuse unsupported encodings. |
| `boehm-forcing-r4` | Exact repaired source executes; maximum discrepancy1.8106e-6 percentage points. | Retain result and add early source-size, dimension, expanded-AST and observation-contract bounds. |
| `boehm-forcing-r5` | Same numerical result under bounded final source. | Replayed on both earlier public models without changing their outcomes. |

The strongest discovered defect was a silent factor-of-ten-million error in a known stimulus. The source contains `<cn type="e-notation">1.25<sep/>-7</cn>`, whose exact value is `1/8000000`. A text-only literal reader interpreted it as `5/4`. The source-based literal regression and refused unsupported encodings are recorded in `LITERAL_QUALIFICATION.json`; the large source-reference failure and its exact source revision/code snapshot remain in the attempt history. The final extension uses exact rational decoding for integer, real, e-notation and rational numbers. Other bases/encodings fail explicitly.

`compile_petab_forcing.py` is the final extension. Its source file and imported `gauge_probe.py` dependency are hash-bound in `FORCING_FREEZE.json`. The emitted `model_constraints.json` provenance also records these exact source hashes and all input hashes. It never executes source-model programs: fixed AST operations handle arithmetic, exponential forcing and the known time symbol; assignment dependencies are expanded only when acyclic and bounded. The integration owner's seccomp interpreter separately executes the emitted linear-plan program. The scientific producer's trusted source/dependency closure and numerical runs are distinct from that qualification.

The final scope adds fixed positive compartment volumes for concentration states and acyclic parameter assignments. Dynamic/estimated volumes, algebraic species, events, rate/algebraic rules, function definitions, amount-only state models, condition overrides, unsupported observation operators and nonpositive estimated scaling parameters remain refused. Early bounds limit each source file to2MiB, aggregate source files to16MiB, XML/expanded expression nodes to20,000, unknown dimension to48, measurement rows to10,000 and distinct observation contracts to256. These operational bounds are safeguards, not scientific success criteria.

Replay with a new output directory:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 timeout 180 python3 compile_petab_forcing.py --source boehm_source --output /tmp/boehm-replay-NEW
```

Final executed results are `runs/boehm-forcing-r5`, `runs/elowitz-forcing-r5` and `runs/crauste-forcing-r5`. Original fixtures/source pins and all failed attempts remain. The old frozen general compiler is unchanged. Each final run compares the original independent published trajectory using the same numerical tolerance; all measured rows remain present.

The critic-to-repair path is substantive source interpretation and execution. It is ordinary developer-directed engineering informed by verified counterexamples, **not autonomous invention**, a scientific advantage over strong existing identifiability/OED tools, an earned-funded successor or commercial success. The next scientific step remains action-relevant disagreement on independently measured attainable interventions, including actual calibration uncertainty and a strong profile-likelihood/OED route. Merely broadening a parser's accepted model set does not complete that experiment.
