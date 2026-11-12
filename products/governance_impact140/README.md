# Governance change-impact instrument 140 — offline research prototype

This product is a **small working and reproducible subsystem**, motivated by the [Shared Services Canada 30 Oct 2026 public challenge](https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance), not an eligible tender response, compliance platform, certificate or paid service. The government states a Phase 2 **CAD $2M maximum contract** (potentially one or two awards), **TRL 5–9** qualification, closing **22 Dec 2026, 14:00 ET**. No funding/award/revenue is presumed.

From the repository root, run the frozen synthetic tests:

~~~sh
python3 -m unittest tests.test_governance_impact140 -v
~~~

Programmatic use:

~~~python
from products.governance_impact140.engine import assess
receipt = assess({
    "systems": [{"id":"example","tags":["finance"]}],
    "requirements_before": [],
    "requirements_after": [{"id":"R","version":"1","control":"log outputs","applies_to":["finance"]}],
    "evidence": [],
})
assert receipt["findings"][0]["status"] == "unable_to_determine"
~~~

CLI on *synthetic data only*: \`python3 -m products.governance_impact140.engine --input /tmp/synthetic.json --output /tmp/new-report.json\`. Outputs are deterministic; an independent party can recompute \`receipt_sha256\` over canonical output **excluding** that field. An SHA256 digest without an external trust anchor is **not** a signature and does **not** prove the source was authentic. Never include private AI-system data or signing keys in public artifacts.


Independent integrity checking is explicit and **requires externally preserved anchors**:
~~~python
from products.governance_impact140.engine import verify_receipt
# expected_input_sha and expected_receipt_sha come from a separate trusted record,
# never from the untrusted receipt being checked.
assert verify_receipt(receipt, anchored_receipt_sha256=expected_receipt_sha,
                      anchored_input_sha256=expected_input_sha)
~~~
Even a passing check does not authenticate a reviewer or prove compliance. A dishonest producer can replace a receipt and calculate matching new digests unless the expected digests were obtained independently.

Covered: rule add/modify/retire, scope matching, evidence provenance, changed-version invalidation, pending human review, deterministic output and error fail-close.

**Evidence reconciliation:** `evidence_reconciliation` reports the numbers of submitted, referenced and quarantined evidence identities. A registered but inapplicable assertion appears in `quarantined_evidence` with its source identifiers and `NO_COMPLIANCE_OR_REVIEW_APPROVAL`, instead of silently vanishing from the displayed findings. Each input evidence ID is accounted for exactly once across the referenced-ID set and quarantine. A single ID that is both historical and current is counted once. This diagnostic is **not** proof that the underlying claims or scope tags are true; inputs remain synthetic and unauthenticated. The prospective independent [reconciliation criterion](../../campaign/public-demand140/EVIDENCE_RECONCILIATION_20261112.md) supplements, but does not replace, the original frozen protocol. **Not covered:** authenticated reviewer identity, comprehensive audit-log chain, RBAC/data residency/deletion, policy-feed monitoring, enterprise API connectors, genuine AI/ML platform integration, real high-risk AI judgments, bilingual UI, actual tender eligibility/TRL or complete customer delivery.

The [frozen protocol](../../campaign/public-demand140/PROTOCOL.md) precedes this implementation and compares human conventional work, existing GRC integrators, an offline impact engine and no-deploy. The strongest real comparator and full buyer costs remain unmeasured. No native financial account or prospective capital funding action occurs. A tiny deterministic pilot cannot establish a transformational invention, scalable demand or the US$3B trailing-365-day complete-cost profit objective.
