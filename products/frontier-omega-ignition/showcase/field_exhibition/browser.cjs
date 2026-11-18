'use strict';
// Qualify visitor interactions against registered source records, then run the actual downloaded programs.
const assert = require('node:assert/strict');
const {execFileSync, spawnSync} = require('node:child_process');
const {createHash} = require('node:crypto');
const {mkdtemp, mkdir, readFile, writeFile, rm} = require('node:fs/promises');
const {tmpdir} = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');

const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const readJSON = async file => JSON.parse(await readFile(file,'utf8'));
const py = (args, cwd) => execFileSync('python3',['-B',...args],{cwd,encoding:'utf8'});
let checkedDownloads=0;
async function download(page, selector, destination) {
  const waiting=page.waitForEvent('download');
  await page.locator(selector).click();
  await (await waiting).saveAs(destination);
  checkedDownloads++;
}

async function qualifySerializedExports(filename) {
  const html = await readFile(filename, 'utf8');
  const match = html.match(/<script type="application\/json" id="public-evidence">([\s\S]+?)<\/script>/);
  assert(match, 'Standalone page has no source payload');
  const payload = JSON.parse(match[1]);
  const temp = await mkdtemp(path.join(tmpdir(), 'observing-export-'));
  try {
    const archive = Buffer.from(payload.archive.bytes, 'base64');
    assert.equal(sha(archive), payload.archive.sha256);
    await writeFile(path.join(temp, 'received.zip'), archive);
    py(['-m', 'zipfile', '-e', 'received.zip', '.'], temp);
    const provenance='invention/sources/alerts-source.json';
    assert.deepEqual(await readFile(path.join(temp,provenance)),await readFile(path.resolve(__dirname,'../..',provenance)));
    for (const item of payload.sky.cases) {
      // The visitor receives exact bytes. Independent tools may equate 32.0 with 32 when
      // they read and reserialize the mission. Both recipients must still verify.
      const exact = JSON.parse(item.receipt_text);
      const normalized = JSON.stringify(exact);
      for (const receipt of [item.receipt_text, normalized]) {
        await writeFile(path.join(temp, 'case.json'), receipt);
        const checked = JSON.parse(py(['replay.py', '--case', 'case.json'], temp));
        assert.deepEqual(checked.selected_case, {id:item.id, accepted:true, covered_targets:item.objective});
      }
      await writeFile(path.join(temp, 'mission.json'), JSON.stringify(exact.mission));
      py(['invention/plan.py', '--mission', 'mission.json', '--out', item.id], temp);
      assert.equal(await readFile(path.join(temp, item.id, 'worklist.csv'), 'utf8'), item.csv);
    }
    assert.equal(await readFile(path.join(temp, 'field_trials/recorded/summary.json'), 'utf8'), payload.pilotReport);
    assert.equal(await readFile(path.join(temp, 'invention/next_week/RESULT.json'), 'utf8'), payload.secondWeekReport);
    const repeat=JSON.parse(payload.secondWeekReport);
    const expectedNew=repeat.pairs_120.filter(row=>repeat.overlap_with_first.includes(row.target_id)
      && payload.sky.photometry.missing_pair.includes(row.target_id)).map(row=>row.target_id).sort();
    const repeated=JSON.parse(py(['replay.py'],temp)).second_week;
    assert.deepEqual(repeated,{targets:repeat.targets,pairs_120:repeat.pairs_120.length,
      pairs_10:repeat.pairs_10.length,previously_withheld_now_measured:expectedNew});
    console.log(JSON.stringify({serialized_cases:payload.sky.cases.length, exact_and_normalized:true,
      regenerated_csvs:payload.sky.cases.length, recorded_model_arms:JSON.parse(payload.pilotReport).arms.length, second_week:repeated}));
  } finally { await rm(temp, {recursive:true,force:true}); }
}

async function main() {
  if (process.argv[2] === '--recipient-only') return qualifySerializedExports(process.argv[3]);
  const {chromium} = require('playwright-core');
  const [input,screens]=process.argv.slice(2);
  if (!input) throw Error('Provide the standalone exhibition path.');
  const product=path.resolve(__dirname,'../..');
  const scientific=await readJSON(path.join(product,'invention/public.json'));
  const field=await readJSON(path.join(product,'field_lab/PUBLIC.json'));
  const repeatFile=path.join(product,'invention/next_week/RESULT.json');
  const repeated=await readJSON(repeatFile);
  const pilotFile=path.join(product,'field_trials/recorded/summary.json');
  const pilot=await readJSON(pilotFile);
  const catalog=await readJSON(path.join(product,'discovery_field/decision_study/possibilities.json'));
  const widths=[320,390,768,1024,1440];
  const temp=await mkdtemp(path.join(tmpdir(),'observing-recipient-'));
  const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',
    chromiumSandbox:process.env.CHROMIUM_SANDBOX==='1'});
  try {
    if(screens) await mkdir(screens,{recursive:true});
    const ctx=await browser.newContext({viewport:{width:1440,height:940},offline:true,reducedMotion:'reduce'});
    const page=await ctx.newPage(), errors=[], requests=[];
    page.on('pageerror', e=>errors.push(e.message));
    page.on('console', m=>{if(m.type()==='error') errors.push(m.text());});
    page.on('request', r=>{if(/^https?:/.test(r.url())) requests.push(r.url());});
    const url=pathToFileURL(path.resolve(input));
    await page.goto(url.href);
    await page.waitForFunction(()=>document.getElementById('plan-number').textContent.length>0);
    await page.keyboard.press('Tab');
    assert.equal(await page.locator(':focus').getAttribute('class'),'skip');
    await page.locator('h1').click();
    await page.locator('#supporting > summary').click();
    const series=await page.locator('#public-evidence').evaluate(n=>JSON.parse(n.textContent).changeSeries);
    assert.equal(series.length,4);
    for(const locale of ['en','fr']) {
      if(locale==='fr') await page.locator('#lang').click();
      assert.equal(await page.locator('html').getAttribute('lang'),locale);
      assert.equal(await page.locator('h1').count(),1);
      const cards=page.locator('#choices button');
      assert.equal(await cards.count(),catalog.opportunities.length);
      for(const [idx,item] of catalog.opportunities.entries()) {
        await cards.nth(idx).click();
        assert.equal(await cards.nth(idx).getAttribute('aria-pressed'),'true');
        assert.equal(await page.locator('#opp-title').innerText(),item[locale].title);
        assert.equal(await page.locator('#opp-source').getAttribute('href'),item.url);
      }
      await page.selectOption('#signal-window','early_warm');
      if(await page.locator('#compare-archive').getAttribute('aria-pressed')==='true') await page.locator('#compare-archive').click();
      for(const window of series) {
        await page.selectOption('#signal-window',window.id);
        for(const sample of window.days) {
          await page.selectOption('#signal-date',sample.as_of_utc);
          const now=page.locator('#signal-coverage tr');
          assert.equal(await now.count(),sample.coverage.length);
          assert.deepEqual(await now.locator('td:first-child').allTextContents(),sample.coverage.map(r=>r.target_id));
          assert.deepEqual(await now.locator('td:nth-child(3)').allTextContents(),sample.coverage.map(r=>String(r.eligible_detections)));
          for(const item of [sample.coverage[0], ...sample.alerts]) {
            await page.selectOption('#signal-choice',item.target_id+'/'+item.band);
            const match=sample.alerts.find(a=>a.target_id===item.target_id&&a.band===item.band);
            const coverage=sample.coverage.find(a=>a.target_id===item.target_id&&a.band===item.band);
            const comparison=match||coverage.strongest_comparison;
            const ids=comparison?[comparison.baseline,comparison.trigger,...(match?.followup?[match.followup]:[])].map(p=>'ID '+p.candid):[];
            assert.deepEqual(await page.locator('#signal-points small').allTextContents(),ids);
            assert.equal(await page.locator('#trace-drawing .trace-observation').count(),ids.length);
            assert.equal(await page.locator('#trace-target').textContent(),item.target_id);
          }
        }
        await page.locator('#signal-step').click();
        assert.equal(await page.locator('#signal-date').inputValue(),window.days[0].as_of_utc);
      }
      const warm=series.find(s=>s.id==='early_warm');
      await page.selectOption('#signal-window',warm.id);
      const alert=warm.days.at(-1).alerts[0], focus=alert.target_id+'/'+alert.band;
      await page.selectOption('#signal-choice',focus);
      await page.selectOption('#signal-date',alert.issued_utc);
      await page.locator('#compare-history').click();
      assert.equal(await page.locator('#signal-window').inputValue(),'early_cold');
      assert.equal(await page.locator('#signal-choice').inputValue(),focus);
      assert.equal(await page.locator('#signal-date').inputValue(),alert.issued_utc);
      assert.equal(await page.locator('#trace-drawing .trace-observation').count(),0);
      await page.locator('#compare-history').click();
      assert.equal(await page.locator('#trace-drawing .trace-observation').count(),2);
      await page.locator('#compare-archive').click();
      await download(page,'#signal-download',path.join(temp,'before-witness-'+locale+'.json'));
      assert.deepEqual((await readJSON(path.join(temp,'before-witness-'+locale+'.json'))).second_archive.witnesses,[]);
      const visible=warm.days.find(d=>warm.second_archive[d.as_of_utc].witnesses.some(x=>x.target_id+'/'+x.band===focus));
      await page.selectOption('#signal-date',visible.as_of_utc);
      assert.equal(await page.locator('#trace-drawing .trace-observation').count(),3);
      assert.equal(await page.locator('#trace-source').textContent(),'FINK + ALeRCE / ZTF');
      assert((await page.locator('#al-source').getAttribute('href')).startsWith('https://api.alerce.online/'));
      await download(page,'#signal-download',path.join(temp,'later-witness-'+locale+'.json'));
      await download(page,'#signal-csv',path.join(temp,'later-witness-'+locale+'.csv'));
      assert.deepEqual(await readJSON(path.join(temp,'later-witness-'+locale+'.json')),{...visible, second_archive:warm.second_archive[visible.as_of_utc]});
      await page.locator('#compare-archive').click();
      assert.equal(await page.locator('#trace-drawing .trace-observation').count(),2);
      await page.selectOption('#signal-window',series.find(s=>s.id==='nov10').id);
      await page.selectOption('#signal-date','2026-11-13T00:00:00Z');
      const expected=series.find(s=>s.id==='nov10').days.find(q=>q.as_of_utc==='2026-11-13T00:00:00Z');
      const file=path.join(temp,'observations-'+locale+'.json');
      await download(page,'#signal-download',file);
      assert.deepEqual(await readJSON(file),expected);
      await download(page,'#signal-csv',path.join(temp,'observations-'+locale+'.csv'));
      for(const sample of scientific.cases) {
        await page.selectOption('#budget',String(sample.budget));
        await page.selectOption('#coverage',String(sample.visits));
        assert.match(await page.locator('#plan-number').textContent(),new RegExp('^'+sample.objective+' '));
        assert.equal(await page.locator('#worklist tr').count(),sample.slots.length);
        assert.equal(await page.locator('#drawing [data-scheduled="true"]').count(),sample.objective);
        assert.deepEqual(await page.locator('#worklist tr td:nth-child(2)').allTextContents(),sample.slots.map(s=>s.target_id));
        assert.deepEqual(await page.locator('#worklist time').evaluateAll(rows=>rows.map(r=>r.dateTime)),sample.slots.map(s=>s.utc));
      }
      const laterFinding=await page.locator('#second-outcome').innerText();
      assert(laterFinding.includes(`${repeated.pairs_120.length}/${repeated.targets}`));
      assert(laterFinding.includes(`${repeated.pairs_10.length}/${repeated.targets}`));
      for(const row of scientific.exploratory_color_counts) {
        await page.selectOption('#gap',String(row.max_gap_minutes));
        assert.equal(await page.locator('#photometry tr').count(),row.accepted_pairs);
        assert.equal(await page.locator('#second-outcome').innerText(),laterFinding);
        const kept=scientific.photometry.pairs.filter(p=>1440*Math.abs(p.g_jd-p.r_jd)<=row.max_gap_minutes);
        assert.deepEqual(await page.locator('#photometry tr td:first-child').allTextContents(),kept.map(p=>p.target_id));
        const missing=scientific.targets.filter(t=>!kept.some(p=>p.target_id===t.id));
        for (const m of missing) assert((await page.locator('#withheld').textContent()).includes(m.id));
      }
      await page.locator('#field-proof summary').click();
      const intake=await readJSON(path.join(product,'field_lab/intake_recorded/result.json'));
      for(const [name,route] of Object.entries(intake.fresh.routes)) {
        assert((await page.locator(`#intake-results [data-route="${name}"]`).innerText()).includes(route.correct+'/'+route.attempted));
      }
      for(const load of [...new Set(field.arms.map(a=>a.concurrency))]) {
        await page.selectOption('#service-load',String(load));
        const matching=field.arms.filter(a=>a.concurrency===load);
        assert.equal(await page.locator('#field-results article').count(),matching.length);
        const text=await page.locator('#field-results article').allTextContents();
        for (const [i,arm] of matching.entries()) assert(text[i].includes(`${arm.quality_accepted}/${arm.requests}`));
        const modelArms=pilot.arms.filter(a=>a.concurrency===load);
        assert.equal(await page.locator('#model-results article').count(),modelArms.length);
        for(const arm of modelArms){
          const card=page.locator(`#model-results [data-route="${arm.route}"][data-concurrency="${load}"]`);
          const content=await card.innerText();
          assert(content.includes(`${arm.quality_accepted}/${arm.requests}`));
          const latency=new Intl.NumberFormat(locale,{maximumFractionDigits:3}).format(arm.p90_turn_ms/1000);
          assert(content.includes(`${latency} s (${arm.transport_complete}/${arm.requests})`));
        }
      }
      if(locale==='en') {
        const secondary=path.join(temp,'later.json');
        await download(page,'#second-source',secondary);
        assert.deepEqual(await readFile(secondary),await readFile(repeatFile));
        const pilotDownload=path.join(temp,'qwen-cpu-pilot.json');
        await download(page,'#pilot-summary',pilotDownload);
        assert.deepEqual(await readFile(pilotDownload),await readFile(pilotFile));
      }
      await page.locator('#field-proof summary').click();
      await page.selectOption('#budget','6'); await page.selectOption('#coverage','1');
      await cards.first().click();
      const heroWindow=series.find(s=>s.days.at(-1).alerts.length)||series.find(s=>s.id==='nov10');
      await page.selectOption('#signal-window',heroWindow.id);
      await page.selectOption('#signal-date',visible.as_of_utc);
      if(await page.locator('#compare-archive').getAttribute('aria-pressed')==='false') await page.locator('#compare-archive').click();
      for(const width of widths) {
        await page.setViewportSize({width,height:width<500?844:940});
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${locale} overflow at ${width}px`);
        assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollBehavior),'auto');
        if(screens && (width===390||width===1440)) {
          await page.evaluate(()=>scrollTo(0,0));
          await page.screenshot({path:path.join(screens,`observing-night-${locale}-${width}.png`)});
          await page.locator('#signals-title').scrollIntoViewIfNeeded();
          await page.screenshot({path:path.join(screens,`archive-decision-${locale}-${width}.png`)});
        }
      }
    }
    await page.selectOption('#coverage','2');await page.selectOption('#gap','10');
    const archive=path.join(temp,'received.zip');
    await download(page,'#download',archive);
    await page.locator('#instrument details summary').click();
    assert.equal(sha(await readFile(archive)),await page.locator('#kit-hash').innerText());
    await download(page,'#receipt',path.join(temp,'selected.json'));
    await download(page,'#csv',path.join(temp,'selected.csv'));
    await download(page,'#colors',path.join(temp,'colors.csv'));
    py(['-m','zipfile','-e',archive,temp],temp);
    const checked=JSON.parse(py(['replay.py','--case','selected.json','--snapshot','observations-en.json'],temp));
    assert.equal(checked.selected_change_queue.cohort,'nov10');
    assert.deepEqual(await readFile(path.join(temp,'observations-en.csv')),await readFile(path.join(temp,'observations-fr.csv')));
    const earlyVerified=JSON.parse(py(['replay.py','--snapshot','later-witness-en.json'],temp));
    assert.equal(earlyVerified.selected_change_queue.cohort,'early_warm');
    assert.deepEqual(await readFile(path.join(temp,'later-witness-en.csv')),await readFile(path.join(temp,'later-witness-fr.csv')));
    const forgedWitness=await readJSON(path.join(temp,'later-witness-en.json'));
    forgedWitness.second_archive.witnesses[0].witness.candid+='7';
    await writeFile(path.join(temp,'changed-witness.json'),JSON.stringify(forgedWitness));
    assert.notEqual(spawnSync('python3',['-B','replay.py','--snapshot','changed-witness.json'],{cwd:temp}).status,0);
    const changed=await readJSON(path.join(temp,'observations-en.json'));
    changed.coverage[0].status='persisted';
    await writeFile(path.join(temp,'altered-change.json'),JSON.stringify(changed));
    assert.notEqual(spawnSync('python3',['-B','replay.py','--snapshot','altered-change.json'],{cwd:temp}).status,0);
    assert.equal(checked.registered_worklists,scientific.cases.length);
    assert.equal(checked.selected_case.id,'b6-v2');assert.equal(checked.selected_case.accepted,true);
    const selected=await readJSON(path.join(temp,'selected.json'));
    await writeFile(path.join(temp,'mission.json'),JSON.stringify(selected.mission));
    py(['invention/plan.py','--mission','mission.json','--out','fresh-plan'],temp);
    assert.deepEqual(await readFile(path.join(temp,'selected.csv')),await readFile(path.join(temp,'fresh-plan/worklist.csv')));
    py(['invention/photometry.py','--max-gap-minutes','10','--out','fresh-colors.csv'],temp);
    const checkCSV=`import csv\nfrom decimal import Decimal\nwith open('colors.csv',newline='') as f, open('fresh-colors.csv',newline='') as g:\n a,b=csv.DictReader(f),csv.DictReader(g)\n assert a.fieldnames == b.fieldnames\n for u,v in zip(a,b,strict=True):\n  for k in u:\n   if k=='target_id' or k.endswith(('_candid','_utc')): assert u[k] == v[k], k\n   else: assert Decimal(u[k]) == Decimal(v[k]), k`;
    py(['-c',checkCSV],temp);
    for(const route of ['retained','ordinary','direct']) {
      py(['successor_field/triage.py','--route',route,'--output',`${route}.csv`],temp);
      py(['successor_field/audit.py',`${route}.csv`],temp);
      assert.deepEqual(await readFile(path.join(temp,`${route}.csv`)),await readFile(path.join(temp,'successor_field/archive-queue.csv')));
    }
    selected.worklist.slots[0].ra_deg+=1;await writeFile(path.join(temp,'forged.json'),JSON.stringify(selected));
    assert.notEqual(spawnSync('python3',['-B','replay.py','--case','forged.json'],{cwd:temp}).status,0);
    url.search='?lang=fr&budget=1&visits=2';url.hash='forge';await page.goto(url.href);
    assert.equal(await page.locator('html').getAttribute('lang'),'fr');
    assert.match(await page.locator('#plan-number').innerText(),/^0 /);
    assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
    console.log(JSON.stringify({browser:browser.version(),languages:['en','fr'],widths,registered_contracts:scientific.cases.length,
      photometry_intervals:scientific.exploratory_color_counts.length,change_windows:series.length, change_checkpoints:series.reduce((n,s)=>n+s.days.length,0), checked_downloads:checkedDownloads,external_requests:requests.length,
      page_errors:errors.length,recipient:checked}));
  } finally {await browser.close();await rm(temp,{recursive:true,force:true});}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
