export const sourceReviewSchema = 'frontier/battery-source-review-v1';

const fields = new Map([
  ['batteryCapacity', {label:'rated electrical capacity', units:new Map([['ah',0], ['mah',3]])}],
  ['batteryWeight', {label:'net battery weight', units:new Map([['kg',0], ['g',3]])}],
  ['nominalVoltage', {label:'nominal voltage', units:new Map([['v',0], ['mv',3]])}],
]);
const scopeFields = ['model','version','market','level','boundary'];
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const tidy = value => typeof value === 'string' ? value.normalize('NFKC').trim().toLowerCase().replace(/\s+/gu, ' ') : '';
const digest = /^[a-f0-9]{64}$/u;
const decimal = /^([+-]?)(\d{1,12})(?:[.,](\d{1,8}))?$/u;

function exactQuantity(value, unit, units) {
  if (typeof value !== 'string' && !Number.isFinite(value)) return undefined;
  const match = String(value).match(decimal);
  const scale = units.get(tidy(unit));
  if (!match || scale === undefined) return undefined;
  const [, sign, whole, fraction = ''] = match;
  return BigInt(sign + whole + fraction) * 10n ** BigInt(11 - fraction.length - scale);
}

function eligibleScope(target, observed) {
  return isObject(observed) && scopeFields.every(key => !tidy(target[key]) || tidy(target[key]) === tidy(observed[key]));
}

function validSource(item) {
  return isObject(item) && typeof item.id === 'string' && /^[a-z0-9][a-z0-9._:-]{0,95}$/iu.test(item.id) &&
    typeof item.excerpt === 'string' && item.excerpt.length > 0 && item.excerpt.length <= 8000 &&
    typeof item.url === 'string' && /^https:\/\/[^\s]+$/u.test(item.url) &&
    typeof item.locator === 'string' && item.locator.trim().length > 0 && digest.test(item.sha256 ?? '');
}

function quoteQuantifies(quote, observation, units) {
  // A source row can state a unit once after an ordered series of configuration columns.
  const expected = exactQuantity(observation.value, observation.unit, units);
  if (expected === undefined) return false;
  const tokens = quote.matchAll(/(?<![\p{L}\p{N}.,+±−–—-])([+-]?\d{1,12}(?:[.,]\d{1,8})?(?:\s+\/\s+[+-]?\d{1,12}(?:[.,]\d{1,8})?)*)\s*(?:(?:\(±\s*\d+(?:[.,]\d+)?\)|±\s*\d+(?:[.,]\d+)?)\s*)?(mAh|Ah|kg|g|mV|V)(?:dc|ac)?\b/giu);
  for (const match of tokens) {
    // A suffix after a range separator, exponent, or unsupported tolerance is not a new value.
    const before = quote.slice(0, match.index);
    if (/(?:\d|\))\s*(?:[±−–—+\/-]|[eE][+-]?)\s*$/u.test(before) || /\d\p{Zs}+$/u.test(before)) continue;
    const [, values, unit] = match;
    if (values.split('/').some(value => exactQuantity(value.trim(), unit, units) === expected)) return true;
  }
  return false;
}

export function reviewClaim(input) {
  if (!isObject(input) || typeof input.id !== 'string' || !/^[a-z0-9][a-z0-9._:-]{0,95}$/iu.test(input.id) ||
      !fields.has(input.field) || !isObject(input.target) || !tidy(input.target.model) || !tidy(input.target.level) ||
      !isObject(input.claim) || !Array.isArray(input.sources) || input.sources.length > 12 ||
      !input.sources.every(validSource) || new Set(input.sources.map(row => row.id)).size !== input.sources.length ||
      !Array.isArray(input.observations) || input.observations.length > 32) throw new Error('SOURCE_REVIEW_CASE');
  const {id,field,target,claim,sources,observations} = input;
  const {label,units} = fields.get(field);
  const inputById = new Map(sources.map(row => [row.id,row]));
  const values = new Map();
  let rejected = 0;
  for (const entry of observations) {
    const source = inputById.get(entry?.source);
    if (!source || entry.field !== field || !eligibleScope(target, entry.target) ||
        typeof entry.quote !== 'string' || !entry.quote.length || !source.excerpt.includes(entry.quote) ||
        !quoteQuantifies(entry.quote, entry, units)) {
      rejected++;
      continue;
    }
    const quantity = exactQuantity(entry.value, entry.unit, units);
    if (!values.has(quantity)) values.set(quantity, new Set());
    values.get(quantity).add(source.id);
  }
  const evidence = [...new Set([...values.values()].flatMap(items => [...items]))].sort();
  const claimed = exactQuantity(claim.value, claim.unit, units);
  const decision = claimed === undefined || !values.size ? 'insufficient' : values.size > 1 ? 'conflicting'
    : values.has(claimed) ? 'supported' : 'contradicted';
  return {id, decision, evidence, rejected, fieldLabel:label};
}

/** Exact comparisons over supplied, source-located observations. Scope labels still require review. */
export function reviewBatterySources(bundle) {
  if (!isObject(bundle) || bundle.schema !== sourceReviewSchema || !Array.isArray(bundle.cases) ||
      bundle.cases.length === 0 || bundle.cases.length > 64 ||
      new Set(bundle.cases.map(item => item?.id)).size !== bundle.cases.length) throw new Error('SOURCE_REVIEW_PACKET');
  return {schema:'frontier/battery-source-review-result-v1', results:bundle.cases.map(reviewClaim)};
}
