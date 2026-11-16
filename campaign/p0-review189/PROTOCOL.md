# P0-189 — Self-contained historical CAS proof transport (research only)

Registration: 2026-11-16 UTC. Parent and unchanged P0-188 head `d6b8e8a364bf25287e33f1b7da5c646aa6b16291`. Historical financial owner PR #40 remains `ced6c1cb004887dcdafaea59a2976020be649f8e`. This protocol is frozen in a separate commit **before** code or tests.

## Identified residual / hypothesis
P0-188 captured immutable CAS blobs plus the *digest* of the root signed ticket, but did not carry the root signed ticket's bytes. A digest cannot reconstruct the ticket in an independent receiver. Therefore a P0-188 snapshot is useful as a companion proof store, but is not self-contained proof transport on its own.

Construct an additive research-only portable root-ticket representation: retain **canonical immutable root-ticket bytes** within `HistoryEvidenceSnapshot`, provide a fail-closed `reopen_ticket()` that strictly reparses and independently revalidates the root and complete nested closure against its recorded fingerprints, without consulting the original mutable evidence directory. Never treat this verification as authentication of the owner's HMAC, acceptance of a prior audit, writer-leasing, cash authority, or current account authorization.

## Fixed finite controls
1. A synthetic two-generation V2 history captured in a trusted scope can be reopened using **only** its snapshot object after the original source file tree is removed; original ticket equality, schema, nested ticket and recorded root/closure digests are checked.
2. Modified, truncated or duplicate-key root ticket bytes are refused; a forged digest field or mismatched root ticket cannot silently reopen.
3. Tampered CAS bytes, removed nested CAS values, forged closure fingerprint or forged ticket count reject with no successful output.
4. Canonical root bytes and captured CAS are immutable to ordinary callers; no exported key, financial audit authorization, renewal or reservation API.
5. Original P0-184/P0-185/P0-186 and P0-187 unmodified test controls remain visible separately: P0-187 currently **FAILS** on the unchanged P0-186 cached verifier and is not to be hidden/changed or retrospectively marked successful.

Use one preregistered test implementation and exact source-head Actions. Preserve every failed, skipped, cancelled or interrupted job and declare real process/host costs unknown if not measured.

## Scope and integration ownership
This is a proof-transport repair, *not* a cached historical verifier repair and **not** the source/account/evidence atomic authority transaction. It does not change `upgrades.py`, `transition_evidence.py`, `operations.py`, financial owner PR40, native account/key/journal/queue, current main or any release. Neither a reconstructed ticket nor proof bytes can replace actual HMAC verification, pinned historical replay and canonical writer lease. A forged unsigned fixture is intentionally ineligible for finance. Do not merge wholesale into main.
