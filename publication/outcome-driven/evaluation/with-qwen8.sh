#!/usr/bin/env bash
set -Eeuo pipefail
runtime_root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
models="$runtime_root/models"
model_log=${1:?pass a model log path}
shift
LD_LIBRARY_PATH="$models/llama-b12242${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"  "$models/llama-b12242/llama-server" --host 127.0.0.1 --port 38461 --model "$models/qwen8.gguf"  --alias qwen3-8b-q4_k_m --ctx-size 16384 --threads 8 --threads-batch 8 --parallel 1 --batch-size 128 --ubatch-size 64  --cache-ram 0 --ctx-checkpoints 0 --no-ui --jinja --reasoning off --reasoning-budget 0  --cors-origins http://127.0.0.1:38463 --no-cors-credentials >"$model_log" 2>&1 &
model_pid=$!
trap 'kill "$model_pid" 2>/dev/null || true' EXIT
ready=0
for attempt in {1..75}; do
  if curl --noproxy '*' --silent --fail --max-time 2 http://127.0.0.1:38461/health --output /dev/null; then
    ready=1
    break
  fi
  kill -0 "$model_pid"
  sleep 1
done
[[ "$ready" == 1 ]]
"$@"
