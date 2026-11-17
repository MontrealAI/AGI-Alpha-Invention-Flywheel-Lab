'use strict';

const assert = require('node:assert/strict');

// Operator-authored exchanges on a real private HTTP workspace. The backend
// builds and evaluates the candidates; this procedure makes no model claim.
async function qualifyAdaptiveRepair(page, send, assertLayout, sample) {
  await page.locator('#fresh').click();
  await page.locator('#example').selectOption('integrity');
  assert.equal(await page.locator('#strategy').inputValue(), 'adaptive');
  for (const permission of ['local_model', 'assisted_model', 'public_sources', 'allow_program_reuse']) {
    assert.equal(await page.locator('#' + permission).isChecked(), false);
  }
  // A declared manifest is compilable by a conventional specialist without
  // a model permission, external source retrieval, or operator handoff.
  await page.locator('#start').click();
  await page.locator('#actions').waitFor();
  const specialist = JSON.parse(await page.locator('#raw').textContent());
  assert.equal(specialist.routing.method, 'specialist');
  assert.equal(await page.locator('#route-method').textContent(), 'Built-in specialist');
  assert.equal(specialist.events.some(e => e.stage === 'discover'), false);
  await page.locator('#fresh').click();
  await page.locator('#example').selectOption('integrity');
  await page.locator('#settings').evaluate(el => { el.open = true; });
  await page.locator('#assisted_model').check();
  await page.locator('#direct-method').selectOption('model');
  const resources = JSON.parse(await page.locator('#resources').inputValue());
  resources.max_repairs = 1;
  await page.locator('#resources').fill(JSON.stringify(resources));
  await page.locator('#start').click();

  const manifest = sample.mission.construction_spec.definition.manifest;
  const changed = {...manifest, [Object.keys(manifest)[0]]: '0'.repeat(64)};
  await send(page, 'construct', {kind: 'manifest_audit', program: {manifest: changed}});
  await page.waitForFunction(() => {
    const text = document.getElementById('raw').textContent;
    return text && JSON.parse(text).handoff?.stage === 'repair';
  });
  assert.equal(await page.locator('#route-title').textContent(), 'Direct ignition');
  assert.match(await page.locator('#attempt-list h4').textContent(), /Rejected/);
  assert.equal(await page.locator('#bundle').getAttribute('href'), null);
  assert.match(await page.locator('#handoff-title').textContent(), /Repair/);
  await assertLayout(page, 360);
  await send(page, 'repair', {kind:'manifest_audit', program:{manifest}});
  await page.locator('#actions').waitFor();

  const run = JSON.parse(await page.locator('#raw').textContent());
  assert.equal(run.routing.route, 'direct');
  assert.equal(run.routing.strategy, 'adaptive');
  assert.deepEqual(run.construction_attempts.map(x => x.status), ['rejected', 'accepted']);
  assert.equal(run.construction_attempts[0].contract_sha256, run.construction_attempts[1].contract_sha256);
  assert.equal(run.events.some(e => e.stage === 'discover' || e.stage === 'challenge'), false);
  assert.equal(await page.locator('#attempt-list .attempt').count(), 2);
  assert.equal(await page.locator('#checkpoints li').count(), Math.min(3, run.events.length));
  assert.equal(await page.locator('#checkpoints li:last-child p').textContent(), run.events.at(-1).message);
  await page.locator('#try').click();
  await page.waitForFunction(() => document.getElementById('output').textContent.includes('"matched"'));
  for (const width of [360, 390, 1280]) await assertLayout(page, width);
  await page.locator('#beneficiary').fill('Reviewer for a fresh revision');
  assert.equal(await page.locator('#actions').isHidden(), true);
  assert.equal(await page.locator('#bundle').getAttribute('href'), null);
}

async function qualifyPairingDecision(page, assertLayout) {
  await page.locator('#fresh').click();
  await page.locator('#example').selectOption('pairing');
  assert.equal(await page.locator('#pairing-budget').inputValue(), '2000000');
  assert.equal(await page.locator('#pairing-percent').inputValue(), '45');
  await page.locator('#start').click();
  await page.locator('#actions').waitFor();
  const baseline = JSON.parse(await page.locator('#raw').textContent());
  assert.equal(baseline.pairing_result.audit.solved, 18);
  assert.equal(baseline.pairing_result.audit.tasks, 40);
  assert.equal(baseline.pairing_result.sql_agreement, true);
  assert.equal(await page.locator('#pairing-verdict').textContent(), 'Pilot criteria met');
  assert.match(await page.locator('#pairing-metrics').textContent(), /18 of 40/);
  assert.equal(await page.locator('#trial').isVisible(), false);
  assert.equal(await page.locator('#pilot-next').isVisible(), true);
  assert.equal(await page.locator('#recipient-command').textContent(), 'python3 -B verify_decision.py');
  await page.locator('#try').click();
  await page.waitForFunction(() => document.getElementById('output').textContent.includes('"audit_pass"'));
  await assertLayout(page, 360);
  await page.locator('#pairing-percent').fill('60');
  await page.locator('#strategy').selectOption('research');
  assert.equal(await page.locator('#actions').isHidden(), true);
  await page.locator('#start').click();
  await page.waitForFunction(() => {
    const raw = document.getElementById('raw').textContent;
    return raw && JSON.parse(raw).version === 2 && JSON.parse(raw).status === 'verified';
  });
  const followup = JSON.parse(await page.locator('#raw').textContent());
  assert.equal(followup.evaluation.status, 'pass');
  assert.equal(followup.routing.route, 'research');
  assert.equal(await page.locator('#study-candidates details').count(), 6);
  assert.equal(await page.locator('#study-candidates details[open]').count(), 1);
  const selected = page.locator('#study-candidates details[open]');
  assert.match(await selected.locator('summary').textContent(), /Challenger selected/);
  assert.match(await selected.locator('a').first().getAttribute('href'), /^https:/);
  assert.equal(await page.locator('#pilot-next').isHidden(), true);
  assert.equal(followup.pairing_result.verdict, 'audit_failed');
  assert.equal(await page.locator('#pairing-verdict').textContent(), 'Pilot criteria missed');
  assert.equal(await page.locator('#bundle').isVisible(), true);
  assert.notEqual(followup.contract_sha256, baseline.contract_sha256);
  await assertLayout(page, 1280);
}

async function qualifyPublicBoundary(page) {
  const context = page.context();
  const endpoint = new URL('/showcase', page.url()).href;
  const response = context.waitForEvent('response', r => r.url() === endpoint);
  const opened = context.waitForEvent('page');
  await page.locator('#public-showcase').click();
  const exhibit = await opened;
  try {
    await exhibit.waitForLoadState('load');
    const result = await response;
    assert.equal(result.status(), 200);
    assert.match(result.headers()['content-security-policy'], /connect-src 'none'/);
    assert.match(result.headers()['content-security-policy'], /sandbox allow-scripts allow-downloads/);
    const boundary = await exhibit.evaluate(() => ({
      origin: self.origin, opener: !!window.opener, referrer: document.referrer
    }));
    assert.deepEqual(boundary, { origin: 'null', opener: false, referrer: '' });
    assert.equal(await exhibit.locator('#brief').count(), 0);
  } finally {
    await exhibit.close();
  }
}

module.exports = { qualifyAdaptiveRepair, qualifyPairingDecision, qualifyPublicBoundary };
