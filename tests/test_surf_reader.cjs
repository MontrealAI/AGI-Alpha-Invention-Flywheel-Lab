const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../docs/research/surf-the-exponential.html'), 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length, 1, 'Exercise the complete inline reader script.');

function openReader() {
  const nodes = new Map();
  function element(id) {
    if (!nodes.has(id)) {
      const classes = new Set();
      nodes.set(id, {
        value: '', checked: false, hidden: false, textContent: '', dataset: {}, attributes: {}, events: {},
        classList: { toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); },
          contains(name) { return classes.has(name); } },
        setAttribute(name, value) { this.attributes[name] = value; },
        addEventListener(name, callback) { this.events[name] = callback; }
      });
    }
    return nodes.get(id);
  }
  for (const [id, value] of [['p', 50], ['q', 25], ['r', 6]]) element('retention-' + id).value = String(value);
  const presets = ['likely', 'cheaper', 'rare'].map(key => {
    const button = element('preset-' + key); button.dataset.retentionPreset = key; return button;
  });
  vm.runInNewContext(scripts[0][1], { document: {
    getElementById: element,
    querySelectorAll(selector) { assert.equal(selector, '[data-retention-preset]'); return presets; }
  } });
  function select(P, Q, r, late) {
    for (const [key, value] of [['p', P], ['q', Q], ['r', r]]) element('retention-' + key).value = String(value);
    element('retention-late').checked = late;
    element('retention-p').events.input();
  }
  return { element, presets, select };
}

// Independent finite decision tree: enumerate 10,000 equally weighted branches.
// Availability is conditional on arrival, and actions cannot use a missing source.
function branchOracle(P, Q, r) {
  const total = { d: 0, r: 0, a: 0, l: 0 };
  for (let arrival = 0; arrival < 100; arrival++) {
    for (let access = 0; access < 100; access++) {
      const arrived = arrival < P, available = access < Q;
      total.r -= 4; total.a -= 2;
      if (!arrived) continue;
      total.r += 20;
      const reconstruct = Math.max(...[0, 20 - r]);
      total.a += reconstruct;
      if (available) {
        total.d += reconstruct; total.l += reconstruct;
      } else {
        total.l += Math.max(...[0, 20 - r - 2]);
      }
    }
  }
  return total;
}

function check(reader, P, Q, r, late) {
  reader.select(P, Q, r, late);
  const expected = branchOracle(P, Q, r);
  const menu = late ? ['d', 'r', 'a', 'l'] : ['d', 'r', 'a'];
  const best = Math.max(...menu.map(key => expected[key]));
  for (const key of ['d', 'r', 'a', 'l']) {
    const displayed = reader.element('retention-value-' + key).textContent.replace('−', '-');
    assert.equal(Number(displayed), expected[key] / 10000, `${key}: ${P}/${Q}/${r}/${late}`);
    assert.equal(reader.element('retention-policy-' + key).classList.contains('is-best'),
      menu.includes(key) && expected[key] === best, `Winner ${key}`);
  }
  assert.equal(reader.element('retention-policy-l').hidden, !late);
  assert.equal(reader.element('retention-results').classList.contains('has-late'), late);
}

test('three reader presets agree with separately enumerated decisions', () => {
  const reader = openReader();
  assert.equal(reader.element('retention-interactive').hidden, false);
  assert.equal(reader.element('retention-static').hidden, true);
  for (const [index, parameters] of [[0, [50, 25, 6]], [1, [50, 25, 1]], [2, [5, 25, 6]]]) {
    reader.presets[index].events.click();
    assert.deepEqual(['p', 'q', 'r'].map(key => Number(reader.element('retention-' + key).value)), parameters);
    check(reader, ...parameters, false);
  }
});

test('the exact switch preserves both winners and announces the tie', () => {
  const reader = openReader(); check(reader, 50, 25, 4, false);
  assert.match(reader.element('retention-verdict').textContent, /^Tied highest/);
  assert.equal(reader.element('retention-status-r').textContent, 'Tied highest in the selected menu');
  assert.equal(reader.element('retention-status-a').textContent, 'Tied highest in the selected menu');
});

test('changed timing admits the adaptive late control instead of blind purchase', () => {
  const reader = openReader(); check(reader, 50, 25, 1, true);
  assert.equal(reader.element('retention-value-l').textContent, '8.75');
  reader.element('retention-late').checked = false;
  reader.element('retention-late').events.change();
  assert.equal(reader.element('retention-policy-l').hidden, true);
  assert.equal(reader.element('retention-policy-a').classList.contains('is-best'), true);
});

test('absence, certain access and uneconomic exercise keep costs and outside options', () => {
  const reader = openReader();
  for (const params of [[0, 25, 6, false], [50, 100, 1, true], [50, 0, 1, true],
    [5, 25, 30, true], [50, 25, 20, true], [1, 1, 1, false]]) check(reader, ...params);
  assert.equal(reader.element('retention-value-d').textContent, '0.0019');
  assert.equal(reader.element('retention-p').attributes['aria-valuetext'], '1 percent');
});

test('no-JavaScript and print readers retain the scenarios and explicit assumptions', () => {
  assert.match(html, /id="retention-interactive" hidden/);
  assert.match(html, /<div class="retention-static" id="retention-static">/);
  assert.match(html, /#retention-static\[hidden\]\s*\{\s*display:\s*block\s*!important/);
  assert.match(html, /8\.75/);
  assert.match(html, /Arrival and availability reveal no hidden answer information/);
  assert.match(html, /net of common fulfillment costs/);
  assert.match(html, /aria-live="polite"/);
});
