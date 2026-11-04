# Registered native-configuration 089 — executed red result

**Execution date:** 4 November 2026 UTC. **Protocol committed before the test and before this execution** at `c078ac62ef7b13b3e558407d620d28c7d165bc33`. Source-parent: `68eef714f62fab64b04131377afd6ae2047358f9`. Tested exact-head: `176040a4bcb0514324bcc5724ba0148f65f1b3bc`.

Actual GitHub Actions execution: [workflow 41759852505, job 126344696257](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41759852505/job/126344696257). Standard CPython 3.12, pinned project requirements; 3 methods ran in **12.577 seconds**. **FAILED: 3 assertion failures, 0 errors.** Historical and red-first outcomes must remain failed; no retrospective pass.

| Frozen test | Native account provenance | Result of required V4 registered-config rejection |
| --- | --- | --- |
| 01: legitimate USD200,000 opening, report label reset to USD100,000 | Real source-matched native ledger exported and independently replayed; `ledger.config.opening` positively checked | **FAILED** — public V4 audit did not raise |
| 02: legitimate USD100,000 opening, USD1 working reserve instead of zero | Real source-matched native ledger exported and independently replayed; `ledger.config.working` positively checked | **FAILED** — public V4 audit did not raise |
| 03: alternate native contract | Real source-matched native ledger exported and independently replayed; `ledger.config.contract` positively checked | **FAILED** — public V4 audit did not raise |

The tests use existing V4 source, service/acceptance, actual `JournalAccount`, signed native actions and canonical `audit_journal` under a fixed small *engineering* market. These are **not** fabricated success/failed-economic worlds or genuine customer contracts. The observed bug is narrowly scoped: self-consistent but **wrongly registered** native account configurations can pass the V4 public operating audit if summary/report metadata are consistent. It does not show a forged signature, a changed historical private account, an actual accounting discrepancy or a completed P0 migration.

**Required owner-controlled prospective repair:** In `mechanism_harness/cart_native.py:audit`, independently require `exp['ledger']['config']` to bind the registered `OPENING`, `working=0`, and `CONTRACT`, before accepting the canonical journal as evidence for this experiment. Keep `audit_journal`, causal cost reconstructors, SOURCE/CONTRACT/report checks, private live-resume guard and original source authority intact. Re-run the same registered tests without case changes, then independent source-matched full suite and normal release qualification. Any new passing head is new evidence, not a revision of this failure.

**Acceptance matrix:** protocol freeze **ACHIEVED**; disjoint implementation and GitHub publication **ACHIEVED**; native-account execution and independent journal replay **ACHIEVED**; **three registered-config rejection checks FAILED**; canonical repair **BLOCKED ON OWNER SOURCE INTEGRATION**; original-account nonempty legacy-state migration **NOT TESTED**; qualified full release/downloaded operation **NOT ACHIEVED**; external customer value, paid collections, complete lifecycle costs, strong human alternatives, $3B trailing profit **NOT ESTABLISHED**.

**Safety/ownership:** No output directory, simulation signing key or recovery file was published. No new model API/billing, outreach, external transaction, production deployment, original-account modification, liability reset, forged provenance or change to historical failed evidence. The V4 owner remains the one source/financial integrator. This draft is an independent regression/handoff, not a replacement audit authority.
