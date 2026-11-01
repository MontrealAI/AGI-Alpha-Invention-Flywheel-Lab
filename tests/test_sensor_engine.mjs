import test from 'node:test';
import assert from 'node:assert/strict';
import {parseCsv,constructSensor,toCsv} from '../docs/research/sensor-engine.mjs';
const temp = 'timestamp,temperature_c\n2026-07-01T10:00:00Z,34\n2026-07-01T12:00:00Z,30\n2026-07-02T10:00:00Z,35\n';
const hum = 'timestamp,humidity_pct\n2026-07-01T10:00:00Z,80\n2026-07-01T12:00:00Z,82\n';
test('constructs a historical indicator without classifying missing evidence as safe',()=>{
 const r=constructSensor({temperatureCsv:temp,humidityCsv:hum});
 assert.deepEqual(r.summary,{met:1,measured:2,unknown:1,coverage:2/3,days:2});
 assert.deepEqual(r.days.map(x=>[x.date,x.met,x.unknown]),[['2026-07-01',1,0],['2026-07-02',0,1]]);
 assert.equal(r.evidence[2].state,'unknown');
 assert.match(toCsv(r),/2026-07-02,0,0,1,/);
});
test('changes the generated sensor when the question changes',()=>{
 const a=constructSensor({temperatureCsv:temp,humidityCsv:hum,temperatureThreshold:32});
 const b=constructSensor({temperatureCsv:temp,humidityCsv:hum,temperatureThreshold:35});
 assert.equal(a.summary.met,1);assert.equal(b.summary.met,0);
});
test('conflicting duplicates are not silently averaged',()=>{
 const r=constructSensor({temperatureCsv:temp,humidityCsv:hum+'2026-07-01T10:00:00Z,10\n'});
 assert.equal(r.evidence[0].state,'unknown');assert.deepEqual(r.evidence[0].humidity_rows,[2,4]);
});
test('missing, invalid, and impossible values remain unknown',()=>{
 const r=constructSensor({temperatureCsv:temp,humidityCsv:'timestamp,humidity_pct\n2026-07-01T10:00:00Z,101\n2026-07-01T12:00:00Z,\n'});
 assert.equal(r.summary.measured,0);assert.equal(r.summary.unknown,3);
});
test('rejects malformed quotes and unreasonable thresholds',()=>{
 assert.throws(()=>parseCsv('timestamp,temperature_c\n"bad,42', ['timestamp','temperature_c']),/Unclosed/);
 assert.throws(()=>constructSensor({temperatureCsv:temp,humidityCsv:hum,humidityThreshold:101}),/Threshold/);
 const r=constructSensor({temperatureCsv:temp.replace('Z,34','+00:00,34'),humidityCsv:hum});
 assert.equal(r.summary.unknown,2);
});
test('supports quoted fields and rejects duplicate columns',()=>{
 assert.equal(parseCsv('timestamp,temperature_c,comment\n2026-07-01T10:00:00Z,32,"rare, important"',['timestamp','temperature_c'])[0].comment,'rare, important');
 assert.throws(()=>parseCsv('timestamp,temperature_c,timestamp\nx,3,y',['timestamp','temperature_c']),/unique/);
});
test('does not invent a successful measurement where no temporal join exists',()=>{
 const r=constructSensor({temperatureCsv:temp,humidityCsv:'timestamp,humidity_pct\n2025-01-01T10:00:00Z,80'});
 assert.equal(r.summary.measured,0);assert.equal(r.summary.coverage,0);
 assert.match(r.warning,/Unknown intervals/);
});
