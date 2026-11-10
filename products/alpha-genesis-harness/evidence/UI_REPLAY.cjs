/* SPDX-License-Identifier: Apache-2.0; Copyright 2026 Vincent Boucher.
 * DOM-emulation regression, not a rendered-browser or operating-system test.
 * Requires jsdom 26.1.0 in NODE_PATH (development only; never bundled).
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { JSDOM, VirtualConsole } = require('jsdom');
const root = path.resolve(__dirname, '..');
const key = 'alpha-genesis-harness-project-v1';
const pause = () => new Promise(r => setTimeout(r, 30));

function boot(saved) {
  const errors = [], downloads = [];
  const console = new VirtualConsole();
  console.on('jsdomError', e => errors.push(e.message));
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'app/index.html'), 'utf8'), { url: 'https://harness-test.invalid/', runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole: console });
  const w = dom.window;
  w.scrollTo = () => {};
  w.HTMLElement.prototype.scrollIntoView = () => {};
  w.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  w.HTMLDialogElement.prototype.close = function () { this.open = false; };
  w.HTMLAnchorElement.prototype.click = function () {};
  w.fetch = async () => { throw new Error('No network in DOM test'); };
  w.Blob = class { constructor(parts, options) { this.parts = parts; this.options = options; } };
  w.URL.createObjectURL = blob => { downloads.push(blob); return 'blob:test-' + downloads.length; };
  w.URL.revokeObjectURL = () => {};
  Object.defineProperty(w.navigator, 'clipboard', { value: { writeText: async () => {} } });
  if (saved) w.localStorage.setItem(key, saved);
  for (const name of ['engine.js', 'app.js']) w.eval(fs.readFileSync(path.join(root, 'app', name), 'utf8'));
  const click = id => { const n = w.document.getElementById(id); assert.ok(n, id); n.click(); };
  const fill = (id, value) => { const n = w.document.getElementById(id); assert.ok(n, id); n.value = value; n.dispatchEvent(new w.Event('input', { bubbles: true })); };
  return { w, click, fill, errors, downloads, dom };
}

(async () => {
  let t = boot();
  t.fill('mission-name', 'Independent DOM mission');
  t.fill('mission-objective', 'Calculate a source-bound result for a new instrument');
  t.click('save-project'); await pause();
  assert.equal(JSON.parse(t.w.localStorage.getItem(key)).title, 'Independent DOM mission', 'Toolbar Save must capture unsent mission edits');
  t.click('export-project'); await pause();
  assert.equal(JSON.parse(t.downloads.at(-1).parts.join('')).title, 'Independent DOM mission');
  const response = { summary: 'Model-proposed bounded instrument', opportunities: [{ title: 'A custom calibration route', hypothesis: 'Test the supplied linear relation', requiredCapabilities: [], evidenceIds: [], assumptions: [], alternatives: [] }], instrumentSpec: { name: 'Custom UI instrument', inputs: ['x'], outputs: { result: { op: 'add', args: [{ op: 'mul', args: [{ field: 'x' }, 3] }, 2] } } }, experimentInputs: { x: 6 } };
  t.fill('model-response', JSON.stringify(response)); t.click('import-response'); await pause();
  t.w.document.querySelector('[data-view="experiment"]').click();
  t.click('run-experiment'); await pause();
  const experiment = t.w.document.getElementById('experiment-result').textContent;
  assert.match(experiment, /20/);
  assert.match(experiment, /UNKNOWN/);
  t.click('save-project'); await pause();
  let customSaved = t.w.localStorage.getItem(key);
  assert.equal(JSON.parse(customSaved).runs.at(-1).execution.outputs.result, 20);
  t.dom.window.close();
  t = boot(customSaved);
  assert.equal(t.w.document.getElementById('mission-name').value, 'Independent DOM mission');
  t.click('load-demo'); await pause();
  if (t.w.document.getElementById('confirm-dialog').open) t.click('dialog-confirm'); await pause();
  t.click('run-experiment'); await pause();
  assert.match(t.w.document.getElementById('experiment-result').textContent, /PASSED IN SCOPE/);
  t.click('retain-capability'); await pause();
  t.click('test-inheritance'); await pause();
  assert.match(t.w.document.getElementById('inheritance-result').textContent, /PASSED IN SCOPE/);
  t.click('export-instrument'); t.click('export-dossier');
  t.click('language-toggle');
  assert.equal(t.w.document.documentElement.lang, 'fr');
  t.click('save-project'); await pause();
  const saved = t.w.localStorage.getItem(key);
  assert.equal(JSON.parse(saved).capabilities.length, 1);
  const priorErrors = t.errors;
  t.dom.window.close();
  t = boot(saved);
  assert.match(t.w.document.getElementById('capability-list').textContent, /UNKNOWN/);
  assert.deepEqual(priorErrors.concat(t.errors), []);
  t.dom.window.close();
  // A valid optional workflow is a complete artifact without a top-level instrument.
  t = boot();
  const workflow = { name: 'Workflow-only computation', inputs: ['data'], effects: [], budget: { maxOperations: 10000 }, steps: [{ id: 'result', op: 'execute', dependsOn: ['data'], args: { instrument: { name: 'Internal increment', inputs: ['x'], outputs: { value: { op: 'add', args: [{ field: 'x' }, 4] } } }, input: { $ref: 'data' } } }], outputs: ['result'] };
  t.fill('model-response', JSON.stringify({ summary: 'Workflow-only proposal', workflow, experimentInputs: { data: { x: 7 } } }));
  t.click('import-response'); await pause();
  t.w.document.querySelector('[data-view="experiment"]').click();
  assert.equal(t.w.document.getElementById('workflow-panel').closest('.hidden'), null, 'Workflow controls must be visible without an unrelated instrument');
  assert.equal(t.w.document.getElementById('workflow-panel').open, true);
  assert.equal(t.w.document.getElementById('instrument-panel').classList.contains('hidden'), true);
  assert.equal(t.w.document.getElementById('economics-panel').classList.contains('hidden'), true);
  t.click('run-workflow'); await pause();
  assert.equal(JSON.parse(t.w.document.getElementById('workflow-result').textContent).outputs.result.outputs.value, 11);
  const replacementWorkflow={...workflow,name:'Replacement workflow'};
  t.fill('model-response',JSON.stringify({summary:'Replacement workflow proposal',workflow:replacementWorkflow,experimentInputs:{data:{x:20}}}));t.click('import-response');await pause();t.w.document.querySelector('[data-view="experiment"]').click();
  assert.equal(JSON.parse(t.w.document.getElementById('workflow-input').value).name,'Replacement workflow','Prior executed workflow alias must not override a newly imported workflow');
  assert.equal(JSON.parse(t.w.document.getElementById('workflow-data').value).data.x,20,'Prior saved workflow inputs must not override new inputs');
  t.click('run-workflow');await pause();assert.equal(JSON.parse(t.w.document.getElementById('workflow-result').textContent).outputs.result.outputs.value,24);
  t.click('save-project'); await pause();
  const workflowSaved = t.w.localStorage.getItem(key);
  assert.equal(JSON.parse(workflowSaved).instrumentSpec, undefined, 'Workflow use must not create an unrelated top-level instrument');
  assert.deepEqual(t.errors, []); t.dom.window.close();
  t = boot(workflowSaved);t.w.document.querySelector('[data-view="experiment"]').click();
  assert.equal(t.w.document.getElementById('workflow-panel').closest('.hidden'), null, 'Reopened workflow-only project stays usable');
  t.click('run-workflow');await pause();assert.equal(JSON.parse(t.w.document.getElementById('workflow-result').textContent).outputs.result.outputs.value,24);
  assert.deepEqual(t.errors, []);t.dom.window.close();

  // An economic arrangement is independently executable without either other artifact kind.
  t = boot();
  const arrangement = { currency: 'CAD', participants: [{ id: 'Participant A', benefitMinor: 1000, costMinor: 0, paymentMinor: 300, outsideOptionMinor: 100 }], costs: [{ id: 'instrument-rental', category: 'tools', amountMinor: 300 }], alternatives: [{ id: 'conventional', name: 'Conventional complete route', totalCostMinor: 450, feasible: true }] };
  t.fill('model-response', JSON.stringify({ summary: 'Arrangement-only proposal', arrangement }));
  t.click('import-response');await pause();t.w.document.querySelector('[data-view="experiment"]').click();
  assert.equal(t.w.document.getElementById('economics-panel').closest('.hidden'), null, 'Arrangement check must be visible without an instrument');
  assert.equal(t.w.document.getElementById('instrument-panel').classList.contains('hidden'), true);
  assert.equal(t.w.document.getElementById('workflow-panel').classList.contains('hidden'), true);
  t.click('check-economics');await pause();assert.match(t.w.document.getElementById('economics-result').textContent,/PASSED IN SCOPE/);
  t.click('save-project');await pause();const arrangementSaved=t.w.localStorage.getItem(key);const arranged=JSON.parse(arrangementSaved);
  assert.equal(arranged.instrumentSpec,undefined);assert.equal(arranged.workflow,undefined);assert.equal(arranged.runs.at(-1).totalCostMinor,300);
  assert.deepEqual(t.errors, []);t.dom.window.close();
  t=boot(arrangementSaved);t.w.document.querySelector('[data-view="experiment"]').click();assert.equal(t.w.document.getElementById('economics-panel').closest('.hidden'),null);t.click('check-economics');await pause();assert.match(t.w.document.getElementById('economics-result').textContent,/PASSED IN SCOPE/);assert.deepEqual(t.errors, []);t.dom.window.close();
  // Malformed saved workflow data stays an inspectable draft and cannot crash navigation.
  t=boot();const invalidDraft=t.w.HarnessEngine.createProject({title:'Malformed workflow draft'});invalidDraft.workflow=t.w.JSON.parse('{}');const invalidSaved=t.w.HarnessEngine.exportProject(invalidDraft);t.dom.window.close();
  t=boot(invalidSaved);t.w.document.querySelector('[data-view="experiment"]').click();assert.equal(t.w.document.getElementById('workflow-input').value,'{}');assert.equal(t.w.document.getElementById('workflow-panel').closest('.hidden'),null);
  t.click('run-workflow');await pause();assert.match(t.w.document.getElementById('notice').textContent,/Workflow name is required/);t.click('save-project');await pause();assert.equal(JSON.parse(t.w.localStorage.getItem(key)).id,invalidDraft.id);assert.equal(JSON.parse(t.w.localStorage.getItem(key)).runs.length,0);assert.deepEqual(t.errors,[]);t.dom.window.close();
  console.log(JSON.stringify({ verdict: 'PASSED IN SCOPE', environment: 'jsdom 26.1.0 emulation; no graphical browser', flows: ['unsent mission save/export', 'custom manual instrument import/execution', 'save/reopen', 'demo verification', 'retention', 'successor comparison', 'instrument/dossier export', 'French toggle', 'reopened verification downgraded', 'workflow-only import, execution, replacement and reopen', 'arrangement-only import, checking and reopen', 'malformed saved workflow remains inspectable and execution is rejected'], noNetwork: true }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
