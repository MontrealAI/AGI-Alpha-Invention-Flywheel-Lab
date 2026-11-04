# Replay the registered study

An independent reproduction creates new simulated accounts. Its output will not recreate another account's signer, signed journal or byte-identical export. Compare economic histories, logical work, settlements and balances. To verify an *existing* account, use its own source and complete private recovery directory at its original absolute namespace; see [safe resume](README.md#run-and-recover).

The public protocol is commit `786d1d085f83c70ab8b7b9a3ee0c79530af7c79b`. All ten operating accounts used `9187e8f0b57d4b11124a14ed89582914f33b30b6`. The exact 325-test receipt is [STUDY_SOURCE_GATE.json](review/STUDY_SOURCE_GATE.json); [STUDY_TESTS.json](review/STUDY_TESTS.json) names the methods and runtime. The scripts used to orchestrate those original operations are retained in [review/reproduction](review/reproduction). The operating source and solver pins are unchanged between the ten cells.

From a local checkout of this results edition, using Python 3.12, a POSIX filesystem and new private directories:

```sh
set -eu
umask 077
repo_root=$(git rev-parse --show-toplevel)
study_sha=9187e8f0b57d4b11124a14ed89582914f33b30b6
replay_root=$(mktemp -d)
git -C "$repo_root" worktree add --detach "$replay_root/source" "$study_sha"
python -m venv "$replay_root/venv"
. "$replay_root/venv/bin/activate"
python -m pip install -r "$replay_root/source/requirements-omega-mechanisms-v3.txt"
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
tools_dir="$repo_root/campaign/omega-paid-reach-20261104/review/reproduction"
python "$tools_dir/qualify_reach_head.py" --source "$replay_root/source" \
  --commit "$study_sha" --out "$replay_root/tests"
python "$tools_dir/run_reach_matrix.py" --source "$replay_root/source" \
  --output "$replay_root/accounts" --gate "$replay_root/tests/COMPLETION.json"
python "$replay_root/source/scripts/summarize_omega_reach.py" \
  --input "$replay_root/accounts" --output "$replay_root/PAIRED_EVIDENCE.json"
```

The runner uses four separate workers. Each receives a fresh, individually funded account; results remain independent. It retains each attempt and audit. If a process exits, keep the directories and diagnostics. Inspect the reported failure before using the same matrix invocation on the *same* output and qualifier receipt: existing cells use resume, not a new opening balance. An unchanged closed cell can be audited and resumed again without a second business history. A stale or altered account fails closed. Never delete a saved report, journal or signer to force progress, and never publish the generated account directories.

The lighter [single-account commands](README.md#run-and-recover) are useful for familiarization. Rerunning a published seed is an engineering reproduction, not a new market sample. The executed [public comparison](PAIRED_EVIDENCE.json) excludes buyer-level orders and account authority.
