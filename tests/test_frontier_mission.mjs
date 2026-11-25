import assert from 'node:assert/strict';
import test from 'node:test';

import {fingerprint} from '../docs/research/frontier-omega-alpha/outcome-receipt.mjs';
import {addMissionInstruction, setMissionDocuments} from '../docs/research/frontier-omega-alpha/frontier-mission.mjs';
import {createMissionRequest} from '../docs/research/frontier-omega-alpha/frontier-mission-router.mjs';
import {
  beginMission, bindMissionRequest, cancelMission, continueMission, createMission, exportMission, importMission, interruptMission,
  maxAmbitionBytes, maxMissionBytes, missionPacket, prepareMission, recordMission, reviseMission,
} from '../docs/research/frontier-omega-alpha/frontier-mission.mjs';

const exactAmbition = 'Build Frontier AI for Game Theory.';
const frenchAmbition = 'Étudier les archives d’un orgue et proposer une méthode de restitution.\n';
const report = {
  route: 'research', objective: 'Explain which historical sources constrain the reconstruction.',
  nextAction: 'Check the dates and provenance of each independent record.',
  progress: 'Identified a comparison and confirmed which sources can be inspected.',
  assumptions: ['The published editions are independent only after provenance review.'],
  constraints: ['Use original public records.'], capabilityIds: ['reference-check'],
  evidence: [{label: 'Catalogue record', url: 'https://example.test/archive', sha256: 'a'.repeat(64)}],
  artifacts: [{label: 'Reproduction notes', kind: 'plain text', content: 'Input → check → record'}],
};

test('conversation preserves the exact ambition and restores local documents without execution authority', async () => {
  const sources = [{name:'observations.csv',text:'station,valid\nTémiscamingue,yes\n'}];
  const followUp = '  Revoir les observations.\nCiter le tableau d’origine.  ';
  const original = setMissionDocuments(createMission(exactAmbition), sources);
  const waiting = prepareMission(original, {provider:'assisted'});
  const next = addMissionInstruction(waiting, followUp);
  assert.equal(missionPacket(next).instruction, followUp);
  assert.equal(next.ambition, exactAmbition);
  assert.equal(next.status, 'ready');
  assert.equal(next.request, null);
  assert.equal(missionPacket(next).documents, undefined);
  assert.deepEqual((await importMission(await exportMission(next))).documents, sources);
  assert.deepEqual(next.turns.map(turn => turn.instruction), [followUp]);
  assert.equal(missionPacket(reviseMission(next, frenchAmbition)).instruction, null);
  assert.throws(() => setMissionDocuments(next, [{name:'../private.csv',text:'ok'}]), /MISSION_DOCUMENTS/);
  assert.throws(() => setMissionDocuments(next, [...sources, ...sources]), /MISSION_DOCUMENTS/);
  assert.throws(() => addMissionInstruction(next, '🚀'.repeat(513)), /MISSION_INSTRUCTION/);
});

test('the exact ambition and long multilingual work are preserved independently of catalogue matches', () => {
  const mission = createMission(exactAmbition);
  assert.equal(mission.status, 'ready');
  assert.equal(mission.run, null);
  assert.equal(mission.originalAmbition, exactAmbition);
  assert.equal(missionPacket(mission).ambition, exactAmbition);
  const long = `  ${frenchAmbition.repeat(60)}Étape suivante : comparer les méthodes. 日本語. Ω ♾️  `;
  const initial = createMission(long, {language: 'fr'});
  assert.equal(initial.ambition, long);
  assert.equal(initial.language, 'fr');
  const revised = reviseMission(initial, frenchAmbition);
  assert.equal(revised.originalAmbition, long);
  assert.equal(revised.revision, 2);
  assert.deepEqual(revised.revisions.map(entry => entry.ambition), [long, frenchAmbition]);
  assert.throws(() => createMission('é'.repeat(maxAmbitionBytes)), /MISSION_AMBITION/);
  assert.throws(() => createMission('   \n'), /MISSION_AMBITION/);
  assert.throws(() => createMission('New scope\0hidden'), /MISSION_AMBITION/);
});

test('waiting needs a real selected run or an assisted submission before it records work', () => {
  const initial = createMission(exactAmbition);
  const waiting = prepareMission(initial);
  assert.equal(waiting.status, 'waiting');
  assert.equal(waiting.run.provider, null);
  assert.equal(waiting.run.startedAt, null);
  assert.equal(prepareMission(waiting), waiting);
  assert.equal(recordMission(waiting, waiting.run.id, report), waiting);
  assert.throws(() => beginMission(waiting), /MISSION_ROUTE/);
  const assisted = prepareMission(waiting, {provider: 'assisted'});
  assert.equal(assisted.run.startedAt, null);
  const reviewed = recordMission(assisted, assisted.run.id, report);
  assert.equal(reviewed.status, 'review');
  assert.equal(reviewed.reports[0].provider, 'assisted');
  assert.equal(reviewed.reports[0].revision, 1);
  assert.equal(reviewed.reports[0].route, 'research');
  assert.equal(reviewed.reports[0].nextAction, report.nextAction);
  assert.equal(reviewed.run.startedAt, null);
  assert.equal(recordMission(reviewed, assisted.run.id, report), reviewed);
  assert.equal(missionPacket(reviewed).previousReport.progress, report.progress);
  assert.ok(Object.isFrozen(reviewed.reports[0].artifacts[0]));
});

test('canceled, superseded, and unrelated operations cannot overwrite a mission', () => {
  const initial = createMission(exactAmbition);
  const running = beginMission(initial, {route: 'invention', provider: 'local', model: 'local-test'});
  assert.equal(beginMission(running, {provider: 'deterministic'}), running);
  const revised = reviseMission(running, 'Build a reference-bound adaptive comparison for unfamiliar tasks.');
  const next = beginMission(revised, {provider: 'local'});
  assert.equal(next.revision, 2);
  assert.equal(recordMission(next, running.run.id, report), next);
  const other = beginMission(createMission('Investigate a method to measure old ironwork.'), {provider: 'local'});
  assert.equal(recordMission(other, next.run.id, report), other);
  assert.equal(interruptMission(other, next.run.id, 'stale callback'), other);
  const canceled = cancelMission(next, 'Member stopped the first comparison.');
  assert.equal(canceled.status, 'canceled');
  assert.equal(cancelMission(canceled), canceled);
  assert.equal(beginMission(canceled, {provider: 'local'}), canceled);
  assert.equal(recordMission(canceled, next.run.id, report), canceled);
  const resumed = beginMission(continueMission(canceled), {provider: 'local'});
  assert.notEqual(resumed.run.id, canceled.run.id);
  assert.equal(resumed.originalAmbition, exactAmbition);
  assert.equal(resumed.incidents[0].reason, 'Member stopped the first comparison.');
});

test('explicit checkpoints restore exact text and pause an interrupted request without executing it', async () => {
  const initial = createMission(frenchAmbition, {language: 'fr'});
  const waiting = prepareMission(initial, {provider: 'assisted'});
  const pausedHandoff = interruptMission(waiting, waiting.run.id, 'Pause before sharing.');
  assert.equal(pausedHandoff.status, 'paused');
  assert.equal(recordMission(pausedHandoff, waiting.run.id, report), pausedHandoff);
  assert.deepEqual(await importMission(await exportMission(pausedHandoff)), pausedHandoff);
  const assisted = prepareMission(continueMission(pausedHandoff), {provider: 'assisted'});
  assert.notEqual(assisted.run.id, waiting.run.id);
  const reviewed = recordMission(assisted, assisted.run.id, report);
  const revised = reviseMission(reviewed, 'Construire un témoin portable et réexécutable.');
  const running = beginMission(revised, {route: 'adaptation', provider: 'local', model: 'owner-local-test'});
  const file = await exportMission(running);
  const restored = await importMission(JSON.stringify(file, null, 2));
  assert.equal(restored.status, 'paused');
  assert.equal(restored.run.id, running.run.id);
  assert.equal(restored.incidents.at(-1).reason, 'checkpoint-restored');
  assert.deepEqual(restored.revisions, running.revisions);
  assert.deepEqual(restored.reports, running.reports);
  assert.equal(restored.originalAmbition, frenchAmbition);
  assert.equal(recordMission(restored, running.run.id, report), restored);
  const retry = beginMission(continueMission(restored), {provider: 'deterministic'});
  assert.notEqual(retry.run.id, running.run.id);
  assert.deepEqual(await importMission(await exportMission(restored)), restored);
});

test('serialized input rejects altered, oversized and authority-bearing records', async () => {
  const initial = createMission(exactAmbition);
  const running = beginMission(initial, {provider: 'local'});
  assert.throws(() => recordMission(running, running.run.id, {...report, independentlyVerified: true}), /MISSION_REPORT/);
  assert.throws(() => recordMission(running, running.run.id, {
    ...report, artifacts: [{label: 'Unexpected link', url: 'javascript:alert(1)'}],
  }), /MISSION_REPORT/);
  assert.throws(() => recordMission(running, running.run.id, {
    ...report, evidence: [{label: 'Unexpected origin', url: '//example.test/item'}],
  }), /MISSION_REPORT/);
  const file = await exportMission(initial);
  const tampered = structuredClone(file);
  tampered.mission.language = 'fr';
  await assert.rejects(importMission(tampered), /MISSION_DIGEST/);
  const unsupported = {...file.mission, credentials: {token: 'should never be persisted'}};
  await assert.rejects(importMission({mission: unsupported, sha256: await fingerprint(unsupported)}), /MISSION_INVALID/);
  await assert.rejects(importMission('{"mission":'), /MISSION_FILE/);
  await assert.rejects(importMission(' '.repeat(maxMissionBytes + 1)), /MISSION_SIZE/);
});

test('an authorized local checkpoint retains the exact prepared handoff and its return binding', async () => {
  const waiting = prepareMission(createMission(frenchAmbition, {language: 'fr'}), {provider: 'assisted'});
  const {missionId, revision, language, ambition, originalAmbition} = missionPacket(waiting);
  const request = await createMissionRequest({missionId, revision, language, ambition, originalAmbition,
    context: ['Use the versioned public sheet that the member provided.'],
    capabilities: [{id: 'reference-check', title: 'Reference check', scope: 'Compare authorized records.'}]});
  const bound = await bindMissionRequest(waiting, waiting.run.id, request);
  assert.equal(await bindMissionRequest(bound, waiting.run.id, request), bound);
  const saved = await exportMission(bound);
  const restored = await importMission(JSON.stringify(saved));
  assert.equal(restored.status, 'waiting');
  assert.equal(restored.run.id, waiting.run.id);
  assert.equal(restored.run.startedAt, null);
  assert.deepEqual(restored.request, request);
  assert.equal(recordMission(restored, restored.run.id, report).status, 'review');
  assert.equal(reviseMission(restored, 'Nouvelle ambition.').request, null);
  await assert.rejects(bindMissionRequest(waiting, waiting.run.id, {...request, endpoint: 'https://example.test'}), /MISSION_REQUEST/);
  const altered = structuredClone(saved.mission);
  altered.request.context[0] = 'Unbound data substituted after export.';
  await assert.rejects(importMission({mission: altered, sha256: await fingerprint(altered)}), /MISSION_REQUEST/);
});
