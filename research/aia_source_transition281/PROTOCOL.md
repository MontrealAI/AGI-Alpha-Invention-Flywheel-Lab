# AIA source-transition 281 — frozen review-triage experiment
Registered 2026-11-25 against main 297a51c25c48031e1e6f964835f4dfae3ddb8023. Independent research branch; no native financial or existing governance-owner writes. No bid, account, private responses, deployment or spending.

## Decision and alternatives
SSC's published 30 October 2026 governance challenge asks for traceable change impact and reassessment; program page modified 24 November now lists 8 December 2026 14:00 Eastern, while historical repo materials list 22 December. Controlling CanadaBuys notice must be checked separately; do not silently overwrite past records. Potential CAD2M contract, no award. Compare: (1) direct competent human specialist using official AIA and full review; (2) established GRC platform/integrator (IBM, Credo AI); (3) source-version-aware review triage alongside existing governance tools; (4) no bid/deploy. Considered separately the Open Food Facts idea challenge (no verified cash) and ISC high-altitude backhaul (requires physical means outside this experiment). Select (3) as a missing-means construction only, not a commercial winner.

The existing 140/152/159/171/197 components assume curated requirement changes or synthetic records. This experiment uses the actual bilingual MIT-licensed Canada-ca/aia-eia-js survey definitions, not citizen/employee responses. It identifies changed definitions and context for reviewers before any attempted reassessment. A structural diff is not legal interpretation or proof that unchanged answers remain valid. Full official calculator and human validation remain required.

## Exact input and finite stopping rule
Retrieve src/survey-enfr.json at four exact public revisions:
2a5180351fb6c47d389a7ab01bacb944c911d35a
dab75e23cbf792f68c9e89891e3ad2fc261a5ba0
b900dc7d21126a69a7661a90b8b57d37c8a52231
d4ce64c4e6c1a254d38108a20b8d7e60a92389e8
Compare each adjacent pair once, preserving all results and input blob IDs. The first two revisions are associated with public bug fixes, not fresh blind holdouts. Do not tune cases after execution.

## Acceptance
T1. Inventory each named element reached by recursively walking pages/elements; reject duplicate names, unsupported unnamed nodes, missing arrays or invalid roots. Keep entire raw object identity as canonical sorted JSON including choices, bilingual strings, conditions and scoring metadata. Record ancestor page/panel context (excluding sibling arrays), order path and root settings. Unsupported nested schema is a failure or explicit incomplete scope; no silent omission.
T2. Exhaustively report added, removed, modified definitions and modified context/order, separately; unchanged only means equal represented bytes. Independent direct conventional comparison over the same inventory (separate traversal and equality implementation) must agree on every category.
T3. Validate a full-document structural change is either captured in element/context/root/order changes or flagged as unallocated structural change; no silent equality. Track root and page metadata changes.
T4. Deliberately alter a definition choice/text, root setting and ancestor metadata in synthetic copies of a real input; identify changes without modifying original inputs. Do not claim an adversarial change is a real policy change.
T5. Never transfer, approve or score an assessment. Preserve unknown complete costs, actual buyer demand, TRL and eligibility; no original financial account action. Report structural coverage scope and ordinary comparator; no algorithmic superiority if tied.
One execution with all three adjacent pairs and the fixed mutations; if unsupported shape fails, preserve failure and revise only after diagnosis. Source and result hashes/identities, measured local telemetry, original outcome and exact reproduction instructions. Independent algorithm is authored in same workstream, not independent human approval.

## Sources
https://github.com/canada-ca/aia-eia-js (MIT; Crown copyright, no government marks reused)
https://open.canada.ca/aia-eia-js/
https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance
https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-189-51083224 (controlling notice not retrievable in this session)
https://www.ibm.com/new/announcements/new-in-ibm-watsonx-governance-govern-ai-agents-as-you-build-expand-accountability-and-streamline-compliance
https://www.credo.ai/solutions/risk-management
