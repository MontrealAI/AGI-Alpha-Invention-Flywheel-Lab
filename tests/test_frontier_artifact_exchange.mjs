import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash, webcrypto} from 'node:crypto';
import {File} from 'node:buffer';
import {readMissionArtifact, inspectReturnedWork} from '../docs/research/frontier-omega-alpha/frontier-artifact-exchange.mjs';
import {createMission, reviseMission, addMissionArtifacts, removeMissionArtifact, exportMission, importMission} from '../docs/research/frontier-omega-alpha/frontier-mission.mjs';
import {fingerprint} from '../docs/research/frontier-omega-alpha/outcome-receipt.mjs';
import {reviewClaim} from '../docs/research/frontier-omega-alpha/dpp-source-review.mjs';

globalThis.crypto ??= webcrypto;

test('a claimed assistant file and an inline example are distinct from file possession', () => {
  const work = '[Get code](sandbox:/mnt/data/check%20tool.py)\n\n```python\nraise RuntimeError()\n```';
  assert.deepEqual(inspectReturnedWork(work), {missing:['check tool.py'], sourceSnippet:true});
  assert.deepEqual(inspectReturnedWork(work, [{name:'check tool.py'}]), {missing:[], sourceSnippet:true});
  assert.deepEqual(inspectReturnedWork('[file](sandbox:/mnt/data/..%2fprivate.py)'), {missing:[], sourceSnippet:false});
  assert.deepEqual(inspectReturnedWork('[file](sandbox:/mnt/data/analysis/run.py).').missing, ['run.py']);
  assert.deepEqual(inspectReturnedWork('https://example.org/mnt/data/remote.py').missing, []);
});

test('working source preserves exact UTF-8 bytes across revision and checkpoint without evaluating it', async () => {
  const bytes = Buffer.from('\ufeff# Test\r\nraise RuntimeError("source remains inert")\r\n');
  const file = await readMissionArtifact(new File([bytes], 'experiment.py'), 1);
  assert.equal(file.sha256, createHash('sha256').update(bytes).digest('hex'));
  assert.deepEqual(Buffer.from(file.content), bytes);
  const first = createMission('Check the candidate');
  const mission = reviseMission(addMissionArtifacts(first, [file, file]), 'Continue the source check');
  const checkpoint = await exportMission(mission);
  assert.equal(checkpoint.mission.workFiles.length, 1);
  const restored = await importMission(JSON.stringify(checkpoint));
  assert.equal(restored.workFiles[0].revision, 1);
  assert.deepEqual(Buffer.from(restored.workFiles[0].content), bytes);
  const tampered = structuredClone(checkpoint.mission);
  tampered.workFiles[0].content = tampered.workFiles[0].content.replace('Test', 'Fake');
  await assert.rejects(importMission({mission:tampered, sha256:await fingerprint(tampered)}), /MISSION_ARTIFACT/);
});

test('review intake rejects unsafe names, disallowed binaries, invalid UTF-8 and malformed structured data', async () => {
  for (const file of [
    new File(['echo'], '../run.py'), new File(['echo'], 'CON.txt'), new File(['x'], 'module.exe'),
    new File([Uint8Array.of(0xff)], 'tool.py'), new File(['{'], 'result.json'),
    new File(['{"nbformat":4}'], 'study.ipynb'),
  ]) await assert.rejects(readMissionArtifact(file, 1));
  assert.equal((await readMissionArtifact(new File(['{"nbformat":4,"cells":[]}'], 'study.ipynb'), 1)).kind, 'notebook');
});

test('removing one exact version permits corrected files to enter the same full mission', async () => {
  const versions = await Promise.all(Array.from({length:8}, (_,n) =>
    readMissionArtifact(new File([`Result version ${n}`], 'result.txt'), 1)));
  const full = addMissionArtifacts(createMission('Original goal'), versions);
  const updated = reviseMission(full, 'Recheck the result');
  const correction = await readMissionArtifact(new File(['Corrected result'], 'result.txt'), 2);
  assert.throws(() => addMissionArtifacts(updated, [correction]), /MISSION_ARTIFACT/);
  const continued = addMissionArtifacts(removeMissionArtifact(updated, versions[0]), [correction]);
  const reopened = await importMission(await exportMission(continued));
  assert.equal(reopened.originalAmbition, 'Original goal');
  assert.deepEqual(reopened.workFiles, [...versions.slice(1), correction]);
});

test('quantity checks reject exponents, tolerances and range suffixes as independent measurements', () => {
  const target = {model:'Example Pack',level:'system'};
  const review = (quote, value) => reviewClaim({
    id:'weight', target, field:'batteryWeight', claim:{value,unit:'kg'},
    sources:[{id:'datasheet',excerpt:quote,url:'https://example.org/data',locator:'table',sha256:'a'.repeat(64)}],
    observations:[{source:'datasheet',target,field:'batteryWeight',quote,value,unit:'kg'}],
  }).decision;
  assert.equal(review('Net battery weight: 6.4e1 kg.', 1), 'insufficient');
  assert.equal(review('Net battery weight: 6.4e+1 kg.', 1), 'insufficient');
  assert.equal(review('Net battery weight: 64 ± 2 kg.', 2), 'insufficient');
  assert.equal(review('Net battery weight: 64 ± 2 kg.', 64), 'supported');
  assert.equal(review('Net battery weight: 64 (±2) kg.', 64), 'supported');
  assert.equal(review('Net battery weight: 60 – 68 kg.', 68), 'insufficient');
  assert.equal(review('Net battery weight: 1/2 kg.', 2), 'insufficient');
  assert.equal(review('Net battery weight: 1 200 kg.', 200), 'insufficient');
  assert.equal(review('Net battery weights by column: 64 / 80 / 100 kg.', 80), 'supported');
});

test('compound dimensions are not field measurements, while same-unit table columns remain usable', () => {
  const target = {model:'Example Pack',level:'system'};
  const review = (quote, value, field = 'batteryWeight', unit = 'kg') => reviewClaim({
    id:'field-check',target,field,claim:{value,unit},
    sources:[{id:'table',excerpt:quote,url:'https://example.org/data',locator:'table',sha256:'f'.repeat(64)}],
    observations:[{source:'table',target,field,quote,value,unit}],
  }).decision;
  assert.equal(review('Specific capacity: 100 Ah/kg.',100,'batteryCapacity','Ah'), 'insufficient');
  assert.equal(review('Mass per unit energy: 10 kg/kWh.',10), 'insufficient');
  assert.equal(review('Mass per unit energy: 10 kg per kWh.',10), 'insufficient');
  assert.equal(review('Mass relationship: 10 kg·m⁻³.',10), 'insufficient');
  assert.equal(review('Experimental ratio: 100 Ah / 5 kg.',5), 'insufficient');
  assert.equal(review('Specified net weight: 1,200 kg.',1.2), 'insufficient');
  assert.equal(review('Table of weights: 72.2 kg / 68.5 kg.',72.2), 'supported');
  assert.equal(review('Table of weights: 72.2 kg / 68.5 kg.',68.5), 'supported');
});
