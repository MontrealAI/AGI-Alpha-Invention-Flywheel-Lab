# Operating IGNITION safely

The public GitHub qualification uses public, synthetic missions. Operate customer work separately in a private, owner-controlled environment. Before submission, agree on what the operator may read, what the model may receive, what outputs the customer can keep, and the retention period. Minimise the material submitted. Keep state on an encrypted, access-controlled volume. A collaborator with access to that volume can read the mission. Local browser access is a trust boundary, not tenant isolation.

## Mission and evidence boundaries

Treat source documents, retrieved text, model completions and artifact input as untrusted data. A sentence in a source cannot consent to another fetch, add a tool, expand the execution budget, choose a recipient or grant publication. A file digest identifies bytes; corroborate the source identity and independently test any claim on which acceptance depends. Inspect the actual conditions in a receipt before reusing it for another mission.

Model configurations require an explicit, authorized inference route. Never enter API keys in mission text, artifacts, issues, or Actions settings for this workflow. Use a clean profile for demos. Keep database files, journals, backups, customer text and model transcripts outside Git. The public model job uploads one named synthetic-trial receipt; review its fields and the exact workflow source before authorizing customer-specific changes to the publication boundary.

## Retention, deletion and incidents

For a retention agreement record the owner, expiry, storage location, backups and any copies delivered to the recipient. At expiry, the owner should stop the local service and remove the complete authorized mission store and any exports covered by the agreement, including database sidecar files and backups at their agreed expiry. Where a store contains several customers, migrate or isolate it before erasing anything. Erasing a file on a shared disk alone does not guarantee physical media sanitization. Confirm the scope before destruction. Quarantine suspicious evidence away from the working store. Preserve only the evidence necessary to investigate under the applicable agreement.

## GitHub qualification boundary

The workflow checks out the exact candidate commit into a standard ephemeral GitHub-hosted job. Checkout credentials are not persisted, external actions are pinned to the immutable identities also used by HARNESS, and the token receives read-only repository contents permission. Qualification uses ordinary pull-request events, no environment secrets and no deployment step. The two jobs distinguish application correctness from the outcome of the live model trial. A model trial that cannot execute or fails acceptance must be inspected as such even if the application tests pass.

Anyone who can change the workflow or qualification scripts can change what those scripts claim, request or upload. Review changes to these files alongside review of the executable and the oracle. A public PR job must never receive confidential customer inputs, host credentials or private state. Authentication, multi-tenant isolation, remote TLS termination and abuse controls require their own qualification before offering a hosted customer service.

## Engineering references

- [OWASP Top 10 for Agentic Applications (2026)](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- [OWASP GitHub Actions Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/GitHub_Actions_Security_Cheat_Sheet.html)
- [GitHub guidance on pull-request workflows and trust boundaries](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)
