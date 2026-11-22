#!/usr/bin/env bash
set -euo pipefail
umask 077

state_ref='refs/heads/frontier-omega-alpha-state'
origin='https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab.git'
published='https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/library.json'
work="$(mktemp -d "$RUNNER_TEMP/frontier-native.XXXXXX")"
state_git="$work/git"
product="$GITHUB_WORKSPACE/products/frontier-omega-alpha"
git init -q "$state_git"
git -C "$state_git" remote add origin "$origin"
previous=-
public=-

if git ls-remote --exit-code origin "$state_ref" >/dev/null; then
  git -C "$state_git" fetch -q --depth=1 origin "$state_ref"
  membership="$(git -C "$state_git" ls-tree --name-only FETCH_HEAD)"
  [[ "$membership" == $'library.json\nstate.json' ]]
  git -C "$state_git" checkout -q --detach FETCH_HEAD
  previous="$state_git/state.json"
  public="$state_git/library.json"
  [[ -f "$previous" && ! -L "$previous" && -f "$public" && ! -L "$public" ]]
else
  absence=$?
  [[ "$absence" == 2 ]]
fi

node "$product/native/operator.mjs" run "$product/native/approved-releases.json" "$previous" "$public" "$work/next"
unset FRONTIER_ALPHA_PUBLISH_KEY FRONTIER_ALPHA_RPC
cp "$work/next/state.json" "$state_git/state.json"
cp "$work/next/library.json" "$state_git/library.json"
git -C "$state_git" add -- state.json library.json
git -C "$state_git" -c user.name='github-actions[bot]' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
  -c core.hooksPath=/dev/null commit -qm 'Checkpoint encrypted FRONTIER Ω ALPHA publication'
GIT_TERMINAL_PROMPT=0 git -C "$state_git" -c credential.helper= -c 'credential.helper=!gh auth git-credential' \
  push -q origin "HEAD:$state_ref"

# A successful state write may outlive a failed dispatch. Repairs use the published bytes as their receipt.
if curl -q --silent --fail --max-time 20 --max-filesize 6291456 --proto '=https' "$published" -o "$work/published.json" &&
   cmp -s "$work/next/library.json" "$work/published.json"; then
  exit 0
fi
gh workflow run research-pages.yml --repo MontrealAI/AGI-Alpha-Invention-Flywheel-Lab --ref main
