# Recovery audit before mutation

Adversarial review of composed source fee293f found that journal recovery audited
coverage only after completing a pending financial operation. The original
counterexample in RECOVERY_PREFLIGHT.before.json records an unexpected native
cost after an authenticated earned reservation. Reopen appended `finish`, charged
60,000,000 microUSD and released the reservation before rejecting incomplete
journal coverage. This was an integrity failure, not a successful recovery.

The repair audits native finances and the completed journal prefix before resume,
then requires the pending native suffix to be an exact prefix of its authenticated
request: zero or one ordinary/seed action, or zero/reserve/reserve-plus-finish for
an earned resource. It binds the reservation to the original pre-action state,
source, request, proof and resolution commitment. An unrelated native action
therefore rejects before further native mutation.

The final regressions exercise legitimate zero/reserve/finish crash boundaries
and inject an extra native cost at each boundary. Rejected recovery must preserve
all authoritative tape, WAL, proof and resolution bytes and its native financial
export. RECOVERY_FINAL.json binds final rechecks to exact file hashes; full composed
qualification remains a separate release gate.

RECOVERY_INTERMEDIATE_REGRESSIONS.log preserves 26 passing finance/recovery tests
before the final explicit source-contract/state checks were added. It is not an
exact-final-source qualification. The earlier broad fee293f test run was stopped
at its review resource boundary (exit 130); PARTIAL_FEE293F_TESTS.json records its
partial scope and measured CPU lower bound. No complete passing-suite result is
claimed for that interrupted run. Full logs and the immutable review snapshot
remain in the session QA directory.

No private simulation keys, account credentials, live customer data or historical
confirmation output was changed or published by this repair.
