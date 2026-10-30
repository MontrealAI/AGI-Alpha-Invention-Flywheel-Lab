# Current policy and frozen reproduction inputs

The repository root contains current operating instructions. Historical cycle-001
reproduction uses the unchanged `campaign/cycle-001/EDITION_SHA256.json` and
`CLOSURE.json` identities. It must not execute later instructions as though they
were those frozen inputs.

`AGENTS.md.txt`, `CHARTER.md.txt`, `FIRST_CAMPAIGN.md.txt` and `README.md.txt` are
byte-for-byte copies fetched from commit
`c487e4741aa9d6f1a0928bc73d399d8a247b62e4`, checked against the original edition
hashes. The source URLs have the form
`https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/c487e4741aa9d6f1a0928bc73d399d8a247b62e4/AGENTS.md`.
The existing `campaign-workflow.yml.txt` is preserved.

`flywheel.legacy` first accepts an exact matching current-tree input; when one of
these explicitly listed policy files has changed, it materializes only the
hash-matched original snapshot and records the origin. There is no generic
fallback for runtime code, manifests, data, or arbitrary missing files. Missing,
changed, or symlinked historical inputs fail. No historical manifest or reference
identity is regenerated.

These files are reproduction data, not the current campaign's operating policy.
Historical successful replay is engineering evidence, not a new scientific or
commercial confirmation. The original interruption defect remains preserved.
