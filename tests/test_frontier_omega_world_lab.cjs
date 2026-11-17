'use strict';
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const test=require('node:test');
const assert=require('node:assert/strict');
const html=fs.readFileSync(path.resolve(__dirname,'../docs/research/frontier-omega-world-lab.html'),'utf8');
const match=html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(match,'single self-contained source script');
const src=match[1];
function extract(name,kind='function'){
 const head=kind+' '+name+(kind==='function'?'(':'=');
 const i=src.indexOf(head);
 assert.ok(i>=0,'missing '+name);
 const j=src.indexOf('\n',i);
 return src.slice(i,j<0?src.length:j);
}
const strategyStart=src.indexOf('function strategisePolicy(');
const strategyEnd=src.indexOf('function drawStrategy(',strategyStart);
assert.ok(strategyStart>=0&&strategyEnd>strategyStart,'strategy functions exposed in the actual published source');
const strategyCode=src.slice(strategyStart,strategyEnd);
const program=[
 strategyCode,
 extract('MARKET','const'),extract('TASKS','const'),
 extract('causalCompute'),extract('marketFormula'),extract('marketIndependent'),
 extract('builderSource'),extract('referenceValue'),extract('compiledValue'),extract('enumerateBuild')
].join('\n');
const ctx=vm.createContext({});
vm.runInContext(program,ctx);
const run=expression=>vm.runInContext(expression,ctx);
test('Frontier World Lab: five primary-source leads and four live laboratories, no prior event references',()=>{
 assert.ok(!/Bengio|Marcus|AI Debate|aidebate|2019/.test(html));
 for(const term of ['FlashProve','Claude Fable 5.2','AlphaProof Code','Engineering for the Physical World','Gemini 4 Carbon','id="lab-strategy"','id="lab-causal"','id="lab-market"','id="lab-builder"'])assert.ok(html.includes(term),term);
 assert.ok(html.includes('No AI model inference occurred'));
});
test('Transformational Intelligence: exact intervention versus passive ceiling',()=>{
 const r=run('causalCompute(12)');
 assert.equal(r.correct,8191);assert.equal(r.total,8192);assert.equal(r.analytic,8191/8192);assert.ok(r.pass);
 const z=run('causalCompute(0)');assert.equal(z.correct,1);assert.equal(z.total,2);
});
test('Invent the Economy: expected contribution, cash and rejection control',()=>{
 const a=run('marketFormula({n:4,k:600,p:.8,cash:900})');
 const b=run('marketIndependent({n:4,k:600,p:.8,cash:900})');
 assert.equal(a.expected_contribution,60);assert.equal(a.required_prefunding,900);assert.ok(a.qualified_model_route);
 assert.equal(a.conditional_cost_source_contribution,120,'historical contingent-cost author case preserved separately');
 assert.equal(b.expected_delta,60);assert.equal(b.min_cash_prefix,0);
 assert.equal(a.modes.join(','),'0,0,0,60');
 assert.equal(run('marketFormula({n:4,k:600,p:.8,cash:600})').qualified_model_route,false);
});
test('Learning to Build: original four finite authored schemas pass 4000 checks',()=>{
 const r=run('enumerateBuild()');
 assert.equal(r.cases,4000);assert.equal(r.passed,4000);assert.ok(r.qualified);
 assert.equal(r.detail.map(x=>x.count).join(','),'125,125,625,3125');
 assert.equal(run('TASKS[0].threshold'),2);assert.equal(run('TASKS[1].threshold'),7);
 assert.equal(run('TASKS[2].constant'),6);assert.equal(run('TASKS[3].constant'),7);
});

test('Out-Strategise: full-world network construction achieves exact 7/11/20 costs',()=>{
 const r=run('strategiseEvaluate(4,4,9,false,false)');
 assert.equal(r.worlds,16);assert.equal(r.passed,16);assert.ok(r.qualified);
 assert.equal(r.costs.joint,7);assert.equal(r.costs.repair_only,11);assert.equal(r.costs.no_observation,20);
});
test('Out-Strategise: full 1024-world replay matches exact 7/67/160 source model',()=>{
 const r=run('strategiseEvaluate(32,32,517,false,false)');
 assert.equal(r.worlds,1024);assert.equal(r.passed,1024);assert.ok(r.qualified);
 assert.equal(r.costs.joint,7);assert.equal(r.costs.repair_only,67);assert.equal(r.costs.no_observation,160);
});
test('Out-Strategise: old strategy rejected after purpose or assumption change',()=>{
 const checkpoint=run('strategiseEvaluate(4,4,9,true,false)');
 const second=run('strategiseEvaluate(4,4,9,false,true)');
 assert.equal(checkpoint.qualified,false);assert.equal(checkpoint.passed,0);
 assert.equal(second.qualified,false);assert.equal(second.passed,0);
 assert.throws(()=>run('strategisePolicy(33,33)'));
});

test('registered World Lab cash integrity: no unearned refund in failed-world ledger',()=>{
 const r=run('marketIndependent({n:4,k:600,p:.8,cash:900})');
 assert.equal(r.prepayment_cash,0,'full construction and four adaptation debits precede receipts');
 assert.equal(r.success_cash,1200);
 assert.equal(r.failure_cash,0,'failed world cannot silently refund incurred adaptation');
 assert.equal(r.min_cash_prefix,0);
});
test('registered World Lab cash integrity: complete non-refundable expected contribution is 60',()=>{
 const a=run('marketFormula({n:4,k:600,p:.8,cash:900})');
 const b=run('marketIndependent({n:4,k:600,p:.8,cash:900})');
 assert.equal(a.expected_contribution,60,'960 collected expected receipts less 600+300 incurred debits');
 assert.equal(b.expected_delta,60,'distinct event-branch arithmetic must reconcile');
 assert.equal(a.required_prefunding,900);
 assert.equal(a.qualified_model_route,true);
});
test('registered World Lab zero acceptance cannot recover adaptation without a recorded entitlement',()=>{
 const a=run('marketFormula({n:4,k:600,p:0,cash:900})');
 const b=run('marketIndependent({n:4,k:600,p:0,cash:900})');
 assert.equal(a.expected_contribution,-900);
 assert.equal(b.failure_cash,0);
 assert.equal(b.expected_delta,-900);
 assert.equal(a.qualified_model_route,false);
});
test('registered World Lab no-deploy is mandatory at break-even or inadequate prefunding',()=>{
 const flat=run('marketFormula({n:4,k:600,p:.75,cash:900})');
 assert.equal(flat.expected_contribution,0);
 assert.equal(flat.qualified_model_route,false);
 const unfinanced=run('marketFormula({n:4,k:600,p:.8,cash:899})');
 assert.equal(unfinanced.qualified_model_route,false);
});


// Registered before implementation: market receipts must track CURRENT visitor
// controls, not the previously calculated S.market snapshot. Execute the
// actual inline producer/event-binding source with a deliberately minimal DOM.
function marketReceiptSession() {
 const first=src.indexOf('function runMarket(');
 const last=src.indexOf('/* REAL LAB C:',first);
 assert.ok(first>=0&&last>first,'real market event handlers must be extracted');
 const handlers={}; const elements={}; const downloads=[];
 const defaults={'market-buyers':'4','market-cost':'600','market-prob':'80','market-cash':'900'};
 function element(id) {
  if (!elements[id]) elements[id]={
   value: defaults[id]??'',textContent:'',classList:{toggle(){}},
   addEventListener(type,fn){(handlers[id]??={})[type]=fn;}
  };
  return elements[id];
 }
 const sandbox={S:{market:null},$:element,save:(payload)=>downloads.push(JSON.parse(payload))};
 const isolated=vm.createContext(sandbox);
 vm.runInContext([extract('MARKET','const'),extract('marketFormula'),
                  extract('marketIndependent'),src.slice(first,last)].join('\n'),isolated);
 return {
  set(id,value) {const target=element(id);target.value=String(value);
   assert.equal(typeof handlers[id]?.input,'function','input handler must exist');
   handlers[id].input({target});},
  calculate() {handlers['run-market'].click();return sandbox.S.market;},
  download() {handlers['download-market'].click();return downloads.at(-1);},
  independent(a) {return vm.runInContext('marketIndependent('+JSON.stringify(a)+')',isolated);}
 };
}
test('registered receipt freshness F1: editing probability invalidates the previous downloadable decision',()=>{
 const s=marketReceiptSession();
 assert.equal(s.calculate().input.p,.8);
 const same=s.download();assert.equal(same.input.p,.8,'no-change positive control');
 s.set('market-prob',55);
 const fresh=s.download();
 assert.equal(fresh.input.p,.55,'exported probability must match current visitor control');
 assert.equal(fresh.reference.expected_delta,s.independent(fresh.input).expected_delta,
   'downloaded economic result must match a fresh independent cash-path replay');
});
test('registered receipt freshness F2: changing buyers and available cash must not preserve stale inputs',()=>{
 const s=marketReceiptSession();
 s.calculate();s.set('market-prob',55);s.download();
 s.set('market-buyers',5);s.set('market-cash',1500);
 const fresh=s.download();
 assert.equal(fresh.input.n,5,'download must bind current buyer-count control');
 assert.equal(fresh.input.cash,1500,'download must bind current available-cash control');
 assert.equal(fresh.input.p,.55);
 assert.equal(fresh.reference.expected_delta,s.independent(fresh.input).expected_delta);
});
