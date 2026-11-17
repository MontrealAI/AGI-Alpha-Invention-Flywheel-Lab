'use strict';
// Qualify the same offline bytes a visitor opens. Optional images need only Chromium.
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {readFile,mkdir,mkdtemp,rm} = require('node:fs/promises');
const path = require('node:path');
const {tmpdir} = require('node:os');
const {pathToFileURL} = require('node:url');
const {execFileSync} = require('node:child_process');
const {chromium} = require('playwright-core');
async function main(){
  const source=process.argv[2], output=process.argv[3], product=path.resolve(__dirname,'..');
  if(!source) throw Error('Provide the built standalone HTML.');
  const receipt=JSON.parse(await readFile(path.join(product,'flagship/receipt.json')));
  const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',chromiumSandbox:process.env.CHROMIUM_SANDBOX==='1'});
  const temp=await mkdtemp(path.join(tmpdir(),'pairing-browser-'));
  try{
    if(output) await mkdir(output,{recursive:true});
    const context=await browser.newContext({offline:true,viewport:{width:1440,height:900},reducedMotion:'reduce',deviceScaleFactor:1});
    const page=await context.newPage(),errors=[],requests=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
    page.on('console',m=>{if(m.type()==='error') errors.push(m.text());});
    await page.goto(pathToFileURL(path.resolve(source)).href);
    const score=page.locator('#score');
    await page.waitForFunction(()=>document.querySelector('#score').textContent==='18 / 40');
    assert.equal(await page.locator('#loom path').count(),40);
    assert.equal(await page.locator('html').getAttribute('lang'),'en');
    if(output) await page.screenshot({path:path.join(output,'desktop.png'),animations:'disabled'});
    for(const key of Object.keys(receipt.arms)){
      if(key==='successor') await page.selectOption('#scope','successor');
      else {
        const [budget,width]=key.split('/');
        await page.selectOption('#scope','main');
        await page.selectOption('#budget',budget);
        await page.locator('[data-width="'+width+'"]').click();
      }
      const ref=receipt.arms[key];
      assert.equal(await score.textContent(),ref.audit.solved+' / '+ref.audit.tasks);
      assert.equal(await page.locator('#outcome').getAttribute('data-pass'),String(ref.qualifies));
      assert.equal(await page.locator('#case option').count(),ref.audit.tasks);
    }
    await page.locator('#witness summary').click();
    await page.selectOption('#case',{index:1});
    assert.equal(await page.locator('#witness-rows p').count(),2);
    await page.locator('#replay').click();
    assert.equal(await page.locator('#events li').count(),7);
    assert.match(await page.locator('#events').innerText(),/Confirmed/);
    assert.equal(await page.locator('#routes button').count(),5);
    await page.locator('#challenge').click();
    assert.equal(await page.locator('#routes button').count(),6);
    assert.match(await page.locator('#route-card h3').textContent(),/every pairing/);
    await page.locator('#language').click();
    assert.equal(await page.locator('html').getAttribute('lang'),'fr-CA');
    assert.match(await page.locator('#route-card h3').textContent(),/configurations/);
    assert.match(await page.locator('#outcome').textContent(),/non satisfaits/);
    await page.setViewportSize({width:390,height:844});
    await page.selectOption('#scope','main');await page.selectOption('#budget','2000000');await page.locator('[data-width="2"]').click();
    await page.evaluate(()=>window.scrollTo(0,0));
    if(output) await page.screenshot({path:path.join(output,'mobile-fr.png'),animations:'disabled'});
    for(const width of [320,390,768,1024,1440]){
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Overflow at '+width);
    }
    async function saved(id){
      const ready=page.waitForEvent('download');
      await page.locator(id).click();
      const download=await ready, file=path.join(temp,download.suggestedFilename());
      await download.saveAs(file);return file;
    }
    const customer=JSON.parse(await readFile(await saved('#receipt')));
    assert.equal(customer.matches_recorded,true);assert.deepEqual(customer.reproduced.audit,receipt.arms['2000000/2'].audit);
    const file=await saved('#download');
    const expected=path.join(temp,'reference.zip');
    execFileSync('python3',[path.join(product,'flagship/package.py'),expected]);
    assert.deepEqual(await readFile(file),await readFile(expected));
    const restored=path.join(temp,'recipient');
    execFileSync('python3',['-m','zipfile','-e',file,restored]);
    const run=JSON.parse(execFileSync('python3',['-B','pairing_lab.py','--summary'],{cwd:restored,encoding:'utf8'}));
    assert.deepEqual(run.audit,receipt.arms['2000000/2'].audit);
    const message='<img src=x onerror=alert(1)> privé';
    await page.fill('#purpose',message);
    assert.equal(JSON.parse(await readFile(await saved('#savebrief'))).purpose,message);
    assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);
    console.log(JSON.stringify({source_sha256:createHash('sha256').update(await readFile(source)).digest('hex'),offline:true,languages:2,registered_arms:7,practical_recipient:true,replay:run.audit,requests:requests.length,page_errors:errors.length}));
  } finally {await browser.close();await rm(temp,{recursive:true,force:true});}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
