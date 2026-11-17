'use strict';
// Exercise the actual recipient, including offline downloads and both languages.
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {execFileSync} = require('node:child_process');
const {readFile, mkdir, mkdtemp, rm} = require('node:fs/promises');
const {tmpdir} = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright-core');
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

async function main() {
  const [source, screenshotDir, service] = process.argv.slice(2);
  if (!source) throw Error('Pass the exhibit HTML, an optional image directory and an optional local workbench URL.');
  const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
    chromiumSandbox: process.env.CHROMIUM_SANDBOX === '1'});
  const temp = await mkdtemp(path.join(tmpdir(), 'frontier-exhibition-'));
  try {
    const context = await browser.newContext({offline:true, viewport:{width:1440,height:960}, reducedMotion:'reduce'});
    const page = await context.newPage();
    const errors = [], requests = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => {if (m.type() === 'error') errors.push(m.text());});
    page.on('request', r => {if (/^https?:/.test(r.url())) requests.push(r.url());});
    await page.goto(pathToFileURL(path.resolve(source)).href);
    const record = await page.locator('#public-record').evaluate(e => JSON.parse(e.textContent));
    const product = path.resolve(__dirname, '..');
    const archivedStudy = JSON.parse(await readFile(path.join(product, 'reading_room_study/RESULTS.json')));
    assert.deepEqual(record.study, archivedStudy);
    const counts = record.receipt.summary;
    assert.equal(await page.locator('#count-total').textContent(), String(counts.total));
    assert.equal(await page.locator('.folio-page').count(), record.receipt.page_count);
    assert.equal(await page.locator('#choices button').count(), 5);
    for (const language of ['en','fr']) {
      if (language === 'fr') await page.locator('#locale').click();
      assert.equal(await page.locator('html').getAttribute('lang'), language);
      const first = page.locator('#choices button').first();
      await first.focus();
      await page.keyboard.press('Space');
      assert.equal(await first.getAttribute('aria-pressed'), 'true');
      for (const button of await page.locator('#choices button').all()) {
        await button.click();
        assert.equal(await page.locator('#candidate-title').textContent(), await button.textContent());
        assert.ok(await page.locator('#sources a').count() >= 1);
      }
      for (const crop of ['1','2']) {
        await page.selectOption('#table-page',crop);
        await page.waitForFunction(()=>document.querySelector('#table-image').naturalWidth===1422);
        assert.ok((await page.locator('#table-caption').textContent()).includes(crop));
        assert.ok((await page.locator('#table-result').textContent()).includes('12'));
      }
      for (const status of ['all','matched','ambiguous','missing']) {
        await page.selectOption('#filter',status);
        const blocks = record.receipt.blocks.filter(b => status === 'all' || b.status === status);
        assert.equal(await page.locator('#passage option').count(), blocks.length);
        for (const b of blocks) {
          await page.selectOption('#passage',String(b.index));
          assert.equal(await page.locator('#quotation').textContent(),b.text);
          assert.equal(await page.locator('#source-page').isVisible(),b.status === 'matched');
          if (b.page) assert.ok((await page.locator('#source-page').getAttribute('href')).endsWith('#page='+b.page));
        }
      }
      await first.click();
      await page.selectOption('#filter','all');
      const snapshot = await page.locator('body').ariaSnapshot();
      assert.ok(snapshot.includes('heading') && snapshot.includes('combobox') && snapshot.includes('navigation'));
      for (const width of [320,390,768,1024,1440]) {
        await page.setViewportSize({width,height:900});
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'overflow at '+width+' '+language);
      }
      if (screenshotDir) {
        await mkdir(screenshotDir,{recursive:true});
        await page.setViewportSize({width:language==='en'?1440:390,height:language==='en'?920:844});
        await page.evaluate(()=>scrollTo(0,0));
        await page.screenshot({path:path.join(screenshotDir,language+'.png'),animations:'disabled'});
      }
    }
    const download = page.waitForEvent('download');
    await page.locator('#download').click();
    const file = await download;
    const zip = path.join(temp,file.suggestedFilename());
    await file.saveAs(zip);
    assert.equal(digest(await readFile(zip)),record.archive.sha256);
    execFileSync('python3',['-m','zipfile','-e',zip,temp]);
    const receipt = JSON.parse(await readFile(path.join(temp,'receipt.json')));
    assert.deepEqual(receipt,record.receipt);
    for (const [name, expected] of Object.entries(archivedStudy.publication_receipt.recipient_sha256)) {
      assert.equal(digest(await readFile(path.join(temp,name))),expected,name);
    }
    assert.equal(digest(await readFile(path.join(temp,'edition.py'))),archivedStudy.code_sha256['edition.py']);
    assert.equal(digest(await readFile(path.join(temp,'source.pdf'))),receipt.pdf_sha256);
    const rich = record.qualified_recipient.results['cycle-001'];
    assert.equal(digest(await readFile(path.join(temp,'annotated-author.html'))),rich.html_sha256);
    const acceptedTable = JSON.parse(await readFile(path.join(temp,'table/nemotron/receipt.json')));
    assert.equal(digest(await readFile(path.join(temp,'table/cycle-001.csv'))),acceptedTable.csv_sha256);
    execFileSync('python3',['-B','edition.py','--pdf','source.pdf','--source','manuscript.original.txt',
      '--source-format','html','--output','replay'],{cwd:temp});
    const replay = JSON.parse(await readFile(path.join(temp,'replay/receipt.json')));
    const replayExtractor = replay.extractor;
    // The production environment can have a different Poppler version. Compare every output row.
    assert.match(replayExtractor,/pdftotext version/);
    assert.deepEqual({...replay,extractor:receipt.extractor},receipt);
    assert.deepEqual(errors,[]); assert.deepEqual(requests,[]);
    if (service) {
      const live = await browser.newContext();
      const operator = await live.newPage();
      await operator.goto(service);
      const opened = live.waitForEvent('page');
      const response = live.waitForEvent('response',r=>new URL(r.url()).pathname==='/exhibition');
      await operator.locator('a[href="/exhibition"]').click();
      const exhibit = await opened;
      await exhibit.waitForLoadState('load');
      assert.match((await response).headers()['content-security-policy'],/connect-src 'none'/);
      assert.deepEqual(await exhibit.evaluate(()=>[self.origin,!!opener,document.referrer]),['null',false,'']);
      assert.equal(await exhibit.locator('#count-total').textContent(),String(counts.total));
      assert.equal(await exhibit.locator('#pair-link').getAttribute('href'),'/showcase');
      const saved = exhibit.waitForEvent('download');
      await exhibit.locator('#pdf-download').click();
      const savePath = path.join(temp,'served-source.pdf');
      await (await saved).saveAs(savePath);
      assert.equal(digest(await readFile(savePath)),receipt.pdf_sha256);
      await live.close();
    }
    console.log(JSON.stringify({chromium:browser.version(),languages:2,widths:[320,390,768,1024,1440],
      examined_blocks:counts.total,offline_requests:requests.length,download_reproduced:true,registered_extractor:receipt.extractor,replay_extractor:replayExtractor,
      workbench_boundary:!!service}));
  } finally { await browser.close(); await rm(temp,{recursive:true,force:true}); }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
