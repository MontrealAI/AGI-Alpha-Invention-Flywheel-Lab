# FIRSTCASH210 — independently pinned public-source witness

**Research-only dependency for FIRSTCASH209.** Not a new autonomous invention, buyer acceptance, first payment, production release or an update to the authoritative native account.

FIRSTCASH209 can construct a deterministic ten-page bilingual kit from *author-submitted* source URLs. FIRSTCASH210 retrieves **one already pinned public source** and verifies returned bytes against the registered Git blob OID, then writes a compact provenance witness that can be audited offline. This verifies the source bytes, **not their semantic correctness, the commercial hypothesis or independent third-party endorsement**.

## Fixed public case

The public FIRSTCASH206 ADMISSION.md at exact commit 7f299640e9ad311b79b71850a9e0370aeb2984d9, expected Git blob 184291fa360326fe3cb44b213b74053ba486817a. This source came from GitHub's file API before implementing the witness. A separate unpinned PR506 reference in FIRSTCASH209 remains UNVERIFIED; do not silently claim it is immutable. No customer-supplied or private source is read.

## Reproduce on a machine with public HTTPS

    python3 -B -m unittest -v tests.test_firstcash210_source_witness
    python3 -B tools/firstcash210_source_witness.py fetch --output /absolute/new/firstcash210
    python3 -B tools/firstcash210_source_witness.py verify --output /absolute/new/firstcash210

The fetch makes one fixed HTTPS raw-file request with a 256 KiB cap, no redirects and no retries. Locally, SOURCE.md and WITNESS.json preserve the observed source bytes and canonical witness. The public CI artifact uploads only the witness and SHA256 inventory; reproducing a byte audit requires the locally retained source or an independent public refetch. The observation time is a download timestamp, not a source publication date.

## Strong alternatives and bounds

(A) Competent manual human/hybrid source review can do the same task without this helper, with unknown actual cost. (B) Automated pinned byte witness may reduce repeated manual retrieval but has no proven full-workflow advantage. (C) NO DEPLOY is the preferred policy where source truth, demand, rights, buyer acceptance or complete costs are not established.

Actual positive/negative test verdicts belong to the exact-head hosted workflow, not this document. No model, hosting or founder-work accounting is invented. A checked citation alone is not evidence a new business is viable. The next consequential commercial gate is voluntarily collected outside payment for a decision that proves useful, customer acceptance, actual complete costs, and repeat purchase/use.

**Owner boundary:** independent research branch dependent on FIRSTCASH209 commit 03ab77bf51c6fef2308556bfc0541a965d880030. Frozen registration d9e20f242a617a0acf2fdbd461c1c235a39f4462. Owner PRs #505–508, finance PR #40, current main, release, official checkout, private original account, signing keys and all obligations remain unchanged. No real purchase, outreach, production deployment, additional account, loan, paid API or spending occurs. US$3B T365 complete-cost profit remains unqualified.
