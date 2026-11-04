# Governance091 — policy rollback must not resurrect stale approval

**Separate prospective review cycle, frozen before adversarial implementation or remedy.** Source base: Governance090 research PR #214 head `96466572049bd67a4c1fe0250d9d59e9c5f7d0e6`, independently observed original eight tests and all twelve workflow groups passing. This is not a change to the completed Governance090 protocol, not a security certification, not a new customer, and not a native financial experiment.

## Consequential failure hypothesis

The current `ImpactRegistry.evaluate` selects the last review for the current requirement **content digest**. If a policy changes from wording A to B and is then restored to A, the earlier A approval might be selected again. The same issue could arise when an obligation is retired and reactivated with identical text. In real governance a later document state is not proof that historic evidence was independently re-reviewed. The correct witness must bind each approval to a *continuous, uninterrupted validity epoch* since the latest explicit change, not just the current digest. This is distinct from detecting text differences, user authentication or interpreting legal obligations.

## Finite frozen tests and interpretation

Cases are fixed before any source edit, with no seed search. Exercise `ImpactRegistry` against authored synthetic public text; actual government policy semantics are **not** inferred or verified.

* **R1:** initial approved A; update A→B; restore B→A. Initial approval **must remain UNDETERMINED**, `all_controls_met = false`.
* **R2:** initial approved active requirement; retire; reactivate identical original text. Old approval **must remain UNDETERMINED**.
* **R3:** no-op repeated requirement update with no changed requirement: existing accepted review **must remain MET**; no new update journal event.
* **R4:** after a reversion, a **new** review event may approve the current requirement; the prior original review is never reused; independent pinned-tip verification succeeds.
* **R5:** policy change limited to R1 does not destroy an unrelated R3 approval, and an explicit independent ordinary event replay oracle yields the same latest current-epoch findings.
* **R6:** no available old approval ever upgrades `qualified_compliance` (always false). Invalid/missing independent tip cannot authenticate a modified chain.

**Before fix:** run the fixed tests on original exact source and record genuine red cases. Do not alter frozen case requirements, reclassify failures or delete logs. **Prospective fix:** on a separate source head, select reviews only when newer than the latest update event that changed their requirement, preserving externally pinned hash-chain validation and no-op continuity. Keep the existing review/event format if possible, so old records are not rewritten. A competent ordinary forward replay that resets affected requirement reviews at update provides a strong correctness control. Confirm all six cases plus original eight Governance090 tests on an exact hosted source. Report every failure and distinct head; do not claim a new holdout or broader statistical reliability.

## Exit and authority

Implementation is restricted to the research-only `research/governance090/impact.py`, separate Governance091 test and workflow/evidence. It neither changes the author's completed Governance090 evidence nor the canonical `JournalAccount`, native-account source, source/version guard, release, protected financial authority or any original signer. PR targets the existing research branch for owner integration review, **not main**. Before any release require normal source-matched integration and downloaded actual release proof; never merge experimental review evidence wholesale. The public challenge is a real need but this tool has no demonstrated TRL5, contract, authenticated identity, legal interpretation, data rights, complete costs or buyer superiority. **NO BID / NO DEPLOY** and **US$3B NOT ACHIEVED** remain unchanged.

Stop after these six fixed tests, original eight regressions, source review and hosted check; no additional tuned examples under this registration. Record a compact tried → outcome → why → next lesson. Actual whole-campaign model/host billing unknown.
