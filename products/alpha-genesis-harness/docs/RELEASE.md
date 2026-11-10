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

## Version retention

Keep the exact archive, public digest and release receipt for each sold version. Replacing the file behind a storefront listing can affect old customers' download links. Give later versions their own explicit identities, preserve the purchased-version entitlement and test delivery again. Do not silently promise future editions.

## Operate the exact archive with UI integration checks

The qualifier extracts the verified immutable ZIP into a fresh temporary directory and runs its JavaScript acceptance tests, every Python component test, launcher help and workflow construction demonstration. The demonstration has authored model responses; it is not live inference.

For the complete DOM/HTTP integration gate, install the development-only dependency from the committed `tests/dom/package-lock.json` using `npm ci --ignore-scripts --no-audit --no-fund` in that directory. Pass its absolute `node_modules` directory explicitly:

```sh
python3 scripts/qualify_archive.py /absolute/release.zip \
  --expected-sha256 PUBLISHED_SHA256 \
  --expected-source-revision FULL_COMMIT_SHA \
  --output /absolute/new-qualification \
  --dom-modules /absolute/development-node_modules
```

The qualifier checks the installed jsdom version against the packaged requirement and runs all five UI replays against the extracted application. The HTTP replay starts the actual connector and workflow engine with authored model fixtures. Credentials are not inherited. Omitting `--dom-modules` leaves this UI criterion explicitly **NOT TESTED**. DOM emulation does not replace actual rendered-browser, assistive-technology or cross-OS testing.

## Read the actual platform reports

The hosted release workflow can run `scripts/qualify_platform.py` on actual macOS and Windows hosts against the **same** source-bound archive. Published `PLATFORM-Darwin-VERIFICATION.json` and `PLATFORM-Windows-VERIFICATION.json` identify the source commit, whole-archive SHA-256, host and operation outcomes. The corresponding screenshots use `Darwin-HARNESS-` and `Windows-HARNESS-` prefixes.

Check that those identities match the downloaded customer archive and read the recorded status. These reports cover the JavaScript engine tests, native launcher help, Python loopback startup and headless browser first use on the named host. They exclude the complete cross-platform Python/security suite, live authenticated model calls, signed installers and Finder/Explorer double-click. A configured CI job is not a passing result; missing or failed reports leave that scope unverified. Repeated JavaScript tests are **per-platform executions**, not additional unique tests.

### Français

Le qualificateur vérifie le ZIP exact, l’extrait dans un dossier neuf et exécute ses tests, son lanceur et la démonstration de construction. L’option `--dom-modules` ajoute les cinq scénarios d’interface sur les octets extraits, avec la version jsdom déclarée. Le scénario HTTP utilise le vrai connecteur et le moteur, mais des réponses de modèles préparées. Sans cette option, le critère d’interface reste explicitement non testé. Ces contrôles ne remplacent pas les essais graphiques et multiplateformes.

Les rapports `PLATFORM-Darwin-VERIFICATION.json` et `PLATFORM-Windows-VERIFICATION.json`, lorsqu'ils sont publiés, documentent l'exécution du même ZIP sur des hôtes macOS et Windows réels. Vérifiez la source, l'empreinte, l'hôte et le résultat. Le périmètre couvre JavaScript, l'aide du lanceur natif, le démarrage Python local et le premier parcours dans un navigateur sans fenêtre; il exclut la suite Python/sécurité complète, les modèles authentifiés, les installateurs signés et le double-clic Finder/Explorer. Les captures portent le préfixe du système. Une tâche CI prévue ne prouve pas sa réussite. Les tests répétés sur plusieurs systèmes sont comptés par plateforme, sans addition en tant que tests uniques.
