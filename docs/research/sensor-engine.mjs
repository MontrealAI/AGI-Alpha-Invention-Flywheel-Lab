/* AGI ALPHA Retroactive Sensor Lab — deterministic, local-only reference engine. */
const LIMIT = 100000;

export function parseCsv(text, required) {
  if (typeof text !== 'string' || text.length > 6000000) throw Error('CSV must be text under 6 MB.');
  const rows = [];
  let row = [], field = '', quoted = false, closed = false;
  const pushField = () => { row.push(field); field = ''; closed = false; };
  const pushRow = () => { pushField(); if (row.some(v => v.trim())) rows.push(row); row = []; };
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') { quoted = false; closed = true; }
      else field += c;
    } else if (c === '"' && !field && !closed) quoted = true;
    else if (c === ',') pushField();
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      pushRow();
    } else if (closed && c !== ' ' && c !== '\t') throw Error('Characters after quoted CSV field.');
    else if (!closed) field += c;
  }
  if (quoted) throw Error('Unclosed quoted CSV field.');
  if (field || row.length || closed) pushRow();
  if (rows.length < 2) throw Error('CSV needs a header and at least one observation.');
  if (rows.length - 1 > LIMIT) throw Error('CSV exceeds the 100,000-observation limit.');
  const cols = rows.shift().map(s => s.trim().replace(/^\uFEFF/, ''));
  if (new Set(cols).size !== cols.length || required.some(c => !cols.includes(c))) {
    throw Error('CSV must have unique headers including ' + required.join(', ') + '.');
  }
  const records = rows.map((values, i) => {
    if (values.length !== cols.length) throw Error('Malformed CSV observation ' + (i + 2) + '.');
    return Object.fromEntries(cols.map((c, j) => [c, values[j].trim()] ).concat([['_row', i + 2]]));
  });
  return records;
}

function normalize(rows, field, unit) {
  const byTime = new Map();
  const issues = [];
  rows.forEach(row => {
    const time = row.timestamp;
    if (!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(time) || !Number.isFinite(Date.parse(time)) || new Date(time).toISOString().replace('.000Z','Z') !== time) {
      issues.push({row: row._row, reason: 'Invalid UTC timestamp in ' + field}); return;
    }
    const raw = row[field];
    const n = raw === '' ? NaN : Number(raw);
    const ok = Number.isFinite(n) && (unit !== '%' || n >= 0 && n <= 100);
    const next = {time, value: ok ? n : null, row: row._row, invalid: !ok};
    if (!byTime.has(time)) byTime.set(time, [next]);
    else byTime.get(time).push(next);
  });
  return {byTime, issues};
}

export function constructSensor({temperatureCsv, humidityCsv, temperatureThreshold = 32, humidityThreshold = 70}) {
  const t = Number(temperatureThreshold), h = Number(humidityThreshold);
  if (!Number.isFinite(t) || !Number.isFinite(h) || h < 0 || h > 100 || t < -120 || t > 100) throw Error('Thresholds must be finite; humidity 0–100%, temperature −120–100°C.');
  const temperature = normalize(parseCsv(temperatureCsv, ['timestamp','temperature_c']), 'temperature_c', '°C');
  const humidity = normalize(parseCsv(humidityCsv, ['timestamp','humidity_pct']), 'humidity_pct', '%');
  const all = [...new Set([...temperature.byTime.keys(), ...humidity.byTime.keys()])].sort();
  const byDay = new Map(), evidence = [];
  for (const timestamp of all) {
    const a = temperature.byTime.get(timestamp) || [], b = humidity.byTime.get(timestamp) || [];
    const pair = a.length === 1 && b.length === 1 && !a[0].invalid && !b[0].invalid;
    const state = !pair ? 'unknown' : a[0].value >= t && b[0].value >= h ? 'threshold_met' : 'threshold_not_met';
    const date = timestamp.slice(0,10);
    if (!byDay.has(date)) byDay.set(date, {date, measured:0, met:0, not_met:0, unknown:0});
    const d = byDay.get(date);
    if (state === 'threshold_met') { d.met++; d.measured++; }
    else if (state === 'threshold_not_met') { d.not_met++; d.measured++; }
    else d.unknown++;
    evidence.push({timestamp, state, temperature_c:pair?a[0].value:null, humidity_pct:pair?b[0].value:null,
      temperature_rows:a.map(x=>x.row),humidity_rows:b.map(x=>x.row),
      reason:pair?'Exact-UTC-time join; both observed values':a.length !== 1 || b.length !== 1?'Missing or duplicated archive timestamp':'Invalid or missing archived value'});
  }
  const days = [...byDay.values()].map(d => ({...d, fraction_observed:d.measured?d.met/d.measured:null, fully_resolved:d.unknown===0}));
  const total = days.reduce((s,d)=>({met:s.met+d.met,measured:s.measured+d.measured,unknown:s.unknown+d.unknown}),{met:0,measured:0,unknown:0});
  return {schema_version:1, measurement:'Co-occurrence of temperature and humidity thresholds at identical archived UTC timestamps',
    hypothesis_not_fact:'This is a constructed indicator, not a measurement of indoor temperature, human exposure, causal harm, or a verified economic outcome.',
    rule:{temperature_c_gte:t,humidity_pct_gte:h,join:'exact_utc_timestamp',imputation:'none',duplicate_policy:'unknown'},
    summary:{...total,coverage:total.measured+total.unknown?total.measured/(total.measured+total.unknown):null,days:days.length},
    days,evidence,source_errors:[...temperature.issues,...humidity.issues],
    warning:all.length?'Input provenance and sensor validity are not independently certified. Unknown intervals are never counted as safe.':'No compatible valid timestamp found; do not infer absence of exposure.'};
}

export function toCsv(result) {
  return ['date,threshold_met,threshold_not_met,unknown,observed_fraction',
    ...result.days.map(d => [d.date,d.met,d.not_met,d.unknown,d.fraction_observed===null?'':d.fraction_observed.toFixed(6)].join(','))].join('\n')+'\n';
}
