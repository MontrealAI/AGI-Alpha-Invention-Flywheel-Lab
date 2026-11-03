# Lab acknowledgement ambiguity 079 — frozen independent conformance check

Frozen prospectively on an isolated review branch from main `a704d03bbbf855c50c3fd758e7f9ef548bcf527c`, before implementation or tests. This is independent **supporting evidence** for the separately owned modular-lab Enterprise078 construction. Do not write to, merge, or relabel its source/results. It is not a new physical laboratory, commercial enterprise, model, market or discovered algorithm.

## Decision-relevant question
When a command has an irreversible effect (e.g. depositing a dose) and its response is lost, can an arbitrary controller guarantee both exact-once action and eventual correct completion, without authenticated device readback or retained idempotency? Define two indistinguishable traces: `unexecuted` (effect 0) and `executed` (effect 1), both returning only `ACK_LOST`. Same observation implies the same controller decision. `RETRY` risks dose 2 in the latter; `DECLARE_COMPLETED` lies in the former; `REFUSE` preserves safety without delivering. A perfect no-observation completion policy is impossible, regardless of how much computing it has.

## Preregistered finite cases / controls
Six fixed tests, without seeds or retrospective tuning: (1) no-readback/no-dedup indistinguishability and safe abstention, (2) retry counterexample, (3) false completion counterexample, (4) authentic readback restores a safe completion path under a **single** injected loss, (5) durable device-side idempotency key restores a safe completion path under a **single** injected loss, (6) stale readback or expired idempotency is insufficient for a safety guarantee. The strong conventional human+software comparator is allowed the very same readback, command UUID, durable dedup and status information as the candidate and can use existing SiLA 2 observable-command workflows or EPICS completion methods. Non-entry is a valid baseline. A candidate that merely implements the same capabilities ties, not wins.

Scope: precisely one non-idempotent effect, an acknowledged command retry only under the stated reliable observability/dedup assumption, and finite traces above. This does not prove a physical device's implementation, safety, calibration, network fairness or progress under arbitrary repeated losses. Durable idempotency must persist over retries, across crashes and for an identified execution, and no stale/expired record may be treated as current.

## Completion and use boundary
Execute exactly these six prospective tests on the first implemented source. Preserve every failure and never change the registered cases after seeing outcomes. A pass qualifies an offline information/safety assertion **only**, not superiority, physical operation, device interoperability, rights, customer demand, finance, investment, paid acceptance, or US$3B trailing-365-day profit. Forward findings as independent review to Enterprise078's owner; no automatic integration.

Primary conventional baselines: https://sila-standard.com/standards/ and https://pyepics.github.io/pyepics/pv.html . NIST describes the broader four standards dimensions at https://www.nist.gov/programs-projects/development-standards-support-modular-and-autonomous-laboratory-ecosystem . These establish existing methods, not endorsement of this research prototype.

No model API, paid service, customer outreach, private inputs, account creation, credentials, physical actuation or real transaction. Operating costs/actual model bills unmeasured; no native profit is booked. 
