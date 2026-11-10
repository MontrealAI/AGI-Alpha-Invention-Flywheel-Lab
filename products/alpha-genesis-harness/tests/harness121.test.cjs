// SPDX-License-Identifier: Apache-2.0
// HARNESS121 exact frozen owner-safe regression: qualified against PR320 parent 74d8b5f.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const E = require('../app/engine.js');

function instrument(operation, args, inputs = ['x']) {
  return E.constructInstrument({name: 'Frozen precision witness', inputs, outputs: {answer: {op: operation, args}}});
}

test('HARNESS121: escaped 2.6M-character response cannot strand a saved workspace', () => {
  const project = E.createProject({title: 'Preserve customer work'});
  const before = E.exportProject(project);
  const response = '\\'.repeat(2600000);
  // Either a restorable export is accepted or import refuses without mutating existing work.
  let accepted = false;
  try {
    E.importResponse(project, response, {provider: 'manual'});
    accepted = true;
  } catch (error) {
    assert.match(String(error.message), /restorable|envelope|large|limit/i);
  }
  if (accepted) {
    const portable = E.exportProject(project);
    assert.ok(portable.length <= 5000000);
    assert.equal(E.importProject(portable).modelOutputs[0].text, response);
  } else {
    assert.equal(E.exportProject(project), before, 'Failed import must not mutate retained work.');
  }
});

test('HARNESS121: exact-integer accumulations reject an unsafe temporary before cancellation', () => {
  const x = Number.MAX_SAFE_INTEGER;
  const add = instrument('add', [{field: 'x'}, 2, -2]);
  assert.equal(E.executeInstrument(add, {x}).verdict, 'INVALID');
  const sum = instrument('sum', [{field: 'x'}]);
  assert.equal(E.executeInstrument(sum, {x: [x, 2, -2]}).verdict, 'INVALID');
  assert.equal(E.executeInstrument(add, {x: 12}).outputs.answer, 12);
  assert.equal(E.executeInstrument(sum, {x: [7, 3, -2]}).outputs.answer, 8);
  const product = instrument('mul', [{field: 'x'}, 2, 3]);
  assert.equal(E.executeInstrument(product, {x: 7}).outputs.answer, 42);
  assert.equal(E.executeInstrument(product, {x}).verdict, 'INVALID');
});

function renderExperimentInIsolatedDOM(project) {
  const source = fs.readFileSync(path.join(__dirname, '..', 'app', 'app.js'), 'utf8');
  const start = source.indexOf('  function renderExperiment(){');
  const end = source.indexOf('  function readInstrumentField(input){', start);
  assert.ok(start !== -1 && end > start, 'Real production renderer must be present.');
  const elements = new Map();
  const panels = new Map();
  function get(id) {
    if (!elements.has(id)) {
      const element = {
        value: '',
        classList: {
          classes: new Set(),
          toggle(name, enabled) { if (enabled) this.classes.add(name); else this.classes.delete(name); },
          contains(name) { return this.classes.has(name); }
        },
        closest(selector) {
          const key = id + ':' + selector;
          if (!panels.has(key)) panels.set(key, {
            classList: {
              classes: new Set(),
              toggle(name, enabled) { if (enabled) this.classes.add(name); else this.classes.delete(name); },
              contains(name) { return this.classes.has(name); }
            }
          });
          return panels.get(key);
        }
      };
      elements.set(id, element);
    }
    return elements.get(id);
  }
  let economicEditorCalls = 0, lastResultCalls = 0;
  const context = {
    project,
    $: get,
    json: value => JSON.stringify(value, null, 2),
    renderEconomicEditor: () => economicEditorCalls++,
    renderLastResult: () => lastResultCalls++,
    // All instrument-only functions deliberately absent: missing-instrument route
    // must never reference them.
  };
  vm.runInNewContext(source.slice(start, end) + '\nrenderExperiment()', context, {timeout: 500});
  return {elements, panels, economicEditorCalls, lastResultCalls, get};
}

test('HARNESS121: workflow-only proposals are visible and independently executable via the public editor', () => {
  const workflow = {name:'Intact workflow only',inputs:['source'],effects:[],budget:{maxOperations:100},steps:[],outputs:[]};
  const project = {workflow};
  const view = renderExperimentInIsolatedDOM(project);
  assert.equal(view.get('experiment-workspace').classList.contains('hidden'), false);
  assert.equal(view.get('instrument-spec').closest('.panel').classList.contains('hidden'), true);
  assert.equal(view.get('workflow-input').closest('details').classList.contains('hidden'), false);
  assert.equal(JSON.parse(view.get('workflow-input').value).name, workflow.name);
  assert.equal('instrumentSpec' in project, false, 'Do not fabricate an instrument as a hidden prerequisite.');
  assert.equal(view.lastResultCalls, 1);
});

test('HARNESS121: arrangement-only proposals expose cost and incentive checks without a calculator', () => {
  const arrangement = {currency: 'CAD', participants: [], costs: [], alternatives: []};
  const project = {arrangement};
  const view = renderExperimentInIsolatedDOM(project);
  assert.equal(view.get('experiment-workspace').classList.contains('hidden'), false);
  assert.equal(view.get('instrument-spec').closest('.panel').classList.contains('hidden'), true);
  assert.equal(view.get('workflow-input').closest('details').classList.contains('hidden'), true);
  assert.equal(JSON.parse(view.get('arrangement-input').value).currency, 'CAD');
  assert.equal(view.economicEditorCalls, 1);
  assert.equal('instrumentSpec' in project, false);
});
