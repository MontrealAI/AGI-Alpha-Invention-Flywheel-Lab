# ALPHA GENESIS FLYWHEEL Ω — publication deployment

**Release 1.1.0 · 4 November 2026**

## What is being deployed

A static research publication: reading page, PDF, editable LaTeX, reproducible source ZIP and evidence links. The website includes a clearly labeled mathematical illustration. It has no account system, live model, backend worker, telemetry, payment workflow or hardware connection.

**This is not a deployable GENESIS Discovery Studio application.** The paper specifies that product; the companion implements exact supplied analytical examples. Publication success must not be represented as operational qualification of the proposed foundry.

## The simplest handoff

Use the supplied `ALPHA_GENESIS_FLYWHEEL_OMEGA_v1.1.0_WEBSITE.zip`. Extract it and open `index.html` locally to inspect the reading experience. Upload the extracted folder contents together to a static host you control. All links are relative, so the site can live under a versioned subfolder without replacing an existing website.

For the existing research repository, a suitable **proposed** destination is `docs/alpha-genesis-flywheel-omega-v1.1.0/`. Integrate through the repository's normal publication review and CI process; do not replace the whole `docs/` folder or overwrite another contributor's work. This package has not changed a repository, DNS record, host configuration or live site.

Keep the complete source archive adjacent to `index.html`; do not upload only the PDF. Preserve the old edition under its own versioned name. Avoid claiming an untested short URL or release identifier as live.

## Rebuild the publication bundle from source

Reading the delivered PDF or website needs no Python. Reproduction needs Python 3.10+ and no third-party Python packages. A paper rebuild additionally needs `pdflatex`, its TeX packages, and Poppler's `pdftotext`.

From the extracted source folder:

```sh
python3 verify.py --full
python3 publish.py --output /absolute/new/genesis-publication
```

Use a new output directory outside the source folder. `publish.py` checks package hashes, local links, exact reproduced artifacts, and tests before creating:

- a versioned PDF and editable LaTeX;
- a flat, self-contained source ZIP;
- `site/`, containing the static publication and source download;
- a website ZIP, plus outer `SHA256SUMS`.

It does not upload anything. The original inspected PDF remains unchanged; rebuild output is isolated in `build/`. If source is intentionally edited, assign a new edition and rebuild its evidence and manifest rather than bypassing the checker.

## Validate the served artifact before switching a public link

Run from the extracted source package, supplying the **site** manifest created above:

```sh
python3 check_published.py \
  --expected /absolute/new/genesis-publication/site/SHA256SUMS \
  --base-url https://YOUR-HOST/YOUR-VERSIONED-PATH/
```

Replace the example URL with the actual destination. This explicit command performs network requests and compares every served file with the trusted local manifest. It fails on a missing or altered file, cross-origin redirect, unsupported URL or unexpectedly large response. It does not trust a replacement manifest downloaded from the host. HTTPS is required except for localhost preview.

This is a delivery-integrity check, not an audit of the host's security, scientific validity or application behavior. An authenticated distribution channel is still important: unsigned checksums do not authenticate an author.

Check the actual deployed page on desktop and mobile, including the paper link, source ZIP, local evidence links, keyboard navigation, counterexample button and reset. Verify MIME types and HTTPS. Some hosts rewrite content or block unfamiliar file extensions; the byte check will identify those differences. Record the final URL and served-file check output in the publication receipt.

## What is qualified locally

The release report records the exact tested Python, TeX and browser environment. The paper is rendered and inspected, and the source rebuild is compared with it. The release handoff also checks source-ZIP extraction and static-site served bytes under a local server. Desktop/mobile layout and arithmetic interactions are tested in an offline injected-document harness using the actual CSS/JavaScript bytes. Managed Chromium blocked direct file and local-HTTP navigation in the test environment, so that complete browser navigation path and the chosen public host still require validation. A local HTTP byte-check success is **not** a completed public-host deployment. No macOS or Windows application-installation result is claimed.

## Rollback

Keep the prior publication and its checksums. If a served-byte check fails, keep the previous public landing link and correct the new version's upload. If an already published paper needs a substantive correction, publish a new numbered edition and a correction note; preserve the old edition rather than silently rewriting its evidence.

## Separate product pilot requirements

A future runtime pilot must identify its exact executable release, permitted inputs/effects, available provider model, evaluator, resource accounting, recovery policy and operator. Exercise the installed browser-to-executor path, isolation, holdout protection, interruption recovery, denial of unauthorized effects, duplicate prevention and rollback. Establish an actual complete campaign and fresh successor comparison.

No passing publication check enables customer-data processing, model spending, unattended agents, physical actuation, collection of payments or claims of commercial profitability. Those require the actual implementation and applicable authority. Ordinary already-authorized computation should not be obstructed by ceremonial approvals, but publication does not create new operating permissions.
