import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash, webcrypto} from 'node:crypto';
import {File} from 'node:buffer';
import {readMissionArtifact, inspectReturnedWork} from '../docs/research/frontier-omega-alpha/frontier-artifact-exchange.mjs';
import {createMission, reviseMission, addMissionArtifacts, exportMission, importMission} from '../docs/research/frontier-omega-alpha/frontier-mission.mjs';
import {fingerprint} from '../docs/research/frontier-omega-alpha/outcome-receipt.mjs';

globalThis.crypto ??= webcrypto;

test('a claimed assistant file and an inline example are distinct from file possession', () => {
  const work = '[Get code](sandbox:/mnt/data/check%20tool.py)\n\n```python\nraise RuntimeError()\n```';
  assert.deepEqual(inspectReturnedWork(work), {missing:['check tool.py'], sourceSnippet:true});
  assert.deepEqual(inspectReturnedWork(work, [{name:'check tool.py'}]), {missing:[], sourceSnippet:true});
  assert.deepEqual(inspectReturnedWork('[file](sandbox:/mnt/data/..%2fprivate.py)'), {missing:[], sourceSnippet:false});
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
