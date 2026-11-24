import {candidate, checkSuite, compare, formulaPrompt, freeze, mission, reopen, requalify, runtime} from './foundry-core.mjs';
import {canonical, fingerprint} from './outcome-receipt.mjs';

const schema = 'frontier/foundry-study-v1';
export const studyArms = Object.freeze(['direct', 'ordinary', 'retained']);
const bounded = (value, length) => typeof value === 'string' && value.trim().length > 0 && value.length <= length;
const hash = value => typeof value === 'string' && /^[0-9a-f]{64}$/u.test(value);
const count = value => Number.isSafeInteger(value) && value >= 0;
const exact = (value, keys) => value && typeof value === 'object' && !Array.isArray(value) &&
  Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
function requireStudy(valid) {
  if (!valid) throw new Error('STUDY');
}

function inheritedOutputs(parent, task) {
  requireStudy(parent.task.objective.trim() !== task.objective.trim() &&
    canonical(parent.task.outputs) !== canonical(task.outputs));
  for (const [name, type] of Object.entries(parent.task.inputs)) {
    const destination = task.inputs[name];
    requireStudy(destination !== undefined && (canonical(destination) === canonical(type) ||
      (typeof destination === 'object' && (type === 'integer' ||
        (typeof type === 'object' && destination.min >= type.min && destination.max <= type.max)))));
  }
  const entries = Object.entries(parent.instrument.outputs).map(([key, value]) => ['inherited_' + key, value]);
  requireStudy(entries.every(([key]) => !Object.hasOwn(task.inputs, key)));
  return Object.fromEntries(entries);
}

export async function openStudy(envelope) {
  requireStudy(exact(envelope, ['study','sha256']) && hash(envelope.sha256));
  const s = envelope.study;
  requireStudy(exact(s, ['schema','runtime','task','hypothesis','model','output_tokens','suite_sha256','parent','incumbent']) &&
    s.schema === schema && s.runtime === runtime && bounded(s.hypothesis, 640) && bounded(s.model, 160) &&
    count(s.output_tokens) && s.output_tokens > 0 && s.output_tokens <= 4096 && hash(s.suite_sha256));
  const task = mission(s.task);
  const {frozen:parent} = await reopen(s.parent);
  const incumbent = await freeze(task, s.incumbent);
  const bindings = inheritedOutputs(parent, task);
  requireStudy(await fingerprint(s) === envelope.sha256);
  return {s, task, parent, incumbent, bindings};
}

export async function registerStudy(spec, parent, originalCases, incumbent, cases) {
  requireStudy(exact(spec, ['task','hypothesis','model','output_tokens']));
  await requalify(await reopen(parent), originalCases);
  const frozen = await freeze(spec.task, incumbent);
  const suite = await checkSuite(cases, frozen);
  const study = {schema, runtime, ...spec, suite_sha256:await fingerprint(suite), parent, incumbent:frozen.instrument};
  const envelope = {study, sha256:await fingerprint(study)};
  await openStudy(envelope);
  return envelope;
}

export async function constructionPlan(envelope) {
  const {s, task, parent, bindings} = await openStudy(envelope);
  const common = formulaPrompt(task);
  const reuse = '\nEarlier instrument, provided as background. Its exact expression tree is ' + canonical(parent.instrument) + '.';
  return {
    study_sha256:envelope.sha256, task, model:s.model, output_tokens:s.output_tokens, bindings,
    prompts:{direct:common,
      ordinary:common + reuse,
      retained:common + reuse + '\nYou may use these precomputed scalar names for the earlier outputs: ' +
        Object.keys(bindings).map(key => key + ' for ' + key.slice('inherited_'.length)).join(', ') + '.'},
  };
}

export async function evaluateStudy(envelope, cases, attempts) {
  const {s, task, incumbent, bindings} = await openStudy(envelope);
  const suite = await checkSuite(cases, incumbent);
  requireStudy(await fingerprint(suite) === s.suite_sha256 && exact(attempts, studyArms));
  async function grade(frozen) {
    const result = await compare(frozen, suite);
    return {...result.summary, rows_sha256:await fingerprint(result.rows)};
  }
  const reference = await grade(incumbent);
  const outcomes = {};
  for (const arm of studyArms) {
    const attempt = attempts[arm];
    requireStudy(exact(attempt, ['status','candidate','elapsed_ns','usage','reason','bindings_used']) &&
      ['SEALED','NO_CANDIDATE','PROVIDER_ERROR','INTERRUPTED','PENDING'].includes(attempt.status) &&
      (attempt.elapsed_ns === null || count(attempt.elapsed_ns)) &&
      (attempt.reason === null || (typeof attempt.reason === 'string' && /^[A-Z_]{1,40}$/u.test(attempt.reason))) &&
      Array.isArray(attempt.bindings_used) && attempt.bindings_used.length <= Object.keys(bindings).length &&
      new Set(attempt.bindings_used).size === attempt.bindings_used.length &&
      attempt.bindings_used.every(name => typeof name === 'string' && arm === 'retained' && Object.hasOwn(bindings, name)) &&
      (attempt.usage === null || (exact(attempt.usage, ['input_tokens','output_tokens']) &&
        [attempt.usage.input_tokens, attempt.usage.output_tokens].every(n => n === null || count(n)))));
    if (attempt.status === 'SEALED') {
      const frozen = await freeze(task, candidate(attempt.candidate, task));
      outcomes[arm] = {status:attempt.status, candidate_sha256:frozen.instrument_sha256, comparison:await grade(frozen)};
    } else {
      requireStudy(attempt.candidate === null);
      outcomes[arm] = {status:attempt.status, candidate_sha256:null, comparison:null};
    }
  }
  const scores = studyArms.map(arm => outcomes[arm].comparison?.matched);
  const [direct, ordinary, retained] = scores;
  const comparison = {
    reference, outcomes, quality_only:true,
    retained_vs_ordinary:retained === undefined || ordinary === undefined ? 'UNRESOLVED' :
      retained === ordinary ? 'TIE' : retained > ordinary ? 'HIGHER' : 'LOWER',
    retained_vs_direct:retained === undefined || direct === undefined ? 'UNRESOLVED' :
      retained === direct ? 'TIE' : retained > direct ? 'HIGHER' : 'LOWER',
    decision:reference.verdict === 'MATCHED' ? 'KEEP_INCUMBENT' : 'REVIEW_REQUIRED',
  };
  const report = {plan:envelope, attempts, comparison};
  return {report, sha256:await fingerprint(report)};
}

export async function replayStudy(bundle, cases) {
  requireStudy(exact(bundle, ['report','sha256']) && hash(bundle.sha256) &&
    exact(bundle.report, ['plan','attempts','comparison']));
  const replayed = await evaluateStudy(bundle.report.plan, cases, bundle.report.attempts);
  requireStudy(replayed.sha256 === bundle.sha256 && canonical(replayed.report) === canonical(bundle.report));
  return replayed.report;
}
