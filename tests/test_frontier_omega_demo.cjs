'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');

const file = path.resolve(__dirname, '../docs/research/frontier-omega.html');
const html = fs.readFileSync(file, 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length, 1, 'one self-contained executable script');
const listeners = new Map();
const elements = new Map();
const node = (id) => {
  if (!elements.has(id)) {
    elements.set(id, {
      id, value: '', min: '0', max: '1000000000', dataset: {},
      addEventListener: (name, handler) => listeners.set(id + ':' + name, handler),
      setAttribute() {}, classList: { toggle() {} }, querySelectorAll: () => [],
      scrollIntoView() {}, textContent: '', innerHTML: ''
    });
  }
  return elements.get(id);
};
const document = {
  getElementById: node,
  querySelectorAll: () => []
};
const window = {
  matchMedia: () => ({ matches: true }),
  FRONTIER_OMEGA_DEMO: null
};
const sandbox = { document, window, Intl, Number, Math, Date, URL, Blob, setTimeout, console };
vm.runInNewContext(scripts[0][1], sandbox, { filename: 'frontier-omega.html', timeout: 3000 });
const api = window.FRONTIER_OMEGA_DEMO;

test('all five opportunities have explicit primary research sources and unresolved claims', () => {
  assert.equal(api.CATALOG.length, 5);
  for (const c of api.CATALOG) {
    assert.match(c.url, /^https:\/\//);
    assert.ok(c.blocker.length > 30);
    assert.ok(c.alternative.length > 30);
  }
  assert.match(html, /No AI model calls/);
  assert.match(html, /not verified claims/i);
});

test('the exact Eight Fundamental Mechanisms are retained, not replaced by generic stages', () => {
  assert.deepEqual(Array.from(api.MECHANISMS, x => x[0]), [
    'Structural Transfer',
    'Adversarial Discovery',
    'Strategic Invention',
    'Problem Transformation',
    'Epistemic Invention',
    'Self-Correcting Evidence',
    'Generative Capability Inheritance',
    'Recursive Economic and Strategic Selection'
  ]);
});

test('business and assurance missions rank differently under transparent rules', () => {
  const business = api.rank({ ambition:'Build an autonomous company with agentic business operations', domain:'venture', priority:'repeat', horizon:90 });
  const assurance = api.rank({ ambition:'Formal proof for mission-critical cryptographic software', domain:'software', priority:'assurance', horizon:90 });
  assert.equal(business[0].candidate.name, 'WORKCELL Ω');
  assert.equal(assurance[0].candidate.name, 'PROVE Ω');
});

test('candidate loses when a strong alternative beats its complete scenario economics', () => {
  const a = { value:100, probability:.5, delivery_cost:20, verification_cost:5, failure_downside:10, successor_option_value:0, alternative_net_value:30 };
  const result = api.calculate(a);
  assert.equal(result.candidate, 20);
  assert.equal(result.outside, 30);
  assert.equal(result.advantage, -10);
  assert.equal(result.best_action, 'Existing alternative');
  assert.equal(api.enumerateExpected(a), 20);
});

test('independent enumeration, edge cases, forged-result rejection and downside stress execute', () => {
  const a = { value:80000, probability:.55, delivery_cost:24000, verification_cost:4500, failure_downside:6000, successor_option_value:9000, alternative_net_value:5000 };
  const r = api.allChecks(a);
  assert.equal(r.passes, 6);
  assert.equal(r.verdicts.length, 6);
  assert.equal(r.verdicts.find(x => x.case === 'Altered result is rejected').passed, true);
  assert.ok(r.stress.acceptance_probability < a.probability);
  assert.equal(r.stress.best_action, 'Existing alternative');
});

test('portable stand-alone artifact generator and exports are part of delivered page', () => {
  assert.match(html, /function portableHTML\(/);
  assert.match(html, /Download working artifact/);
  assert.match(html, /Export evidence JSON/);
  assert.doesNotMatch(html, /fetch\(|XMLHttpRequest|WebSocket/);
});
