# Replay the problem-first trials

The two briefs are [research release evidence](MISSION-1.json) and
[public tender review](MISSION-2.json). Both run through the normal invited
Studio worker on the original `0da09f1` source. The private independent cases
are under evaluator custody. The worker gets public observations, the brief
and its operating limits. It receives no tests, solution or construction
specification. Any scope confirmation is recorded separately.

Read [the initial attempt](INITIAL-ATTEMPT.md) before interpreting the recovery
run. The local first attempt lost terminal evidence. The corrected driver keeps
its disposable staging state inside a private work directory. GitHub Actions
retains a redacted receipt for each result, including stopping states. The
model's full proposal and private work directory are never uploaded.

From this continuation's repository root, use Python 3.12, Git, OpenSSL and a
compatible Linux x86-64 host. The first run provisions the independently pinned
public weights and runtime, which require about 2.53 GB before the work state.
Use a network on which the reviewed public publisher hosts are reachable.
Readouts record retrieval failures without granting more egress.

```sh
root=$(pwd)
experiment=docs/frontier-omega-ignition/continuation/problem-first
brief="$experiment/MISSION-1.json"
registered=$(git log -1 --format=%H -- "$brief")
trial=$(mktemp -d)
git worktree add --detach "$trial/original" 0da09f16c29b7ee0758f016e47d42808e3e8ab58
python3.12 -IB "$experiment/run_registered.py" \
  --repo "$trial/original" --registration-sha "$registered" \
  --brief "$root/$brief" --work "$trial/mission-1" --assets "$trial/assets"
```

Use `MISSION-2.json` and a separate work directory for the independent brief.
Exit status 1 means that the run did not produce a within-budget worker
artifact. Inspect `public-receipt.json` for the stage and diagnostic. An
`awaiting_contract` result means the worker is waiting for a scope review.
The default read-only qualification records this state without fabricating
operator confirmation. For a separately authorized recovery, `--review-seconds`
allows a review of the original proposal inside the mission deadline. Approval
requires the exact proposal hash and fresh public development confirmations.
Keep the evaluator's withheld cases out of that review. A build, if any, must
still be independently replayed against the frozen external panel.
