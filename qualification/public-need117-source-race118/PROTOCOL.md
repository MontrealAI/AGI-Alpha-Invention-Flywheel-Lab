# Qualification 118 — source-identity race in external perception audit (frozen before witness code)

**Frozen source:** protected main `3ccf23595c65f8a85b1e69391820463a2d72d5e8`. **Independent owner source:** draft PR #316 at exact head `9e9b501c84ffe7b7969027c43eb465aff81f8499` (do not modify its branch). This is a supporting adversarial source-custody investigation, not a commercial or Blue Sky success.

## Original claim and falsifiable test

The public-need117 offline verifier is supposed to bind the independently recounted sample to the SHA-256 stored in `RESULT.json`. Its current `verify()` performs `csv_path.read_bytes()` for hashing, then separately `csv_path.open()` to parse. Freeze two different *synthetic* CSV byte streams A/B, identical group confusion counts but different case IDs. Construct a receipt for A with the pinned generator, and first show its normal verifier accepts A.

In the **single registered adversarial schedule**, replace A with B after `read_bytes()` returns original A but before `open()` reads the pathname. Re-run the pinned external `verify()` unchanged under the deterministic swap. Record whether it accepts B while reporting the SHA-256 for A. Any such acceptance is an **INTEGRITY FAILURE** despite successful diagnostic execution. Rejecting the swapped bytes is the required secure outcome; never relabel a successful exploit as a passing verifier.

Use exact PR316 source and no government data, networks, credentials, original native accounts or private subjects. Preserve the source SHA, A/B SHA, receipt/source mismatch, command, exit, and complete reported outcome. A prospective owner repair should read and parse one bounded immutable byte buffer (or hold a file descriptor and hash/recount those exact bytes), and independently test the repaired source. Do not alter PR316, original outcomes or the financial P0 owner. No merge before an independent review of the finding and repository-wide source-matched qualification.

## Commercial dependency and limits

A verifier that recounts different bytes than it authenticated cannot substantiate source-bound acceptance of a social-perception methodology artifact, a supporting component of publicly expressed DFO procurement need #316. Repairing it would still not establish population representativeness, independent labels, supplier eligibility, buyer acceptance, actual customer revenue, Blue Sky qualification or the US$3B profit target. Noncontact prototype only; **NO BID / NO DEPLOY**.
