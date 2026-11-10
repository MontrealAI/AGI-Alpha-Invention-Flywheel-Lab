/* SPDX-License-Identifier: Apache-2.0
 * DOM emulation against an in-memory mocked bridge; no network, paid APIs,
 * real credentials, graphical browser or authenticated provider qualification.
 * Requires jsdom 26.1.0 in NODE_PATH (development only; never bundled).
 */
const fs=require('node:fs'),assert=require('node:assert/strict'),path=require('node:path');
const {JSDOM,VirtualConsole}=require('jsdom');
const root=path.resolve(__dirname,'..','app');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function boot(kind,scenario={}){
 const errors=[],requests=[],cancels=[];let active=0,maxActive=0;const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 const d=new JSDOM(fs.readFileSync(root+'/index.html','utf8'),{url:'http://127.0.0.1:8877/',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc}),w=d.window;
 w.scrollTo=()=>{};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};
 const response=(data,ok=true)=>({ok,json:async()=>w.JSON.parse(JSON.stringify(data))});
 const status={providers:[{id:'alpha',label:'Alpha fixture',ready:true,models:['alpha-test']},{id:'beta',label:'Beta fixture',ready:true,models:['beta-test']}],budget:{currency:'CAD',remaining:10}};
 w.fetch=async(url,options={})=>{if(url==='/api/session')return response({token:'test-only'});if(url==='/api/status')return response(status);const b=JSON.parse(options.body||'{}');if(url==='/api/cancel'){cancels.push(b.run_id);if(kind==='cancel')await pause(250);return response({cancelled:true});}if(url==='/api/generate'){requests.push(b);active++;maxActive=Math.max(maxActive,active);await pause(['cancel','ownership'].includes(kind)?100:b.provider==='alpha'?35:15);active--;if(kind==='failure'&&b.provider==='beta')return response({error:{code:'FIXTURE_FAILURE',message:'Injected failed provider'},budget:status.budget},false);return response({run_id:b.run_id,provider:b.provider,model:b.model,text:scenario.responseText??JSON.stringify(scenario.artifact||{summary:'Fixture output only',instrumentSpec:{name:b.provider+' instrument',inputs:['x'],outputs:{result:{op:'add',args:[{field:'x'},b.provider==='alpha'?1:2]}}},experimentInputs:{x:10}}),usage:{input_tokens:10,output_tokens:20},cost:{currency:'CAD',amount:0.01,complete_cost_known:false},budget:status.budget});}throw Error('Unexpected mocked endpoint '+url);};
 if(scenario.savedProject)w.localStorage.setItem('alpha-genesis-harness-project-v1',JSON.stringify(scenario.savedProject));
 for(const n of ['engine.js','app.js'])w.eval(fs.readFileSync(root+'/'+n,'utf8'));
 return {d,w,errors,requests,cancels,max:()=>maxActive,click:id=>w.document.getElementById(id).click()};
}
(async()=>{
 let t=boot('success');await pause(45);t.w.document.querySelector('input[value="parallel"]').click();t.click('bridge-add-model');assert.equal(t.w.document.querySelectorAll('.bridge-alternative').length,1);t.click('bridge-generate');await pause(120);t.click('save-project');await pause(35);let p=JSON.parse(t.w.localStorage.getItem('alpha-genesis-harness-project-v1'));assert.equal(t.max(),2);assert.equal(t.requests.length,2);assert.equal(t.requests[0].prompt,t.requests[1].prompt);assert.equal(p.modelOutputs.length,2);assert.equal(p.providerCosts.length,2);assert.equal(p.artifactCandidates.length,2);assert.equal(p.instrumentSpec,undefined,'No automatic last-model artifact selection');const choose=[...t.w.document.querySelectorAll('#contribution-list button')].find(n=>n.textContent.includes('Use this proposed'));choose.click();assert.match(t.w.document.getElementById('instrument-description').textContent,/alpha instrument/);assert.deepEqual(t.errors,[]);t.d.window.close();
 t=boot('failure');await pause(45);t.w.document.querySelector('input[value="parallel"]').click();t.click('bridge-add-model');t.click('bridge-generate');await pause(120);t.click('save-project');await pause(35);p=JSON.parse(t.w.localStorage.getItem('alpha-genesis-harness-project-v1'));assert.equal(p.modelOutputs.length,1);assert.equal(p.providerRuns.length,2);assert.equal(p.providerRuns[1].status,'FAILED');assert.equal(p.providerRuns[1].cost.amount,null);assert.match(t.w.document.getElementById('contribution-list').textContent,/Injected failed provider/);assert.deepEqual(t.errors,[]);t.d.window.close();
 t=boot('cancel');await pause(45);t.w.document.querySelector('input[value="parallel"]').click();t.click('bridge-add-model');t.click('bridge-generate');await pause(10);t.click('bridge-cancel');await pause(120);t.click('load-demo');await pause(5);assert.match(t.w.document.getElementById('notice').textContent,/before replacing/);await pause(160);t.click('save-project');await pause(35);p=JSON.parse(t.w.localStorage.getItem('alpha-genesis-harness-project-v1'));assert.equal(t.cancels.length,2);assert.deepEqual(new Set(t.cancels),new Set(t.requests.map(x=>x.run_id)));assert.equal(p.modelOutputs.length,0);assert.ok(p.providerRuns.every(x=>x.status==='CANCELLED'));assert.equal(p.providerCosts.length,2);assert.equal(p.providerCancellations.length,1);assert.deepEqual(t.errors,[]);t.d.window.close();
 t=boot('ownership');await pause(45);const name=t.w.document.getElementById('mission-name');name.value='Original request owner';name.dispatchEvent(new t.w.Event('input',{bubbles:true}));let resolveFile;const opening=new Promise(resolve=>{resolveFile=resolve});const imported=t.w.HarnessEngine.exportProject(t.w.HarnessEngine.demoProject());const input=t.w.document.getElementById('project-file');Object.defineProperty(input,'files',{configurable:true,value:[{size:imported.length,text:()=>opening}]});input.dispatchEvent(new t.w.Event('change',{bubbles:true}));t.w.document.querySelector('input[value="parallel"]').click();t.click('bridge-add-model');t.click('bridge-generate');resolveFile(imported);await pause(15);assert.equal(t.w.document.getElementById('confirm-dialog').open,true);t.click('dialog-confirm');await pause(10);assert.match(t.w.document.getElementById('notice').textContent,/before opening another project/);t.click('load-demo');await pause(5);assert.match(t.w.document.getElementById('notice').textContent,/before replacing/);await pause(120);t.click('save-project');await pause(25);p=JSON.parse(t.w.localStorage.getItem('alpha-genesis-harness-project-v1'));assert.equal(p.title,'Original request owner');assert.equal(p.modelOutputs.length,2);assert.equal(p.runs.at(-1).projectId,p.id);assert.equal(p.runs.at(-1).requestPrompt,t.requests[0].prompt);assert.deepEqual(t.errors,[]);t.d.window.close();
 // Connected single-model modes must install each supported artifact immediately.
 // Start with a different active artifact so a stale restoration is observable.
 const E=require(path.join(root,'engine.js'));
 const arrangement=amount=>({currency:'CAD',participants:[{id:'participant',benefitMinor:1000,costMinor:0,paymentMinor:amount,outsideOptionMinor:100}],costs:[{id:'shared-tool',category:'tools',amountMinor:amount}],alternatives:[]});
 const workflow=(name,increment)=>({name,inputs:['data'],effects:[],budget:{maxOperations:10000},steps:[{id:'result',op:'execute',dependsOn:['data'],args:{instrument:{name:'Internal increment',inputs:['x'],outputs:{value:{op:'add',args:[{field:'x'},increment]}}},input:{$ref:'data'}}}],outputs:['result']});
 for(const selectedMode of ['direct','transformational']){
  for(const kind of ['instrument','arrangement','workflow']){
   const savedProject=E.createProject({title:selectedMode+' '+kind+' import'});
   savedProject.workflow=workflow('Original workflow',100);savedProject.workflowSpec=workflow('Edited active workflow',200);savedProject.workflowInputs={data:{x:9}};
   let artifact;
   if(kind==='instrument'){
    savedProject.instrumentSpec={name:'Old instrument',inputs:['x'],outputs:{value:{field:'x'}}};
    artifact={summary:'New connected instrument',instrumentSpec:{name:'New '+selectedMode+' instrument',inputs:['x'],outputs:{value:{op:'add',args:[{field:'x'},4]}}},experimentInputs:{x:7}};
   }else if(kind==='arrangement'){
    savedProject.arrangement=arrangement(500);
    artifact={summary:'New connected arrangement',arrangement:arrangement(300)};
   }else{
    savedProject.workflow=workflow('Old workflow',100);
    savedProject.workflowSpec=workflow('Old executed alias',200);
    savedProject.workflowInputs={data:{x:1}};
    artifact={summary:'New connected workflow',workflow:workflow('New '+selectedMode+' workflow',4),experimentInputs:{data:{x:7}}};
   }
   t=boot('success',{artifact,savedProject});await pause(45);
   t.w.document.querySelector('input[value="'+selectedMode+'"]').click();t.click('bridge-generate');await pause(120);
   t.click('save-project');await pause(25);p=JSON.parse(t.w.localStorage.getItem('alpha-genesis-harness-project-v1'));
   assert.equal(t.requests.length,1);assert.equal(p.providerRuns[0].status,'IMPORTED');assert.equal(p.modelOutputs.length,1);
   assert.equal((p.artifactCandidates||[]).length,0,selectedMode+' must not require parallel-candidate selection');
   if(kind!=='workflow'){assert.deepEqual(p.workflowSpec,savedProject.workflowSpec,'An unrelated artifact must preserve the edited workflow');assert.deepEqual(p.workflowInputs,savedProject.workflowInputs);}
   t.w.document.querySelector('[data-view="experiment"]').click();
   if(kind==='instrument'){
    assert.equal(p.instrumentSpec.name,artifact.instrumentSpec.name,selectedMode+' must activate the new instrument');
    t.click('run-experiment');await pause(80);t.click('save-project');await pause(25);const executed=JSON.parse(t.w.localStorage.getItem('alpha-genesis-harness-project-v1')).runs.at(-1);assert.equal(executed.execution.outputs.value,11);assert.equal(executed.execution.verdict,'PASSED IN SCOPE');
   }else if(kind==='arrangement'){
    assert.equal(p.arrangement.costs[0].amountMinor,300,selectedMode+' must activate the new arrangement');
    assert.equal(p.instrumentSpec,undefined);t.click('check-economics');await pause(25);assert.match(t.w.document.getElementById('economics-result').textContent,/PASSED IN SCOPE/);
   }else{
    assert.equal(p.workflow.name,artifact.workflow.name,selectedMode+' must activate the new workflow');
    assert.equal(p.workflowSpec,undefined,'Stale executed workflow alias must be cleared');assert.equal(p.workflowInputs,undefined,'Stale saved workflow inputs must be cleared');
    assert.equal(JSON.parse(t.w.document.getElementById('workflow-data').value).data.x,7);
    t.click('run-workflow');await pause(40);assert.equal(JSON.parse(t.w.document.getElementById('workflow-result').textContent).outputs.result.outputs.value,11);
   }
   assert.deepEqual(t.errors,[]);t.d.window.close();
  }
 }
 // Commentary alone must not discard a previously edited/executed workflow.
 for(const importMode of ['direct','transformational','manual']){
  for(const responseText of [JSON.stringify({summary:'Additional commentary; no replacement artifact.'}),'Plain prose commentary only.']){
   const savedProject=E.createProject({title:importMode+' commentary preservation'});
   savedProject.workflow=workflow('Original workflow',100);savedProject.workflowSpec=workflow('Edited active workflow',200);savedProject.workflowInputs={data:{x:9}};
   t=boot('success',{savedProject,responseText});await pause(45);
   if(importMode==='manual'){t.w.document.getElementById('model-response').value=responseText;t.click('import-response');}
   else{t.w.document.querySelector('input[value="'+importMode+'"]').click();t.click('bridge-generate');}
   await pause(120);t.click('save-project');await pause(25);p=JSON.parse(t.w.localStorage.getItem('alpha-genesis-harness-project-v1'));
   assert.equal(p.modelOutputs.length,1);assert.deepEqual(p.workflowSpec,savedProject.workflowSpec,importMode+' commentary must preserve edited workflow');assert.deepEqual(p.workflowInputs,savedProject.workflowInputs,importMode+' commentary must preserve workflow inputs');
   t.w.document.querySelector('[data-view="experiment"]').click();t.click('run-workflow');await pause(40);
   assert.equal(JSON.parse(t.w.document.getElementById('workflow-result').textContent).outputs.result.outputs.value,209,'Preserved edited workflow must remain executable');
   assert.deepEqual(t.errors,[]);t.d.window.close();
  }
 }
 console.log(JSON.stringify({verdict:'PASSED IN SCOPE',environment:'jsdom mock bridge; no provider requests or graphical browser',checks:['concurrent independent two-model requests','frozen identical mission prompts','every successful contribution and usage retained','explicit artifact selection (no last-model overwrite)','partial provider failure preserved with unknown costs','all-run cancellation and suppression of late responses','active-workspace replacement refused at action time','deferred file-read confirmation cannot redirect request ownership','delayed cancellation acknowledgement retained on originating project','direct connected responses install each active artifact kind','transformational connected responses install each active artifact kind','connected workflow replacement clears stale aliases and inputs','commentary-only manual/direct/transformational imports preserve edited workflows','unrelated instrument/arrangement imports preserve edited workflows']},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
