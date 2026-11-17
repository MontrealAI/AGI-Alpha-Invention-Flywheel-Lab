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

## Registered observation

The [registered protocol](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/c326679543960c3d364f1582d91e9cb0e61d406f) preceded the [scored producer and independent checker](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/971abc64c3545d5e476c9cb36e71ed8bf41eb925). One process per arm completed successfully. The [observation](RESULTS.json) records the content hashes, environment and process times.

| Recipient or control | Observed result |
| --- | --- |
| Reading Room | All 37 source blocks preserved in order. 34 correct unique page links, zero incorrect. One passage crosses pages 2–3 and two math paragraphs need the source. |
| Independent MuPDF clickable edition | 31 correct links, zero incorrect. Keeps all three tables, both MathML equations, links and the bibliography in the original markup. |
| Original HTML and PDF | All 37 source blocks already available; no passage-level PDF links. Original PDF viewer retains ordinary Find and visual navigation. |
| Poppler native text | All five pages produced text. Native extraction alone requires the reader to reconcile passages to the author edition. |
| Five adverse blocks | All five passed. Both unique pages were correct. A two-page repeat, altered quantity and split passage received no invented link. |

With the native extractor used here, the three additional correct links over the conventional comparator were blocks 9, 26 and 35. The registered paper has five physical pages and no heading/paragraph blocks on page 5. The independent comparator is preferable for a reader relying on the original tables or MathML. This conditional technical difference did not establish task-time savings, general superiority, a frontier crossing, an economic advantage or buyer acceptance.

The observer around the scorer timed the four arms and adjudication together and hashed every file in the delivered recipient. Reproduce the observation with `python3 products/frontier-omega-ignition/reading_room_study/observe.py --output /tmp/rr01-observation-new`; compare the `publication_receipt.recipient_sha256` field in `observed.json`. Building the actual paper took 0.084 s and the conventional clickable version took 0.148 s on the observed host; these single measurements are implementation telemetry and have no human-productivity interpretation. Engineering effort and complete delivery costs remain unknown.
