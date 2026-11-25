# Browser and recovery verification

The browser test uses an isolated eligibility fixture, the distributed website and executor, a native local runtime, and a real browser. The test profile carries public research ambitions. It records the exact Pages revision, module and archive hashes, model readiness, accepted ambition, journal state, provider usage, tool events, file names and portable export digest. Pairing tokens, the private browser link and raw browser session remain local.

## Live production

The [live release receipt](LIVE-RELEASE.json) binds merged source `f8b8f95b1ef10641a82d1b98f4b13e0b8cd5bb43` to the distributed executor 1.1.0 and page code. The public deployment, independent asset checks and post-deploy bilingual browser replays passed. [Public asset verification](LIVE-STATIC-VERIFICATION.json) · [Deployment and workflow receipts](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/runs/45547873631)

- The [English owner case](LIVE-OWNER.json) sent **Build frontier AI LLM for Game Theory.** exactly once after discovering and checking Qwen3-8B. The native mission completed three real model requests, attempted ten actions and retained four files. It exhausted the declared model budget and earned no independently accepted strategic result. Connector restart verified the saved model again and reopened the identical checkpoint and export without resubmission. The independent specialist fit ran separately. [Game Theory research and evaluation](../strategic/README.md)
- The [French mobile case](LIVE-FR.json) completed one model request, constructed and ran a local calculator and verified the result of **106,251 octets** against an independent byte-count reference on both exact downloaded archives. The setup included operator-authored binding instructions after the preview failures. The final arithmetic claim earned case-level verification. Overall mission status remained `needs_review`.

## Candidate and recovery controls

The [candidate owner replay](CANDIDATE-OWNER.json) ran the exact English ambition with Qwen3-8B on Linux. The downloaded launcher opened a one-use guide, the browser discovered the running model on its standard port, and a real schema-constrained readiness request completed. The page sent the original ambition once and reopened the running journal. One model response constructed and ran a table on generated development data. The one-turn lease then ended. This established transport, actual inference, and construction in the declared scope. The result supplied no independently accepted strategic capability.

The [French mobile candidate replay](CANDIDATE-FR-RESTART.json) discovered Qwen3-8B, executed two model requests and reopened the same portable checkpoint after a fresh connector process. The model constructed a calculator but failed to run it against the bound inputs. A second candidate run computed the same number from inline development data. The page withheld the registered numerical claim in both runs.

The [portable restore replay](RESTORE-REPLAY.json) executes the native bridge, journal and isolated SQL worker with authored action responses. The approved numerical manifest matches the exact ambition and language. The restored journal preserves its old files and ancestry and opens in pause. All three claims await fresh execution. The same quantities bind again under the newly approved manifest. A French-only manifest grants no evidence permissions on the English archive. The original proposal never receives fresh authority through the checksum alone.

## Reproduce

Run from the repository root with an existing compatible llama.cpp model already running on `127.0.0.1:8080`. Use Python 3.11 or later, Node.js, Playwright Core `1.62.1`, and an installed Chrome or Chromium executable. Set `FRONTIER_EXPECTED_COMMIT` to the exact `source_commit` you intend to verify. The script refuses archive or site-module bytes that fail that revision’s receipt.

```bash
export FRONTIER_CHROME=/path/to/chrome
export FRONTIER_EXPECTED_COMMIT=THE_EXACT_VERIFIED_SOURCE
site='https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/'
replay=publication/evidence-bound/production/run-evidence-browser.sh
"$replay" "$site" /path/to/private-owner-test en 'Build frontier AI LLM for Game Theory.' start
"$replay" "$site" /path/to/private-owner-test en 'Build frontier AI LLM for Game Theory.' restart
python -B publication/evidence-bound/production/replay_restore.py
```

Use `FRONTIER_EVIDENCE_INPUT` to name an explicitly approved local input manifest. The case preparation tool reads the exact release receipt and both previously downloaded archives, verifies their hashes, constructs the French case’s private manifest and prints its independently calculated byte-count difference. It never downloads models or accesses a private member service.

## Français

La vérification utilise un profil admissible simulé, le site distribué, l’exécuteur local et un vrai navigateur. En production, le parcours anglais a poursuivi l’ambition exacte du propriétaire, exécuté trois appels au modèle et conservé quatre fichiers de mise au point. Le redémarrage a rouvert le même dossier sans nouvel envoi. Le parcours mobile français a construit et exécuté un calculateur. Il a vérifié la différence de **106 251 octets** entre les deux archives publiques téléchargées. Le contrôleur a aussi vérifié la restauration des dossiers et le rattachement des données approuvées. [Vérification en production](LIVE-STATIC-VERIFICATION.json) · [Résultat français](LIVE-FR.json)
