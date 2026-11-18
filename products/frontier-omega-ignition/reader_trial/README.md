# RR-H1 · Reader performance

MONTREAL.AI can run a consented, blinded study on fresh research publications using this offline kit. The [registration](REGISTRATION.md) fixes four reading workflows and eight tasks. The [operator-only key](REGISTERED.json) contains the rubrics. Keep that key, the repository checkout and the private roster away from participants until collection is complete. The publication itself is public; meaningful participation requires readers who have not seen these materials or the key.

**Current status.** No participants were enrolled. No assistive-technology user was observed. Reading speed, task success, willingness to pay and cost per accepted reader outcome are unmeasured. The [automated receipt](QUALIFICATION.json) records the actual packet builds and independent reference-page checks. All eight packets successfully reproduce the two unchanged source pairs. Conventional indexing and multi-term search cover all 21 English and 29 French pages. The existing passage instrument supplies unique links for 1 of 30 English and 9 of 72 French guide blocks. In these cases the publisher HTML introduces the paper; the full text is in the PDF. These link counts do not measure accuracy or reading benefit.

## Reproduce the technical qualification

From the product directory, use Python 3.11 or newer, Poppler and PyMuPDF. The private enrollment and packet collection components need no online service or credentials. PyMuPDF is needed only for independent technical qualification. The original inclusion and task-page references were [frozen before scoring](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/3f6ab5cad5606c2ebfce64ced680ee5d92e12945).

```sh
python3 -B reader_trial/qualify.py --output /tmp/rr-h1-packets-new
python3 -B -m unittest discover -s reader_trial -v
node reader_trial/browser.cjs /tmp/rr-h1-packets-new
```

Open e.g. `en-D/START.html` or `fr-B/START.html` inside the output directory. These qualification packets have technical IDs and cannot be submitted as participant responses. The browser check uses the same Playwright Core and Chromium as IGNITION’s public qualification. It checks keyboard initiation, a real file download, language, no offline HTTP requests, all eight arm handoffs and query/abstention behavior in both languages. It uses ordinary browser automation. It does not simulate a person using a screen reader. Build times and duplicate packet size are measured machine resources. No observed person took those times. The first independent reference lookup failed on the line-wrap division of “com- / plete” in the English paper. The receiver now recognizes alphabetic line-end hyphenation when checking the reference; no page, answer or expected value changed.

### Scientific navigation and source version checks

The [RR-N1 registration](NAVIGATION_REGISTRATION.md) freezes 15 search vectors, two genuine source controls and four single-byte substitutions. The [full result](NAVIGATION_RESULT.json) preserves every first and repaired hit set. The first search returned the same pages for opposing signs, percent and bare values, and opposite inequality directions. It passed 2 of 15 cases. The current generated packet passed all 15 after preserving scientific literals and supporting quoted, ordered terms. For example, use `"x <= 5"` or `« x ≤ 5 »` to require the operator and term order. Plain terms can occur anywhere on the same page. Always check the original page for table layout and mathematical meaning. Both genuine source pairs built; all four substitutions were refused before packet creation.

`test_navigation.py` creates a four-page control PDF, runs it through the actual packet builder and drives the delivered inline script in Node with a minimal DOM. The offline Chromium run in this workspace stopped before opening a page because the native process could not create a socket. The separate browser command above runs on a host with Chromium socket access. It checks real keyboard and download behavior. The publication packets carry the original guide and PDF; links in the original guides to other publications, source bundles and the wider publisher site are outside the offline packet.

## Run an authorized study privately

For every invocation use the same operator-owned `--private` directory. Only the coordinator controls its roster, enrollment assignment seed, respondent material, costs and access barriers. Store the signed approval and consent externally; the tool checks attestations and retains their hashes, not the identity or authority of the signer. Never publish participant inputs or the unredacted analysis. Use one person once across both languages. A reader can use their usual screen reader, magnification, keyboard or other assistive tools.

1. Obtain the actual approval for recruitment and human data collection and the relevant accessible, voluntary consent from every participant. Explain the tasks, saved data, intended users, compensation if any, withdrawal and retention, and who to contact. Before recruitment freeze the costing window and shared-cost allocation policy. Provide the coordinator with an authorization JSON containing `study` = `RR-H1`, `human_collection_authorized` = true, a real `authority_reference`, and `accounting` = `{"currency":"CAD","allocation_rule":"…","measurement_window":"…"}`. Replace the ellipses with the actual plan before use.
2. Record a consent JSON with `study`, pseudonymous `subject`, `lang` = `en` or `fr`, `stratum` = `ordinary` or `screen_reader` and a private opaque `consent_reference`. Confirm `consented`, `fluent`, `reads_research`, `paper_and_key_unseen`, `unique_person` and `retention_terms_explained` as true only after the actual checks. The screen-reader stratum is for regular screen-reader users. The coordinator retains the identity crosswalk separately. Never impute a participant or an answer.
3. Assign and generate the session. The opaque assignment is generated after consent in blocks of four within each stratum. Only the participant packet leaves private coordinator storage.

```sh
python3 -B reader_trial/trial.py --private /private/rr-h1 init --authorization /private/authority.json
python3 -B reader_trial/trial.py --private /private/rr-h1 enroll --consent /private/consent.json
python3 -B reader_trial/trial.py --private /private/rr-h1 packet --subject READER-CODE --output /private/issued-packet
python3 -B reader_trial/trial.py --private /private/rr-h1 receive /private/returned-responses.json
```

Open `START.html` on a private participant machine. Use a neutral practice example to explain physical PDF pages and confirm their assistive setup works before the first real question. The form presents one question at a time, starts the timer when the reader requests it and stops only at submission. The publication opens in a separate tab. Breaks or assistance are noted. Responses remain in that browser locally until transfer by the agreed private channel. A reader can explicitly mark a question unresolved/abandoned and download after any completed task. Reimport permits a longer response containing the identical initial prefix. A withdrawal erases responses in the coordinator roster and prevents reimport. Use the consented retention policy for consent records, previously transferred files, downloaded answers and browser storage.

```sh
python3 -B reader_trial/trial.py --private /private/rr-h1 withdraw --subject READER-CODE
```

4. After completing the fixed endpoint or documenting a stopped/partial study, export the blind packet. Give it independently to two different readers of the original PDFs. Each adjudicator returns one JSON object with `reviewer` = a unique code, `decisions` = a list of `{"id":"opaque blind ID","grade":"accepted","basis":"source-grounded rationale"}`. Allowed grades are `accepted`, `ordinary_error`, `consequential_error` and `unresolved`. Reviewers must verify the full meaning and quotation, the physical page and units. The operator may not substitute a grade from a keyword match. Another actually supporting page can be accepted with an explicit check. A third independent reviewer resolves only the disagreements. None sees assignments/timings; raw free text should be screened by the coordinator for inadvertent disclosures without altering the answer. Do not claim an independent review occurred merely because two different strings were entered.

```sh
python3 -B reader_trial/trial.py --private /private/rr-h1 blind --output /private/blind.json
python3 -B reader_trial/trial.py --private /private/rr-h1 analyze --a /private/grade1.json \
  --b /private/grade2.json --costs /private/costs.json --output /private/analysis.json
```

Add `--tie /private/grade3.json` when needed. Cost input is optional; absent values remain unknown. Format it as `{"currency":"CAD","groups":{"en.ordinary.B":{…}}}`. Each supplied group must include exactly `development_and_failed_attempts`, `maintenance`, `materials_and_preparation`, `study_administration`, `reader_and_assistance`, `independent_review`, `support_and_delivery`, and `compute_and_software`, each in integer millionths of the registered currency, or null if missing. Keep underlying times, rates and allocation evidence privately. Actual technology, barriers and interruptions are returned privately for review. Read the stratum-specific comparisons, coverage, cost, attrition and recruitment limits alongside any larger-study eligibility verdict. The final response export cannot measure how long a reader spent on a task they left open without ever submitting; such durations remain missing.
