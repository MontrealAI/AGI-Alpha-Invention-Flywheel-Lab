# P0-257 — bounded key-free dependency closure feasibility

Base 3cc6bc95a13f991b5158e5bd5064b766b21632a4; owner PR40 ced6c1cb004887dcdafaea59a2976020be649f8e; independent PR553 1851100612b8c80a1852f413057bdb635de62d3a. No owner modification, account access, signing, financial action, release or competing writer. P0-255 qualified isolated interoperability and P0-256/256b historical outcomes remain unchanged.

Question: can isolated Python startup still use a narrowly staged, independently content-pinned installed cryptographic dependency set without enabling the entire ambient site-packages directory? This is a dependency prerequisite, NOT full execution-closure or native financial qualification. Actual interpreter and OS trusted; installed distribution RECORD metadata and a locally frozen manifest are development provenance, not independently trusted release-wheel identities. No new package installs, downloads or paid resources.

Use the actual available local interpreter and installed cryptography, cffi, pycparser distributions; record versions and bytes, not pretend they match owner release requirements. Build a temporary import root from regular non-symlink, package-relative, SHA256-verified RECORD members, excluding bytecode/cache and metadata, with exact membership and per-file manifest. Do not copy the whole ambient site-packages. Run a fixed harmless known-answer SHA256 computation with isolated startup (-I -S -B), using only the explicitly staged dependency path. No real secrets, no keys, no account records. Six registered cases, once each:
1. Isolated interpreter with no added dependency root must fail to import cryptography.
2. Staged dependency closure must compute the exact known SHA256 of ASCII abc, with isolated flags active.
3. Same staged closure with changed one pinned member must be rejected before child launch.
4. Same staged closure with an extra unregistered Python member must be rejected before child launch.
5. Same staged closure with a symlink replacing one pinned member must be rejected before child launch.
6. Explicit broad ambient-path control (site-packages plus separately staged benign unrelated test module) must compute same result and see that unrelated module; staged-only positive case must not see it. This establishes only the difference for the declared explicit path fixture, not a general sandbox.

Freeze source and record hashes, six outcomes, elapsed wall and waited-child CPU, and limitations. Stop after six cases, even if any fail. No acceptance repair in place; subsequent changes require a separately registered attempt. Success is dependency feasibility under the named trusted host, not owner adoption, not a release, not economic progress. No new authority needed for this separate research.