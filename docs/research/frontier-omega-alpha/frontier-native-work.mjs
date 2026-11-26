export const nativeWorkSchema = 'frontier/source-calculation-v1';
const receiptSchema = 'frontier/source-calculation-receipt-v1';
const day = /^\d{4}-\d\d-\d\d$/u;
const digits = /^(?:0|[1-9]\d{0,17})$/u;
const hash = /^[a-f0-9]{64}$/u;
const dayMillis = 86_400_000;

function need(condition, code = 'INVALID_INPUT') {
  if (!condition) throw new Error(code);
}

function csv(value) {
  const text = value.replace(/^\ufeff/u, '');
  const rows = [];
  let row = [], field = '', quoted = false, closed = false;
  for (let index = 0; index <= text.length; index++) {
    const char = text[index] ?? '\n';
    if (quoted) {
      if (char !== '"') field += char;
      else if (text[index + 1] === '"') { field += char; index++; }
      else { quoted = false; closed = true; }
    } else if (char === ',' || char === '\n' || char === '\r') {
      row.push(field); field = ''; closed = false;
      if (char !== ',') {
        if (char === '\r' && text[index + 1] === '\n') index++;
        if (row.length > 1 || row[0]) rows.push(row);
        row = [];
      }
    } else if (!field && !closed && char === '"') quoted = true;
    else { need(!closed && char !== '"'); field += char; }
  }
  need(!quoted && rows.length > 0);
  const headings = rows.shift();
  need(new Set(headings).size === headings.length && rows.every(line => line.length === headings.length));
  return {headings, rows};
}

function scalar(value, precision) {
  if (value === undefined || value === null || value === '') return null;
  need(typeof value === 'string');
  const parts = /^(-?)(0|[1-9]\d{0,17})(?:\.(\d{1,12}))?$/u.exec(value);
  need(parts && (parts[3]?.length ?? 0) <= precision);
  return (parts[1] ? -1n : 1n) * BigInt(parts[2] + (parts[3] ?? '').padEnd(precision,'0'));
}

function decimal(value, precision) {
  if (value === null) return null;
  const negative = value < 0n;
  const magnitude = String(negative ? -value : value).padStart(precision + 1, '0');
  return (negative ? '-' : '') + (precision ? `${magnitude.slice(0,-precision)}.${magnitude.slice(-precision)}` : magnitude);
}

function millisecond(value) {
  need(typeof value === 'string' && day.test(value));
  const stamp = Date.parse(value);
  need(Number.isFinite(stamp) && new Date(stamp).toISOString().slice(0,10) === value);
  return stamp;
}

function calendar(first, last) {
  const start = millisecond(first), end = millisecond(last);
  need(end >= start && end - start <= 3660 * dayMillis);
  return Array.from({length:(end-start)/dayMillis + 1},(_,index) => new Date(start + index * dayMillis).toISOString().slice(0,10));
}

function path(record, selector) {
  return selector.split('.').reduce((current,key) => current && Object.hasOwn(current,key) ? current[key] : undefined, record);
}

function rowsFor(input, data) {
  const {format, dateField, values, flags = [], list} = input.source;
  const {dates, precision} = input;
  need(typeof dateField === 'string' && Number.isInteger(precision) && precision >= 0 && precision <= 12);
  need(Array.isArray(values) && values.length > 0 && values.length <= 8 && values.every(field => typeof field === 'string')
    && new Set(values).size === values.length && Array.isArray(flags) && flags.length <= 8 && flags.every(field => typeof field === 'string'));
  need(values.every(field => !flags.includes(field)));
  const datesInOrder = calendar(dates?.[0],dates?.[1]);
  const available = new Map();
  function remember(date, valueOf) {
    millisecond(date);
    if (date < datesInOrder[0] || date > datesInOrder.at(-1)) return;
    need(!available.has(date), 'DUPLICATE_DATE');
    const amounts = values.map(field => scalar(valueOf(field),precision));
    const indicators = flags.map(field => valueOf(field) ?? '');
    need(indicators.every(value => typeof value === 'string' && value.length <= 128));
    available.set(date, {amounts, indicators});
  }
  if (format === 'csv') {
    const {headings, rows} = csv(data.content), columns = new Map(headings.map((name,index)=>[name,index]));
    need([dateField,...values,...flags].every(field => columns.has(field)));
    for (const row of rows) remember(row[columns.get(dateField)],field => row[columns.get(field)]);
  } else {
    need(format === 'json' && typeof list === 'string');
    const rows = path(JSON.parse(data.content.replace(/^\ufeff/u, '')),list);
    need(Array.isArray(rows));
    for (const row of rows) remember(path(row,dateField),field => path(row,field));
  }
  const ordered = datesInOrder.map(date => ({date, published:available.has(date), ...available.get(date)}));
  return {ordered, values, flags};
}

function concentration(rows, width, precision) {
  need(Number.isSafeInteger(width) && width >= 2 && width <= rows.length);
  need(rows.every(row => !row.amounts || row.amounts[0] === null || row.amounts[0] >= 0n));
  const valid = rows.filter(row => row.amounts?.[0] != null);
  const total = valid.reduce((sum,row) => sum + row.amounts[0],0n);
  let maximum = null, windows = [], sum = 0n, missing = 0;
  for (let index = 0; index < rows.length; index++) {
    const incoming = rows[index].amounts?.[0] ?? null;
    sum += incoming ?? 0n;
    if (incoming === null) missing++;
    if (index >= width) {
      const outgoing = rows[index-width].amounts?.[0] ?? null;
      sum -= outgoing ?? 0n;
      if (outgoing === null) missing--;
    }
    if (index + 1 < width || missing) continue;
    if (maximum === null || sum > maximum) { maximum = sum; windows = []; }
    if (sum === maximum) windows.push([rows[index-width+1].date,rows[index].date]);
  }
  const share = maximum !== null && total > 0n ? decimal((2n * maximum * 10_000n + total) / (2n * total),2) : null;
  return {measuredDays:valid.length, missingDays:rows.length-valid.length,
    total:decimal(total,precision), windowTotal:decimal(maximum,precision), maximumWindows:windows,
    percentageOfMeasuredTotal:share, completeCoverage:valid.length === rows.length};
}

function changes(rows, values, precision) {
  return values.map((series,index) => {
    const published = rows.filter(row => row.amounts?.[index] != null);
    let largest = null, steps = [];
    for (let i = 1; i < published.length; i++) {
      const left = published[i-1], right = published[i];
      const difference = right.amounts[index] - left.amounts[index];
      const absolute = difference < 0n ? -difference : difference;
      if (largest === null || absolute > largest) { largest = absolute; steps = []; }
      if (absolute === largest) steps.push({from:left.date,to:right.date,
        amount:decimal(difference,precision),before:decimal(left.amounts[index],precision),after:decimal(right.amounts[index],precision)});
    }
    return {series, publishedDates:published.map(row=>row.date), unquotedDates:rows.filter(row=>row.amounts?.[index] == null).map(row=>row.date),
      largestAbsoluteChange:decimal(largest,precision), largestSteps:steps};
  });
}

function sourceCalculation(input, files) {
  const {source, operation, precision} = input;
  need(source && typeof source.file === 'string' && hash.test(source.sha256 ?? '') && typeof source.url === 'string');
  let url;
  try { url = new URL(source.url); } catch { throw Error('INVALID_INPUT'); }
  need(url.protocol === 'https:' && !url.username && !url.password);
  const raw = files.find(file => file.name === source.file && file.sha256 === source.sha256 && file.kind === 'data');
  need(raw, files.some(file => file.name === source.file) ? 'SOURCE_HASH' : 'SOURCE_MISSING');
  const {ordered, values, flags} = rowsFor(input, raw);
  const units = source.units ?? {};
  need(typeof units === 'object' && !Array.isArray(units)
    && Object.entries(units).every(([field,label]) => values.includes(field) && typeof label === 'string'
      && label.length <= 32 && /^[\p{L}\p{N}²³°% /._-]+$/u.test(label)));
  const output = operation === 'concentration' ? concentration(ordered, input.days, precision) : changes(ordered, values, precision);
  return {source:{file:raw.name,sha256:raw.sha256,url:url.href}, operation, precision, output,
    ...(Object.keys(units).length && {units}), rows:ordered.map(row => ({date:row.date, published:row.published,
      values:Object.fromEntries(values.map((field,index)=>[field,decimal(row.amounts?.[index] ?? null,precision)])),
      flags:Object.fromEntries(flags.map((field,index)=>[field,row.indicators?.[index] ?? null]))}))};
}

function band(level, maximum) {
  return [1n,2n,3n,4n].find(k => 4n * level <= k * maximum);
}

function boundaryCalculation(file) {
  const header = /^current_score,level_max_([1-9]\d{0,17}),level_max_([1-9]\d{0,17})(?:\r?\n|$)/u.exec(file.content.replace(/^\ufeff/u,''));
  if (!header) return null;
  const [a,b] = header.slice(1).map(BigInt);
  const cap = a < b ? a : b;
  const breakpoints = [0n,cap+1n,...[a,b].flatMap(m => [1n,2n,3n].map(k => k*m/4n+1n)).filter(k => k<=cap)];
  const sorted = [...new Set(breakpoints)].sort((x,y) => x < y ? -1 : x > y ? 1 : 0);
  const ranges = sorted.slice(0,-1).flatMap((start,i) => {
    const left = band(start,a), right = band(start,b);
    return left === right ? [] : [[start, sorted[i+1]-1n,left,right]];
  });
  const {rows} = csv(file.content);
  const seen = new Set();
  const rowsAgree = rows.every(([score,left,right]) => {
    if (!digits.test(score) || !/^[1-4]$/u.test(left) || !/^[1-4]$/u.test(right) || seen.has(score)) return false;
    seen.add(score);
    const value = BigInt(score);
    return value <= cap && left !== right && band(value,a) === BigInt(left) && band(value,b) === BigInt(right);
  });
  const count = ranges.reduce((sum,[start,end])=>sum+end-start+1n,0n);
  need(rowsAgree && BigInt(rows.length) === count, 'TABLE_MISMATCH');
  return {operation:'decision-boundaries', scope:'equal-quartiles-integer-scores', maxima:[String(a),String(b)],
    comparedScores:String(cap+1n), differingScores:String(count), ranges:ranges.map(range=>range.map(String))};
}

/** The installed operations interpret data only. A supplied receipt or code cannot activate an operation. */
export function evaluateMissionFiles(files) {
  const results = [];
  for (const file of files) {
    if (file.kind !== 'data') continue;
    let selected = false;
    try {
      let computed = null;
      if (/\.csv$/iu.test(file.name)) {
        selected = /^\ufeff?current_score,level_max_\d+,level_max_\d+[\r\n]/u.test(file.content);
        if (selected) computed = boundaryCalculation(file);
      } else if (/\.json$/iu.test(file.name)) {
        const input = JSON.parse(file.content.replace(/^\ufeff/u,''));
        selected = input?.schema === nativeWorkSchema;
        if (selected) {
          need(['concentration','successive-changes'].includes(input.operation));
          need(input.operation !== 'concentration' || input.source?.values?.length === 1);
          computed = sourceCalculation(input,files);
        }
      }
      if (computed) results.push({schema:receiptSchema, disposition:'VERIFIED_CALCULATION', proof:{file:file.name,sha256:file.sha256}, ...computed});
      else if (selected) throw Error('INVALID_INPUT');
    } catch (error) {
      if (selected) results.push({disposition:'WITHHELD', file:file.name, reason:error.message});
    }
  }
  return results;
}
