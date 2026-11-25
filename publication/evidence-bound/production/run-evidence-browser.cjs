'use strict';
const assert = require('node:assert/strict');
const {readFileSync, writeFileSync} = require('node:fs');
const {join} = require('node:path');
const {createHash} = require('node:crypto');
const {chromium} = require('playwright-core');

const {base, resultDir, connectorLog, ambition, language, mode, archiveName} = JSON.parse(process.env.FRONTIER_EXECUTION_TEST);
const endpoint = 'http://127.0.0.1:38463/api/frontier-missions/';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const fixture = readFileSync('tests/live_frontier_browser.cjs','utf8')
  .match(/function fakeWallet\(\) \{[\s\S]*?\n\}(?=\n\nasync function foundryJourney)/u)?.[0];
assert.ok(fixture);

(async () => {
  const proxy = new URL(base).protocol === 'https:' && process.env.HTTPS_PROXY;
  const browser = await chromium.launch({executablePath:process.env.FRONTIER_CHROME,
    proxy:proxy ? {server:new URL(proxy).origin,bypass:'127.0.0.1,localhost'} : undefined});
  const context = await browser.newContext({viewport:language === 'fr' ? {width:390,height:844} : {width:1440,height:900},
    reducedMotion:'reduce', acceptDownloads:true});
  await context.grantPermissions(['local-network-access'],{origin:new URL(base).origin});
  await context.addInitScript({content:fixture + '\nfakeWallet();'});
  const operations = [], submitted = [], errors = [];
  const localCode = () => {
    const pattern = /FRONTIER Ω one-use pairing code: ([A-Za-z0-9_-]{43})/gu;
    return [...readFileSync(connectorLog,'utf8').matchAll(pattern)].at(-1)?.[1];
  };
  const open = async () => {
    const page = await context.newPage();
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request', req => {
      if (req.method() !== 'POST') return;
      if (!req.url().startsWith(endpoint)) {errors.push('Unexpected outbound submission'); return;}
      const operation = req.url().slice(endpoint.length);
      operations.push(operation);
      if (operation === 'submit') submitted.push(req.postDataJSON());
    });
    assert.equal((await page.goto(base+(language==='fr'?'fr.html':'')+'#my-frontier')).status(),200);
    await page.locator('[data-connect="token"]').click();
    await page.locator('#member').waitFor({state:'visible'});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),true);
    return page;
  };
  const pair = async (page,code) => {
    await page.locator('.mf-intelligence-link').press('Enter');
    const outer=page.locator('#mission-intelligence');
    if (!(await outer.evaluate(el=>el.open))) await outer.locator(':scope > summary').click();
    const details = outer.locator('.mission-execution-connection');
    if (!(await details.evaluate(el=>el.open))) await details.locator(':scope > summary').click();
    await page.locator('#execution-code').evaluate((element,value)=>{element.value=value;},code);
    const response = page.waitForResponse(r=>r.url()===endpoint+'pair' && r.request().method()==='POST');
    await page.locator('#execution-code-form button').click();
    const paired=await response;
    assert.equal(paired.status(),200);
    await page.locator('#intelligence-local-controls').waitFor({state:'visible'});
    return (await paired.json()).intelligence?.selection;
  };
  const readSaved = async page => {
    await page.locator('.mf-destinations a[href="#mv-results"]').press('Enter');
    const history=page.locator('#mission-keeper');
    if (!(await history.evaluate(el=>el.open))) await history.locator(':scope > summary').click();
    await page.locator('#execution-open-saved').click();
    await page.locator('#execution-saved-list button').filter({hasText:ambition}).first().click();
    await page.waitForFunction(text=>document.getElementById('mission-ambition').textContent===text,ambition);
    await page.locator('#mission-execution').waitFor({state:'visible'});
  };
  const safeSelection = value=>({model:value.model_label,provider:value.provider,mode:value.mode,ready:value.ready,
    check:value.verification});

  try {
    const guide = await context.newPage();
    const guideURL=readFileSync(process.env.FRONTIER_PAIR_GUIDE_FILE,'utf8').trim();
    assert.equal(new URL(guideURL).origin,'http://127.0.0.1:38463');
    assert.equal((await guide.goto(guideURL)).status(),200);
    const code=(await guide.locator('code').textContent()).trim();
    assert.ok(code === localCode());
    assert.equal((await guide.reload()).status(),404);
    await guide.close();
    let page=await open();
    const receipt=JSON.parse(readFileSync(join(resultDir,'live-release.json'),'utf8'));
    const module=await (await context.request.get(base+'frontier-execution.mjs')).body();
    assert.equal(digest(module),receipt.universal_mission_sha256['frontier-execution.mjs']);
    let selection, discovery, reopened=false;
    if (mode === 'start') {
      await page.locator('#goal-text').fill(ambition);
      await page.locator('#goal-submit').press('Enter');
      await page.waitForFunction(text=>document.getElementById('mission-ambition').textContent===text,ambition);
      const prior = await pair(page,code);
      assert.equal(prior,null);
      assert.deepEqual(submitted,[]);
      const found=page.waitForResponse(r=>r.url()===endpoint+'intelligence-discover' && r.request().method()==='POST');
      await page.locator('#intelligence-discover').press('Enter');
      const response=await found;
      assert.equal(response.status(),200);
      discovery=await response.json();
      await page.locator('#intelligence-select-form').waitFor({state:'visible'});
      const choice=discovery.candidates.find(row=>row.engine==='llama-cpp');
      assert.ok(choice,'Expected an automatically discovered llama.cpp model');
      await page.locator('#intelligence-choice').selectOption(choice.id);
      await page.locator('#intelligence-hybrid').check();
      const checked=page.waitForResponse(r=>r.url()===endpoint+'intelligence-connect' && r.request().method()==='POST');
      await page.locator('#intelligence-select-form button').press('Enter');
      const connected=await checked;
      assert.equal(connected.status(),200);
      selection=(await connected.json()).selection;
      assert.equal(selection.ready,true);
      assert.equal(selection.mode,'hybrid');
      await page.waitForFunction(text=>!document.getElementById('frontier-mission-panel').hidden && document.getElementById('mission-ambition').textContent===text && !!document.getElementById('mission-execution').dataset.state,ambition,{timeout:20000});
      assert.deepEqual(submitted,[{ambition,language}]);
      await page.close();
      page=await open();
      const sameProcess=await pair(page,localCode());
      assert.equal(sameProcess.provider,selection.provider);
      assert.equal(sameProcess.ready,true);
      await readSaved(page);
      reopened=true;
    } else {
      const saved=await pair(page,code);
      assert.equal(saved.ready,false);
      const expected=page.waitForResponse(r=>r.url()===endpoint+'intelligence-reconnect' && r.request().method()==='POST');
      await page.locator('#intelligence-reconnect').press('Enter');
      const response=await expected;
      assert.equal(response.status(),200);
      selection=(await response.json()).selection;
      assert.equal(selection.provider,saved.provider);
      assert.equal(selection.ready,true);
      assert.ok(selection.verification.at >= saved.verification.at);
      await readSaved(page);
      reopened=true;
    }
    const finished = () => page.waitForFunction(()=>{const root=document.getElementById('mission-execution');
      return root.dataset.state && !['ready','running'].includes(root.dataset.state) && !document.getElementById('execution-export').disabled;
    },null,{timeout:500000});
    await finished();
    const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#execution-export').click()]);
    const archive=readFileSync(await download.path());
    const {state,sha256,files}=JSON.parse(archive);
    const visibleClaims=await page.locator('#execution-claims li').allTextContents();
    const outcomeLocator = page.locator('#execution-evidence');
    const visibleOutcome = await outcomeLocator.isVisible() ? await outcomeLocator.innerText() : null;
    assert.equal(state.spec.mission.original_ambition,ambition);
    assert.equal(state.spec.mission.language,language);
    assert.deepEqual(submitted,mode==='start' ? [{ambition,language}] : []);
    assert.deepEqual(errors,[]);
    const observations={release_revision:receipt.source_commit, workflow_run:receipt.workflow_run,
      executor_sha256:receipt.universal_mission_sha256[archiveName ?? 'frontier-harness-executor-1.1.0.zip'],module_sha256:digest(module),
      base,language,mode,ambition,wallet:'isolated eligibility fixture',selection:safeSelection(selection),
      discovery:discovery?.candidates.map(({model,engine,configured})=>({model,engine,configured})),
      setup:{guide_one_use:true,exact_submit_count:submitted.length,automatic_return:mode==='start',reopened},
      visible_claims:visibleClaims,visible_outcome:visibleOutcome,
      state:{id:state.id,status:state.status,phase:state.phase,model_calls:state.model_calls,actions:state.actions,
        evidence:state.evidence,qualification:state.qualification,files:Object.keys(files),
        recorded_events:state.events.map(({kind,detail})=>({kind,tool:detail?.tool,reason:detail?.reason,usage:detail?.usage}))},
      checkpoint_sha256:sha256,export_sha256:digest(archive),operations:[...new Set(operations)]};
    writeFileSync(join(resultDir,mode+'-archive.private.json'),archive,{mode:0o600});
    writeFileSync(join(resultDir,mode+'-receipt.json'),JSON.stringify(observations,null,2)+'\n',{mode:0o600});
    const follow = process.env.FRONTIER_FOLLOWUP_GOAL;
    if (follow && mode === 'start') {
      const configCalls = operations.filter(operation => operation.startsWith('intelligence-')).length;
      await page.locator('.mf-destinations a[href="#my-frontier"]').press('Enter');
      await page.locator('#mission-new').press('Enter');
      await page.locator('#goal-text').fill(follow);
      const secondResponse = page.waitForResponse(response => response.url() === endpoint+'submit' && response.request().method() === 'POST');
      await page.locator('#goal-submit').press('Enter');
      await page.waitForFunction(text => document.getElementById('mission-ambition').textContent === text, follow);
      const secondRun = await secondResponse;
      assert.equal(secondRun.status(),200);
      const second = await secondRun.json();
      assert.notEqual(second.id,state.id);
      assert.equal(second.original_ambition,follow);
      await finished();
      const [continued] = await Promise.all([page.waitForEvent('download'),page.locator('#execution-export').click()]);
      const followBytes = readFileSync(await continued.path());
      const followExport = JSON.parse(followBytes);
      assert.deepEqual(submitted,[{ambition,language},{ambition:follow,language}]);
      assert.equal(operations.filter(operation => operation.startsWith('intelligence-')).length,configCalls);
      assert.equal(followExport.state.spec.mission.original_ambition,follow);
      assert.deepEqual(errors,[]);
      writeFileSync(join(resultDir,'followup-archive.private.json'),followBytes,{mode:0o600});
      writeFileSync(join(resultDir,'followup-receipt.json'),JSON.stringify({revision:receipt.source_commit,
        same_pair:true,same_model:selection.model_label,new_intelligence_setup_calls:0,id:second.id,original_ambition:follow,
        status:followExport.state.status,model_calls:followExport.state.model_calls,actions:followExport.state.actions,
        artifacts:Object.keys(followExport.files),checkpoint_sha256:followExport.sha256,export_sha256:digest(followBytes),
        visible_outcome:await outcomeLocator.innerText()},null,2)+'\n',{mode:0o600});
    }
    process.stdout.write(JSON.stringify({language,mode,status:state.status,model_calls:state.model_calls,actions:state.actions, files:Object.keys(files),checkpoint_sha256:sha256})+'\n');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error.message);process.exitCode=1;});
