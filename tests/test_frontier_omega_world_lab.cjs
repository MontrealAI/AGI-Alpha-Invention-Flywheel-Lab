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
const program=[
 extract('MARKET','const'),extract('TASKS','const'),
 extract('causalCompute'),extract('marketFormula'),extract('marketIndependent'),
 extract('builderSource'),extract('referenceValue'),extract('compiledValue'),extract('enumerateBuild')
].join('\n');
const ctx=vm.createContext({});
vm.runInContext(program,ctx);
const run=expression=>vm.runInContext(expression,ctx);
test('Frontier World Lab: five primary-source leads and three live laboratories',()=>{
 for(const term of ['FlashProve','Claude Fable 5.2','AlphaProof Code','Engineering for the Physical World','Gemini 4 Carbon','id="lab-causal"','id="lab-market"','id="lab-builder"'])assert.ok(html.includes(term),term);
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
 assert.equal(a.expected_contribution,120);assert.equal(a.required_prefunding,900);assert.ok(a.qualified_model_route);
 assert.equal(b.expected_delta,120);assert.equal(b.min_cash_prefix,0);
 assert.equal(a.modes.join(','),'0,0,0,120');
 assert.equal(run('marketFormula({n:4,k:600,p:.8,cash:600})').qualified_model_route,false);
});
test('Learning to Build: original four finite authored schemas pass 4000 checks',()=>{
 const r=run('enumerateBuild()');
 assert.equal(r.cases,4000);assert.equal(r.passed,4000);assert.ok(r.qualified);
 assert.equal(r.detail.map(x=>x.count).join(','),'125,125,625,3125');
 assert.equal(run('TASKS[0].threshold'),2);assert.equal(run('TASKS[1].threshold'),7);
 assert.equal(run('TASKS[2].constant'),6);assert.equal(run('TASKS[3].constant'),7);
});
