# EIT192 — typed AppleDouble classifier for original-source qualification

## Scope and source freeze (before implementation)

Independent, additive read-only classification helper for the distinct EIT190 source-owner PR #480. It **does not modify or replace** EIT190, its exact source, frozen acquisition, historical failed live-source run #44507389309, or scores. Preselected archive remains Zenodo record 24120439, `AgarChestPhantom.zip`; an observed suspect `__MACOSX/.../._*.mat` member starts with the AppleDouble signature `0005160700020000`. No new archive selection or data acquisition is authorized by this classifier.

## Finite preregistered acceptance

Only classify an exact `__MACOSX/` plus `._` path as AppleDouble metadata when its **actual bytes** parse as AppleDouble v2 with valid header, descriptor table, entry identifiers, bounded ranges and non-overlap. Preserve exact member names, SHA-256 and sizes of metadata examined, record canonical counterpart presence, and retain all genuine MATLAB-looking paths (including malformed ordinary `.mat` members) for the original strict parser. Reject duplicate casefold paths, invalid Unicode normalization, unsafe names, symlinks and unsupported metadata. Do not delete or extract archive contents. This is **not** complete ZIP CRC validation, Zenodo manifest validation, EIT190 MATLAB parsing or calibrated physics.

Frozen offline regression cases: valid one/two-entry AppleDouble, magic/version, truncated headers/tables, filler/count, duplicate entry IDs, out-of-range/overlapping descriptors, size limit, correct and orphan counterpart classification, malformed metadata, wrong-path `._` treated as real content, invalid `__MACOSX` entry, traversal/backslash, duplicate folded paths, noncanonical Unicode, symlinks and create-only receipts. Failed outcomes are preserved without cherry-picking or retroactive repair.

## Acceptance and economic boundaries

Success permits only a prospective **owner-reviewed** EIT190 reader integration and requalification against the same preregistered original chest archive. It is not itself a successful EIT190 real-source run, physical-property reconstruction, AI breakthrough, cross-phantom generalization, recognized revenue, capital migration, or released system. Retain existing finance PR #40 authority/account/queue/signer and the qualified Connected014 release. No paid APIs, spending, outreach, private data, real transactions, account mutations, protected merge or production deployment. Decision remains HOLD / NO DEPLOY / NO BID. Complete-cost T365 US$3B remains unachieved.
