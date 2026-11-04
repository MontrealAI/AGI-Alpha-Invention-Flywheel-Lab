# Physical battery 100: measured-data construction

## Selected consequential outcome

Construct a usable cell-characterization and capacity-retention decision artifact from independently measured physical cycling, before proposing any commercial operation. This is a new additive study, not a rewrite of numerical battery PR84/147 or native GENESIS accounts. No physical equipment is operated.

Three alternatives were compared before this acquisition probe:

1. **Battery characterization and retention:** Microsoft/LF Energy released measured end-, middle- and multi-tab cell cycling in March 2026. Source: https://lfenergy.org/lf-energys-battery-data-alliance-and-microsoft-release-standardized-battery-dataset-to-accelerate-storage-interoperability/ . This offers a near-term independently checkable technical artifact, subject to actual schema and experiment compatibility. The separate October-2026 field-data survey (https://arxiv.org/abs/2610.05811) exposes other possible releases but does not supply capacity ground truth automatically. The FlashBattery AGV aggregate was rejected for capacity prediction because its fields do not include capacity labels.
2. **Wind-turbine early fault detection:** Fraunhofer CARE provides actual operating measurements, 44 anomaly frames and 51 normal series: https://arxiv.org/abs/2404.10320 and https://zenodo.org/records/10958774 . Its normal-behaviour and autoencoder controls are direct alternatives. More extensive raw acquisition and fault-window validation are needed; released statistics include documented quality defects. This remains a fallback if battery labels are insufficient, not a synthetic substitute.
3. **Sparse industrial CT reconstruction:** measured walnut projections and existing ASTRA FDK/iterative reconstruction: https://github.com/cicwi/WalnutReconstructionCodes . This has real projections and an established full-data reference, but substantial data/compute needs and strong existing reconstruction software. Do not call routine reconstruction a new enabling advantage.

## Stage 0 frozen before acquisition

- Base main: `2874984e93045feed649d8ff13481369402b8388`.
- Upstream BDF snapshot: `754304f6191b06a78a762636f211e98fcf3dc305`.
- Read exactly one **development cell**, manufacturer1 end-tab A0067, 1000x1C at 35 C. Publisher Git LFS declares 8,346,123 bytes, SHA256 `2f9b6c457da76b95b4780c703f90280210f57b818ac677ff0c9ff4968bba49c3`.
- Check exact source identity, then report schema, row count, numeric ranges and two development rows. Do not execute upstream code, fit models, read other cell outputs or claim observed capacity until its measurement fields and protocol have been inspected.
- Other cells, manufacturers and tab layouts are reserved for separately frozen validation. A0067 can never count as untouched evaluation.
- Actual data are **controlled laboratory cycling**, not field operation, actual customer acceptance, physical safety qualification, novel discovery, funding or profit.
- Payload license verified in the upstream `Microsoft/LICENSE`: CDLA-Permissive-2.0, which permits analysis and results. Do not republish raw payloads; reference exact upstream URL/hash and retrieval.
- Acquisition success establishes usable measured inputs only. Stop model design if the fields do not support the intended outcome. Preserve acquisition failure rather than replace measurements with simulation.

## Next decision, contingent on observed schema

If physical discharge-capacity and cycle measurements exist, preregister a concrete capacity-retention or design-screening deliverable and comparable manufacturer/protocol groups. Compare ordinary integration/curve fitting, competent BatteryML/PyProBE-style conventional analysis, and modern CPU-capable prediction. Time splits and disjoint-cell/manufacturer checks must prevent leakage. Report actual intervention, measured execution and complete-cost unknowns. Do not infer causality of tab design from unmatched cells or protocols; three replicates cannot support universal superiority.

The frontier-AI versus 100%-human productivity benchmark requires separately grounded full-workflow costs and human effort. Numerical accuracy alone cannot establish it. Deployment, paid demand, customer contracts, validation against future cells, engineering/billing costs and profit remain open.

Run `python -m unittest research.battery_physical100.test_probe -v`, then `python -m research.battery_physical100.probe` using standard Python 3.12. The public CPU workflow performs this exact one-source probe. No ledger, source inventory, native account, private input, paid API, external outreach, purchase, merge or release is changed.
