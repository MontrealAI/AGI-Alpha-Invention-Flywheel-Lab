# Reproduce the Reading Room study

The public research benchmark uses the authored HTML and the printed pages of the first AGI ALPHA campaign paper. A researcher may open the existing paper, the new passage edition, or the independently implemented clickable MuPDF edition. The latter preserves the original tables, bibliography, links and math markup.

From the repository root, with Python 3.11 or later, Poppler's `pdftotext`, PyMuPDF and lxml available:

```sh
python3 products/frontier-omega-ignition/reading_room_study/run.py --output /tmp/rr01-new
```

Choose a new directory for each invocation. Open `candidate/index.html` or `conventional/index.html` inside that directory. The paper and both readers work offline. Online citations in the existing author edition still require their publishers. For only the independent conventional version, run:

```sh
python3 products/frontier-omega-ignition/reading_room_study/compare.py \
  docs/research/cycle-001.html docs/research/cycle-001.pdf /tmp/rr01-conventional-new
```

The candidate itself only needs Python and Poppler. The recipient study additionally uses MuPDF for the complete conventional alternative and lxml for independent HTML inspection. Reference environment versions are recorded in `RESULTS.json`. Opening a source PDF at a physical page depends on the PDF viewer's support for the standard page fragment. The receipt also makes the page number available directly.

The committed [protocol](PROTOCOL.md) fixes all 37 source blocks and the expected physical pages. The original math PDF and authored markup remain authoritative. The evaluator checks actual local output against the frozen key. Process success and scientific outcomes are separate: read the boolean verdicts, denominators, omitted indices and costs in `RESULTS.json`, including when the reproduction process exits successfully.

The scored-run directory contains the full reproducible recipient and both baselines. Only compact results belong in the repository. Reproductions should compare substantive verdicts, source and producer identities and counts. Process timing and host versions can differ.
