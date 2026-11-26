# FRONTIER Ω IGNITION — Reduced-input inlet-state construction

Status: **constructed, not yet evaluated**  
Owner: MONTREAL.AI campaign branch  
Date frozen: 2026-11-25  
Parent evidence: PR #441 → #461; KTC physical residual at `campaign/omega-ktc-residual-20261103`

## Beneficiary decision

For one stable bubble-column operating point, report:

1. which of six gas-injection ports are active; and
2. total gas flow in litres per minute.

The proposed construction uses only ring 1 (nearest the inlets) at 1 kHz. That is 2,048 real-valued coordinates per frame instead of the full 65,536-coordinate, eight-ring, four-frequency acquisition: **1/32 of the recorded measurement coordinates**.

## Frozen construction

- Aggregate every contiguous operating-point acquisition into one mean measurement vector. Frames are not treated as independent decisions.
- Encode the active ports as six binary outputs, so unseen combinations can be composed from evidence about individual ports.
- Fit a deterministic standardized dual-ridge model (`alpha=1.0`) jointly for the six port indicators and total flow.
- Threshold each port output at `0.5`; clip flow to the public apparatus range, 1.0–6.5 L/min.
- Make exactly one prediction per held-out operating-point segment. There is no post-outcome tuning and no silent refusal.

This is a mission-specific construction, not a claim that a trained model is a new sensor or a deployable control system.

## Comparators retained

The same group split and ridge procedure will also be run on:

- all eight rings and all four frequencies (65,536 coordinates);
- a standardized nearest-neighbour conventional baseline on the reduced input; and
- a standardized nearest-neighbour conventional baseline on the full input.

The experiment separately records the strongest direct alternative: the commanded valve state plus Bronkhorst controller reading. Those records define the archive labels and therefore dominate any inference system when command state and controller flow are the accepted outcome. They do **not** independently establish actual per-port delivery after an obstruction, leak or valve fault.

## Source identity and rights boundary

- Hollenberg et al., *Reconstruction-Free EIT for Injection-Pattern Classification and Superficial Gas Velocity Regression as Proxies for Local Gas Holdup in Bubble Columns*, DOI `10.1021/acs.iecr.6c01116`.
- Public data: Zenodo `10.5281/zenodo.21773393`, version 1, published 2026-08-03.
- Public software comparator: Zenodo `10.5281/zenodo.21771095`, version 1.0.
- The article is CC BY 4.0. The data record is public; this branch uses the archive only for reproducible research and does not redistribute the 5.7 GB source archive.

## What this construction cannot establish

The public archive contains commanded inlet patterns and total-flow reference values, not independently measured per-port delivered flow during faults. It contains no operator action threshold, installed bill of materials, maintenance outcome, production loss, buyer acceptance, adoption or payment. Those remain explicit downstream gates even if the registered measurement test passes.

