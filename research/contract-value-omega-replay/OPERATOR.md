# CONTRACT VALUE Ω — supplemental buyer-side source replay

Dependent draft qualification for [commercial product PR #405](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/405). Independent protocol frozen **before** test implementation at commit `1ed236ee78cd6c069f3604f7054a2ad330b66004`. The product's original owner maintains its source and integration. This adds only a new verifier, a separate adversarial test suite and its own CI.

## Why an ordinary hash isn't financial proof

The original checker verifies five input SHA-256 hashes, internal line arithmetic, CSV/report consistency, currency totals, and zero recorded collections. However, someone who can rebuild the output can also recompute its unkeyed SHA-256 manifest. Unless the verifier rederives the expected charges from the supplied contract and independent usage rows, a financially false amount can remain arithmetically and cryptographically *self-consistent*. The six registered cases expose this boundary rather than falsely treating hashes as signatures.

## Run locally, without a service or external API

Use the **same** buyer-authorized original input folder and a new offline output folder:

```sh
python3 -m products.contract_value_omega.run --input products/contract_value_omega/demo --output /tmp/contract-review
python3 -m products.contract_value_omega.verify --input products/contract_value_omega/demo --report /tmp/contract-review
python3 -m products.contract_value_omega.verify_replay --input products/contract_value_omega/demo --report /tmp/contract-review
python3 -m unittest discover -s tests -p 'test_contract_value_omega_replay.py' -v
```

Only the included fictional demo can be put into public CI. Never upload customer inputs or buyer report files to GitHub. For real buyer use, execute on buyer-owned encrypted storage with authorized contract data and verify the complete supplier invoice, approved quantity, credit, payment and signed effective terms manually.

The supplemental checker independently recomputes per-line expected charges, rate ceilings, chronological shared usage quotas, repeated whole-document status, payment classes, source provenance, candidate quantities and review classifications without calling `core.audit()`. It reuses the product CSV parser and its deterministic presentation writer; thus it is **not** a completely independent accounting implementation, external audit, or cryptographic signing authority. Output files are re-rendered into an ephemeral local directory and compared byte-for-byte, including buyer HTML and supplier Markdown packets. No vendor contact, private ledger mutation, money movement or collection is performed.

## Immutable test history and acceptance boundary

- Frozen protocol: `1ed236ee...` (before code).
- Preregistered tests + workflow before the corrective module: `fcdacbfe...`. First hosted execution [#43917117989](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/43917117989) **FAILED** with missing optional verifier; preserve that genuine failure.
- Initial implementation at `f773d5d8...`: hosted [#43917356684](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/43917356684) **FAILED one positive test** because the original writer preserves input-manifest insertion order in visible HTML, whereas canonical JSON sorts keys. Not a financial success; source-order repair applied prospectively at `2d223af3...`.
- The specific forged candidate is built from the same ten fictional source lines: its original fixed rate/usage expected charge on line A-001 is forcibly set to zero, gross/net and all downstream outputs are consistently recalculated, and the unkeyed output hashes regenerated. The old verifier is required to **accept** the self-consistent lie, while the new source-derived verifier must reject it.
- Positive acceptance: preserved 10-line fictional customer demonstration, unchanged CAD 20,700 screened candidates / CAD 16,700 payment-record subset / CAD 0 recoveries; original checks and supplemental checks both pass. All negative cases must reject without retroactive threshold changes.
- Hosted exact-head result must be checked in the [PR #407 Actions](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/407/checks) before any completed/qualified claim. A successful CI run does not establish a paid engagement, refund entitlement or a new scientific capability.

**External value proposition:** a buyer can independently check the local structured reports before review. The product itself is a private-sector paid diagnostic hypothesis, competing with skilled spreadsheet/ERP auditors and recovery-audit firms. There are no real customer contracts, collected fees or evidence of reproducibly profitable customer acquisition. This branch does not merge into main or touch the protected native-capital account.

**Decision after qualification:** present this supplement to PR #405 owner for safe source review. Do not silently swap the existing verifier, weaken original test failures, or claim deployed release until normal integration, published downloadable buyer assets and a clean independent downloaded run are completed.
