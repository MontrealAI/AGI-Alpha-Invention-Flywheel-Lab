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

## Continuous opt-in frontier release sensor

To monitor permitted public, open-source release metadata, create a JSON configuration outside the repository:

    {
      "schema": "frontier-omega/github-release-sources/v1",
      "repositories": [
        {"repository":"ggml-org/llama.cpp","tags":["coding","local-inference"]},
        {"repository":"ollama/ollama","tags":["local-inference"]}
      ]
    }

Then invoke (with a private inventory already seeded from PR #422):

    python3 -m frontier_omega.releases --root ./frontier-omega-private --config release-sources.json --once

For continuous polling, omit --once; the default polling interval is one hour, adjustable with --poll-seconds between 300 and 86400 seconds. The process must remain running under a suitable owner-controlled service manager. No process or scheduled paid runner is left running by the implementation.

Only exact configured owner/repository identifiers are permitted. URLs are constructed for api.github.com and redirects are refused. Upstream responses are bounded; source errors create no capability claim. Stable release identities are deduplicated across days, preserving the original observation date, and create only the preexisting inventory's INVESTIGATE_ONLY matching triggers.

A GitHub release announcement is *never* a benchmark: the stored availability status is REPORTED. Successful agent performance, historical reproducibility, customer demand, costs and payment must be tested separately. Polling makes only explicit, authorized public GET requests and has no financial authority.

**Single-writer operation:** When using continuous release sensing, run the release-radar watch as the sole process for that private inventory. It ingests local inbox records and polls the configured public release endpoints within the same writer lease. Do not start the original inbox-only watch simultaneously on the same private directory.
