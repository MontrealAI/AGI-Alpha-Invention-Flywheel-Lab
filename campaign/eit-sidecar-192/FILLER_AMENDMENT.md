# EIT192 prospective source-format correction — Mac OS X AppleDouble filler

**Frozen before changing the parser or running new cases:** parent EIT192 source `86ec3a6c3ce14b53f7e1fa73085a8385e763e7bb`, existing 16/16 focused tests and 16/16 PR workflows. This is a new engineering amendment, not retroactive qualification of earlier code, source archives or EIT190.

## New independently identified failure mode

The original EIT190 failed archived member `__MACOSX/AgarChestPhantom/Data/._2o2_AgarChestPhantom_Inc_missingPiece_1.mat` has a recorded first-16-byte header `00051607000200004d6163204f532058`, which decodes to AppleDouble-v2 magic/version followed by `Mac OS X`. The current EIT192 parser insists the 16-byte home-filesystem/filler field is all zero. Authentic macOS ZIP AppleDouble headers also use **exactly** `b"Mac OS X        "` (16 bytes). The present source would reject that valid variant, so previous fixture-only passes are not source-format acceptance.

References: [RFC1740 AppleDouble format](https://www.rfc-editor.org/rfc/rfc1740), [AppleDouble v2 layout / macOS ZIP examples](https://github.com/fadden/CiderPress2/blob/main/DiskArc/Arc/AppleSingle-notes.md), [macOS header example](https://github.com/abenori/TeX2img/blob/master/AppleDouble.cs). The observed prefix alone does not prove the entire original resource fork is valid; the remaining descriptors and complete archive must still pass independent checks.

## Frozen prospective change and tests

Permit only two exact 16-byte field forms: 16 NUL bytes (existing valid fixtures) or `Mac OS X` followed by eight ASCII spaces (documented macOS ZIP form). Reject arbitrary home-filesystem strings, truncation, case/padding variations, altered signatures, descriptor corruption and unsafe archive paths. Preserve the current explicit v2 magic/version and descriptor length/range/overlap enforcement; do not relax genuine .mat parsing or drop metadata from accounting.

Add synthetic regression for the exact macOS field and negative near misses, retain the 16 original tests, and qualify the changed exact head with the existing public standard runner. Do not select, replace or score scientific source data; do not modify EIT190's owner branch or finance/native ledger. Any actual-source qualification is a separately registered future experiment, not a retroactive pass. Previous published EIT192 exact-head success and EIT190 live-source failures remain immutable historical facts.

**Acceptance:** updated fixture-only parser correctly accepts two documented fillers and refuses variants; exact-head offline/CI checks pass. Original chest real-source, reconstructed conductivity, external value, paid demand, capital migration, protected merge and release remain unqualified. Decision HOLD / NO DEPLOY / NO BID; US$3B trailing-365 complete-cost profit unachieved.
