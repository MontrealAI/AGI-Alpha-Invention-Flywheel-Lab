'use strict';
// Run the published programs and reopen the bytes actually received by the browser.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { execFileSync } = require('node:child_process');
const { chromium } = require('playwright-core');

const repo = path.resolve(__dirname, '../../..');
const pages = path.join(repo, 'docs/research');

async function download(page, button, target) {
  const received = page.waitForEvent('download');
  await page.locator(button).click();
  await (await received).saveAs(target);
}

async function world(page, file, scratch) {
  await page.goto(pathToFileURL(file).href);
  for (const kind of ['strategy', 'causal', 'market']) {
    await page.locator('[data-lab="' + kind + '"]').click();
    await page.locator('#run-' + kind).click();
    assert.equal(await page.locator('#download-' + kind).isEnabled(), true);
  }
  await page.locator('#market-prob').press('ArrowLeft');
  await page.locator('[data-lab="causal"]').click();
  await page.locator('#causal-m').press('ArrowLeft');
  await page.locator('[data-lab="strategy"]').click();
  await page.locator('#strategy-checkpoint').check();
  for (const kind of ['strategy', 'causal', 'market']) {
    assert.equal(await page.locator('#download-' + kind).isDisabled(), true);
    assert.match(await page.locator('#' + kind + '-verdict').textContent(), /changed/i);
  }
  const sessionFile = path.join(scratch, 'session.json');
  await download(page, '#download-session', sessionFile);
  const session = JSON.parse(await fs.readFile(sessionFile, 'utf8'));
  for (const kind of ['strategy', 'causal', 'market']) assert.equal(session[kind + '_study'], null);

  await page.locator('[data-lab="causal"]').click();
  await page.locator('#run-causal').click();
  await download(page, '#download-causal', sessionFile);
  assert.equal(JSON.parse(await fs.readFile(sessionFile, 'utf8')).m, 11);

  await page.locator('[data-lab="builder"]').click();
  const artifact = path.join(scratch, 'instrument.html');
  await download(page, '#download-instrument', artifact);
  await page.goto(pathToFileURL(artifact).href);
  const first = page.locator('#inputs input').first();
  for (const unsupported of ['', '3', '-3', '0.5']) {
    await first.fill(unsupported);
    assert.match(await page.locator('#decision').textContent(), /refused/i);
    assert.equal(await page.locator('#measurement').textContent(), '—');
    assert.doesNotMatch(await page.locator('#verification').textContent(), /PASS/);
  }
  await first.fill('-2');
  assert.match(await page.locator('#verification').textContent(), /PASS/);
}

async function gate(page, scratch) {
  await page.goto(pathToFileURL(path.join(pages, 'frontier-omega.html')).href);
  await page.locator('[data-preset="founder"]').click();
  await page.locator('#discover').click();
  await page.locator('[data-select]').first().click();
  await page.locator('#go-build').click();

  // Pause the digest at precisely the boundary where a later edit used to resurrect evidence.
  await page.evaluate(() => {
    window.originalDigest = crypto.subtle.digest.bind(crypto.subtle);
    crypto.subtle.digest = () => new Promise(resolve => { window.resolveDigest = resolve; });
  });
  await page.locator('#run-checks').click();
  await page.waitForFunction(() => typeof window.resolveDigest === 'function');
  await page.locator('#prob').fill('54');
  await page.evaluate(() => { window.resolveDigest(new ArrayBuffer(32)); });
  assert.equal(await page.locator('#export').isDisabled(), true);
  assert.doesNotMatch(await page.locator('#receipt').textContent(), /Payload checksum/);
  await page.evaluate(() => { crypto.subtle.digest = window.originalDigest; });
  await page.locator('#run-checks').click();
  await page.waitForFunction(() => !document.getElementById('export').disabled);

  const portable = path.join(scratch, 'decision-gate.html');
  await download(page, '#artifact', portable);
  await page.goto(pathToFileURL(portable).href);
  const prob = page.locator('[data-key="probability"]');
  for (const unsupported of ['', '-0.01', '1.01', '0.123']) {
    await prob.fill(unsupported);
    assert.equal(await page.locator('#download').isDisabled(), true);
    assert.equal(await page.locator('#result').textContent(), '—');
    assert.doesNotMatch(await page.locator('#check').textContent(), /PASS/);
    assert.equal(await page.evaluate(() => window.latest), null);
  }
  await prob.fill('0.3');
  const receipt = path.join(scratch, 'gate.json');
  await download(page, '#download', receipt);
  const result = JSON.parse(await fs.readFile(receipt, 'utf8'));
  assert.equal(result.assumptions.probability, 0.3);
  assert.equal(result.arithmetic_passed, true);
}

async function main() {
  const scratch = await fs.mkdtemp(path.join(os.tmpdir(), 'ignition-browser-'));
  let browser;
  try {
    const assembled = path.join(scratch, 'assembled');
    const original = path.join(pages, 'frontier-omega-world-lab.html');
    execFileSync('python3', [path.join(repo, 'docs/frontier-omega-ignition/research-edition/assemble.py'),
      '--base', original, '--output', assembled]);
    browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
      chromiumSandbox: process.env.CHROMIUM_SANDBOX === '1'});
    const page = await browser.newPage({reducedMotion: 'reduce'});
    await page.route(/^https?:/, route => route.abort());
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    await world(page, original, scratch);
    await world(page, path.join(assembled, 'index.html'), scratch);
    await gate(page, scratch);
    assert.deepEqual(errors, []);
    console.log('Passed file-navigation checks for two World Lab editions, economic gate, downloaded tools and receipts.');
  } finally {
    if (browser) await browser.close();
    await fs.rm(scratch, {recursive: true, force: true});
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
