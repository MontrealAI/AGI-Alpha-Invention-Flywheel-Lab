# GENESIS — design the observation

**Discovery question:** could increasingly capable scientific/engineering agents make purpose-specific measurement systems economical, rather than asking every user to purchase a general-purpose laboratory instrument?

This is a first raw-data falsification test of one necessary condition, not a declaration that the business exists. The concrete candidate constructs a six-band optical measurement specification for identifying six known polymers in mixtures. A numerical filter specification is not a fabricated sensor. Real buyer demand, detector performance, optics, acquisition noise/speed, calibration, cost and independent field acceptance remain unmeasured.

## What changed at the frontier (inspected 4 November 2026)

OpenAI's 3 November physical-engineering report connects mechanical/electrical design, software and simulation, but still reports manufacturing review and internal-only capabilities. Google DeepMind's 3 November cheminformatics release connects scientific reasoning with executable specialist tools; proposed molecules still require experiments. These developments motivate testing more integrated construction workflows; neither establishes this sensing capability or that it was impossible last week.

- https://openai.com/index/accelerating-engineering-for-the-physical-world/
- https://deepmind.google/blog/agentic-cheminformatics-with-google-antigravity/
- https://research.google/blog/empirical-research-assistance-era-from-nature-publication-to-catalyzing-computational-discovery/ (3 November MCP update; approved-user access, not assumed installed)

## Three materially different possibilities

1. **Task-specific scientific sensing.** Turn a consequential material-identification requirement into an acquisition specification and interpretation program. A successful small sensor could enable measurements where a complete laboratory workflow is unaffordable. Strong alternatives include existing spectroscopy, commercial sorting equipment, conventional chemometrics and scientists using the same AI. Selected for this computational probe because actual raw public spectra make a decisive no-hardware first comparison possible.
2. **Research-to-production algorithms.** Translate newly supported scientific/mathematical methods into executable industrial tools. OpenAI/math explicitly describes unevenly verified raw research from an internal model. Each candidate needs a theorem-to-algorithm/application bridge and must beat competent established numerical methods at complete cost. No particular theorem has yet earned selection here.
3. **Verifiable AI services.** Combine inference-origin evidence and independent outcome acceptance so buyers can outsource useful work on better terms. The repository's separate PR240 owns its new verifier investigation; this branch neither duplicates it nor assumes that provenance proves correctness. Buyer and strongest signed-receipt/TEE alternatives still matter.

These are opportunity hypotheses, not measured market rankings. This probe does not preempt the battery, thermal, surface or native-commerce owners.

## A consequential discovery before coding

The convenient mean-reflectance dataset has already undergone continuum removal, full-spectrum normalizations and smoothing. Selecting six columns from it would silently retain information from the full spectrometer. That would not test a genuine six-measurement pathway. The authors' source states this preprocessing:
https://zenodo.org/records/14419753/files/NIR_PlasticMixes_BandEQs.py?download=1

A newer camera-array comparator exists (Kossira, Seiler, Kaup, 2026; https://arxiv.org/abs/2608.22531). Its repository README currently points to a database marked TBA: https://github.com/FAU-LMS/MHPM . Do not count a proposed public dataset as downloaded evidence.

Therefore this test starts from the raw ASD archive, not the convenient processed CSV. The measurement projection uses only its own wavelength range. Training-derived normalization is fixed, and test inference does not use unselected wavelengths. The reference conversion follows the public SpecDAL same-channel target/reference logic; the decoder checks supported type/layout and independently unpacks numerical bytes. This is not independent instrument metrology.

## Registered before payload access

`PROTOCOL.json` was committed first at `5e1bf15a7fdf21a9afb83bd1bdb846042b982d06`. Publisher documentation and parser documentation were read, but no spectral payload was opened before that freeze. Fit on three soils, choose models on concrete, and score once on vegetation and water. Average instrumental repetitions within a specimen condition; do not treat them as independent materials.

All six polymer types are used at 5%, 15% and 50% mass concentration. This is closed-set material identification, not environmental trace detection. Expected unit counts are 54 training, 18 validation and 36 test condition means. This small single-laboratory experiment cannot establish generalization to unseen manufacturers, fields or devices.

Compare the full 850–2400 nm recorded spectrum, 22 integrated bands, uniform six-band selection, training-ANOVA selection, group-aware sequential forward selection, and ten seeded random six-band plans. Every plan receives the same five classifier candidates. The strongest conventional method is a tool in GENESIS, not an artificial opponent. Freeze the chosen sparse and reference plans before test scores. Report every test arm; never select a winner using the test outcomes.

The public-data workflow is an assistant-authored application of established methods. No unattended frontier-agent campaign, new band-selection algorithm, AI-versus-human benchmark, model improvement or learned inventor is established.

## Reproduce

```sh
python -m pip install -r research/genesis_spectral/requirements.txt
python -B -m unittest discover -s research/genesis_spectral -p 'test_*.py' -v
python -B research/genesis_spectral/study.py --out /absolute/new/spectral-study
```

The study downloads a single checksum-bound public archive temporarily, records SHA256 as well as the publisher's MD5, processes it, then removes the temporary raw archive. It does not extract archive paths or publish the bulk input. The output includes the frozen plans, all comparisons and predictions, the six-band research specification, and `START_HERE.html`. Runtime uses no model account, API key, payment service or hardware. Failed retrieval/decoding/completeness remains a failed run; it is not replaced by another favorable dataset.

## Source credit and scope

Holt, Khan and Rodrigues, NIR/SWIR Spectral Library of Plastic-Substrate Mixtures, Zenodo record 14419753 (2024), CC BY 4.0 according to the publisher README. https://doi.org/10.5281/zenodo.14419753 ; https://creativecommons.org/licenses/by/4.0/ . This workflow performs new analyses, grouping and ideal band integration. It does not imply author endorsement. Existing spectroscopy and feature selection are not attributed to GENESIS as inventions.

No modified native account, financial ledger, private user material, paid model use, buyer contact, merge, release or deployment. Source/CI correctness, computational acceptance, physical qualification and commercial viability are separate verdicts. Historical source and failed comparisons remain unchanged.
