// The Pages and offline tools share this contract and the licensed HARNESS evaluator.
import * as harness from './harness-engine.js';
import {canonical, fingerprint} from './outcome-receipt.mjs';

const engine = globalThis.HarnessEngine ?? harness.default;
export const runtime = 'alpha-genesis-harness@' + engine.VERSION;
export const maxBytes = 128 * 1024;
export const kinds = Object.freeze({
  mission: 'frontier/foundry-mission-v1',
  confirmation: 'frontier/foundry-cases-v1',
  asset: 'frontier/foundry-asset-v1',
});
const hash = /^[0-9a-f]{64}$/u;
const operations = 8000;
const object = value => Boolean(value && typeof value === 'object' && !Array.isArray(value));
const exact = (value, keys) => object(value) && Object.keys(value).length === keys.length &&
  keys.every(key => Object.hasOwn(value, key));
const fieldName = value => typeof value === 'string' && /^[a-zA-Z][a-zA-Z0-9_]{0,31}$/u.test(value) &&
  !Object.hasOwn(Object.prototype, value) && value !== 'prototype';
const text = (value, size) => typeof value === 'string' && value.trim().length > 0 &&
  value.length <= size && !/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/u.test(value);
const scalar = value => typeof value === 'boolean' || Number.isSafeInteger(value) || text(value, 240);
function need(condition, code) {
  if (!condition) throw new Error(code);
}

export function readJSON(raw, allowFence = false) {
  need(typeof raw === 'string' && new TextEncoder().encode(raw).length <= maxBytes, 'FILE');
  let data = raw.trim();
  if (allowFence) data = data.replace(/^\x60{3}(?:json)?\s*([\s\S]*?)\s*\x60{3}$/iu, '$1');
  try { return JSON.parse(data); }
  catch { throw new Error('JSON'); }
}

function schema(fields) {
  return object(fields) && Object.keys(fields).length >= 1 && Object.keys(fields).length <= 12 &&
    Object.entries(fields).every(([name, spec]) => fieldName(name) && (
      spec === 'boolean' || spec === 'text' || spec === 'integer' ||
      (exact(spec, ['min','max']) && Number.isSafeInteger(spec.min) && Number.isSafeInteger(spec.max) && spec.min <= spec.max)));
}

function record(value, fields, code) {
  need(exact(value, Object.keys(fields)), code);
  for (const [name, spec] of Object.entries(fields)) {
    const item = value[name];
    need(spec === 'boolean' ? typeof item === 'boolean' : spec === 'text' ? text(item, 240) :
      Number.isSafeInteger(item) && (spec === 'integer' || (item >= spec.min && item <= spec.max)), code);
  }
  return value;
}

export function mission(value) {
  need(exact(value, ['schema','language','objective','rule','inputs','outputs','alternative','acceptance']) &&
    value.schema === kinds.mission && ['en','fr'].includes(value.language) &&
    text(value.objective, 360) && text(value.rule, 2400) && text(value.alternative, 640) &&
    text(value.acceptance, 640) && schema(value.inputs) && schema(value.outputs), 'MISSION');
  return structuredClone(value);
}

export function fieldsFromText(value) {
  const parts = value.trim().split(',').map(part => part.trim().split(/\s*:\s*/u));
  const fields = Object.fromEntries(parts);
  need(parts.every(pair => pair.length === 2) && Object.keys(fields).length === parts.length && schema(fields), 'FIELDS');
  return fields;
}

export function promptFor(value) {
  const task = mission(value);
  const fields = Object.keys(task.inputs);
  const example = {name:'Example',inputs:['x','y'],outputs:{total:{op:'add',args:[{field:'x'},{field:'y'}]}}};
  return [
    'Return one JSON object representing a bounded HARNESS instrument. Return only JSON.',
    'Exactly three top-level keys: name, inputs, outputs.',
    'inputs is an array of these declared names: ' + JSON.stringify(fields),
    'outputs is an object with one expression per declared output name.',
    'Expressions are safe integer, boolean or text literals, {"field":"name"}, or {"op":"add","args":[1,2]}.',
    'Allowed operators: add, sub, mul, min, max, eq, lt, lte, gt, gte, and, or, not. Use sub, comparisons and not with their usual arity.',
    'Arguments must be expressions. Use raw numeric literals. No assignments, source code, nested data lookups, permissions or confirmations.',
    'Syntax example for an unrelated task: ' + JSON.stringify(example),
    'Mission: ' + JSON.stringify(task),
  ].join('\n');
}

export function formulaPrompt(value) {
  const task = mission(value);
  return [
    'Return one assignment per output, in plain text. Use scalar Python expressions only.',
    'Inputs: ' + Object.keys(task.inputs).join(', ') + '.',
    'Output assignments: ' + Object.keys(task.outputs).map(key => key + ' = ___').join('; ') + '.',
    'Use exact integers, booleans or text. Allowed operations include +, -, *, comparisons, and, or, not, min and max.',
    'Do not use len, assignment within an expression, external tools, loops or code blocks.',
    'Objective: ' + task.objective,
    'Rule: ' + task.rule,
    'Acceptance: ' + task.acceptance,
  ].join('\n');
}

function expression(term, fields, depth = 0) {
  need(depth <= 18, 'CANDIDATE');
  if (scalar(term)) return;
  if (exact(term, ['field'])) { need(fields.includes(term.field), 'CANDIDATE'); return; }
  need(exact(term, ['op','args']) && ['add','sub','mul','min','max','eq','lt','lte','gt','gte','and','or','not'].includes(term.op) &&
    Array.isArray(term.args) && term.args.length <= 16, 'CANDIDATE');
  for (const argument of term.args) expression(argument, fields, depth + 1);
}

export function candidate(value, task) {
  const fields = Object.keys(task.inputs);
  need(exact(value, ['name','inputs','outputs']) && text(value.name, 120) &&
    Array.isArray(value.inputs) && value.inputs.length === fields.length &&
    fields.every(key => value.inputs.includes(key)) && exact(value.outputs, Object.keys(task.outputs)), 'CANDIDATE');
  for (const expr of Object.values(value.outputs)) expression(expr, fields);
  need(canonical(value).length <= 12_000, 'CANDIDATE');
  try { engine.constructInstrument(value); }
  catch { throw new Error('CANDIDATE'); }
  return structuredClone(value);
}

export async function freeze(task, draft) {
  const item = mission(task);
  const instrument = candidate(draft, item);
  return {
    task:item, instrument,
    mission_sha256:await fingerprint(item),
    instrument_sha256:await fingerprint(instrument),
  };
}

export async function checkSuite(value, frozen) {
  need(exact(value, ['schema','mission_sha256','reference','cases']) && value.schema === kinds.confirmation &&
    value.mission_sha256 === frozen.mission_sha256 && text(value.reference, 640) && Array.isArray(value.cases) &&
    value.cases.length >= 1 && value.cases.length <= 64, 'SUITE');
  for (const row of value.cases) {
    need(exact(row, ['input','expected']), 'SUITE');
    record(row.input, frozen.task.inputs, 'SUITE');
    record(row.expected, frozen.task.outputs, 'SUITE');
  }
  return structuredClone(value);
}

export function run(frozen, inputs) {
  record(inputs, frozen.task.inputs, 'INPUT');
  const outcome = engine.executeInstrument(frozen.instrument, inputs, {budget:{maxOperations:operations}});
  need(outcome.verdict === 'PASSED IN SCOPE', 'EXECUTION');
  return record(outcome.outputs, frozen.task.outputs, 'OUTPUT');
}

export async function compare(frozen, suite) {
  const cases = await checkSuite(suite, frozen);
  const rows = cases.cases.map(({input,expected}, index) => {
    try {
      const actual = run(frozen, input);
      return {case:index + 1, expected, actual, matches:canonical(actual) === canonical(expected)};
    } catch (error) {
      return {case:index + 1, expected, actual:null, matches:false, error:error.message};
    }
  });
  const matched = rows.filter(row => row.matches).length;
  return {
    summary: {reference:cases.reference, suite_sha256:await fingerprint(cases),
      matched, total:rows.length, verdict:matched === rows.length ? 'MATCHED' : 'REJECTED'},
    rows,
  };
}

export async function retain(frozen, suite) {
  const {summary} = await compare(frozen, suite);
  need(summary.verdict === 'MATCHED', 'REJECTED');
  const asset = {schema:kinds.asset, runtime, mission:frozen.task, candidate:frozen.instrument,
    mission_sha256:frozen.mission_sha256, candidate_sha256:frozen.instrument_sha256, comparison:summary};
  return {asset, sha256:await fingerprint(asset)};
}

export async function reopen(envelope) {
  need(exact(envelope, ['asset','sha256']) && hash.test(envelope.sha256), 'ASSET');
  const a = envelope.asset;
  need(exact(a, ['schema','runtime','mission','candidate','mission_sha256','candidate_sha256','comparison']) &&
    a.schema === kinds.asset && a.runtime === runtime, 'ASSET');
  const frozen = await freeze(a.mission, a.candidate);
  const c = a.comparison;
  need(exact(c, ['reference','suite_sha256','matched','total','verdict']) && c.verdict === 'MATCHED' &&
    hash.test(c.suite_sha256) && Number.isInteger(c.total) && c.total >= 1 && c.total <= 64 &&
    c.matched === c.total && text(c.reference, 640) && a.mission_sha256 === frozen.mission_sha256 &&
    a.candidate_sha256 === frozen.instrument_sha256 && await fingerprint(a) === envelope.sha256, 'ASSET');
  return {frozen, comparison:c};
}

export async function requalify(saved, suite) {
  const result = await compare(saved.frozen, suite);
  need(canonical(result.summary) === canonical(saved.comparison), 'RECHECK');
  return result;
}


export function harnessProject(task, frozen) {
  const item = mission(task);
  const project = engine.createProject({title:item.objective.slice(0, 150), objective:item.objective, language:item.language});
  project.constraints = [
    {kind:'hard', text:item.rule},
    {kind:'hard', text:JSON.stringify({inputs:item.inputs, outputs:item.outputs})},
    {kind:'method', text:item.alternative},
    {kind:'hard', text:item.acceptance},
  ];
  if (frozen) {
    engine.importResponse(project, JSON.stringify({instrumentSpec:candidate(frozen.instrument, item)}),
      {provider:'my-frontier', role:'unverified portable candidate'});
  }
  return JSON.parse(engine.exportProject(project));
}
