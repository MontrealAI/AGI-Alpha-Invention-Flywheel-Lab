#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
node 00_STAGE/run_show.mjs --mode preview --focus confidence
if [[ "$OSTYPE" == darwin* ]]; then open 00_STAGE/output/ALPHA_GENESIS_MISSION_STUDIO.html; fi
