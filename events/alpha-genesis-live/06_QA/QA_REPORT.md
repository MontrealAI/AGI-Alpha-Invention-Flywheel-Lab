# ALPHA GENESIS FLYWHEEL Ω — LIVE · Release QA

**Inspected on November 16, 2026.** Event teaching package v1, evidence mode explicitly labeled.

## Executed and passed

| Acceptance surface | Actual observation |
|---|---|
| Deterministic agent, read-only tool broker, verifier and scenario-engine tests | **40/40 Node tests passed**, 0 failed (see `node_test.log`) |
| Multi-step agent rehearsal, policy verification and construction | Full scripted run produced source-bound dossier, verified baseline and standalone studio |
| Audience time, cost, confidence variants | Each ran from source case with separate `CHECKS_PASS` and 28 recorded tool events (including final submission) |
| Studio browser exercise | Three alternatives selectable, conditional combined 8/8 for human review, fresh totals check, evidence export, four source identities, mobile viewport, no reported JavaScript errors |
| Independent evidence lab | Wrong-claim rejection, reference acceptance, changed CSV comparison and evidence download tested in browser |
| Sales landing preview | Desktop/mobile render, FAQ sections and links checked, no reported browser errors |
| Editable and printable instructional materials | 18-slide PowerPoint and PDF; 8-page Word workbook and PDF; rendered pages visually inspected |
| Integrity and distribution | Complete archive hash supplied outside the archive; file inventory retained in ZIP |

## Live-stage qualification required on the event operator's computer

The **offline included instrument is a SCRIPTED PREVIEW**, not an authenticated model inference receipt. To advertise a fresh live Codex-backed demonstration as tested, the organizer must complete `codex login` using their own eligible ChatGPT account and run `node 00_STAGE/run_show.mjs --mode codex-pro --focus confidence` successfully. Retain its source-bound receipt, verify the generated HTML on the presentation computer, and qualify Zoom/checkout. The Codex CLI can use official ChatGPT sign-in, but login and actual model-backed behavior were not executed in this container. No browser cookie or ChatGPT account token is bundled.

Official HARNESS is separately published in the MONTREAL.AI repository and is **not bundled, automatically interconnected or certified by this event companion**. The package provides a documented, transparent manual handoff via `HARNESS_HANDOFF.md`. The hypothetical improvements in the scenario desk are not actual vendor concessions, purchases, measured revenue, or operational authorization.

## Reproduce source-bound checks

```sh
node --test engine/tests/*.test.mjs lab/test/*.test.mjs 06_QA/stage_engine.test.mjs
node 00_STAGE/run_show.mjs --mode preview --focus confidence
node engine/verify_receipt.mjs 00_STAGE/output/agent-receipt.json
python 06_QA/test_stage_browser.py   # requires Playwright+Chromium
python 06_QA/test_landing_browser.py # requires Playwright+Chromium
```

Do not change `mode` fields or present the included sample preview as a live agent run. The official model-backed mode will generate a new receipt after the account owner authorizes the sign-in. A later generated receipt must be validated on its own actual source bytes.
