#!/usr/bin/env bash
set -euo pipefail
umask 077

ref='refs/heads/frontier-omega-alpha-radar'
origin='https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab.git'
work="$(mktemp -d "$RUNNER_TEMP/frontier-radar.XXXXXX")"
snapshot="$work/revisions"
git init -q "$snapshot"
git -C "$snapshot" remote add origin "$origin"
previous=()
if git ls-remote --exit-code origin "$ref" >/dev/null; then
  git -C "$snapshot" fetch -q --depth=1 origin "$ref"
  [[ "$(git -C "$snapshot" ls-tree --name-only FETCH_HEAD)" == 'radar.json' ]]
  git -C "$snapshot" checkout -q --detach FETCH_HEAD
  previous=(--previous "$snapshot/radar.json")
else
  absence=$?
  [[ "$absence" == 2 ]]
fi

cd "$GITHUB_WORKSPACE/products/frontier-omega-alpha"
python3 -m research.scheduled --output "$work/radar.json" "${previous[@]}"
if [[ ! -f "$work/radar.json" ]]; then exit 0; fi
cp "$work/radar.json" "$snapshot/radar.json"
git -C "$snapshot" add -- radar.json
git -C "$snapshot" -c user.name='github-actions[bot]' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
  -c core.hooksPath=/dev/null commit -qm 'Record public FRONTIER Ω ALPHA source observations'
GIT_TERMINAL_PROMPT=0 git -C "$snapshot" -c credential.helper= -c 'credential.helper=!gh auth git-credential' \
  push -q origin "HEAD:$ref"
