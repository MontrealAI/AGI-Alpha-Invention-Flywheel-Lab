# Reader V3 native CPU qualification

This experiment tests whether MONTREAL.AI’s sparse-normalization change preserves a real recipient’s 8-bit TIFF predictions when substituted into the public flat-ink Reader V3 inference CLI. The registered comparator is the stronger upstream histogram implementation in ScrollPrize/villa at `4c0a117f4ae983992bbe2ce134c0389d7280f120`. Both arms use the same checkout, checkpoint, data, process settings and loader. Only the compiled normalization header changes.

## Registered comparison

The source is the PHerc0139 w054 surface volume at 9.362 µm. Use all 28 original depth planes from two adjoining 3×3 sets of 128×128 chunks. The edge and ordinary panels start at chunk coordinates (29,84) and (39,39). Their complete 28×384×384 byte arrays have frozen SHA-256 digests in [reader_cpu.py](reader_cpu.py). These coordinates were chosen relative to the earlier component study. They constitute two known cases. Both panels have nonzero median absolute deviation across the native 17-plane input. This study therefore measures interoperability; its two-panel timing has limited power to resolve the sparse-case speedup.

Use the published MIT Reader V3 checkpoint from Hugging Face revision `aee1d64bced4eb35546348f3d276b9e2a0b99c46`. The fixture verifies the aggregate panel bytes, native extension selection, and the 138,379,659-byte checkpoint before interpreting results. Missing or changed bytes fail the test. The CLI selects one complete 384×384 patch in each direction, uses 50% configured overlap with Hann blending, CPU, batch size one, no torch compilation and no ROI. In each panel compare two counterbalanced orders in fresh processes. The first runs histogram then candidate. The second reverses the order. Filesystem and kernel caches may be warm across calls. Require exact encoded TIFF and decoded pixel equality, nonconstant uint8 pixels, correct dimensions, both directions and a checkpoint load with zero missing or unexpected keys. Stop at the first failure and retain the partial receipt. The job budget is 100 minutes on one standard hosted CPU runner.

The 3.12 interpreter runs the exact upstream source module directly. The `vesuvius` distribution’s current metadata declares Python 3.14. This experiment does not qualify a packaged 3.14 installation, GPU kernels, a complete scroll, interpretation of ground-truth ink, financial savings, acceptance by a beneficiary, or award eligibility.

[PHerc0139 data and research terms](https://scrollprize.org/data_browser/PHerc0139) · [model card](https://huggingface.co/domenicor046/reader-v3/tree/aee1d64bced4eb35546348f3d276b9e2a0b99c46) · [upstream CLI](https://github.com/ScrollPrize/villa/blob/4c0a117f4ae983992bbe2ce134c0389d7280f120/vesuvius/src/vesuvius/ink_detection/inference/infer.py)

## Replay

The [hosted job](../../../../.github/workflows/ignition-reader-cpu.yml) specifies the system packages and CPU-only wheel pins. From the repository root with the same system packages and a fresh Linux x86-64 Python 3.12 environment:

```sh
study=products/frontier-omega-ignition/invention/scroll_reader
python -m pip install -r "$study/requirements-cpu.txt"
workspace=$(mktemp -d)
bash "$study/replay.sh" "$workspace/builds" "$workspace/receipts"
cat "$workspace/receipts/reader-v3.json"
```

The runner cold-builds both native wheels in separate directories. It measures elapsed time, CPU and peak RSS for each build, CLI process and the complete acquisition/comparison. It also records package versions, wheel and extension hashes, all fetched CT chunk digests, output TIFF/pixel digests and failure details. GitHub provides phase logs if setup fails before inference. Receipts contain aggregate values and digests. Scan volumes and weights are fetched from their original publishers for the research run and excluded from the artifact. Monetary cost requires separate billing records.

## Earlier local probe

In the constrained local environment the native wheel build and a separate 384×384 full-model attempt ended in SIGKILL. A reduced adapter ran the original checkpoint’s graph on four 17×128×128 real CT inputs with both normalizers. It used a separate single-tile I/O and blending adapter. All four incumbent/candidate pairs produced equal float predictions and equal TIFF bytes. The observed TIFF SHA-256 prefixes and distinct pixel counts were:

| Input | TIFF SHA-256 prefix | Distinct byte values |
| --- | --- | ---: |
| Edge, forward | 94be979dfe515a | 48 |
| Edge, reverse | fe9df95a3843ea | 28 |
| Ordinary, forward | 7c1c8936abd2c2 | 21 |
| Ordinary, reverse | bd7124c4e9d6c4 | 31 |

The local results came from one call per arm and pair, with observed inference times between 0.086 and 0.258 seconds. They do not establish a speed advantage. The registered native result depends on the completed hosted receipt for its exact tested commit.
