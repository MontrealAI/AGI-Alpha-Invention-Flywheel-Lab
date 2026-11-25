import {fingerprint} from './outcome-receipt.mjs';
import {createMissionRequest, missionRouteRequest} from './frontier-mission-router.mjs';
import {isMissionArtifact, maximumArtifacts, maximumArtifactBytes, verifyMissionArtifact} from './frontier-artifact-exchange.mjs';

export const missionSchema = 'frontier/universal-mission-v1';
export const maxAmbitionBytes = 24 * 1024;
export const maxMissionBytes = 2 * 1024 * 1024;
export const maxInstructionBytes = 2 * 1024;
export const maxDocumentBytes = 96 * 1024;
export const maxDocuments = 8;
export const routes = Object.freeze([
  'direct', 'capability', 'composition', 'adaptation', 'research', 'invention', 'continuing', 'clarification',
]);
export const providers = Object.freeze(['deterministic', 'local', 'authorized', 'assisted', 'hybrid']);

const encoder = new TextEncoder();
const states = ['ready', 'waiting', 'running', 'review', 'paused', 'canceled'];
const uuid = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/u;
const hash = /^[a-f0-9]{64}$/u;
const badControl = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/u;
const reportLists = [
  'assumptions', 'constraints', 'resources', 'knowledge', 'hypotheses', 'alternatives',
  'approaches', 'experiments', 'failures', 'retainedCapabilities', 'capabilityIds',
];
const reportText = {progress: 12 * 1024, work: 12 * 1024, outcome: 12 * 1024};
const reportFields = ['route', 'objective', 'nextAction', ...Object.keys(reportText), ...reportLists, 'evidence', 'artifacts'];
const reportMetadata = ['runId', 'revision', 'provider', 'model', 'recordedAt'];
const requestFields = ['schema', 'requestId', 'missionId', 'revision', 'language', 'ambition',
  'originalAmbition', 'context', 'capabilities'];

const object = value => value !== null && typeof value === 'object'
  && [Object.prototype, null].includes(Object.getPrototypeOf(value));
const allowedKeys = (value, keys) => object(value) && Object.keys(value).every(key => keys.includes(key));
const exact = (value, keys) => allowedKeys(value, keys) && keys.every(key => Object.hasOwn(value, key));
const text = (value, bytes) => typeof value === 'string' && value.length <= bytes && value.trim().length > 0
  && !badControl.test(value) && encoder.encode(value).length <= bytes;
const integer = (value, minimum) => Number.isSafeInteger(value) && value >= minimum;
const instant = value => typeof value === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/u.test(value)
  && Number.isFinite(Date.parse(value)) && new Date(value).toISOString() === value;

function need(condition, code = 'MISSION_INVALID') {
  if (!condition) throw new Error(code);
}

function freeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const item of Object.values(value)) freeze(item);
    Object.freeze(value);
  }
  return value;
}

function bounded(mission) {
  // Use the indented representation that the workbench actually downloads.
  const size = encoder.encode(JSON.stringify({mission, sha256: '0'.repeat(64)}, null, 2)).length;
  // Keep room for a pause followed by cancellation even when the work log is full.
  const reserve = mission.status === 'canceled' ? 0 : mission.status === 'paused' ? 8192 : 16384;
  need(size <= maxMissionBytes - reserve, 'MISSION_SIZE');
  return freeze(mission);
}

function timestamp(previous = '') {
  const current = new Date().toISOString();
  return current < previous ? previous : current;
}

function update(mission, fields, at = timestamp(mission.updatedAt)) {
  return bounded({...mission, ...fields, updatedAt: at});
}

function validLink(value) {
  if (!text(value, 2048) || /[\s\\]/u.test(value)) return false;
  if (/^#[A-Za-z][A-Za-z0-9_.:-]{0,119}$/u.test(value)) return true;
  if (/^[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$/u.test(value)) {
    return value.split('/').every(part => part && part !== '.' && part !== '..');
  }
  try {
    const url = new URL(value);
    return value.startsWith('https://') && url.protocol === 'https:' && !url.username && !url.password;
  } catch {
    return false;
  }
}

function reference(value) {
  if (typeof value === 'string') return text(value, 2048);
  return allowedKeys(value, ['label', 'url', 'sha256', 'kind', 'content']) && text(value.label, 512)
    && (!Object.hasOwn(value, 'url') || validLink(value.url))
    && (!Object.hasOwn(value, 'sha256') || (typeof value.sha256 === 'string' && hash.test(value.sha256)))
    && (!Object.hasOwn(value, 'kind') || text(value.kind, 160))
    && (!Object.hasOwn(value, 'content') || text(value.content, 32 * 1024));
}

const validList = (value, validate) => Array.isArray(value) && value.length <= 64
  && Array.from(value).every(validate);

function validReport(value, keys = reportFields) {
  return allowedKeys(value, keys) && ['route', 'objective', 'nextAction'].every(key => Object.hasOwn(value, key))
    && routes.includes(value.route)
    && text(value.objective, maxAmbitionBytes) && text(value.nextAction, 2048)
    && Object.entries(reportText).every(([key, bytes]) => !Object.hasOwn(value, key) || text(value[key], bytes))
    && reportLists.every(key => !Object.hasOwn(value, key) || validList(value[key], item => text(item, 2048)))
    && ['evidence', 'artifacts'].every(key => !Object.hasOwn(value, key) || validList(value[key], reference));
}

function validSelection(route, provider, model) {
  return (route === null || routes.includes(route)) && (provider === null || providers.includes(provider))
    && (model === null || (provider !== null && text(model, 256)));
}

export function createMission(ambition, {language = 'en'} = {}) {
  need(text(ambition, maxAmbitionBytes), 'MISSION_AMBITION');
  need(['en', 'fr'].includes(language));
  const at = timestamp();
  return bounded({schema: missionSchema, id: crypto.randomUUID(), language, originalAmbition: ambition, ambition,
    revision: 1, revisions: [{revision: 1, ambition, at}], status: 'ready', runSequence: 0,
    run: null, request: null, reports: [], incidents: [], createdAt: at, updatedAt: at});
}

export function reviseMission(mission, ambition) {
  need(text(ambition, maxAmbitionBytes), 'MISSION_AMBITION');
  if (ambition === mission.ambition) return mission;
  const at = timestamp(mission.updatedAt);
  const revision = mission.revision + 1;
  return update(mission, {ambition, revision, revisions: [...mission.revisions, {revision, ambition, at}],
    run: null, request: null, status: 'ready'}, at);
}

export function addMissionInstruction(mission, instruction) {
  need(text(instruction, maxInstructionBytes), 'MISSION_INSTRUCTION');
  const at = timestamp(mission.updatedAt);
  const turns = [...(mission.turns ?? []), {revision: mission.revision, instruction, at}];
  return update(continueMission(mission), {turns}, at);
}

function validDocuments(value) {
  return Array.isArray(value) && value.length <= maxDocuments && Array.from(value).every(document =>
    exact(document, ['name', 'text']) && text(document.name, 200) && !/[\\/:\r\n\t]/u.test(document.name)
    && !['.', '..'].includes(document.name)
    && text(document.text, maxDocumentBytes)) && new Set(value.map(document => document.name)).size === value.length
    && value.reduce((total, document) => total + encoder.encode(document.text).length, 0) <= maxDocumentBytes;
}

export function checkMissionDocuments(documents) {
  need(validDocuments(documents), 'MISSION_DOCUMENTS');
  return documents;
}

export function setMissionDocuments(mission, documents) {
  checkMissionDocuments(documents);
  return update(mission, {documents: structuredClone(documents)});
}

function validWorkFiles(files, revision) {
  return Array.isArray(files) && files.length <= maximumArtifacts &&
    files.every(file => isMissionArtifact(file) && file.revision <= revision) &&
    files.reduce((total, file) => total + file.bytes, 0) <= maximumArtifactBytes;
}

export function addMissionArtifacts(mission, artifacts) {
  const files = [...(mission.workFiles ?? [])];
  for (const item of artifacts) {
    need(isMissionArtifact(item) && item.revision === mission.revision, 'MISSION_ARTIFACT');
    if (!files.some(file => file.name === item.name && file.revision === item.revision && file.sha256 === item.sha256)) {
      files.push({...item});
    }
  }
  need(validWorkFiles(files, mission.revision), 'MISSION_ARTIFACT');
  return update(mission, {workFiles:files});
}

function start(mission, {route = null, provider = null, model = null}, status) {
  if (mission.status === 'running' || mission.status === 'canceled') return mission;
  need(validSelection(route, provider, model) && (status === 'waiting' || provider !== null), 'MISSION_ROUTE');
  const previous = mission.status === 'waiting' && mission.run;
  const sameRoute = previous && previous.route === route && previous.provider === provider && previous.model === model;
  if (sameRoute && status === 'waiting') return mission;
  const runSequence = sameRoute ? mission.runSequence : mission.runSequence + 1;
  need(Number.isSafeInteger(runSequence), 'MISSION_SIZE');
  const at = timestamp(mission.updatedAt);
  const run = {id: `${mission.id}:${runSequence}`, revision: mission.revision, route, provider, model,
    startedAt: status === 'running' ? at : null};
  return update(mission, {runSequence, run, status, request: sameRoute ? mission.request : null}, at);
}

export function prepareMission(mission, selection = {}) {
  return start(mission, selection, 'waiting');
}

export function beginMission(mission, selection = {}) {
  return start(mission, selection, 'running');
}

async function checkedRequest(mission, value) {
  need(exact(value, requestFields) && value.schema === missionRouteRequest && typeof value.requestId === 'string'
    && hash.test(value.requestId) && value.missionId === mission.id && value.revision === mission.revision
    && value.language === mission.language && value.ambition === mission.ambition
    && value.originalAmbition === mission.originalAmbition, 'MISSION_REQUEST');
  const {schema, requestId, ...input} = value;
  const verified = await createMissionRequest(input);
  need(verified.requestId === requestId, 'MISSION_REQUEST');
  return verified;
}

export async function bindMissionRequest(mission, runId, request) {
  if (mission.run?.id !== runId || !['waiting', 'running'].includes(mission.status)) return mission;
  const verified = await checkedRequest(mission, request);
  if (mission.request?.requestId === verified.requestId) return mission;
  return update(mission, {request: verified});
}

export function recordMission(mission, runId, report) {
  const {run, status} = mission;
  if (!run || run.id !== runId || (status !== 'running' && !(status === 'waiting' && run.provider === 'assisted'))) return mission;
  need(validReport(report), 'MISSION_REPORT');
  const at = timestamp(mission.updatedAt);
  const nextReport = {...structuredClone(report), runId, revision: mission.revision, provider: run.provider,
    model: run.model, recordedAt: at};
  return update(mission, {status: 'review', run: {...run, route: report.route}, reports: [...mission.reports, nextReport]}, at);
}

function incident(mission, type, reason, status) {
  need(reason === null || text(reason, 2048), 'MISSION_REASON');
  const at = timestamp(mission.updatedAt);
  const detail = {type, revision: mission.revision, runId: mission.run?.id ?? null, at, reason};
  return update(mission, {status, incidents: [...mission.incidents, detail]}, at);
}

export function interruptMission(mission, runId, reason = null) {
  if (!['running', 'waiting'].includes(mission.status) || mission.run.id !== runId) return mission;
  return incident(mission, 'interrupted', reason, 'paused');
}

export function cancelMission(mission, reason = null) {
  if (mission.status === 'canceled') return mission;
  return incident(mission, 'canceled', reason, 'canceled');
}

export function continueMission(mission) {
  if (['ready', 'running'].includes(mission.status)) return mission;
  return update(mission, {status: 'ready', run: null, request: null});
}

export function missionPacket(mission) {
  // Configuration credentials and execution permissions are outside this projection.
  return freeze({schema: 'frontier/universal-mission-packet-v1', missionId: mission.id, revision: mission.revision,
    runId: mission.run?.id ?? null, language: mission.language, originalAmbition: mission.originalAmbition,
    ambition: mission.ambition, previousReport: mission.reports.at(-1) ?? null,
    instruction: mission.turns?.findLast(item => item.revision === mission.revision)?.instruction ?? null});
}

function sequence(mission, runId) {
  if (typeof runId !== 'string' || !runId.startsWith(mission.id + ':')) return 0;
  const number = Number(runId.slice(mission.id.length + 1));
  return integer(number, 1) && number <= mission.runSequence && runId === `${mission.id}:${number}` ? number : 0;
}

function checkMission(mission) {
  const required = ['schema', 'id', 'language', 'originalAmbition', 'ambition', 'revision', 'revisions',
    'status', 'runSequence', 'run', 'request', 'reports', 'incidents', 'createdAt', 'updatedAt'];
  need(allowedKeys(mission, [...required, 'turns', 'documents', 'workFiles']) && required.every(key => Object.hasOwn(mission, key)));
  need(mission.schema === missionSchema && typeof mission.id === 'string' && uuid.test(mission.id)
    && ['en', 'fr'].includes(mission.language) && states.includes(mission.status)
    && instant(mission.createdAt) && instant(mission.updatedAt) && mission.createdAt <= mission.updatedAt
    && integer(mission.runSequence, 0) && integer(mission.revision, 1));

  const {run, reports, incidents, revisions, status} = mission;
  need(Array.isArray(revisions) && revisions.length === mission.revision);
  let previous = mission.createdAt;
  for (const [index, entry] of revisions.entries()) {
    need(exact(entry, ['revision', 'ambition', 'at']) && entry.revision === index + 1
      && text(entry.ambition, maxAmbitionBytes) && instant(entry.at) && entry.at >= previous && entry.at <= mission.updatedAt);
    previous = entry.at;
  }
  need(revisions[0].ambition === mission.originalAmbition && revisions[0].at === mission.createdAt
    && revisions.at(-1).ambition === mission.ambition);
  const validTime = (revision, at) => integer(revision, 1) && revision <= mission.revision
    && instant(at) && at >= revisions[revision - 1].at && at <= mission.updatedAt;
  if (Object.hasOwn(mission, 'turns')) {
    need(Array.isArray(mission.turns));
    let last = mission.createdAt;
    for (const turn of mission.turns) {
      need(exact(turn, ['revision', 'instruction', 'at']) && validTime(turn.revision, turn.at)
        && turn.at >= last && text(turn.instruction, maxInstructionBytes));
      last = turn.at;
    }
  }
  if (Object.hasOwn(mission, 'documents')) need(validDocuments(mission.documents));
  if (Object.hasOwn(mission, 'workFiles')) need(validWorkFiles(mission.workFiles, mission.revision), 'MISSION_ARTIFACT');

  need(Array.isArray(reports) && Array.isArray(incidents));
  let lastRun = 0;
  for (const report of reports) {
    need(validReport(report, [...reportFields, ...reportMetadata]) && validTime(report.revision, report.recordedAt)
      && providers.includes(report.provider) && validSelection(report.route, report.provider, report.model));
    const number = sequence(mission, report.runId);
    need(number > lastRun);
    lastRun = number;
  }
  for (const detail of incidents) {
    need(exact(detail, ['type', 'revision', 'runId', 'at', 'reason']) && ['interrupted', 'canceled'].includes(detail.type)
      && validTime(detail.revision, detail.at) && (detail.runId === null || sequence(mission, detail.runId) > 0)
      && (detail.reason === null || text(detail.reason, 2048)));
  }
  if (run === null) {
    need(['ready', 'canceled'].includes(status) && mission.request === null);
    return;
  }
  need(status !== 'ready' && exact(run, ['id', 'revision', 'route', 'provider', 'model', 'startedAt'])
    && run.revision === mission.revision && mission.runSequence > 0 && sequence(mission, run.id) === mission.runSequence
    && validSelection(run.route, run.provider, run.model)
    && (run.startedAt === null || validTime(run.revision, run.startedAt)));
  if (status === 'waiting') need(run.startedAt === null && lastRun < mission.runSequence);
  if (status === 'running') {
    need(run.provider !== null && run.startedAt !== null && lastRun < mission.runSequence);
  }
  if (status === 'paused') {
    const latest = incidents.at(-1);
    need(lastRun < mission.runSequence && latest?.type === 'interrupted' && latest.runId === run.id);
  }
  if (status === 'review') {
    const result = reports.at(-1);
    need(result && result.runId === run.id && result.revision === run.revision && result.route === run.route
      && result.provider === run.provider && result.model === run.model
      && (run.startedAt === null ? run.provider === 'assisted' : run.startedAt <= result.recordedAt));
  }
}

export async function exportMission(mission) {
  checkMission(mission);
  const snapshot = bounded(structuredClone(mission));
  if (snapshot.request !== null) await checkedRequest(snapshot, snapshot.request);
  for (const file of snapshot.workFiles ?? []) need(await verifyMissionArtifact(file), 'MISSION_ARTIFACT');
  return {mission: snapshot, sha256: await fingerprint(snapshot)};
}

export async function importMission(value) {
  if (typeof value === 'string') {
    need(value.length <= maxMissionBytes && encoder.encode(value).length <= maxMissionBytes, 'MISSION_SIZE');
    try { value = JSON.parse(value); }
    catch { throw new Error('MISSION_FILE'); }
  }
  need(exact(value, ['mission', 'sha256']) && typeof value.sha256 === 'string' && hash.test(value.sha256), 'MISSION_FILE');
  const digest = value.sha256;
  checkMission(value.mission);
  const mission = bounded(structuredClone(value.mission));
  need(await fingerprint(mission) === digest, 'MISSION_DIGEST');
  if (mission.request !== null) await checkedRequest(mission, mission.request);
  for (const file of mission.workFiles ?? []) need(await verifyMissionArtifact(file), 'MISSION_ARTIFACT');
  if (mission.status === 'running') return interruptMission(mission, mission.run.id, 'checkpoint-restored');
  return mission;
}
