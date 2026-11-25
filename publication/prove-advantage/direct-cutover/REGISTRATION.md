# Direct included-Codex exploration

Original ambition as supplied: **CAPTURE THE EXPONENTIAL**

Registration adopted before obtaining reflectance observations or scored results, 25 November 2026. The exploratory control has no curated FRONTIER Ω treatment package. Both reserve the possibility that the best direct result is a useful negative result. Objective, treatment selection and matched result must be separately registered.

## Selection

- MODIS scientific continuity. NASA published the 1 December 2026 Terra science stop on 19 November. The same month NOAA-21 VJ209H1 became available on Earth Engine on 11 November, and on 23 November Planet announced switching its atmospheric correction to VIIRS on 30 November. A bounded cutover decision can advance real local monitoring and avoid silent false trends. The candidate is a transfer test against actual local observations under a data/credential constraint, with an independently reproducible refusal.
- CAD redesign on a limited number of costly simulation solves. Starostina et al. first posted their 1,650-parameter nonlinear study on 19 November. A credible adoption experiment requires a beneficiary's qualified part and simulator plus the incumbent design team or validated reference workload. No such assets or authority are present. A small numerical surrogate cannot establish an actual replacement.
- Evaluation of agent work under revised requirements. The public MaxxBench owners altered 89 DeepSWE tasks and graded required and regression checks; METR on 20 November reported public-model progress and the difficulty of lifecycle measurement. An actual selling point requires work contracts and costly accepted outcomes out of reach of ordinary tests. Existing evaluators are strong and likely tie on an authored test. A benchmark repackager is insufficient.
- Proof of model identity at inference. Anthropic's 2 November report announced FlashProve. Verifying exact transcript/model provenance could enable high-assurance contracting. No trusted independent inference operator, patient/regulated workload, actual model access or accepted budget is present; a hash audit is no substitute.

Select MODIS continuity because the timing, public data, target MONTREAL.AI research location, and concrete cutoff allow an actual preregistered operation without any external authority. NASA already offered transition guidance by 2025 and the 2017/18 literature already tested cross-spectral adjustment. The situation and product accessibility changed. The method is a conventional direct control, not claimed as a new method.

## Work product and decision

Return a bounded executable for whether a 500 m, 8-day red/NIR NDVI time series can accept replacing Terra (MOD09A1.061) with a specific VIIRS product using observed matched compositing windows and known differences. Identify the real privilege or science blocker when necessary. The primary product is NOAA-21 VJ209H1.002; assess its exact archive availability and authorization. An anonymous ORNL product/band metadata query returned 404 for VJ209H1 and VJ109H1, but 200 for Suomi VNP09H1.002 and Terra MOD09A1.061. If the newly catalogued source is not accessible anonymously, record it as BLOCKED and qualify only the explicit Suomi research subset. Never transfer acceptance to NOAA-21.

The two real site points, fixed before data inspection, are (45.432139, -73.950000) in the Morgan Arboretum research area and (45.550000, -73.316667) at the official Mont-Saint-Bruno park coordinates. The Morgan point comes from the Canadian Forest Service 1988 field-table coordinates and is a nominal coordinate probe at 463 m, not a surveyed plot or a NAD27 reprojection. This investigation is for MONTREAL.AI's environmental research, with no commitment or observation of operational adoption by the parks.

Use 17 composite starts per site per year (days 145 to 273 inclusive, every 8 days), 2024 as calibration and 2025 as held confirmation. Fixtures authorize pixel subsets and exact common grid/window, positive legal red/NIR values, strict sensor-specific cloud, land and snow filtering and band quality. Treat QA invalid, missing rows, mismatched grid/window and conflicting duplicate rows as unavailable. Each composite is one observation, selected across a period. Composite pairs are not coincident in time-of-day or source acquisition day. Do not count adjacent pixels computed from the same composite as independent. No truth claim on phenology or bias against physical observations.

Compare (i) underlying raw Suomi NDVI; (ii) a common easy median NDVI offset fitted on eligible 2024 pairs at the same site; (iii) ordinary per-band least-squares harmonization fitted on exactly those 2024 pairs. Terms derived without holding evidence. Also inspect Morgan-trained fits on Mont-Saint-Bruno as a deliberate transfer stress, never used to reselect after holdout. No simulated data deployed as observed. If positive, block extrapolation beyond observed calibration red/NIR range for guarded output and identify its reduced coverage.

Accept plug-in continuity for a single site only if at least 8 held eligible composites and at least 70% of the 17 requested held composites are scoreable, NDVI MAE at most 0.035, worst absolute error at most 0.08 and absolute mean signed error at most 0.015. Accept an added calibration benefit only if the same rule is met at both sites, band affine MAE improves at least 20% versus raw and median-offset at each site, and its worst error does not increase. These are conservative pilot decision tolerances declared prospectively, not sector-wide standards. With fewer eligible windows, return ABSTAIN even when the point errors are small. Count data retrieval, QA, calibration, verification, wall time, included-model and complete-cost unknowns separately. No charging, sign-in, external communications or downstream operation.

Hold-out red/NIR outcomes, exact method receipt and all cases are retained. No substitution for independently authored tasks or separate evaluator custody. Compare fit and score with an independent implementation when available.

## Checked dated sources

- [NASA Earth Observing System, 19 November 2026](https://terra.nasa.gov/2026/11)
- [NASA Land Product Quality Assessment cutover](https://landweb.modaps.eosdis.nasa.gov/displayissue?id=1546)
- [Earth Engine catalog release, 11 November 2026](https://developers.google.com/earth-engine/docs/data-catalog/release-notes)
- [Planet support, 23 November 2026](https://support.planet.com/hc/en-us/articles/40893230900253-Ensuring-Long-Term-Data-Continuity-for-Planet-s-Surface-Reflectance-Products)
- [NASA 18 April 2025 transition plan](https://ladsweb.modaps.eosdis.nasa.gov/learn/modis-to-viirs-transition/MODIS-VIIRS_Transition.pdf)
- [Yang et al., inter-consistency of NDVI for agricultural monitoring](https://pubmed.ncbi.nlm.nih.gov/29892137/)
- [ORNL NASA DAAC TESViS API](https://modis.ornl.gov/data/modis_webservice.html)
- [NASA MOD09A1.061 Earth Engine reference](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD09A1)
- [NASA VNP09H1.002 Earth Engine reference](https://developers.google.com/earth-engine/datasets/catalog/NASA_VIIRS_002_VNP09H1)
- [NASA VJ209H1.002 Earth Engine reference](https://developers.google.com/earth-engine/datasets/catalog/NASA_VIIRS_002_VJ209H1)
- [Canadian Forest Service Morgan table](https://publications.gc.ca/collections/Collection/Fo46-17-378E.pdf)
- [Canadian Geographical Names Database official Mont-Saint-Bruno coordinates](https://geonames.nrcan.gc.ca/search-place-names/unique?id=EKYDJ)
- [Starostina et al. engineering redesign study](https://arxiv.org/abs/2611.26003)
- [MaxxBench](https://benchlm.ai/benchmarks/maxxbench) and [METR, 20 November](https://metr.org/blog/2026-11-20-q4-2026-capability-update/)
- [Anthropic FlashProve technical report, 2 November](https://www.anthropic.com/research/provable-inference)
