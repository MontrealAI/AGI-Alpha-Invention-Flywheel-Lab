# Verified public release and operation

[FLYWHEEL Ω release](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases/tag/connected014-4abbb85893c9c073ca092db4ad858f7bb156dc35) was published from commit `4abbb85893c9c073ca092db4ad858f7bb156dc35`. The public tag resolves to that commit. Verification matched all 15 assets to their provider hashes and all 1,305 source archive files to the release checkout. The canonical enterprise and the V4 and paid-reach operators ran from the downloaded release. Each of the latter two passed its source-identity, run, independent audit and resume stages. The central V4 engineering account recorded 27 opportunities, 19 settlements and eight declines. The paid-reach engineering receipt records acceptance and unchanged export and recovery authority. Financial results for the operating study belong to its original accounts. [Published operation](PUBLISHED_OPERATION.json) · [Provider metadata](PROVIDER.json) · [Hosted download and operating job](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41771560549/job/126390614408).

## What qualified

| Source | Check | Evidence |
| --- | --- | --- |
| Economic integration, PR #206 | All 23 applicable PR workflows passed. Local targeted selection passed 342 of 342. Repository discovery ran 1,961 tests with two optional OR-Tools skips. | [CI and job-level results](PR206_WORKFLOWS.json) |
| First merge on main | The 342 targeted tests passed and the aggregate passed with two optional skips. A subsequent paper merge superseded two main checks before publication. The release gate refused the cancelled adaptive prerequisite. | [Initial main results](SUPERSEDED_MERGE_WORKFLOWS.json) |
| Subsequent paper merge | Its new workflow failed the repository's hosted-runner requirement. All 71 economic operating files retained their hashes. | [Failed workflows](PAPER_INTEGRATION_FAILURES.json) |
| Compatibility repair, PR #213 | The paper build, original 1,961-test campaign and clean package passed. All 12 applicable PR workflows succeeded. | [Repair CI](PR213_WORKFLOWS.json) |
| Released main | All 12 main-push workflows passed. The aggregate ran 1,961 tests, with two optional OR-Tools dispatch cases skipped. All 342 exact-source targeted tests ran and passed. Nine unmodified tests supplied by four independent PRs passed, including six signed accounting faults and seven interruption points. | [Main workflows](MAIN_WORKFLOWS.json) · [Targeted selection](RELEASE_SOURCE_TARGETED_TESTS.json) · [External tests](EXTERNAL_PR_TESTS.json) |

The [integration record](INTEGRATION.json) preserves earlier source identities, timings and original evidence hashes. After some temporary staging files became unavailable, the final source and evidence were recovered from the public repository and provider. The frozen release verifier was recovered byte-for-byte, and the nine external tests were rerun on the final source. Engineering reproductions use separate accounts and add no profit to the designated primary.

## Replay the independent verification

Obtain the two original ZIP files from the [publication gate](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41771560549/artifacts/13296610775) and [downloaded operation](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/41771560549/artifacts/13297368670). Save them as `gate.zip` and `operation.zip` in a new working directory. The provider may require a signed-in GitHub session for Actions artifacts. Published release assets and the compact verification receipts also have permanent repository links.

Use Python 3.12. The evidence branch contains the frozen independent verifier and the minimized provider records. A separate worktree contains the exact program that the verifier imports.

```sh
set -eu
tag_commit=4abbb85893c9c073ca092db4ad858f7bb156dc35
git clone --branch evidence/omega-enterprise-release-4abbb85 \
  https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab.git evidence
git -C evidence worktree add --detach ../source "$tag_commit"
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r source/requirements-omega-mechanisms-v3.txt
review=evidence/campaign/omega-economy-v4/review/released-enterprise
python -B "$review/verify_published_operation.py" --commit "$tag_commit" \
  --verifier-source "$PWD/source" --provider "$review/PROVIDER.json" \
  --gate-zip "$PWD/gate.zip" --operation-zip "$PWD/operation.zip"
```

[Seven operating verdicts](../../OPERATING_RESULT.md) · [Run the cart enterprise](../../README.md) · [Reproduce all five matched distribution pairs](../../../omega-paid-reach-20261104/REPLAY.md).
