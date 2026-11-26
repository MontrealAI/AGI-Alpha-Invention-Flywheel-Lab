// The member workspace executes the same bounded instruments as the HARNESS Foundry.
import {compare, freeze, kinds, retain, run, runtime} from './foundry-core.mjs';

export const instrumentCandidate = 'frontier/mission-instrument-candidate-v1';
export const instrumentBatch = 'frontier/mission-instrument-batch-v1';
const receipt = 'frontier/mission-instrument-receipt-v1';
const sha = /^[a-f0-9]{64}$/u;
const id = /^[a-zA-Z0-9][a-zA-Z0-9./:_-]{0,179}$/u;

function exact(value, keys) {
  return value && typeof value === 'object' && !Array.isArray(value) &&
    Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value,key));
}

function need(condition, reason = 'FORMAT') {
  if (!condition) throw Error(reason);
}

function reference({name, sha256, bytes}) {
  return {name, sha256, bytes};
}

function jsonRecords(files) {
  return files.flatMap(file => {
    if (file.kind !== 'data' || !/\.json$/iu.test(file.name)) return [];
    try { return [{file, value:JSON.parse(file.content.replace(/^\ufeff/u,''))}]; }
    catch { return []; }
  });
}

function inputAt(data, path) {
  for (const key of path) {
    need(data && typeof data === 'object' && Object.hasOwn(data,key), 'INPUT');
    data = data[key];
  }
  return data;
}

async function runBatch(batch, records, files, revision) {
  const {file,value} = batch;
  try {
    need(exact(value, ['schema','candidate_file_sha256','confirmation_file_sha256','sources','cases']) &&
      typeof value.candidate_file_sha256 === 'string' && sha.test(value.candidate_file_sha256) &&
      (value.confirmation_file_sha256 === null || typeof value.confirmation_file_sha256 === 'string' &&
        sha.test(value.confirmation_file_sha256)));
    need(Array.isArray(value.sources) && value.sources.length >= 1 && value.sources.length <= 8 &&
      value.sources.every(item => exact(item, ['name','sha256']) && typeof item.name === 'string' &&
        typeof item.sha256 === 'string' && sha.test(item.sha256)) &&
      new Set(value.sources.map(item=>item.name)).size === value.sources.length);
    const sourceFiles = value.sources.map(item => {
      const source = files.find(other => other.revision === revision && other.name === item.name &&
        other.sha256 === item.sha256 && other !== file && ['data','text'].includes(other.kind));
      need(source, 'SOURCE_MISSING');
      return source;
    });
    need(Array.isArray(value.cases) && value.cases.length >= 1 && value.cases.length <= 32 &&
      value.cases.every(item => exact(item, ['id','source','path']) && typeof item.id === 'string' && id.test(item.id) &&
        typeof item.source === 'string' && Array.isArray(item.path) && item.path.length <= 8 &&
        item.path.every(key => typeof key === 'string' && key.length <= 180 &&
          !['__proto__','constructor','prototype'].includes(key))) &&
      new Set(value.cases.map(item=>item.id)).size === value.cases.length);

    const entry = records.find(item => item.value?.schema === instrumentCandidate &&
      item.file.sha256 === value.candidate_file_sha256);
    need(entry, 'INSTRUMENT_MISSING');
    need(exact(entry.value, ['schema','mission','candidate']));
    const frozen = await freeze(entry.value.mission,entry.value.candidate);
    const confirmation = records.find(item => item.value?.schema === kinds.confirmation &&
      item.file.sha256 === value.confirmation_file_sha256 && item.value.mission_sha256 === frozen.mission_sha256);
    need(value.confirmation_file_sha256 === null || confirmation, 'SUITE');
    const comparison = confirmation ? await compare(frozen,confirmation.value) : null;
    const accepted = comparison?.summary.verdict === 'MATCHED';
    // A new ambition can use an earlier instrument only if its supplied checks still replay.
    need(entry.file.revision === revision || accepted, 'RECHECK_REQUIRED');
    const results = value.cases.map(({id,source,path}) => {
      const record = records.find(item => item.file.name === source && sourceFiles.includes(item.file));
      need(record && record.file !== entry.file && record.file !== confirmation?.file, 'INPUT');
      const input = inputAt(record.value,path);
      return {id, source, path, input, output:run(frozen,input)};
    });
    return {
      schema:receipt, disposition:'EXECUTED_INSTRUMENT', runtime, instrument:frozen.instrument.name,
      candidate:{...reference(entry.file), mission:frozen.task, specification:frozen.instrument,
        sha256Canonical:frozen.instrument_sha256},
      batch:reference(file), sources:sourceFiles.map(reference), results,
      comparison: comparison ? {confirmationFile:reference(confirmation.file), ...comparison.summary} : null,
      retained: entry.file.revision < revision,
      asset: accepted ? await retain(frozen,confirmation.value) : null,
    };
  } catch (error) {
    const allowed = ['SOURCE_MISSING','INSTRUMENT_MISSING','RECHECK_REQUIRED','INPUT','OUTPUT','EXECUTION','SUITE','CANDIDATE'];
    return {schema:receipt, disposition:'WITHHELD', batch:reference(file),
      reason:allowed.includes(error.message) ? error.message : 'FORMAT'};
  }
}

export async function evaluateMissionInstruments(files, revision) {
  const records = jsonRecords(files);
  const batches = records.filter(({file,value}) => file.revision === revision && value?.schema === instrumentBatch);
  return Promise.all(batches.map(batch=>runBatch(batch,records,files,revision)));
}
