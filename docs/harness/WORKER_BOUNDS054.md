# Frozen-worker active-phase qualification 054

The current checker is `verification/probe_worker_bounds_current054.py`. It
qualifies resource guards and interruption of an already running protected worker
against the exact materialized cycle-001 closure. The frozen `reproduce.py`,
original `verification/probe_worker_bounds.py`, closure, edition and paper bytes
remain unchanged. This is a checker-readiness repair, not a startup recovery
repair or a new financial/model result.

Main `99769a8a4d19a8cfc1b3c6d05084d7ed99b76849` failed bounded run
`41300637969`: public artifact `13082132066`, ZIP SHA-256
`a8bcbe0d49b1184a5058b97d5a965000b1efc18ad507a0d75dd0dde371b0f0fd`.
The actual traceback shows SIGINT during `STARTED.json` publication, before the
parent entered its protected `try`. No `INTERRUPTED.json` was produced. That
historical result remains failed, and the early-STARTED interruption defect is
**PRESERVED_NOT_REPAIRED**. Neither an old receipt nor that initialization property
is relabeled as passed by 054.

The original checker treated mere STARTED-file existence as readiness. The new
checker instead requires all of these observations before its real parent SIGINT:

- Exact pinned frozen inputs; the live parent belongs to this invocation.
- Only that parent's direct child list is read. Its worker must have the exact
  frozen runner, `--worker`, output path, parent identity and PID namespace.
- A pidfd binds that worker; its start identity is rechecked, SIGSTOP is delivered
  to it, and its stopped state is confirmed. `WORKER.log` establishes the protected
  phase; REPORT and COMPLETE must still be absent.
- The pinned single-threaded parent is observed in `hrtimer_nanosleep`, its
  subprocess timeout-wait loop. This is after Popen construction, so the parent
  owns worker cleanup when SIGINT is delivered. No arbitrary readiness sleep is
  substituted for these events.

Success still requires a real KeyboardInterrupt `INTERRUPTED.json`, nonzero
parent exit, no COMPLETE, pidfd-confirmed worker termination caused by the parent
SIGINT, and same-directory restart refusal with identical partial-file hashes.
The worker is quiescent before hashing. Cleanup targets only the known parent or
worker; any forced checker kill is recorded and **cannot pass qualification**.
The original actual 2-GiB allocation, 20-MiB file and 200-descriptor overrun attempts
still exercise the frozen 1-GiB address-space, 10-MiB file and 128-descriptor
limits. Effective CPU limits are recorded as before.

054 requires Linux pidfds, direct-child procfs, parent wait-channel observation
and child-subreaper support. Missing support fails closed; it is not an accepted
interruption receipt. `tests/test_worker_bounds_readiness054.py` retains a
deterministic early-STARTED negative and exercises the real frozen main/worker
with a disclosed test-only Popen PID observer on restricted hosts. That
instrumented test is separate from canonical-path acceptance. The focused
`active-worker-bounds054` Ubuntu job runs the normal uninstrumented checker early,
retains only its compact public REPORT/resources/interruption receipts, and gates
existing publication jobs. The full bounded job also runs the current checker.

No all-initialization-point recovery, host-power-loss durability, financial
performance, or scientific/commercial advance is established by this check.
