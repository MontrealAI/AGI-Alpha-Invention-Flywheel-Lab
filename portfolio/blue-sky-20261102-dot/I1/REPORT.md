# I1: optical interface construction — bounded result

**Verdict:** working algebraic K1 and distinct K2 in a declared reciprocal optical model, independently replayed. No qualified physical instrument, commercial residual, improved invention method, or profit established.

Public preregistration: commit `97df4404b4f51e5043657f66d4a1eb8430883e65`, preceding model execution. Constructor `c1f0b7688e81e11850a319d228bb3afde36dad6c2e39b4e6f2c36b2207b66db2`. Three materially different interface candidates and their selection reasons are in PREREG.md.

## Actual construction and result

K1 reconstructs a reciprocal fibre's transmission operator up to independent row signs using two designed-reflector responses. Its phase-conjugated commands deliver the maximum attainable target intensity. K2 uses a third, coupled reflector to resolve relative signs and reconstruct a complex field, a measurement function different from K1's energy delivery. Scope validation prevents using intensity-only K1 as an authorized coherent imager.

The registered driver executed 189 finite cases; 27 noiseless cases all passed. Worst noiseless K2 relative field error was 3.2762e-14; minimum achieved/optimal target intensity was 0.9999999999999993. An independent verifier using separately generated matrices replayed 27/27, checked generalized eigenvalues, analytic gauge counterexamples and six invalid-input rejections. These are model/code checks, not a physical sampling population.

| Authored challenge | Returned /27 | Largest K2 relative error among returns |
|---|---:|---:|
| No noise, no drift |27|3.2762e-14|
| Relative noise 1e-6 |27|4.7535e-5|
| Relative noise 1e-4 |27|0.006335|
| Relative noise 0.01 |2|0.016567|
| Within-session drift 1e-6 |27|1.7611e-5|
| Within-session drift 0.001 |27|0.020910|
| Within-session drift 0.05 |0|Not applicable|

“Returned” means the implementation passed its consistency guards, **not** that a physical accuracy requirement was met. No noisy-data accuracy promise was registered. Abstentions stay in the denominator.

Full results: `results-registered-001/results.json` SHA256 `458c4d9c5771b11c4d7cba6ffb57ecd0e80f34dd1825b6fada6380b0b7b57cd2`. Summary SHA256 `2c6900b0cac6be416fad622fb29528b6eb44ffc8fbd7fcc27b15714c52213eeb`.

## What the strongest controls change

- Fresh and retained ordinary construction match exactly (operator gap 0); classical algebra already solves the stated model. K1 costs 2n complex probe columns; K2 adds n; complete lineage and fresh direct construction both cost 3n. No fictitious total saving.
- One reflector leaves an orthogonal gauge; two leave independent row signs; a disconnected third reflector leaves componentwise signs. Those are information limitations, not slow reasoning.
- A broken-reciprocity scaling error can produce residual 1.95e-16. Small residual alone cannot qualify one-way field magnitude.
- Before confirmation, independent static review found and repaired a NaN acceptance bypass. Old and corrected source identities remain recorded.
- Registered stale-calibration and wrong-reflector controls were absent from the first driver. This omission was disclosed, their supplemental source was publicly frozen at `a64eaec35f147779545c718fd74f6a628d1aedfb`, and all three registered seed cases then executed without main-code changes. Stale calibration gives relative field errors 1.411–1.673; fresh recalibration reduces these to <=4.699e-15. A 1.21x error in assumed reflector amplitude produces **9.09% field bias** while residual stays <=1.226e-14. Actual reflector norms remain <=0.847, so passivity does not expose this wrong calibration. Supplemental result SHA256 `5d67270a0def1d8d858024d359f996a532f6d8bdb66ad6b7b45d3760f417ac1f`.

## Physical and business decision

The hard unbuilt means is **selectable, calibrated, coupled reflectors at one wavelength without changing the optical path or obstructing imaging**. Mathematical passivity does not establish this hardware. The predecessor's realizable spectral-stack proposal instead needs dispersion correction; importing its measured fibre support does not validate our simplification.

The current artifact is useful for testing identifiability, scope extension and calibration failure. It is not yet the missing industrial instrument. Industrial inspection access is a possible beneficiary; conventional endoscopes, coherent bundles, distal calibration and existing reflector methods remain complete outside options. No evidence yet establishes cheaper qualified delivery, customer willingness to pay, rights, fabrication yield, calibration throughput or lifecycle cost. Hence no native account, assumed sales or capital-profit trajectory was fabricated. A technical tie does not prove commercial failure, but it supplies no commercial success either.

## Resources and next discriminating work

Driver wall time 0.490 s on included local CPU; no new cash spend or physical actions. Full agent development/verification time, included-resource economic billing, hardware manufacture, qualification, deployment, maintenance and human specialist effort are not measured monetary costs. They cannot be silently treated as zero.

Negative controls are now complete. The next useful step is a realizable reflector/dispersion construction or independent measured multi-reflector dataset—not further ideal-matrix tuning. Without that, do not advance this route to instrument sale or scale forecasts. The portfolio can retain the compact inverse instrument and ambiguity witnesses while allocating effort to a stronger physical/commercial route.
