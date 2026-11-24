# P0-270B — native evidence scope effect qualification (development only)

Frozen before one new hosted invocation; this is not a retry of the P0-270 static anchor inventory or the timed-out native lifecycle. Use PR40 source ced6c1cb004887dcdafaea59a2976020be649f8e and exact transition_evidence.py Git blob 2397091ef8e1960ad13950693d5b3cd04e2ff7c5. Execute the original native codec/storage module on newly created disposable, key-free, nonfinancial data only. No private accounts, actual source migration, ledger actions, signed authority, new credentials, cache adoption or owner runtime modification.

## Fixed acceptance and stopping rule

One invocation; retain every case, including unexpected rejection or exception. Seven checks:

1. Canonical directory entry removes a valid same-inode interrupted-publication staging alias, while retaining exactly the published bytes.
2. A second entry is idempotent.
3. Native in-memory evidence_scope resolves the same exact codec body as the directory scope but leaves a separately created valid staging alias untouched; equality of the codec result does not establish equal storage effects.
4. The canonical directory entry does not remove an unlinked, non-alias staging file; preserve the native recovery distinction.
5. Corrupted published bytes with a matching staging hardlink fail closed; retain both paths on rejection.
6. A key-free immutable snapshot of the fixture's two canonical final objects, captured after native directory recovery, resolves through the original evidence_scope; a corrupt snapshot is rejected. No assertion of consistency under a concurrent writer or of a complete transitive audit closure.
7. Isolated child started with no directory or explicit bytes has no inherited evidence scope. An explicit caller-selected directory route in a separate isolated child resolves the same body and performs native alias recovery. No claim that a real historical journal audit is pure or that arbitrary processes can be safely mediated.

Compare the full native directory route, native immutable-byte route and no-scope rejection, using identical codec input. All checks use canonical native functions. The fixture is not a valid financial transition; it deliberately tests only content resolution/storage effects. No signatures are authenticated, no real account identity is accessed. Use the original file/byte bounds, no limit relaxation. Exit nonzero if any check fails. Keep the compact aggregate receipt; no raw fixtures or paths are retained. Record exact source/test Git blobs, Python version, CPU (self and waited children), elapsed time; actual billing unknown.

## Decision

A pass establishes only this native storage boundary. Keep broad historical cache reuse blocked until the actual historical implementation/descendant execution closure, effect-preserving recovery, full transitive evidence set, authority boundaries and fresh-vs-reused native acceptance are qualified. Owner custody and protected integration remain separate blockers. Do not increase the successive-transition timeout or retry its unchanged failing fixture.
