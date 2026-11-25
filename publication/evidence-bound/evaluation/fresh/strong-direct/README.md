# Direct included-Codex comparison

An isolated author received the three original local tasks and the approved primary datasets. It produced three standalone Python programs. The independent evaluator checked the frozen source hashes, reran each program on the primary input, and tested the two numerical programs on the pre-existing withheld reuse datasets. All five executions passed exact acceptance checks. The missing-data program identified `ligne-11.minutes` and withheld the rate. [Independent result](RESULT.json) · [Actual execution outputs](OBSERVED-OUTPUTS.json) · [Frozen author receipt](public-results.json)

This was a post-registration supplement using different compute and assisted operation. The live source task remained outside this comparison. The author observed 76.606 seconds from the first clock reading after inspecting the inputs through initial execution and one ordering check. Total setup, inference, and monetary costs remain unknown.

The programs accept JSON through a filename or standard input and depend on Python's standard library. From this directory, run the original inputs as follows.

```sh
sha256sum -c SHA256SUMS
python3 -I -S -B blend.py public-inputs.json
python3 -I -S -B acceptance.py public-inputs.json
python3 -I -S -B flow.py public-inputs.json
```
