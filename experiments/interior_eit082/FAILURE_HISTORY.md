# Immutable execution and correction history — EIT082

## 2026-11-03: initial workflow publication error

The first workflow heads failed before a job could start because the YAML inline `--only-binary=:all:` argument was an invalid YAML scalar. The first invalid runs [41662978449](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41662978449) and [41663093854](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41663093854) are **FAILED** and must stay failed. Prospective workflow syntax corrected at `92c1010fad87a129029dfa3a17b69a226dfaa117`. No physical sample was processed in those invalid runs.

## 2026-11-03: first executable source-inventory failure

The first hosted executable run, [41663364228](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41663364228), source `92c1010fad87a129029dfa3a17b69a226dfaa117`, passed the source/protocol regression step and acquired the exact registered public ZIP with verified MD5. The scientific step **FAILED before any classifier fitting or heldout result** at `load_physical` with `FROZEN_SOURCE_MEMBER_COUNT_CHANGED`. This resulted from the implementation's unregistered assumption of **exactly 38** `.mat` ZIP members, derived from catalog wording rather than an actual inspected member listing. The protocol's registered comparison does not rely on unselected cases; the required 17 specific case names and their class/count allocation were frozen before implementation.

Prospective correction at `e06919db0a3b2dbf71c13adab15a47c86d8b4a68`: remove that gratuitous total-member equality, require at least the 17 registered cases and independently enforce **every** archive member's safe canonical name and uniqueness, complete expected matrix schema and identical excitation patterns. Continue to require the same exact source MD5, pinned registered cases, fixed four-pattern budget and original decision threshold. Record the actual MAT member count and source SHA256 in the scientific result. This is a **source-inventory implementation correction**, not changed economic evidence, a new label, substituted physical sample or softened source checksum. Do not reclassify the prior run as passed; it is preserved above. The corrected head still needs independent actual hosted qualification.

## Scope

Neither the original native-capital source, any JournalAccount/Account authority or balance, other teams' source, historical experiment failures or contractual obligations was read or modified. No private material, paid model API, customer interaction, physical purchase, real transaction or production deployment. A physically successful classification would not establish a new profitable industry or the US$3B trailing-365 complete-cost milestone.
