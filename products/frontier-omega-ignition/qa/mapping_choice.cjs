'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

async function openChoice(page, method) {
  await page.locator('#fresh').click();
  await page.locator('#example').selectOption('migration');
  const settings = page.locator('#settings');
  if (!(await settings.evaluate(el => el.open))) await settings.locator('summary').click();
  await page.locator('#direct-method').selectOption(method);
  if (method === 'model_choice') await page.locator('#assisted_model').check();
  await page.locator('#start').click();
}
async function readPending(page, version) {
  await page.waitForFunction(v => {
    const value = document.getElementById('raw').textContent;
    if (!value) return false;
    const run = JSON.parse(value);
    return run.version === v && run.status === 'awaiting_choice';
  }, version);
  return JSON.parse(await page.locator('#raw').textContent());
}
async function qualifyMappingChoice(page, work, assertLayout, receive, send) {
  await openChoice(page, 'operator_choice');
  const old = await readPending(page, 1);
  assert.equal(await page.locator('#apply-choice').isDisabled(), true);
  assert.equal(await page.locator('#bundle').getAttribute('href'), null);
  assert.equal(await page.locator('#choice-options input').count(), 2);
  assert.match(await page.locator('#choice-examples-content').textContent(), /passive-mechanical-function/);
  for (const frozenCase of old.mission.construction_spec.cases) {
    assert.equal((await page.locator('#mapping-choice').textContent()).includes(frozenCase.name), false);
  }
  assert.equal(await page.locator('#choice-options input:checked').count(), 0);
  await assertLayout(page, 360);

  // A revision change discards the old option selection and its request identity.
  await page.locator('#choice-options input').first().check();
  await page.locator('#beneficiary').fill('Editorial release coordinator');
  assert.equal(await page.locator('#mapping-choice').isHidden(), true);
  await page.locator('#start').click();
  const current = await readPending(page, 2);
  assert.notEqual(current.mapping_choice.sha256, old.mapping_choice.sha256);
  assert.equal(await page.locator('#choice-options input:checked').count(), 0);
  const address = new URL('/api/runs/' + current.id + '/choose', page.url()).href;
  const stale = await page.request.post(address, {
    headers:{'X-Ignition-Request':'1'}, data:{version:2, sha256:old.mapping_choice.sha256, choice:'abstain'}
  });
  assert.equal(stale.status(), 409);
  await page.reload();
  await readPending(page, 2);

  // The published ambition expressly requires the first identifier segment.
  // Choose from the displayed operations, without using evaluator cases.
  const options = current.mapping_choice.candidates;
  const index = options.findIndex(c => c.operations.some(op =>
    op.column?.target === 'area' && op.column.source === 'id' &&
    op.column.split?.separator === '-' && op.column.split.index === 0));
  assert.ok(index >= 0, 'The intended public operation must be inspectable');
  await page.locator('#choice-options input').nth(index).check();
  await page.locator('#apply-choice').click();
  await page.locator('#actions').waitFor();
  const accepted = JSON.parse(await page.locator('#raw').textContent());
  assert.equal(accepted.status, 'verified');
  assert.equal(accepted.evaluation.status, 'pass');
  assert.equal(accepted.evaluation.cases.every(c => c.candidate_pass), true);
  const zip = path.join(work, 'mapping-choice.zip');
  await receive(page, '#bundle', zip);
  execFileSync('python3', ['-c',
    "import tempfile,zipfile,subprocess,sys\nwith tempfile.TemporaryDirectory() as d:\n with zipfile.ZipFile(sys.argv[1]) as z: z.extractall(d)\n subprocess.run([sys.executable,'-I','run.py','verify'],cwd=d,check=True)",
    zip]);
  await assertLayout(page, 1280);

  await openChoice(page, 'operator_choice');
  await readPending(page, 1);
  await page.locator('#abstain-choice').click();
  await page.waitForFunction(() => JSON.parse(document.getElementById('raw').textContent).status === 'deferred');
  assert.equal(await page.locator('#bundle').getAttribute('href'), null);
  assert.equal(await page.locator('#mapping-choice').isHidden(), true);

  // An operator-assisted model is separately attributed. Its abstention never
  // becomes an unrequested manual intervention or an accepted construction.
  await openChoice(page, 'model_choice');
  await send(page, 'choose_hypothesis', {choice:'abstain'});
  await page.waitForFunction(() => JSON.parse(document.getElementById('raw').textContent).status === 'deferred');
  assert.equal(await page.locator('#bundle').getAttribute('href'), null);
  assert.equal(await page.locator('#mapping-choice').isHidden(), true);
}

module.exports = {qualifyMappingChoice};
