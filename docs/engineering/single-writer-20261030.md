# One cash history, one live owner

## Why this was selected

Before joining portfolio planning to earned-funded execution, the account must
have one current state. At commercial head `7e47bfefebd5e47b594f9efe85412eefd4cc33e4`
(and unchanged persistence at `364f5ee41d1ac21f368cc3d19109cd4067de8c9f`), two
`DurableTape` instances can simultaneously open one action file, each restoring
an independent in-memory native exchange. Per-instance SQLite transactions do
not coordinate these two copies.

A directed persistence/native-layer probe established 90 simulated USD earned
in each identical starting view. Two 60-unit reservations both passed locally
and wrote sequence zero to the shared tape. The resulting history was not a
valid serialized history. This does not assert that the full campaign already
overspent or that its independent auditor would approve such a history. It
shows why a future multi-worker deployment must not acknowledge both owners.

## Change

`commercial/tape_lease.py` provides a nonblocking POSIX lifetime writer lock on
a stable sidecar inode. `commercial/single_writer.py` wraps the existing tape
or actual `TapeExchange` with ownership acquired **before** opening/replay,
retained through native mutation/checkpoint, and released on close or process
exit. A competing owner fails before it can read a stale financial snapshot.
Successful takeover restores the existing native history; it does not reset
capital or erase an earlier reservation.

Historical `commercial/persistence.py`, `ledger.py`, source freezes, outcomes,
policy, scenarios, price rules and financial algorithms remain byte-identical.
The new facade is an **opt-in current-execution entrypoint**, not a retroactive
rewrite of earlier evidence. All cooperating live owners of the same account
must use it; legacy unguarded instances can bypass the lease. Adoption belongs
to the commercial runtime owner and requires a new, explicit source qualification.

Use `SingleWriterExchange` around the real account, not a second `OwnedTape`
around an already-owned exchange. The lock does not authenticate customers,
validate market assumptions, add money, reserve forecasts or approve spending.
Distinct accounts can proceed in parallel; operations on one account remain
serialized. This is for an operator-owned local POSIX filesystem, **not** a
distributed lock, hostile-host sandbox, or network-filesystem guarantee. Do not
unlink an active or idle lock file: its stable inode is the coordination point.

```python
from commercial.single_writer import SingleWriterExchange

with SingleWriterExchange(path, root=root, manifest=manifest,
                          opening=opening, working=working, contract=contract) as account:
    before = account.snapshot()
    account.execute(op, args, day)
    after = account.export()
```

The trusted controller still supplies permissions and invokes the existing
independent audit and native earned-funds checks. No real payment credentials
or live external system is involved.

## Validation and limits

Eighteen targeted Linux tests pass using exact native exchange/contracts bytes
recovered from source-matched hosted artifact 12989922435 (SHA256
`7a353815059784e96641fc37bf092a31f2e303fa456074165edfccffe7e9a371`).
Native blob identities match the current repository:
`protected_exchange.py` = `378bf67ae24c18ad58b684ce8b13492fd06f8556`;
`contracts.py` = `a26129ff4ee72ed8b4f8467f6c9de07b8d67508c`.
Original persistence blob: `6a8bed689c976cc969b80db44d65d57cb000795a`.

Checks cover same/separate-process contention, crash recovery of an fsynced
action, initialization failure, symlink/FIFO/hardlink refusal, inode replacement,
forked-child refusal, sequential takeover, checkpoint integrity, and native
reservation of 60 from 90 followed by rejection of another 60 after replay.
These are directed engineering cases, not independently sampled businesses.

Three additional tests target the full `commercial.ledger.TapeExchange` and
its actual service manifest. They are included in normal root test discovery;
local execution of those three is not claimed without the full source closure.
They must pass on exact-head hosted CI before runtime adoption. No existing
historical freeze is rehashed to obtain a passing check.

The original negative probe and logs are retained in the accompanying artifact.
An intermediate local refactor failed with an undefined encode name; that
attempt is retained and is not the submitted design. The submitted design
instead preserves the frozen module and uses the separate ownership facade.

## The actual next milestone

Adopt this ownership boundary in a qualified current runtime; feed source-bound
accepted jobs and audited available earnings into the allocator; commit via the
existing native gate; execute further delivery; compare predicted with realized
simulated cash. Keep commercial success independent of capability improvement.
This patch prevents a specific unsafe path toward that experiment. It does not
claim the planner integration, a new profitable business, capability improvement,
or physical productive expansion has been completed.
