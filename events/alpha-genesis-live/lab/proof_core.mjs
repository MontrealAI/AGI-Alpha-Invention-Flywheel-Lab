// SPDX-License-Identifier: MIT
// MONTREAL.AI event-specific ORIGINAL supplementary verifier; not the Alpha Agent engine.
export const CORE_VERSION = 'proof-lab/v1.0.0';
const MAX_TEXT = 300000;
const MAX_ROWS = 1500;
const MAX_COLS = 32;
const MAX_CELL = 4096;

export function parseCSV(input) {
  if (typeof input !== 'string' || !input.trim()) throw new Error('CSV must be nonempty text.');
  if (input.length > MAX_TEXT) throw new Error('CSV is too large for the workshop checker.');
  let text = input.charCodeAt(0) === 0xfeff ? input.slice(1) : input;
  const rows = []; let row = []; let cell = ''; let quote = false; let started = false;
  function addCell() {
    if (cell.length > MAX_CELL) throw new Error('CSV cell exceeds the workshop limit.');
    row.push(cell); cell = ''; started = false;
    if (row.length > MAX_COLS) throw new Error('Too many columns.');
  }
  function addRow() {
    addCell();
    if (row.some(x => x !== '') || rows.length > 0) rows.push(row);
    row = [];
    if (rows.length > MAX_ROWS + 1) throw new Error('Too many data rows.');
  }
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quote) {
      if (c === '"') { if (text[i + 1] === '"') { cell += '"'; i++; } else { quote = false; } }
      else { cell += c; }
    } else if (c === '"') {
      if (cell.length || started) throw new Error('Invalid quoted CSV field.');
      quote = true; started = true;
    } else if (c === ',') addCell();
    else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; addRow(); }
    else { if (started) throw new Error('Unexpected data after a quoted field.'); cell += c; }
    if (cell.length > MAX_CELL) throw new Error('CSV cell exceeds the workshop limit.');
  }
  if (quote) throw new Error('Unclosed CSV quotation.');
  if (cell.length || row.length || started) addRow();
  if (rows.length < 2) throw new Error('CSV requires a header and at least one data row.');
  const header = rows[0];
  if (header.some(x => !x)) throw new Error('CSV header fields must not be empty.');
  if (new Set(header).size !== header.length) throw new Error('Duplicate column names are not allowed.');
  const records = rows.slice(1).map((r, i) => {
    if (r.length !== header.length) throw new Error(`CSV row ${i + 2} has ${r.length} columns; expected ${header.length}.`);
    return {line: i + 2, values: Object.fromEntries(header.map((h, j) => [h, r[j]]))};
  });
  return {header, records};
}

const sorted = xs => [...xs].sort((a, b) => a.localeCompare(b, 'en'));
const identity = x => String(x.sku) + '\u0000' + String(x.field);
function repeats(records, key) {
  const seen = new Set(), dup = new Set();
  for (const r of records) { const k = r.values[key]; if (seen.has(k)) dup.add(k); seen.add(k); }
  return sorted(dup);
}

export function compareCSV(aText, bText, key='sku') {
  const a = parseCSV(aText), b = parseCSV(bText);
  if (!a.header.includes(key) || !b.header.includes(key)) throw new Error(`Both CSVs need the ${key} key column.`);
  for (const [label, x] of [['A', a], ['B', b]]) {
    if (x.records.some(r => !r.values[key])) throw new Error(`Source ${label} contains an empty identifier.`);
  }
  const duplicateLeft = repeats(a.records, key), duplicateRight = repeats(b.records, key);
  const common = a.header.filter(x => x !== key && b.header.includes(x));
  const unexaminedLeft = a.header.filter(x => x !== key && !b.header.includes(x));
  const unexaminedRight = b.header.filter(x => x !== key && !a.header.includes(x));
  if (duplicateLeft.length || duplicateRight.length) {
    return {version:CORE_VERSION,status:'BLOCKED',key,reason:'Duplicate identifiers need human key-resolution; this supplementary checker does not multiply ambiguous pairs.',duplicateLeft,duplicateRight,unexaminedLeft,unexaminedRight,stats:{leftRows:a.records.length,rightRows:b.records.length},expectation:null};
  }
  const am = new Map(a.records.map(r => [r.values[key], r]));
  const bm = new Map(b.records.map(r => [r.values[key], r]));
  const unmatchedLeft = sorted([...am.keys()].filter(x => !bm.has(x)));
  const unmatchedRight = sorted([...bm.keys()].filter(x => !am.has(x)));
  const conflicts = [];
  for (const [k, ar] of am) if (bm.has(k)) {
    const br = bm.get(k);
    for (const field of common) if (ar.values[field] !== br.values[field]) {
      conflicts.push({sku:k,field,left:ar.values[field],right:br.values[field],leftLine:ar.line,rightLine:br.line});
    }
  }
  conflicts.sort((x,y) => identity(x).localeCompare(identity(y),'en'));
  const expectation = {unmatchedLeft,unmatchedRight,conflicts:conflicts.map(({sku,field})=>({sku,field}))};
  return {version:CORE_VERSION,status:'COMPUTED_NOT_APPROVED',key,duplicateLeft,duplicateRight,unexaminedLeft,unexaminedRight,stats:{leftRows:a.records.length,rightRows:b.records.length,matchedIdentifiers:a.records.length-unmatchedLeft.length,conflicts:conflicts.length,unmatchedLeft:unmatchedLeft.length,unmatchedRight:unmatchedRight.length},conflicts,unmatchedLeft,unmatchedRight,expectation};
}

function normalizeIDs(x, label) {
  if (!Array.isArray(x) || x.some(y => typeof y !== 'string')) throw new Error(`${label} must be an array of identifier strings.`);
  if (x.length !== new Set(x).size) throw new Error(`${label} contains duplicate claims.`);
  return sorted(x);
}
function normalizeConflicts(x) {
  if (!Array.isArray(x) || x.some(y => !y || typeof y.sku !== 'string' || typeof y.field !== 'string')) throw new Error('conflicts must be objects with sku and field strings.');
  const ids=x.map(identity);
  if (ids.length !== new Set(ids).size) throw new Error('conflicts contains duplicate claims.');
  return sorted(ids);
}
function delta(found,expected) {
  const f=new Set(found), e=new Set(expected);
  return {missing:expected.filter(x=>!f.has(x)),unsupported:found.filter(x=>!e.has(x)),pass:found.length===expected.length && found.every(x=>e.has(x))};
}
export function verifyClaim(compare, claim) {
  if (!compare || compare.status==='BLOCKED') return {status:'BLOCKED',reason:compare?.reason||'No verified comparison.',checks:[]};
  if (!claim || typeof claim !== 'object') throw new Error('AI claim must be a JSON object.');
  const expected=compare.expectation;
  const checks=[
    {label:'Only in A',...delta(normalizeIDs(claim.unmatchedLeft,'unmatchedLeft'),expected.unmatchedLeft)},
    {label:'Only in B',...delta(normalizeIDs(claim.unmatchedRight,'unmatchedRight'),expected.unmatchedRight)},
    {label:'Conflicting fields',...delta(normalizeConflicts(claim.conflicts),normalizeConflicts(expected.conflicts))}
  ];
  return {status:checks.every(x=>x.pass)?'CHECKS_PASS':'CHECKS_FAIL',checks,scope:'Only the structured claims were checked against exact text equality. Free-text summary, source truth, economic impact and decision authority were NOT independently verified.'};
}

export function canonicalClaim(comparison) {
  if (!comparison.expectation) throw new Error('Blocked comparison has no canonical claim.');
  return {summary:'Calculated differences only; source authority remains unresolved.',...comparison.expectation};
}
