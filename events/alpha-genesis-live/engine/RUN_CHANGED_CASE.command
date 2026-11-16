#!/bin/bash
# Runs an actual follow-on mission on changed synthetic data. Use after an initial successful live mission.
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -f artifacts/live_codex_receipt.json ]]; then echo 'Run RUN_LIVE_MISSION.command first.'; exit 2; fi
if ! codex login status 2>&1 | grep -qi 'Logged in using ChatGPT'; then echo 'Run codex login with ChatGPT.'; exit 3; fi
mkdir -p artifacts
node make_challenge.mjs
node mission_agent.mjs --provider codex-pro --case-dir challenge_case --output artifacts/live_changed_receipt.json --max-rounds 15
node verify_receipt.mjs artifacts/live_changed_receipt.json --case-dir challenge_case > artifacts/live_changed_independent_verification.json
node render_mission_board.mjs --receipt artifacts/live_changed_receipt.json --case-dir challenge_case --output artifacts/LIVE_Changed_Case_Board.html
if command -v open >/dev/null 2>&1; then open artifacts/LIVE_Changed_Case_Board.html; fi
echo 'The changed case has been investigated and checked. The prior approval is never inherited.'
