import test from 'node:test';
import assert from 'node:assert/strict';
import {createAssistedBrief, maximumReturnedBytes, readAssistedReply, workPreview} from '../docs/research/frontier-omega-alpha/frontier-assisted-work.mjs';
import {createMissionRequest, missionRouteResult} from '../docs/research/frontier-omega-alpha/frontier-mission-router.mjs';

const originalAmbition = 'Capture the exponential of AI progrees.';
const draftWork = '## Candidate mechanism\n\nCompare 20 opportunities to the same documented baseline.';

async function preparedMission(changes = {}) {
  return createMissionRequest({missionId:'handback-check', revision:1, language:'en', ambition:originalAmbition,
    ...changes});
}

function structured(request, changes = {}) {
  return {schema:missionRouteResult, requestId:request.requestId, route:'research', objective:'Compare prior claims',
    nextAction:'Run the same documented cases', work:draftWork, assumptions:[], capabilityIds:[], ...changes};
}

test('ordinary brief preserves verbatim ambition and reviews selected context without transport syntax', async () => {
  const request = await preparedMission({language:'fr', revision:2, ambition:'Vérifier la meilleure piste.\nComparer le coût.', originalAmbition});
  const brief = createAssistedBrief(request, ['Piste 2 à vérifier\nComparer 20 pistes avec une méthode de référence.'], true);
  assert.ok(brief.includes('Poursuivez à partir du travail ci-dessous.'));
  assert.ok(brief.includes(request.ambition));
  assert.ok(brief.includes(originalAmbition));
  assert.ok(brief.includes('Piste 2 à vérifier'));
  assert.ok(!brief.includes('requestId'));
  assert.ok(!brief.includes(request.requestId));
});

test('pasted Markdown and code are retained as exact original text plus a reading view', async () => {
  const request = await preparedMission();
  const raw = '## Candidate\n\n- Evidence &amp; limits\n\n| Claim | Test |\n| --- | --- |\n| A | B |\n\n```js\nconsole.log("\\n");\n```';
  const result = await readAssistedReply(raw, request);
  assert.equal(result.kind, 'general');
  assert.equal(result.raw, raw);
  assert.match(result.work, /Evidence & limits/u);
  assert.match(result.work, /console\.log\("\\n"\)/u);
  assert.equal(Object.hasOwn(result, 'receipt'), false);
});

test('broken copied result with prose, smart quotes, HTML escapes and backslashes recovers useful content', async () => {
  const request = await preparedMission();
  const raw = 'My answer\n\n```json\n{\n  “schema”: “frontier/mission-route-result-v1”,\n  “requestId”: “copied from an earlier run”,\n'
    + '  “work”: “## Candidate\\n\\nA &amp; B&#x20;\\n| Method | Evidence |\\n| --- | --- |\\n| 1 | 2 |”,\n\n```';
  const wrapped = JSON.stringify({text:raw});
  const result = await readAssistedReply(wrapped, request);
  assert.equal(result.kind, 'unmatched');
  assert.equal(result.raw, wrapped);
  assert.equal(result.work, '## Candidate\n\nA & B\n| Method | Evidence |\n| --- | --- |\n| 1 | 2 |');
  assert.equal(Object.hasOwn(result, 'receipt'), false);

  const ordinary = 'Compare the methods. \\\n\\\n&#x20;Candidate &ldquo;A&rdquo; &rarr; B\n&lt;img onerror=alert(1)&gt;';
  const general = await readAssistedReply(ordinary, request);
  assert.equal(general.kind, 'general');
  assert.equal(general.raw, ordinary);
  assert.equal(general.work, 'Compare the methods.\n\n Candidate “A” → B\n<img onerror=alert(1)>');
});

test('valid fenced or wrapped responses remain request-bound assisted drafts', async () => {
  const request = await preparedMission();
  const body = JSON.stringify(structured(request));
  const formats = [body, `Here is my response:\n\n\x60\x60\x60json\n${body}\n\x60\x60\x60\n\nPlease review.`,
    JSON.stringify({text:body}), body.replaceAll('"', '&quot;')];
  for (const raw of formats) {
    const result = await readAssistedReply(raw, request);
    assert.equal(result.kind, 'structured');
    assert.equal(result.raw, raw);
    assert.equal(result.work, draftWork);
    assert.equal(result.receipt.requestId, request.requestId);
    assert.equal(result.receipt.revision, 1);
    assert.equal(result.receipt.intelligence.mode, 'manual');
    assert.equal(result.receipt.verification, 'unverified');
    assert.equal(result.receipt.isOperationalApproval, false);
  }
});

test('fenced one-field clipboard wrapper retains readable work and the current request binding', async () => {
  const request = await preparedMission();
  const correct = structured(request);
  const wrapper = result => `\x60\x60\x60json\n${JSON.stringify({text:JSON.stringify(result)})}\n\x60\x60\x60`;
  for (const raw of [wrapper(correct), wrapper({...correct, requestId:'1'.repeat(64)})]) {
    const result = await readAssistedReply(raw, request);
    assert.equal(result.raw, raw);
    assert.equal(result.work, draftWork);
    if (raw === wrapper(correct)) {
      assert.equal(result.kind, 'structured');
      assert.equal(result.receipt.requestId, request.requestId);
      assert.equal(result.receipt.isOperationalApproval, false);
    } else {
      assert.equal(result.kind, 'unmatched');
      assert.equal(Object.hasOwn(result, 'receipt'), false);
    }
  }
});

test('other revisions and tampered receipts can only offer general recovery', async () => {
  const request = await preparedMission({revision:2});
  const previous = await preparedMission();
  const correct = JSON.stringify(structured(request));
  const invalid = [JSON.stringify(structured(previous)),
    JSON.stringify(structured(request, {verification:'accepted', isOperationalApproval:true})),
    correct.replace('{', '{"\\u0072equestId":"unrelated",'),
    correct.slice(0, -1),
    `\x60\x60\x60json\n${correct}\n\x60\x60\x60\n\n\x60\x60\x60json\n${JSON.stringify(structured(previous))}\n\x60\x60\x60`];
  for (const raw of invalid) {
    const result = await readAssistedReply(raw, request);
    assert.equal(result.kind, 'unmatched');
    assert.equal(result.work, draftWork);
    assert.equal(result.raw, raw);
    assert.equal(Object.hasOwn(result, 'receipt'), false);
  }
});

test('UTF-8 bounds are enforced before parsing and previews do not cut a Unicode character', async () => {
  const request = await preparedMission();
  const raw = '🌓'.repeat(maximumReturnedBytes / 4);
  const result = await readAssistedReply(raw, request);
  assert.equal(result.raw, raw);
  const preview = workPreview(result.work);
  assert.match(preview, /\n…$/u);
  assert.ok(!preview.includes('�'));
  assert.ok(new TextEncoder().encode(preview).length <= 12 * 1024);
  await assert.rejects(readAssistedReply(raw + 'x', request), /ASSISTED_TEXT/u);
  await assert.rejects(readAssistedReply('unsafe\u0000control', request), /ASSISTED_TEXT/u);
});
