# N1 independent provenance review

Date: 2026-11-02. Reviewer: `independent_scientist`, procedurally separate from the adapter constructor on the same host. This is a bounded source review before fresh sensor outcomes, not physical certification. Frozen W1 outcomes at `a5df603854f98cbd673204258c8d768e0c759975` remain unchanged.

## Newly retrieved authoritative information

The [publisher supplement](https://static-content.springer.com/esm/art%3A10.1038%2Fs44221-024-00314-6/MediaObjects/44221_2024_314_MOESM1_ESM.pdf) was successfully retrieved: HTTP 200, 1,634,588 bytes, 22 PDF pages, SHA256 `97f37f427764ff8cee536aa22f4b340dfcd8382d6993e1ca9e32f055e2239f61`. This resolves the earlier transport failure, not the quality-acceptance gap. Credit Bessette, Pratt and Winter, [Nature Water 2024](https://doi.org/10.1038/s44221-024-00314-6), under the article's CC BY 4.0 terms, subject to any separately credited material.

The reviewer extracted the text and visually inspected PDF pages 7-8, printed pages 19-20:

| Source | Established fact | Not established |
| --- | --- | --- |
| Table S1, PDF p7 / printed p19 | Nine process states. State 3 includes reversal; 6 recirculates; 7 drains diluate with product bypass on; 8 drains concentrate; 9 performs post-batch checks. | Which archived tag records these states; logged transitions; batch-level acceptance at each release. |
| Fig S2C, PDF p8 / printed p20 | Physical flow diagram, reversal plumbing, inlet/outlet conductivity locations and product routing. | Mapping from unnumbered conductivity symbols to `conductivity1_DS` through `conductivity4_DS`. Numbers 1-10 identify valves, not conductivity channels. |
| Table S1, sensor specifications | Outlet instrument is Sensorex TCS3020; the stated uncertainty depends on span, and two-second averaging is listed. | Installed span, calibration coefficients/standards/dates, calibration validity or actual temperature-compensation settings. |
| Table S1 caption versus article controller section | Caption states a 100 ms PLC sampling interval; article describes 100 Hz readout. | Equivalence of these clocks, archive aggregation timing or a justified reconciliation. They may describe different layers and must not be silently conflated. |

The [Figshare metadata API](https://api.figshare.com/v2/articles/24991158) returned version 1, 193 CSV files and CC BY 4.0 attribution to Jonathan Bessette, Amos G. Winter V and Shane Pratt. The retrieved metadata response SHA256 was `31333b52afe1d5ea849589869a65643adb09b46a27ffd5fb1c43b2dd9c4b652f`. This is a retrieval receipt, not a frozen local copy or a promise that dynamic metadata will retain that hash. Inspected descriptions identify conductivity sensors only by number and do not specify a process-state tag or PLC-code link. No fresh sensor CSV measurements were opened. A metadata omission does not prove that no undocumented measurement field exists.

The primary [Sensorex installation instructions](https://sensorex.com/wp-content/uploads/2021/09/TCS3020-Instructions.pdf) describe calibration after installation using known standards and installation-dependent geometry. The [manufacturer specification](https://sensorex.com/wp-content/uploads/2018/09/TCS3020-Specification-Sheet.pdf) describes selectable temperature elements. These were inspected through primary-source web retrieval; manufacturer PDF byte hashes were not collected in this review. Device capability does not establish the field pilot's installed calibration or compensation.

## Bounded retrieval and remaining source

Publisher/DOI web retrieval encountered redirects; direct public publisher HTML supplied the supplement link and the direct PDF retrieval succeeded. Figshare DOI web retrieval failed, while the public metadata API succeeded. Exact paper/title/author/GitHub searches did not locate an authenticated public PLC repository. A same-name GitHub profile was not treated as the paper author's account.

An additional author source was found but its full contents were **not inspected**: Jonathan Bessette, *Control, design, and field validation of photovoltaic electrodialysis desalination systems for decentralized applications*, MIT, February 2026, [repository record](https://dspace.mit.edu/entities/publication/bec7ff50-942f-44af-aa01-46868098c735). Its metadata reports 78.43 MB, MD5 `1c19f6f905a4367956aba90f3d0d4e08`, and CC BY-NC-ND 4.0. Indexed searches did not reveal a tag dictionary; this is not a full-text negative finding. The review does not claim exhaustive public-source absence.

## Admission implication

The retrieved sources do not yet connect archived sensor identity, historical calibration, process-state timing and releasable batch volume. Keep these fields UNKNOWN and quality HOLD. A numerical counter increment is not batch acceptance. Choosing the lowest conductivity or correlating channels with production would replace missing provenance with an outcome-dependent rule.

The next source that can change the decision is an authoritative tag-to-instrument dictionary plus logged release-state/batch association and calibration/temperature records. Until then, a fail-closed adapter is an executable unsupported-mapping result. Another storage sweep or fresh-date download cannot supply the missing semantics. This conclusion does not establish physical impossibility or contradict the original authors' experimentally demonstrated controller.

Independent implementation review and challenge execution are separate later steps; neither is claimed by this source note.
