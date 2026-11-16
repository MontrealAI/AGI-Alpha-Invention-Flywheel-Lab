# P0-185 extension — in-place historical CAS disappearance after cached approval

Prospective, separately registered adversarial follow-on to the **unchanged failed P0-184** test. This file is committed before new test implementation. Original P0-184 protocol, test, failed hosted receipts and findings must remain unchanged. Parent source is financial-owner PR40 at `ced6c1cb004887dcdafaea59a2976020be649f8e`. Independent reviewer owns only the additive test and this registration; no original account or signing material is used.

## Fixed schedule and rejection criterion

Use the identical synthetic two-generation v2 CAS ticket factory in `tests/test_transition_store184.py` (no actual HMAC or monetary account). Persist **both generations** in one caller-owned ephemeral evidence directory. Under mocked historical source inventory, job loader and nested-CAS-aware historical subprocess:

1. With immutable outer ticket, manifest and pinned historical root, invoke `verify_historical` in that directory. Require first verifier invocation to succeed; an identical second lookup may be cached.
2. Exit the evidence-directory context. Simulate loss of **exactly one already identified nested predecessor CAS object, chosen deterministically as the lexicographically first member of `inner_objects - outer_objects`**. Never remove real or historical repository evidence; the test owns and deletes only its ephemeral fixture blob.
3. Reenter the **same directory path** with the same outer ticket, manifest, root and unchanged module-level historical cache. Require outer ticket resolution to succeed and inner predecessor `ticket_body(nested)` to reject `TRANSITION_EVIDENCE_MISSING_OR_CHANGED` under real CAS code.
4. Invoke `verify_historical` again. **Require refusal** (`PINNED_HISTORICAL_AUDIT_FAILED` from the mocked independent subprocess) and require that subprocess invocation count increases to two. If cached success is returned, the test must FAIL without retuning fixtures or treating the failure as a pass.
5. Clear the process-local historical audit cache in `finally`; avoid any other financial/source mutation.

The registered mutation is identical-store object disappearance, not changed directory identity. An implementation that merely adds evidence-directory pathname to the cache key would still fail. A safe remedy must revalidate transitive blob availability/integrity on reuse, or conservatively bypass historical-success caching whenever evidence-backed v2 CAS is involved, while retaining pinned source/audit semantics and full account authority. The test does not validate original-account finance or prove real store deletion occurred. Preserve both P0-184 original failures; P0-185 is a separate independently classified execution.

## Constraints

Read-only GitHub Actions workflow, standard public runner, same pinned actions, initial platform start marker. No new secrets, purchases, paid model use, original signer/ledger/queue access, release, merge, or outreach. The owner-source exact-head qualification and authenticated operating-queue migration remain blocked.
