# Reproduce and verify a release

## Source and archive identity

Every archive contains `RELEASE-MANIFEST.json`: product version, exact source commit, product tree, build mode and SHA-256/byte count for every included file. The manifest deliberately excludes its own hash. A separate published archive SHA-256 binds the whole ZIP, including that manifest.

`source-bound` means the packager read product files from an exact Git commit and compared the finished archive with those bytes. `candidate` means the selected working files were used; its base commit is context, not a claim that the files match it. Never promote a working-tree candidate into a source-matched release by renaming it.

Build from a complete source revision:

```bash
python3 products/alpha-genesis-harness/scripts/package_release.py build --source-revision FULL_COMMIT_SHA --output /absolute/release-output
```

The deterministic archive has a fixed ZIP timestamp, sorted paths and stable permissions. Repeating a build with the same source and Python compression implementation should produce identical bytes. Different compression implementations may change ZIP bytes; the contained file hashes remain the source comparison. Python, Git and archive tool versions belong in a qualification receipt.

## Customer verification

The browser core does not require Python. Customers who want a command-line integrity check can use Python 3.10+:

```bash
python3 scripts/package_release.py verify /path/to/download.zip --expected-sha256 PUBLISHED_SHA256 --expected-source-revision FULL_COMMIT_SHA
```

Use an independently trusted release page to obtain both values. Do not take an expected hash from an untrusted email that supplies the archive. SHA-256 verifies bytes; it does not by itself certify the software's safety, claims or authorship.

Maintainers with the repository can additionally pass `--compare-source-revision FULL_COMMIT_SHA`. This compares the selected source tree, full included inventory and every source file. Without it, the verifier reports the archive's source claim separately from an independently established source-byte match.

The verifier rejects duplicate members, missing or unlisted files, path traversal, symlinks, malformed identity, hash/size mismatches, oversized archives and detected private-key material. These checks reduce known packaging errors; they are not a universal secret scanner or malware detector.

## Qualification before promotion

Run the scoped development and independently prepared acceptance tests. Inspect actual browser behavior from a fresh extraction, including demonstration, manual response import, export/reopen, malformed inputs and accessible error recovery. A Linux browser pass does not establish macOS, Windows, Safari or every assistive technology.

Authenticated provider tests need approved access and spending authority. Mock responses must remain labeled. The current mandate forbids obtaining keys or making separately billable calls without separate authorization, so provider protocol tests alone cannot earn a live-integration claim.

The hosted workflow may publish an immutable **prerelease** bound to its source and verify operation from a fresh download. A prerelease and passing tests do not automatically qualify the Official Edition for sale. Consult the acceptance record and commercial checklist. Do not alter evidence after observing results to make a release pass.

The core distribution contains newly authored product source and public demonstration fixtures. It excludes old research source, models, customer projects, private configs and credentials. Keep merchant/customer state outside the repository and archive.

## Native platform evidence

The release workflow receives the identical Linux-built ZIP on standard public Windows and macOS runners. It verifies the external archive digest, starts the shipped `.cmd` or `.command` source launcher and operates the local application in headless native-OS Chromium. The platform receipt identifies the source, archive, host, interpreter and browser. This covers source-launcher execution and rendered browser workflows; Finder/Explorer double-click, code signing, notarization and a clean consumer-machine installation remain separate.

A release requires both native jobs to succeed. Their source-specific receipts, screenshots and actual downloaded exports are checked before publication and bundled in a separate `HARNESS_NATIVE_EVIDENCE_<source>.zip` with its own checksum. The workflow rejects missing or failed receipts, mismatched OS/source/archive identities, absent screenshots and export hash mismatches. This evidence supplement is distinct from the installable product archive. The accompanying `RELEASE-QUALIFICATION.json` and `.md` reconcile the frozen matrix with actual extracted, Linux browser, native platform and source-observation receipts. They identify each input by filename and SHA-256, retain failed and blocked criteria, and explicitly leave the full commercial mandate unsatisfied. They are generated after testing and do not change the customer ZIP.

Credential-free hosted probes record actual Codex sandbox/interpreter operation and authorized official-source monitoring separately. A blocked probe stays **BLOCKED**, and a successful probe does not establish authenticated model construction, autonomous improvement or reproduced frontier capabilities.

## Version retention

Keep the exact archive, public digest and release receipt for each sold version. Replacing the file behind a storefront listing can affect old customers' download links. Give later versions their own explicit identities, preserve the purchased-version entitlement and test delivery again. Do not silently promise future editions.

## Operate the exact archive with UI integration checks

The qualifier extracts the verified immutable ZIP into a fresh temporary directory and runs its JavaScript acceptance tests, every Python component test, launcher help, the Linux source-launcher entry point where available, workflow construction, the Ω GENESIS NEXT experiment and a separately frozen fresh-instance successor comparison. The workflow demonstration has authored model responses; it is not live inference. The Ω experiment constructs an authored bounded source modification and measures actual checker operations. Neither demonstration establishes autonomous scientific discovery.

For the complete DOM/HTTP integration gate, install the development-only dependency from the committed `tests/dom/package-lock.json` using `npm ci --ignore-scripts --no-audit --no-fund` in that directory. Pass its absolute `node_modules` directory explicitly:

```sh
python3 scripts/qualify_archive.py /absolute/release.zip \
  --expected-sha256 PUBLISHED_SHA256 \
  --expected-source-revision FULL_COMMIT_SHA \
  --output /absolute/new-qualification \
  --dom-modules /absolute/development-node_modules
```

The qualifier checks the installed jsdom version against the packaged requirement and runs all six UI replays against the extracted application. The HTTP replay starts the actual connector and workflow engine with authored model fixtures. Credentials are not inherited. Omitting `--dom-modules` leaves this UI criterion explicitly **NOT TESTED**. DOM emulation does not replace actual rendered-browser, assistive-technology or cross-OS testing.

### Français

Le qualificateur vérifie le ZIP exact, l’extrait dans un dossier neuf et exécute ses tests, son lanceur et la démonstration de construction. L’option `--dom-modules` ajoute les six scénarios d’interface sur les octets extraits, avec la version jsdom déclarée. Le scénario HTTP utilise le vrai connecteur et le moteur, mais des réponses de modèles préparées. Sans cette option, le critère d’interface reste explicitement non testé. Ces contrôles ne remplacent pas les essais graphiques et multiplateformes.
