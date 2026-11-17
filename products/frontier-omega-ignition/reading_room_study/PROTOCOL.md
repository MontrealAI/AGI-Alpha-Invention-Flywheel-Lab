# Reading Room · registered recipient study RR-01

**Decision.** Can a researcher start with the existing public HTML and PDF of one Montréal research paper, open an offline edition in author order, and follow reliable links back to physical PDF pages? Links are useful at passage level even when the entire paper cannot be represented. The existing HTML and PDF remain the complete editions.

**Registration order.** Freeze this protocol and the physical-page key below in Git before any candidate scoring. The evaluator inspected the author HTML structure and visually inspected all five rendered pages to create the key. The builder receives only the two source files, no page key or successful reference links. Distinct agents own the builder and adjudication, within the same engineering team. The public registration is reproducible rather than secret or third-party blinded.

## Population and independent reference

Use research edition 001, *AGI ALPHA Invention Flywheel Lab*, 29 October 2026. The author publishes a substantive, complete Pandoc HTML edition with paragraphs, headings, lists, tables and math alongside its five-page PDF. Inspect every heading and paragraph in document order in the published body; include title/byline, equations and every hard case. Count tables and lists separately as out-of-scope whole-publication structures. A language declaration inferred from content is unnecessary. Retain the two sources at their original lawfully public repo paths.

| Source at commit ebc8341e2fd7941674b7b7311d92b49b25d2eec8 | SHA-256 |
| --- | --- |
| docs/research/cycle-001.html | 237e73a6dfb99ddfaf4d2d184e8783c87ba0332e77e1fb655dce1a3557facd71 |
| docs/research/cycle-001.pdf | 4c303bc5a9c4cafbbb11b4d84a0fb4ceb8f7b95822fbdf935c6560f658807c01 |

This physical-page key comes from looking at the published page images, independently of text-extraction algorithms. Ordinals refer to the 37 author blocks in the HTML DOM. Subscript/equation authorship and mathematical accessibility are outside the acceptance contract. A passage spanning pages cannot earn a one-page link.

| Ordered HTML blocks | Physical reference pages |
| --- | --- |
| 1–9 | 1 |
| 10–18 | 2 |
| 19 | 2 and 3 (must abstain from a single link) |
| 20–27 | 3 |
| 28–37 | 4 |

Page 5 contains continuation of the bibliography in a list. There are three tables. The paper remains essential for these components. It is a failure to claim whole-publication faithful reflow or accessibility conformance from this test.

## Arms, decision and controls

1. **Candidate** – Execute the offline instrument on the unchanged HTML/PDF. Use a new empty output. Compare receipt order/content to extraction from the original XHTML using a separate XML parser. Check actual rendered-HTML passage text, link targets, unresolved labels, and byte identity of the delivered PDF. Check every linked passage against the independent physical-page key, including the prohibited cross-page claim. Score once on frozen code. Preserve any later correction in a separate observation.
2. **Existing author HTML/PDF** – Count every identical authored block already available and inspect in-document page-specific PDF anchors. Existing tables, list structure, equations and navigation are credited. Native PDF viewer Find/manual navigation is a capable outside option. No timed human user has been recruited.
3. **Conventional automation** – Supply the same author HTML and PDF to an independent MuPDF extractor with normal reading-order sorting. Normalize whitespace and compatibility ligatures, preserving letters, punctuation and digits. For each source block map an exact token sequence to a unique physical page or abstain. Use this complete lightweight comparator to emit a portable clickable concordance preserving author markup. Also execute Poppler's default native text export. Credit real output, elapsed times and the human actions still needed. Neither comparator reads the expected key when constructing its output.
4. **Adverse fixture** – Generate deterministic two-page PDF with unique text on page 1, one sentence repeated on pages 1 and 2, a separate single-page hit on page 2, a known absent sentence with a changed material digit, and one passage split between the pages. Supply these five blocks in deliberately nonphysical order. Require correct unique pages, explicit ambiguity with both pages, explicit absence for the changed digit and abstention for the boundary-spanning block. Unresolved passages have no page anchors. A matched altered digit or wrong unique physical page fails safety.

**Acceptance fixed before execution.** Engineering delivery requires a portable offline reader/receipt and byte-identical PDF. Passage navigation on this paper requires every author block preserved in order, zero incorrect links, at least one correct link on each of pages 1–4, and the split block unlinked. All five adverse rows must meet their registered behavior. Report counts and failures even if an arm fails. No universal target matching rate, general coverage, economic or accessibility certification claim follows. Superiority requires a materially superior measured full outcome under matched conditions; a tie, observed comparator advantage or incomplete comparison does not establish it.

**Resources and obligations.** Record commands, exact input and producer identities, tool versions, process CPU and elapsed time, attempt count and output sizes. Keep scorer and producer effects separate. Included Codex engineering effort/inference, operational labor, distribution, accessibility review, support, market demand and account billing are unmeasured. No paid service, private data or outreach. No parallel human worker or direct frontier-document model run is registered, so the primary AI-versus-human productivity question remains unmeasured. End after these fixed arms and adversarial cases.

**Successor test.** Obtain permission from a reader who routinely uses a screen reader. On fresh papers, blind and randomize citation tasks between original HTML/PDF, the conventional clickable edition and Reading Room, measuring correct cited passages, completion time, abstention burden, assistive-technology usability and paid human work. No enrollment or result implied.
