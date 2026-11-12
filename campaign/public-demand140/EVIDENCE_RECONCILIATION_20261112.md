# Supplemental independent evidence-reconciliation criterion — 2026-11-12 UTC

**Source observed before this addendum:** PR #345 at `abf51b2471b713881b94b17ba5881b1593b90fce`; original frozen public-demand140 protocol `428bcd2f005b03ecc3f18b473db7230643d51dff` is **unchanged**. This is a new, prospective independent review criterion, not a retroactive alteration of T1–T9 or buyer/TRL claims. Research-only, no real user data, no native account, no external action.

## Actual defect and risk

`_read_evidence` accepts a validly registered requirement/version and system even if the control is inapplicable to that system **both before and after**. `assess` loops only over applicable system/requirements, so such a submitted evidence claim can disappear entirely from the public findings. This is visible in the existing synthetic T8 example (plant's `R2` assertion). The control correctly never awards compliance from it, but the audit receipt does not disclose that an assertion was excluded. An external user could mistake the displayed findings as complete evidence processing.

## Prospective fail-closed acceptance

1. Every **input evidence ID** must be accounted for by at least one finding's `evidence_id` or `historical_evidence_id`, **or** by a separate clearly labeled quarantined/unapplied evidence record; no evidence ID is silently dropped.
2. A quarantined record retains the source evidence ID, system, requirement and claimed version, explains `NO_APPLICABLE_REQUIREMENT_FOR_SYSTEM` or an equivalent precise reason, and **never** creates an approval/compliance claim.
3. Duplicate evidence IDs and cross-system or unknown references continue to fail closed. The existing T8 no-cross-system-authorization behavior remains.
4. Deterministic record ordering, independent receipt hash recomputation, external digest-anchor verification and all T1–T9 outcomes remain unchanged in meaning.
5. Report the count of input, referenced and quarantined evidence identities. Counts reconcile without counting a historical/current reference to the same ID twice. Use only synthetic fixtures, protect the original failed trace, and keep model/host dollars unknown.

**Decision rule:** Accept only if the source-matched exact-head regression passes and an independent review finds no hidden evidence claim. The output remains an unauthenticated synthetic *impact proposal*, not a compliance certificate, procurement eligibility, buyer acceptance, or a profit result. PR #345 stays draft until a separate adoption decision.
