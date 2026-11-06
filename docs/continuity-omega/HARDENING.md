# CONTINUITY Ω — Evidence hardening, 0.2.0 candidate

**Keep the promise. Do not let a success badge replace the evidence.**

This increment hardens the synthetic handoff from merged PR #278, source
`0d2b130f8be4c3fc1590bb436631d0d4a5cb4097`. It does not certify cyber resilience,
operate recovery infrastructure, reserve supplier capacity, authorize execution,
or alter any native financial account. Separate research PR #277 and the earlier
GENESIS Commitment 001 commercial loss remain unchanged.

## Reproduced findings and dispositions

| Finding | Original behavior | Correction / boundary |
|---|---|---|
| Boolean offer | A coherent zero-cost case accepted JSON `true` as a one-unit offer. | Exact integer types for all monetary and resource values; booleans never count as money. |
| Malformed evidence | Null top-level input, null supplier collection, and null reservation raised exceptions. | Explicit structural validation before arithmetic/replay; returns structured FAIL. |
| Coherent scenario replacement | Rewriting source events and recreating their seal and outputs passed a consistency check. | Optional caller-held canonical whole-case digest detects substitution. Original behavior was a disclosed v1 trust limitation, not proof of authentic source custody. |
| Stale display | `inspect` displayed a stored passport without a fresh audit. | Replays the current evidence on every inspection. Earlier files stay untouched. |
| Ambiguous JSON | Standard JSON decoding accepted duplicate object keys. | CLI reader rejects duplicate keys and non-finite numbers. |
| Implied timing | Legacy field `rehearsed_completion_hours` contains an authored lead time. | Field retained for v1 compatibility; new audit and display explicitly label STIPULATED_NOT_MEASURED. No stopwatch measurement or actual manufacturing is inferred. |

The original 13,342-byte replay implementation remains byte-preserved in
`continuity_omega/_replay_v1.py` (Git blob
`0f0bbd32000b35453958f31b18bbf868c7ce1ad5`). Use the public
`continuity_omega.checker.audit` entry, not the private replay. The independent
boundary and replay import no constructor. They still share research authorship;
this is not third-party independent assurance.

## Run

Python standard library only; no network, external account, key, purchase or installation.
From the repository root or a clean source package:

```sh
python3 -m unittest discover -s tests -p 'test_continuity*.py' -v
python3 -m continuity_omega demo --out /tmp/continuity-example
python3 -m continuity_omega.review \
  --in-dir /tmp/continuity-example \
  --expected-case-sha256 65ddee00ca5fa0a64817ffcb3a052da189594d2b3988b10671772460c8293ed8 \
  --report-dir /tmp/continuity-review
```

Both output directories must be new. Open `index.html` inside the review output.
It is an offline, accessible static report with no scripts, network calls or telemetry.
Existing `demo`, `verify`, and `inspect` commands remain available. `verify` and
`inspect` accept the optional `--expected-case-sha256` argument. Without a pin,
the verdict is consistency-only and explicitly reports UNPINNED.

The published digest describes **this authored fixture only**. For a different
case, a trusted owner must establish and retain its original canonical digest
outside the package before producing the candidate. `case_digest` defines the
canonical serialization. Computing a new digest from an untrusted package and
then accepting that digest does not create trust. A matching pin establishes
byte-level identity under the hash assumptions, not truth, current capacity,
authorized source origin, elapsed recovery time, or customer acceptance.

## Executed evidence

46 focused tests pass locally: the unchanged 29-test regression suite and 17 new
boundary/inspection tests. The latter includes every one of 945 changed single-node
input mutations from the declared replacement set; all fail against the original
pin. These are engineering mutations, not 945 customers, cyberattacks, independent
scientific discoveries, or statistical evidence of a failure probability.

The baseline source ZIP has SHA-256
`eb6b4f7f8152f1a9e90b47038c07eeec127a1f5fcf112774d848053ba60cbf16`.
Its 29 tests were re-executed before modification. The first new mutation-count
assertion expected more than 1,000 cases but enumerated 945; the exact denominator
was corrected without dropping any mutation. All functional mutation assertions
already passed in that run. No empirical success claim was produced from it.

Browser rendering was checked at 1280px and 390px widths using local authored HTML;
status and no horizontal overflow were verified. Public deployment, hosted review,
merge and release are separate receipts, not implied by these local checks.

## Remaining decisive work

The next useful result is one genuinely authorized, independently accepted customer
rehearsal, not another synthetic victory. The [pilot specification](REAL_PILOT.md)
remains proposed, not an executed contract. Start with authentic records, an actual
supplier's reserved capacity, permitted data sharing, an explicit clock and deadline,
and agreed acceptance. Compare with competent conventional recovery and fallback
fulfillment on the same requirements and complete costs. Preserve refusals and failures.

Do not sell the same backup slot twice. A collection of individually passing local
passports is not a jointly feasible capacity portfolio. The native capacity/account
machinery and supplier commitments need their own scoped integration and stress tests.
A pin is not that machinery, and this increment creates no parallel ledger.
