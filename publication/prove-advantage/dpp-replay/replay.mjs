import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import {reviewBatterySources} from '../../../docs/research/frontier-omega-alpha/dpp-source-review.mjs';

const read = async name => JSON.parse(await readFile(new URL(name, import.meta.url), 'utf8'));
const decisions = rows => rows.map(({id, decision, evidence}) => ({id, decision, evidence}));
const outcomes = [];
for (const stage of ['PRIMARY', 'ADVERSE', 'CONFIRMATION']) {
  const packet = await read(stage + '-OBSERVATIONS.json');
  const frozen = decisions(await read(stage + '-PREDICTIONS.json'));
  assert.deepEqual(decisions(reviewBatterySources(packet).results), frozen);
  const result = {stage,cases:frozen.length,decisionsAndEvidenceReproduced:true};
  if (stage !== 'CONFIRMATION') {
    for (const row of packet.cases) for (const observation of row.observations) observation.target = row.target;
    const withdrawn = decisions(reviewBatterySources(packet).results);
    const original = decisions(await read(stage + '-WITHDRAWAL.json'));
    const changes = withdrawn.filter((row, index) => JSON.stringify(row) !== JSON.stringify(original[index]));
    assert.deepEqual(changes, stage === 'PRIMARY' ? [
      {id:'batt-12',decision:'supported',evidence:['b1']},
      {id:'batt-16',decision:'contradicted',evidence:['b1']},
    ] :
      [{id:'control-2',decision:'contradicted',evidence:['sim-2']}]);
    result.withdrawalChanges = changes;
  }
  outcomes.push(result);
}
console.log(JSON.stringify(outcomes, null, 2));
