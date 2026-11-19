# Corrective execution receipt — 2026-11-19

**Original preregistration is immutable:** `c508a2b9b0405329161795abfb1c5079b59d0422`. The four EVM cases, seven Python checks, source pins, number of orders and expected outcomes remain unchanged.

## First executing head (failed owner-suite composition)

- Head `e16254e88f62f8195297cede736250dfc9ef5b76`.
- Dedicated [push workflow 44637673824](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44637673824) and [PR workflow 44637953176](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/44637953176) **SUCCEEDED**, both Python and local EVM jobs.
- **Original-owner foundry workflow 44637953194 FAILED** in `discovery-evidence` (31 checks successful; one `test_microfee_precision` failed before execution) with exact `ModuleNotFoundError: No module named 'products'`. Owner discovery runs from `products/frontier_mechanism_foundry`, whereas independent dedicated runner had invoked it from repository root. The independent `evm-contract` job in that same failed workflow succeeded.
- This was not a failure of the registered settlement arithmetic, but **is a real full-workflow source-composition failure** and stays FAILED. No retroactive pass or hidden retest.

## Prospective minimal repair

Commit `52ad8cf732d0fdff2796b0251e5591580f3f2910` alters **only the independent test's import resolution**. It accepts package-style import from root and exact same file's local sibling import in the owner's working-directory discovery; it catches only a missing `products` root package and does not suppress missing other modules, relax assertions, modify source owners or change the registered cases.

New exact-head qualifications must be inspected separately; no new revenue, live payments, protected branch merge, native-account transition or user authority is inferred. Existing owner PR486, PR484 and published Connected014 remain unchanged. Historical source failures and account liabilities are untouched.

**Decision remains:** conditional microfee arithmetic, NO DEPLOY / NO BID, potential mechanism reconsideration only after complete accepted buyer/outcome/cost proof and authorized official token semantics.
