# Prospective trusted-command resource wrapper

`experiments.resource006.run(command, output, ledger, run_id, limits, cwd=None)`
reserves before launching, records exact waited-child exit/rusage, preserves logs
and receipts, and settles under a separate `flock` lock. Output and run identities
are exclusive. A reused ID or conflicting settlement refuses; repeating the
identical settlement is idempotent. The resource ledger is separate from the
existing simulated commercial accounting.

```sh
python -m experiments.resource006 --ledger /tmp/alpha006-resources.json \
  --run-id pilot-001 --output /tmp/alpha006-pilot-001 \
  --wall 120 --cpu 120 --memory-bytes 1073741824 \
  --output-bytes 20971520 --storage-bytes 67108864 \
  -- /absolute/path/to/python -m your_trusted_fixed_experiment
```

The callable's `limits` has exactly five positive integer fields:
`wall_seconds`, `cpu_seconds`, `memory_bytes`, `output_bytes`, `storage_bytes`.
The per-file output limit must not exceed the total run storage reservation.
Use one shared ledger outside the run output directories. Its campaign reservation
capacities are 5,400 CPU-seconds and 6 GiB, matching the recorded cycle allocation.
These capacities do not erase earlier unmetered work; the ledger is prospective.

The wrapper constrains each launched process with CPU/address-space/file-size
limits, removes ambient credential variables, uses a fresh process group, and
kills that group on wall timeout or observed output-storage excess. These are
trusted-command controls, **not a sandbox**. Commands can still access host files
and network; generated policies must continue through the qualified seccomp
runtime. Per-process limits do not establish a hard aggregate process-group CPU,
memory or disk quota. Output monitoring is sampled and can observe an overrun;
a measured overrun blocks further reservations rather than relabeling it safe.

`os.wait4` attributes waited-child rusage to this run without overlapping a
supervisor's other child commands. It includes descendants accounted by that
child, but cannot certify escaped or unwaited descendants. The receipt therefore
states `aggregate_cpu_complete:false`. No unused CPU reservation is refunded:
its conservative budget charge is distinguished from measured CPU and money.
Storage unused after observed complete/failed process termination is released.
Interruptions retain pending reservations and a receipt; unknowns remain unknown.
An actual supervisor SIGKILL can leave only its initial pending record: automatic
reconciliation or refunds are intentionally unavailable without adjudication.

The three tests cover success/nonzero exit, exact duplicate settlement, reused
IDs, wall interruption, seeded prelaunch interruption, malformed limits and
aggregate reservation exhaustion. Owner evidence includes a real accepted smoke
and the preserved inconsistent-limit refusal. Complete monetary, inference and
historical campaign costs remain unknown.


## Executable preflight repair

The original wrapper's sanitized `os.defpath` does not include this runtime's
Python. Real literal-`python` attempts failed before their science commands ran;
their conservative reservations and receipts remain unchanged. The exact original
wrapper is retained at `historical/cycle-006/resource-wrapper-before-python-alias.txt`.

Version 2 normalizes only the exact aliases `python` and `python3` to the current
absolute `sys.executable` before reserving resources. Both the requested and
normalized command are recorded; the virtual-environment entrypoint is preserved.
Every other executable must be an explicit absolute executable file. There is no
ambient PATH lookup, shell parsing or interpreter-version guess. An unavailable,
relative or directory executable produces an exclusive `REFUSAL.json` where
possible without touching the campaign ledger. Invalid commands cannot spend a
fresh reservation. Launch/monitor exceptions now retain their type and at most
512 characters of detail; they do not trigger automatic historical refunds.
