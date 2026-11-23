/** Exact finite screening for one declared, unchanged test scope. */
export const version = '1.0.0';
const documentFields = ['schema', 'source', 'scope', 'cutoff', 'minimum_tokens_per_s', 'maximum_p90_ttft_ms', 'rows'];
const rowFields = ['id', 'published', 'load', 'tokens_per_s', 'p90_ttft_ms'];
const unsigned = /^\d{1,24}(?:\.\d{1,24})?$/u;
const identity = /^[a-zA-Z0-9._:-]{1,100}$/u;

function fields(value, expected) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === expected.length && expected.every(k => Object.hasOwn(value, k));
}

function day(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/u.test(value)) return false;
  const time = Date.parse(value + 'T00:00:00.000Z');
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value;
}

function positiveText(value, limit) {
  return typeof value === 'string' && value.trim() === value && value.length > 0 && value.length <= limit
    && !/[\p{Cc}\p{Cf}\p{Cs}]/u.test(value);
}

function exact(value) {
  if (typeof value !== 'string' || !unsigned.test(value)) throw new Error('DECIMAL');
  const [integer, fraction = ''] = value.split('.');
  return BigInt(integer + fraction.padEnd(24, '0'));
}

export function validate(input) {
  if (!fields(input, documentFields) || input.schema !== 'frontier/endpoint-screen-v1') throw new Error('SCHEMA');
  if (!positiveText(input.source, 220) || !fields(input.scope, ['model', 'workload', 'system'])
    || !Object.values(input.scope).every(value => positiveText(value, 170))) throw new Error('SCOPE');
  if (!day(input.cutoff)) throw new Error('CUTOFF');
  exact(input.minimum_tokens_per_s);
  exact(input.maximum_p90_ttft_ms);
  if (!Array.isArray(input.rows) || input.rows.length < 1 || input.rows.length > 10000) throw new Error('ROWS');
  const loadSeen = new Set();
  const idSeen = new Set();
  for (const row of input.rows) {
    if (!fields(row, rowFields) || typeof row.id !== 'string' || !identity.test(row.id)
      || !Number.isSafeInteger(row.load) || row.load < 1
      || (row.published !== null && !day(row.published))) throw new Error('ROW');
    if (idSeen.has(row.id) || loadSeen.has(row.load)) throw new Error('AMBIGUOUS_ROW');
    idSeen.add(row.id);
    loadSeen.add(row.load);
    if (row.tokens_per_s !== null) exact(row.tokens_per_s);
    if (row.p90_ttft_ms !== null) exact(row.p90_ttft_ms);
  }
  return input;
}

function disposition(row, cutoff, minimum, maximum) {
  if (row.published === null) return 'missing-publication-date';
  if (row.published > cutoff) return 'not-yet-documented';
  if (row.tokens_per_s === null || row.p90_ttft_ms === null) return 'missing-measurement';
  if (exact(row.tokens_per_s) < minimum) return 'below-threshold';
  if (exact(row.p90_ttft_ms) > maximum) return 'above-ceiling';
  return 'qualified';
}

export function screen(input) {
  validate(input);
  const min = exact(input.minimum_tokens_per_s);
  const max = exact(input.maximum_p90_ttft_ms);
  const rows = input.rows.map(row => ({
    id: row.id, load: row.load, disposition: disposition(row, input.cutoff, min, max)
  })).sort((a, b) => a.load - b.load);
  const highest = rows.findLast(row => row.disposition === 'qualified');
  return {
    schema: 'frontier/endpoint-result-v1',
    screening: highest ? 'QUALIFIED_TESTED_POINT' : 'ABSTAIN',
    highest_tested_load: highest?.load ?? null,
    evidence_id: highest?.id ?? null,
    operating_adoption: 'ABSTAIN',
    rows,
  };
}
