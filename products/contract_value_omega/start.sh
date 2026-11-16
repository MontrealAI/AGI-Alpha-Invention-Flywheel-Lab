#!/usr/bin/env bash
# CONTRACT VALUE Ω — buyer-local launcher. No network, model or credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [ "$#" -ge 1 ]; then
  DATA="$1"
else
  DATA="$ROOT/products/contract_value_omega/demo"
fi
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if [ "$#" -ge 2 ]; then
  OUTPUT="$2"
else
  OUTPUT="$HOME/ContractValueOmega/review-$STAMP"
fi
cd "$ROOT"
python3 -m products.contract_value_omega.run --input "$DATA" --output "$OUTPUT"
python3 -m products.contract_value_omega.verify --input "$DATA" --report "$OUTPUT"
printf '\nCONTRACT VALUE Ω — source-bound review created.\nOpen locally: %s/index.html\n\n' "$OUTPUT"
printf 'No files were uploaded, no vendor was contacted and no money was recovered.\n'
