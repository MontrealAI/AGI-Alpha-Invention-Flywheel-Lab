# Executed cross-domain mapping and measurement-grammar diagnostic

This contribution derives typed observation-partition facts from the actual published diffraction diagnostic and from exact circuit-model responses on the pinned ngspice example topology. All cases are exposed DEVELOPMENT. Circuit responses are model predictions, not measurements of physical specimens. The physical units, calibration assumptions, hypothesis population and measurement obligations remain distinct.

Run from repository root:

```bash
python research/consequential009/transfer/run_transfer.py
```

The extractor reads the actual two diffraction point sets from `alternatives/diffraction/RESULT.json`, reconstructs their exact integer autocorrelations and verifies that the uncoded observations agree while an added amplitude mask separates them. For the circuit it reads `analog/rc-meas-ac.sp`, invokes the candidate's actual passive-law exponent derivation, constructs a common-scale2 parameter witness and executes the exact Kirchhoff solver at five angular frequencies. Every modeled voltage ratio agrees between the two states; input admittance differs. The candidate's current-sense strategy is then compiled and executed on the same two-state obligation under a declared gain interval of `[0.99,1.01]` and absolute coordinate error `1e-8` in each observable's own unit. The new-observable uncertainty boxes are disjoint; identical voltage responses cannot separate the pair.

The research role supplies the source choices, extraction procedure and abstraction ontology: a latent-state pair, an old observation partition, a new measurement, a refined partition and an identification decision. Only the dimensionless relations of equality and separation are transferred. The inherited `mechanisms.mapping.discover` searches these typed graphs and discovers one relation-preserving correspondence. `check_mapping` validates it. This is bounded correspondence discovery inside a supplied ontology, not autonomous discovery across arbitrary fields or evidence of beyond-human foresight.

A raw physical-quantity mapping is separately attempted and rejected with `ROLE_KIND_OR_UNIT_MISMATCH`: detector intensity and mask transmission are not volts and amperes. In the circuit, voltage ratios have unit V/V and the normalized current observable is input admittance, A/V = S. A physical implementation would measure voltage in V and current in A with their own calibration; no numeric conversion between those measurements and diffraction intensity is authorized by the mapping.

The inherited mapping compiler cannot express this construction. Its allowed transforms are `protect`, `atomic_publish` and `compensate`; compiling the proposed `refine_observation_partition` recipe correctly produces `UNSUPPORTED_ROLE_TRANSFORM`. These operations change execution lifecycle obligations, not information acquired about a hidden physical state. The separate candidate grammar supplies `input_admittance` in addition to `voltage_ratio`; its actual `compile_plan` computes response rectangles, pair coverage and a selected measurement strategy. The proposed typed extension means: add a qualified observable, recompute the uncertainty-aware partition and require separation of the original unresolved pair. It does not permit changing the hidden-state cohort or weakening the endpoint.

The executed results are deliberately separated:

| Arm | Complete two-state model acceptance | Interpretation |
|---|---|---|
| Restricted voltage-only grammar | false | A verified information obstruction remains. |
| Transferred measurement-refinement hint enables the candidate's current observable | true | The added observable changes the actual executed acceptance result. |
| Equal-action ordinary compiler with no transfer hint | true, same selected action | A tie. The mapping does not establish a causal discovery advantage over a competent control given the same observable. |

The enabling contrast is availability of a different modeled observable. The same-source/no-hint control prevents attributing that contrast to the graph mapping itself. Passive-network symmetry, coded diffraction, and generic test-set design are established ideas. The model supplied the abstraction and authored the candidate modality; no novelty or autonomous invention claim follows from their successful execution.

`RESULT.json` retains all exact signatures, model derivation, graphs, correspondences, refusals, selected action ancestry, uncertainty policies, source SHA256 identities and measured resources. Source files were unchanged across the recorded execution. CPU0.010072747s was observed for the run, excluding import/tool/inference overhead; the parent300CPU-second reservation remains charged conservatively. No physical calibration, demand, money cost, earned financing or protected-confirmation evidence was produced here.
