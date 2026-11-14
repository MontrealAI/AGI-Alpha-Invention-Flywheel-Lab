# Governance Linked Portable158 — clean, key-free research download

**Purpose:** carry three already implemented, unchanged synthetic engines as one independently verifiable package: governance change-impact140, first-party raw-case risk152 and linked requirement-version reassessment153. Compared with the prior Impact140-only portable141, this allows a recipient to recompute an adverse synthetic quality signal after a stricter policy change using one extracted source tree. It does **not** establish compliance, regulated-system suitability, authenticated reviewers, a standards API, enterprise integration, TRL 5+, a buyer, or paid demand.

**Primary expressed-need source:** Shared Services Canada's official 2026-10-30 public AI-governance challenge, [closing 2026-12-22 at 14:00 ET](https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance). The published Phase 2 CAD2M ceiling is neither a purchase of this source nor revenue. Official CanadaBuys solicitation and amendments control any future proposal; no bid or outreach is authorized.

## Qualify without installing anything or providing real/private data

From an exact checkout, run:

```sh
python3 -B -m unittest discover -s tests -p test_governance_linked_portable158.py -v
python3 -B -m unittest discover -s tests -p test_governance_native_reassessment153.py -v
python3 -B scripts/package_governance_linked158.py build --root . \
  --archive /absolute/new/source.zip --receipt /absolute/new/RECEIPT.json \
  --source-commit FULL_40_CHAR_GIT_COMMIT
```

Keep the **receipt separately and independently** of the untrusted ZIP. Verify using the exact expected SHA-256 digests and source commit **taken from that separate receipt or source-bound workflow outputs**, never from a received ZIP's own manifest:

```sh
python3 -B scripts/package_governance_linked158.py verify \
  --archive /absolute/new/source.zip --expected-archive ARCHIVE_SHA256 \
  --expected-manifest MANIFEST_SHA256 --expected-commit FULL_40_CHAR_GIT_COMMIT \
  --extract /absolute/new/clean-tree
cd /absolute/new/clean-tree
python3 -B -m unittest discover -s tests -p test_governance_native_reassessment153.py -v
```

The exact-head `.github/workflows/governance-linked-portable158.yml` independently downloads the previous job's key-free artifact into a second clean job, reruns all three original suites and executes the **real** extracted 153 CLI using the original frozen synthetic sample. It verifies a changed threshold produces an adverse signal while governance approval stays *unable to determine*; it does not invent a compliant certificate. A passing ZIP hash without a separately trusted SHA is not independent authenticity.

## Decision after this finite construction

The stronger complete alternatives remain a competent human governance team with conventional scripts, established GRC/AI-risk solutions plus integrations, internal construction and no purchase. This package does not compare their measured costs, speed or enterprise scope. **No-deploy/no-bid remains the decision** until legitimate eligibility, baseline comparative acceptance, integration/permissions, real buyer terms, complete costs and genuinely available capital are established. No native financial account was opened, credited or migrated; never import this package as a financial authority.

The governing [preregistration](PROTOCOL.md) was committed before the package implementation. The prior Portable141 and Native153 exact-head qualifications and their historical negative outcomes remain unchanged. All missing commercial facts remain UNKNOWN, not zero.