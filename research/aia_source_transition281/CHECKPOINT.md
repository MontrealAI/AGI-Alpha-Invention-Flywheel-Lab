# AIA source-transition 281 — November 25 checkpoint

**Original 281: FAILED. Scoped engineering diagnostic 281B: PASS (10/10 checks). Commercial: NO BID / NO DEPLOY.**

The existing governance components assume curated changes. This independent branch investigated actual official questionnaire changes as an upstream reassessment dependency. No private assessment or individual data was obtained. Original frozen protocol dfc54788d067ab5f323f8fff402e2232bc7a446a; exact source 81c1f478ae7badb1bec1b70f7814902c864b1bbf. [First failure](RESULT.json): the official survey has two non-answer HTML nodes with the same name, consultation-intro, in distinct consultation design and implementation panels. The original global-unique-name contract correctly rejected this input and remains failed.

[Separate diagnostic protocol](DIAGNOSTIC_PROTOCOL.md) at 247f921f8e91427355116dfb0695f32ec2008087 froze ancestry-qualified identities for duplicate HTML display nodes only. The [diagnostic source](diagnostic.cjs) at 87598bd197470cefc567984a030e51578a39b4d4 rejected both duplicate answer-bearing names and duplicates within the same display ancestry. [Original diagnostic result](DIAGNOSTIC_RESULT.json), 9c8ab9d28f2d6c3e9dac4ce7276ed5d9dd1d91dd, is preserved byte-for-byte. Both algorithms agree on all three pairs, and the fixed mutation tests pass.

| Official adjacent revision | Added | Removed | Modified full objects | Unchanged represented entries |
| --- | ---: | ---: | ---: | ---: |
| 2a518035 -> dab75e23 | 4 | 4 | 1 | 311 |
| dab75e23 -> b900dc7d | 0 | 0 | 3 | 313 |
| b900dc7d -> d4ce64c4 | 0 | 0 | 2 | 314 |

Each revision has 316 named elements, including panels and non-answer display nodes. A panel's full object includes its children, so modified objects are not independent changes. The 8 September 2025 commit addressed incorrectly merged data-type/data-source questions: the structural instrument flags four removed aboutDataType IDs and four new aboutDataSourceType IDs rather than assuming answer equivalence. The later two revisions changed the department choice definition, among other recorded objects. No answer transfer, scoring, legal or compliance claim was made. Scope is parsed pages/elements of the exact survey JSON, not SurveyJS runtime, transitive expression dependency analysis, duplicate JSON key validation, legal meaning, official calculator behavior or questionnaire-wide safe answer migration. The two implementations share the chosen identity contract; independent human approval is not established. The direct ordinary comparator tied. No novelty or labor saving claim.

## Reproduction
Retrieve four MIT-licensed source definitions (Crown copyright, Government of Canada; no government marks redistributed) at exact refs from PROTOCOL.md, verify their Git blob IDs in DIAGNOSTIC_RESULT.json (e.g. git hash-object), run node diagnostic.cjs with four local paths in that order. In this session the published function body was fetched and actually executed, with returned source blob identity checked. CLI wrapper/Node startup and hosted CI not exercised. Original wall 0.021s; diagnostic wall 0.295s, excluding source fetching, assistant work and publication. CPU and actual billing unknown.

## Updated commercial evidence
The official ISED program page modified 24 November now lists 8 December 2026, 14:00 ET, versus 22 December in historical repository records. The controlling CanadaBuys notice could not be independently retrieved; treat the earlier date as a planning boundary, not a verified tender amendment. Source: https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance
The potential CAD2M ceiling (up to 20 months, one or two awards estimated) is not an award, income or profit. One supplier may receive one contract per phase per challenge. TRL5–9 and Canadian business eligibility unverified. IBM's 14 October 2026 release already advertises inventory-to-control mapping, evaluation metrics and review assistance; Credo AI advertises existing policy packs and evidence workflows. Direct competent specialist using the official AIA, complete GRC/integrator, narrowly scoped research instrument and nonentry remain the alternatives. No new full-cost comparator measurement, buyer consent, eligibility, enterprise security or complete delivery established. Do not extend into another synthetic governance suite. The next meaningful use is source-bound linkage to real policy dependencies and official calculator verification with consented inputs only, if a consequential independently evidenced commercial residual exists. Otherwise choose a different opportunity.

## Acceptance matrix and ownership
- Achieved: actual four pinned public source definitions, original failure preserved, independently implemented structural comparison and fixed diagnostic, exact retrieved result byte comparison.
- Partial: source-change triage; no semantic transfer or comprehensive runtime verification; no standalone module/hosted qualification.
- Blocked: full government eligibility, acceptance, complete costs, buyer and authorized commercial delivery; original native financial-owner custody remains unverified.
- Failed: original global name identity protocol, not retroactively passed. No new paid operation; US$3B T365 target not achieved.
- Main 297a51c25c48031e1e6f964835f4dfae3ddb8023, release connected014-297a51c25c48031e1e6f964835f4dfae3ddb8023, workflow 45551095868 all three jobs success. Original overnight handoff retains separate owner. No main, financial owner source, accounts, obligations, earlier branches, guard or automations modified. No spending, credentials, outreach, transactions or deployment.
