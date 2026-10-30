# Executed receivables reconciliation service

This is actual autonomous execution of a small digital service on **authored public synthetic workloads**. It is not a customer transaction, empirical demand study, accounting attestation, or demonstration of novel invention. The production code computes row-level results from input records; acceptance is recomputed by a separately implemented checker. The same system-provided model family and host were used, so the separation is procedural and does not constitute external certification.

## Selection and contract

The bounded candidate screen compared three materially different complete services: researched articles (useful but source/interpretation acceptance is harder to automate), tested software patches (useful but repair scope and repository-specific obligations vary greatly), and receivables reconciliation (selected because exact cents, row conservation, references and ambiguity can be rejected independently). This selection addresses the independently authorized fixed-capability commercial lane. It claims neither a new enabling means nor superiority to competent conventional accounting tools. Ordinary accounting tools and AI-native suppliers remain competing buyer options in the market model.

An order supplies 1–1,000 invoice and 1–1,000 bank-payment records, USD integer cents, customer identities and explicit invoice references where known. Delivery includes `reconciliation.json` with exact matches, unmatched balances and conservation totals, plus `exceptions.csv` for follow-up. Grouped invoices and split payments can match when the reference group and exact cents agree. An unreferenced payment matches only a unique same-customer invoice for the same amount, with a unique corresponding payment. Overlapping exact reference groups are conservatively quarantined. Ambiguous or incomplete records remain visible; they are not invented into a balanced ledger.

The original order controls acceptance: an exception-schedule order may accept an accurately unresolved outcome; a `require_complete=true` order fails if any rows remain unmatched. Negative reversals and non-USD inputs are rejected as outside the bounded contract. A delivered reconciliation does not edit source records, file taxes, attest accounts, move money or claim to detect fraud. Seven modeled support days and defect correction are charged by the separate complete-cost market policy.

## Executed cohort and adverse evidence

`executed-002/manifest.json` binds all 19 orders of **1,000 source rows each**, 16 accepted deliveries, three rejected orders, independent receipts and 20 attempt records. The 19,000 records are synthesized as independently namespaced blocks from the exposed templates. Every accepted order contains mixed patterns: reference matches, split and bundled payments, unique unreferenced payments and customer isolation; exception-schedule orders also include partial payments, equal-amount ambiguity and overlapping references. IDs and customer namespaces prevent accidental matches across blocks. Three boundary orders reject CAD, a negative reversal, and an unresolved strict-completeness obligation. Seeds and source hashes were written to `PROTOCOL.json` before execution.

The original smaller `executed-001` cohort remains preserved, including exact producer/checker/runner source snapshots. Its 19 jobs have 123 invoice and 122 payment rows; those small jobs do not justify a high human task-time benchmark. Source bounds were deliberately widened from50to1,000rows/table for the larger execution, and an independent checker test verifies1,000 source rows under five permutations. Both cohorts use the same disclosed families; the larger execution is engineering replication, **not a fresh holdout or real-accounting population study**. Human time assumptions must be sensitized separately (including fast conventional tools), not inferred from row count alone.

The preserved unsafe-first-match artifact is an **agent-authored adversarial counterexample**, not an observed naturally occurring frontier-model mistake. Its arithmetic balances, but it arbitrarily consumes one of two equally eligible invoices; the independent checker rejects it. The corrected ambiguity policy produces the checked exception schedule. It must not be relabeled an autonomous discovery or a measured first-attempt error rate. The reused seed sets provide engineering replication within the same disclosed generator; they do not establish performance across real accounting populations.

All accepted service artifacts begin commercially unallocated. The separate strategic market may sell each at most once per run, leave work unsold, or lose buyer participation. Acceptance here establishes the declared functional contract, not willingness to pay. Every rejected order, failed probe, acquisition failure and unsold output belongs in the modeled complete-cost cohort.

## Execution, accounting and reproduction

```sh
python scripts/run_service010.py --output runs/service010-replay
python -m unittest discover -s tests -p 'test_service*010.py' -v
```

The runner refuses existing output directories. It records measured process and wall time for production/checking. These milliseconds exclude agent inference, code construction, orchestration and broader campaign work. They are **not complete monetary costs** and must not be converted to human labor hours. Exact host model routing/version, token receipts and billing are unavailable; those values remain unknown and must be covered by explicitly conditional conservative complete-cost intervals in simulated commerce.

No human reviewer, paid provider, outreach, client data, real payment or credential access was used. Synthetic records are agent-authored and intentionally safe for public disclosure. Native invention mechanisms and historical evidence remain separately evaluated; this ordinary service does not acquire their stronger claims.
