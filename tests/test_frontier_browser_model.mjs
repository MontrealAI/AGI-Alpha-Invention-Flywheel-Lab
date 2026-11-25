import assert from 'node:assert/strict';
import test from 'node:test';
import {browserModelAvailability, runBrowserStarter} from '../docs/research/frontier-omega-alpha/frontier-browser-model.mjs';

test('reports browser availability per language without creating a session', async () => {
  const fixture = {
    availability({expectedInputs}) { return expectedInputs[0].languages[0] === 'fr' ? 'downloadable' : 'available'; },
    create() { throw new Error('Availability cannot download a model'); },
  };
  assert.equal(await browserModelAvailability('fr', fixture), 'downloadable');
  assert.equal(await browserModelAvailability('en', fixture), 'available');
  assert.equal(await browserModelAvailability('de', fixture), 'unavailable');
  assert.equal(await browserModelAvailability('en', {}), 'unavailable');
  fixture.availability = () => { throw new Error('Unsupported browser'); };
  assert.equal(await browserModelAvailability('en', fixture), 'unavailable');
});

test('forwards the exact ambition to the selected browser runtime and releases the session', async () => {
  const ambition = '  Concevoir un outil inédit.\nPréserver ces précisions.  ';
  const progress = [];
  let closed = false;
  let calls = 0;
  let ready = false;
  const controller = new AbortController();
  const fixture = {create(options) {
    assert.equal(options.signal, controller.signal);
    assert.deepEqual(options.expectedOutputs, [{type: 'text', languages: ['fr']}]);
    options.monitor({addEventListener: (_, report) => report({loaded: 0.5})});
    return {
      prompt(messages, {signal}) {
        assert.equal(signal, controller.signal);
        if (calls++ === 0) return messages[0].content.match(/F-[a-f0-9]{8}/u)[0];
        assert.equal(ready, true);
        assert.deepEqual(messages, [{role: 'user', content: ambition}]);
        return '  Travail proposé.  ';
      },
      destroy() { closed = true; },
    };
  }};
  const result = await runBrowserStarter({ambition, language: 'fr', signal: controller.signal,
    onProgress: value => progress.push(value), onReady() { ready = true; }}, fixture);
  assert.equal(result, 'Travail proposé.');
  assert.deepEqual(progress, [0.5]);
  assert.equal(closed, true);
  assert.equal(calls, 2);
});

test('fails closed on a Chromium echo before sending the member ambition', async () => {
  let calls = 0;
  let closed = false;
  const fixture = {create() { return {
    prompt(messages) { calls++; return `On-device model is not available in Chromium. ${messages[0].content}`; },
    destroy() { closed = true; },
  }; }};
  await assert.rejects(runBrowserStarter({ambition: 'Invent a useful instrument.', language: 'en'}, fixture),
    {message: 'BROWSER_MODEL_UNVERIFIED'});
  assert.equal(calls, 1);
  assert.equal(closed, true);
});

test('a late browser response cannot complete a canceled draft', async () => {
  const controller = new AbortController();
  let closed = false;
  let calls = 0;
  const fixture = {create() { return {
    prompt(messages) {
      if (calls++ === 0) return messages[0].content.match(/F-[a-f0-9]{8}/u)[0];
      controller.abort();
      return 'late';
    },
    destroy() { closed = true; },
  }; }};
  await assert.rejects(runBrowserStarter({ambition: 'Build a useful initial capability.', language: 'en',
    signal: controller.signal}, fixture), {name: 'AbortError'});
  assert.equal(closed, true);
});
