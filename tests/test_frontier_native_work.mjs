import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createHash} from 'node:crypto';
import {evaluateMissionFiles, nativeWorkSchema} from '../docs/research/frontier-omega-alpha/frontier-native-work.mjs';
import {importMissionArtifacts, missionArtifactBytes, verifyMissionArtifact} from '../docs/research/frontier-omega-alpha/frontier-artifact-exchange.mjs';

const data = (name, content) => ({kind:'data',name,content,sha256:createHash('sha256').update(content).digest('hex')});

function zipped() {
  // Standard deflated one-file archive whose UTF-8 source is never interpreted.
  return Uint8Array.from(Buffer.from('UEsDBBQAAAAIAAAAIQD1u+gHKwAAACkAAAAHAAAAd29yay5weStKzCxOVQgqzSvJzE11LSrKL9JQKs4vLUpOVSguSawsVsjMSy0qUdLkAgBQSwECFAMUAAAACAAAACEA9bvoBysAAAApAAAABwAAAAAAAAAAAAAAgAEAAAAAd29yay5weVBLBQYAAAAAAQABADUAAABQAAAAAAA=','base64'));
}

test('archived content is received as exact original bytes and safe review copies', async () => {
  const raw = zipped();
  const file = new File([raw],'bundle.zip');
  const [archive, source] = await importMissionArtifacts(file,1);
  assert.equal(archive.kind,'archive');
  assert.deepEqual(missionArtifactBytes(archive),raw);
  assert.equal(source.name,'work.py');
  assert.equal(source.kind,'source');
  assert.equal(await verifyMissionArtifact(archive),true);
  await assert.rejects(importMissionArtifacts(new File([raw.subarray(0,-1)],'truncated.zip'),1),/ARTIFACT_ARCHIVE/);
});

test('exact boundary witness requires the entire set and checks the hard equality boundary', () => {
  const header = 'current_score,level_max_8,level_max_10\n';
  const good = data('comparison.csv',header+'5,3,2\n7,4,3\n8,4,4\n');
  const accepted = evaluateMissionFiles([data('comparison.csv',header+'5,3,2\n7,4,3\n')])[0];
  assert.equal(accepted.differingScores,'2');
  assert.deepEqual(accepted.ranges,[['5','5','3','2'],['7','7','4','3']]);
  assert.equal(evaluateMissionFiles([good])[0].reason,'TABLE_MISMATCH');
  assert.equal(evaluateMissionFiles([data('partial.csv',header+'5,3,2\n')])[0].disposition,'WITHHELD');
});

test('daily windows preserve absent days, zeros and original quality flags', () => {
  const source = data('observations.csv','date,amount,quality\n2024-01-01,12.0,\n2024-01-03,0.0,T\n2024-01-04,2.0,\n');
  const input = {schema:nativeWorkSchema,operation:'concentration',days:2,precision:1,dates:['2024-01-01','2024-01-04'],
    source:{file:source.name,sha256:source.sha256,url:'https://example.org/original',format:'csv',dateField:'date',values:['amount'],flags:['quality']}};
  const manifest = data('operation.json',JSON.stringify(input));
  const [checked] = evaluateMissionFiles([source,manifest]);
  assert.deepEqual(checked.output,{measuredDays:3,missingDays:1,total:'14.0',windowTotal:'2.0',
    maximumWindows:[['2024-01-03','2024-01-04']],percentageOfMeasuredTotal:'14.29',completeCoverage:false});
  assert.deepEqual(checked.rows[1],{date:'2024-01-02',published:false,values:{amount:null},flags:{quality:null}});
  assert.equal(checked.rows[2].flags.quality,'T');
  assert.equal(evaluateMissionFiles([manifest])[0].reason,'SOURCE_MISSING');
  assert.equal(evaluateMissionFiles([data(source.name, source.content+'\n'),manifest])[0].reason,'SOURCE_HASH');
});

test('successive quotes use chronological published dates and preserve the sign', () => {
  const source = data('quotes.json', JSON.stringify({observations:[{day:'2024-01-03',price:{v:'1.0200'}},{day:'2024-01-01',price:{v:'1.0150'}}]}));
  const plan = {schema:nativeWorkSchema,operation:'successive-changes',precision:4,dates:['2024-01-01','2024-01-03'],
    source:{file:source.name,sha256:source.sha256,url:'https://example.org/quotes',format:'json',list:'observations',dateField:'day',values:['price.v']}};
  const [receipt] = evaluateMissionFiles([source,data('operation.json',JSON.stringify(plan))]);
  assert.deepEqual(receipt.output[0].unquotedDates,['2024-01-02']);
  assert.deepEqual(receipt.output[0].largestSteps,[{from:'2024-01-01',to:'2024-01-03',amount:'0.0050',before:'1.0150',after:'1.0200'}]);
});


test('ties across long consecutive windows retain endpoints and the complete underlying calendar', () => {
  const dates = Array.from({length:3661},(_,i)=>new Date(Date.UTC(2020,0,1+i)).toISOString().slice(0,10));
  const source = data('zero-records.csv','date,amount\n'+dates.map(date=>`${date},0`).join('\n'));
  const plan = {schema:nativeWorkSchema,operation:'concentration',days:1831,precision:0,dates:[dates[0],dates.at(-1)],
    source:{file:source.name,sha256:source.sha256,url:'https://example.org/zero-days',format:'csv',dateField:'date',values:['amount']}};
  const [receipt] = evaluateMissionFiles([source,data('operation.json',JSON.stringify(plan))]);
  assert.equal(receipt.output.maximumWindows.length,1831);
  assert.deepEqual(receipt.output.maximumWindows[0],[dates[0],dates[1830]]);
  assert.deepEqual(receipt.output.maximumWindows.at(-1),[dates[1830],dates.at(-1)]);
  assert.equal(receipt.rows.length,3661);
});
