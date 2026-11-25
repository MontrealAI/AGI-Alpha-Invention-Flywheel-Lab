#!/usr/bin/env bash
set -Eeuo pipefail
# Run from the project root with Node, playwright-core and Chrome installed.
umask 077
base=${1:?base URL with trailing slash}
run_dir=${2:?dedicated output tree}
language=${3:?language}
ambition=${4:?exact ambition}
mode=${5:-start}
runtime_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$run_dir"
run_dir=$(realpath "$run_dir")
connector_log="$run_dir/$mode-connector.private.log"
connector_dir="$run_dir/connector"
mkdir -p "$connector_dir"
executor_version=${FRONTIER_EXECUTOR_VERSION:-1.1.0}
archive_name="frontier-harness-executor-$executor_version.zip"
origin=$(python - "$base" <<'PY'
import sys, urllib.parse
parts = urllib.parse.urlsplit(sys.argv[1]); print(f'{parts.scheme}://{parts.netloc}')
PY
)
if [[ "$base" != https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/ && "$base" != http://127.0.0.1:8767/frontier-omega-alpha/ ]]; then
  echo 'Use the approved GitHub Pages publication or the local qualification preview.' >&2
  exit 1
fi
cleanup() {
  [[ -z "${connector_pid:-}" ]] || kill "$connector_pid" 2>/dev/null || true
  [[ -z "${preview_pid:-}" ]] || kill "$preview_pid" 2>/dev/null || true
}
trap cleanup EXIT
if [[ "$origin" == http://127.0.0.1:8767 ]]; then
  site="${FRONTIER_RELEASE_SITE:?staged site required for the local preview}"
  python -m http.server 8767 --bind 127.0.0.1 --directory "$site" >"$run_dir/preview.log" 2>&1 &
  preview_pid=$!
  cp "$site/frontier-omega-alpha/$archive_name" "$run_dir/executor.zip"
  cp "$site/frontier-omega-alpha/atlas-release.json" "$run_dir/live-release.json"
else
  if [[ -n "${HTTPS_PROXY:-}" && -f "${SSL_CERT_FILE:-}" ]] && command -v certutil >/dev/null; then
    browser_data="$run_dir/browser-data"
    mkdir -p "$browser_data/pki/nssdb"
    if ! test -f "$browser_data/pki/nssdb/cert9.db"; then
      certutil -N -d "sql:$browser_data/pki/nssdb" --empty-password
      certutil -A -d "sql:$browser_data/pki/nssdb" -n 'Execution environment HTTPS root' -t 'C,,' -i "$SSL_CERT_FILE"
    fi
    export XDG_DATA_HOME="$browser_data"
  fi
  curl -fsS --max-time 30 "$base/atlas-release.json" -o "$run_dir/live-release.json"
  curl -fsS --max-time 30 "$base/$archive_name" -o "$run_dir/executor.zip"
fi
: "${FRONTIER_EXPECTED_COMMIT:?required verified source}"
python - "$run_dir" "$FRONTIER_EXPECTED_COMMIT" "$archive_name" "$executor_version" <<'PY'
import hashlib, json, sys, zipfile
from pathlib import Path
root = Path(sys.argv[1]); receipt = json.loads((root/'live-release.json').read_bytes())
assert receipt['source_commit'] == sys.argv[2], 'Unexpected Pages revision'
archive = root/'executor.zip'; digest = hashlib.sha256
assert digest(archive.read_bytes()).hexdigest() == receipt['universal_mission_sha256'][sys.argv[3]]
with zipfile.ZipFile(archive) as package:
    manifest = json.loads(package.read('manifest.json'))
    assert manifest['source'].endswith('/commit/'+sys.argv[2]) and manifest['version'] == sys.argv[4]
    assert len(package.namelist()) == len(manifest['file_sha256']) + 1
    for name, fingerprint in manifest['file_sha256'].items():
        path=Path(name)
        assert not path.is_absolute() and '..' not in path.parts
        assert digest(package.read(name)).hexdigest() == fingerprint
PY
unzip -q -o "$run_dir/executor.zip" -d "$connector_dir"
printf '%s\n' '#!/bin/sh' 'printf "%s\n" "$1" > "$FRONTIER_PAIR_GUIDE_FILE"' > "$run_dir/capture-browser"
chmod 700 "$run_dir/capture-browser"
export FRONTIER_PAIR_GUIDE_FILE="$run_dir/$mode-guide.private.txt"
rm -f "$FRONTIER_PAIR_GUIDE_FILE"
args=()
if [[ -n "${FRONTIER_EVIDENCE_INPUT:-}" ]]; then args+=(--mission-evidence "$FRONTIER_EVIDENCE_INPUT"); fi
BROWSER="$run_dir/capture-browser %s" "$connector_dir/Launch-FRONTIER.sh" --workspace "$run_dir/workspace" \
  --pages-origin "$origin" --mission-lease-minutes 25 --mission-turns "${FRONTIER_TURNS:-2}" \
  --mission-actions 10 --mission-output-tokens "${FRONTIER_OUTPUT_TOKENS:-448}" "${args[@]}" > "$connector_log" 2>&1 &
connector_pid=$!
for attempt in {1..40}; do
  if [[ -s "$FRONTIER_PAIR_GUIDE_FILE" ]]; then break; fi
  kill -0 "$connector_pid"
  sleep .15
done
[[ -s "$FRONTIER_PAIR_GUIDE_FILE" ]]
export FRONTIER_EXECUTION_TEST
FRONTIER_EXECUTION_TEST=$(python - "$base" "$run_dir" "$connector_log" "$ambition" "$language" "$mode" "$archive_name" <<'PY'
import json,sys
base,result,log,ambition,locale,mode,archive=sys.argv[1:]
print(json.dumps(dict(base=base,resultDir=result,connectorLog=log,ambition=ambition,language=locale,mode=mode,archiveName=archive)))
PY
)
node "$runtime_root/run-evidence-browser.cjs"
