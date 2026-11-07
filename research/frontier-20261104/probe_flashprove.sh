#!/usr/bin/env bash
# GENESIS FRONTIER 001: source-pinned CPU verification; not a live model attestation.
set -euo pipefail
if [[ "$(id -u)" == 0 ]]; then echo "Do not run untrusted research code as root" >&2; exit 2; fi
if [[ $# != 1 || "$1" != /* || -e "$1" ]]; then
  echo "Usage: probe_flashprove.sh /absolute/new/output-directory" >&2; exit 2
fi
OUT=$1
UPSTREAM_SHA=9e2bdd8ff5bf9c62f18263d7dac189b0400b260c
mkdir -p "$OUT"
WORK=$(mktemp -d "$HOME/genesis-flashprove-XXXXXXXX")
git clone --quiet --no-checkout https://github.com/anthropics/FlashProve.git "$WORK/src"
git -C "$WORK/src" checkout --quiet --detach "$UPSTREAM_SHA"
ACTUAL_SHA=$(git -C "$WORK/src" rev-parse HEAD)
[[ "$ACTUAL_SHA" == "$UPSTREAM_SHA" ]] || { echo "Source mismatch" >&2; exit 3; }
printf '%s\n' "$ACTUAL_SHA" > "$OUT/upstream_sha.txt"
cd "$WORK/src"
(cd examples/accepted-proof && sha256sum -c SHA256SUMS) > "$OUT/source_integrity.txt" 2>&1
set +e
verifier/build.sh > "$OUT/build.log" 2>&1
BUILD_RC=$?
set -e
printf '%s\n' "$BUILD_RC" > "$OUT/build.exit"
[[ "$BUILD_RC" == 0 ]] || { tail -n 8 "$OUT/build.log" >&2; exit 10; }
# The ID supplied WITH this published SYNTHETIC example is allowed for self-test only.
# A real verifier must obtain a trusted model commitment independently beforehand.
EXAMPLE_ID=$(cat examples/accepted-proof/ID.txt)
set +e
bin/cp_verify examples/accepted-proof/config examples/accepted-proof/ivk \
  examples/accepted-proof/example.req examples/accepted-proof/example.y \
  examples/accepted-proof/example.proof -id "$EXAMPLE_ID" > "$OUT/accepted.log" 2>&1
ACCEPTED_RC=$?
set -e
printf '%s\n' "$ACCEPTED_RC" > "$OUT/accepted.exit"
[[ "$ACCEPTED_RC" == 0 && "$(tail -n 1 "$OUT/accepted.log")" == YES ]] || {
  echo "Synthetic stored proof did not verify" >&2; exit 11;
}
set +e
python3 examples/rejected-proofs/try_altered_copies.py bin/cp_verify \
  "$WORK/rejected-copies" > "$OUT/rejected.log" 2>&1
REJECTED_RC=$?
set -e
printf '%s\n' "$REJECTED_RC" > "$OUT/rejected.exit"
[[ "$REJECTED_RC" == 0 && "$(tail -n 1 "$OUT/rejected.log")" == '10 altered sets: all rejected' ]] || {
  echo "Altered-proof negative controls did not all reject as expected" >&2; exit 12;
}
python3 - "$OUT" "$UPSTREAM_SHA" "$EXAMPLE_ID" <<'PY'
import pathlib, json, hashlib, sys
p=pathlib.Path(sys.argv[1])
accepted=(p/'accepted.log').read_text().splitlines()
negative=(p/'rejected.log').read_text().splitlines()
record=dict(
    study="GENESIS-FRONTIER-001",
    status="SYNTHETIC_PROOF_VERIFIER_AND_NEGATIVE_CONTROLS_PASSED",
    upstream_repository="https://github.com/anthropics/FlashProve",
    upstream_commit=sys.argv[2],
    example_commitment_id=sys.argv[3],
    commitment_independently_trusted=False,
    sample="Published synthetic 8-layer example, not a served AI model",
    accepted_exit=int((p/'accepted.exit').read_text()),
    accepted_last_line=accepted[-1],
    covered_line=next((s for s in accepted if s.startswith('covered:')),None),
    result_v1_line=next((s for s in accepted if s.startswith('result-v1')),None),
    negative_controls_exit=int((p/'rejected.exit').read_text()),
    negative_controls_last_line=negative[-1],
    negative_controls_count=10,
    boundaries=[
        "Does not establish independently pinned model identity for a real request",
        "Does not establish model response correctness or job acceptance",
        "C++ verifier is tested, not subject to the Lean verifier's proof scope",
        "Does not establish demand, revenue, new model performance or an improved inventor",
    ],
    log_sha256={
        n:hashlib.sha256((p/n).read_bytes()).hexdigest()
        for n in ['build.log','accepted.log','rejected.log','source_integrity.txt']
    },
)
(p/'RESULT.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
print("SYNTHETIC_PROOF_VERIFIER_AND_NEGATIVE_CONTROLS_PASSED")
print("upstream_sha="+sys.argv[2])
print("accepted_exit=0, last_line=YES")
print("negative_controls_exit=0, last_line=10 altered sets: all rejected")
PY