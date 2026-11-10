# Independent source-stream integrity review of Source Trace129 — preregistration

Frozen on 2026-11-10 **before any correction code or test implementation**. Parent Source Trace129 PR334 exact source `1041ee11571956dc78482a534c411c0eae7991c8`. Independent review branch `review/source-trace129-single-stream-provenance-20261110`; no change to its owner branch, the already published original 16 tests, original award/tender data, financial PR40, source, signer, account, queues or liabilities.

## Mechanistic problem and fixed decisive test
Source Trace129 currently computes each file SHA-256 with one open/read, then parses rows through a **different** opening of the path. A same-path atomic replacement between those openings can cause **different parsed bytes to be reported under the first file's hash**. This is not a fresh buyer, demand, commercial profit, or original-source document. The concrete claim tested is source-byte provenance only.

Test one: register an in-process deterministic file replacement after the first award input descriptor is acquired but before parsing begins; original file has one matched accessibility record, replacement has an independent recycling record. Under the unmodified code, the first digest may be bound to the different later parsed row: **FAIL_DIFFERENT_BYTES_ATTRIBUTED**. The test must expose this failure without cherry-picking or changing source/expected cases. Under corrected code, a **single read/parse descriptor** must bind exactly the bytes parsed to the emitted SHA-256 and recorded rows, even if the path is atomically renamed after the descriptor is opened.

Test two: an in-place mutation of the active input descriptor during parsing must be rejected as **SOURCE_CHANGED_DURING_PARSE** (or stronger rejection), without publishing a successful result. Existing malformed UTF-8, CSV width, privacy and amendment-cardinality failures remain fail-closed.

## Authorized prospective correction
Use a bounded streaming binary-to-text reader with incremental SHA-256 on the **same underlying descriptor** as the CSV parser, with pre/post descriptor metadata continuity checks. Never pre-hash one opening and parse another. Stream both official inputs exactly once each, no remote acquisition rerun for choosing better source, no field/keyword changes, no fabricated metadata or buyers. Report exact hash, bytes and observed rows from the consumed stream. Preserve the existing 16 frozen source-trace tests and add independently falsifiable tests. Run focused tests and exact-head hosted CI; preserve failures as failures. Do not merge a stacked review wholesale into main or reinterpret past proof.

## Status on registration
Code fix: PENDING. Adversarial test: PENDING. Independent exact-head CI: PENDING. Financial/capital/native commerce: NOT APPLICABLE. Decision remains HOLD / NO BID / NO DEPLOY; target US$3B T365 not achieved.
