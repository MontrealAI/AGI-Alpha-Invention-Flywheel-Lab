/* SPDX-License-Identifier: Apache-2.0
 * Real HTTP + DOM + Runtime + WorkflowService integration. Only the provider's
 * inference response is an authored fixture; no live model or graphical browser.
 */
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {JSDOM,VirtualConsole}=require('jsdom');
const product=path.resolve(__dirname,'..');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function until(predicate,label){for(let i=0;i<150;i++){if(await predicate())return;await pause(50);}throw Error('Timed out: '+label);}
const fixture=String.raw`
import json,sys
from bridge.adapters import Runtime
from bridge.server import HarnessServer
calls=0
def sender(url,headers,body=None,timeout=60):
    global calls
    prompt=body['messages'][0]['content']
    data=json.loads(prompt.split('UNTRUSTED_WORKSPACE_DATA\n',1)[1])
    if 'You are a separate critic call.' in prompt:
        output={'verdict':'accept' if data['verification']['passed'] else 'revise','feedback':'Check the frozen multiplication cases. No broader claim.'}
    elif 'You are an independent adversarial invocation.' in prompt:
        output={'counterexamples':[{'artifact':'calculator.json','input':{'price':7,'quantity':3},'expected':{'total':21},'reason':'Check the existing frozen case independently.'}],'feedback':'Fixture uses operator-frozen expected output.'}
    elif 'Identify transferable mechanism' in prompt or 'Evaluate complete construction' in prompt:
        output='Authored analysis fixture; costs and external applicability remain unknown.'
    else:
        calls+=1
        output={'summary':'Authored transport fixture, not a model inference','actions':[{'tool':'construct_instrument','name':'calculator.json','spec':{'name':'HTTP fixture quote','inputs':['price','quantity'],'outputs':{'total':{'op':'add' if calls==1 or 'fixture-rejected' in data['context'] or 'Use the strongest direct conventional approach first.' in data['context'] else 'mul','args':[{'field':'price'},{'field':'quantity'}]}}}}],'done':True}
    return {'message':{'content':json.dumps(output)},'prompt_eval_count':10,'eval_count':50}
config={'local_only':True,'providers':{'local-fixture':{'kind':'ollama','label':'Authored local fixture','base_url':'http://127.0.0.1:1','models':{'fixture-builder':{'input_per_million':0,'output_per_million':0},'fixture-critic':{'input_per_million':0,'output_per_million':0}}}}}
server=HarnessServer(('127.0.0.1',0),Runtime(config,sender=sender),config=config,workspace=sys.argv[1])
print(server.origin,flush=True)
server.serve_forever()
`;
(async()=>{
 const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'harness-ui-http-')),child=spawn(process.env.PYTHON||'python3',['-c',fixture,workspace],{cwd:product,stdio:['ignore','pipe','pipe']});
 let dom;let stderr='';child.stderr.on('data',d=>stderr+=d.toString());
 try{
  const origin=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error('Fixture server did not start: '+stderr)),10000);child.stdout.on('data',d=>{out+=d;const line=out.split('\n')[0];if(/^http:\/\/127\.0\.0\.1:\d+$/.test(line)){clearTimeout(timer);resolve(line);}});child.on('exit',code=>{clearTimeout(timer);reject(Error('Fixture server exit '+code+': '+stderr));});});
  const errors=[],downloads=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e.message));dom=new JSDOM(fs.readFileSync(path.join(product,'app/index.html'),'utf8'),{url:origin,runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});const w=dom.window;
  w.scrollTo=()=>{};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};w.HTMLAnchorElement.prototype.click=()=>{};w.Blob=class{constructor(parts){this.parts=parts}};w.URL.createObjectURL=b=>{downloads.push(b.parts[0]);return 'blob:test'};w.URL.revokeObjectURL=()=>{};
  w.fetch=async(url,opts)=>{const response=await fetch(new URL(url,origin),opts);return {ok:response.ok,status:response.status,json:async()=>w.JSON.parse(await response.text()),blob:()=>response.blob()};};
  for(const file of ['engine.js','app.js'])w.eval(fs.readFileSync(path.join(product,'app',file),'utf8'));
  const $=id=>w.document.getElementById(id);const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new w.Event('input',{bubbles:true}));};
  await until(()=>$('agent-create').disabled===false,'bridge connected');
  fill('mission-name','Actual HTTP workflow');fill('mission-objective','Construct a transparent price times quantity calculator');fill('agent-critic-model','fixture-critic');fill('agent-acceptance',JSON.stringify([{input:{price:7,quantity:3},expected:{total:21}},{input:{price:0,quantity:4},expected:{total:0}}]));$('agent-permission').checked=true;$('agent-create').click();
  try{await until(()=>$('agent-state').textContent.startsWith('Complete'),'actual construction completion');}catch(error){error.message+='; state='+$('agent-state').textContent+'; notice='+$('notice').textContent+'; trace='+$('agent-trace').textContent+'; server='+stderr;throw error;}
  assert.match($('agent-trace').textContent,/verification/);assert.match($('agent-trace').textContent,/false/,'Failed first attempt is retained');assert.equal($('agent-artifacts').querySelectorAll('article').length,2,'Constructed instrument and independent runner available');
  $('agent-export').click();await until(()=>downloads.length===1,'JSON export');const exported=JSON.parse(downloads[0]);assert.equal(exported.state.status,'complete');assert.equal(exported.state.model_calls,4,'Builder, critic, repair, critic all executed');assert.equal(exported.state.verification.passed,true);assert.equal(exported.state.spec.acceptance[0].expected.total,21);assert.ok(exported.files['RUN_INSTRUMENT.py']);
  $('agent-download').click();await until(()=>downloads.length===2,'ZIP export');const bytes=Buffer.from(await downloads[1].arrayBuffer());assert.equal(bytes.subarray(0,2).toString(),'PK');
  $('capabilities-refresh').click();await until(()=>$('connected-capability-list').querySelector('textarea'),'actual retained registry');const reuse=$('connected-capability-list').querySelector('textarea');reuse.value='{"price":13,"quantity":11}';$('connected-capability-list').querySelector('button').click();await until(()=>$('connected-capability-list').textContent.includes('EXECUTED_NOT_SUCCESSOR_ACCEPTED'),'actual retained execution');assert.match($('connected-capability-list').textContent,/143/);assert.equal($('agent-inherit').options.length,2);
  const imported=$('agent-run-file');Object.defineProperty(imported,'files',{configurable:true,value:[{size:JSON.stringify(exported).length,text:async()=>JSON.stringify(exported)}]});imported.dispatchEvent(new w.Event('change',{bubbles:true}));await until(()=>$('agent-state').textContent==='Paused'||$('notice').classList.contains('error'),'import completes or reports failure');assert.equal($('agent-state').textContent,'Paused',$('notice').textContent);assert.equal($('agent-resume').disabled,false);assert.match($('agent-progress').textContent,/Acceptance has not passed/);
  $('history-refresh').click();await until(()=>$('history-connected').querySelectorAll('article').length===2,'two actual persisted runs');
  const strategies=[];
  for(const strategy of ['single-model','researcher-builder-verifier','strategist-economist','parallel-exploration','adaptive','adversarial-review']){
   const previous=$('agent-contract').textContent;fill('mission-objective','Construct a transparent price times quantity calculator');$('agent-strategy').value=strategy;$('agent-strategy').dispatchEvent(new w.Event('change'));fill('agent-approaches',strategy==='parallel-exploration'?'fixture-rejected: test an incorrect sum.\nfixture-accepted: multiply price and quantity.':'Construct multiplication directly.\nCompose multiplication as a declared operation.');$('agent-create').click();
   try{await until(()=>$('agent-contract').textContent!==previous&&$('agent-state').textContent.startsWith('Complete'),'strategy '+strategy);}catch(error){error.message+='; state='+$('agent-state').textContent+'; notice='+$('notice').textContent+'; trace='+$('agent-trace').textContent;throw error;}
   const count=downloads.length;$('agent-export').click();await until(()=>downloads.length===count+1,'strategy export '+strategy);const result=JSON.parse(downloads.at(-1));assert.equal(result.state.spec.strategy,strategy);assert.equal(result.state.verification.passed,true);
   if(strategy==='parallel-exploration'){assert.equal(result.branch_exports.length,2);assert.ok(result.branch_exports.some(b=>b.state.status==='exhausted'));assert.ok(result.state.selected_branch);assert.match($('agent-progress').textContent,/retained/);assert.equal(result.state.model_calls,6);}
   if(strategy==='adaptive'){assert.equal(result.branch_exports.length,3);assert.ok(result.state.events.some(e=>e.kind==='strategy_switched'));assert.equal(result.state.model_calls,6);}
   if(strategy==='adversarial-review')assert.ok(result.state.events.some(e=>e.kind==='adversarial_review'));
   strategies.push({strategy,model_calls:result.state.model_calls,passed:result.state.verification.passed});
  }
  // Imported recorded results are never promoted into current acceptance.
  assert.deepEqual(errors,[]);console.log(JSON.stringify({status:'PASS',scope:'Actual loopback HTTP, native Runtime and WorkflowService; authored inference fixtures; DOM only',checks:['builder critic repair executed with frozen cases','original failed checks preserved','real artifact and ZIP export','retained capability registry and new input execution','validated JSON import resets checks and pauses','persistent run history and explicit resume controls','six additional strategies execute real server and runner paths; parallel preserves failed branch, adaptive switches after failure'],strategies,model_calls:exported.state.model_calls,artifact_count:Object.keys(exported.files).length},null,2));
 }finally{if(dom)dom.window.close();child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)return resolve();child.once('exit',resolve);});fs.rmSync(workspace,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1});
