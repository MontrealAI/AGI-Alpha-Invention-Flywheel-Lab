#!/usr/bin/env bash
# Replays the CPU qualification in a fresh Linux directory.
set -euo pipefail
root=$(cd "$(dirname "$0")" && pwd)
work=$(realpath -m "$1")
receipts=$(realpath -m "$2")
mkdir -p "$receipts"
mkdir "$work"
upstream=4c0a117f4ae983992bbe2ce134c0389d7280f120
patch="$root/../scroll_normalization/candidate.patch"
printf '%s  %s\n' 336420772c845a10ece5edf316ab7494d79662390580112496299a0524727c57 "$patch" | sha256sum -c -
git -C "$work" init --quiet villa
src="$work/villa"
git -C "$src" remote add origin https://github.com/ScrollPrize/villa.git
git -C "$src" sparse-checkout init --cone
git -C "$src" sparse-checkout set vc_reader vesuvius/src/vesuvius
git -C "$src" fetch --depth=1 --filter=blob:none origin "$upstream"
git -C "$src" checkout --quiet --detach FETCH_HEAD
test "$(git -C "$src" rev-parse HEAD)" = "$upstream"
export CMAKE_BUILD_PARALLEL_LEVEL=2
export CMAKE_ARGS="-DVC_READER_ENABLE_CUDA=OFF -DCURL_LIBRARY=/usr/lib/x86_64-linux-gnu/libcurl.so"
for arm in histogram candidate; do
    if [[ "$arm" == candidate ]]; then
        git -C "$src" apply --check "$patch"
        git -C "$src" apply "$patch"
        test "$(git -C "$src" diff --name-only)" = "vc_reader/src/cpp/transforms/cpu/normalization.hpp"
    else
        git -C "$src" diff --quiet HEAD
    fi
    mkdir "$work/wheel-$arm"
    /usr/bin/time -f 'wall_seconds=%e user_cpu_seconds=%U system_cpu_seconds=%S peak_rss_kib=%M' \
        -o "$receipts/build-$arm.txt" \
        python -m pip wheel --no-cache-dir --no-build-isolation --no-deps \
        -C "build-dir=$work/build-$arm" -w "$work/wheel-$arm" "$src/vc_reader"
    python -m pip install --no-deps --target "$work/installed-$arm" "$work/wheel-$arm"/*.whl
done
/usr/bin/time -f 'wall_seconds=%e user_cpu_seconds=%U system_cpu_seconds=%S peak_rss_kib=%M' \
    -o "$receipts/comparison-cost.txt" python "$root/reader_cpu.py" "$src" "$work" "$receipts"
