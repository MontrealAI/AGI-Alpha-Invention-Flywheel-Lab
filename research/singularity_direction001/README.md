# Ω REALITY PROBE 001 — THE COUNTERINTUITIVE SWITCH

**A publicly reproducible experiment in which opening a *second* transmission connection after an outage increases modeled power delivery.**

**Status: scoped mathematical result under an authored stress scenario.** Not a new law of physics, discovery of the Braess paradox, physical-grid validation, authorized operating advice, real power supplied, autonomous AI research superiority, revenue, or evidence of institutional #1 status.

## Results: globally optimized conventional redispatch is not enough

The existing [IEEE PES Power Grid Library](https://github.com/power-grid-lib/pglib-opf) IEEE-14 and IEEE-30 test networks are treated with **20% additional nominal demand** and **25% lower active-flow proxy ratings**. The stress and initial outages were chosen retrospectively during exploration, *not* as a prospective blind experiment. The cases are mathematical benchmarks, not operating utility networks.

| Source network | Initial outage | Extra opened branch | Fixed-topology best unserved MW | With extra opening | Modeled gain |
| --- | --- | --- | ---: | ---: | ---: |
| IEEE-14 (14 buses; 20 branches) | 2–5 | **4–5** | **11.555738** | **0** | **11.555738 MW** |
| IEEE-30 (30 buses; 41 branches) | 12–16 | **2–4** | **69.139396** | **40.450000** | **28.689396 MW** |

A Braess-type improvement from *removing* infrastructure is counterintuitive, but the underlying network principle is established science. The result is a bounded executed illustration of an institutional method for problem transformation, not a new scientific priority claim.

**Strong control.** The baseline permits *all* continuous generator dispatches, nodal load shedding, and phase angles within the same declared lossless DC model and constraints. SciPy HiGHS solves the full linear program, rather than applying a weak heuristic. The alternative exhaustively compares **every single additional branch opening** under that same LP and stress.

## What is independently proved

The constructor publishes both *primal feasible vectors* and *dual bound multipliers*. A second, scalar checker, which does not use the optimizer, rebuilds the constraints and verifies KCL, the angle reference, line flow/phase bounds, generator and shed bounds, dual signs, stationarity, weak duality and the primal–dual gap.

The fixed-topology dual establishes a **global lower bound within the declared linear DC model**. The modified topology has a separate feasible witness below that bound. This proves a change in the *mathematical* feasible set under stated conditions, not AC power-system safety. Duality is accepted within 2×10⁻⁵ MW. Negative controls alter inputs, primal/dual evidence and claims and must fail.

The model ignores reactive power, AC voltage effects, resistance/losses, transients, protection, stability, tap-control dynamics, real-world communications, operator authority and financial costs. Thermal ratings are used as active-flow proxies. Results do **not** justify line switching in a real grid.

## Reproduce from pinned source bytes

From repository root, with Python 3.11+:

~~~sh
python3 -m pip install --only-binary=:all: numpy==2.3.5 scipy==1.17.0
python3 -m unittest discover -s tests -p 'test_singularity_direction001.py' -v
python3 -m research.singularity_direction001.experiment --output /tmp/reality-probe-001.json
python3 -m research.singularity_direction001.verify --evidence /tmp/reality-probe-001.json
~~~

Select a new path for the output if it already exists. CI runs the same checks against the exact candidate Git SHA and retains both the source-bound evidence and separate proof verdict as publicly inspectable workflow artifacts.

Original case data: [IEEE-14](../pglib_opf_case14_ieee.m), [IEEE-30](../pglib_opf_case30_ieee.m), [PGLib attribution and licence](../PGLIB_LICENSE.txt), IEEE PES Power Grid Library v23.07, CC BY 4.0. Both original source files are checked against their Git blob identities before computation.

## Why the eight mechanisms matter here

**01 Structural transfer:** transfer the known Braess-type network insight. **02 Adversarial discovery:** challenge the assumption that more active links must help, and permit worsening counterexamples. **03 Strategic invention:** alter topology rather than merely redispatch generation. **04 Problem transformation:** remove the condition inducing congestion instead of buying extra hardware. **05 Epistemic invention:** build an exact LP with a re-checkable dual instrument. **06 Self-correcting evidence:** pin sources and make corrupt witnesses fail. **07 Generative inheritance:** execute the same solver/checker on a second benchmark, without claiming superiority over ordinary reusable code. **08 Economic selection:** track a prospective physically relevant output (unserved MW), **without inventing customers, actual payments or financial value**.

## Decisive next experiment

Use qualified AC power flow, real accepted grid constraints, and N−1 events fixed *before* observing outcomes. Compare against a fully capable existing optimal-transmission-switching method with equal options and full implementation costs. No safety or deployment interpretation should precede independent domain review.

This is a **first public, falsifiable institutional technical demonstration**, not yet the hoped-for consequential breakthrough. It establishes a stricter standard for future missions: a surprising construction must be accompanied by the strongest incumbent, an independent bounded proof, adverse evidence, clear limits, and a genuinely fresh successor test before claiming compounding.

[Ω Singularity Direction — Issue #395](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/issues/395) · The existing [Blue Sky 064](../../campaign/blue-sky-064/CANDIDATES.md) candidates remain HOLD; this result does not silently replace them.
