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
  const controller = new AbortController();
  const fixture = {create(options) {
    assert.equal(options.signal, controller.signal);
    assert.deepEqual(options.expectedOutputs, [{type: 'text', languages: ['fr']}]);
    options.monitor({addEventListener: (_, report) => report({loaded: 0.5})});
    return {
      prompt(messages, {signal}) {
        assert.equal(signal, controller.signal);
        assert.deepEqual(messages, [{role: 'user', content: ambition}]);
        return '  Travail proposé.  ';
      },
      destroy() { closed = true; },
    };
  }};
  const result = await runBrowserStarter({ambition, language: 'fr', signal: controller.signal,
    onProgress: value => progress.push(value)}, fixture);
  assert.equal(result, 'Travail proposé.');
  assert.deepEqual(progress, [0.5]);
  assert.equal(closed, true);
});

test('a late browser response cannot complete a canceled draft', async () => {
  const controller = new AbortController();
  let closed = false;
  const fixture = {create() { return {
    prompt() { controller.abort(); return 'late'; },
    destroy() { closed = true; },
  }; }};
  await assert.rejects(runBrowserStarter({ambition: 'Build a useful initial capability.', language: 'en',
    signal: controller.signal}, fixture), {name: 'AbortError'});
  assert.equal(closed, true);
});
