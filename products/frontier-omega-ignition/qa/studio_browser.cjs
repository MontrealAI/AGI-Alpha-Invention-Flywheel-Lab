'use strict';
// First-use acceptance against the real Studio over HTTPS. The disposable default
// has no model or paid integrations. For an authorized production smoke supply an
// exact origin and four dedicated invitations via the operator environment.
const assert = require('node:assert/strict');
const { spawn, execFileSync } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { createInterface } = require('node:readline');
const { chromium } = require('playwright-core');
const axe = require('axe-core');
const targets = require('./studio_targets.json').staging_and_production_budgets;
const product = path.resolve(__dirname, '..');

async function audit(page, scope) {
  const { overflow, lang } = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth > innerWidth,
    lang: document.documentElement.lang,
  }));
  assert.equal(overflow, false, 'Horizontal page overflow at ' + scope);
  // Evaluate in the automation realm, without relaxing the site's script CSP.
  await page.evaluate(axe.source);
  const found = await page.evaluate(async () => {
    const result = await window.axe.run(document, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] }
    });
    return result.violations.map(v => ({ id: v.id, targets: v.nodes.map(n => n.target) }));
  });
  assert.deepEqual(found, [], 'Accessibility findings on ' + scope + ': ' + JSON.stringify(found));
  return { scope, lang, overflow, automated_violations: found.length };
}

async function qualify(config, index, local, root) {
  const lang = index % 2 === 0 ? 'en' : 'fr';
  const width = index < 2 ? 1280 : 390;
  const profile = path.join(root, 'profile-' + index);
  const options = {
    executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
    locale: lang + (lang === 'fr' ? '-CA' : '-US'),
    viewport: { width, height: 844 }, reducedMotion: 'reduce',
    ignoreHTTPSErrors: local, acceptDownloads: true,
    headless: true, chromiumSandbox: process.env.CHROMIUM_SANDBOX === '1',
  };
  const report = { language: lang, viewport_width: width, accessibility: [] };
  let browser = await chromium.launchPersistentContext(profile, options);
  try {
    let page = browser.pages()[0];
    const errors = [];
    page.on('pageerror', e => errors.push(e.name));
    await page.goto(config.origin);
    await page.locator('#' + lang).click();
    await page.keyboard.press('Control+Home');
    assert.equal(await page.locator('html').getAttribute('lang'), lang);
    report.accessibility.push(await audit(page, 'introduction'));
    await page.locator('a[href="/demo"]').first().click();
    report.accessibility.push(await audit(page, 'public-demo'));
    await page.locator('a[href="/studio"]').first().click();
    await page.locator('#invite').fill(config.invites[index]);
    await page.locator('#signin-button').click();
    await page.locator('#workspace').waitFor({ state:'visible' });
    assert.equal(await page.locator('html').getAttribute('lang'), lang);
    report.accessibility.push(await audit(page, 'intake'));

    const text = lang === 'fr' ? 'Échantillon public validé' : 'Reviewed public sample';
    const purpose = lang === 'fr' ? 'Convertir un registre de recherche pour la livraison bilingue.' :
      'Convert a research register for bilingual handoff.';
    await page.locator('#template').selectOption('migration');
    await page.locator('#purpose').fill(purpose);
    await page.locator('#beneficiary').fill('MONTREAL.AI');
    await page.locator('#from-field').fill('finding');
    await page.locator('#to-field').fill('label');
    await page.locator('#sample-value').fill(text);
    await page.locator('#expected-value').fill(text);
    await page.locator('#review').click();
    await page.locator('#review-panel').waitFor({ state: 'visible' });
    await page.locator('#start').click();
    await page.locator('#bundle').waitFor({ state:'visible', timeout:45000 });
    report.accessibility.push(await audit(page, 'accepted-result'));
    const runLink = await page.locator('#bundle').getAttribute('href');
    const pendingDownload = page.waitForEvent('download');
    await page.locator('#bundle').click();
    const folder = path.join(root, 'received-' + index);
    await fs.mkdir(folder);
    const zipPath = path.join(folder, 'artifact.zip');
    await (await pendingDownload).saveAs(zipPath);
    const verification = execFileSync('python3', ['-B', '-c',
      'from pathlib import Path; from qualify_live import check_portable; import sys; ' +
      'p=Path(sys.argv[1]); r=check_portable(p.read_bytes(), p.parent); ' +
      'assert r["verified_exit"] == r["example_exit"] == 0', zipPath],
      { cwd:product, stdio:['ignore','pipe','pipe'] });
    report.portable_replay = verification !== undefined;
    const evidence = await page.request.get(new URL(await page.locator('#run-evidence').getAttribute('href'), config.origin).href);
    assert.equal(evidence.status(), 200);
    assert.ok(Object.keys(await evidence.json()).length > 0);
    report.private_evidence_download = true;
    await page.locator('#try-panel summary').click();
    await page.locator('#sample').fill(JSON.stringify({rows:[{finding:'fresh-é-' + index}]}));
    await page.locator('#try').click();
    await page.waitForFunction(s => document.querySelector('#output').textContent.includes(s), 'fresh-é-' + index);
    const sample = JSON.parse(await page.locator('#output').textContent());
    assert.equal(JSON.stringify(sample).includes('"label":"fresh-é-' + index + '"'), true);

    const timing = await page.evaluate(async n => {
      const ms = [];
      for (let i=0; i<n; i++) {
        const t=performance.now();
        const response=await fetch('/api/runs');
        if (!response.ok) throw new Error('Status request failed');
        await response.json(); ms.push(performance.now()-t);
      }
      return ms.sort((a,b)=>a-b);
    }, targets.status_sample_count);
    report.authenticated_status_p95_ms = Math.ceil(timing[Math.ceil(timing.length * .95)-1]);
    assert.ok(report.authenticated_status_p95_ms <= targets.p95_authenticated_status_ms_excluding_async_worker);
    assert.deepEqual(errors, []);
    await browser.close();
    browser = await chromium.launchPersistentContext(profile, options);
    page = browser.pages()[0];
    await page.goto(config.origin + '/studio');
    const saved = page.locator('#inventory button').first();
    await saved.waitFor({state:'visible'});
    await saved.click();
    await page.locator('#bundle').waitFor({state:'visible'});
    assert.equal(await page.locator('#bundle').getAttribute('href'), runLink);
    report.resume_after_browser_restart = true;
    return report;
  } finally { await browser.close(); }
}

async function main() {
  const origin = process.env.IGNITION_SMOKE_ORIGIN;
  const local = !origin;
  let child, reader, config;
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ignition-first-use-'));
  try {
    if (local) {
      child = spawn('python3', ['-B', 'qa/studio_staging.py'], {cwd: product,stdio:['pipe','pipe','inherit']});
      reader = createInterface({input: child.stdout});
      const line = await Promise.race([once(reader,'line').then(x=>x[0]),once(child,'exit').then(()=>{
        throw new Error('Staging bootstrap exited before readiness');
      })]);
      config = JSON.parse(line);
    } else {
      const parsed = new URL(origin);
      assert.equal(parsed.protocol,'https:');
      assert.equal(parsed.origin,origin);
      assert.equal(process.env.IGNITION_SMOKE_CONFIRM,'authorized-production-missions');
      config = {origin, invites:JSON.parse(process.env.IGNITION_SMOKE_INVITES || '[]')};
    }
    assert.equal(config.invites.length,4);
    const observations = [];
    for (let index=0; index<4; index++) observations.push(await qualify(config,index,local,root));
    const receipt = {schema:'ignition/studio-first-use/v1', environment:local?'disposable-staging':'production',
      operator:'automated-browser', mission:'guided direct construction',source:execFileSync('git',
        ['rev-parse','HEAD'], {cwd:product,encoding:'utf8'}).trim(), observations};
    console.log(JSON.stringify(receipt,null,2));
  } finally {
    if (child && child.exitCode === null) {
      const closed = once(child,'exit');
      child.stdin.end('\n');
      await closed;
    }
    if (reader) reader.close();
    await fs.rm(root,{recursive:true,force:true});
  }
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
