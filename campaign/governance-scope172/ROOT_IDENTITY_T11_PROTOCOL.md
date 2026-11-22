# OSCAL172 T11 — prior catalog root-identity transfer (prospectively frozen)

Registered after the exact-head T1–T10 [PASS](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/43729950000), before adding this new adversarial test or changing source. Source head for the adversarial test: `0b36c8c31114849bf919adb421eb0ce6a66d36d3`. Original `PROTOCOL.md`, fixed tests and official NIST T9 remain untouched.

## Threat
`semantic_sha256` in OSCAL171 hashes the control plus ancestor group content, but does **not** include the **catalog root UUID**. A distinct publisher/catalog with copied control IDs/content could otherwise inherit prior applicability proposals despite different source authority/identity. An external integrity hash verifies each catalog's bytes but does not establish that *these two catalog identities are equivalent for scope continuity*.

## Frozen T11 acceptance
Use the existing two-control synthetic catalog and exactly the same registered system inventory and previously explicit scope. Replace *only the after catalog root UUID* with a different, syntactically valid canonical UUID, and independently re-anchor the after catalog. Retain unchanged titles, control content, group context and metadata version. All copied controls must be `EXPLICIT_NEW_SCOPE_REVIEW_REQUIRED` for reason `CATALOG_IDENTITY_CHANGED`, with **zero** provisional carries and no approvals or native effects. Unchanged-UUID original T1 must continue allowing two provisional suggestions. An altered source with stale external anchor must still fail.

Run unchanged old suite plus this one new case against original source first, preserve genuine failure if found. Only then repair narrowly: compare full root UUID before allowing continuity. Do not silently treat distinct public issuer catalog identities as equivalent. This is source-identity conservative engineering, not publisher signature validation. Re-run original and T11 and official NIST data without changing any original acceptance or original failed traces. No claims of real legal scope, buyer, financial authority, profit, original account access or runtime release.
