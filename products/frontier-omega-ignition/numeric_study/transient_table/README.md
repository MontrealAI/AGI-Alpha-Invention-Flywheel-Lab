# Reading a transient without losing its observing conditions

An observer evaluating a past detection needs to preserve missing bands, magnitude signs and observing-window notes. Terwel et al. distinguish a detected range from an unobserved band and report their timing relative to discovery. Their Table 4 has three header levels, three footnote marks and nine ambiguous-origin objects. This is a fresh technical extraction task for the Numerical Table Desk; the article supplies historical context, not the Fink catalog used to plan a night.

| Route on the registered table | Correct scientific fields / 63 | Correct object IDs / 9 | Recovered table-wide conditions / 2 |
| --- | ---: | ---: | ---: |
| First included visual transcription of physical page 10 | 63 | 9 | 2 |
| Direct extraction of the PDF text and glyph positions with Poppler | 63 | 9 | 2 |
| Direct structured export from the author’s versioned HTML, the reference | 63 | 9 | 2 |
| Unmodified historical Table Desk on the native semantic table | Withheld | Withheld | Merged header needs a rectangular reference |

The 63 fields comprise redshift, host separation, two timing fields and three photometric bands for each of the nine objects. Decimals retain their printed precision. Ranges retain both signs. Each missing band has an explicit null; a superscript remains associated with its specific field. The two conditions cover rounding to ten rest-frame days and the interpretation of detected absolute magnitudes. Superscripts 1–3 respectively flag a published second detection period, censoring at survey start, and boundaries affected by gaps or data availability. These historical rows do not establish that an object received follow-up from our planner.

**What changed the decision.** The reader limited to rectangular author tables correctly deferred on the multi-level header. Direct semantic export and PDF text extraction both delivered the complete registered data. No ranking by scientific accuracy or incremental AI advantage was earned here. The sign/precision comparison checks both the retained image reading and the conventional extractor. The shared authorship of the PDF and HTML limits the claim to transcription, never astrophysical truth.

**Costs and scope.** The pinned local extraction observed 0.025 s for HTML, 0.061 s for Poppler/PDF and 0.015 s for the existing reader, including source hashing and parser imports in their execution order. Input acquisition (1,145,836 PDF bytes, 367,987 HTML bytes), page rendering, comparison design, included-model reading and implementation also consumed resources. Their complete elapsed time and monetary amounts were not measured. The visual reader saw the registered headers and caption before the page. Raw HTML data rows were inspected after freezing its transcript. There was no human-reader trial. The historical Nemotron arm has no result for this PDF; its pinned local model and inference dependencies were unavailable in this runtime. External model prices, procurement, time savings, demand and production economics remain unknown.

## Reproduce

From the product directory, run the offline audit on the retained independent observations.

```sh
python3 -B numeric_study/transient_table/study.py
```

For a fresh extraction, install lxml and Poppler's pdftotext in an authorized environment. Download the two versioned publications, then compare the three observations with the registered record. The script refuses a change to either source digest.

```sh
curl -fLsS https://arxiv.org/pdf/2503.19558v1 -o /tmp/terwel25.pdf
curl -fLsS https://arxiv.org/html/2503.19558v1 -o /tmp/terwel25.html
python3 -B numeric_study/transient_table/study.py --pdf /tmp/terwel25.pdf --html /tmp/terwel25.html
```

To inspect the visual witness, use `pdftoppm -f 10 -l 10 -r 135 -singlefile -png /tmp/terwel25.pdf /tmp/page10`. The original Poppler 26.05.0 image SHA-256 was `91d9616d78be5471f36003dbaa1fe7b63f54d7d79d6fd498a88a8fd8c10f0898`. Renderer and font versions can change these pixels. The result records both publication byte digests, the frozen first transcript hash and notes.

Source and attribution: J. H. Terwel et al., *ZTF-observed late-time signals of pre-ZTF transients* (2025), Table 4, adapted into typed scientific cells, normalized ranges and labeled notes. [Publication and authors](https://arxiv.org/abs/2503.19558v1) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · [Registered comparison](REGISTRATION.md).

## Does NOMAI’s historical inspection identify the planner’s targets?

The April author edition of Russeil et al. lists 83 unique ZTF object IDs in five inspection categories on appendix page 12. All 83 category assignments matched across the HTML export, physical PDF text layer and the unmodified Table Desk. The PDF and HTML caption independently identify the provisional photometric basis for potential SLSNe. The original rectangular reader does not export that caption.

| Inspection category as printed | Objects |
| --- | ---: |
| True positives | 22 |
| Potential-SLSN | 17 |
| Compatible | 12 |
| SNIIn | 4 |
| False positives | 28 |

**None of the six archived targets in the new planning catalog appears among these 83 inspected objects.** The paper’s separately reported recovery of 22 out of 24 active known examples answers a different question. The historical inspection therefore supplies no object-specific confirmation or calibrated probability for these six later alerts. The planner gave them equal weight. Its accepted result concerns feasible visits.

The recorded extraction covers every ID in the author edition of this table and this six-ID catalog. A single included engineering session selected and checked the comparison. Acquisition, engineering and monetary costs were not fully metered. Per-route wall time appears in the compact observation. No scientist or observing facility participated.

```sh
python3 -B numeric_study/transient_table/nomai.py
curl -fLsS https://arxiv.org/pdf/2604.14761v1 -o /tmp/nomai.pdf
curl -fLsS https://arxiv.org/html/2604.14761v1 -o /tmp/nomai.html
python3 -B numeric_study/transient_table/nomai.py --pdf /tmp/nomai.pdf --html /tmp/nomai.html
```

Attribution: E. Russeil et al., *NOMAI* (2026), author edition Table 3. IDs were regrouped for a source-bound intersection test. The September journal publication and the April author edition have separate version identities. [Tested edition](https://arxiv.org/abs/2604.14761v1) · [Journal publication](https://doi.org/10.1051/0004-6361/202660399) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
