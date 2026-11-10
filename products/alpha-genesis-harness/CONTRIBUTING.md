# Contributing to the HARNESS

Read the repository's canonical `AGENTS.md` and current `docs/harness/DEVELOPER_GUIDE.md` first. This product area does not replace the canonical enterprise runtime, account or financial history.

Submit a scoped branch and pull request against the current main branch. Describe the user-visible outcome, assumptions, source compatibility, actual tests and any remaining uncertainty. Preserve failures that explain a consequential result. Keep public artifacts free of credentials, private customer documents and personal account state.

Contributions intentionally submitted for inclusion in this product are offered under Apache License 2.0, consistent with section 5. Submit only material you own or are authorized to contribute. Identify copied/adapted third-party material and preserve its provenance and notices. A maintainer must review licence compatibility before inclusion. A contribution does not assign its copyright to the project or automatically grant proprietary relicensing rights.

New adapters need contract tests, cancellation/error/cost tests, current official API references and an honest live-test status. New mechanisms need declared inputs, outputs, effects, dependencies, costs and stopping rules. Tests authored by a candidate's developer establish development confidence; they do not replace independent acceptance.

Run the scoped tests and rebuild the release from committed source. Reconcile `THIRD-PARTY.json`, documentation and the acceptance matrix whenever scope changes. Do not add a hosted service, paid dependency, model credential, native ledger or new permission without appropriate authorization.

Use the project names descriptively. Modified distributions must not imply that they are an official MONTREAL.AI or QUÉBEC.AI release.
