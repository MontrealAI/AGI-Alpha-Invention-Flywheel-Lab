/* SPDX-License-Identifier: Apache-2.0 */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');

async function main() {
  const [url, mode, output] = process.argv.slice(2);
  assert.ok(url && ['static', 'reopen', 'construct'].includes(mode) && output,
    'Usage: node UI_WORKSHOP_BROWSER.cjs URL static|reopen|construct OUTPUT');
  await fs.mkdir(output, {recursive: true});
  const browser = await chromium.launch(process.env.WORKSHOP_CHROMIUM ? {executablePath: process.env.WORKSHOP_CHROMIUM} : {});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}, acceptDownloads: true});
  const errors = [], api = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/')) api.push(new URL(request.url()).pathname);
  });
  const capture = async name => {
    const file = path.join(output, name + '.png');
    await page.locator('#workshop').scrollIntoViewIfNeeded();
    await page.screenshot({path: file});
    return crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex');
  };
  const state = {url, mode, browser: browser.version(), os: process.platform, screenshots: {}, checks: {}};
  try {
    assert.equal((await page.goto(url, {waitUntil: 'domcontentloaded'})).status(), 200);
    await page.locator('#workshop-title').waitFor();
    const mission = page.locator('[data-workshop-view="mission"]');
    await mission.focus();
    assert.equal(await mission.evaluate(button => getComputedStyle(button).outlineStyle), 'solid');
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement.dataset.workshopView), 'bench');
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('[data-workshop-view="bench"]').getAttribute('aria-pressed'), 'true');
    await mission.click();
    state.checks.keyboardFocus = true;
    const draft = 'Calibrate a repair station before its first shift.';
    await page.locator('#workshop-ambition').fill(draft);
    await page.locator('#workshop-save').click();
    await page.reload({waitUntil: 'domcontentloaded'});
    assert.equal(await page.locator('#workshop-ambition').inputValue(), draft);
    state.checks.draftReload = true;
    state.screenshots['workshop-en'] = await capture('workshop-en');
    if (mode === 'static') {
      await page.locator('#workshop-connection').getByText('Downloadable editions').waitFor();
      assert.equal(await page.locator('#workshop-start').isEnabled(), false);
      assert.deepEqual(api, []);
      state.checks.staticNoConnectorRequests = true;
    } else {
      if (mode === 'construct') {
        await page.waitForFunction(() => document.querySelector('#workshop-model').options.length > 1);
        await page.locator('#workshop-model').selectOption({index: 1});
        await page.locator('#workshop-details > summary').click();
        await page.locator('#workshop-context').fill('Input x is a package count. Return exactly one output result equal to twice x.');
        await page.locator('#workshop-cases').fill('[{"input":{"x":2},"expected":{"result":4}},{"input":{"x":0},"expected":{"result":0}},{"input":{"x":17},"expected":{"result":34}}]');
        await page.locator('#workshop-consent').check();
        await page.locator('#workshop-start').click();
      } else {
        await page.waitForFunction(() => document.querySelector('#workshop-history').options.length > 1);
        await page.locator('#workshop-history').selectOption({index: 1});
      }
      await page.locator('#workshop-summary').getByText('Qualified for these checks', {exact: false}).waitFor({timeout: 240000});
      assert.equal(await page.locator('#workshop-export').isEnabled(), true);
      await page.locator('[data-workshop-view="bench"]').click();
      await page.locator('#workshop-bench').getByText('instrument.json', {exact: false}).first().waitFor();
      state.screenshots['workshop-artifacts'] = await capture('workshop-artifacts');
      await page.locator('[data-workshop-view="evidence"]').click();
      await page.locator('#workshop-evidence').getByRole('heading', {name: 'Independent checks'}).waitFor();
      state.screenshots['workshop-evidence-en'] = await capture('workshop-evidence-en');
      await mission.click();
      const download = page.waitForEvent('download');
      await page.locator('#workshop-export').click();
      const archive = await download;
      const destination = path.join(output, 'browser-instrument-proof.zip');
      await archive.saveAs(destination);
      state.archiveSha256 = crypto.createHash('sha256').update(await fs.readFile(destination)).digest('hex');
      await page.reload({waitUntil: 'domcontentloaded'});
      await page.locator('#workshop-summary').getByText('Qualified for these checks', {exact: false}).waitFor();
      state.checks.connectedReopen = true;
    }
    await page.locator('#language-toggle').click();
    assert.equal(await page.locator('html').getAttribute('lang'), 'fr');
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await page.locator('#workshop-title').textContent(), 'L’atelier des instruments');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    state.screenshots['workshop-fr-mobile'] = await capture('workshop-fr-mobile');
    state.checks.bilingualResponsive = true;
    assert.deepEqual(errors, []);
    state.status = 'PASS';
  } catch (error) {
    state.status = 'FAIL';
    state.error = String(error);
    state.screenshots['workshop-failure'] = await capture('workshop-failure').catch(() => null);
    process.exitCode = 1;
  } finally {
    await fs.writeFile(path.join(output, 'WORKSHOP-BROWSER.json'), JSON.stringify(state, null, 2) + '\n');
    await browser.close();
    console.log(JSON.stringify(state));
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
