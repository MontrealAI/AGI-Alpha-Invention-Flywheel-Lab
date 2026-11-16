# P0-184 — independent historical-audit evidence-store rebinding challenge

Frozen prospective adversarial protocol, 2026-11-15 UTC.

**Parent source:** `ced6c1cb004887dcdafaea59a2976020be649f8e` (financial owner's draft PR #40). **Branch:** `review/p0-historical-evidence-store184-20261115`. **Ownership:** independent reviewer. Test-only, additive, no financial-authority, account, journal, production, publication, or source changes. This branch is **not** to be merged into main while based on owner draft.

## Threat and fixed test

The existing module-level `connected_enterprise.upgrades._HISTORICAL_AUDITS` caches a historical verifier's success by ticket, manifest, verifier inventory and historical root. A v2 CAS ticket may contain a signed outer `prior_record` whose recursively referenced historical ticket requires additional immutable CAS objects. Reusing an earlier success from evidence directory A when caller explicitly chooses B, where B has the outer hashes but lacks an inner required CAS object, could bypass the independent historical audit's recursive verification. The outer ticket may still resolve: this alone does **not** prove its nested history is present.

1. Construct an in-memory synthetic prior v2 ticket with a referenced immutable nested record and a separate v2 outer ticket embedding the prior ticket in `prior_record.source_transitions`; use no actual signer, account or key.
2. Publish create-only identical outer CAS objects to *two* trusted temporary directories A and B; publish the nested inner CAS objects only in A. The old inner ticket must resolve in A and fail in B under the real `ticket_body` and `evidence_directory` implementation.
3. Under fixed mocks for job/source inventory and an independently modeled subprocess verifier that resolves the nested CAS, call `verify_historical` with A and require accepted, then with B and **require refusal**. Same outer ticket, manifest and historical source; change *only* the caller-owned evidence-store directory and availability of the nested object. Clear global cache before/after the test.
4. Preserve the failing original hosted result if the current owner source accepts B. Do not edit the owner's runtime, weaken source guards, re-sign old tickets or reinterpret the failure as success. Report exact code path and minimal safe correction boundary to the owner; a separate change would require independent testing and ownership-aware integration.
5. Also verify that same-scope repeated lookup may reuse a valid earlier result, but only within the identical verified evidence context. Test refusal rather than positive economic outcome.

**Acceptance:** both trusted-store contexts verified, correct refusal on missing nested CAS, no cash/account mutation, no source write. Exactly one preregistered counterexample; no switching fixtures to obtain favorable verdict. The mock checks only whether a nested historical verification is called; it does not assert production exploitation or a full native account migration.

**Resources and scope:** standard public GitHub Actions only with read-only token, pinned official checkout/Python actions and mandatory platform start marker. No API keys, paid services, new credentials, outreach, external transactions, private owner files or economic claims. Retain all actual failures. Full source-matched financial-owner qualification and operational handoff remain separate.
