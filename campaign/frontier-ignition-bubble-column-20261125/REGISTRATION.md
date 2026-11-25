# Prospective registration — reduced-input inlet-state consequence

Registration status: **frozen before held-out execution**  
Registration date: 2026-11-25  
Frozen construction commit: [`269f162a4fdfc9a0f1e16372675bdc8df6d68edd`](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/269f162a4fdfc9a0f1e16372675bdc8df6d68edd)

## Question

Can the frozen one-ring, one-frequency construction preserve a beneficiary-relevant operating-point decision—active inlet set plus total gas flow—while reading 1/32 of the coordinates used by the full recorded EIT arrangement?

## Public source

- Data DOI: `10.5281/zenodo.21773393`, version 1, published 2026-08-03.
- Expected archive: `measurement_data_bubbly_flow.zip`, 5.7 GB, published MD5 `f53345e798200524b8808455b5b55792`.
- The archive records 17 inlet configurations, twelve coarse flow settings from 1.0 to 6.5 L/min, eight 32-electrode rings and four frequencies.
- Source identities, downloaded archive hashes and every `.npy` SHA-256 will be retained with the outcome.

## Frozen split

All partitions are grouped into contiguous acquisition segments before any fitting or scoring. Frames are never counted as separate decisions.

- Held-out inlet configurations: `S_3`, `S_2_6`, `S_2_3_5`.
- Held-out total flows: `1.5`, `3.5`, `5.5` L/min.
- Training groups exclude the union of those inlet configurations and flows.
- Test groups are the intersection: a held-out inlet configuration at a held-out flow.

This forces both compositional inlet-pattern generalization and interpolation to unseen flow settings in the same operating-point decision.

## Frozen systems

1. **Primary:** standardized dual ridge, ring 1 at 1 kHz, 2,048 coordinates.
2. **Full-input direct comparator:** the identical ridge procedure, all rings and frequencies, 65,536 coordinates.
3. **Reduced conventional comparator:** standardized nearest neighbour, ring 1 at 1 kHz.
4. **Full conventional comparator:** standardized nearest neighbour, all rings and frequencies.
5. **Strongest direct alternative:** commanded valve state plus Bronkhorst total-flow reference. It defines the labels and is recorded as exact for the archived accepted outcome; it is not scored as an inference model.

No hyperparameter, feature, threshold, split or comparator may be changed after this registration. A later improvement must be a new named registration and must retain this result.

## One decision and acceptance rule

For every held-out operating-point segment:

- the predicted active-port set must be exactly correct;
- absolute total-flow error must be **strictly less than 0.25 L/min**;
- refusal counts as failure.

The registered test passes only if the primary passes every held-out group and records at least as many joint decisions as the full-input ridge comparator. Coordinate-count reduction is 65,536 / 2,048 = **32×**; storage, acquisition-time, electronics, energy and installed-cost reductions are not inferred from that ratio.

## Interpretation gates

- **Pass:** establishes retrospective reduced-coordinate sufficiency on this public apparatus campaign only.
- **Fail:** falsifies this frozen reduced-input construction for the registered decision.
- Neither result establishes independent per-port delivered flow, an obstruction/leak/valve fault, live control, operator benefit, installed savings, production benefit, buyer acceptance, adoption, payment or complete lifecycle cost.
- The direct valve/controller alternative wins whenever commanded valve state and controller total flow are the accepted outcome.
- No public flagship or breakthrough claim is admitted unless the registered consequence passes **and** a residual remains against that direct alternative. This archive alone cannot establish the residual.

## Resource and cost boundary

Execution is CPU-only on an existing public GitHub-hosted runner with NumPy. No paid model, API, GPU, purchase, credential, private input or external participant is authorized. Public runner accounting, network egress, instrumentation cost, installation cost and full lifecycle cost are unknown and will not be represented as zero.

