# EIT40 operator integrity — frozen prospective regression (2026-11-07)

## Source and authority
Parent exact research commit `47ad3808bf6a3b5d2e619b29bb27a574572fd5c9`, draft PR #292, stacked on independent owner PR #262. This is **an isolated engineering-integrity test/repair**, not a rerun or reinterpretation of the frozen development and retrospective EIT40 experiment, not a new physical measurement and not a commercial claim. No modification to main, owner #262, private accounts or their source authority.

## Falsification target
The existing frozen `Plan` dataclass exposes mutable NumPy `operator` and `basis` fields. `Plan.predict` checks the basis against a stored hash but does **not** check whether its operator still equals the one compiled by `compile_plan`. After compiling from unchanged calibration and geometry, changing an unacquired-column coefficient in `plan.operator` must be rejected *before* the program displays any reconstructed target. Inherited code is predicted to **FAIL** this test (silently emit a changed reconstruction). A separately locked selected-column tuple must also refuse unrecognized changes, rather than silently binding measurements to another acquisition plan.

## Fixed acceptance / stopping
1. Before changing the implementation, add one test proving in-place operator corruption with the exact compiled plan and otherwise matching current/source. Add a second test proving selected-pattern mutation. Preserve the initial failed test result as failed.
2. Repair the owned EIT40 `Plan` only. Pin SHA-256 of the compiled operator and of the selected-column index encoding within the frozen plan; reject with explicit source-integrity errors before producing any prediction. Include the two pins in `plan_receipt`. Do not weaken any existing source, geometry, finance or workflow guard.
3. Verify all earlier 11 EIT40 synthetic regressions plus two new ones under Python normal and `-O` on literal exact head. A reviewer should distinguish rerun engineering reproduction from new physical confirmation; the previously frozen failed 19/21 residual screen and favorable retrospective PCA control are **unchanged**, not retested as a new discovery.
4. Keep the original parent experiment's fully exposed results, historical failed CI, PR #262 owner boundary and NO DEPLOY verdict. Do not merge this repair PR wholesale into main. No paid services, outreach, physical testing, real commerce, key access, new business account or release claim.

Outcome after the first red test is fixed: repair the two integrity defects, then stop; do not tune any physical scientific parameters or report additional economic observations.
