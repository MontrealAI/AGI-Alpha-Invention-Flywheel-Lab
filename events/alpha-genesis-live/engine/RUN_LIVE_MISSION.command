#!/bin/bash
# MONTREAL.AI: official ChatGPT account sign-in through the official Codex CLI.
# No account token is read or copied by the workshop scripts.
set -euo pipefail
cd "$(dirname "$0")"
printf '\033[35m\n╔══════════════════════════════════════════════════════════════╗\n║   MONTREAL.AI  ·  AI AGENTS THAT PROVE THEIR WORK            ║\n║          LIVE AGENTIC PROCUREMENT MISSION                    ║\n╚══════════════════════════════════════════════════════════════╝\033[0m\n\n'
if ! command -v node >/dev/null 2>&1; then echo 'Node.js 22+ is required. Install Node.js LTS from nodejs.org.'; exit 2; fi
if ! command -v codex >/dev/null 2>&1; then
  echo 'The official OpenAI Codex CLI is not installed.'
  echo 'Install it now using the official npm package @openai/codex? [y/N]'
  read -r APPROVE
  if [[ "$APPROVE" =~ ^[yY]$ ]]; then npm install -g @openai/codex; else echo 'Install manually: npm install -g @openai/codex'; exit 3; fi
fi
if ! codex login status 2>&1 | grep -qi 'Logged in using ChatGPT'; then
  echo 'Complete the official Sign in with ChatGPT flow in your browser.'
  echo 'Use your own Pro account and authorize the Codex client. No password is requested by this script.'
  codex login
fi
if ! codex login status 2>&1 | grep -qi 'Logged in using ChatGPT'; then echo 'ChatGPT sign-in has not been confirmed. No AI calls were made.'; exit 4; fi
mkdir -p artifacts
echo 'Official Codex ChatGPT sign-in detected. Starting real tool-using AI mission...'
node mission_agent.mjs --provider codex-pro --output artifacts/live_codex_receipt.json --max-rounds 15
node verify_receipt.mjs artifacts/live_codex_receipt.json > artifacts/live_independent_verification.json
node render_mission_board.mjs --receipt artifacts/live_codex_receipt.json --output artifacts/LIVE_Mission_Board.html
printf '\nLIVE MISSION COMPLETE: independent checks passed.\n'
printf 'Receipt: %s\n' "$(pwd)/artifacts/live_codex_receipt.json"
printf 'Board:   %s\n' "$(pwd)/artifacts/LIVE_Mission_Board.html"
if command -v open >/dev/null 2>&1; then open artifacts/LIVE_Mission_Board.html; fi
