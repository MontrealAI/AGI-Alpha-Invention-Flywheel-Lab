# Definitive connected-journal rejection

The original source left an unknown-trade event PENDING despite no native action.
That blocked a legitimate cost and made reopen repeat the same rejection.
COUNTEREXAMPLE.before.json preserves the exact baseline source hash and outcome;
REVIEW_FINDING.json preserves the source-bound review finding.

New execute and resource-spend attempts carry a source/request/current-state
certificate in their authenticated write-ahead entry before native execution.
A ValueError can become terminal REJECTED only under the qualified owner, with
identical full Account export (including proofs/resolutions), last native time,
healthy byte-identical durable action tape, and no obligation-resolution progress.
An isolated canonical native replay must reproduce the exact error without
changing its full exported state or last time. Public audit independently verifies
the rejection, its ordered prefix/certificate, and zero native action coverage.
The global complete native coverage requirement remains unchanged.

The failed request, bounded error, source, prefix and native-record hashes survive.
The same key and payload return the same rejection after advancement/reopen;
changed payload fails collision checks. Retrying changed circumstances requires a
fresh action/event identifier. Rejections claim no expense or investment.

Certified fresh-format PENDING entries can retire safely after restart only when
their exact preattempt state still matches and the zero-effect domain rejection
is reproduced. Partial native commits, acknowledgment loss, unrelated advancement,
failed storage and nonreproducible errors retain pending recovery. A rejection-save
failure stops further writes until reopen; both save-before-write and
save-before-acknowledgment are tested. Older uncertified PENDING intents remain
fail-closed; no missing old authority is reconstructed or silently rewritten.

Fourteen final focused regressions pass. The earlier eleven-test pass predates the
additional restart-certificate coverage and is preserved separately. All original
eight worlds have 2,113 COMPLETE entries covering 2,212 native actions, with zero
pending/rejected entries or coverage gaps. Their original economics and failed
600-CPU qualification remain historical evidence, not a repaired-source run.
No commercial experiment, native financial algorithm, cost, price or acceptance
rule was changed. Full composed exact-head qualification remains separate.

Reproduce the read-only original-record inspection with:

`python evidence/completion015/journal-rejection-repair/scan_history.py /path/to/original/public-package /tmp/journal-impact.json`
