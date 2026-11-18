'use strict';
// Replay the enrolled reader interface using only packets explicitly marked technical.
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {readFile} = require('node:fs/promises');
const {chromium} = require('playwright-core');

async function main() {
  const folder = process.argv[2];
  if (!folder) throw Error('Pass the fresh output directory from qualify.py.');
  const browser = await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium', chromiumSandbox:false});
  let checked=0;
  try {
    for (const lang of ['en','fr']) for (const arm of ['A','B','C','D']) {
      const context=await browser.newContext({offline:true,reducedMotion:'reduce',viewport:{width:390,height:844}});
      const page=await context.newPage(), requests=[], errors=[];
      context.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
      page.on('pageerror',e=>errors.push(e.message));
      const dir=path.resolve(folder,lang+'-'+arm);
      await page.goto(pathToFileURL(path.join(dir,'START.html')).href);
      assert.equal(await page.locator('html').getAttribute('lang'),lang);
      const cfg=await page.locator('#task-data').evaluate(e=>JSON.parse(e.textContent));
      assert.equal(cfg.session,'technical-'+lang+'-'+arm);
      await page.locator('#start').focus(); await page.keyboard.press('Enter');
      assert.ok((await page.locator('#question').textContent()).length>30);
      await page.selectOption('#outcome','unresolved');
      await page.locator('#task button').click();
      const downloaded=page.waitForEvent('download'); await page.locator('#download').click();
      const response=JSON.parse(await readFile(await (await downloaded).path()));
      assert.deepEqual(response.rows.map(r=>[r.task,r.status]),[[cfg.tasks[0].id,'unresolved']]);
      assert.ok(response.rows[0].elapsed_ms>=0);
      await page.goto(pathToFileURL(path.join(dir,'publication/index.html')).href);
      assert.equal(await page.locator('li a').count(),arm==='A'?2:3);
      if (arm==='D') {
        await page.locator('li a').last().click();
        const term=lang==='en'?'funding':'acheteurs';
        await page.locator('#query').fill(term);
        assert.ok(await page.locator('#hits a').count()>0);
        await page.locator('#query').fill('zzznomatchingtextz');
        assert.equal(await page.locator('#hits a').count(),0);
        assert.match(await page.locator('#summary').textContent(),/^0/);
      }
      assert.deepEqual(requests,[]); assert.deepEqual(errors,[]);
      await context.close(); checked++;
    }
    console.log(JSON.stringify({packets:checked,kind:'automated interface qualification',human_participants:0,chromium:browser.version()}));
  } finally {await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
