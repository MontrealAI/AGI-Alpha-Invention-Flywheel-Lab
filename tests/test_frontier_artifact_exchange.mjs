import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash, webcrypto} from 'node:crypto';
import {File} from 'node:buffer';
import {readMissionArtifact, inspectReturnedWork} from '../docs/research/frontier-omega-alpha/frontier-artifact-exchange.mjs';
import {createMission, reviseMission, addMissionArtifacts, removeMissionArtifact, exportMission, importMission} from '../docs/research/frontier-omega-alpha/frontier-mission.mjs';
import {fingerprint} from '../docs/research/frontier-omega-alpha/outcome-receipt.mjs';
import {reviewClaim} from '../docs/research/frontier-omega-alpha/dpp-source-review.mjs';

globalThis.crypto ??= webcrypto;

test('a claimed assistant file and an inline example are distinct from file possession', () => {
  const work = '[Get code](sandbox:/mnt/data/check%20tool.py)\n\n```python\nraise RuntimeError()\n```';
  assert.deepEqual(inspectReturnedWork(work), {missing:['check tool.py'], sourceSnippet:true,sources:[],hasTable:false});
  assert.deepEqual(inspectReturnedWork(work, [{name:'check tool.py'}]), {missing:[], sourceSnippet:true,sources:[],hasTable:false});
  assert.deepEqual(inspectReturnedWork('[file](sandbox:/mnt/data/..%2fprivate.py)'), {missing:[], sourceSnippet:false,sources:[],hasTable:false});
  assert.deepEqual(inspectReturnedWork('[file](sandbox:/mnt/data/analysis/run.py).').missing, ['run.py']);
  assert.deepEqual(inspectReturnedWork('https://example.org/mnt/data/remote.py').missing, []);
});

test('working source preserves exact UTF-8 bytes across revision and checkpoint without evaluating it', async () => {
  const bytes = Buffer.from('\ufeff# Test\r\nraise RuntimeError("source remains inert")\r\n');
  const file = await readMissionArtifact(new File([bytes], 'experiment.py'), 1);
  assert.equal(file.sha256, createHash('sha256').update(bytes).digest('hex'));
  assert.deepEqual(Buffer.from(file.content), bytes);
  const first = createMission('Check the candidate');
  const mission = reviseMission(addMissionArtifacts(first, [file, file]), 'Continue the source check');
  const checkpoint = await exportMission(mission);
  assert.equal(checkpoint.mission.workFiles.length, 1);
  const restored = await importMission(JSON.stringify(checkpoint));
  assert.equal(restored.workFiles[0].revision, 1);
  assert.deepEqual(Buffer.from(restored.workFiles[0].content), bytes);
  const tampered = structuredClone(checkpoint.mission);
  tampered.workFiles[0].content = tampered.workFiles[0].content.replace('Test', 'Fake');
  await assert.rejects(importMission({mission:tampered, sha256:await fingerprint(tampered)}), /MISSION_ARTIFACT/);
});

test('review intake rejects unsafe names, disallowed binaries, invalid UTF-8 and malformed structured data', async () => {
  for (const file of [
    new File(['echo'], '../run.py'), new File(['echo'], 'CON.txt'), new File(['x'], 'module.exe'),
    new File([Uint8Array.of(0xff)], 'tool.py'), new File(['{'], 'result.json'),
    new File(['{"nbformat":4}'], 'study.ipynb'),
  ]) await assert.rejects(readMissionArtifact(file, 1));
  assert.equal((await readMissionArtifact(new File(['{"nbformat":4,"cells":[]}'], 'study.ipynb'), 1)).kind, 'notebook');
});

test('removing one exact version permits corrected files to enter the same full mission', async () => {
  const versions = await Promise.all(Array.from({length:8}, (_,n) =>
    readMissionArtifact(new File([`Result version ${n}`], 'result.txt'), 1)));
  const full = addMissionArtifacts(createMission('Original goal'), versions);
  const updated = reviseMission(full, 'Recheck the result');
  const correction = await readMissionArtifact(new File(['Corrected result'], 'result.txt'), 2);
  assert.throws(() => addMissionArtifacts(updated, [correction]), /MISSION_ARTIFACT/);
  const continued = addMissionArtifacts(removeMissionArtifact(updated, versions[0]), [correction]);
  const reopened = await importMission(await exportMission(continued));
  assert.equal(reopened.originalAmbition, 'Original goal');
  assert.deepEqual(reopened.workFiles, [...versions.slice(1), correction]);
});

test('quantity checks reject exponents, tolerances and range suffixes as independent measurements', () => {
  const target = {model:'Example Pack',level:'system'};
  const review = (quote, value) => reviewClaim({
    id:'weight', target, field:'batteryWeight', claim:{value,unit:'kg'},
    sources:[{id:'datasheet',excerpt:quote,url:'https://example.org/data',locator:'table',sha256:'a'.repeat(64)}],
    observations:[{source:'datasheet',target,field:'batteryWeight',quote,value,unit:'kg'}],
  }).decision;
  assert.equal(review('Net battery weight: 6.4e1 kg.', 1), 'insufficient');
  assert.equal(review('Net battery weight: 6.4e+1 kg.', 1), 'insufficient');
  assert.equal(review('Net battery weight: 64 ± 2 kg.', 2), 'insufficient');
  assert.equal(review('Net battery weight: 64 ± 2 kg.', 64), 'supported');
  assert.equal(review('Net battery weight: 64 (±2) kg.', 64), 'supported');
  assert.equal(review('Net battery weight: 60 – 68 kg.', 68), 'insufficient');
  assert.equal(review('Net battery weight: 1/2 kg.', 2), 'insufficient');
  assert.equal(review('Net battery weight: 1 200 kg.', 200), 'insufficient');
  assert.equal(review('Model columns: First Pack, Example Pack, Third Pack. Net battery weights by column: 64 / 80 / 100 kg.', 80), 'supported');
});

test('compound dimensions are not field measurements, while same-unit table columns remain usable', () => {
  const target = {model:'Example Pack',level:'system'};
  const review = (quote, value, field = 'batteryWeight', unit = 'kg') => reviewClaim({
    id:'field-check',target,field,claim:{value,unit},
    sources:[{id:'table',excerpt:quote,url:'https://example.org/data',locator:'table',sha256:'f'.repeat(64)}],
    observations:[{source:'table',target,field,quote,value,unit}],
  }).decision;
  assert.equal(review('Specific capacity: 100 Ah/kg.',100,'batteryCapacity','Ah'), 'insufficient');
  assert.equal(review('Rated capacity: 100 Ah÷kg.',100,'batteryCapacity','Ah'), 'insufficient');
  assert.equal(review('Rated capacity: 100 Ah／kg.',100,'batteryCapacity','Ah'), 'insufficient');
  for (const separator of ["'", '’', '_']) {
    assert.equal(review(`Rated capacity: 1${separator}200 mAh.`,200,'batteryCapacity','mAh'), 'insufficient');
  }
  assert.equal(review('Mass per unit energy: 10 kg/kWh.',10), 'insufficient');
  assert.equal(review('Mass per unit energy: 10 kg per kWh.',10), 'insufficient');
  assert.equal(review('Mass relationship: 10 kg·m⁻³.',10), 'insufficient');
  assert.equal(review('Experimental ratio: 100 Ah / 5 kg.',5), 'insufficient');
  assert.equal(review('Specified net weight: 1,200 kg.',1.2), 'insufficient');
  assert.equal(review('Net battery weight: < 64 kg.',64), 'insufficient');
  assert.equal(review('Net battery weight: 64 to 68 kg.',68), 'insufficient');
  assert.equal(review('Table of weights: 72.2 kg / 68.5 kg.',72.2), 'insufficient');
  const table = 'Model columns: Example Pack, Second Pack. Table of weights: 72.2 kg / 68.5 kg.';
  assert.equal(review(table,72.2), 'supported');
  assert.equal(review(table,68.5), 'insufficient');
});

test('source excerpts cannot hide a qualifier or pass an unrelated field heading', () => {
  const target = {model:'Example Pack',level:'system'};
  const review = (excerpt, quote = excerpt, field = 'batteryWeight', unit = 'kg', value = 64) => reviewClaim({
    id:'clause-check',target,field,claim:{value,unit},
    sources:[{id:'table',excerpt,url:'https://example.org/data',locator:'table',sha256:'a'.repeat(64)}],
    observations:[{source:'table',target,field,quote,value,unit}],
  }).decision;
  for (const quote of ['Upper bound for net battery weight: 64 kg.', 'Not the net battery weight: 64 kg.',
    'Packaged weight: 64 kg.', 'Weight: 64 kg / 80 kg.', 'Manual mentions columns. Weight: 64 / 80 kg.']) {
    assert.equal(review(quote), 'insufficient');
  }
  assert.equal(review('Not the net battery weight: 64 kg.', 'net battery weight: 64 kg.'), 'insufficient');
  assert.equal(review('Net battery weight: 64 kg (estimate).', 'Net battery weight: 64 kg'), 'insufficient');
  assert.equal(review('Example R2. Complete battery net weight: 64 kg.', 'Complete battery net weight: 64 kg.'), 'supported');
  for (const quote of ['Less than the rated battery capacity: 64 Ah.', 'Capacity: 64 Ah.']) {
    assert.equal(review(quote, quote, 'batteryCapacity', 'Ah'), 'insufficient');
  }
  for (const quote of ['Inverter nominal voltage: 64 V.', 'Rated AC voltage: 64 V.', 'Nominal voltage: 64 Vac.']) {
    assert.equal(review(quote, quote, 'nominalVoltage', 'V'), 'insufficient');
  }
  const footnote = 'Net battery weight: 184¹ kg.';
  assert.equal(review(footnote, footnote, 'batteryWeight', 'kg', 1841), 'insufficient');
  assert.equal(review(footnote, footnote, 'batteryWeight', 'kg', 184), 'insufficient');
  const french = 'Tension nominale : 64 Vdc.';
  assert.equal(review(french, french, 'nominalVoltage', 'V'), 'supported');
  const accented = 'Capacite\u0301 nominale : 0,234 Ah.';
  assert.equal(review(accented, accented, 'batteryCapacity', 'mAh', 234), 'supported');
});

test('a malformed supplied scope cannot erase a comparison constraint', () => {
  const target = {model:'Example Pack',version:'2',level:'system'};
  const quote = 'Net battery weight: 64 kg.';
  const packet = {id:'typed-scope',target,field:'batteryWeight',claim:{value:64,unit:'kg'},
    sources:[{id:'table',excerpt:quote,url:'https://example.org/data',locator:'table',sha256:'a'.repeat(64)}],
    observations:[{source:'table',target,field:'batteryWeight',quote,value:64,unit:'kg'}],
  };
  assert.equal(reviewClaim(packet).decision, 'supported');
  for (const version of [2, true, null, {}, ' ']) {
    assert.throws(() => reviewClaim({...packet,target:{...target,version}}), /SOURCE_REVIEW_CASE/);
    const observations = [{...packet.observations[0],target:{...target,version}}];
    assert.equal(reviewClaim({...packet,observations}).decision, 'insufficient');
  }
});

test('a multi-model row binds the value to its exact supervised column label', () => {
  const review = (excerpt, values, quote = excerpt, model = 'Beta Pack') => {
    const target = {model,level:'system'};
    return reviewClaim({id:'column',target,field:'batteryWeight',claim:{value:72.2,unit:'kg'},
      sources:[{id:'table',excerpt,url:'https://example.org/data',locator:'rows',sha256:'a'.repeat(64)}],
      observations:values.map(value => ({source:'table',target,field:'batteryWeight',quote,value,unit:'kg'})),
    });
  };
  const row = 'Weight: 72.2 kg / 68.5 kg.';
  const explicit = `Model columns: Alpha Pack, Beta Pack. ${row}`;
  assert.equal(review(explicit,[72.2]).decision, 'insufficient');
  assert.equal(review(explicit,[72.2,68.5]).decision, 'contradicted');
  assert.equal(review(explicit,[72.2],explicit,'Alpha Pack').decision, 'supported');
  assert.equal(review(explicit,[68.5],row).decision, 'insufficient');
  assert.equal(review(explicit,[68.5],explicit,'Beta').decision, 'insufficient');
  assert.equal(review(`Model columns: Beta Pack, Beta Pack. ${row}`,[72.2]).decision, 'insufficient');
  assert.equal(review(`Model columns: Beta¹ Pack, Alpha Pack. ${row}`,[72.2],undefined,'Beta1 Pack').decision, 'insufficient');
  assert.equal(review('Alpha Pack and Alpha Plus in first column. Beta and Beta Pack in second. Weight: 72.2 kg in both columns.',[72.2]).decision, 'supported');
  assert.equal(review('Model columns: Alpha Pack, Beta Pack, Extra Pack. Weight: 72.2 kg in both columns.',[72.2]).decision, 'insufficient');
  assert.equal(review('Model columns: Alpha Pack, Beta Pack. Weight: 72.2 kg.',[72.2]).decision, 'insufficient');
  const example = `Model columns: Beta Pack, Alpha Pack.\n${row}`;
  const source = 'Model columns: Alpha Pack, Beta Pack.\n    ' + example;
  assert.equal(review(source,[72.2],example).decision, 'insufficient');
  assert.equal(review(source,[72.2,68.5]).decision, 'contradicted');
});

test('a qualified source section cannot support exact readings or be cropped to remove its heading', () => {
  const target = {model:'Example Pack',level:'system'};
  const row = 'Net battery weight: 64 kg.';
  const review = (excerpt, quote = excerpt) => reviewClaim({
    id:'section-check',target,field:'batteryWeight',claim:{value:64,unit:'kg'},
    sources:[{id:'table',excerpt,url:'https://example.org/data',locator:'section',sha256:'a'.repeat(64)}],
    observations:[{source:'table',target,field:'batteryWeight',quote,value:64,unit:'kg'}],
  }).decision;
  for (const heading of ['Maximum values …\n', 'Upper limits; ', 'Table 3 — Estimates\n', 'Table 3 - Estimates\n',
    'Data (approximate). ', 'Valeurs maximales\n', 'Limite supérieure; ', 'À titre indicatif\n', 'Données provisoires\n',
    '## Maximum values\n', '• Upper limits; ', '- Upper limits\n', '**Estimated values**\n', '> Upper limits\n',
    '<h3>Maximum values</h3>\n']) {
    const excerpt = heading + row;
    assert.equal(review(excerpt), 'insufficient');
    assert.equal(review(excerpt, row), 'insufficient');
  }
  assert.equal(review('Maximum continuous charging/discharging current: 30 A.\n' + row), 'supported');
  assert.equal(review('Maximum operating current: 30 A.\n' + row), 'supported');
  assert.equal(review('Maximum discharge current: 30 A.\n' + row), 'supported');
  assert.equal(review('Maximum charging/discharging current: 25 / 30 A.\n' + row), 'supported');
  assert.equal(review('Maximum operating voltage: 68 V.\n' + row), 'supported');
  assert.equal(review('Minimum discharge voltage: 48 V.\n' + row), 'supported');
  assert.equal(review('Maximum operating values for 30 A.\n' + row), 'insufficient');
  assert.equal(review('Maximum discharge current: 30 kg.\n' + row), 'insufficient');
  assert.equal(review('Independent measurements.\n' + row), 'supported');
  assert.equal(review(row + '\nUpper limits for a subsequent section.'), 'supported');
});

test('explicit peer headings end a qualifier without dropping inherited limits in subsections', () => {
  const target = {model:'Example Pack',level:'system'};
  const row = 'Net battery weight: 64 kg.';
  const review = excerpt => reviewClaim({
    id:'heading-level',target,field:'batteryWeight',claim:{value:68,unit:'kg'},
    sources:[{id:'manual',excerpt,url:'https://example.org/data',locator:'two sections',sha256:'a'.repeat(64)}],
    observations:[{source:'manual',target,field:'batteryWeight',quote:row,value:64,unit:'kg'}],
  }).decision;
  const first = '## Upper limits\nMaximum discharge current: 30 A.\n';
  assert.equal(review(first + '## Measured specifications\n' + row), 'contradicted');
  assert.equal(review(first + '# Measured specifications\n' + row), 'contradicted');
  assert.equal(review(first + '### Measured specifications\n' + row), 'insufficient');
  assert.equal(review(first + 'Measured specifications\n' + row), 'insufficient');
  assert.equal(review('## Maximum discharge current: 30 A.\n' + row), 'insufficient');
  assert.equal(review('<h2 class="table">Limites supérieures</h2>\n<h2>Mesures exactes</h2>\n' + row), 'contradicted');
  assert.equal(review('## Upper limits\n### Estimates\n### Measured examples\n' + row), 'insufficient');
  assert.equal(review('## Measured specifications\n' + row + '\n## Upper limits'), 'contradicted');
  assert.equal(review('## Upper limits\n' + row + '\n## Measured specifications\n' + row), 'insufficient');
  for (const text of ['<h2>', '<h2></h2>', '<h2><em></em></h2>', '<h2>Measured</h3>', '> ## Measured specifications',
    '## ---', '```md\n## Measured specifications\n```', '~~~\n## Measured specifications\n~~~',
    '    ## Measured specifications', '\t## Measured specifications', 'Note; ## Measured specifications',
    '    <h2>Measured specifications</h2>', 'Note; <h2>Measured specifications</h2>',
    '<pre>\n## Measured specifications\n</pre>', '<!--\n## Measured specifications\n-->',
    '<h2 hidden>Measured specifications</h2>']) {
    assert.equal(review(first + text + '\n' + row), 'insufficient');
  }
  assert.equal(review(first + '- Example\n   ## Measured specifications\n' + row), 'insufficient');
  assert.equal(review('## Measured specifications\n    ' + row), 'insufficient');
});
