/* SPDX-License-Identifier: Apache-2.0 */
// Graphical host-OS browser verification. No external models, authentication or user files.
const { chromium } = require('playwright-core');
const fs = require('node:fs');
const path = require('node:path');
const { spawn, execFileSync } = require('node:child_process');
const assert = require('node:assert/strict');
const os = require('node:os');
const { pathToFileURL } = require('node:url');

function findBrowser() {
  if (process.env.CHROME_BIN) {
    fs.accessSync(process.env.CHROME_BIN, fs.constants.X_OK);
    return process.env.CHROME_BIN;
  }
  for (const name of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']) {
    try { return execFileSync('which', [name], { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim(); }
    catch (_) { /* Try the next installed browser name. */ }
  }
  throw Error('Install Chrome/Chromium or set CHROME_BIN to its executable.');
}
const crypto = require('node:crypto');

(async () => {
  const product = path.resolve(__dirname, '..');
  const output = path.resolve(process.env.HARNESS_SCREENSHOT_DIR || path.join(os.tmpdir(), 'harness-visual'));
  fs.mkdirSync(output, { recursive: true });
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-visual-work-'));
  const external = process.env.HARNESS_BASE_URL;
  if (external) {
    const base = new URL(external);
    assert.ok(base.protocol === 'http:' && base.hostname === '127.0.0.1' && !base.username && !base.password && base.pathname === '/' && !base.search && !base.hash, 'Browser qualification accepts only the exact loopback application');
  }
  const server = external ? null : spawn(process.env.PYTHON || 'python3', ['-u', path.join(product, 'launch.py'), '--port', '0', '--no-browser', '--workspace', path.join(temporary, 'work')], { stdio: ['ignore', 'pipe', 'pipe'] });
  let browser, page, origin, serverError, serverStderr = '';
  server?.on('error', error => { serverError = error; });
  server?.stderr.on('data', chunk => { serverStderr = (serverStderr + chunk.toString()).slice(-16000); });
  const ready = server ? new Promise((resolve, reject) => {
    let stdout = '';
    const finish = (error, address) => {
      clearTimeout(timer);
      server.stdout.off('data', onData);
      server.off('error', onError);
      server.off('exit', onExit);
      if (error) reject(error); else resolve(address);
    };
    const onData = chunk => {
      stdout = (stdout + chunk.toString()).slice(-16000);
      const match = stdout.match(/^ALPHA GENESIS HARNESS: (http:\/\/127\.0\.0\.1:\d+)\r?$/m);
      if (match) finish(null, match[1]);
    };
    const onError = error => finish(error);
    const onExit = (code, signal) => finish(Error(`Connector exited before readiness (${code ?? signal}): ${serverStderr}`));
    const timer = setTimeout(() => finish(Error('Connector did not announce readiness: ' + serverStderr)), 10000);
    server.stdout.on('data', onData);
    server.once('error', onError);
    server.once('exit', onExit);
  }) : Promise.resolve(new URL(external).origin);
  const errors = [], checks = [], screenshots = [], exports = [];
  try {
    // The child announces its own ephemeral port. A stale listener cannot be
    // mistaken for the source under test merely because a fixed port is open.
    origin = await ready;
    checks.push(external ? 'native source launcher supplied the verified loopback origin' : 'spawned connector announced its own loopback origin');
    const executablePath = findBrowser();
    browser = await chromium.launch({ executablePath, headless: true, args: process.platform === 'linux' ? ['--no-sandbox'] : [] });
    page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', error => errors.push(error.message));
    const response = await page.goto(origin);
    assert.equal(response.status(), 200);
    const shot = async name => { await page.screenshot({ path: path.join(output, name), fullPage: true }); screenshots.push(name); };
    await page.locator('#start-mission').waitFor();
    await page.keyboard.press('Tab');
    assert.equal(await page.locator('.skip-link').evaluate(element => element === document.activeElement), true);
    await page.keyboard.press('Enter');
    assert.equal(new URL(page.url()).hash, '#main');
    checks.push('keyboard skip link reaches workspace');
    await shot('HARNESS-01-start-en.png');
    checks.push('first-run rendered');
    await page.locator('#start-genesis-next').click();
    await page.waitForFunction(() => document.querySelector('#omega-capabilities')?.textContent?.includes('bounded-verification'));
    assert.equal(await page.locator('#omega-run').isEnabled(), false);
    await shot('HARNESS-07-genesis-next-en.png');
    await page.locator('#foundry-refresh').click();
    await page.waitForFunction(() => document.querySelector('#foundry-status')?.textContent?.includes('Isolated research selection'));
    assert.equal(await page.locator('#foundry-construct').isEnabled(), false);
    checks.push('model-driven source foundry visible; no unregistered or unconsented construction');

    await page.locator('#omega-discover').click();
    await page.waitForFunction(() => document.querySelector('#omega-candidates')?.textContent?.includes('dependency'));
    await page.locator('#omega-authorize').check();
    const omegaResponse = page.waitForResponse(response => response.url().endsWith('/api/genesis-next/demo'));
    await page.locator('#omega-run').click();
    const omegaResult = await (await omegaResponse).json();
    assert.equal(omegaResult.experiment.qualification.correctness, 'PASS');
    assert.equal(omegaResult.experiment.qualification.production_promotion, false);
    assert.equal(omegaResult.experiment.successor.verdict, 'TIE_WITH_STRONG_ORDINARY_REUSE');
    await page.waitForFunction(() => document.querySelector('#omega-results')?.textContent?.includes('NO_SUPERIORITY_ESTABLISHED'));
    assert.equal(await page.locator('#omega-run').isEnabled(), false);
    await shot('HARNESS-08-genesis-next-result-en.png');
    const omegaDownload = page.waitForEvent('download');
    await page.locator('#omega-export').click();
    const omegaExport = await omegaDownload;
    const omegaExportPath = path.join(output, 'GENESIS-NEXT-browser-export.json');
    await omegaExport.saveAs(omegaExportPath);
    const omegaExportBytes = fs.readFileSync(omegaExportPath);
    assert.ok(JSON.parse(omegaExportBytes).experiments.some(item => item.id === omegaResult.experiment.id), 'Downloaded evidence must contain the actual completed experiment');
    exports.push({ file: path.basename(omegaExportPath), sha256: crypto.createHash('sha256').update(omegaExportBytes).digest('hex'), bytes: omegaExportBytes.length });
    checks.push('actual browser evidence download contains the completed local self-upgrade experiment');
    checks.push('actual local self-upgrade HTTP experiment; consent, independent checks, conventional tie and unknown complete costs');
    await page.locator('[data-view="economy"]').click();
    await page.locator('#proof-example').click();
    await page.locator('#proof-assess').click();
    await page.waitForFunction(() => document.querySelector('#proof-result')?.textContent?.includes('NOT_ESTABLISHED'));
    assert.match(await page.locator('#proof-result').textContent(), /Complete costs remain unknown/);
    checks.push('actual proof-to-market HTTP assessment keeps hypothetical funding and commercial stages distinct');

    await page.locator('[data-view="intelligence"]').click();
    assert.equal(await page.locator('[data-access]').count(), 4);
    await page.locator('[data-access="chatgpt"]').click();
    const planStatusResponse = page.waitForResponse(response => response.url().endsWith('/api/chatgpt/status') && response.status() === 200);
    await page.locator('#chatgpt-refresh').click();
    const planStatus = await (await planStatusResponse).json();
    assert.equal(planStatus.enabled, false);
    await page.waitForFunction(reason => document.querySelector('#chatgpt-status')?.textContent?.includes(reason), planStatus.reason);
    assert.equal(await page.locator('#chatgpt-connect').isEnabled(), false);
    await shot('HARNESS-02-intelligence-en.png');
    checks.push('unauthorized plan connection remains disabled');
    await page.locator('[data-view="start"]').click();
    await page.locator('#load-demo').click();
    await page.locator('[data-view="experiment"]').click();
    await page.locator('#run-experiment').click();
    await page.waitForFunction(() => !document.querySelector('#run-experiment').disabled && document.querySelector('#experiment-result')?.textContent?.includes('PASSED IN SCOPE'));
    assert.equal(await page.locator('#experiment-result .metric-value').first().textContent(), '42500');
    assert.match(await page.locator('#experiment-result').textContent(), /Planted cost omission detected/);
    await shot('HARNESS-03-construction-en.png');
    checks.push('synthetic instrument executed in real browser');
    await page.locator('#codex-panel > summary').click();
    const codexStatusResponse = page.waitForResponse(response => response.url().endsWith('/api/codex/status') && response.status() === 200);
    await page.locator('#codex-refresh').click();
    const codexStatus = await (await codexStatusResponse).json();
    assert.equal(codexStatus.enabled, false);
    await page.waitForFunction(reason => document.querySelector('#codex-status')?.textContent?.includes(reason), codexStatus.reason);
    assert.equal(await page.locator('#codex-run').isEnabled(), false);
    await page.locator('#codex-panel').screenshot({ path: path.join(output, 'HARNESS-07-codex-en.png') });
    screenshots.push('HARNESS-07-codex-en.png');
    checks.push('separate Codex engineering path displays actual disabled authorization status');
    await page.locator('#codex-panel > summary').click();
    await page.locator('[data-view="verification"]').click();
    assert.match(await page.locator('#verification-list').textContent(), /PASSED IN SCOPE/);
    await shot('HARNESS-04-verification-en.png');
    await page.locator('#save-project').click();
    const projectName = await page.locator('#project-name').textContent();
    const downloaded = page.waitForEvent('download');
    await page.locator('#export-project').click();
    const exported = path.join(temporary, 'portable-project.harness.json');
    await (await downloaded).saveAs(exported);
    assert.ok(fs.statSync(exported).size > 100);
    await page.reload();
    assert.equal(await page.locator('#project-name').textContent(), projectName);
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    assert.notEqual(await page.locator('#project-name').textContent(), projectName);
    await page.locator('#project-file').setInputFiles(exported);
    await page.waitForFunction(name => document.querySelector('#project-name').textContent === name, projectName);
    checks.push('saved project survives reload; downloaded JSON reopens in fresh browser storage');
    await page.locator('#language-toggle').click();
    assert.equal(await page.locator('html').getAttribute('lang'), 'fr');
    await page.locator('[data-view="start"]').click();
    await shot('HARNESS-05-start-fr.png');
    checks.push('French interface rendered');
    await page.setViewportSize({ width: 390, height: 844 });
    await shot('HARNESS-06-mobile-fr.png');
    const widths = await page.evaluate(() => ({ viewport: innerWidth, content: document.documentElement.scrollWidth }));
    assert.ok(widths.content <= widths.viewport + 2, JSON.stringify(widths));
    checks.push('390px responsive layout without page overflow');
    await page.locator('[data-view="genesis-next"]').click();
    await page.locator('#omega-refresh').click();
    await page.waitForFunction(() => document.querySelector('#omega-results')?.textContent?.includes('NO_SUPERIORITY_ESTABLISHED'));
    await shot('HARNESS-09-genesis-next-mobile-fr.png');
    const omegaWidths = await page.evaluate(() => ({ viewport: innerWidth, content: document.documentElement.scrollWidth }));
    assert.ok(omegaWidths.content <= omegaWidths.viewport + 2, JSON.stringify(omegaWidths));
    assert.match(await page.locator('#omega-title').textContent(), /Inventez/);
    checks.push('GENESIS NEXT French mobile results without page overflow');
    await page.locator('[data-view="frontier"]').click();
    await page.waitForFunction(() => document.querySelector('#frontier-monitor-status')?.textContent?.length > 0);
    assert.equal(await page.locator('#frontier-monitor-add').isEnabled(), false);
    await shot('HARNESS-10-frontier-mobile-fr.png');
    const frontierWidths = await page.evaluate(() => ({ viewport: innerWidth, content: document.documentElement.scrollWidth }));
    assert.ok(frontierWidths.content <= frontierWidths.viewport + 2, JSON.stringify(frontierWidths));
    checks.push('Frontier Observatory French mobile view; no consent means no monitor creation');


    const offlineContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    try {
      const offline = await offlineContext.newPage();
      const networkRequests = [];
      offline.on('pageerror', error => errors.push(error.message));
      offline.on('request', request => { if (/^https?:/.test(request.url())) networkRequests.push(request.url()); });
      await offline.goto(pathToFileURL(path.join(product, 'START-HERE.html')).href);
      await offline.locator('a[href="app/index.html"]').click();
      await offline.locator('#load-demo').click();
      await offline.locator('[data-view="experiment"]').click();
      await offline.locator('#run-experiment').click();
      await offline.waitForFunction(() => !document.querySelector('#run-experiment').disabled && document.querySelector('#experiment-result')?.textContent?.includes('PASSED IN SCOPE'));
      assert.equal(await offline.locator('#experiment-result .metric-value').first().textContent(), '42500');
      assert.deepEqual(networkRequests, []);
      checks.push('START-HERE opens local files; offline experiment completes without any HTTP requests');
    } finally { await offlineContext.close(); }
    assert.deepEqual(errors, []);
    if (server) {
      assert.equal(serverError, undefined);
      assert.equal(server.exitCode, null);
      assert.equal(server.signalCode, null);
    }
    fs.writeFileSync(path.join(output, 'BROWSER-VERIFICATION.json'), JSON.stringify({ status: 'PASS', source_revision: process.env.EXPECTED_SOURCE || null, origin, browser: await browser.version(), platform: process.platform, architecture: process.arch, headless: true, server_mode: external ? 'external-native-launcher' : 'spawned-source-launcher', checks, screenshots, exports, errors, scope: 'Headless graphical checks on the recorded host OS, including runnable source launcher and offline files. No live model, signed installer, Finder/Explorer double-click or other OS qualification.' }, null, 2));
    console.log(JSON.stringify({ status: 'PASS', platform: process.platform, checks, screenshots, exports }));
  } catch (error) {
    if (page && !page.isClosed()) {
      try { await page.screenshot({ path: path.join(output, 'HARNESS-FAILURE.png'), fullPage: true }); screenshots.push('HARNESS-FAILURE.png'); }
      catch (_) { /* Preserve the original failure even if rendering stopped. */ }
    }
    fs.writeFileSync(path.join(output, 'BROWSER-VERIFICATION.json'), JSON.stringify({ status: 'FAIL', source_revision: process.env.EXPECTED_SOURCE || null, origin, platform: process.platform, architecture: process.arch, headless: true, server_mode: external ? 'external-native-launcher' : 'spawned-source-launcher', checks, screenshots, exports, errors, server_stderr: serverStderr, failure: error.message }, null, 2));
    throw error;
  } finally {
    try { if (browser) await browser.close(); }
    finally {
      if (server?.pid && server.exitCode === null && server.signalCode === null) {
        await new Promise(resolve => {
          const timer = setTimeout(() => server.kill('SIGKILL'), 3000);
          server.once('exit', () => { clearTimeout(timer); resolve(); });
          server.kill('SIGTERM');
        });
      }
      fs.rmSync(temporary, { recursive: true, force: true });
    }
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
