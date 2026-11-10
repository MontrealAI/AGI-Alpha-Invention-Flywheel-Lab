// SPDX-License-Identifier: Apache-2.0
const test = require('node:test');
const assert = require('node:assert/strict');
const H = require('../app/engine.js');
const quote = () => H.constructInstrument({ name: 'Quote', inputs: ['price', 'quantity', 'setup'], outputs: { total: { op: 'add', args: [{ op: 'mul', args: [{ field: 'price' }, { field: 'quantity' }] }, { field: 'setup' }] } } });
const confirmation = (independence = 'independently-prepared') => H.freezeConfirmation({ id: 'unit', preparedBy: 'unit test', independence, scope: 'unit fixture', cases: [{ input: { price: 12, quantity: 3, setup: 4 }, expected: { total: 40 } }] });

test('demo computes useful economics and catches an exact planted error', () => {
  const p = H.demoProject(), r = H.runDemo(p);
  assert.equal(r.economics.totalCostMinor, 270000);
  assert.equal(r.economics.savingsMinor, 60000);
  assert.equal(r.plantedError.verdict, 'REJECTED');
  assert.match(r.plantedError.issues.join(' '), /260000.*270000/);
  assert.equal(r.execution.outputs.total, 42500);
  assert.equal(r.successor.recursiveEnablingClaim, 'NOT ESTABLISHED');
  assert.equal(p.runs.length, 1);
});
test('outside options and cost precision are enforced', () => {
  const p = H.demoProject(); p.arrangement.participants[0].outsideOptionMinor = 86000;
  assert.equal(H.evaluateArrangement(p.arrangement).feasible, false);
  p.arrangement.costs[0].amountMinor = 0.5;
  assert.equal(H.evaluateArrangement(p.arrangement).verdict, 'INVALID');
});
test('signed transfers preserve an operator incentive without double counting', () => {
  const x = { currency:'CAD', participants:[...['a','b','c'].map(id=>({id,benefitMinor:60000,costMinor:0,paymentMinor:14000,outsideOptionMinor:40000})),{id:'operator',benefitMinor:0,costMinor:33000,paymentMinor:-42000,outsideOptionMinor:6000}],costs:[],alternatives:[{id:'ordinary',name:'Shared conventional route',totalCostMinor:30000,feasible:true}] };
  const r = H.evaluateArrangement(x); assert.equal(r.totalCostMinor,33000); assert.equal(r.fundingGapMinor,0); assert.equal(r.participation[3].netBenefitMinor,9000); assert.equal(r.savingsMinor,-3000);
});
test('total funding override does not double count participant payments', () => {
  const a=H.demoProject().arrangement; a.fundingAvailableMinor=100;
  assert.equal(H.evaluateArrangement(a).fundingGapMinor,254900);
});
test('unknown costs remain explicit', () => {
  const a=H.demoProject().arrangement; a.costs=[];
  assert.match(H.evaluateArrangement(a).completeCostStatus,/UNKNOWN/);
});
test('raw manual contributions are useful but never auto-approved', () => {
  const p=H.createProject({objective:'Probe adaptive calibration'}); const r=H.importResponse(p,'Try a shared calibration reference.',{model:'My chat account'});
  assert.equal(r.verdict,'UNKNOWN'); assert.equal(p.modelOutputs.length,1); assert.equal(p.opportunities.length,0);
});
test('new hypotheses and enabling graphs are accepted without menu membership', () => {
  const p=H.createProject(); p.availableCapabilities=['raw-data'];
  H.importResponse(p,JSON.stringify({opportunities:[{title:'An unseen idea',hypothesis:'Derive a sensor contract',requiredCapabilities:['verified-signal']}],capabilities:[{id:'extract',requires:['raw-data'],provides:['signal'],costMinor:20},{id:'check',requires:['signal'],provides:['verified-signal'],costMinor:12}]}));
  const o=H.discover(p)[0]; assert.deepEqual(o.investigation.stepProvenance.map(s=>s.sourceId),['extract','check']); assert.equal(o.investigation.costMinor,32); assert.equal(o.verdict,'UNKNOWN');
});
test('ordinary direct route wins when cheaper and unknown graph stays unknown', () => {
  const x={available:['a'],required:['c'],capabilities:[{id:'x',requires:['a'],provides:['b'],costMinor:10},{id:'y',requires:['b'],provides:['c'],costMinor:10},{id:'direct',requires:['a'],provides:['c'],costMinor:15}]};
  assert.deepEqual(H.synthesizePlan(x).steps,['direct']); x.maxCostMinor=14; assert.equal(H.synthesizePlan(x).verdict,'UNKNOWN');
});
test('typed structural mapping identifies a missing relation', () => {
  const r=H.structuralTransfer({sourceRelations:[['server','serves','request']],targetRelations:[['instrument','serves','sample']],mapping:{server:'instrument',request:'sample'}});
  assert.equal(r.verdict,'PASSED IN SCOPE');
  assert.equal(H.structuralTransfer({sourceRelations:[['a','needs','b']],targetRelations:[],mapping:{a:'x',b:'y'}}).verdict,'REJECTED');
});
test('expression evaluation rejects code, undefined division and unsafe integers', () => {
  assert.throws(()=>H.constructInstrument({name:'evil',inputs:['x'],outputs:{result:{op:'eval',args:['fetch("https://evil.test")']}}}),/Unsupported/);
  const divide=H.constructInstrument({name:'division',inputs:['x'],outputs:{y:{op:'div',args:[1,{field:'x'}]}}}); assert.equal(H.executeInstrument(divide,{x:0}).verdict,'INVALID');
  assert.equal(H.executeInstrument(quote(),{price:Number.MAX_SAFE_INTEGER,quantity:2,setup:0}).verdict,'INVALID');
});
test('aggregate and parameterized instrument constructors work', () => {
  const source={name:'aggregate',inputs:['rows'],outputs:{total:{op:'sum',args:[{field:'rows'}]},count:{op:'count',args:[{field:'rows'}]}}};
  assert.deepEqual(H.executeInstrument(H.constructInstrument(source),{rows:[4,7,2]}).outputs,{total:13,count:3});
  const specialized=H.abstractInstrument({template:quote(),parameters:{setup:13},name:'Fixed setup'}); assert.deepEqual(specialized.inputs,['price','quantity']); assert.equal(H.executeInstrument(specialized,{price:7,quantity:9}).outputs.total,76);
});
test('confirmation copy is protected, altered candidate fails and dev tests cannot approve', () => {
  const spec={id:'frozen',preparedBy:'unit',independence:'independently-prepared',scope:'arith',cases:[{input:{price:12,quantity:3,setup:4},expected:{total:40}}]};
  const token=H.freezeConfirmation(spec); spec.cases[0].expected.total=39;
  assert.equal(H.verifyInstrument(quote(),token).verdict,'PASSED IN SCOPE');
  const bad=H.constructInstrument({name:'wrong',inputs:['price','quantity','setup'],outputs:{total:39}}); assert.equal(H.verifyInstrument(bad,token).verdict,'REJECTED');
  assert.equal(H.verifyInstrument(quote(),confirmation('development')).verdict,'UNKNOWN');
  assert.equal(H.verifyInstrument(quote(),{...token}).verdict,'INVALID');
});
test('retention binds instrument, version and dependency retirement', () => {
  const p=H.createProject(), instrument=quote(), v=H.verifyInstrument(instrument,confirmation());
  const a=H.retainCapability(p,{instrument,verification:v,name:'Q'}), b=H.retainCapability(p,{instrument,verification:v,name:'Q',dependencies:[a.id]});
  assert.equal(b.version,2);
  assert.throws(()=>H.retainCapability(p,{instrument,verification:JSON.parse(JSON.stringify(v))}),/in-session/);
  H.retireCapability(p,a.id,'Replaced'); assert.equal(b.currentVerification,'UNKNOWN');
});
test('successor matching does not manufacture advantage or fresh input', () => {
  const p=H.createProject(), instrument=quote(), verification=H.verifyInstrument(instrument,confirmation()); const c=H.retainCapability(p,{instrument,verification});
  assert.equal(H.testInheritance(c,[{input:{price:12,quantity:3,setup:4},expected:{total:40}}]).verdict,'INVALID');
  const r=H.testInheritance(c,[{input:{price:8,quantity:6,setup:3},expected:{total:51}}]); assert.equal(r.verdict,'PASSED IN SCOPE'); assert.equal(r.improvedOutcome,false);
});
test('workflow compiles generated composition and records actual results', async () => {
  const w=H.compileWorkflow({name:'Quote experiment',inputs:['data'],effects:[],budget:{maxOperations:10000},steps:[{id:'tool',op:'construct',dependsOn:[],args:quote()},{id:'result',op:'execute',dependsOn:['tool','data'],args:{instrument:{$ref:'tool'},input:{$ref:'data'}}}],outputs:['result']});
  const r=await H.runWorkflow(w,{data:{price:3,quantity:5,setup:2}}); assert.equal(r.verdict,'PASSED IN SCOPE'); assert.equal(r.outputs.result.outputs.total,17); assert.equal(r.trace.length,2);
});
test('workflow cannot expand authority or use undeclared dependencies', () => {
  const w={name:'No effects',inputs:[],effects:['network'],budget:{maxOperations:10000},steps:[],outputs:[]}; assert.throws(()=>H.compileWorkflow(w),/pure data/);
  w.effects=[]; w.steps=[{id:'bad',op:'execute',dependsOn:[],args:{$ref:'missing'}}]; assert.throws(()=>H.compileWorkflow(w),/declared dependency/);
});
test('cancellation and computational limits stop rather than grant resources', async () => {
  const controller=new AbortController();controller.abort(); assert.throws(()=>H.executeInstrument(quote(),{price:1,quantity:1,setup:0},{signal:controller.signal}),/cancelled/);
  assert.equal(H.executeInstrument(quote(),{price:1,quantity:1,setup:0},{budget:{maxOperations:2}}).verdict,'INVALID');
  const token=H.freezeConfirmation({id:'many',preparedBy:'test',independence:'independently-prepared',scope:'repetition',cases:Array.from({length:8},()=>({input:{price:1,quantity:1,setup:0},expected:{total:1}}))});
  assert.equal(H.verifyInstrument(quote(),token,{budget:{maxOperations:100}}).verdict,'INVALID');
  assert.throws(()=>H.importResponse(H.createProject(),JSON.stringify({data:Array(100001).fill(0)})),/envelope/);
});
test('project persistence, credential field redaction and source changes', () => {
  const p=H.demoProject(); p.settings={apiKey:'secret-value'}; const saved=H.exportProject(p); assert.ok(!saved.includes('secret-value'));
  const loaded=H.importProject(saved); assert.equal(loaded.title,p.title); assert.equal(loaded.confirmation.independence,'development');
  assert.throws(()=>H.importProject('{"schema":"alpha-genesis-project/v1","__proto__":{}}'),/Unsafe/);
  const s={id:'paper',content:'old',retrievedAt:'2026-01-01T00:00:00Z'}; const t={...s,content:'new'};assert.equal(H.sourceDiff(s,t).changed,true);
  assert.match(H.exportDossier(p),/Unknown actual costs remain unknown/);
});
test('generated artifacts install transactionally, execute and never inherit approval', () => {
  const p=H.demoProject();
  const body={instrumentSpec:{name:'Affine calibration',inputs:['reading'],outputs:{calibrated:{op:'mul',args:[{op:'sub',args:[{field:'reading'},100]},25]}}},experimentInputs:{reading:235},workflow:{name:'Measure',inputs:['data'],effects:[],budget:{maxOperations:10000},steps:[{id:'measure',op:'execute',dependsOn:['data'],args:{instrument:{name:'Twice',inputs:['x'],outputs:{y:{op:'mul',args:[{field:'x'},2]}}},input:{$ref:'data'}}}],outputs:['measure']}};
  H.importResponse(p,JSON.stringify(body),{model:'manual account'});
  assert.equal(H.executeInstrument(H.constructInstrument(p.instrumentSpec),p.instrumentInput).outputs.calibrated,3375);
  assert.equal(p.confirmation,undefined); assert.equal(p.artifactProvenance.verification,'UNKNOWN');
  const previous=H.exportProject(p);
  assert.throws(()=>H.importResponse(p,JSON.stringify({opportunities:[{title:'X',hypothesis:'Y'}],instrumentSpec:body.instrumentSpec,arrangement:{currency:'CAD'}})),/Invalid arrangement/);
  assert.equal(H.exportProject(p),previous);
});

test('rival model capability identifiers remain independent and inspectable', () => {
  const p=H.createProject(); p.availableCapabilities=['input'];
  const response=(cost)=>JSON.stringify({opportunities:[{title:'Unlisted candidate '+cost,hypothesis:'Use a converter',requiredCapabilities:['output']}],capabilities:[{id:'converter',requires:['input'],provides:['output'],costMinor:cost}]});
  const a=H.importResponse(p,response(17),{model:'Rival A'}),b=H.importResponse(p,response(11),{model:'Rival B'});
  assert.equal(p.proposedCapabilities.length,2); assert.notEqual(p.proposedCapabilities[0].id,p.proposedCapabilities[1].id);
  assert.deepEqual(p.proposedCapabilities.map(c=>c.sourceId),['converter','converter']);
  const opportunities=H.discover(p); assert.equal(opportunities.length,2); assert.equal(opportunities[0].investigation.costMinor,11);
  assert.equal(opportunities[0].investigation.stepProvenance[0].contributionId,b.id); assert.notEqual(a.id,b.id);
});

test('malformed imported rows are rejected before replacing the workspace', () => {
  for (const key of ['sources','modelOutputs','opportunities','capabilities','runs']) {
    for(const bad of [null,'bad',[]]) { const p=H.createProject();p[key]=[bad];assert.throws(()=>H.importProject(JSON.stringify(p)),/plain object/); }
  }
  const p=H.createProject();p.title=41;assert.throws(()=>H.importProject(JSON.stringify(p)),/title/);
});

test('aggregate response growth cannot trap an otherwise exportable project', () => {
  const p=H.createProject(), identity=p;
  H.importResponse(p,'a'.repeat(2600000),{model:'first'});
  const saved=H.exportProject(p);
  assert.throws(()=>H.importResponse(p,'b'.repeat(2600000),{model:'second'}),/envelope/);
  assert.equal(p,identity); assert.equal(p.modelOutputs.length,1); assert.equal(H.exportProject(p),saved);
});
test('optional parallel provider records reject malformed rows but remain optional', () => {
  for (const key of ['providerRuns','providerCosts','providerCancellations','artifactCandidates']) {
    const p=H.createProject();p[key]=[null];assert.throws(()=>H.importProject(JSON.stringify(p)),/plain object/);
  }
  assert.equal(H.importProject(H.exportProject(H.createProject())).providerRuns,undefined);
});
