# Governance Portable141 — operator and evidence boundary

**Purpose:** make the already merged Governance Impact140 research subsystem independently reproducible from downloaded, allowlisted, key-free bytes. It does not publish a government-ready offering, start a native enterprise, contact a buyer, authenticate a reviewer or create revenue.

The **Connected014** runtime source archives intentionally use a curated execution closure. Direct inspection of the freshly published `connected014-ee103269...` Actions release-assets artifact found **no Governance Impact140 engine/test files** in either source or key-free ZIP. An independent audit of the released finance package returned exit code 0, with **two packaged worlds and 104 registered jobs**; this was engineering reproduction only. Do not claim the governance subsystem was in that package merely because its source PR merged. The new standalone bundle is separate, research-only and contingent on its own CI.

## Build and verify offline

At a clean checked-out GitHub commit, using Python 3.12 and the standard library:

```sh
python3 -B -m unittest discover -s tests -p 'test_governance_impact140.py' -v
python3 -B -m unittest discover -s tests -p 'test_governance_portable141.py' -v
python3 -B scripts/package_governance_impact141.py build \
  --root . --archive /absolute/fresh/governance-portable141.zip \
  --receipt /absolute/fresh/RECEIPT.json \
  --source-commit "$(git rev-parse HEAD)"
```

To verify a downloaded archive, obtain expected archive SHA-256, manifest SHA-256 and commit from an **independently trusted** GitHub run/commit record, not just from the untrusted archive's self-description:

```sh
python3 -B scripts/package_governance_impact141.py verify \
  --archive /absolute/downloaded/governance-portable141.zip \
  --expected-sha256 EXPECTED_ARCHIVE_SHA256 \
  --expected-manifest-sha256 EXPECTED_MANIFEST_SHA256 \
  --expected-commit PINNED_COMMIT_SHA \
  --extract /absolute/fresh/clean-source
cd /absolute/fresh/clean-source
python3 -B -m unittest discover -s tests -p 'test_governance_impact140.py' -v
```

The [standalone qualification workflow](../../.github/workflows/governance-portable141.yml) builds, uploads, downloads, verifies and executes the clean bundle, then runs an actual synthetic-input CLI. The downloadable Actions artifact contains only the research engine, existing tests, protocol/README and manifest. No signing keys or private accounts are shipped. The GitHub run itself is not a buyer acceptance decision or independent signature authority.

**Commercial selection remains NO BID / NO DEPLOY.** The same four arrangement alternatives in [Public Demand140](../public-demand140/PROTOCOL.md) remain: competent human conventional service, incumbent GRC/integrator, prototype with external authorized review, and no deploy. TRL, formal supplier eligibility, interface compliance, costs and demand remain unverified. Unknown billing stays unknown. The USD3B trailing365 complete-cost profit target is not attained. Historical failures and original financial-account ownership are untouched.

Evidence criterion: same source commit, complete test denominator, source SHA/ZIP digest, exact archive member allowlist, no traversal/symlinks/duplicates, independent clean operation and explicit failed-run preservation. The downloadable artifact does **not** constitute deployment.
