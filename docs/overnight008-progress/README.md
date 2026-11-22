# Ongoing progress paper: exact source freeze plus recorded typesetting

**MISSION NOT COMPLETE. This is an ongoing checkpoint, not final overnight closeout.** The original window still ends at 11:07:44 UTC on 30 October 2026.

[PDF](AGI_ALPHA_Progress_008.pdf) · [LaTeX](AGI_ALPHA_Progress_008.tex) · [GitHub-readable report](REPORT.md) · [self-contained HTML](index.html)

The paper's scientific/code/evidence source is exact public commit **`2b7a58e6e6593ae48da6f7f33865db94868c957f`**. The builder reads all **100** consumed inputs directly from that immutable Git source, including its own bytes, the frozen registry, and the historical report. The source/data snapshot is `544eb4eaff1a8cf0cd78aaa1bd51fd9e94595297755776fd5543ec406cf28262`.

The final PDF and LaTeX are explicitly recorded typesetting derivatives: an unbreakable status label overflowed one table cell. `apply_typesetting.py` inserts three `\allowbreak{}` commands after its underscores, without changing any scientific word, number, input, builder or registry. [The exact diff](TYPESETTING_PATCH.diff), [repair receipt](TYPESETTING_REPAIR.json), [document provenance](DOCUMENT_PROVENANCE.json) and [original overflow PDF](typesetting_original/AGI_ALPHA_Progress_008.pdf) preserve that history. The original LaTeX and compiler log are also under `typesetting_original/`. HTML and Markdown remain unchanged outputs of the frozen source builder.

All ten final PDF pages were rendered and visually inspected. [Visual QA](VISUAL_QA.json) establishes document readability only. [Artifact hashes](ARTIFACT_SHA256.json) establish bytes, not experiment truth. Source-specific downloaded-package qualification and the red legacy SIGINT check are reported separately in the paper. Later coordinate-repair and paired fuel-cell work are outside this freeze; no unexecuted result is silently included.

Reproduce from a public repository checkout that contains the exact frozen commit and these subsequently published typesetting artifacts:

```sh
python3 scripts/build_progress008_paper.py \
  --repo . \
  --source-ref 2b7a58e6e6593ae48da6f7f33865db94868c957f \
  --inputs docs/overnight008-progress/SOURCE_INPUTS.json \
  --self-path scripts/build_progress008_paper.py \
  --output /tmp/progress-paper-NEW

python3 docs/overnight008-progress/apply_typesetting.py \
  --directory /tmp/progress-paper-NEW
```

The executing builder must match the frozen source bytes. The style script must match SHA256 `701cdaee5bd54b3d348fd263221f727ffdf67c918d7403902c9aff96036992ba`. It refuses an already repaired artifact and preserves first-build outputs. Render and inspect the newly generated PDF again; an old QA receipt cannot qualify new bytes.

Build, repair and rendering receipts cover measured document processes only. Prior lost work, model inference, orchestration and complete monetary costs remain UNKNOWN. This work stays inside the original 600 CPU-second paper reservation; no time, resource or error budget is renewed. No numerical experiment is performed by these document builders. No campaign candidate, verifier, authority, historical paper, frozen builder or registry was modified by this artifact-only repair.
