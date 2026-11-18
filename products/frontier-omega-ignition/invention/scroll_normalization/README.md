# Normalize flat ink-inference patches from scroll CT

The recipient converts one raw unsigned-byte image patch to the little-endian float32 values consumed by a flat-ink research model. For a patch in which half or more of the voxel intensities coincide, the robust statistic can have zero median absolute deviation. The program then uses the original CPU standard-deviation calculation in voxel order while reusing the histogram. This avoids sorting and allocating more arrays. Dense patches use the existing histogram implementation.

The release contains the exact public CPU source, its license, the proposed patch, a compile wrapper and direct comparators. Linux x86-64 was tested with Python 3.12, GNU C++20, and GNU patch. Source acquisition and model inference are separate from the offline receiver. The input must be uncompressed, single-channel uint8 voxel bytes, 1 to 50 million values. Supply one model patch per invocation so its percentiles have the intended scope. For example a 17×384×384 patch is 2,506,752 bytes and its result is 10,027,008 bytes. Tensor dimensions and byte order of indexing stay unchanged. The operation clips to the 1st and 99th percentiles and uses robust scaling. Input bytes are never uploaded.

## Use

From the extracted recipient directory:

```sh
python3 -IB scroll_tool.py self-check
python3 -IB scroll_tool.py normalize --input patch.u8 --output patch.float32
python3 -IB scroll_tool.py verify --input patch.u8
```

The self-check compiles three real C++ operators and compares their output on 32 local controls. The verify command runs both pinned alternatives against the candidate on your own bytes. A mismatch exits with an error. The output argument is an ordinary file path and an existing output file will be replaced after success.

For repeated use, avoid compilation on every invocation by supplying the same trusted private cache. The cache contains locally compiled libraries. Compiler identity, target architecture and source bytes are part of its key. The receiver verifies the stored binary digest and rebuilds incomplete or damaged cache entries before use.

```sh
python3 -IB scroll_tool.py prepare --cache ./local-compiled
python3 -IB scroll_tool.py normalize --cache ./local-compiled --input patch.u8 --output patch.float32
```

## Registered measurement

The beneficiary problem came from [a flat-ink operator’s real workload](https://github.com/ScrollPrize/villa/issues/2522). Compare the published [histogram implementation and full Reader V3 evaluation](https://github.com/ScrollPrize/villa/pull/2521). That researcher identified the sparse-case fallback, improved whole inference from 55.2 to 41.2 seconds on PHerc0139 w054 and recorded only 3.7 seconds of remaining GPU input wait. Those timings belong to the earlier contributor. This candidate adds an exact CPU optimization for that remaining class of patches. The upstream GPU path and recent [GPU inference alternatives](https://github.com/ScrollPrize/villa/pull/2525) require their own evaluation.

The hypothesis, positions, comparators and stopping rule appear in REGISTRATION.md. The registration was hashed before acquiring the public CT chunks locally. It is an internal sequence record. The chosen scroll was known to the upstream author; these are prospectively specified positions inside a previously studied scan. This is a test of an incremental change to a recently published AI pipeline. Earlier feasibility was not tested. No run here used an inference model in the timed CPU code.

The pinned base is 14d4e725df8b569e6fc8ceb3c04d130f705c1565. Its six compiled dependency headers were also byte-identical to the November 18 upstream main 0bddf2757ea1e97572e86d06d448d8e4a7e207b3. The stronger exact-output alternative is upstream contributor LynnHenry’s draft 4c0a117f4ae983992bbe2ce134c0389d7280f120. `upstream.zip` groups verbatim upstream files under base/ and incumbent/ with their original paths. The CPU patch can be inspected or applied on that exact contributor revision with `git apply candidate.patch`. The candidate is provided in this research repository, pending any separate upstream review.

| 17×128×128 measured crop | Prior best median | Proposed median | Relative speed |
| --- | ---: | ---: | ---: |
| Nonconstant zero-MAD, row 30 col 86 | 6.105 ms | 0.630 ms | 9.69× |
| Nonconstant zero-MAD, row 50 col 86 | 6.091 ms | 0.612 ms | 9.96× |
| Thirteen other nonconstant crops | Per-case samples in result.json | Per-case samples in result.json | 1.011× median ratio |

Fifteen retrieved nonconstant crops of the 18 registered positions were byte-identical across all three operators. Three missing S3 chunks were counted and excluded from positive evidence. Two sparse crops met the speed criterion. The 13 other crops passed the registered regression limit. These timings cover the normalization call in one CPU process. They exclude assembling files and tensors, model execution, rendering, subsequent image analysis and user review.

An independent second trial reconstructed the original 2,122 scheduled Reader V3 tiles and prospectively selected six full-size 17×384×384 windows, using the original centered depth and occupancy mask. All six were byte-identical across all three CPU operators. The first and last scheduled windows had zero MAD and improved 12.71× and 11.09× respectively. The other four ranged from 1.005× to 1.022×. These six purposively selected windows cannot estimate the frequency of sparse windows on this or another scroll. The independent trial retained its source digest, registration, metadata, per-pass CPU timings and acquisition scripts alongside this package in the research repository.

For the real-data experiment, read the dataset’s attribution, access conditions and [CC BY-NC 4.0 terms](https://scrollprize.org/data_browser/PHerc0139). This recipient includes no original CT voxels. To repeat the research experiment with authorized use and public network access, use the following commands. `acquire.py` records URL, missing objects, and raw and selected-plane hashes. `benchmark.py` compares every acquired crop byte for byte in seven counterbalanced timed passes after warm-up and writes a fresh receipt.

```sh
python3 -IB acquire.py
python3 -IB benchmark.py observations new-result.json
```

## Cost, rights and the commercial decision

Fifteen uncompressed source objects transferred 6,881,280 payload bytes, plus metadata, listings and three missing-object responses. The recorded primary comparison including compilation took 5.161 wall seconds on the test runner. The independent full-size window trial transferred 52,171,228 bytes in approximately 199 seconds. Its recipient comparison took 11.153 wall seconds and 11.952 process-plus-children CPU seconds including compilation and checks. The measured per-call times exclude compiling the operator. No paid API, cloud rental, GPU run, transfer of funds or authorized outreach occurred. Metered agent or host cost, labor, overhead, end-user review time and delivery support cost are unknown. Economic return, total benefit and profit cannot yet be calculated.

The upstream program is MIT-licensed. Retain SOURCE-LICENSE.txt and the contributor attribution. The [November progress award](https://scrollprize.org/prizes#progress-prizes) accepts open-source tools that help read scrolls and considers significant real-data improvement and demonstrated use. The next published deadline is November 30, 2026 at 11:59 p.m. Pacific. The best monthly contribution receives US$20,000. Other discretionary awards range from US$250 to US$20,000. Selection, acceptance, installation by a beneficiary, and payment have not occurred. Already-read material from this scroll cannot qualify this measurement for a First Letters award.

The proposed handoff is to let the Scroll Prize technical or annotation team run the CPU patch on a representative full Reader V3 configuration, review identical TIFF hashes and measure whole-run wall time and queue wait against their current methods. Their confirmation that the change improves a workflow they actually run is the next acceptance test. Publish or submit only with the owner’s explicit authority for upstream outreach and any permissive licensing commitment covering the new contribution, then await sponsor review. Research access to CC BY-NC scan data does not establish rights to sublicense the scans or use them in a commercial customer deployment. The small patch, compiler wrapper and acceptance design can be reused on separately authorized inputs.
