# RR-02 · retain the author's complete reading edition

**Decision.** For two explicitly pinned public manuscripts, offer the existing author XHTML with independently checked PDF-page anchors, preserving tables, MathML, bibliography, headings, inline links and code. The first paper is a reuse check. The second is fresh transfer. Freeze this decision and page key before scoring. RR-01 is immutable.

**Inputs.** Cycle 001 uses the two digests registered in RR-01. Cycle 007, a different paper by Vincent Boucher dated 30 October, has 71 heading/paragraph blocks across seven physical pages. HTML SHA-256 cf1b5583aa251226cecc9fae991061c783fd5ff6088710b94db9183b02260738; PDF SHA-256 816f02210ffae281aac747af57aa59f02a79db2d4e36c639808527269b6ad662. The evaluator visually inspected all seven original pages and manually recorded the physical-page key for the independent second case. Neither constructor may read the key. The author editions are at docs/research/cycle-001 and cycle-007 with .html and .pdf extensions.

| Cycle 007 ordinal | Physical pages |
| --- | --- |
| 1–9 | 1 |
| 10 | 1 and 2 |
| 11–21 | 2 |
| 22–34 | 3 |
| 35–43 | 4 |
| 44 | 4 and 5 |
| 45–56 | 5 |
| 57 | 5 and 6 |
| 58–64 | 6 |
| 65–71 | 7 |

**Complete alternatives.** Give an independent ordinary source-to-page matcher the same Poppler text and the same source HTML, using whitespace/ligature normalization, full-block token matching and ambiguity abstention. Use the conventional author-markup-preserving renderer in both arms. Register the earlier independent MuPDF comparator separately. Original HTML and reader Find are available without installation. AI/human user time and complete economic costs remain unmeasured. This evaluates a specifically requested capability beyond author summaries; no document-model inference is claimed.

**Adopt the annotated edition** for a paper only if removing the inserted local page anchors and inert-content policy restores a canonically identical XHTML DOM, original document links/references are preserved, matching PDF bytes are packaged, each accepted anchor lands on the independently registered physical page, and all split blocks remain unlinked. Return the paper for source review if these conditions fail. Report all anchor counts on each paper. Report the strong conventional result even if it matches or wins. No claim of unique engineering advantage from this transfer. Require refusal of input identity changes and altered receipt content. Score one registered attempt per paper and arm; keep attributable repair or later reproduction separate.
