import assert from 'node:assert/strict';
import test from 'node:test';
import {screen} from '../docs/research/frontier-omega-alpha/endpoint-screen.mjs';
import {fingerprint, freezeScreen, outcome, verifyOutcome} from '../docs/research/frontier-omega-alpha/outcome-receipt.mjs';
import {rankOpportunities, readSavedGoal, reviewSaved} from '../docs/research/frontier-omega-alpha/frontier-goals.mjs';

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

const records = [
  {id:'forecast', title:'Historical NOAA forecasts', subject:'Recover a native grid point', outcome:'archive',
    tool:'archive', observed:'2026-11-20', state:'verified', version:'a'.repeat(40), review:'e'.repeat(64)},
  {id:'endpoint', title:'Choose a tested operational Endpoint load', subject:'Scope-limited latency checks',
    outcome:'screening', tool:'endpoint', observed:'2026-11-20', state:'abstain', version:'b'.repeat(40), review:'f'.repeat(64)},
  {id:'new', title:'Unproven method for forecasts', subject:'An author-reported test', outcome:'evidence',
    observed:'2026-11-23', state:'discovered', version:'2611.20000v2', review:'d'.repeat(64)},
];

test('goal matches prefer applicable evidence, pass through operating scope and abstain on unrelated goals', () => {
  const match = goal => rankOpportunities(records, goal)[0];
  assert.equal(match({text:'retrouver une prévision historique NOAA'}).record.id, 'forecast');
  assert.equal(match({text:'retrouver une prévision historique NOAA sans installation'}).action, 'review');
  assert.equal(match({text:'check endpoint latency on real traffic'}).action, 'review');
  assert.equal(match({preset:'endpoint'}).action, 'demo');
  assert.equal(match({text:'research 2611.20000v2'}).record.id, 'new');
  assert.equal(match({text:'research 2611.20000v1'}), undefined);
  assert.equal(match({text:'tune a harmonica reed with beeswax'}), undefined);
});

test('a saved goal reports a corrected same-version decision and rejects unsupported file fields', () => {
  const {id, version, review} = records[0];
  const envelope = {schema:'frontier/saved-goal-v1', goal:{preset:'archive'}, pin:{id, version, review}};
  const saved = readSavedGoal(envelope);
  assert.equal(reviewSaved(saved.pin, records[0]), 'current');
  assert.equal(reviewSaved(saved.pin, {...records[0], review:'a'.repeat(64)}), 'revised');
  assert.equal(reviewSaved(saved.pin, records[1]), 'missing');
  assert.equal(reviewSaved(saved.pin, undefined), 'missing');
  assert.throws(() => readSavedGoal({...envelope, goal:{preset:'bogus'}}), /INVALID_GOAL/);
  assert.throws(() => readSavedGoal({...envelope, goal:{text:'a'.repeat(201)}}), /INVALID_GOAL/);
  assert.throws(() => readSavedGoal({...envelope, wallet:'internal'}), /INVALID_GOAL/);
});

test('double flywheel independently compares exact measured answers and applies both resource gates', async () => {
  const {runDoubleFlywheel,CASES,COST}=await import('../docs/research/frontier-omega-alpha/double-flywheel.mjs');
  const run=runDoubleFlywheel();
  assert.deepEqual(run.checks, CASES.first.map(([r,o,t])=>r-o>t));
  assert.deepEqual(run.next, CASES.next.map(([r,o,s,t])=>(r-o)/s>t));
  assert.deepEqual(run.next,run.fresh);
  assert.equal(run.receipts-run.cost1,run.surplus);
  assert.equal(run.retainedSurplus+run.reinvestment,run.surplus);
  assert.equal(run.budget2,COST.nextBase+run.reinvestment);
  assert.ok(COST.nextBase<run.retainedCost && run.retainedCost<=run.budget2 && run.budget2<run.freshCost);
  assert.equal(run.freshEligible,false);
  assert.equal(run.retainedEligible,true);
  assert.equal(run.retainedBudgetRemaining,3);

  const failure=runDoubleFlywheel({rejectFirst:true});
  assert.notDeepEqual(failure.checks,run.checks);
  assert.equal(failure.acceptedFirst,false);
  assert.equal(failure.receipts,0);
  assert.equal(failure.reinvestment,0);
  assert.equal(failure.budget2,COST.nextBase);
  assert.equal(failure.next,null);
  assert.equal(failure.retainedEligible,false);
  assert.equal(failure.retainedBudgetRemaining,null);
});
