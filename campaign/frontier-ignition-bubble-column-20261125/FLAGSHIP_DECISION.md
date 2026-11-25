# FRONTIER Ω IGNITION — Flagship review decision

Review date: **2026-11-25**  
Campaign PR: [#598](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/598)  
Registered execution: [run 45643876317](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45643876317)  
Status: **FLAGSHIP NOT ADMITTED**

## What was inspected

The campaign continued PR #441 through its qualified mission-specific successor and the physical residual preserved in `campaign/omega-ktc-residual-20261103`.

A frozen construction attempted to decide, for one bubble-column operating point:

1. the exact active set of six possible gas-injection ports; and
2. total gas flow within 0.25 L/min.

The primary construction used only the first electrode ring at 1 kHz: 2,048 coordinates rather than the full 65,536-coordinate, eight-ring, four-frequency recording. The prospective registration withheld three inlet patterns (`S_3`, `S_2_6`, `S_2_3_5`) and three flow settings (1.5, 3.5 and 5.5 L/min) together, producing 27 held-out operating-point segments after training on 378 groups.

## Exact verdict

**FAIL — the reduced-input construction did not preserve every registered operating-point decision.**

| System | Exact ports | Flow error < 0.25 L/min | Complete joint decisions | Registered pass |
|---|---:|---:|---:|---|
| One-ring/1 kHz dual ridge | 7/27 | 4/27 | **1/27** | no |
| Full-input dual ridge | 10/27 | 5/27 | **3/27** | no |
| One-ring/1 kHz nearest neighbour | 0/27 | 0/27 | **0/27** | no |
| Full-input nearest neighbour | 0/27 | 0/27 | **0/27** | no |
| Commanded valve state + Bronkhorst controller | defines archive labels | defines archive label | direct record | wins for the archived outcome |

The primary construction's largest absolute flow error was **3.539528 L/min**. It did better than the reduced nearest-neighbour baseline, but that does not rescue a 1/27 complete-decision result. The full-input ridge also failed 24/27 complete decisions. No coordinate-reduction, operational-benefit or economic claim is admitted.

## Source and reproduction identity

- Dataset: Hollenberg et al., Zenodo [10.5281/zenodo.21773393](https://doi.org/10.5281/zenodo.21773393), version 1.
- Retrieved archive: `measurement_data_bubbly_flow.zip`, **5,707,799,262 bytes**.
- Published and observed MD5: `f53345e798200524b8808455b5b55792`.
- Observed SHA-256: `5cccd335774df3392e55361e7264a7fa29043f3f408c42bee27cedf78b6a87f9`.
- Runtime: Linux x64, Python 3.11, NumPy 2.1.3, CPU-only.
- Frozen construction: [commit 269f162](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/269f162a4fdfc9a0f1e16372675bdc8df6d68edd).
- Prospective registration: [commit 1b1fa4e](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/1b1fa4ebe99f87e1a55baac6e512ef1151fc3981).
- Exact per-group results and every `.npy` SHA-256: [results.json](./outcome/results.json).
- Human-readable result: [RESULTS.md](./outcome/RESULTS.md).

Source retrieval and unpacking took about 29 minutes in the recorded workflow; registered scoring then completed in about six seconds. GitHub-hosted runner accounting, network egress, acquisition electronics, installation, maintenance, operator effort and full lifecycle monetary cost remain unknown and are not represented as zero.

## Why no public flagship showcase was built

The archive's accepted outcome is commanded valve state plus controller-reported total flow. The direct records already supply that outcome exactly. The archive does not independently measure actual gas delivered by each port during an obstruction, leak or valve failure. It therefore cannot establish the consequential residual that would justify inference: detecting a mismatch between command and physical delivery soon enough to change an operator decision.

A polished showcase would conceal this failed causal and alternative comparison. The reviewable PR and this non-admission record are the authorized public result.

## Exact decision for Vincent

Choose one of two paths:

1. **Authorize a beneficiary-owned physical fault pilot.** A willing bubble-column or bioprocess operator must first define the action, false-alarm tolerance and loss avoided. The pilot must independently measure per-port delivered flow while introducing safe, approved obstruction/leak/valve-fault cases; compare reduced EIT, the strongest full EIT method, valve/controller telemetry and ordinary inspection; and record installed equipment, calibration, labour, maintenance, downtime and lifecycle cost. This requires an external participant, site authority, likely equipment/instrumentation and a new prospective protocol. None was authorized here.
2. **Close this sensing lane as negative and pivot the limited IGNITION demonstration.** Preserve PR #598 as the result and select a different Blue Sky candidate with a public source that already contains a real beneficiary consequence and a complete incumbent comparison.

Until path 1 is explicitly authorized and supplied, the scientifically correct campaign status is: **construction executed, registered test failed, flagship withheld**. No invitation, purchase, deployment, merge, external announcement, adoption or payment occurred.
