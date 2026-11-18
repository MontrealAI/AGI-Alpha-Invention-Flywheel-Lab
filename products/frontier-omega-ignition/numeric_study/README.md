# Numerical Table Desk

A research editor can recover a printed table as CSV, keep its units and source-page identities, and withhold a candidate when a span or qualification cannot be justified. [Open the CSV from the published study](examples/publication.csv) · [Inspect its provenance](examples/publication-provenance.json).

The first registered source is MONTREAL.AI's published Enterprise-011 report. It describes simulated commercial trajectories. Its PDF prints four columns. Its HTML adds a fifth, a success-rate column that is absent from the printed table. The conventional export projects the source onto the four printed columns explicitly. A separate verifier checks every delivered CSV against the TeX used for the printed table.

| Registered table | Direct semantic export | Native PDF with cell geometry | Tesseract with cell geometry | Local NVIDIA model using the whole crop |
| --- | --- | --- | --- | --- |
| Printed simulation results, one page | 20/20 | 20/20 | 20/20 | 20/20 |
| Two-page calibration control | 25/25 plus both qualifying notes | 25/25 plus both notes | Withheld for a conflicting or missing two-row span anchor | Initial receiver withheld an unsupported LaTeX cell form |

The publication has four headings, four regime names and twelve quantitative entries. Both negative currency amounts, all percentage units, fractions and printed decimal precision survive. Cash-survival percentages measure the modeled trajectories described in the paper. The second table is a synthetic metrology control with signed mV values and percentages, fixed decimals, two-row spans, a repeated header and a footnote qualifying the operating temperature. It demonstrates behavior of the instrument on designed adverse conditions. [Initial protocol](REGISTRATION.md) · [Independent verification](AUDIT.json) · [Per-arm outcomes and costs](RESULTS.json).

## Receive the study independently

Use Python 3.11+ with PyMuPDF 1.26.6, ReportLab 4.4.9, Pillow and lxml installed. The recorded OCR used Tesseract 5.5.0 with its English language data. From the product directory:

```sh
python3 -B numeric_study/receive.py --output /tmp/nd02-received
python3 -B numeric_study/audit.py /tmp/nd02-received
python3 -B -m unittest discover -s numeric_study -v
```

Choose new output directories. The recipient validates the original PDF and HTML bytes and re-renders the three registered PNGs. Pinned crop identities depend on the recorded renderer and fonts. Accepted directories contain `table.csv` and `provenance.json`; the metadata includes both physical pages and their qualifying notes, where applicable. Withheld arms have no deliverable CSV. Published TeX provides a separate reference for the real printed table; an independent XML parser checks the synthetic authors' rows, spans and notes.

Rebuild source images with `python3 -B numeric_study/prepare.py /tmp/nd02-images`. Rerun actual inference with the official checkpoint files from the [original Table Desk model instructions](../table_desk/NVIDIA-ARM.md), adding `run_transformers_inference.py` at the same pinned revision to the download. From the product directory run:

```sh
python3 -B numeric_study/observe_model.py --model /tmp/td01-model \
  --python /path/to/model-venv/bin/python --output /tmp/nd02-new-model
python3 -B numeric_study/receive.py --model-observation /tmp/nd02-new-model \
  --output /tmp/nd02-new-evaluation
```

The original three model observations, raw LaTeX generations, exact model weights/driver identifiers, and per-crop timings are [preserved here](model_observation/observation.json). Hash checking, loading and three independent processes with four CPU threads took 68.2773 wall seconds. The accepted published-table model call took 14.5405 seconds, including process setup and model load. Direct semantic projection took 0.000261 seconds, native PDF 0.488043 seconds and segmented OCR 1.514294 seconds in their receiver windows. Those windows exclude source preparation and shared crop rendering. The model saw no reference or per-cell guide. Conventional PDF/OCR arms received registered geometry. Labor to register geometry, complete engineering and delivery costs, taxes, buyer uptake and comparative reader time remain unmeasured.
