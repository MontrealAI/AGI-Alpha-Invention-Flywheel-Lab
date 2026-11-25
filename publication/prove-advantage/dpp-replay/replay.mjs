import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {reviewBatterySources} from '../../../docs/research/frontier-omega-alpha/dpp-source-review.mjs';

const read = async name => JSON.parse(await readFile(new URL(name, import.meta.url), 'utf8'));
const decisions = rows => rows.map(({id, decision, evidence}) => ({id, decision, evidence}));
const differences = (actual, frozen) => actual.filter((row, index) => JSON.stringify(row) !== JSON.stringify(frozen[index]));

async function reviewedPrimary(packet) {
  const labels = await read('PRIMARY-COLUMN-LABELS.json');
  const projected = structuredClone(packet);
  for (const [id, sourceId] of Object.entries(labels.case_source)) {
    const row = projected.cases.find(item => item.id === id);
    const source = row.sources.find(item => item.id === sourceId);
    assert.equal(source.locator, labels.source_locator);
    assert.ok(source.excerpt.includes(labels.original_clause));
    for (const observation of row.observations.filter(item => item.source === sourceId)) {
      assert.equal(observation.quote, source.excerpt);
      observation.quote = observation.quote.replace(labels.original_clause, labels.reviewed_clause);
    }
    source.excerpt = source.excerpt.replace(labels.original_clause, labels.reviewed_clause);
  }
  return projected;
}

if (process.argv[2] === '--reviewed-primary') {
  console.log(JSON.stringify(await reviewedPrimary(await read('PRIMARY-OBSERVATIONS.json')), null, 2));
  process.exit(0);
}

const outcomes = [];
for (const stage of ['PRIMARY', 'ADVERSE', 'CONFIRMATION']) {
  const originalPacket = await read(stage + '-OBSERVATIONS.json');
  const frozen = decisions(await read(stage + '-PREDICTIONS.json'));
  const originalChanges = differences(decisions(reviewBatterySources(originalPacket).results), frozen);
  assert.deepEqual(originalChanges, stage === 'PRIMARY' ? [
    {id:'batt-02',decision:'insufficient',evidence:[]},
    {id:'batt-05',decision:'insufficient',evidence:[]},
  ] : []);
  const packet = stage === 'PRIMARY' ? await reviewedPrimary(originalPacket) : originalPacket;
  assert.deepEqual(decisions(reviewBatterySources(packet).results), frozen);
  const result = {stage,cases:frozen.length,originalChanges,decisionsAndEvidenceReproduced:true};
  if (stage !== 'CONFIRMATION') {
    for (const row of packet.cases) for (const observation of row.observations) observation.target = row.target;
    const withdrawn = decisions(reviewBatterySources(packet).results);
    const original = decisions(await read(stage + '-WITHDRAWAL.json'));
    const changes = differences(withdrawn, original);
    assert.deepEqual(changes, stage === 'PRIMARY' ? [
      {id:'batt-10',decision:'contradicted',evidence:['b1']},
      {id:'batt-11',decision:'insufficient',evidence:[]},
      {id:'batt-12',decision:'insufficient',evidence:[]},
      {id:'batt-13',decision:'contradicted',evidence:['b2']},
      {id:'batt-16',decision:'insufficient',evidence:[]},
    ] :
      [{id:'control-2',decision:'contradicted',evidence:['sim-2']}]);
    result.withdrawalChanges = changes;
  }
  outcomes.push(result);
}
console.log(JSON.stringify(outcomes, null, 2));
