export const sourceReviewSchema = 'frontier/battery-source-review-v1';

const fields = new Map([
  ['batteryCapacity', {label:'rated electrical capacity', units:new Map([['ah',0], ['mah',3]]),
    heading:/^(?:(?:rated|nominal) (?:(?:electrical|battery|system|charge) )?capacity|capacité (?:électrique )?nominale)\b\s*:?\s*/iu}],
  ['batteryWeight', {label:'net battery weight', units:new Map([['kg',0], ['g',3]]),
    heading:/^(?:general data\s*[—–-]\s*)?(?:table of )?(?:(?:(?:complete battery net|net battery|battery|net) )?weights?(?: of one complete battery system| by column)?|poids(?: net)?|masse nette)\b\s*:?\s*/iu}],
  ['nominalVoltage', {label:'nominal voltage', units:new Map([['v',0], ['mv',3]]),
    heading:/^(?:(?:rated|nominal) (?:(?:battery|DC) )?voltage|tension nominale)\b\s*(?:\(DC\)\s*)?:?\s*/iu}],
]);
const scopeFields = ['model','version','market','level','boundary'];
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const tidy = value => typeof value === 'string' ? value.normalize('NFC').trim().toLowerCase().replace(/\s+/gu, ' ') : '';
const digest = /^[a-f0-9]{64}$/u;
const decimal = /^([+-]?)(\d{1,12})(?:[.,](\d{1,8}))?$/u;
const qualificationHeading = /(?:^|[:—–(]\s*|\s-\s+)(?:max(?:imums?|ima)?|min(?:imums?|ima)?|(?:upper|lower) (?:bounds?|limits?|estimates?)|bounds?|limits?|caps?|ceilings?|floors?|at (?:most|least)|approximat\p{L}*|estimat\p{L}*|typical|indicative|provisional|preliminary|not (?:reported|measured)|(?:valeurs?|mesures?|données) (?:maximales?|minimales?|approximatives?|indicatives?|estim[ée]es?|provisoires?|préliminaires?)|limites?|bornes?|estimations?|environ|à titre indicatif)(?=$|[\s.:,—–…/)])/iu;
const boundedPropertyHeading = /^(?:max(?:imum)?|min(?:imum)?)\.?\s+(?:(?:continuous|operating|peak|rated|charge|charging|discharge|discharging|and|allowable|input|output|net|battery|pack|system|module|DC|AC)(?:\s*\/\s*|\s+))*(current|voltage|capacity|weight|mass|power|energy)\s*(?:\((?:AC|DC)\)\s*)?:?\s*/iu;
const boundedPropertyUnits = new Map([
  ['current', new Map([['a',0], ['ma',3]])],
  ['voltage', fields.get('nominalVoltage').units],
  ['capacity', fields.get('batteryCapacity').units],
  ['weight', fields.get('batteryWeight').units],
  ['mass', fields.get('batteryWeight').units],
  ['power', new Map([['kw',0], ['w',3]])],
  ['energy', new Map([['kwh',0], ['wh',3]])],
]);

function exactQuantity(value, unit, units) {
  if (typeof value !== 'string' && !Number.isFinite(value)) return undefined;
  // Without a source locale, a three-digit group after one separator is ambiguous.
  if (typeof value === 'string' && /^[+-]?[1-9]\d{0,2}[.,]\d{3}$/u.test(value)) return undefined;
  const match = String(value).match(decimal);
  const scale = units.get(tidy(unit));
  if (!match || scale === undefined) return undefined;
  const [, sign, whole, fraction = ''] = match;
  return BigInt(sign + whole + fraction) * 10n ** BigInt(11 - fraction.length - scale);
}

function validScope(scope) {
  return isObject(scope) && scopeFields.every(key => !Object.hasOwn(scope, key) || tidy(scope[key]) !== '');
}

function eligibleScope(target, observed) {
  return validScope(observed) && scopeFields.every(key => !Object.hasOwn(target, key) ||
    (Object.hasOwn(observed, key) && tidy(target[key]) === tidy(observed[key])));
}

function validSource(item) {
  return isObject(item) && typeof item.id === 'string' && /^[a-z0-9][a-z0-9._:-]{0,95}$/iu.test(item.id) &&
    typeof item.excerpt === 'string' && item.excerpt.length > 0 && item.excerpt.length <= 8000 &&
    typeof item.url === 'string' && /^https:\/\/[^\s]+$/u.test(item.url) &&
    typeof item.locator === 'string' && item.locator.trim().length > 0 && digest.test(item.sha256 ?? '');
}

function measurementValues(text, units, ordered) {
  const parts = text.trim().split(/\s+\/\s+|,\s+(?=[+-]?\d)/u);
  if (parts.length > 1 && !ordered) return [];
  const readings = parts.map(part => part.match(/^([+-]?\d{1,12}(?:[.,]\d{1,8})?)\s*(?:(?:\(±\s*\d+(?:[.,]\d+)?\)|±\s*\d+(?:[.,]\d+)?)\s*)?([a-z]+)?$/iu));
  if (readings.some(row => !row)) return [];
  const unitOf = row => tidy(row[2]).replace(/^(mv|v)dc$/u, '$1');
  const lastUnit = unitOf(readings.at(-1));
  const sharedUnit = ordered && /\s+\/\s+/u.test(text) && !/,\s+(?=[+-]?\d)/u.test(text);
  const measured = readings.map(row => exactQuantity(row[1], unitOf(row) || (sharedUnit ? lastUnit : ''), units));
  return measured.includes(undefined) ? [] : measured;
}

function clauses(text) {
  return text.split(/[;\r\n]+|\.\s+(?=\p{Lu}[\p{L}\p{N}-]{2,}\b)/u)
    .map(part => part.trim().replace(/\.$/u, '')).filter(Boolean);
}

function sectionDepth(part) {
  const markdown = part.match(/^(#{1,6})\s+(.*)$/u);
  const hasTitle = body => /[\p{L}\p{N}]/u.test(body.replace(/<[^>]*>/gu, ''));
  if (markdown && hasTitle(markdown[2])) return markdown[1].length;
  const html = part.match(/^<h([1-6])(?:\s[^>]*)?>(.*)<\/h\1>$/iu);
  if (html && hasTitle(html[2])) return Number(html[1]);
  return undefined;
}

function qualifiedSection(part, isHeading) {
  const heading = part.replace(/<\/?(?:h[1-6]|strong|em|b|i)(?:\s[^>]*)?>|[*_`]/giu, '')
    .replace(/^(?:(?:[#>•●◦▪+—–-]+|\d+[.)])\s*)+/u, '').trim();
  if (!qualificationHeading.test(heading)) return false;
  if (isHeading) return true;
  // A complete bound on one named property is a field row, not a section heading.
  const field = boundedPropertyHeading.exec(heading);
  if (!field) return true;
  const units = boundedPropertyUnits.get(field[1].toLowerCase());
  return !measurementValues(heading.slice(field[0].length), units, true).length;
}

function sectionQualifications(parts) {
  const active = [];
  let depth = 1;
  return parts.map(part => {
    const level = sectionDepth(part);
    if (level !== undefined) {
      while (active.at(-1) >= level) active.pop();
      depth = level;
    }
    if (qualifiedSection(part, level !== undefined) && active.at(-1) !== depth) active.push(depth);
    return active.length > 0;
  });
}

function columnHeaders(parts) {
  const headers = [];
  for (const [index, part] of parts.entries()) {
    const columns = part.match(/^(?:model columns|colonnes des systèmes)\s*:\s*(.*)$/iu);
    const first = part.match(/^(.+) in first column$/iu);
    const second = (parts[index + 1] ?? '').match(/^(.+) in second(?: column)?$/iu);
    if (columns) headers.push({index, labels:columns[1].split(',').map(model => [tidy(model)])});
    else if (first && second) {
      const labels = [first[1], second[1]].map(group => group.split(/\s+and\s+/iu).map(tidy));
      headers.push({index:index + 1, labels});
    }
  }
  return headers;
}

function quoteQuantifies(quote, excerpt, observation, {heading, units}) {
  // Parse complete labelled clauses. An unsupported expression cannot contribute a suffix.
  const expected = exactQuantity(observation.value, observation.unit, units);
  if (expected === undefined || !excerpt.includes(quote) || /^[^\S\r\n]*(?:>[^\S\r\n]*)*(?:`{3,}|~{3,})/mu.test(excerpt)) return false;
  // Preserve compatibility characters such as superscript footnote digits.
  const read = text => clauses(text.normalize('NFC').replace(/[^\S\r\n]+/gu, ' '));
  const sourceParts = read(excerpt);
  const parts = read(quote);
  const starts = sourceParts.flatMap((_, start) => parts.every((part, index) => sourceParts[start + index] === part) ? [start] : []);
  if (starts.length !== 1 || parts.length === 0) return false;
  // A source section heading still applies when the supplied quote begins at its field row.
  const qualified = sectionQualifications(sourceParts);
  const tables = columnHeaders(parts);
  if (tables.length > 1 || tables.length !== columnHeaders(sourceParts).length) return false;
  const [table] = tables;
  const model = tidy(observation.target.model);
  const positions = table?.labels.flatMap((models, index) => models.includes(model) ? [index] : []) ?? [];
  if (table && (table.labels.length < 2 || table.labels.some(models => models.includes('')) || positions.length !== 1)) return false;
  return parts.some((clause, index) => {
    const prefix = heading.exec(clause);
    if (!prefix || (table && index <= table.index) || qualified[starts[0] + index]) return false;
    const text = clause.slice(prefix[0].length);
    const sharedAcrossBoth = /\s+in both columns$/iu.test(text);
    const values = measurementValues(text.replace(/\s+in both columns$/iu, ''), units, Boolean(table));
    if (!table || sharedAcrossBoth) {
      return (!sharedAcrossBoth || table?.labels.length === 2) && values.length === 1 && values[0] === expected;
    }
    return values.length === table.labels.length && values[positions[0]] === expected;
  });
}

export function reviewClaim(input) {
  if (!isObject(input) || typeof input.id !== 'string' || !/^[a-z0-9][a-z0-9._:-]{0,95}$/iu.test(input.id) ||
      !fields.has(input.field) || !validScope(input.target) || !Object.hasOwn(input.target, 'model') || !Object.hasOwn(input.target, 'level') ||
      !isObject(input.claim) || !Array.isArray(input.sources) || input.sources.length > 12 ||
      !input.sources.every(validSource) || new Set(input.sources.map(row => row.id)).size !== input.sources.length ||
      !Array.isArray(input.observations) || input.observations.length > 32) throw new Error('SOURCE_REVIEW_CASE');
  const {id,field,target,claim,sources,observations} = input;
  const definition = fields.get(field);
  const {label,units} = definition;
  const inputById = new Map(sources.map(row => [row.id,row]));
  const values = new Map();
  let rejected = 0;
  for (const entry of observations) {
    const source = inputById.get(entry?.source);
    if (!source || entry.field !== field || !eligibleScope(target, entry.target) ||
        typeof entry.quote !== 'string' || !entry.quote.length ||
        !quoteQuantifies(entry.quote, source.excerpt, entry, definition)) {
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
