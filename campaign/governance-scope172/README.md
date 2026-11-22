# OSCAL172 — conservative source-anchored applicability continuity

**Research-only. NO BID / NO DEPLOY.** This is a real executable scope-proposal generator, not source or reviewer authentication, a compliance engine replacement, a procurement offer or a financial business. Source protocol was committed first in `PROTOCOL.md` at `349185c88159a98b854443d4746a9e5ea6fa5134`. Original current-main baseline: `75f8f722c923e448d8f1fb44aa762b6ba0cd5a46`.

## Productive constraint addressed

The existing [OSCAL171 importer](../../research/governance_oscal171.py) correctly requires explicit applicability assignments for every catalog control. This proposed companion *prepares a reviewable carry-forward*, avoiding unnecessary new annotations for unchanged content and inventories **only if** previously explicit annotations and both catalogs match their independently held SHA-256 anchors. Any changed/added control, retired history or changed registered systems are visible. There is no implied official NIST system assignment or presumption that a publisher's prose identifies the correct regulated system.

A competent conventional hash-based script can perform the same continuity. No new algorithmic edge or human-hour savings has been measured, so this is a narrow tool, not evidence of a new Blue Sky flagship. A capable incumbent GRC provider may already provide stronger authenticated versioning and workflow. Incomplete authorization, privacy, legal applicability, schema coverage, RBAC, deployment, measured full costs and actual buyer value remain open.

## Operator (offline, source-only)

Use a unique create-only output path. Inputs require `schema=agi-alpha/governance-scope-continuity172/input-v1`, `before_catalog`, `after_catalog`, complete `before_scope`, `before_systems`, `after_systems` and the exact four `anchors` enumerated in the protocol. **Anchor digests must originate independently of the data being checked; calculating them from the same potentially altered input is not security.** The tool checks hash identity, not origin authority; signing and reviewer authorizations are outside scope.

```sh
python3 -B -m research.governance_scope172 --input /absolute/source-only-input.json --output /absolute/new-proposal.json
python3 -B -m unittest tests.test_governance_scope172 tests.test_governance_oscal171 tests.test_governance_impact140 -v
```

Output contains separate `provisional` rows, `review_required` exceptions (with null proposed scope), `retired` history and digest-bound source summaries. **Provisional means no new change has been detected, not that the old mapping was correct or newly authorized.** To obtain actual reassessment findings, authorized users must supply complete explicit `after_scope` and separately run the unchanged `governance_oscal171.assess`; this tool never grants approval or writes a system/ledger.

The [pinned NIST AI RMF official-source test](../../research/governance_scope172_official_t9.py) uses Git tag `usnistgov/oscal-content v1.6.0`, known Git blob `1f625a618448cec41f8f7fa8ea50bbaf7751bb82`. All 91 official control IDs are real and unchanged. The one changed control is an explicitly synthetic mutation; the 91 synthetic applicability labels represent **no actual policy or company**. Official-source validity of the OSCAL format is distinct from authenticated system applicability. This test is not an observation of 2026 NIST changes across releases.

## Admission decision

Compare competent human/conventional scripting, the strongest GRC provider, this provisional bridge and no-deploy. Current outcome: no measured competitive advantage; no evidenced buyer acceptance; no company eligibility or complete commercial cost. Do not present source compatibility as a procurement result or a US$3B annual profit contribution. No independent signing/finance/account custody is obtained through this work. Historical transition failures and all other owner branches remain unchanged. Merge, release and extracted-byte qualification are separate stages and should not be presumed from local/source tests.
