# Measurement construction 009

This instrument constructs a source-identification observation plan from an actual
EPA EPANET network simulation. Its first useful delivery is an auditable planning
package for engineering analysis: model inputs, complete source-response corpus,
an ambiguity witness, a generated calibrated measurement expression, a sensor
plan, and diagnostic interpretation. It is not a deployed water-safety service.

## Why construct a new observation path?

The exposed Net1 development experiment supports two distinct modeled sources,
23 and 32, whose complete 24-hour traces at all nine sensors can be made identical
by allowed constant sensor offsets and bounded reading errors. Exact rational
bias, error, and shared-observation vectors are emitted. Selecting more of those
unchanged observations cannot resolve that witness.

The extension proposes an additional **known-zero reference measurement at each
selected sensor**, with the same additive offset as the subsequent trace. This is
new information and a prospective physical assumption. Such references have not
been obtained in the field. The compiler enumerates bounded signed expressions,
checks units and nuisance coefficients, and generates
`subtract(read(sensor,time), zero_reference(sensor))`. It records which parts were
generated and which primitive proposal was supplied by the builder after the
counterexample. There is no arbitrary-code evaluation.

Calibration subtraction, test-cover optimization, and error propagation are
established techniques. Constructing their executable combination here does not
establish a novel scientific method or superiority over a competent conventional
workflow. The strongest ordinary comparator receives exactly the same reference
information and assumptions.

## Exact finite model

For source h, sensor s, and sampled time t, the uncalibrated observation is
`y[h,s,t] = x[h,s,t] + b[s] + e[s,t]`. The bias is arbitrary but constant; every raw
reading error is bounded by epsilon, including the reference error. The reference
reads `r[s] = b[s] + e0[s]` at a known-zero condition. Corrected traces are
`z[s,t] = x[h,s,t] + e[s,t] - e0[s]`. Reference noise is shared across the time
series; it is not ignored or modeled as independently resampled for every time.

For the difference d between two source signatures at one sensor, define M as its
maximum and m as its minimum over the complete declared time grid. Without a
reference, the pair remains compatible iff `M - m <= 4 epsilon`. With the
reference, compatibility additionally requires `M <= 4 epsilon` and
`m >= -4 epsilon`. These are equivalent to an interval-intersection condition
used by the separate verifier. A pair must be incompatible at at least k+1
selected sensors to survive arbitrary erasure of k sensors. Error correction for
unreported faulty sensors is a different obligation and is not claimed.

The declared development epsilon is 1 source-contribution percentage point,
with one sensor erasure. These are authored engineering assumptions, not an
instrument calibration certificate, physical toxicant threshold, or buyer
acceptance criterion. TRACE quantities describe source contribution percentages;
they are not general contaminant concentrations or unknown injection profiles.

Numerical semantics are
`canonical-json-finite-binary64-decimal-rational-v1`: finite parsed binary64
values are canonically serialized with Python `json.dumps`, and the resulting
numeric decimals are interpreted as `Fraction(str(value))`. This is neither the
exact binary expansion produced by `Fraction.from_float` nor an arbitrary raw
JSON lexeme. A development disagreement about this convention is preserved in
the verifier's original probe and adjudication; it preceded confirmation.

## Execution and comparisons

From the repository root, use the existing resource wrapper and the single
campaign ledger. Give each run a fresh output path and run identifier:

```bash
python -m experiments.resource006_v3 \
  --ledger evidence/next009/RESOURCE_LEDGER.json \
  --run-id measurement009-example \
  --output /tmp/measurement009-example \
  --wall 420 --cpu 360 --memory-bytes 2147483648 \
  --output-bytes 67108864 --storage-bytes 268435456 \
  -- python -m inventions.measurement009.run \
  --output /tmp/measurement009-example/artifacts --networks Net1 Net3
```

The program runs the actual source-pinned EPANET library, generates a complete
model corpus, constructs the observation expression and sensor plan, and runs
the following controls with the same source inputs:

- Complete uncalibrated time traces, including every possible sensor.
- Ordinary calibrated greedy multicover.
- Ordinary exhaustive calibrated selection for small networks and MILP for the
  larger network.
- Generated calibrated-expression plan using the same strong MILP solver.

The generator is not a novel optimization algorithm. The common MILP results
are expected to tie. An independent implementation separately checks the plan,
ambiguity witness and, for Net1, exact minimum cardinality by all subsets.

`ObservationInterpreter` captures an immutable numeric model at initialization.
It chooses the next diagnostic trace according to how many remaining source
pairs it distinguishes, filters the compatible source set, and checks every
remaining supplied trace before accepting a unique result. It abstains or
reports model inconsistency when evidence does not support a unique source.
This is adaptive interpretation of declared observations. It does not avoid
their physical acquisition, sensor deployment, calibration, or monitoring time.

## Public Python interfaces

```python
from inventions.measurement009.compiler import compile_plan, diagnose, ObservationInterpreter
plan = compile_plan(corpus, noise_bound_pp='1', max_sensor_erasures=1, algorithm='milp')
answer = diagnose(corpus, plan, observations)
interpreter = ObservationInterpreter(corpus, plan)
answer = interpreter.diagnose(observations)
```

`relation_matrix`, `sensor_separates`, and `solve_relations` expose the typed
construction boundary for a separately registered extension. `simulate` accepts
only the two registered development networks by default; a fresh verifier model
requires an explicit path and expected Git blob. Net2 is reserved for the separate
successor protocol and is not bundled or inspected by this construction worker.

## Limits that cannot be removed by a software pass

The known zero must actually be known, and sensor offset must remain constant
between the reference and sampled trace. Drift, invalid standards, timing errors,
unmodeled source mixtures, or demand-model errors require a qualified extension
or abstention. Boolean claims about reference validity are declarations, not
evidence that a physical calibration occurred. A later drift-aware successor
must pay for any extra reference measurements and qualify the changed model.

All development cases, failed runs, disagreements, and interruption receipts
remain exposed and charged. Compute measurements are not complete monetary
costs. No order, receipt, unrestricted earnings, or investment is generated by
this instrument. The first offer is a model-based planning deliverable; field
collection, professional sign-off, and live safety decisions remain outside its
qualified scope.

## Sources and licenses

The bundled network inputs and EPANET library come from WNTR commit
`11eec7d5bf0a9367ffe04d75707918f0c0a890a1`. Every execution verifies their Git blob
identities before loading the simulator. The upstream BSD and EPANET MIT notices
are included in `inputs/WNTR_LICENSE.md`.

- [Official WNTR examples](https://usepa.github.io/WNTR/examples.html)
- [Sandia Chama sensor-placement example](https://github.com/sandialabs/chama/blob/main/examples/water_network_example.py)
- [EPA source-identification benchmark](https://catalog.data.gov/dataset/dataset-for-testing-contamination-source-identification-methods-for-water-distribution-net)
- [Minimum test-cover formulation, author manuscript](https://arxiv.org/abs/1507.07134)
- [Robust sensor placement, primary paper](https://par.nsf.gov/servlets/purl/10350109)

The earlier independent cheap baseline reproduced Chama's exact Net1 three-sensor
detection optimum, 12/23/32 and 7,600 seconds. Detection time and robust source
identification are different obligations; the latter is not claimed to beat a
competent identification baseline merely by outperforming the detection layout.
