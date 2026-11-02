# Qualification addendum: workflow syntax repair

The original reports and independent review describe the scientific source and first results at `00946cf112e457eabf0e5aa8163e931cb562cf54`. They remain intact. A subsequent hosted qualification attempt exposed a **workflow-only YAML syntax error**. This addendum separates that repair from scientific confirmation.

## Retained failed attempts

| Source head | Hosted run | Outcome |
|---|---|---|
| Public source freeze `28d9a23f6436d40655035c87bd9cc497ecd12812` | [41518432976](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41518432976) | Dedicated workflow parse failure on push; no experiment job executed |
| Original result publication `00946cf112e457eabf0e5aa8163e931cb562cf54` | [41519572200](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41519572200) | Same dedicated workflow parse failure on push; no experiment job executed |

The unquoted scalar `run: python -m pip install --only-binary=:all: numpy==2.3.5 scipy==1.17.0` contains a colon followed by a space. A direct PyYAML parse reproduced `ScannerError: mapping values are not allowed here` at line 26, column 54. The earlier runtime tests did not detect this YAML syntax error; their passes did not imply a valid hosted workflow.

The repair changes this one `run` value to a YAML block scalar. Dependency versions, commands, model acceptance, case denominators, result files, job-clock order and permissions are unchanged. The original workflow remains in the immutable freeze commit and its hash remains in `FREEZE.json`; it is not retroactively relabeled as passing.

- Original workflow SHA256: `a64b003a47ef88c62988ebbf8bf91d9c555772ceab0f3b3675ba18678d4889fe`.
- Repaired workflow SHA256: `7064d654b066f672743eb78bbb505b240d6f281755e976ae4885e62bb3f47712`.
- All **19 other frozen bindings** and all four original result files are unchanged.
- Direct YAML syntax parsing passed after the repair.
- Mandatory runtime/workflow preflight passed **16/16 tests** after the repair. [Attempt-specific receipt](QUALIFICATION_001.json).

This is a disclosed qualification repair after outcomes, not a change to any scientific constructor, independent reference, threshold or empirical denominator. The original program attempts are preserved. Hosted reproduction on the repaired source must receive its own exact-head receipt and cannot be counted as fresh physical confirmation.

The PR description records the latest source-matched workflow status. A dedicated model pass is not full repository qualification, merge, public release or physical admission. No formal PR approval or merge is performed by this repair.
