# FRONTIER Ω — Executable 35-day capability replay

This is an **executed bounded-task comparator** for the persistent opportunity reservoir in PR #422. It is not a competing inventory, a new financial ledger, or proof that any model created demand.

## Run the benchmark

From the repository root:

    python3 -m frontier_omega.executable --demo
    python3 -m unittest discover -s tests -p 'test_frontier_omega_executable.py' -v

The synthetic demonstration executes three submitted declarative instruments on the same three finite held-out cases using the existing HARNESS bounded evaluator. An illustrative old method fails a capacity limit; a newer method passes; **a competent conventional min method also passed before the historical cutoff**. The output is correctly classified as HISTORICALLY_FEASIBLE_VIA_STRONG_ALTERNATIVE, not a novel commercial crossing.

No actual model is invoked in this demonstration. Method vintages, source identities and cost estimates are declared scenario inputs, not independently authenticated production history.

## Conduct a source-matched comparison

For each frozen problem, provide a private suite JSON object with exactly: schema = frontier-omega/heldout-suite/v1, problem_id, historical_cutoff, as_of, inputs (declared string names), cases (input and expected output objects), min_pass_bps (1..10000), max_operations (1..100000), and acceptance_text_sha256 (SHA-256 of the canonical JSON representation of the problem's frozen acceptance string).

Provide three JSON method records, each with schema = frontier-omega/declarative-method/v1, role (HISTORICAL_FRONTIER, CURRENT_FRONTIER, STRONG_ALTERNATIVE), id, available_at, source_sha256, instrument (a bounded evaluator JSON spec), complete_unit_cost_microUSD (nonnegative integer or null), and cost_basis (DECLARED_SCENARIO or UNKNOWN).

Invoke:

    python3 -m frontier_omega.executable --suite suite.json --historical old.json --current new.json --alternative incumbent.json --problem frozen-problem.json --out receipt.json

The optional --problem binds the test suite to the immutable acceptance text of the registered dossier. Without it, the receipt remains a separate local experiment.

Every arm uses the same held-out cases, declared inputs, acceptance threshold and operation limit. The receipt reports source, artifact, suite and case hashes, exact observed pass rates, incumbent comparisons and scopes. Any missing unit cost remains UNKNOWN rather than becoming zero.

## Hard evidence boundary

A passing finite task test does not establish model-generated authorship, model weights, the true date a model became available, general reliability, customer willingness to pay, complete commercial costs, payment collection or economic advantage. All three method availability dates remain externally supplied claims. A strong historical alternative defeating novelty is recorded even if the newer method succeeds.

No untrusted Python or shell from a model is executed. The source-pinned, bounded JSON evaluator refuses dynamic imports and unrestricted operations. The comparison does not create customers, authorize production or spending, change native ALPHA accounting or issue payment instructions.

A genuine five-week commercial crossing requires independently verified historical/current availability, controlled real tasks, competent competing methods, real demand and complete economic measurements. This module is a **sensor and verification dependency**, not a self-financing enterprise.
