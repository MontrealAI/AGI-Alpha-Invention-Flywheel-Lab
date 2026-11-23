import assert from 'node:assert/strict';
import test from 'node:test';
import {screen} from '../docs/research/frontier-omega-alpha/endpoint-screen.mjs';
import {fingerprint, freezeScreen, outcome, verifyOutcome} from '../docs/research/frontier-omega-alpha/outcome-receipt.mjs';

const input = {
  schema:'frontier/endpoint-screen-v1', source:'example local authorized data',
  scope:{model:'example', workload:'example', system:'example'},
  cutoff:'2026-11-23', minimum_tokens_per_s:'100', maximum_p90_ttft_ms:'500.000000000000000000000001',
  rows:[
    {id:'a', published:'2026-11-23', load:1, tokens_per_s:'100', p90_ttft_ms:'500.000000000000000000000001'},
    {id:'b', published:'2026-11-23', load:2, tokens_per_s:'101', p90_ttft_ms:'500.000000000000000000000002'},
    {id:'c', published:'2026-11-24', load:4, tokens_per_s:'110', p90_ttft_ms:'400'},
  ],
};
const tool = {version:'1.0.0', sha256:'c'.repeat(64)};
const publicSample = {input_sha256:'a'.repeat(64), result_sha256:'b'.repeat(64)};

test('decimal edges, untested points, abstention and incomplete measurements', () => {
  assert.deepEqual(screen(input).rows.map(row => row.disposition), ['qualified','above-ceiling','not-yet-documented']);
  assert.equal(screen(input).highest_tested_load, 1);
  assert.equal(screen(input).operating_adoption, 'ABSTAIN');
  const missing = structuredClone(input);
  missing.rows[0].p90_ttft_ms = null;
  assert.equal(screen(missing).screening, 'ABSTAIN');
  assert.equal(screen(missing).rows[0].disposition, 'missing-measurement');
  const ambiguous = structuredClone(input);
  ambiguous.rows[1].load = 1;
  assert.throws(() => screen(ambiguous), /AMBIGUOUS_ROW/);
  assert.throws(() => screen({...input, cutoff:'2026-02-30'}), /CUTOFF/);
});

test('local receipt requires consent, excludes identifiers and downgrades self-reported result', async () => {
  const plan = await freezeScreen(input, tool, publicSample);
  const result = screen(input);
  await assert.rejects(outcome(plan, result, 1.2, publicSample, false), /EXPORT_CONSENT/);
  const envelope = await outcome(plan, result, 1.2, publicSample, true);
  assert.equal(envelope.receipt.plan.classification, 'local-self-reported');
  assert.equal(envelope.receipt.recorded_highest_load, null);
  assert.equal(envelope.receipt.complete_cost, null);
  assert.equal(envelope.receipt.is_operational_approval, false);
  assert.equal(await verifyOutcome(envelope), true);
  const changed = structuredClone(envelope);
  changed.receipt.elapsed_ms = 25;
  assert.equal(await verifyOutcome(changed), false);
  assert.ok(!JSON.stringify(envelope).includes(input.source));
  assert.ok(!JSON.stringify(envelope).includes('wallet'));
});

test('a controlled receipt binds a frozen independent reference and forbids promotion', async () => {
  const result = screen(input);
  const reference = {input_sha256:await fingerprint(input), result_sha256:await fingerprint(result)};
  const plan = await freezeScreen(input, tool, reference);
  const item = await outcome(plan, result, 1, reference, true);
  assert.equal(item.receipt.comparator_result_sha256, reference.result_sha256);
  assert.equal(item.receipt.verification, 'matched-frozen-independent-sqlite-reference');
  assert.equal(await verifyOutcome(item), true);
  await assert.rejects(outcome(plan, {...result, highest_tested_load:2}, 1, reference, true), /REFERENCE_MISMATCH/);
  const contaminated = structuredClone(item);
  contaminated.receipt.plan.source = 'private-export';
  contaminated.receipt.plan_sha256 = await fingerprint(contaminated.receipt.plan);
  contaminated.sha256 = await fingerprint(contaminated.receipt);
  assert.equal(await verifyOutcome(contaminated), false);
});
