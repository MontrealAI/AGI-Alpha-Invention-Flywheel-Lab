#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v codex >/dev/null 2>&1; then
  echo "Codex CLI is not installed. Official install: npm install -g @openai/codex"
  exit 1
fi
printf '\nOfficial ChatGPT / Codex session status:\n'
codex login status
printf '\nLive ALPHA GENESIS agent mission begins. Account sign-in must already be authorized on this computer.\n'
node 00_STAGE/run_show.mjs --mode codex-pro --focus confidence
if [[ "$OSTYPE" == darwin* ]]; then open 00_STAGE/output/ALPHA_GENESIS_MISSION_STUDIO.html; fi
