/* SPDX-License-Identifier: Apache-2.0
 * Copyright 2026 Vincent Boucher
 * Render an already assembled owner handoff without modifying its ZIP.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { pathToFileURL, fileURLToPath } = require('node:url');
const { chromium } = require('playwright-core');

async function main() {
  const [directory, output, source] = process.argv.slice(2);
  assert(directory && output && /^[0-9a-f]{40}$/.test(source), 'Expected owner directory, output directory and exact source SHA');
  const root = fs.realpathSync(directory);
  const identity = JSON.parse(fs.readFileSync(path.join(root, 'OWNER-HANDOFF.json'), 'utf8'));
  assert.equal(identity.source_revision, source);
  assert.equal(identity.required_deliverables.length, 22);
  assert(identity.required_deliverables.every(row => row.included === true), 'A required delivery category is incomplete');
  const genesis = identity.required_deliverables.find(row => row.id === '11');
  const scientific = identity.required_deliverables.find(row => row.id === '13');
  assert(genesis.paths.includes('02-EXPLORE-THE-EDITION/bridge/genesis_next.py'), 'The GENESIS implementation is missing');
  for (const name of ['OMEGA-DEMONSTRATION.json', 'OMEGA-FRESH-SOURCE-FREEZE.json', 'OMEGA-FRESH-SUCCESSOR.json']) {
    assert(scientific.paths.includes('05-VERIFICATION/' + name), 'The current GENESIS raw evidence is missing');
  }
  const start = path.join(root, '00-OWNER-START.html');
  assert(fs.statSync(start).isFile());
  const destination = path.resolve(output);
  fs.mkdirSync(destination, { recursive: true });
  const receipt = {
    schema: 'alpha-genesis-harness-owner-visual/v1', status: 'FAIL',
    source_revision: source, platform: process.platform,
    scope: 'Actual headless Chromium rendering, local link inventory and responsive smoke checks of the assembled owner HTML; not a full accessibility audit.',
    checks: [], errors: [], screenshots: [],
  };
  const executable = [process.env.CHROME_BIN, '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].filter(Boolean).find(p => fs.existsSync(p));
  let browser;
  try {
    assert(executable, 'A system Chromium executable is required');
    browser = await chromium.launch({ executablePath: executable, headless: true, args: ['--no-sandbox'] });
    receipt.browser_version = browser.version();
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
    page.on('pageerror', error => receipt.errors.push(String(error)));
    const network = [];
    page.on('request', request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
    await page.goto(pathToFileURL(start).href, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    assert.equal(await page.locator('h1').count(), 1);
    assert((await page.locator('body').innerText()).includes(source));
    const links = await page.locator('a[href]').evaluateAll(nodes => nodes.map(node => node.href));
    let local = 0;
    for (const href of links) {
      const url = new URL(href);
      if (url.protocol !== 'file:') continue;
      const target = fileURLToPath(url);
      const relative = path.relative(root, target);
      assert(relative === '' || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative)), 'Owner link escapes the handoff');
      assert(fs.existsSync(target), 'Missing owner link: ' + relative);
      local++;
    }
    assert(local >= 22, 'Owner deliverable links are missing');
    receipt.checks.push('Exact source identity displayed', 'At least 22 existing local deliverable links, contained within the owner bundle');
    assert.equal(await page.locator('#files tbody tr').count(), 22);
    receipt.checks.push('All 22 delivery categories rendered');
    const desktop = 'HARNESS-OWNER-desktop.png';
    await page.screenshot({ path: path.join(destination, desktop), fullPage: true });
    receipt.screenshots.push(desktop);
    await page.setViewportSize({ width: 390, height: 844 });
    const sizes = await page.evaluate(() => ({ viewport: innerWidth, body: document.documentElement.scrollWidth }));
    assert(sizes.body <= sizes.viewport + 1, 'Owner page overflows the mobile viewport');
    const mobile = 'HARNESS-OWNER-mobile.png';
    await page.screenshot({ path: path.join(destination, mobile) });
    receipt.screenshots.push(mobile);
    receipt.checks.push('390px responsive viewport without document overflow');
    assert.deepEqual(network, [], 'Owner page unexpectedly requested the network');
    assert.deepEqual(receipt.errors, []);
    receipt.checks.push('No network requests or JavaScript page errors');
    receipt.status = 'PASS';
  } catch (error) {
    receipt.error = String(error && error.stack || error);
    throw error;
  } finally {
    fs.writeFileSync(path.join(destination, 'OWNER-VISUAL-VERIFICATION.json'), JSON.stringify(receipt, null, 2) + '\n');
    if (browser) await browser.close();
  }
  console.log(JSON.stringify(receipt));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
