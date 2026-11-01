# Read the papers in your browser

The [original Foundry v2 PDF](autonomous-enterprises-foundry-v2.pdf) is always available in this public repository. GitHub can preview it; use its download control if your browser does not show the preview. This link does not depend on GitHub Pages, an Actions artifact, or an expiring attachment.

The website adds a simple research shelf, dedicated reading pages for all three papers, and visible open/download fallbacks. PDFs remain unchanged. No login, third-party viewer, tracking, API key, paid service, or local setup is needed to read the published site.

## One-time owner setup

1. Open this repository’s [Settings → Pages](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/settings/pages).
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Do **not** add a suggested template: this repository already supplies `.github/workflows/research-pages.yml`.
4. After that workflow is on `main`, open [Actions → Research papers website](https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/actions/workflows/research-pages.yml), choose **Run workflow**, keep branch **main**, and select **Run workflow**. Future changes to the website or papers deploy automatically after they reach `main`.
5. Wait for both **build** and **deploy** to turn green. Open the **github-pages** deployment link shown by GitHub. If an environment approval is required, an authorized owner must approve that deployment; do not remove protections to make it pass.

You need repository settings permission for step 2. If it is not available, ask the repository owner. If deployment ran before Pages was enabled, complete step 2 and rerun the failed workflow. This workflow checks existing Pages configuration; it does not enable Pages or alter repository access settings.

## Addresses after successful deployment

- Research shelf: <https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/>
- Foundry v2 reading page: <https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/foundry-v2.html>
- Direct PDF: <https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/autonomous-enterprises-foundry-v2.pdf>

These are the default project-site addresses, **not a statement that deployment is already live**. Settings → Pages and the successful deployment output are authoritative, especially if the owner configures a custom domain. Bookmark the reading page for sharing; the PDF is also kept at its descriptive versioned repository path. GitHub paths on `main` are stable locations, not immutable content identifiers: use a commit permalink plus the [SHA-256 manifest](publication-manifest.json) when citing exact bytes.

On a phone, tap **Open the full paper** for the native PDF reader. If inline preview is unsupported or blank, **Download PDF** remains available above and beside the preview. The original PDF is not tagged for accessibility; the HTML summary and navigation are accessible alternatives, not a claim of full PDF accessibility remediation.

## Retroactive Sensor Lab

The proposed fifth allowlisted HTML page is **[Retroactive Sensor Lab](sensor-lab.html)**, with its local-only **[sensor constructor module](sensor-engine.mjs)**. This optional user-interactive demonstration operates entirely on pasted CSV or its clearly labeled synthetic sample. It makes no network calls and never publishes or uploads the user-provided archive. Its output includes source-row references, SHA-256 fingerprints of the input bytes and explicit unknown intervals. It is not a certified physical or scientific measurement. Run \`node --test tests/test_sensor_engine.mjs\` plus the existing site tests before publication.

The published site must continue to copy **only explicitly named public HTML, PDF and module files**. The original manuscripts and all unpublished accounts or archives remain outside the boundary.

## What is published

The build copies **only** the five named HTML pages, the three named public PDFs, the single local sensor-engine module, a checksum manifest, and `.nojekyll`. It does not export the repository, accounts, experiment outputs, credentials, or local workspace. Pull requests validate and build only; deployment is restricted to `main`, with Pages/OIDC permissions limited to the deployment job. Existing manuscript paths and release `PAPER.pdf` files are untouched.

Local check (Python standard library only):

```sh
python3 -m unittest discover -s tests -p 'test_research_site.py' -v
python3 scripts/build_research_site.py --output /tmp/research-site-NEW
python3 -m http.server 8000 --directory /tmp/research-site-NEW
```

Use a new output directory for each build. Open `http://localhost:8000/` to preview; do not serve the whole repository or private workspace.

Official guidance: [custom GitHub Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
