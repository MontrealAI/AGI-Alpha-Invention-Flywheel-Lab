# JSON contracts (version 1)

All serialized records use UTF-8 JSON. This file documents the small kernel's actual interface, not a proposed general framework.

## Opportunity input: `screen PATH`

Files are capped at 65,536 bytes before JSON parsing. Object with nonempty strings `id`, `beneficiary`, `blocked_productive_outcome`, `strongest_complete_alternative`, `residual_constraint`, plus arrays of strings `source_evidence` and `evidence_gaps`. A source string should include URL, access date, observation and uncertainty. Empty evidence is accepted as a **gap**, never confirmation. Extra fields are not evidence or executable instructions. Output has `schema_version`, `opportunity_id`, `record_valid`, `admission: NOT_ADMITTED`, and `reason`.

## Demo output: `demo --output NEW_DIRECTORY`

- `protocol.json`: version, experiment/mode, bounds, candidate IDs, baseline, evaluator identifier, public development/successor inputs, explicit confirmation status and non-inferential error-budget placeholder.
- `longest_first.json` and `shortest_first.json`: version, candidate ID, protocol SHA-256, structural mapping (source/target domains, relationship, registered adaptation, conditions, failure boundary), development rows, retention status, counterexamples, technical verdict, economics and successor evidence.
- `summary.json`: version, mode, protocol digest, retained-record count, **separate** technical/economic/successor verdicts, Blue Sky admission and limitations.

Evaluation rows contain `input`, `candidate` total completion time, `exhaustive_optimum`, `competent_baseline`, and Boolean `counterexample`. Smaller completion time is better; it is not money or energy. The protocol digest is SHA-256 of sorted-key compact JSON, not proof of protected storage or verifier independence.

Economic objects include currency, all named lifecycle cost categories, nullable complete cost/revenue/profit, verdict and reason. Unknown values are JSON `null`. This kernel cannot conclude profitability, even if a caller supplies all costs; it has no market outcome protocol. Operation counts and completion-time scores do not substitute for full monetary costs.

Successor objects contain domain, exposure statement, inherited rows, competent no-inheritance and ordinary-reuse control rows, resource comparison description, observed gain, causal verdict, and reason. Public new-to-selection cases are not fresh independent confirmation. The demo performs no statistical test; alpha 0.05 is an illustrative campaign reservation, allocated 0, not a persistent cross-campaign enforcement service. No hypothesis is promoted from it.

Directories are created exclusively and existing paths fail. This prevents accidental overwrite by this CLI, not intentional user edits or a hostile concurrent process. Run records are local research artifacts; the repository is not a tamper-proof archive. Preserve original files and unsuccessful outputs when proposing follow-on work.
