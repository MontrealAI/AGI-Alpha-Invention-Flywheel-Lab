# Activation 1.4 · Intelligence Cascade Ω

Run from the extracted Activation directory. The standard replay uses bundled, byte-bound public evidence and requires Python 3.12 and the dependencies of the existing Activation package. It can run with the network disconnected.

```sh
python3 verify_cascade.py
python3 cascade.py registry
python3 cascade.py replay
python3 cascade_fresh_domain.py --fixture study/cascade/FRESH-DOMAIN.json
```

## Original-source replay

`TTV-INPUT.json` carries the five original MAST product URLs, filenames, byte counts and SHA-256 values. Obtain them from those URLs, keep each archive filename in one local directory, then run the original reductions. Python 3.12, NumPy 2.3.5, SciPy 1.17.0 and CFITSIO 4.06 were used. A [TESS MAST source](https://archive.stsci.edu/missions-and-data/tess) describes the products. Historical edition sources and the ExoClock IV archive are enumerated in `study/liberation/SOURCES.json`.

```sh
OPENBLAS_NUM_THREADS=1 python3 verify_cascade.py --fits-dir /absolute/path/to/fits
python3 verify_cascade.py --oni-html /absolute/path/to/cpc-oni-v5.html
python3 verify_cascade.py --labels-zip /absolute/path/to/by_planet.zip
OPENBLAS_NUM_THREADS=1 python3 ttv_diagnostic.py \
  --elements /absolute/path/to/drc-elements.txt \
  --observations /absolute/path/to/drc-observations.txt \
  --manifest study/cascade/TTV-INPUT.json --output ttv-replay.json
```

The two fitted reductions were designed without the numeric reference times. The shared date-only window was 37.2 hours. `PRIMARY.json` and `ORDINARY.json` preserve the frozen results. `TTV.json` retains the pre-cutoff forecasting diagnostic. Its algorithm, model parameters, partitions, scores and forecasts reproduce the frozen run. The portable manifest drops executor paths and corrects the attribution of Table 8 to Kokori et al. The original manifest digest was `689b7f076188de5f1bbc27cbd363a1e7ad16cadc9fd8f3fcee2d272a0dd6530a` with the checked exact value recorded in `RESULTS.json`. [ExoClock IV and Table 8](https://doi.org/10.3847/1538-4365/ae3238) · [Archived timing rows](https://doi.org/10.17605/OSF.IO/WPJTN)

The separate Sector 64 follow-up checks the source mismatch after opening the reference. It tests two isolated depth templates in 24 combinations of flux product, shape and midpoint perturbation. It reproduces `POST-REVEAL.json` byte for byte in the qualified Python environment. It is a model-conditional check from the same photons, outside held qualification.

```sh
OPENBLAS_NUM_THREADS=1 python3 post_reveal_overlap.py \
  --inputs study/cascade/POST-REVEAL-INPUT.json --fits /absolute/path/to/sector64.fits
```

The historical CPC projection spans DJF 1950 through NDJ 2024. It pins the original NOAA table and replays the numeric classification against native published labels and a separate five-window implementation. All 900 agree and all 15 challenges pass. The operational request correctly abstains and identifies the official RONI scope. [NOAA CPC historical series](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v5/) · [NOAA operational notice 26-05](https://www.weather.gov/media/notification/pdf_2026/pns26-05_Relative_ONI.pdf)

## Operator and owner workstation

The completed local model run uses Qwen3-4B-Instruct-2507 Q4_K_M, weight SHA-256 `2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e`, and llama.cpp b12242. `LOCAL-CONFIG.json` points only to numeric loopback, carries a zero paid-request allowance, and binds an 8,192-token context. The original whole-batch request was rejected before dispatch in every arm under the conservative byte envelope. The subsequent 16,384-context server was killed during initialization, before any call. An initial 8,192-token split passed one typed batch. The other group still exceeded the conservative schema-aware bound, and the server subsequently stopped during the ordinary condition. The measured follow-up uses the same case inputs and equal 1,400-output-token limits, one compact request per arm, six CPU threads and an 8,192-token context. Receipt fields capture the prompt hash, model draft, inference time and observed token usage. A separate deterministic dependency-completion variant uses the exact same model outputs. It does not change the literal model comparison.

On an existing owner-approved Ubuntu host, use a compatible CUDA build of the already approved llama.cpp release and the same model file. Use fresh workspace directories if changing the model or configuration. Capture terminal output and the startup log with the result receipts. The two TITAN RTX cards and sustained GPU performance remain owner-host qualification targets.

```sh
uname -srmo
free -b
nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv
sha256sum "$FRONTIER_GGUF"
llama-server --version
llama-server --host 127.0.0.1 --port 38461 --model "$FRONTIER_GGUF" \
  --alias qwen3-4b-instruct-2507-q4_k_m --ctx-size 8192 --threads 6 --threads-batch 6 \
  --parallel 1 --batch-size 128 --ubatch-size 64 --cache-ram 0 --ctx-checkpoints 0 \
  --n-gpu-layers 99 --split-mode layer --tensor-split 1,1 --no-ui --reasoning off --jinja
```

From a second terminal on that host, run the packaged comparison. Save the three JSON outputs and the server's GPU placement and token throughput lines. The receipt should record peak memory, input and output rates by batch, agreed results and denials, total task and attention time, and any separately observed expenditure. Data and endpoints are public research and loopback.

```sh
python3 cascade.py operator --arm typed --config study/cascade/LOCAL-CONFIG.json --workspace ./gpu-replay
python3 cascade.py operator --arm ordinary --config study/cascade/LOCAL-CONFIG.json --workspace ./gpu-replay
python3 cascade.py operator --arm direct --config study/cascade/LOCAL-CONFIG.json --workspace ./gpu-replay
```

The typed route is constrained by the qualified science operators. The model cannot download arbitrary files, run arbitrary code, publish, pay, book observations, or acquire private permissions through this interface. The registry identifies experimental public research operations. The signed custody and private delivery boundaries are tracked in the owner packet.
