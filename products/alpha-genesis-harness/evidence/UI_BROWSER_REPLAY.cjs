/* SPDX-License-Identifier: Apache-2.0 */
// Graphical Linux browser verification. No external models, authentication or user files.
const { chromium } = require('playwright-core');
const fs = require('node:fs');
const path = require('node:path');
const { spawn, execFileSync } = require('node:child_process');
const assert = require('node:assert/strict');
const os = require('node:os');

(async () => {
  const product = path.resolve(__dirname, '..');
  const output = path.resolve(process.env.HARNESS_SCREENSHOT_DIR || path.join(os.tmpdir(), 'harness-visual'));
  fs.mkdirSync(output, { recursive: true });
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'harness-visual-work-'));
  const server = spawn(process.env.PYTHON || 'python3', [path.join(product, 'bridge/server.py'), '--port', '18765', '--no-browser', '--workspace', path.join(temporary, 'work')], { stdio: 'ignore' });
  let browser;
  const errors = [], checks = [], screenshots = [];
  try {
    const executablePath = process.env.CHROME_BIN || execFileSync('which', ['google-chrome']).toString().trim();
    browser = await chromium.launch({ executablePath, headless: true, args: ['--no-sandbox'] });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', error => errors.push(error.message));
    for (let i = 0; ; i++) {
      try { await page.goto('http://127.0.0.1:18765'); break; }
      catch (error) { if (i >= 20) throw error; await new Promise(resolve => setTimeout(resolve, 100)); }
    }
    const shot = async name => { await page.screenshot({ path: path.join(output, name), fullPage: true }); screenshots.push(name); };
    await page.locator('#start-mission').waitFor();
    await shot('HARNESS-01-start-en.png');
    checks.push('first-run rendered');
    await page.locator('#start-genesis-next').click();
    await page.waitForFunction(() => document.querySelector('#omega-capabilities')?.textContent?.includes('bounded-verification'));
    assert.equal(await page.locator('#omega-run').isEnabled(), false);
    await shot('HARNESS-07-genesis-next-en.png');
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
    await page.locator('[data-view="verification"]').click();
    assert.match(await page.locator('#verification-list').textContent(), /PASSED IN SCOPE/);
    await shot('HARNESS-04-verification-en.png');
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
    await page.waitForFunction(() => document.querySelector('#omega-results')?.textContent?.includes('NO_SUPERIORITY_ESTABLISHED'));
    await shot('HARNESS-09-genesis-next-mobile-fr.png');
    const omegaWidths = await page.evaluate(() => ({ viewport: innerWidth, content: document.documentElement.scrollWidth }));
    assert.ok(omegaWidths.content <= omegaWidths.viewport + 2, JSON.stringify(omegaWidths));
    assert.match(await page.locator('#omega-title').textContent(), /Inventez/);
    checks.push('GENESIS NEXT French mobile results without page overflow');

    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output, 'BROWSER-VERIFICATION.json'), JSON.stringify({ status: 'PASS', source_revision: process.env.EXPECTED_SOURCE || null, browser: await browser.version(), platform: process.platform, checks, screenshots, errors, scope: 'Linux Chromium graphical checks; no live model or other OS qualification.' }, null, 2));
    console.log(JSON.stringify({ status: 'PASS', checks, screenshots }));
  } catch (error) {
    fs.writeFileSync(path.join(output, 'BROWSER-VERIFICATION.json'), JSON.stringify({ status: 'FAIL', checks, screenshots, errors, failure: error.message }, null, 2));
    throw error;
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
    fs.rmSync(temporary, { recursive: true, force: true });
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
