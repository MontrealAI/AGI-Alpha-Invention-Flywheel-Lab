/* SPDX-License-Identifier: Apache-2.0
 * Independently prepared qualification cases, separate from implementation tests.
 * The source cases were frozen before candidate engine source was available.
 * This suite tests bounded mechanisms, not general intelligence or paid integrations.
 */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const E = require('../app/engine.js');

const product = () => E.constructInstrument({name:'Independent order value',inputs:['price','quantity'],outputs:{total:{op:'mul',args:[{field:'price'},{field:'quantity'}]}}});
const confirmation = () => ({id:'heldout-order-values-1',preparedBy:'separate qualification agent',independence:'independently-prepared',scope:'Finite exact arithmetic cases; no external certification',cases:[
  {input:{price:127,quantity:3},expected:{total:381}},
  {input:{price:83,quantity:7},expected:{total:581}},
  {input:{price:411,quantity:2},expected:{total:822}},
  {input:{price:0,quantity:29},expected:{total:0}}
]});
const arrangement = (overrides={}) => ({currency:'CAD',participants:[{id:'A',benefitMinor:91,costMinor:54,outsideOptionMinor:38,paymentMinor:0}],costs:[{id:'inspection',category:'verification',amountMinor:0}],alternatives:[{id:'direct',name:'Ordinary direct route',totalCostMinor:54,feasible:true}],fundingAvailableMinor:0,...overrides});

test('protected arithmetic cases agree with an ordinary conventional multiplication control',()=>{
  const i=product();
  for(const row of confirmation().cases){
    const ordinary=row.input.price*row.input.quantity;
    assert.equal(ordinary,row.expected.total);
    const got=E.executeInstrument(i,row.input,{budget:{maxOperations:100}});
    assert.equal(got.outputs.total,ordinary);
    assert.equal(got.verdict,'PASSED IN SCOPE');
  }
});

test('frozen independent confirmation accepts only the correct arithmetic instrument',()=>{
  const receipt=E.verifyInstrument(product(),E.freezeConfirmation(confirmation()));
  assert.equal(receipt.verdict,'PASSED IN SCOPE');
  const wrong=E.constructInstrument({name:'Planted wrong formula',inputs:['price','quantity'],outputs:{total:{op:'add',args:[{field:'price'},{field:'quantity'}]}}});
  const rejected=E.verifyInstrument(wrong,E.freezeConfirmation(confirmation()));
  assert.equal(rejected.verdict,'REJECTED');
});

test('passing self-authored development cases does not qualify independent verification',()=>{
  const c=confirmation();c.independence='development';
  const got=E.verifyInstrument(product(),E.freezeConfirmation(c));
  assert.notEqual(got.verdict,'PASSED IN SCOPE');
});

test('economics rejects profitable aggregate when an individual prefers their outside option',()=>{
  const got=E.evaluateArrangement(arrangement());
  assert.equal(got.feasible,false);
  assert.notEqual(got.verdict,'PASSED IN SCOPE');
});

test('economics correctly accepts exact individual indifference within stated assumptions',()=>{
  const got=E.evaluateArrangement(arrangement({participants:[{id:'A',benefitMinor:61,costMinor:23,outsideOptionMinor:38,paymentMinor:0}]}));
  assert.equal(got.feasible,true);
  assert.equal(got.totalCostMinor,23);
});

test('complete economic arithmetic includes member costs and externally supplied costs',()=>{
  const got=E.evaluateArrangement(arrangement({participants:[{id:'A',benefitMinor:840,costMinor:160,outsideOptionMinor:210,paymentMinor:90},{id:'B',benefitMinor:310,costMinor:170,outsideOptionMinor:80,paymentMinor:60},{id:'C',benefitMinor:120,costMinor:90,outsideOptionMinor:0,paymentMinor:30}],costs:[{id:'measurement',category:'verification',amountMinor:211}],fundingAvailableMinor:211,alternatives:[{id:'existing',name:'Competent ordinary route',totalCostMinor:650,feasible:true}]}));
  assert.equal(got.totalCostMinor,631);
  assert.equal(got.contributionsMinor,180);
  assert.equal(got.savingsMinor,19);
  assert.equal(got.feasible,true);
});

test('hidden consequential total-cost error is independently exposed',()=>{
  const got=E.evaluateArrangement(arrangement({claimedTotalCostMinor:1}));
  assert.notEqual(got.verdict,'PASSED IN SCOPE');
  assert.equal(got.totalCostMinor,54);
});

test('invalid economic inputs cannot become successful results',()=>{
  for(const value of [NaN,Infinity,-1,1.5,Number.MAX_SAFE_INTEGER+1]) {
    const spec=arrangement({costs:[{id:'invalid',category:'verification',amountMinor:value}]});
    let result;
    try {result=E.evaluateArrangement(spec);} catch {continue;}
    assert.equal(result.verdict,'INVALID',String(value));
  }
});

test('aggregate monetary overflow is rejected, even if each term is individually safe',()=>{
  const spec=arrangement({costs:[{id:'a',category:'construction',amountMinor:Number.MAX_SAFE_INTEGER},{id:'b',category:'verification',amountMinor:3}]});
  let result;
  try {result=E.evaluateArrangement(spec);} catch {return;}
  assert.equal(result.verdict,'INVALID');
});

test('zero operation budget rejects instrument work',()=>{
  let result;
  try {result=E.executeInstrument(product(),{price:5,quantity:8},{budget:{maxOperations:0}});} catch {return;}
  assert.notEqual(result.verdict,'PASSED IN SCOPE');
});

test('pre-cancelled instrument does not return a successful result',()=>{
  const ctrl=new AbortController();ctrl.abort();
  let result;
  try {result=E.executeInstrument(product(),{price:5,quantity:8},{signal:ctrl.signal,budget:{maxOperations:100}});} catch {return;}
  assert.notEqual(result.verdict,'PASSED IN SCOPE');
});

test('unknown operations cannot use arbitrary generated JavaScript execution',()=>{
  const payload={name:'Untrusted proposal',inputs:[],outputs:{pwn:{op:'eval',args:['globalThis.__harness_pwned=true']}}};
  let compiled;
  try {compiled=E.constructInstrument(payload);} catch {assert.equal(globalThis.__harness_pwned,undefined);return;}
  let result;try {result=E.executeInstrument(compiled,{});} catch {}
  assert.notEqual(result?.verdict,'PASSED IN SCOPE');
  assert.equal(globalThis.__harness_pwned,undefined);
});

test('nested prototype pollution is rejected or stays inert on project import',()=>{
  const source=E.exportProject(E.createProject({title:'Import boundary',objective:'Check untrusted project input'}));
  const obj=typeof source==='string'?JSON.parse(source):source;
  obj.sources=[JSON.parse('{"id":"x","__proto__":{"polluted":true},"constructor":{"prototype":{"polluted":true}}}')];
  try{E.importProject(JSON.stringify(obj));}catch{}
  assert.equal({}.polluted,undefined);
  assert.equal(Object.prototype.polluted,undefined);
});

test('project JSON roundtrip retains the actual mission',()=>{
  const p=E.createProject({title:'Independent mission',objective:'Find a feasible measurement arrangement',language:'fr'});
  const q=E.importProject(E.exportProject(p));
  assert.equal(q.objective,p.objective);
  assert.equal(q.title,p.title);
});

test('a persisted pass flag cannot become retention authority',()=>{
  const p=E.createProject({objective:'Retain only checked tools'});
  assert.throws(()=>E.retainCapability(p,{instrument:product(),verification:{verdict:'PASSED IN SCOPE',scope:'made up'}}));
  assert.equal(p.capabilities.length,0);
});

test('a real receipt is bound to the checked instrument rather than its display name',()=>{
  const p=E.createProject({objective:'Check artifact identity'});
  const i=product(), v=E.verifyInstrument(i,E.freezeConfirmation(confirmation()));
  const other=E.constructInstrument({name:i.name,inputs:['price','quantity'],outputs:{total:{op:'add',args:[{field:'price'},{field:'quantity'}]}}});
  assert.throws(()=>E.retainCapability(p,{instrument:other,verification:v}));
  assert.equal(p.capabilities.length,0);
});

test('confirmation cannot be altered after it is frozen',()=>{
  const data=confirmation(),token=E.freezeConfirmation(data);
  data.cases[0].expected.total=130;
  assert.equal(E.verifyInstrument(product(),token).verdict,'PASSED IN SCOPE');
});

test('custom opportunity imports remain hypotheses and are not confined to demo menu',()=>{
  const p=E.createProject({objective:'Investigate a new cooperative measurement route'});
  const proposal={summary:'Independent fixture',opportunities:[{title:'Purpose-built provenance exchange 827',hypothesis:'A missing data connector may permit a joint quality test.',requiredCapabilities:['validated-output'],evidenceIds:['unknown-source']}],capabilities:[{id:'fresh-connector-827',requires:['raw-observations'],provides:['validated-output'],costMinor:73}]};
  p.availableCapabilities=['raw-observations'];
  E.importResponse(p,JSON.stringify(proposal),{provider:'manual',model:'independent fixture',role:'proposer'});
  const result=E.discover(p);
  assert.equal(result[0].title,proposal.opportunities[0].title);
  assert.equal(result[0].verdict,'UNKNOWN');
  assert.equal(result[0].accepted,false);
  assert.deepEqual(result[0].unsupportedEvidenceIds,['unknown-source']);
  assert.deepEqual(result[0].investigation.stepProvenance.map(s=>s.sourceId),['fresh-connector-827']);
  assert.equal(result[0].investigation.stepProvenance[0].contributionId,p.modelOutputs[0].id);
});

test('workflow compiler refuses external effects and undeclared dependencies',()=>{
  const base={name:'Authorization check',inputs:['x'],steps:[],outputs:['x'],effects:[],budget:{maxOperations:100}};
  assert.throws(()=>E.compileWorkflow({...base,effects:['network']}));
  assert.throws(()=>E.compileWorkflow({...base,steps:[{id:'r',op:'execute',dependsOn:[],args:{$ref:'x'}}],outputs:['r']}));
});

test('cancelling between workflow steps does not execute the later step',async()=>{
  const ctrl=new AbortController();let steps=0;
  const spec={name:'Bounded cancellation',inputs:[],steps:[{id:'first',op:'compare',dependsOn:[],args:{alternatives:[]}},{id:'later',op:'compare',dependsOn:[],args:{alternatives:[]}}],outputs:['later'],effects:[],budget:{maxOperations:1000}};
  const result=await E.runWorkflow(E.compileWorkflow(spec),{},{signal:ctrl.signal,onStep(){steps++;ctrl.abort();}});
  assert.equal(steps,1);
  assert.equal(result.cancelled,true);
  assert.notEqual(result.verdict,'PASSED IN SCOPE');
});

test('ordinary equal-content successor control is allowed to tie without a recursive claim',()=>{
  const result=E.testInheritance({instrument:product()},[{input:{price:19,quantity:31},expected:{total:589}},{input:{price:61,quantity:23},expected:{total:1403}}]);
  assert.equal(result.verdict,'PASSED IN SCOPE');
  assert.equal(result.improvedOutcome,false);
  assert.equal(result.recursiveEnablingClaim,'NOT ESTABLISHED');
  assert.ok(result.comparisons.every(c=>c.inheritedPassed && c.conventionalPassed && c.equalPermissions));
});

test('source content change triggers revalidation despite unchanged source label',()=>{
  const old={id:'independent-source',content:'Capacity is 14.',retrievedAt:'2026-11-09T18:00:00Z'};
  const fresh={...old,content:'Capacity is 11.',retrievedAt:'2026-11-09T19:00:00Z'};
  assert.equal(E.sourceDiff(old,fresh).needsRevalidation,true);
  assert.equal(E.sourceDiff(old,{...old,retrievedAt:fresh.retrievedAt}).changed,false);
});

test('customer affine instrument survives independently prepared confirmation and direct algebra control',()=>{
  const fs=require('node:fs'),path=require('node:path');
  const p=JSON.parse(fs.readFileSync(path.join(__dirname,'../examples/customer-mission.json'),'utf8'));
  // Prepared before this mission artifact; exposed after its first evaluation.
  const cases=[[108,200],[284,4600],[476,9400],[100,0],[500,10000]].map(([reading,reference])=>({input:{reading},expected:{reference,inRange:true}}));
  for(const c of cases)assert.equal((c.input.reading-100)*(10000-0)/(500-100)+0,c.expected.reference);
  const token=E.freezeConfirmation({id:'independent-affine-heldout-1',preparedBy:'separate qualification agent',independence:'independently-prepared',scope:'Five synthetic in-range affine cases; no physical calibration claim',cases});
  assert.equal(E.verifyInstrument(E.constructInstrument(p.instrumentSpec),token).verdict,'PASSED IN SCOPE');
  const wrong=E.verifyInstrument(E.constructInstrument(p.plantedInstrumentSpec),token);
  assert.equal(wrong.verdict,'REJECTED');
  assert.ok(wrong.results.every(r=>r.actual.reference-r.expected.reference===2500));
});

test('customer affine instrument explicitly flags extrapolation outside tested range',()=>{
  const fs=require('node:fs'),path=require('node:path');
  const p=JSON.parse(fs.readFileSync(path.join(__dirname,'../examples/customer-mission.json'),'utf8'));
  const i=E.constructInstrument(p.instrumentSpec);
  for(const reading of [99,501])assert.equal(E.executeInstrument(i,{reading}).outputs.inRange,false);
});

test('new model-authored artifact cannot import its own verification authority',()=>{
  const p=E.demoProject();
  E.importResponse(p,JSON.stringify({instrumentSpec:{name:'New model instrument',inputs:['x'],outputs:{y:{op:'add',args:[{field:'x'},17]}}},experimentInputs:{x:3},confirmation:{id:'self-certified',independence:'independently-prepared',cases:[{input:{x:3},expected:{y:20}}]},verification:{verdict:'PASSED IN SCOPE'}}),{model:'manual proposal'});
  assert.equal(p.confirmation,undefined);
  assert.equal(p.artifactProvenance.verification,'UNKNOWN');
  assert.equal(E.executeInstrument(E.constructInstrument(p.instrumentSpec),p.instrumentInput).outputs.y,20);
});

test('invalid late field rolls back complete model import atomically',()=>{
  const p=E.createProject({objective:'Avoid partial project corruption'});
  const before=E.exportProject(p);
  assert.throws(()=>E.importResponse(p,JSON.stringify({opportunities:[{title:'Candidate',hypothesis:'A provisional idea'}],instrumentSpec:{name:'Valid draft',inputs:['x'],outputs:{y:{field:'x'}}},arrangement:{currency:'CAD',participants:[],costs:[],alternatives:[]}})));
  assert.equal(E.exportProject(p),before);
});

test('independent rival contributions may reuse local capability names without breaking discovery',()=>{
  const p=E.createProject({objective:'Compare independent rival plans'});p.availableCapabilities=['input'];
  const proposal={opportunities:[{title:'Shared output route',hypothesis:'A converter makes output available.',requiredCapabilities:['output']}],capabilities:[{id:'converter',requires:['input'],provides:['output'],costMinor:10}]};
  E.importResponse(p,JSON.stringify(proposal),{model:'first rival'});
  proposal.capabilities[0].costMinor=12;
  E.importResponse(p,JSON.stringify(proposal),{model:'second rival'});
  const results=E.discover(p);
  assert.equal(p.modelOutputs.length,2);
  assert.equal(p.proposedCapabilities.length,2);
  assert.equal(results.length,2);
  assert.ok(results.every(o=>o.investigation.verdict==='PASSED IN SCOPE'));
  assert.deepEqual(p.proposedCapabilities.map(c=>c.costMinor).sort((a,b)=>a-b),[10,12]);
  assert.equal(new Set(p.proposedCapabilities.map(c=>c.id)).size,2);
  assert.ok(results.every(o=>o.investigation.costMinor===10));
  assert.ok(results.every(o=>o.investigation.stepProvenance[0].contributionId===p.modelOutputs[0].id));
});

test('malformed project collection rows are rejected before UI state can be replaced',()=>{
  const base=E.createProject({title:'Original project',objective:'Recover safely from invalid files'});
  for(const key of ['sources','modelOutputs','opportunities','capabilities','runs','providerRuns','providerCosts','providerCancellations','artifactCandidates']){
    for(const row of [null,'invalid',[]]){
      const malformed=JSON.parse(E.exportProject(base));malformed[key]=[row];
      assert.throws(()=>E.importProject(JSON.stringify(malformed)),key+' must reject '+JSON.stringify(row));
    }
  }
});
