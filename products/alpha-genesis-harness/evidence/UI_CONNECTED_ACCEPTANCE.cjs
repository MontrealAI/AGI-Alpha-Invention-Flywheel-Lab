/* SPDX-License-Identifier: Apache-2.0
 * Independently authored connected-import acceptance scenarios.
 * Runs the actual UI controller with in-memory bridge responses; no network,
 * credentials, graphical browser or authenticated provider qualification.
 * Requires development-only jsdom 26.1.0 via NODE_PATH; never bundled.
 * Baseline failures and reviewed source hashes are in INDEPENDENT_REVIEW.md
 * and acceptance-results.json; this replay asserts the corrected behavior.
 */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM,VirtualConsole}=require('jsdom');
const root=path.resolve(__dirname,'..','app');
const STORE='alpha-genesis-harness-project-v1';const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function until(fn){for(let i=0;i<200;i++){if(fn())return;await pause(5);}throw Error('UI state not reached');}
function source(file){return fs.readFileSync(path.join(root,file),'utf8');}
const instrument=(name,n)=>({name,inputs:['x'],outputs:{value:{op:'add',args:[{field:'x'},n]}}});
const workflow=(name,n)=>({name,inputs:['data'],effects:[],budget:{maxOperations:10000},steps:[{id:'instrument',op:'construct',dependsOn:[],args:instrument(name,n)},{id:'result',op:'execute',dependsOn:['instrument','data'],args:{instrument:{$ref:'instrument'},input:{$ref:'data'}}}],outputs:['result']});
const arrangement={currency:'CAD',participants:[{id:'review-member',benefitMinor:100,costMinor:20,paymentMinor:0,outsideOptionMinor:10}],costs:[],alternatives:[{id:'ordinary',name:'Ordinary route',totalCostMinor:20,feasible:true}]};
const fresh={instrumentSpec:instrument('review instrument B',7),workflow:workflow('review workflow B',7),arrangement,experimentInputs:{x:4}};
async function boot(mode,initial={},response=fresh){
 const errors=[],requests=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));
 const dom=new JSDOM(source('index.html'),{url:'http://127.0.0.1:8877/',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc}),w=dom.window;
 w.scrollTo=()=>{};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};
 const reply=(x)=>({ok:true,json:async()=>w.JSON.parse(JSON.stringify(x))});
 const status={providers:[{id:'review',label:'Review fixture',ready:true,models:['fixture-model']}],budget:{currency:'CAD',remaining:10}};
 w.fetch=async(url,options={})=>{if(url==='/api/session')return reply({token:'fixture-only'});if(url==='/api/status')return reply(status);if(url==='/api/generate'){const body=JSON.parse(options.body);requests.push(body);await pause(5);return reply({provider:'review',model:'fixture-model',text:typeof response==='string'?response:JSON.stringify(response),usage:{input_tokens:10,output_tokens:20},cost:{amount:0.01,currency:'CAD',complete_cost_known:false}});}throw Error('Unexpected fixture route '+url);};
 w.eval(source('engine.js'));const p=w.HarnessEngine.createProject({title:'Independent import review',objective:'Execute the proposed instrument'});Object.assign(p,w.JSON.parse(JSON.stringify(initial)));p.mode=mode;w.localStorage.setItem(STORE,w.HarnessEngine.exportProject(p));w.eval(source('app.js'));
 await until(()=>!w.document.getElementById('bridge-generate').disabled&&!w.document.getElementById('bridge-controls').classList.contains('hidden'));
 const click=id=>w.document.getElementById(id).click();
 const saved=async()=>{click('save-project');await pause(5);return JSON.parse(w.localStorage.getItem(STORE));};
 return {w,dom,click,saved,requests,errors};
}
async function inspect(mode,initial={}){const t=await boot(mode,initial);t.click('bridge-generate');await until(()=>t.requests.length===1&&!t.w.document.getElementById('bridge-generate').disabled);let p=await t.saved();const result={mode,contribution_count:p.modelOutputs.length,candidate_count:p.artifactCandidates?.length||0,active_instrument:p.instrumentSpec?.name||null,active_workflow:p.workflow?.name||null,workflow_alias:p.workflowSpec?.name||null,workflow_inputs:p.workflowInputs||null,arrangement_active:!!p.arrangement,run_status:p.providerRuns.at(-1).status,project_id:p.id,batch_project_id:p.runs.at(-1).projectId};
  assert.equal(result.run_status,'IMPORTED');assert.equal(result.project_id,result.batch_project_id);
  if(mode==='parallel'){
   assert.equal(result.candidate_count,1);assert.equal(result.active_instrument,null);assert.equal(result.active_workflow,null);assert.equal(result.arrangement_active,false);
   const select=[...t.w.document.querySelectorAll('#contribution-list button')].find(x=>x.textContent.includes('Use this proposed artifact'));assert.ok(select);select.click();
   p=await t.saved();assert.equal(p.instrumentSpec.name,'review instrument B');assert.equal(p.workflow.name,'review workflow B');
  }else{
   assert.equal(result.candidate_count,0);assert.equal(result.active_instrument,'review instrument B');assert.equal(result.active_workflow,'review workflow B');assert.equal(result.arrangement_active,true);assert.equal(p.workflowSpec,undefined);assert.equal(p.workflowInputs,undefined);
  }
  t.w.document.querySelector('[data-view="experiment"]').click();assert.match(t.w.document.getElementById('workflow-input').value,/review workflow B/);t.click('run-workflow');await until(()=>t.w.document.getElementById('workflow-result').textContent.includes('PASSED IN SCOPE'));const executed=JSON.parse(t.w.document.getElementById('workflow-result').textContent);result.executed=executed;assert.equal(executed.outputs.result.outputs.value,11);
  p=await t.saved();const reopen=t.w.HarnessEngine.importProject(t.w.localStorage.getItem(STORE));assert.equal(reopen.workflow.name,'review workflow B');assert.equal(reopen.modelOutputs.length,1);assert.deepEqual(t.errors,[]);
 t.dom.window.close();return result;}
(async()=>{
 const initial={workflow:workflow('original workflow',2),workflowSpec:workflow('edited active workflow',5),workflowInputs:{data:{x:99}}};
 const results=[];
 const activationResults=[];
 for(const mode of ['direct','transformational','parallel'])activationResults.push(await inspect(mode));
 for(const mode of ['direct','transformational'])activationResults.push(await inspect(mode,initial));
 for(const route of ['direct','transformational','manual'])for(const [kind,response] of Object.entries({summary:{summary:'Independent critique; no new workflow proposed.'},prose:'Independent prose critique only; no new workflow proposed.',instrument:{summary:'A separate instrument proposal',instrumentSpec:instrument('unrelated instrument',3),experimentInputs:{x:4}}})){
  const t=await boot(route==='manual'?'direct':route,initial,response);
  if(route==='manual'){t.w.document.getElementById('model-response').value=typeof response==='string'?response:JSON.stringify(response);t.click('import-response');}
  else{t.click('bridge-generate');await until(()=>t.requests.length===1&&!t.w.document.getElementById('bridge-generate').disabled);}
  let p=await t.saved();assert.deepEqual(p.workflow,initial.workflow,route+' '+kind+' original workflow');assert.deepEqual(p.workflowSpec,initial.workflowSpec,route+' '+kind+' active definition');assert.deepEqual(p.workflowInputs,initial.workflowInputs,route+' '+kind+' active inputs');assert.equal(p.modelOutputs.length,1);
  t.w.document.querySelector('[data-view="experiment"]').click();assert.match(t.w.document.getElementById('workflow-input').value,/edited active workflow/);assert.equal(JSON.parse(t.w.document.getElementById('workflow-data').value).data.x,99);t.click('run-workflow');await until(()=>t.w.document.getElementById('workflow-result').textContent.includes('PASSED IN SCOPE'));const result=JSON.parse(t.w.document.getElementById('workflow-result').textContent);assert.equal(result.outputs.result.outputs.value,104);
  p=await t.saved();const reopen=JSON.parse(t.w.HarnessEngine.exportProject(t.w.HarnessEngine.importProject(t.w.localStorage.getItem(STORE))));assert.deepEqual(reopen.workflowSpec,initial.workflowSpec);assert.deepEqual(reopen.workflowInputs,initial.workflowInputs);assert.deepEqual(t.errors,[]);results.push({route,response_kind:kind,active_workflow_preserved:true,active_inputs_preserved:true,executed_value:104,reopened:true});t.dom.window.close();
 }
 const t=await boot('direct',initial);t.w.document.getElementById('model-response').value=JSON.stringify(fresh);t.click('import-response');let p=await t.saved();assert.equal(p.workflow.name,'review workflow B');assert.equal(p.workflowSpec,undefined);assert.equal(p.workflowInputs,undefined);t.w.document.querySelector('[data-view="experiment"]').click();t.click('run-workflow');await until(()=>t.w.document.getElementById('workflow-result').textContent.includes('PASSED IN SCOPE'));assert.equal(JSON.parse(t.w.document.getElementById('workflow-result').textContent).outputs.result.outputs.value,11);assert.deepEqual(t.errors,[]);results.push({route:'manual',response_kind:'new workflow',stale_aliases_cleared:true,executed_value:11});t.dom.window.close();
 console.log(JSON.stringify({verdict:'PASSED IN SCOPE',scenarios_passed:activationResults.length+results.length,scenarios_failed:0,checks:['direct and transformational activate all supplied artifact kinds','parallel activates a candidate only after selection','replacement workflows clear stale aliases and execute11','commentary, prose and unrelated instruments preserve edited workflows and execute104','active workflow and inputs survive save/reopen'],scope:'Independent jsdom controller with in-memory responses; no network or authenticated model calls'},null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
