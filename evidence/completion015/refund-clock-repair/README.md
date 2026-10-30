# Frozen native offer and refund clocks

The prior audit compared actual native and operating refund times to each other,
and compared declared clearing_due_time to the frozen deadline, without connecting
those two checks. Its failed-quality early-continue branch also omitted actual
refund timing. The native offer deadline itself was not bound to the frozen
payment deadline. REVIEW_FINDING.json preserves the primary full-audit finding.

Every native offer now carries exactly qualification + payment_deadline_hours.
For a default refund, both actual native refund and operating REFUND event must
equal the recomputed frozen due time. For failed quality they must equal
production + acceptance_hours before the early continue. Native obligation,
acceptance, settlement, payment shock and completed-outcome checks remain intact.

Five small helper tests cover early/late refunds, independently changed actual
timestamps, failed-quality timing, typed/missing timestamps, changed native offer
deadlines and nonzero qualification time. No full native audit, business run or
14-day engine fixture was executed in this repair.

Read-only original records contain 126 native offer deadlines and five default
refunds; all satisfy the new clock checks. The copied-refund counterexamples show
the precise prior predicates still true when both actual timestamps move to
acceptance while the declared due remains unchanged; the new helper rejects each.
That is branch-predicate evidence, not an independently rerun full-audit result.
There are no original eight-world failed-quality refunds; that branch is covered
by engineering fixtures rather than invented historical evidence.

No producer, cost or financial authority changed. Original results and the failed
CPU qualification retain their original source identity. Exact composed-source
hosted qualification and actual released operation remain separate gates.

`python evidence/completion015/refund-clock-repair/scan_history.py /path/to/original/public-package /tmp/refund-impact.json`
