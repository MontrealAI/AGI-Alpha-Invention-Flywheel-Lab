'use strict';
// These authored responses qualify UI wiring through the real local service.
// They do not qualify a live model. No model endpoints or source feeds are used.
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { spawn, execFileSync } = require('node:child_process');
const { once } = require('node:events');
const { createInterface } = require('node:readline');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright-core');
const product = path.resolve(__dirname, '..');
const { qualifyMappingChoice } = require('./mapping_choice.cjs');
const { qualifyEndpointDecision } = require('./endpoint_operator.cjs');
const { qualifyFollowup } = require('./followup_operator.cjs');
const { qualifyChangeDesk } = require('./change_operator.cjs');
const { qualifyAdaptiveRepair, qualifyPairingDecision, qualifyPublicBoundary } = require('./adaptive_operator.cjs');

async function assertLayout(page, width) {
  await page.setViewportSize({ width, height: 820 });
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),true,
    `Horizontal overflow at ${width}px`);
}
async function send(page, stage, response) {
  await page.waitForFunction(s => {
    const text=document.getElementById('raw').textContent;
    if (!text) return false;
    const r=JSON.parse(text);
    return r.status==='awaiting_model' && r.handoff?.stage===s;
  },stage);
  await page.locator('#response').fill(JSON.stringify(response));
  await page.locator('#respond').click();
}
async function receive(page, selector, dest) {
  const wait=page.waitForEvent('download');
  await page.locator(selector).click();
  await (await wait).saveAs(dest);
}
async function qualifyMissionControls(page, work) {
  const run = JSON.parse(await page.locator('#raw').textContent());
  const bundle = new URL(await page.locator('#bundle').getAttribute('href'), page.url()).href;
  const summary = page.locator('#commercial-record > summary');
  await summary.click();
  await page.waitForFunction(() => document.querySelector('#commercial-state').textContent.toLowerCase().startsWith('unassessed'));
  await summary.click();

  // The local operator imports a labeled fixture. Only its digest and attribution enter the record.
  const cli = ['-B', '-m', 'ignition', '--state', work, '--assisted', 'UI qualification', 'authored test data',
    'commercial', run.id, '--version', String(run.version)];
  const imported = JSON.parse(execFileSync('python3', [...cli, '--template', 'identified'], {cwd:product}));
  const evidence = Buffer.from('Synthetic beneficiary interview for the operator interface check.\n');
  const source = path.join(work, 'operator-source.txt');
  const record = path.join(work, 'operator-observation.json');
  imported.counterparty = 'Synthetic UI beneficiary';
  imported.reviewer = 'Synthetic operator';
  imported.details = {problem:'Synthetic review workload', current_alternative:'Manual review', contact_route:'Fixture'};
  imported.evidence.public_need = {source:'Synthetic interview fixture', sha256:createHash('sha256').update(evidence).digest('hex')};
  await fs.writeFile(source, evidence);
  await fs.writeFile(record, JSON.stringify(imported));
  const observed = JSON.parse(execFileSync('python3', [...cli, '--record', record, '--evidence', 'public_need=' + source], {cwd:product}));
  assert.equal(observed.collected_revenue, null);
  await summary.click();
  await page.locator('#commercial-events li').filter({hasText:'Synthetic UI beneficiary'}).waitFor();
  assert.match(await page.locator('#commercial-state').textContent(), /identified/i);

  await assertLayout(page, 390);
  const draft = 'Unsaved new beneficiary';
  await page.locator('#beneficiary').fill(draft);
  await page.locator('#pause-operation').click();
  await page.waitForFunction(() => document.querySelector('#operation-state').textContent === 'Mission paused');
  assert.equal(await page.locator('#beneficiary').inputValue(), draft);
  assert.equal((await page.request.get(bundle)).status(), 409);
  await page.reload();
  await page.locator('#resume-operation:visible').click();
  await page.waitForFunction(() => document.querySelector('#operation-state').textContent === 'Mission active');
  assert.equal((await page.request.get(bundle)).status(), 200);
  page.once('dialog', dialog => dialog.accept());
  await page.locator('#stop-operation').click();
  await page.waitForFunction(() => document.querySelector('#operation-state').textContent === 'Mission stopped');
  await page.reload();
  await page.waitForFunction(() => document.querySelector('#operation-state').textContent === 'Mission stopped');
  assert.equal(await page.locator('#resume-operation').isVisible(), false);
  assert.equal((await page.request.get(bundle)).status(), 409);
  const stopped = JSON.parse(await page.locator('#raw').textContent());
  assert.deepEqual(stopped.operation.history.map(event => event.action), ['pause', 'resume', 'stop']);
}
async function publicReplayCheck(browser,work) {
  const server=spawn('python3',['-B','-m','ignition','--state',path.join(work,'replays'),'serve','--port','0'],
    {cwd:product,env:{...process.env,IGNITION_MODEL_PROVIDER:'unavailable'},stdio:['ignore','pipe','inherit']});
  const lines=createInterface({input:server.stdout});
  let context;
  try {
    const [ready]=await Promise.race([once(lines,'line'),once(server,'exit').then(()=>{throw Error('Replay service exited');})]);
    const origin=ready.match(/http:\/\/127\.0\.0\.1:\d+/)[0];
    context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'});
    const page=await context.newPage();const mutations=[];
    page.on('request',req=>{if(req.method()!=='GET')mutations.push(req.url());});
    await page.goto(origin);
    await page.locator('#replays').evaluate(el => { el.open = true; });
    await page.locator('[data-public-replay="integrity"]').waitFor();
    assert.match(await page.locator('#mode').textContent(),/unavailable/i);
    await page.locator('#purpose').fill('Preserve my unsent draft');
    for (const id of ['integrity','migration','unsupported']) {
      const expected=JSON.parse(await fs.readFile(path.join(product,'evidence',id+'-run.json'),'utf8'));
      await page.locator('[data-public-replay="'+id+'"]').click();
      await page.waitForFunction(title=>document.getElementById('record-title').textContent===title,expected.mission.purpose);
      assert.match(await page.locator('#run-status').textContent(),/RECORDED REPLAY/);
      assert.match(await page.locator('#run-status').textContent(),new RegExp(expected.status));
      assert.equal(await page.locator('#actions').isHidden(),true);
      assert.equal(await page.locator('#handoff').isHidden(),true);
      assert.equal(await page.locator('#recorded-bundle').isVisible(),id!=='unsupported');
      await assertLayout(page,390);
      if (id!=='unsupported'){
        const zip=path.join(work,'recorded-'+id+'.zip');
        await receive(page,'#recorded-bundle',zip);
        assert.deepEqual(await fs.readFile(zip),await fs.readFile(path.join(product,'evidence',id+'-artifact.zip')));
      }
    }
    await page.locator('#close-replay').click();
    assert.equal(await page.locator('#purpose').inputValue(),'Preserve my unsent draft');
    assert.deepEqual(mutations,[]);
  } finally {
    if(context)await context.close();lines.close();server.kill();
    if(server.exitCode===null && server.signalCode===null) await once(server,'exit');
  }
}
async function main() {
  const work=await fs.mkdtemp(path.join(os.tmpdir(),'ignition-workbench-'));
  const proc=spawn('python3',['-B','-m','ignition','--state',work,'--assisted','UI qualification','authored test data','serve','--port','0'],
    {cwd:product,stdio:['ignore','pipe','inherit']});
  const lines=createInterface({input:proc.stdout});
  let browser;
  try {
    const ready=await Promise.race([once(lines,'line').then(x=>x[0]),
      once(proc,'exit').then(([code])=>{throw Error(`Server exited ${code}`);})]);
    const origin=ready.match(/http:\/\/127\.0\.0\.1:\d+/)[0];
    browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',
      chromiumSandbox:process.env.CHROMIUM_SANDBOX==='1'});
    await publicReplayCheck(browser,work);
    const page=await browser.newPage({reducedMotion:'reduce'});
    const errors=[], external=[];
    page.on('pageerror',e=>errors.push(String(e)));
    await page.route(/^https?:/,route=>{
      if(new URL(route.request().url()).origin===origin)return route.continue();
      external.push(route.request().url());return route.abort();
    });
    await page.goto(origin);
    await page.locator('#presets').waitFor();
    await assertLayout(page,360);await assertLayout(page,390);await assertLayout(page,1200);
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement.className),'skip');
    const deskPage = await browser.newPage({reducedMotion:'reduce'});
    deskPage.on('pageerror', e => errors.push(String(e)));
    await deskPage.route(/^https?:/, route => {
      if (new URL(route.request().url()).origin === origin) return route.continue();
      external.push(route.request().url()); return route.abort();
    });
    await deskPage.goto(origin);
    await deskPage.locator('#presets').waitFor();
    await deskPage.locator('#example').selectOption('evidence_action');
    await deskPage.locator('#start').click();
    await deskPage.locator('#evidence-result').waitFor();
    assert.equal(await deskPage.locator('#evidence-verdict').textContent(), 'Withdraw the shadow review');
    assert.match(await deskPage.locator('#evidence-verdict-fr').textContent(), /Retirer/);
    await deskPage.locator('#try').click();
    await deskPage.waitForFunction(()=>document.getElementById('output').textContent.includes('withdraw_shadow_review'));
    const evidenceZip = path.join(work, 'scientific-decision.zip');
    await receive(deskPage, '#bundle', evidenceZip);
    execFileSync('python3', ['-c',
      'import pathlib,subprocess,sys,zipfile; d=pathlib.Path(sys.argv[2]); zipfile.ZipFile(sys.argv[1]).extractall(d); subprocess.run([sys.executable,"-IB","action_study/desk.py","verify","decision.json","--mission","mission.json"],cwd=d,check=True)',
      evidenceZip, path.join(work, 'received-decision')]);
    await qualifyMissionControls(deskPage, work);
    await deskPage.close();
    await page.locator('#example').selectOption('integrity');
    await page.locator('#strategy').selectOption('research');
    await page.locator('#settings').evaluate(el => { el.open = true; });
    await page.locator('#assisted_model').check();
    const sample=JSON.parse(await fs.readFile(path.join(product,'examples','integrity.json'),'utf8'));
    await page.locator('#start').click();
    const candidate={title:'Offline manifest inspection',beneficiary:sample.mission.beneficiary,
      outcome:sample.mission.purpose,change:'Evidence supports a bounded software check',obstruction:'Release authenticity remains out of scope',
      route:'Compare approved byte digests with received files',value:'Recover detectable distribution errors',
      alternative:'Standard SHA-256 checker',scale:'One batch per release',test:'Run frozen mismatches and missing files',
      kind:'manifest_audit',sources:['S1']};
    await send(page,'discover',{candidates:[candidate],favourite:'C1'});
    await send(page,'challenge',{challenger:null,objections:[],decision:'build',selected:'C1',reason:'Exercise the scoped manifest checks.',
      fit:sample.mission.requirements.map(requirement=>({requirement,check:'Run the frozen verification cases.',status:'supported'}))});
    await send(page,'construct',{kind:'manifest_audit',program:{manifest:sample.mission.construction_spec.definition.manifest}});
    await page.locator('#actions').waitFor();
    await assertLayout(page,360);
    await page.locator('#try').click();
    await page.waitForFunction(()=>document.getElementById('output').textContent.includes('"matched"'));
    const seen=JSON.parse(await page.locator('#output').textContent());
    assert.equal(seen.output.ok,true);
    await page.locator('#trial').fill('{"files":{"../outside":"YQ=="}}');
    await page.locator('#try').click();
    await page.waitForFunction(()=>document.getElementById('output').textContent.includes('refused'));
    const bundle=path.join(work,'download.zip');
    await receive(page,'#bundle',bundle);
    execFileSync('python3',['-c','import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None and len(z.namelist())>3',bundle]);
    const saved=path.join(work,'run.json');
    await receive(page,'#snapshot',saved);
    const recording=JSON.parse(await fs.readFile(saved,'utf8'));
    assert.equal(recording.status,'verified');
    assert.equal(recording.handoff,null);
    await page.locator('#beneficiary').fill('A different named reviewer');
    assert.equal(await page.locator('#actions').isHidden(),true);
    await page.locator('#start').click();
    await page.waitForFunction(()=>document.getElementById('run-id').textContent.includes('Revision 2'));
    await page.reload();
    await page.waitForFunction(()=>document.getElementById('run-id').textContent.includes('Revision 2'));
    await page.locator('#history summary').click();
    await page.waitForFunction(()=>document.getElementById('versions').textContent.includes('"verified"'));
    await qualifyAdaptiveRepair(page, send, assertLayout, sample);
    await qualifyPairingDecision(page, assertLayout);
    await qualifyEndpointDecision(page, work, assertLayout, receive);
    await qualifyPublicBoundary(page);
    await qualifyMappingChoice(page, work, assertLayout, receive, send);
    await qualifyFollowup(page, work, assertLayout, receive);
    await qualifyChangeDesk(page, work, assertLayout, receive);
    await page.goto(pathToFileURL(path.join(product,'web','index.html')).href);
    await page.locator('.replay-picker summary').click();
    recording.mission.purpose='<img src=x onerror="document.body.dataset.injected=1">';
    await page.locator('#replay-file').setInputFiles({name:'historical.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(recording))});
    await page.locator('#close-replay').waitFor();
    assert.match(await page.locator('#run-status').textContent(),/RECORDED REPLAY/);
    assert.equal(await page.locator('#actions').isHidden(),true);
    assert.equal(await page.locator('#record-title img').count(),0);
    assert.equal(await page.locator('#record-title').textContent(),recording.mission.purpose);
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    console.log('Live HTTP UI, authored assisted handoffs, portable download, stale amendment controls, reload, offline replay and mobile layouts passed.');
  } finally {
    if(browser)await browser.close();
    lines.close();proc.kill();
    if(proc.exitCode===null && proc.signalCode===null)await once(proc,'exit');
    await fs.rm(work,{recursive:true,force:true});
  }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
