# Cycle-006 source identity and current qualification

The immutable `campaign/cycle-006/REPRODUCTION_FREEZE.json` binds 6,363 files,
including the historical hosted workflow, policy documents and `flywheel/legacy.py`.
Its SHA-256 remains
`d64396e8d8e058aaddf1ecacf3e89f618d77b1e9ea88c87682ac3e8917534fdc`.

Current benchmark discovery and policy materialization repairs intentionally
change the operating workflow and current `flywheel/legacy.py`. Calling the frozen
runner directly in that changed checkout correctly refuses the changed identities.
The hosted failure at commit `308b2d6393d04689f79970725cf3679d599b9526` is preserved
in `evidence/commercial010/qualification/hosted-repair-308b2d6.log`.

`flywheel.reproduction006` now materializes exactly the unchanged freeze closure
into a separate directory without Git ancestry. Every input is checked against
the old hash before output creation. Only the named workflow, policy documents and
legacy materializer may use a bundled byte-identical original. These originals
were fetched from public main commit
`69a4725d9c12589860670a551911bedbd65cba9e`; their identities match the original
cycle-006 freeze. Policy documents shared with cycle-001 reuse those existing
verified snapshots.

Current tests execute the current repaired source. The cycle-006 replay executes
the original source copied to that separate directory. A successful old replay
does not certify current code as historical code, establish fresh scientific
confirmation, or qualify commercial success. No frozen manifest or reference
identity was rewritten.
