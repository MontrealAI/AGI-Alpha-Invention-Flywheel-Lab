# Agent Skill Provenance 283 — 2026-11-25

## Decision: retain source evidence, no deploy

The public [Agent Skills PURL proposal #867](https://github.com/package-url/purl-spec/issues/867) identifies a concrete interoperability need: versionless logical skill identity is not necessarily exact artifact identity. The fixed [protocol](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/a8f094eb3e8e6a1618ac53f9cb5a89c08aa3403c/research/agent_skill_provenance283/PROTOCOL.json) selected current and first-parent public Git commits for Anthropic, OpenAI and Vercel. Executable comparison functions were publicly frozen at 30aa3f6b7d674fcaa79fe6be12b33febedfbb8f9 before comparative evaluation. First connector attempt hit the tool-call limit with no durable pair results; see INTERRUPTION.md. The same fixed comparisons were then completed in separate batches with unchanged source and acceptance. No revised seeds or substitute data.

69 common skill directories, zero disagreements between tracked Git tree identity and separately ordered tracked leaf path/mode/type/object identity. Four changed directories had the same valid top-level name and absent top-level version at both revisions: docx, pptx, xlsx, skill-installer. The xlsx SKILL.md Git blob itself was unchanged while the directory tree changed. Versionless logical identity or a SKILL.md-only digest is insufficient to identify every tracked source revision. This does not disprove version-bearing PURL, establish executable behavior changes, verify installed bytes or authenticate publishers. The Git objects were accessed via the public connector; not every file was downloaded. No third-party skill code executed.

The strongest accessible incumbent is not name-only identification: [Vercel skill-lock.ts](https://github.com/vercel-labs/skills/blob/57217cf86ba38148a57af9e90d14a4c049558330/src/skill-lock.ts) already implements source commits and folder-tree hashes, [skill-hash.ts](https://github.com/vercel-labs/skills/blob/57217cf86ba38148a57af9e90d14a4c049558330/src/skill-hash.ts) implements framed normalized SHA-256 installed-content hashing under declared exclusions and symlink rules, and [local-lock.ts](https://github.com/vercel-labs/skills/blob/57217cf86ba38148a57af9e90d14a4c049558330/src/local-lock.ts) uses content checks for tracked/modified status. Source inspection only, no execution of those tools. This already supplies the pertinent identity mechanism. Do not market the research comparator as a novel complete supply-chain product. A possible remaining opportunity is a cross-registry interoperable binding between declared identity, exact installed bytes and independently validated execution/acceptance evidence; that residual is not established, and strong lock, SBOM and attestation alternatives must be included.

## Commercial selection

- Agent-skill metadata interoperability: [NLnet CodeSupply second call](https://nlnet.nl/CodeSupply/) closes January 3, 2027, 12:00 CET. Its [FAQ](https://nlnet.nl/codesupply/faq/) states an initial EUR5k–50k proposal range, EUR60k cumulative cap, payment after completed milestones, expected selection of three to five months after deadline, open-source delivery and a required European dimension (exceptional non-European proposals can be considered). Eligibility, applicable rights, competitive distinct contribution, complete cost and funding availability have not been established. No applications, outreach or registry changes. A grant is not customer demand or unrestricted current cash.
- Maven license inheritance: [PurlDB issue tracker](https://github.com/aboutcode-org/purldb/issues?q=is%3Aissue+is%3Aopen+license) shows real open metadata issues and ongoing Maven/license curation; do not duplicate an unverified residual or infer a paid order.
- Foundational open infrastructure: [Sovereign Tech Fund](https://www.sovereign.tech/programs/fund/) requires proposed work above EUR50k and excludes prototypes; prevalence and eligibility of our work are unestablished.
- Non-entry remains the preferred current action. No eligible paid outcome, complete-cost margin, actual funds or reachable volume established. No native operating account was opened. No commercial or recursive-discovery advantage claimed.

Measured batch wall time including retrieval: 10.835 seconds for the five persisted batches; first interrupted attempt and additional research/publication excluded. CPU, whole-episode resources and actual billing unknown.

## Release and ownership refresh

Main 3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c. Refreshed AGENTS.md, Blue Sky charter/mechanisms/candidates, developer/operator/resource guides, exact release workflow and the six durable overnight022 handoff/proof files. Native owner heads candidate 3981b182513abbba1c2ab1102f94732c453422fa, integration 7d75766401adede49afd2427be82eb0302934b80, repair 9eb4441c82177a141096bb071ee757b78c83aeb6 unchanged on inspection. No task checkpoint or custody transfer established.

Previous head cef4d1c release [45658904349](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45658904349) engineering passed, publication failed at EXACT_MAIN_QUALIFICATION_FAILED:omega-economy-v4.yml, operation skipped. The exact-head Omega run 45658904435 was cancelled at 17:22:04 UTC following creation of a newer head run at 17:21:45 UTC; omega-economy-v4.yml declares branch-shared concurrency with cancel-in-progress true. Evidence is consistent with supersession, not proof of the platform's internal cancellation actor. Preserve failure. No stale rerun and no gate weakening. Earlier 1bdac817 publication HTTP 502 also remains preserved.

Current head [45663937453](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45663937453) passed qualification and publication. [Public release](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/connected014-3aa1fd3373e4d44969c26d78c6f3dfd8c7274f6c) published at 18:18:48 UTC, not a draft, with 16 assets. GitHub reports source ZIP digest sha256:1ec89847239b8efde24a62b885c5a587f49cb0598978c98646487c684aaf3a2a; manifest digest sha256:6ec34b9bbaada38e2145035755fc21296e585a0eb48c07fe0c1aa39fcc60a3a2. These are publisher API-reported digests, not independent download checks. Actual downloaded-operation job 139416043932 queued at inspection; do not infer success. Do not push competing main updates or start another release merely to manufacture evidence.

| Stage | Verdict |
|---|---|
| First connector attempt | INCOMPLETE, preserved |
| Same registered input continuation | PASS, 3/3 pairs; 69 comparisons |
| Versionless tracked identity counterexample | ACHIEVED, 4 observed cases |
| Novel or superior complete mechanism | NOT ESTABLISHED; strong incumbent already supports relevant identity checks |
| Independent installed-byte qualification | NOT RUN |
| Current main engineering/publication | ACHIEVED |
| Current main actual downloaded operation | PENDING |
| Native financial owner custody/P0 integration | BLOCKED / UNVERIFIED |
| New commercial result/native profit | NONE / null |
| US$3B trailing-365-day complete-cost profit | UNACHIEVED |

No account or ledger changes, new spending, private data, real transactions, outreach, deployment or automation modifications. Next: retain this evidence, avoid another identity-only suite, and prioritize a distinct consequential accepted outcome with accessible production inputs and actual reachable paid need. Continue monitoring current release gate without disturbing other owners.
