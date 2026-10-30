# Rebuild the publication

The nine-page scientific paper remains frozen to its 95-input manifest and source anchor `326be47e40df57f868b1543e4d5385d490319cea`. Its published builder was independently executed from the downloaded `49838402a170f7c0447ca65fad97a37099a622ef` tree with `--no-compile`; all four generated text derivatives were byte-identical. Use that immutable tree to reproduce the historical paper, rather than substituting later checker source into its manifest.

The separate correction is anchored to `a8cda9befe434b5f906dc57077756cc987a8f03f`. Its builder requires Python, the declared `pypdf` authoring dependency, and a LaTeX installation containing `pdflatex`, `lmodern`, `microtype`, `booktabs`, `array`, `xcolor`, `xurl` and `hyperref`. The observed PDF engine was pdfTeX 1.40.25. These are publication-authoring dependencies; the core experiment dependency file remains separate.

From a source tree matching the correction's checker and receipt hashes, choose a fresh output directory:

```bash
python -m pip install -r docs/consequential009/requirements-paper.txt
mkdir /tmp/consequential009-paper
cp docs/consequential009/paper.pdf docs/consequential009/index.html /tmp/consequential009-paper/
python scripts/build_consequential009_corrigendum.py --source-anchor a8cda9befe434b5f906dc57077756cc987a8f03f --output /tmp/consequential009-paper
```

The builder refuses changed original-PDF bytes, changed checker sources, unaccepted native receipts, or accepting receipts for the original forged summaries. It emits the correction, a ten-page combined PDF and a reading edition with a correction banner. The original PDF and HTML remain unchanged. PDF creation metadata can vary between builds; component identities and the recorded visual/content checks delimit the published edition.
