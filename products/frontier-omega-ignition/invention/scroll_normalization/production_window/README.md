# Independent check on six actual Reader V3 windows

An independently implemented scheduler reconstructed all 2,122 Reader V3 windows for the published PHerc0139 w054 example before sampling the six registered positions. It read all 28 planes of the provider's level-3 occupancy scan. It applied the frozen upstream rule for 384-square windows at 192-pixel stride and selected centered forward layers 6 through 22. The four interior windows and two boundary windows were selected before looking at their full-resolution data. The [upstream scheduler](https://github.com/ScrollPrize/villa/blob/4c0a117f4ae983992bbe2ce134c0389d7280f120/vesuvius/src/vesuvius/ink_detection/inference/infer.py) and [original PR's end-to-end report](https://github.com/ScrollPrize/villa/pull/2521) document the comparator. The source is official [PHerc0139 CT](https://scrollprize.org/data_browser/PHerc0139), licensed CC BY-NC 4.0. The scripts and manifests do not contain CT samples.

The local IGNITION CLI executed the sample mission, then exported its qualified ZIP. A separate process extracted the ZIP into a fresh temporary directory and compiled its environments. All 32 recipient self-checks passed. Each selected real input was independently verified through the recipient CLI and every timed output was hashed against both frozen alternatives. All six normalized float32 buffers had identical bytes across all three implementations.

| Scheduled index (zero-based) | Median absolute deviation | #2521 CPU median (ms) | Candidate CPU median (ms) | Speed ratio |
|---:|---:|---:|---:|---:|
| 0 | 0 | 61.782 | 4.862 | 12.708 |
| 530 | 31 | 3.512 | 3.477 | 1.010 |
| 1061 | 35 | 3.375 | 3.360 | 1.005 |
| 1591 | 18 | 3.347 | 3.275 | 1.022 |
| 2121 | 0 | 54.670 | 4.928 | 11.093 |
| 1017 | 39 | 3.444 | 3.412 | 1.009 |

The two sparse windows each contained real, nonuniform intensities. The seven timing passes per arm exclude conversion, setup and hashing. These six deliberately chosen windows establish that the effect survives production window assembly. Aggregate prevalence and total ink-reader time require a full matched run. Sponsor review, adoption, improved scientific readings and payment remain unobserved.

## Reproduction

Use Python 3 with NumPy, a C++20 compiler and the standard patch utility. Acquire the source objects mentioned above under the sponsor's permissions. The trial was run with a fresh local CLI export of SHA-256 `511e6aa590ffc75de33a8196e64ba187fa0b774d42aff89282007ee9f06597c9`. Compare the four operator source files before comparing another export. Metadata or later documentation may produce a new ZIP hash. These benchmark timings belong to the recorded archive.

```sh
python acquire_windows.py /tmp/scroll-window-replay
python bench_recipient.py /path/to/verified-recipient.zip /tmp/scroll-window-replay /tmp/scroll-window-replay/receiver.json
```

`run/window_inputs.json` logs all consumed chunk paths, hashes and byte ranges, reconstructed window hashes and absent chunks under the Zarr fill rule. `run/window_result.json` contains raw measurements and normalized output digests. `run/window_selection.json` was written before full-resolution acquisition. `run/receiver_resources.json` reports measured subprocess resources.

## Resource accounting

The acquisition consumed 52,171,228 response-body bytes across metadata, listings, stored occupancy chunks and requested full-resolution planes. Approximate elapsed acquisition time was 199.0 seconds, measured from creation of the output directory to issue of the input manifest. Its CPU time, TLS/transport overhead and electricity were unmetered. Preliminary source inspection included a 35,411-byte bucket listing and approximately 1.4 kB of sample metadata, separately from the registered acquisition; source search and code browsing traffic were unmetered. The executed receiver used 11.153 s wall time, 10.380 user CPU seconds and 1.572 system CPU seconds, with peak RSS 171,264 KiB. Archive creation, research, engineering, maintenance and review labor are outside the timing series. No payment, model call through a paid API, GPU rental or supplier charge was authorized; total economic cost is unknown.

## Separate numerical oracle

Run `python3 -IB check_window_oracle.py run` after retrieving the registered windows into `run/research_data`. This independent NumPy implementation checks the selected positions, original byte hashes, clipping, median absolute deviation, ordered-fallback effect on output and full little-endian float32 output hashes. Every one of the six digests matched, covering 60,162,048 output bytes. The observed process took 0.363 wall seconds, 0.945 process CPU seconds and 132,372 KiB peak RSS on Linux. The raw measurement and manifest hashes are in `run/window_oracle.json`.

## Final offline package

A fresh launch of the integrated `examples/scroll.json` mission and export produced the 43,115-byte ZIP with SHA-256 `03f8dbea716abd7108a03b2c947b21a13eb36617750c601733b85ae3b04de7e3`. Its isolated recipient passed 32 controls and reproduced all six registered output digests from the earlier archive. On this run the two sparse windows improved 12.91× and 11.28× over the preceding histogram path; the four other ratios ranged from 0.982× to 1.101×. The repeat used 17.484 s wall time and 18.187 child CPU seconds including a fresh mission and export, reusing the previously acquired data. One earlier final-package attempt exited at compilation without enough detail to determine the cause. The failed attempt and two independent cold compilations are recorded in `final-receiver/qualification-history.json`; the successful full retry and per-window values are in `final-receiver/summary.json` and `final-receiver/window_result.json`. To repeat from this directory with authorized CT inputs in `run/research_data`, run `python3 final_export_check.py . ../../.. /tmp/scroll-receiver-rerun`.
