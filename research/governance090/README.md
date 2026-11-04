# Governance090 — Trace policy change to affected AI systems, not imagined compliance

**Research prototype / public fixtures / NO BID / NO DEPLOY.** The implementation is a narrow, executable missing-means probe for a published real Canadian procurement challenge. It is not an actual commercial contract, a legal assessment, a production governance system, a TRL 5 prototype, a qualified autonomous agent, a new AI governance competitor, or part of the canonical financial operator.

**Public buyer-side requirement:** Shared Services Canada's 30 October 2026 [AI decision visibility, traceability and compliance governance challenge](https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance) has an advertised 22 December 2026, 14:00 Eastern closing date. It asks for continuous change impact on registered AI systems, interoperable governance metadata, traceable evidence, controlled access, reassessment and human review. This is a **competitive opportunity**, not buyer acceptance, paid work or supplier qualification. The government describes up to CAD 2 million for each Phase 2 award (up to 20 months; estimated 1–2), with no award guarantee. Its stated requirement for a demonstrated existing **TRL 5–9** solution is **not met by this stand-alone source prototype**. The Canadian-incorporation/SME/R&D/workforce rules are not verified here.

## An executable instrument

`research/governance090/impact.py` implements a small, deterministic typed graph:

```
requirement version → control → registered AI system
                    ↘ review assertion + evidence digest + externally pinned event-chain tip
```

Each explicit change to a requirement marks affected systems, invalidates prior matching positive review assertions, retains retired requirements as explicit review-needed records and exposes an ordinary complete-scan comparator. Missing or negative evidence never yields a positive finding. The fixture role gate prevents unauthorized test actors and cross-tenant reviewers from writing an assertion. The journal's SHA-256 hash chain can detect mutation **only against a separately retained correct tip**. It does not establish who a person is; a caller can impersonate a fixture username, and there is no live SSO, protected key, API or privacy-enforcement layer. The input requirement text is manually supplied; its correct legal interpretation and document source are not checked. The field `qualified_compliance` is always `false`.

To exercise the eight frozen source-level development/confirmation/adversarial checks:

```sh
python3 -m unittest tests.test_governance090 -v
```

For a local, synthetic CLI experiment (no financial operation):

```sh
python3 -m research.governance090.impact --spec /absolute/example-spec.json --revision /absolute/revision.json --output /absolute/new/result.json
```

The spec is one JSON object with fields `tenant`, `requirements` (id,text,status=active/retired), `controls` (id,requirements), `systems` (id,controls), `reviewers` (actor-name mapped to tenant,roles). Revision is an object containing `requirements`, with the **same set of IDs** and explicit retirement rather than deletion. Ambiguous duplicate JSON keys are rejected. All inputs and output are synthetic/public. CLI refuses to overwrite any existing output. A separate application must implement real user identity, authenticated update authority, persistent append-only storage, appropriate security and enterprise integration before genuine use.

## Strong complete outside options

1. **Complete enterprise AI-governance platform** from a competent established provider (e.g. Microsoft, IBM or a specialized governance vendor): may already cover most mandatory requirements. Requires exact offered-feature, security and total-price assessment; neither advantage nor a supplier agreement is established.
2. **Narrow traceable impact engine sold through an incumbent platform**: lower possible integration burden, but not a standalone eligible submission; partner rights and demand remain absent.
3. **Competent human governance teams using ordinary software**: may already maintain change control, approval trails and documented compliance. They are not artificially slowed; realistic labor, quality, security, supervision and review cost are unknown.
4. **No bid/no deployment**: current chosen route pending the actual missing production capabilities and verified eligibility.

A source-level pass establishes only that authored graph fixtures behave as preregistered. It cannot price services, model actual buyer choices, establish relative capabilities, supply verified evidence sources, certify legal compliance or establish a profitable scalable venture. No new seed capital, invoice, real transaction, borrowed financing, model API or account has been introduced. The existing original native-capital owner and every liability remain untouched.

## Actual acceptance and next constructive gate

See [pre-implementation preregistration](../../campaign/governance090/PROTOCOL.md). Technical eligibility: all fixed D1–D4, H1–H2 and A1–A2 tests pass, and the reverse graph agrees with a separate ordinary full scan. A stronger ordinary implementation may tie; this is not a new algorithmic advantage.

**Next material gate:** Demonstrate justified mapping from an actually versioned public Canadian policy document to a real registered-system inventory with independently reviewed ground truth and strong established governance alternatives, then add all mandatory interfaces/security/retention/human-review and measured total costs. Testing on the official challenge's confidential or internal systems is not authorized. No real proposal or outreach is performed under this mandate. The active US$3B trailing-365-day complete-cost profit target remains unachieved and cannot be inferred from the disclosed public procurement cap.
