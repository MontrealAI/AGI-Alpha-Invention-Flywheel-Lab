# Governance176 — independent reviewer-action provenance (research)

A narrowly scoped executable check against [the 30 October 2026 official Shared Services Canada challenge](https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance), particularly mandatory outcomes 4.4 (authorized assurance artefacts) and 5 (reviewer validation, rejection, modification and annotation). This is **not** a tender response, full OSCAL/RBAC platform, certified assessment, buyer proof, commercial sale or TRL5–9 proof.

The existing `products.governance_impact140.engine.assess` generates **pending** findings and source/receipt SHA-256 identifiers. This additive verifier accepts only an **externally anchored** JSON trust record and expected source/receipt hashes, verifies Ed25519 reviewer signatures through installed OpenSSL, checks the action targets a current pending finding, exact original requirement version, evidence ID, tenant and authorized reviewer scope, and emits only a provenance report. Original findings do not change and `compliance_authorized` remains false. Real organizational trust, assignment, identity and clock must come from independent governance processes, not from this program. No key is generated or stored by the program; tests create ephemeral simulated test keys solely in a private temporary directory.

## Reproduce

From the exact source checkout with Python 3.12 and OpenSSL 3.x on an unprivileged machine:

```sh
python3 -B -m unittest -v tests.test_governance_review176
python3 -O -B -m unittest -v tests.test_governance_review176
python3 -B -m unittest -v tests.test_governance_impact140
```

Use an authorized, independently obtained reviewer trust JSON (no private key); send it separately from the untrusted action bundle. Supply its canonical SHA-256 through an independently trusted channel, and the original Impact140 receipt and input anchors separately from the report. A representative call (only with synthetic input) is:

```sh
python3 -B -m research.governance_review176 \
  --bundle /absolute/synthetic-review-bundle.json \
  --trust /absolute/approved-public-trust-record.json \
  --expected-trust-sha256 TRUST_DIGEST_FROM_SEPARATE_AUTHORITY \
  --expected-receipt-sha256 ORIGINAL_RECEIPT_DIGEST_FROM_SEPARATE_AUTHORITY \
  --expected-input-sha256 ORIGINAL_INPUT_DIGEST_FROM_SEPARATE_AUTHORITY \
  --at-utc 2026-11-18T15:00:00Z \
  --output /absolute/new-key-free-action-receipt.json
```

JSON schemas are intentionally exact. Statement: `schema,decision_id,organization_id,system_id,requirement_id,requirement_version,evidence_id,source_receipt_sha256,source_input_sha256,decision,issued_at_utc,expires_at_utc,note`; valid actions `validate,reject,annotate`. Signed bytes are canonical sorted JSON, compact separators, UTF-8, no NaN, as returned by the source's `canonical` function. `bundle` has `schema,source_receipt,decisions`; each decision holds `reviewer_id,statement,signature_b64`. Trust record: `schema,organization_id,reviewers`; each reviewer holds `reviewer_id,role,systems,requirements,public_key_pem,revoked,valid_from_utc,valid_until_utc`. An externally managed reviewer signs the exact canonical statement using Ed25519. **Never include a private key in inputs, GitHub artifacts or a public repository.**

## Independent verification limitations

Positive tests prove the implementation rejects the registered synthetic attacks with a real cryptographic verifier, **not** that an organization has granted a person's actual authority. A malicious bundle that supplies its own matching public-key trust record and hash is not authentic; the operator must independently pin the trust digest. The user-supplied UTC clock is not attested. This prototype rejects duplicate decision IDs and targets **within one submitted batch**, but **cannot reject a previously accepted action on a later invocation** without an external durable, access-controlled append-only decision register. Revocation updates and identity lifecycle must likewise be managed outside this verifier. The tool does not edit a source finding, handle real private AI-system data, authenticate the issuing government, or provide the complete native risk, enterprise APIs, security/residency or bilingual requirements.

Strong alternatives include signed conventional records supervised by competent reviewers, existing GRC/AI-risk products with RBAC and full audit operations, this scoped offline tool, and no deployment. The incumbent advantage and complete costs remain unknown. No external buyer/award/revenue, native financial action, independent recipient acceptance, release or US$3B complete-profit achievement is claimed. Original financial P0 and other research owners remain untouched. [Frozen prospective protocol](PROTOCOL.md).
