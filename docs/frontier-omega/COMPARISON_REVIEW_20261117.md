# FRONTIER Ω comparison integrity — preregistered review, 17 Nov 2026

**Frozen base:** `580c37a4ccc9a2e96e4814452eb8334b2a28d96b` (17/17 qualified dependent PR #434). **Original integration owner:** PR #429. This branch is a nonfinancial dependent review; it cannot import research proposals, change original owner files, authorize financial activity, or merge itself into main.

## Defect hypothesis

The canonical `Reservoir.compare()` matches trial terms/acceptance/protocol but not complete fixed quoted price or evidence scope. A price-only increase may therefore create a *reported crossing* even where unchanged production loses money. Both canonical `Reservoir.compare()` and `Inventory._comparison()` appear to permit trial records dated **before their referenced capability was observed**. Historical old-method replays executed *after* a new capability's release are valid: do **not** reject merely because the old-method replay happens later.

## Frozen tests before code changes

1. Core: price uplift alone must not be a fixed-price matched crossing.
2. Core: altered trial evidence scope must not be a matched crossing.
3. Core: current trial dated before its capability observation must not be matched.
4. Inventory: current trial dated before observation must produce no comparison.
5. Inventory: old trial dated before old observation must produce no comparison.
6. Existing unchanged valid same-price, same-scope, post-observation control cases continue to pass.

**Expected first attempt:** tests 1–5 fail at frozen base, 6 and existing tests pass. Do not relabel that failure. **Repair scope:** only the two comparison-selection functions; preserve immutable invalid old records as evidence, and refuse to use them for a positive reported crossing. No price change, buyer, collection or authorization is inferred from JSON. Existing failure traces stay historical failures.

**Qualification:** source-matched `test_frontier_omega.py`, `test_frontier_omega_inventory.py` and applicable GitHub workflows; preserve test-first run IDs. Verify exact source head before any owner adoption. Release/downloaded byte gates and original Account/JournalAccount owner custody remain independent.

**Decision rule:** if strict matched controls fail, HOLD and correct on same registered cases; no seed searching, hidden reruns, weakened tests or release claim. Findings and evidence go to PR #429 owner.
