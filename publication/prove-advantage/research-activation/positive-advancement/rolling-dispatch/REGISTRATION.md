# Frontier Ω · feasibility-preserving rolling dispatch replay

**Registered before building or running either new policy.** Retrospective, offline, public-data replay for MONTREAL.AI's internal research decision. There is no dispatch, commercial offer, participation or payment. The public normalized inputs represent historical operational requests under a declared planning model.

## Immutable inputs

- Repository revision `f0c8db6c7a1110dc614ab8a02c7a0bd5f79260de`, exported with Git archive. `production060/dispatch.py` SHA-256 `f1c817938a7e7482937ac2db4030c4f33473980434ad0bd030e9808cab573664`. Independent `production060/acceptance.py` SHA-256 `c7bf65ea6aba50f9f0efb2567b32b9d86dab01103b666396798428031dfb041c`.
- `production060/data/resources.json` SHA-256 `3a5a6ab0db42199a8f75e6ea0847f18cf8d38104fc84e29999be5d7a3acd7d07`. Eight source plants and 214 trucks; exact producer and acceptance rules determine eligible plants and truck assignments.
- [Real operational data for the Concrete Delivery Problem v1, CC BY 4.0](https://data.mendeley.com/datasets/b78bc94d95/1), cited by `production060/data/README.md`. Use the exact normalized repository bytes. The supplied travel and mix fields and known model limitations remain visible.
- Mechanism inspiration: [Decision-Focused Learning for Multistage Stochastic Programs v1](https://arxiv.org/abs/2611.34419v1). The authors' use of modeled continuation values to guide feasible actions motivates examining the constraints of the actual rolling dispatch search. Their power-grid code and learned model are outside this implementation.
- Use Python 3.12 and the repository-pinned OR-Tools `9.15.6755` and NumPy `2.5.4`, from public binary distributions held locally. Frozen wheel hashes identify the loaded dependencies.

## Cases and comparison

**Availability preflight:** ordinary and cold on `cdp_o15_03d` (SHA-256 `3614172577cccbf5576ff4db27b1ecf5903a5fb186218864f09431dc8531df0a`). This is the producer's published development case. Require both plans accepted by the exact independent replay and actual native CP-SAT window calls. If the pinned dependencies, baseline planning or source/acceptance checks fail, stop the comparative run. Preserve the specific result. The preflight cannot tune an arm.

**Held selection:** source-reported dynamic days with finite mapped travel and complete mix identifiers in the normalized data. Exclude the preflight day. Preserve all 31 eligible cases when reconstructing the selection rule. Sort each stratum by SHA-256 of UTF-8 `frontier-dfl-holdout-v1:<id>`; take the first three in each stratum. Hold these outcomes apart from policy construction. Prior repository evaluations of the same public corpus remain historical context.

| Stratum | Exact held day | Source bytes SHA-256 |
| --- | --- | --- |
| 15 orders | cdp_o15_09d | e6d4d2bfa29d90ff572c7013ec4a5519876c6088e41d9271edc3560043cd4348 |
| 15 orders | cdp_o15_29d | f31f809d1cc562a6b167e9b8220839d20c34ad8d575ec3d19347c3fa1f92f76a |
| 15 orders | cdp_o15_24d | 26bd5b2a8e974c261cae760dd7a2d575f33d073ddcbeb819bea966a3d3c0caa0 |
| 25+ orders | cdp_o25_09d | f1b033663b20615fe48fd9fb45e8bcc88ceccb0b01261fa073721290546e32a3 |
| 25+ orders | cdp_o25_27d | 7621f26ce403a18cf24d6e529227328accc31b25c76ab7a21733c231072ce635 |
| 25+ orders | cdp_o30_13d | 250a19c814d158d79e4a9c18b68cc11c42695f9f015acedec82d316d8923af8d |

Call the existing `production060.dispatch.rolling_schedule` for all arms and real release events. Freeze the same benchmark operating profile, seed 60, one CP-SAT worker, 3-load windows, 6-candidate base configuration and shared **2.5 seconds** per whole episode in the native budget mechanism. Preserve native fallback and commitment rules. A local ephemeral hook may change window order only. It gets the producer's window and current release-visible state, never upcoming orders or full-day aggregate features. Every within-order split sequence preserves its load index order. The independent checker determines acceptance.

| Arm | Mechanism |
| --- | --- |
| ordinary | Native target order, full all-plant constructor and CP-SAT, prior-plan hints as available. It already includes the same hints as the native warm and retained aliases. |
| cold | Native target order and all-plant CP-SAT with current incumbent hints, without prior-plan choice hints. |
| lead-time | Fixed conventional priority among ready loads, ascending target minus the shortest enabled-plant outbound time, then target, order ID and load index. Keep the native ordinary mode and solver budget. |
| continuation | Enumerate all at most six split-order-respecting permutations of the same 3-load window. Execute the unchanged all-plant best-fit builder for each order and select the first feasible order with the smallest projected complete window objective. Keep source target order on an exact tie. Run the unchanged ordinary CP-SAT using that permutation, the matching incumbent and the available prior-plan hints. This is bounded, deterministic lookahead over visible tasks. It involves no training, and uses the existing producer to evaluate continuation rather than a learned surrogate. |

The native solver's restricted route arcs follow task ordering. Reordering changes eligible search paths, as intended, while the independent physical and visibility constraints, available workload, input rights, solver budget and accepted objective are fixed. Candidate enumeration counts against the ordinary clock and against measured wall/CPU expense.

## Operating and stopping rules

- Before starting an arm, freeze the independent `production060.acceptance.make_contract` from the source inputs, arm mode and registered config. Verify saved artifacts in a separate process with the unchanged `production060.acceptance.verify`.
- Freeze two repeats per arm and held day. Start with the listed arm order and rotate by `(case_index + repeat_index) mod 4`. All use the same seed and wall budget, and run sequentially. Retain every result including native best-fit fallback or failed acceptance. A process malfunction, 30-second arm watchdog or bad source hash stops the whole comparison and preserves completed receipts. Do not substitute another day, tune the policies or continue to collect favorable cases.
- Primary objective is the checker's complete declared objective `120 × activated trucks + travel minutes + 10 × late minutes`. Also report truck count, travel, late minutes, late loads, quality and driver-review flags, independently accepted volume, actual complete measured wall/CPU per production and check, CP calls and actual branch solver statuses. The weights are benchmark score contributions. No financial valuation, revenues, contract effects, future arrivals, material qualification or operational deployment are inferred.
- **Advance only if** the 48 held plans all pass acceptance with actual native solver calls, and in **each repeat** the continuation arm beats the lowest available per-day control scores in aggregate, strictly improves at least four of six days, and has no additional driver-review flags or missing-mix obligations on any held day relative to the best-score control (ties choose fewer review flags). This control envelope is a conservative retrospective reference. Report timing tradeoffs separately and retain the strongest available operating alternative if the condition fails.
