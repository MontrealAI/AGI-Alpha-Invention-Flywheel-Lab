# Adjacent native snapshot reuse

A released operation completed its run command but exceeded its historical CPU gate. This candidate does not raise a cap, rerun the business or rewrite that failure. Its separate paired read-only experiment replays the existing 528-action central-growth tape.

Two duplicate SQLite reads are removed: the auditor passes the expected opening state to the operation, which validates its own fresh opening snapshot before action validation or effects; conservation checks consume the just-captured post-operation snapshot. Every invariant remains. No state is cached across operations. The underlying connection is enforced private in-memory SQLite by `memory_engine`, remains thread-confined, and the existing single-writer ownership gates remain intact. Standalone conservation checks still obtain a fresh snapshot.

Eight ABBAABBA same-process trials retained every result: mean CPU 1.544980 seconds baseline vs 1.153237 seconds candidate (25.36% lower). All result digests exactly match. Snapshot calls fall from 2,536 to 1,480. Seven source/opening/sequence/after/summary tamper variants reject identically; 36 focused, ownership, cancellation and canonical-prefix regressions pass. See RESULT.json. This microbenchmark does not promise the same improvement on an entire released operation or explain cross-host CPU variance. Unknown actual billing remains unknown.

Tests: `python -m unittest discover -s tests -p test_snapshot_reuse030.py -v`; existing `test_adaptive_account.py`, `test_adaptive_cancellation.py`, and `test_connected_audit_prefixes.py`.

Original financial outcomes and obligations are unchanged. No failure ZIP or bulk logs are added. The publisher must compose this ledger-only runtime delta on current main, update current source binding without altering historical records, and qualify the actual public candidate.
