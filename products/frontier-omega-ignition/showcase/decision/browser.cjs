'use strict';
// Qualify the self-contained bytes, detached workbench route and received Python programs.
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {readFile, mkdir, mkdtemp, rm} = require('node:fs/promises');
const path = require('node:path');
const {tmpdir} = require('node:os');
const {pathToFileURL} = require('node:url');
const {execFileSync} = require('node:child_process');
const {chromium} = require('playwright-core');

const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const json = async file => JSON.parse(await readFile(file));
const python = (args, cwd) => JSON.parse(execFileSync('python3', ['-B', ...args], {cwd, encoding:'utf8'}));
async function save(page, selector, destination) {
  const waiting = page.waitForEvent('download');
  await page.locator(selector).click();
  await (await waiting).saveAs(destination);
}
async function main() {
  const [source, output, service] = process.argv.slice(2);
  if (!source) throw Error('Provide the generated standalone exhibit.');
  const product = path.resolve(__dirname, '../..');
  const expected = await json(path.join(product, 'endpoint_lab/evidence/public.json'));
  const fields = await json(path.join(product, 'opportunity_field/field.json'));
  const widths = [320,390,768,1024,1440];
  const temp = await mkdtemp(path.join(tmpdir(), 'endpoint-exhibit-'));
  const browser = await chromium.launch({
    executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',
    chromiumSandbox:process.env.CHROMIUM_SANDBOX === '1'
  });
  try {
    if (output) await mkdir(output, {recursive:true});
    const ctx = await browser.newContext({offline:true, viewport:{width:1440,height:900}, reducedMotion:'reduce'});
    const page = await ctx.newPage(), errors=[], network=[];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('request', r => { if (/^https?:/.test(r.url())) network.push(r.url()); });
    await page.goto(pathToFileURL(path.resolve(source)).href);
    await page.waitForFunction(() => document.querySelector('.decision-number')?.textContent === '140');
    await page.keyboard.press('Tab');
    assert.equal(await page.locator(':focus').getAttribute('class'),'skip');
    if (output) {
      await page.locator('h1').click();
      await page.screenshot({path:path.join(output,'endpoint-desktop-en.png')});
    }
    assert.equal(await page.locator('html').getAttribute('lang'),'en');
    assert.equal(await page.locator('#reported-load').innerText(),'64');
    assert.equal(await page.locator('#inverse-load').innerText(),'128');
    await page.locator('#rate').focus();
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('#rate-value').innerText(),'111 tokens/s');
    await page.keyboard.press('End');
    assert.deepEqual(await page.locator('#reported-load,#inverse-load').allTextContents(),['Abstain','Abstain']);
    await page.locator('#rate').evaluate(input=>{input.value='64';input.dispatchEvent(new Event('input'));});
    assert.deepEqual(await page.locator('#reported-load,#inverse-load').allTextContents(),['512','256']);
    if (output) await page.locator('#semantics').screenshot({path:path.join(output,'endpoint-rate-en.png')});

    for (const s of expected.scenarios) {
      await page.selectOption('#scenario',s.id);
      const result = s.result;
      const view = await page.locator('.decision-number').innerText();
      assert.equal(view,result.selected.length ? String(result.selected[0].concurrency) : 'Evidence insufficient');
      assert.ok((await page.locator('#decision-note').innerText()).length > 25);
    }
    assert.equal(await page.locator('#choices button').count(),fields.opportunities.length);
    for (const [i,c] of fields.opportunities.entries()) {
      await page.locator('#choices button').nth(i).click();
      assert.equal(await page.locator('#candidate-title').innerText(),c.en.title);
      assert.equal(await page.locator('#candidate-source').getAttribute('href'),c.source.url);
      assert.equal(await page.locator('#candidate-detail dd').count(),3);
    }
    assert.equal(await page.locator('#candidate-state').textContent(),'Overlooked alternative');
    for (const src of expected.sources) {
      await page.selectOption('#system',src.id);
      await page.fill('#latency','500'); await page.fill('#speed','100');
      await page.locator('#filter-form button').click();
      assert.equal(await page.locator('#rows tr').count(),src.points.length);
      assert.equal(await page.locator('#report').getAttribute('href'),src.url);
      const match = p => p.ttft_p90_ms != null && p.tps_per_user != null && Number(p.ttft_p90_ms)<=500 && Number(p.tps_per_user)>=100;
      assert.equal(await page.locator('#rows tr[data-eligible="true"]').count(),src.points.filter(match).length);
    }
    await page.fill('#latency','0.01'); await page.locator('#filter-form button').click();
    assert.equal(await page.locator('#rows tr[data-eligible="true"]').count(),0);
    await page.selectOption('#scenario','interactive_gpt');
    await page.locator('#locale').click();
    assert.equal(await page.locator('html').getAttribute('lang'),'fr');
    assert.equal(await page.locator('#candidate-title').innerText(),fields.opportunities.at(-1).fr.title);
    assert.match(await page.locator('#reader-note').innerText(),/0/);
    assert.match(await page.locator('#numeric-note').innerText(),/25 cellules/);
    for (const width of widths) {
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),true,'Overflow at '+width);
      assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');
    }
    if (output) {
      await page.setViewportSize({width:390,height:844}); await page.evaluate(()=>scrollTo(0,0));
      await page.screenshot({path:path.join(output,'endpoint-mobile-fr.png')});
    }
    const primary=expected.scenarios.find(s=>s.id==='interactive_gpt');
    const receipt=path.join(temp,'receipt.json');
    await save(page,'#receipt',receipt);
    const exported=await json(receipt);
    assert.deepEqual(exported.requirement,primary.requirement);
    assert.deepEqual(exported.result,primary.result);
    const ambition='<image locally> essai de Montréal';
    await page.fill('#purpose',ambition);
    const briefPath=path.join(temp,'brief.json');
    await save(page,'#brief',briefPath);
    const brief=await json(briefPath);
    assert.equal(brief.ambition,ambition);
    assert.equal(brief.deployment_authorized,false);
    assert.equal(brief.opportunity.id,fields.opportunities.at(-1).id);
    assert.deepEqual(brief.endpoint_case.observed_points,primary.result.selected);
    const zip=path.join(temp,'kit.zip'), restored=path.join(temp,'restored');
    await save(page,'#download',zip);
    assert.equal(sha(await readFile(zip)),await page.locator('#kit-hash').textContent());
    execFileSync('python3',['-m','zipfile','-e',zip,restored]);
    const cs='cases/interactive_gpt.json';
    execFileSync('python3',['-B','decide.py','--contract',cs,'--output','new.json'],{cwd:restored});
    assert.equal(python(['reference.py','--contract',cs,'--receipt','new.json'],restored).checked,true);
    assert.deepEqual(python(['reference.py','--contract',cs],restored),(await json(path.join(restored,'observations/independent-sql.json'))).interactive_gpt);
    for (const [selector,filename] of [['#reading','FRONTIER_IGNITION.html'],['#pairing','PAIRING_LAB.html']]) {
      assert.equal(await page.locator(selector).getAttribute('href'),filename);
      assert.deepEqual(await readFile(path.join(restored,filename)),await readFile(path.join(product,'../../docs/frontier-omega-ignition/continuation',filename)));
      const companion=await ctx.newPage();
      await companion.goto(pathToFileURL(path.join(restored,filename)).href);
      assert.ok((await companion.locator('h1').innerText()).length>2);
      await companion.close();
    }
    assert.deepEqual(network,[]); assert.deepEqual(errors,[]);
    if (service) {
      const live=await browser.newContext(), operator=await live.newPage();
      await operator.goto(service);
      const opened=live.waitForEvent('page');
      const response=live.waitForEvent('response',r=>new URL(r.url()).pathname==='/frontier');
      await operator.locator('a[href="/frontier"]').click();
      const exhibit=await opened; await exhibit.waitForLoadState('load');
      const csp=(await response).headers()['content-security-policy'];
      assert.match(csp,/connect-src 'none'/); assert.match(csp,/sandbox allow-scripts/); assert.doesNotMatch(csp,/allow-same-origin/);
      assert.deepEqual(await exhibit.evaluate(()=>[self.origin,!!opener,document.referrer]),['null',false,'']);
      const html=path.join(temp,'served.html');
      await save(exhibit,'#standalone',html);
      assert.deepEqual(await readFile(html),await readFile(source));
      await save(exhibit,'#download',path.join(temp,'served.zip'));
      assert.deepEqual(await readFile(path.join(temp,'served.zip')),await readFile(zip));
      for (const [selector,route] of [['#reading','/exhibition'],['#pairing','/showcase']]) {
        assert.equal(await exhibit.locator(selector).getAttribute('href'),route);
        await Promise.all([exhibit.waitForURL(u=>u.pathname===route),exhibit.locator(selector).click()]);
        assert.ok((await exhibit.locator('h1').innerText()).length>2);
        assert.equal(await exhibit.evaluate(()=>self.origin),'null');
        await exhibit.goto(new URL('/frontier',service).href);
      }
      const blocked=await live.request.get(new URL('/api/status',service).href,{headers:{'Sec-Fetch-Site':'cross-site'}});
      assert.equal(blocked.status(),403);
      await live.close();
    }
    console.log(JSON.stringify({sha256:sha(await readFile(source)),chromium:browser.version(),languages:['en','fr'],
      widths,scenarios:expected.scenarios.length,source_points:expected.sources.reduce((n,s)=>n+s.points.length,0),
      independent_recipient:true,retained_companions:2,network_requests:network.length,page_errors:errors.length,
      detached_workbench:!!service,rate_definition_cases:[64,110,400]}));
  } finally {await browser.close();await rm(temp,{recursive:true,force:true});}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
