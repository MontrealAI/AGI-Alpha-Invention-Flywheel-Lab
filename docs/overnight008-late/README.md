# Append-only late-results supplement

**MISSION NOT COMPLETE. Ongoing checkpoint; not final overnight closeout.** Both earlier papers remain unchanged.

[PDF](AGI_ALPHA_Late_008.pdf) · [LaTeX](AGI_ALPHA_Late_008.tex) · [GitHub-readable report](REPORT.md) · [HTML](index.html)

Scientific/code/evidence source: exact public commit `54f229bb0672201dd635a46f8edd71083f1e7bfe`, with **53 consumed source files** and snapshot SHA256 `7c0fe98cb5f57042b33d1bf49ad4bf5654fafb8e2eb18d3d4c3e260c6ee9d3a1`. The frozen builder reads all inputs, itself, its registry and six earlier-paper files directly from immutable Git objects. Byte provenance does not certify experiment truth.

The final PDF/LaTeX are explicitly recorded document-only derivatives. The frozen builder omitted `xcolor` while requesting its mixed-color syntax. Its first LaTeX build failed. [The original LaTeX](typesetting_original/AGI_ALPHA_Late_008.tex), [compiler error](typesetting_original/AGI_ALPHA_Late_008.log.txt) and [build stdout](typesetting_original/BUILD_PASS_1.log.txt) preserve the failure. [The exact patch](TYPESETTING_PATCH.diff) adds only `\usepackage{xcolor}`; [repair provenance](TYPESETTING_REPAIR.json) binds the original and corrected bytes. No scientific word, number, data, builder, registry or prior paper changed. HTML and Markdown remain direct frozen-builder outputs.

All three final pages were rendered at 120 DPI and visually inspected. The final compiler log has no warnings or overfull/underfull boxes. See [document provenance](DOCUMENT_PROVENANCE.json), [visual QA](VISUAL_QA.json) and [artifact hashes](ARTIFACT_SHA256.json).

Reproduction is two explicit stages, using a repository checkout containing the frozen commit plus this published typesetting artifact:

```sh
python3 scripts/build_late008_paper.py \
  --repo . \
  --source-ref 54f229bb0672201dd635a46f8edd71083f1e7bfe \
  --inputs docs/overnight008-late/SOURCE_INPUTS.json \
  --self-path scripts/build_late008_paper.py \
  --output /tmp/late-paper-NEW
```

In the recorded environment this exits with the documented `Undefined color` error after all source guards and text outputs succeed. Inspect that exact failure, then apply the supplied patch; do not ignore arbitrary build failures:

```sh
python3 docs/overnight008-late/apply_typesetting.py \
  --directory /tmp/late-paper-NEW
```

The patch script must match SHA256 `810e281b053d86f9051d3050b8b5a744310ce206cf2778a2c472d5b4b0fe4bf1`. It checks the precise declaration and failure, preserves originals and refuses an already repaired artifact. Re-render and inspect new PDF bytes; this package's QA receipt does not qualify a later build automatically.

No new scientific experiment or data acquisition occurred in this document task. It distinguishes data-archive integrity from actual downloaded NASA numerical construction/checking, preserves the zero-alias diagnostic and physical-data limits, and reads event28 costs rather than inventing complete profit. Qualified earnings remain zero. Initial failed-compile CPU was not captured and remains UNKNOWN, not zero; measured repair/render CPU is separate. The original 600 CPU-second paper reservation and mission endpoint remain unchanged.
