'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

async function qualifyEndpointDecision(page, work, assertLayout, receive) {
  const field = id => page.locator('#' + id);
  async function submit(version) {
    await field('start').click();
    await page.waitForFunction(v => {
      const raw = document.querySelector('#raw').textContent;
      if (!raw) return false;
      const run = JSON.parse(raw);
      return run.version === v && run.status === 'verified' && run.endpoint_result;
    }, version);
    assert.equal(await field('actions').isVisible(), true);
    const run = JSON.parse(await field('raw').textContent());
    assert.equal(run.evaluation.verification.checked, true);
    return run.endpoint_result;
  }
  await field('fresh').click();
  await field('example').selectOption('endpoint');
  assert.equal(await field('ep-model').inputValue(), 'GPT-OSS 120B');
  assert.equal(await field('ep-ttft').inputValue(), '500');
  assert.equal(await field('ep-rate').inputValue(), '100');
  assert.deepEqual(JSON.parse(await field('resources').inputValue()), {});
  assert.equal((await submit(1)).selected[0].concurrency, 140);
  assert.match(await field('endpoint-verdict').textContent(), /140 concurrent requests/);
  assert.match(await field('endpoint-witnesses').textContent(), /147\.6/);
  assert.match(await field('endpoint-witnesses').textContent(), /294\.4/);
  assert.match(await field('endpoint-next').textContent(), /next higher recorded load/);
  assert.equal(await field('trial').isVisible(), false);
  assert.match(await field('recipient-command').textContent(), /endpoint_lab\/replay_delivery.py/);
  await field('try').click();
  await page.waitForFunction(() => document.querySelector('#output').textContent.includes('"supported"'));
  await assertLayout(page, 360);

  await field('ep-model').fill('deepseek-v4_1-flash');
  await field('ep-dataset').fill('mlperf_agentic_inference_dataset');
  await field('ep-load').selectOption('online');
  await field('ep-metric').selectOption('inverse_p90_tpot');
  await field('ep-rate').fill('110');
  await field('ep-ttft').fill('499.99');
  await field('ep-concurrency').fill('24');
  assert.equal(await field('actions').isVisible(), false);
  assert.equal(await field('bundle').getAttribute('href'), null);
  const fresh = await submit(2);
  assert.equal(fresh.selected[0].concurrency, 128);
  assert.equal(fresh.contract.max_ttft_p90_ms, '499.99');
  assert.match(await field('endpoint-witnesses').textContent(), /8\.64/);
  await page.reload();
  await field('endpoint-result').waitFor();
  assert.equal(await field('ep-ttft').inputValue(), '499.99');
  assert.equal(await field('ep-concurrency').inputValue(), '24');
  assert.equal(await field('ep-metric').inputValue(), 'inverse_p90_tpot');

  await field('ep-price').check();
  const withheld = await submit(3);
  assert.equal(withheld.decision, 'withheld');
  assert.deepEqual(withheld.selected, []);
  assert.match(await field('endpoint-verdict').textContent(), /withheld/);
  assert.match(await field('endpoint-next').textContent(), /Price evidence is missing/);
  await page.locator('#endpoint-witnesses summary').click();
  assert.equal(await page.locator('#endpoint-witnesses .endpoint-point').count(), 9);
  assert.match(await field('endpoint-witnesses').textContent(), /8\.64/);
  await assertLayout(page, 390);
  const zip = path.join(work, 'endpoint-recipient.zip');
  await receive(page, '#bundle', zip);
  execFileSync('python3', ['-c',
    "import subprocess,sys,tempfile,zipfile; t=tempfile.TemporaryDirectory(); zipfile.ZipFile(sys.argv[1]).extractall(t.name); subprocess.run([sys.executable,'-B','endpoint_lab/replay_delivery.py'],cwd=t.name,check=True)", zip]);
}

module.exports = {qualifyEndpointDecision};
