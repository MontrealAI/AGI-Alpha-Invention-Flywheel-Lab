# Independent-owner restart comparison

The first full hosted qualification of the certified journal found seven engine
comparison failures, preserved separately in the primary connected/release logs.
The product full Account certificate intentionally hashes private proof HMACs and
the local filesystem label. The existing test projection stripped their direct
fields, but could not remove that entropy from the derived certificate digest and
enclosing journal digest.

LEAF_DIFF.before.json records two actual independent fixture accounts with distinct
simulation keys executing the same earned-proof sequence. Their raw native ledgers
are identical. After the original projection, precisely two leaf paths differ:
the next journal entry's attempt.account_record_sha256 and the enclosing
connected_journal_sha256. The actual filesystem was the same; an additional
authored-label fixture covers that already-excluded local host field.

Only tests/test_connected_engine.py changes. Its local comparison projection masks
the host/key-bound full Account witness and recomputes the journal digest from the
remaining projected journal. Every other certificate field, source, request,
native action, financial amount, obligation and useful-work field still compares.
Anti-masking checks perturb cash, native action amount, obligation incurred cost,
journal request and five native/request/durable certificate commitments; every
perturbation remains visible. The product full certificate, its live equality and
recovery/audit checks, and shared adaptive projection are unchanged.

Three small focused tests pass without running the 14-day engine class or new
commerce. This is a test comparison repair; the full exact-head engine/release
qualification remains a hosted gate and is not claimed by the focused result.
