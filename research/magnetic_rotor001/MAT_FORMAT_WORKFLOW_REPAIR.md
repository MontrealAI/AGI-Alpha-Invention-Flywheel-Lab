# Format003 GitHub Actions YAML declaration failure — frozen before fix

**Original workflow failure** at exact head `e5411444af6a48193856be77e837968cc0dc4465`: [Actions #42442720412](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/42442720412), GitHub reported FAILED with **zero jobs**. No tests or data retrieval executed. Preserve as FAILED.

**Reproduced static declaration cause:** `.github/workflows/magnetic-mat-format003.yml` includes a plain scalar `run: python -m pip install --only-binary=:all: numpy==...`; YAML parses the `: ` pair inside the unquoted line as a mapping delimiter, making the workflow invalid. This is the same previously known failure class elsewhere in the repository, not an issue with real source data or MATLAB parser. It is a developer workflow error, not an experiment result.

**Single prospective repair:** replace only this inline command with YAML block scalar `run: |` and the otherwise identical install command on an indented line. Keep the frozen diagnostic, pinned packages, source identity, tests, source hashes, first platform clock, restrictions and output unchanged. Validate resulting YAML source and then inspect actual jobs. Do not retroactively pass #42442720412. **NO DEPLOY.**
