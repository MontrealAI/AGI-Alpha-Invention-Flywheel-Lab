'use strict';

/* Run against the public Pages URLs. Wallet permissions are never requested
   from a real wallet. The provider fixture is isolated to its own browser page. */
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {mkdir, readFile} = require('node:fs/promises');
const {join} = require('node:path');
const { chromium } = require('playwright-core');

const base = process.env.FRONTIER_BROWSER_URL ??
  'https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/';
const checks = [];
const screenshots = process.env.FRONTIER_SCREENSHOTS;
const dimensions = width => ({width, height:width === 390 ? 844 : 900});

async function capture(page, language, width, subject) {
  if (!screenshots) return;
  await mkdir(screenshots, {recursive:true});
  await page.screenshot({path:join(screenshots, `${subject}-${language}-${width}.png`), animations:'disabled'});
}

async function publicAtlas(browser, language, width) {
  const path = language === 'fr' ? 'fr.html' : '';
  const page = await browser.newPage({ viewport:dimensions(width), reducedMotion:'reduce' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    const response = await page.goto(base + path, { waitUntil: 'networkidle' });
    assert.equal(response.status(), 200);
    assert.equal(await page.locator('html').getAttribute('lang'), language);
    const inventory = page.locator('#possibility-shifts [data-atlas-record]');
    const count = await inventory.count();
    assert.ok(count >= 8);
    assert.equal(await page.locator('#member').isVisible(), false);
    assert.equal(await page.locator('#my-frontier').isVisible(), false);
    assert.equal(await page.locator('#mf-edition').isVisible(), false);
    assert.equal(await page.locator('#foundry-cascade-results').isVisible(), false);
    assert.equal(await page.locator('#possibility-shifts #foundry-cascade-results').count(), 0);
    assert.equal(await page.locator('#foundry-factory-results').isVisible(), false);
    assert.equal(await page.locator('#possibility-shifts #foundry-factory-results').count(), 0);
    assert.equal(await page.locator('#opportunity-capture').isVisible(), false);
    assert.equal(await page.locator('#possibility-shifts #opportunity-capture').count(), 0);
    assert.equal(await page.locator('#club-form').isVisible(), false);
    assert.match(await page.locator('h1').innerText(), /Member First Ω/i);
    assert.equal(await page.locator('.entry-pillars li').count(), 4);
    const viewport = await page.evaluate(() => {
      const entrance = document.getElementById('access');
      const atlas = document.getElementById('possibility-shifts');
      const actions = [...entrance.querySelectorAll('.entry-portal button')].map(button => {
        const {top,bottom,height,width} = button.getBoundingClientRect();
        return {top:Math.round(top), bottom:Math.round(bottom), height:Math.round(height), width:Math.round(width),
          disabled:button.disabled, background:getComputedStyle(button).backgroundImage};
      });
      return {width:document.documentElement.clientWidth, height:innerHeight,
        scroll:document.documentElement.scrollWidth, hasWallet:Boolean(window.ethereum),
        gateBeforeAtlas:Boolean(entrance.compareDocumentPosition(atlas) & Node.DOCUMENT_POSITION_FOLLOWING),
        actions, atlasTop:Math.round(atlas.getBoundingClientRect().top),
        anchorIDs:[...atlas.querySelectorAll('[data-atlas-record]')].map(card => card.id)};
    });
    assert.ok(viewport.scroll <= viewport.width);
    assert.equal(viewport.hasWallet, false);
    assert.equal(viewport.gateBeforeAtlas, true);
    assert.equal(viewport.actions.length, 2);
    assert.ok(viewport.actions.every(action => !action.disabled && action.top >= 0 && action.bottom < viewport.height && action.height >= 44));
    assert.equal(viewport.actions[0].top, viewport.actions[1].top);
    assert.equal(viewport.actions[0].width, viewport.actions[1].width);
    assert.equal(viewport.actions[0].background, viewport.actions[1].background);
    assert.ok(viewport.atlasTop >= viewport.height);
    assert.equal(new Set(viewport.anchorIDs).size, count);
    const memberData = await (await page.request.get(base + 'member-value.json')).json();
    const preview = page.locator('#member-preview .preview-grid');
    assert.equal(await preview.getAttribute('data-preview-count'), String(count));
    assert.equal(await preview.getAttribute('data-preview-version'), memberData.member_first.edition.source_version);
    assert.match(await page.locator('#preview-capabilities').innerText(), /Endpoint Evidence Screen[\s\S]*NOAA Archive Point/);
    assert.equal(await page.locator('#preview-outcomes li').count(), 4);
    await capture(page, language, width, 'home');

    await page.keyboard.press('Tab');
    assert.match(await page.locator(':focus').getAttribute('href'), /#main$/);
    await page.keyboard.press('Enter');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'main');

    const clubPortal = page.locator('#enter-club');
    await clubPortal.click();
    assert.equal(await page.locator('#entry-help').evaluate(el => el.open), true);
    assert.match(await page.locator('#status').innerText(), /MetaMask Mobile/);
    assert.equal(await page.locator('#wallet-guidance a').getAttribute('href'), 'https://metamask.io/download');
    assert.equal(await page.locator('#club-form').isVisible(), false);
    assert.equal(await page.locator('#member').isVisible(), false);
    await page.locator('[data-connect="token"]').click();
    assert.match(await page.locator('#status').innerText(), /MetaMask Mobile/);
    await page.locator('a[href="#token-requirements"]').click();
    assert.equal(await page.locator('#token-requirements').isVisible(), true);
    await page.locator('.nav-atlas').click();
    await page.waitForURL(/#possibility-shifts$/);
    assert.equal(await page.locator('#atlas-query').isVisible(), true);
    await page.locator('#atlas-query').fill('SQLite');
    assert.equal(await page.locator('#shift-autonomous-endpoint').isVisible(), true);
    assert.equal(await page.locator('#shift-archive-point').isVisible(), false);
    await page.locator('#atlas-state').selectOption('abstain');
    assert.equal(await page.locator('[data-atlas-record]:visible').count(), 1);
    await page.locator('#atlas-query').fill('quiet-no-match-324');
    assert.equal(await page.locator('[data-atlas-record]:visible').count(), 0);
    await page.locator('#atlas-query').fill('');
    await page.locator('#atlas-state').selectOption('');
    assert.equal(await page.locator('[data-atlas-record]:visible').count(), count);
    assert.equal(await page.locator('#monitoring a[href*="2611.23751"]').count(), 0);
    const source = page.locator('#shift-archive-point a').first();
    assert.match(await source.getAttribute('href'), /6a635b77012fb45b4d96c404a33fa04327c19674/);
    const files = ['atlas-ledger.json', 'atlas-release.json', 'member-brief-001.js', 'member-value.json'];
    for (const file of files) assert.equal((await page.request.get(base + file)).status(), 200);
    assert.deepEqual(errors, []);
    checks.push({ kind: 'public', language, viewport: width, redirect: response.url(), records: count,
      actionsAboveFold:viewport.actions.map(({top,bottom,height})=>({top,bottom,height})), atlasTop:viewport.atlasTop,
      keyboard:true, filters:true, evidenceLinks:true, noWalletHelp:true, previewSourceBound:true });
  } finally {
    await page.close();
  }
}

function fakeWallet() {
  const account = '0x' + '12'.repeat(20);
  const word = value => BigInt(value).toString(16).padStart(64, '0');
  const addressWord = value => value.slice(2).padStart(64, '0');
  const abi = value => '0x' + word(value);
  const listeners = new Map();
  window.walletScenario = { account, balance: 1_000_000n, expiration: false, chain: '0x1', methods: [], signed: [] };
  const state = window.walletScenario;
  const block = () => ({ hash: '0x' + '11'.repeat(32), number: '0x16',
    timestamp: '0x' + Math.floor(Date.now() / 1000).toString(16) });
  window.ethereum = {
    isMetaMask: true,
    on(event, handler) { listeners.set(event, handler); },
    removeListener(event) { listeners.delete(event); },
    async request({method, params}) {
      state.methods.push(method);
      if (method === 'eth_chainId') return state.chain;
      if (method === 'eth_getBlockByNumber') return block();
      if (method === 'eth_getCode') return '0x1234';
      if (method === 'eth_requestAccounts' || method === 'eth_accounts') return [state.account];
      if (method === 'personal_sign') {
        if (state.cancel) throw {code: 4001};
        state.signed.push(params[0]);
        return '0x' + '00'.repeat(65);
      }
      if (method !== 'eth_call' || params[1] !== block().number) throw Error('Unexpected wallet call');
      const {data, to} = params[0];
      const selector = data.slice(0, 10);
      if (selector === '0x313ce567') return abi(18);
      if (selector === '0x95d89b41') return '0x' + word(32) + word(8) + '414749414c504841'.padEnd(64, '0');
      if (selector === '0x70a08231') {
        if (data.slice(10) !== addressWord(state.account)) throw Error('Wrong balance account');
        return abi(state.account === account ? state.balance * 10n ** 18n : 0n);
      }
      if (selector === '0x02571be3') return '0x' + addressWord(account);
      if (to.toLowerCase() === '0x57f1887a8bf19b14fc0df6fd9b2acc9af147ea85') {
        return abi(data.length === 10 ? 0 : (state.expiration ? 1 : Math.floor(Date.now() / 1000) + 86400));
      }
      throw Error('Unexpected eligibility selector');
    }
  };
  state.emit = (event, payload) => listeners.get(event)?.(payload);
}

async function foundryJourney(page, language, width) {
  const french = language === 'fr';
  const nav = page.locator('.mf-destinations a[href="#my-intelligence"]');
  await nav.press('Enter');
  assert.equal(await nav.getAttribute('aria-current'), 'page');
  assert.equal(await page.locator(':focus').getAttribute('id'), 'my-intelligence-title');
  assert.equal(await page.locator('[data-member-view]:visible').count(), 1);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await capture(page, language, width, 'my-intelligence');
  const online = page.request;
  const release = await (await online.get(base + 'atlas-release.json')).json();
  const zip = await (await online.get(base + 'frontier-foundry-1.0.0.zip')).body();
  assert.equal(createHash('sha256').update(zip).digest('hex'), release.foundry_sha256['frontier-foundry-1.0.0.zip']);
  assert.equal(release.foundry_sha256['frontier-foundry-1.0.0.zip'], '6306d7adf5841cedfff40cf0b8fd3aa5d77b42d8b3108717a48c81f3946e08cb');
  const studyZip = await (await online.get(base + 'frontier-foundry-1.1.0.zip')).body();
  assert.equal(createHash('sha256').update(studyZip).digest('hex'), release.foundry_sha256['frontier-foundry-1.1.0.zip']);
  const inventorZip = await (await online.get(base + 'frontier-inventor-1.0.0.zip')).body();
  assert.equal(createHash('sha256').update(inventorZip).digest('hex'), release.foundry_sha256['frontier-inventor-1.0.0.zip']);
  const learningZip = await (await online.get(base + 'frontier-learning-1.0.0.zip')).body();
  assert.equal(createHash('sha256').update(learningZip).digest('hex'), release.foundry_sha256['frontier-learning-1.0.0.zip']);
  const activationZip = await (await online.get(base + 'frontier-activation-1.0.0.zip')).body();
  assert.equal(createHash('sha256').update(activationZip).digest('hex'), release.foundry_sha256['frontier-activation-1.0.0.zip']);
  const amplificationZip = await (await online.get(base + 'frontier-activation-1.1.0.zip')).body();
  assert.equal(createHash('sha256').update(amplificationZip).digest('hex'), release.foundry_sha256['frontier-activation-1.1.0.zip']);
  assert.equal(release.foundry_sha256['frontier-activation-1.1.0.zip'],
    '158aa880e2a282915f011ff8c4786ec0641b6d5da82178a9e131d0c64a17499c');
  const substrateZip = await (await online.get(base + 'frontier-activation-1.2.0.zip')).body();
  assert.equal(createHash('sha256').update(substrateZip).digest('hex'), release.foundry_sha256['frontier-activation-1.2.0.zip']);
  assert.equal(release.foundry_sha256['frontier-activation-1.2.0.zip'],
    'f4bc4141d5c86c251b04a9a2d129b65ab610242e5422755161e4882bb35cda06');
  const liberationZip = await (await online.get(base + 'frontier-activation-1.3.0.zip')).body();
  assert.equal(createHash('sha256').update(liberationZip).digest('hex'), release.foundry_sha256['frontier-activation-1.3.0.zip']);
  assert.equal(release.foundry_sha256['frontier-activation-1.3.0.zip'],
    'c73a4f0f261a2be986bf6315bd7ce6102167ccad929d9c44bc31701a1386ff1f');
  assert.equal(release.foundry_sha256['frontier-activation-1.4.0.zip'],
    '075e28dae9c58c3b856eaad57faaf9ffe189cae925954211266dcef95ac9335e');
  const cascadeStudies = {};
  for (const name of ['cascade-results.json', 'cascade-fresh-domain.json']) {
    const response = await online.get(base + name);
    assert.ok(response.ok());
    const raw = await response.body();
    assert.equal(createHash('sha256').update(raw).digest('hex'), release.foundry_sha256[name]);
    cascadeStudies[name] = JSON.parse(raw);
  }
  const factoryResponse = await online.get(base + 'factory-results.json');
  assert.ok(factoryResponse.ok());
  const factoryRaw = await factoryResponse.body();
  assert.equal(createHash('sha256').update(factoryRaw).digest('hex'), release.foundry_sha256['factory-results.json']);
  const factoryResults = JSON.parse(factoryRaw).summary;
  const example = await page.locator('#foundry-public-data').evaluate(node => JSON.parse(node.content.textContent));
  const context = page.context();
  await context.setOffline(true);
  try {
    await page.locator('#foundry-sample').click();
    await page.waitForFunction(() => document.getElementById('foundry-comparison').textContent.includes('6/6'));
    assert.deepEqual(JSON.parse(await page.locator('#foundry-output').textContent()), {bytes:327680,ordered:true});
    const exportButton = page.locator('#foundry-retain');
    assert.equal(await exportButton.isEnabled(), false);
    await page.locator('#foundry-export-consent').check();
    const downloaded = page.waitForEvent('download');
    await exportButton.click();
    const original = JSON.parse(await readFile(await (await downloaded).path(), 'utf8'));
    const altered = structuredClone(original);
    altered.asset.candidate.outputs.bytes = 1;
    const open = page.locator('#foundry-open');
    await open.setInputFiles(content('altered.json', altered));
    await page.waitForFunction(lang => document.getElementById('foundry-status').textContent.includes(
      lang === 'fr' ? 'changé' : 'changed'), language);
    await open.setInputFiles(content('retained.json', original));
    await page.waitForFunction(lang => document.getElementById('foundry-comparison').textContent.toLowerCase().includes(
      lang === 'fr' ? 'intégrité' : 'integrity'), language);
    assert.equal(await page.locator('#foundry-run').isEnabled(), false);
    await page.locator('#foundry-cases').setInputFiles(content('original-cases.json', example.suite));
    await page.waitForFunction(() => document.getElementById('foundry-comparison').textContent.includes('6/6'));
    await page.locator('#foundry-inputs').fill('{"start":0,"end":31}');
    await page.locator('#foundry-run').click();
    assert.deepEqual(JSON.parse(await page.locator('#foundry-output').textContent()), {bytes:32,ordered:true});
    await page.locator('#foundry-clear').click();
    assert.equal(await page.locator('#foundry-output').textContent(), '');

    await destination(page, 'mv-tools');
    assert.equal(await page.locator('#foundry-inventor a[download]').count(), 1);
    const items = page.locator('#foundry-library-items li');
    assert.equal(await items.count(), 1);
    const picker = page.locator('#foundry-library-files');
    await picker.setInputFiles([content('original.json', original), content('invalid.json', altered)]);
    await page.waitForFunction(lang => document.getElementById('foundry-library-status').textContent.includes(
      lang === 'fr' ? 'changé' : 'changed'), language);
    assert.equal(await items.count(), 1);
    const libraryDownload = page.waitForEvent('download');
    await items.first().locator('button').nth(1).click();
    assert.deepEqual(JSON.parse(await readFile(await (await libraryDownload).path(), 'utf8')), original);
    await items.first().locator('button').nth(2).click();
    assert.equal(await items.count(), 0);
    await picker.setInputFiles(content('original.json', original));
    await items.first().locator('button').first().click();
    await page.locator('#foundry-verification').waitFor({state:'visible'});
    assert.equal(await page.locator('#foundry-run').isEnabled(), false);
    await page.locator('#foundry-clear').click();

    await page.locator('#foundry-mission summary').click();
    for (const [id,value] of Object.entries({objective:french ? 'Compter les minutes' : 'Count elapsed minutes',
      rule:'Return elapsed = finish - start.', fields:'start:integer, finish:integer', outputs:'elapsed:integer',
      alternative:'Integer subtraction', acceptance:'Exact result from the authorized clock readings'})) {
      await page.locator('#foundry-' + id).fill(value);
    }
    await page.locator('#foundry-freeze').click();
    await page.locator('#foundry-handoff').waitFor({state:'visible'});
    const prompt = await page.locator('#foundry-prompt').inputValue();
    assert.ok(prompt.includes('Exact result from the authorized clock readings'));
    assert.equal(await page.locator('#foundry-copy').isEnabled(), false);
    const allowed = {name:'Elapsed',inputs:['start','finish'],outputs:{elapsed:{op:'sub',args:[{field:'finish'},{field:'start'}]}}};
    await page.locator('#foundry-response').fill(JSON.stringify({...allowed, instructions:'untrusted code'}));
    await page.locator('#foundry-candidate').click();
    assert.equal(await page.locator('#foundry-verification').isVisible(), false);
    await page.locator('#foundry-response').fill(JSON.stringify(allowed));
    await page.locator('#foundry-candidate').click();
    await page.locator('#foundry-verification').waitFor({state:'visible'});
    const exported = page.waitForEvent('download');
    await page.locator('#foundry-project').click();
    const file = await readFile(await (await exported).path(), 'utf8');
    const result = await page.evaluate(raw => globalThis.HarnessEngine.importProject(raw), file);
    assert.equal(result.artifactProvenance.verification, 'UNKNOWN');
    assert.deepEqual(result.instrumentSpec.inputs, ['start','finish']);
    await page.locator('#foundry-response').fill('');
    await page.locator('#foundry-candidate-file').setInputFiles(content('native-project.json', result));
    await page.waitForFunction(() => {
      const reply = document.getElementById('foundry-response').value;
      return reply && JSON.parse(reply).name === 'Elapsed' && !document.getElementById('foundry-cases').disabled;
    });
    const hash = await page.locator('#foundry-mission-hash').textContent();
    await page.locator('#foundry-cases').setInputFiles(content('cases.json', {schema:'frontier/foundry-cases-v1',
      mission_sha256:hash,reference:'Browser qualification fixture, direct integer arithmetic',
      cases:[{input:{start:10,finish:13},expected:{elapsed:3}}]}));
    await page.waitForFunction(() => document.getElementById('foundry-comparison').textContent.includes('1/1'));
    await capture(page, language, width, 'foundry-verified');

    const fixture = await page.evaluate(async ({example, original}) => {
      const here = path => new URL(path, document.baseURI).href;
      const {registerStudy, evaluateStudy} = await import(here('foundry-study.mjs'));
      const {fingerprint} = await import(here('outcome-receipt.mjs'));
      const task = {...example.task, objective:'Reject ranges that are not singletons', outputs:{single:'boolean'}};
      const candidate = {name:'Single byte', inputs:['start','end'],
        outputs:{single:{op:'eq',args:[{field:'start'},{field:'end'}]}}};
      const cases = {...example.suite, mission_sha256:await fingerprint(task), reference:'Independent browser test fixture',
        cases:[{input:{start:3,end:4},expected:{single:false}},{input:{start:7,end:7},expected:{single:true}}]};
      const plan = await registerStudy({task,hypothesis:'Fixture study',model:'local-fixture',output_tokens:128},
        original, example.suite, candidate, cases);
      const good = {status:'SEALED',candidate,elapsed_ns:100,usage:null,reason:null,bindings_used:[]};
      const fail = {...good,status:'NO_CANDIDATE',reason:'FORMULA_REJECTED',candidate:null};
      return {cases, bundle:await evaluateStudy(plan,cases,{direct:fail,ordinary:good,retained:good})};
    }, {example, original});
    await destination(page, 'mv-results');
    const inventor = page.locator('#foundry-inventor-comparison');
    await inventor.locator('summary').press('Enter');
    assert.equal(await inventor.locator('tbody tr').count() >= 3, true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.locator('#foundry-inventor-open').setInputFiles(content('run.json', {
      schema:'frontier/inventor-run-v1', model:'Local inventor fixture', status:'SEALED', events:[{}],
    }));
    await page.waitForFunction(() => document.getElementById('foundry-inventor-local').textContent.includes('Local inventor fixture'));
    const learning = page.locator('#foundry-gains');
    await learning.locator('summary').press('Enter');
    assert.equal(await learning.locator('tbody tr').count(), 2);
    await page.locator('#foundry-learning-open').setInputFiles(content('learning-status.json', {
      schema:'frontier/learning-status-v1', scope:'public-actions-pages', state:'IDLE', observed_at:1795514400,
      observed:71, candidate_sha256:'a'.repeat(64), admitted_sha256:null,
      stages:[{stage:'learn',state:'COMPLETE',result:{state:'CANDIDATE'}}],
    }));
    await page.waitForFunction(() => document.getElementById('foundry-learning-status').textContent.includes('aaaaaaaaaaaa'));
    assert.equal(await page.locator('#foundry-learning-steps li').count(), 1);
    await page.locator('#foundry-activation-open').setInputFiles(content('activation-status.json', {
      schema:'frontier/activation-run-v1', authority:{scope:'public-readonly-research'}, objective:'learning-replay',
      state:'COMPLETE', journal:[{stage:'construct',state:'SEALED'}],
    }));
    await page.locator('#foundry-activation-steps li').waitFor();
    assert.equal(await page.locator('#foundry-activation-steps li').count(), 1);
    const amplification = page.locator('#foundry-amplification-results');
    assert.equal(await amplification.locator('tbody tr').count(), 3);
    await amplification.locator('summary').press('Enter');
    await page.locator('#foundry-amplification-replay').press('Enter');
    const displayed = await page.locator('#foundry-amplification-replay-status').textContent();
    assert.match(displayed, /256.*e045, e072/);
    await destination(page, 'mv-tools');
    await page.locator('a[href="#foundry-substrate-results"]').press('Enter');
    assert.equal(await page.locator('a[href="#mv-results"]').first().getAttribute('aria-current'), 'page');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'foundry-substrate-title');
    await page.locator('#foundry-substrate-results summary').press('Enter');
    await page.locator('#foundry-substrate-replay').press('Enter');
    assert.match(await page.locator('#foundry-substrate-replay-status').textContent(),
      /(?:Covariance-sensitive|Dépend de la covariance).*5817.*175–267 s.*paper:T8:L98/);
    await destination(page, 'mv-tools');
    await page.locator('a[href="#foundry-liberation-results"]').press('Enter');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'foundry-liberation-title');
    await page.locator('#foundry-liberation-results summary').press('Enter');
    assert.deepEqual(await page.locator('#foundry-liberation-results tr td:nth-child(2)').allTextContents(),
      ['96 / 106', '93 / 106', '93 / 106', '94 / 106']);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await destination(page, 'mv-tools');
    await page.locator('a[href="#foundry-cascade-results"]').press('Enter');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'foundry-cascade-title');
    const headingIsClear = await page.locator('#foundry-cascade-title').evaluate(heading =>
      heading.getBoundingClientRect().top >= document.querySelector('.mf-bar').getBoundingClientRect().bottom);
    assert.ok(headingIsClear, 'Cascade heading must clear the sticky member navigation');
    const cascade = page.getByRole('region', {name:'Activation 1.4 · Cascade'});
    assert.match(await cascade.innerText(), /11.*16|16.*11/);
    const {observed} = cascadeStudies['cascade-fresh-domain.json'];
    assert.ok((await cascade.innerText()).includes(`${observed.matches_published}/${observed.seasons_compared}`));
    for (const filename of Object.keys(cascadeStudies)) {
      assert.equal(await cascade.locator(`a[href="${filename}"][download]`).isVisible(), true);
    }
    await cascade.locator('summary').press('Enter');
    const {composition} = cascadeStudies['cascade-results.json'].summary;
    const cells = await cascade.getByRole('cell').allTextContents();
    assert.deepEqual(cells, ['direct','ordinary','typed','conventional','withdrawn'].map(arm =>
      `${composition[arm]} / ${composition.jobs}`));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await capture(page, language, width, 'cascade');
    await destination(page, 'mv-tools');
    await page.locator('a[href="#foundry-factory-results"]').press('Enter');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'foundry-factory-title');
    const factoryHeadingIsClear = await page.locator('#foundry-factory-title').evaluate(heading =>
      heading.getBoundingClientRect().top >= document.querySelector('.mf-bar').getBoundingClientRect().bottom);
    assert.ok(factoryHeadingIsClear, 'Activation 1.5 heading must clear the sticky member navigation');
    const factory = page.getByRole('region', {name:french
      ? 'Activation 1.5 · Atelier d’intelligence productive' : 'Activation 1.5 · Productive Intelligence Factory'});
    const documented = [
      ['prusa_offer', '2026-09-29', 'Prusa HT Hotend · CORE One L'],
      ['bambu_software', '2026-11-24', 'Bambu Studio · H2D'],
    ];
    for (const [claim, date, title] of documented) {
      const row = factoryResults.industry[claim];
      const task = factory.getByRole('article', {name:title});
      const finding = task.locator(`[data-factory-claim="${claim}"]`);
      assert.equal(await finding.getAttribute('data-verdict'), row.verdict);
      assert.equal(await finding.locator('time').getAttribute('datetime'), row.first_verified_by);
      assert.equal(await finding.locator('time').innerText(), date);
      const witness = task.getByRole('link');
      assert.equal(await witness.getAttribute('href'), row.source_url);
      assert.equal(await witness.isVisible(), true);
    }
    const machine = factory.locator('[data-factory-claim="bambu_machine"]');
    assert.equal(await machine.getAttribute('data-verdict'), factoryResults.industry.bambu_machine.verdict);
    assert.match(await machine.innerText(), french ? /Abstention sur le fonctionnement/ : /Abstain on machine operation/);
    assert.equal(await machine.locator('time').count(), 0);
    for (const [domain, fields] of Object.entries({
      hurricane:['cases','shared_origin','physical_agreement'],
      transit:['blind_products','detected_timings','fresh_events','physical_matches','april_b_offset_days'],
    })) {
      for (const field of fields) {
        const value = String(factoryResults[domain][field]);
        assert.equal(await factory.locator(`[data-factory-field="${domain}.${field}"]`).innerText(),
          french ? value.replace('.', ',') : value);
      }
    }
    const forecast = factory.locator('[data-factory-claim="forecast"]');
    assert.equal(await forecast.getAttribute('data-verdict'), 'ABSTAIN');
    assert.match(await forecast.innerText(), french ? /Abstention sur les nouvelles prévisions/ : /Abstain on new forecasts/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await capture(page, language, width, 'factory');
    await factory.locator('summary').press('Enter');
    assert.match(await factory.locator('pre').innerText(), /evidence_truth\.py --case prusa_offer --case bambu_software --case bambu_machine\s+python3 verify_factory\.py/);
    assert.equal(await factory.locator('pre').isVisible(), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const contextFile = {schema:'frontier/amplification-v1', objective:'Local measurement fixture',
      binding:{model:'Local model fixture', arm:'amplified'}, state:'DEVELOPMENT_PASS',
      attempts:[{number:1,scores:{accepted:2,cases:2}}]};
    await page.locator('#foundry-amplification-open').setInputFiles(content('amplification-status.json', {...contextFile,
      attempts:[{number:1,scores:{accepted:3,cases:2}}]}));
    await page.waitForFunction(() => document.getElementById('foundry-amplification-status').textContent.includes('amplification-status.json'));
    assert.equal(await amplification.locator('ol li').count(), 0);
    await page.locator('#foundry-amplification-open').setInputFiles(content('amplification-status.json', contextFile));
    await page.waitForFunction(() => document.getElementById('foundry-amplification-status').textContent.includes('Local measurement fixture'));
    assert.equal(await amplification.locator('ol li').count(), 1);
    await page.locator('#foundry-study-reopen summary').click();
    await page.locator('#foundry-study-report').setInputFiles(content('report.json', fixture.bundle));
    const studyCases = page.locator('#foundry-study-cases');
    await studyCases.setInputFiles(content('changed-cases.json', {...fixture.cases, reference:'Changed reference'}));
    await page.locator('#foundry-study-check').click();
    await page.waitForFunction(lang => document.getElementById('foundry-study-status').textContent.includes(
      lang === 'fr' ? 'diffère' : 'differ'), language);
    assert.equal(await page.locator('#foundry-study-outcomes').isVisible(), false);
    await studyCases.setInputFiles(content('cases.json', fixture.cases));
    await page.locator('#foundry-study-check').click();
    const comparison = page.locator('#foundry-study-outcomes');
    await comparison.waitFor({state:'visible'});
    assert.equal(await comparison.locator('dd').count(), 4);
    assert.match(await comparison.locator('dd').last().textContent(), /2\/2/);
    await capture(page, language, width, 'successor-study');
    await comparison.locator('button').last().click();
    await page.locator('#foundry-verification').waitFor({state:'visible'});
    assert.match(await page.locator('#foundry-comparison').textContent(), /2\/2/);
  } finally { await context.setOffline(false); }
  await destination(page, 'mv-tools');
  await page.locator('a[href="#foundry-cascade-results"]').press('Enter');
  const [cascadeDownload] = await Promise.all([
    page.waitForEvent('download'),
    page.locator('#foundry-cascade-results a[href="frontier-activation-1.4.0.zip"][download]').press('Enter')
  ]);
  assert.equal(cascadeDownload.suggestedFilename(), 'frontier-activation-1.4.0.zip');
  assert.equal(createHash('sha256').update(await readFile(await cascadeDownload.path())).digest('hex'),
    release.foundry_sha256['frontier-activation-1.4.0.zip']);
  await destination(page, 'mv-tools');
  await page.locator('a[href="#foundry-factory-results"]').press('Enter');
  for (const name of ['frontier-activation-1.5.0.zip', 'factory-results.json']) {
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.locator(`#foundry-factory-results a[href="${name}"][download]`).press('Enter')
    ]);
    assert.equal(download.suggestedFilename(), name);
    assert.equal(createHash('sha256').update(await readFile(await download.path())).digest('hex'), release.foundry_sha256[name]);
  }
}

async function destination(page, name) {
  const destinationId = name === 'mv-earlier' ? 'my-intelligence' : name;
  const nav = page.locator(`.mf-destinations a[href="#${destinationId}"]`);
  await nav.press('Enter');
  if (name === 'mv-earlier') await page.locator('#my-intelligence a[href="#mv-earlier"]').press('Enter');
  assert.equal(await nav.getAttribute('aria-current'), 'page');
  assert.equal(await page.locator('[data-member-view]:visible').count(), 1);
  assert.equal(await page.locator(`#${name}`).isVisible(), true);
}

async function ambitionInput(page) {
  if (!await page.locator('#my-frontier').isVisible()) await destination(page, 'my-frontier');
  const input = page.locator('#goal-text');
  if (!await input.isVisible()) await page.locator('#mission-revise').click();
  await input.waitFor({state:'visible'});
  return input;
}

async function memberWorkbench(page, language) {
  const workbench = page.locator('#member-value');
  assert.equal(await workbench.isVisible(), true);
  assert.match(await page.locator('.mf-brand').innerText(), /Member First Ω/i);
  assert.equal(await page.locator('.mf-verified').isVisible(), true);
  assert.match(await page.locator('.mf-disclosure').innerText(), /public/);
  assert.equal(await page.locator('.mv-nav a').count(), 4);
  await destination(page, 'mv-earlier');
  assert.equal(await page.locator(':focus').getAttribute('id'), 'mv-earlier-title');
  const featured = page.locator('#mf-edition');
  await featured.waitFor({state:'visible'});
  assert.equal(await featured.locator('dl dt').count(), 5);
  assert.equal(await featured.locator('details').evaluate(node => node.open), false);
  const openDecision = featured.locator('[data-mv-open]');
  const id = (await openDecision.getAttribute('href')).slice(1);
  const target = page.locator(`[id=${JSON.stringify(id)}]`);
  const filter = page.locator('#mv-query');
  const count = await page.locator('[data-mv-record]').count();
  assert.ok(count >= 8);
  await filter.fill('SQLite');
  assert.ok((await page.locator('[data-mv-record]:visible').count()) > 0);
  assert.ok((await page.locator('[data-mv-record]:visible').count()) < count);
  await filter.fill('');
  await page.locator('#mv-filters summary').click();
  await page.locator('#mv-action').selectOption('ABSTAIN');
  assert.equal(await page.locator('[data-mv-record]:visible').count(), 1);
  await openDecision.click();
  assert.equal(await target.locator('details').evaluate(node => node.open), true);
  assert.equal(await page.locator('#mv-action').inputValue(), '');
  await page.locator('#mv-order').selectOption('newest');
  const timestamps = await page.locator('[data-mv-record]').evaluateAll(nodes => nodes.map(n => n.dataset.observed));
  assert.deepEqual(timestamps, [...timestamps].sort().reverse());
  const memberData = await (await page.request.get(base + 'member-value.json')).json();
  assert.equal(await featured.getAttribute('data-edition-run'), memberData.member_first.edition.member_run);
  const expected = new Map(memberData.briefs.map(row => [row.id, row.review_sha256]));
  const rendered = await page.locator('[data-mv-record]').evaluateAll(nodes => nodes.map(
    card => [card.id.slice('decision-'.length), card.querySelector('[data-review]').dataset.review]));
  assert.equal(rendered.length, expected.size);
  assert.ok(rendered.every(([id, digest]) => digest === expected.get(id) && /^[a-f0-9]{64}$/.test(digest)));
  const catalogueResponse = await page.request.get(base + 'decision-editions/index.json');
  assert.equal(catalogueResponse.status(), 200);
  const catalogue = await catalogueResponse.json();
  await destination(page, 'mv-tools');
  const archiveBox = page.locator('#edition-history');
  await archiveBox.locator('summary').click();
  for (const edition of catalogue.editions) {
    const download = page.waitForEvent('download');
    await archiveBox.locator(`a[download][href$="/${edition.run}.tar.zst"]`).click();
    const raw = await readFile(await (await download).path());
    assert.equal(raw.length, edition.archive_bytes);
    assert.equal(createHash('sha256').update(raw).digest('hex'), edition.archive_sha256);
  }
  assert.ok(await archiveBox.locator('a[download][href$="/verify.py"]').isVisible());
  await archiveBox.locator('summary').click();
  for (const key of ['endpoint', 'archive']) {
    const tool = page.locator('#tool-' + key);
    if (!await tool.locator('.mf-instructions').evaluate(el => el.open)) {
      await tool.locator('.mf-instructions summary').click();
    }
    assert.ok(await tool.locator('.mf-instructions pre').isVisible());
    const download = page.waitForEvent('download');
    await tool.locator('a[download]').click();
    const artifact = await readFile(await (await download).path());
    assert.equal(createHash('sha256').update(artifact).digest('hex'), memberData.capabilities[key].sha256);
    await tool.locator('.mf-instructions summary').click();
  }
  return memberData;
}

async function matchGoal(page, goal, record, action) {
  const input = await ambitionInput(page);
  await input.fill(goal);
  await input.press('Enter');
  const result = page.locator('#goal-result');
  assert.equal(await result.isVisible(), Boolean(record));
  if (record) assert.equal(await result.getAttribute('data-record'), record);
  if (action) assert.equal(await result.getAttribute('data-action'), action);
}

function content(name, item) {
  return {name, mimeType:'application/json', buffer:Buffer.from(JSON.stringify(item))};
}

async function ownerConnectionJourney(page, language, width) {
  const ambition = 'Capture the exponential of AI progrees.';
  const externalRequests = [];
  const origin = new URL(base).origin;
  const observe = request => {
    const url = new URL(request.url());
    if (request.method() === 'POST' || (/^https?:$/u.test(url.protocol) && url.origin !== origin)) externalRequests.push(request.url());
  };
  page.on('request', observe);
  const pages = page.context().pages().length;
  await page.evaluate(() => {
    window.reviewedBriefWrites = [];
    navigator.clipboard.writeText = async text => { window.reviewedBriefWrites.push(text); };
  });
  await page.locator('#goal-text').fill(ambition);
  await page.locator('#goal-submit').click();
  assert.equal(await page.locator('#goal-text').isVisible(), false);
  assert.equal(await page.locator('#my-frontier').isVisible(), true);
  assert.equal(await page.locator('#goal-result').isVisible(), false);
  const prompt = page.locator('#mission-prompt');
  await prompt.waitFor({state:'visible'});
  const brief = await prompt.inputValue();
  assert.ok(brief.includes(ambition));
  assert.ok(brief.length < 1600);
  assert.doesNotMatch(brief, /frontier\/mission-route-result-v1|requestId/u);
  assert.equal(await page.locator('#mission-share').count(), 0);
  assert.equal(await page.locator('#mission-copy').isEnabled(), true);
  assert.equal(await page.locator('#mission-assistant').isVisible(), true);
  assert.equal(await page.locator('#mission-assistant').getAttribute('href'), 'https://chatgpt.com/');
  assert.equal(await page.locator('#mission-codex').getAttribute('href'), 'https://chatgpt.com/codex/');
  assert.equal(await page.locator('#mission-assistant').getAttribute('rel'), 'noopener noreferrer');
  assert.deepEqual(await page.evaluate(() => window.reviewedBriefWrites), []);
  assert.equal(page.context().pages().length, pages);
  assert.deepEqual(externalRequests, []);
  await page.locator('#mission-copy').click();
  const originalCopy = await page.evaluate(() => window.reviewedBriefWrites);
  assert.equal(originalCopy.length, 1);
  assert.ok(originalCopy[0].startsWith(brief));
  await capture(page, language, width, 'default-assisted-brief');
  await page.locator('#mission-configure').click();
  const choices = page.locator('#frontier-mission-panel .intelligence-grid');
  await choices.waitFor({state:'visible'});
  assert.equal(await choices.locator('[data-frontier-assisted]').count(), 1);
  assert.deepEqual(await choices.locator('[data-frontier-connection]').evaluateAll(items => items.map(item => item.dataset.frontierConnection)), ['local','api']);
  for (const route of ['local','api','hybrid']) {
    const choice = page.locator(`#mission-intelligence [data-frontier-connection="${route}"]`);
    if (!await choice.isVisible()) await choice.locator('xpath=ancestor::details[1]').locator(':scope > summary').click();
    await choice.click();
    assert.equal(await page.locator('#my-frontier').isVisible(), true);
    assert.equal(await page.locator('#my-intelligence').isVisible(), false);
    assert.equal(await page.locator('#intelligence-open-native').getAttribute('href'), null);
    assert.equal(await page.locator('#intelligence-check-native').isVisible(), false);
    assert.equal(await page.locator('#intelligence-companion-download').getAttribute('href'), 'frontier-harness-executor-1.5.0.zip');
    assert.equal(await page.locator('#mission-ambition').textContent(), ambition);
    assert.equal(await prompt.isVisible(), false);
  }
  await capture(page, language, width, 'choose-intelligence');
  await choices.locator('[data-frontier-assisted]').click();
  await prompt.waitFor({state:'visible'});
  const work = '## Candidate work\\n\\nCheck&#x20;the scope with a held comparator.\\n\\n'
    + '| Evidence | Decision |\\n| --- | --- |\\n| Δ &#x2192; α | &lt;img src=x onerror=alert(1)&gt; |';
  const copied = '```json\n{"schema":"frontier/mission-route-result-v1","work":'
    + JSON.stringify(work) + ',"route":}\n```';
  await page.locator('#mission-reply').fill(copied);
  await page.locator('#mission-import-reply').click();
  await page.locator('#mission-keep-unverified').waitFor({state:'visible'});
  assert.equal(await page.locator('#frontier-mission-panel').getAttribute('data-state'), 'waiting');
  await page.locator('#mission-keep-unverified').click();
  await page.waitForFunction(() => document.getElementById('frontier-mission-panel').dataset.state === 'review');
  assert.equal(await page.locator('#frontier-mission-panel').getAttribute('data-route'), 'continuing');
  assert.equal(await page.locator('#mission-work h5').textContent(), 'Candidate work');
  assert.equal(await page.locator('#mission-work tbody td').first().textContent(), 'Δ → α');
  assert.match(await page.locator('#mission-work').textContent(), /Check the scope/u);
  assert.equal(await page.locator('#mission-work img').count(), 0);
  assert.match(await page.locator('#mission-status').innerText(), /Verification pending|Vérification à venir/u);
  const originalDownload = page.waitForEvent('download');
  await page.locator('#mission-work-download').click();
  assert.equal(await readFile(await (await originalDownload).path(), 'utf8'), copied);
  await page.locator('#mission-continue-assisted').click();
  await prompt.waitFor({state:'visible'});
  assert.ok((await prompt.inputValue()).includes('Check the scope'));
  assert.deepEqual(await page.evaluate(() => window.reviewedBriefWrites), originalCopy);
  await page.locator('#mission-follow-up').fill('Use the comparator output as the next piece of evidence.');
  await page.locator('#mission-follow-up-form button').click();
  assert.equal(await page.locator('#mission-dialogue-list li').last().textContent(), 'Use the comparator output as the next piece of evidence.');
  await prompt.waitFor({state:'visible'});
  assert.ok((await prompt.inputValue()).includes('Use the comparator output as the next piece of evidence.'));
  const fileText = 'A result to verify\n<script>throw new Error("inert")</script>\n';
  await page.locator('#mission-import-artifact').setInputFiles({name:'working-note.md',mimeType:'text/markdown', buffer:Buffer.from(fileText)});
  const artifact = page.locator('#mission-returned-files li');
  await artifact.waitFor({state:'visible'});
  assert.equal(await artifact.locator('summary').textContent(), 'working-note.md');
  assert.equal(await artifact.locator('pre').textContent(), fileText);
  assert.equal(await artifact.locator('script').count(), 0);
  await destination(page, 'mv-results');
  if (!await page.locator('#mission-keeper').evaluate(item => item.open)) await page.locator('#mission-keeper summary').click();
  const downloading = page.waitForEvent('download');
  await page.locator('#mission-export').click();
  const checkpoint = JSON.parse(await readFile(await (await downloading).path()));
  assert.equal(checkpoint.mission.originalAmbition, ambition);
  assert.equal(checkpoint.mission.reports[0].artifacts[0].content, copied);
  assert.equal(checkpoint.mission.reports[1].artifacts[0].sha256, createHash('sha256').update(fileText).digest('hex'));
  await page.locator('#mission-import').setInputFiles(content('frontier-mission.json', checkpoint));
  await artifact.waitFor({state:'visible'});
  assert.equal(await artifact.locator('pre').textContent(), fileText);
  assert.equal(await page.locator('#mission-ambition').textContent(), ambition);
  assert.deepEqual(externalRequests, []);
  page.off('request', observe);
  await page.evaluate(() => { delete navigator.clipboard.writeText; });
  await page.locator('#mission-new').click();
}

async function proofOfAdvantageJourney(page, language, width) {
  const origin = new URL(base).origin;
  const external = [];
  const watch = request => {
    if (request.method() === 'POST' || new URL(request.url()).origin !== origin) external.push(request.url());
  };
  page.on('request', watch);
  try {
    await page.evaluate(() => {
      window.advantageClipboard = [];
      navigator.clipboard.writeText = async text => { window.advantageClipboard.push(text); };
    });
    const ambition = 'CAPTURE THE EXPONENTIAL';
    await page.locator('#goal-text').fill(ambition);
    await page.locator('#goal-submit').click();
    const prompt = page.locator('#mission-prompt');
    await prompt.waitFor({state:'visible'});
    assert.equal(await prompt.getAttribute('readonly'), null);
    const evidence = page.locator('#mission-evidence-context');
    await evidence.waitFor({state:'visible'});
    await evidence.locator('summary').click();
    const study = evidence.locator('li').filter({hasText:/Battery passport source review|Passeports de batterie/u});
    await study.waitFor({state:'visible'});
    assert.match(await study.innerText(), /14\/16.*6\/6/u);
    const modified = (await prompt.inputValue()) + '\n\nInspect the actual files and cite the relevant source.';
    await prompt.fill(modified);
    await page.locator('#mission-copy').click();
    const copied = await page.evaluate(() => window.advantageClipboard[0]);
    assert.ok(copied.startsWith(modified) && /14\/16.*6\/6/u.test(copied));
    await study.getByRole('checkbox').uncheck();
    await page.locator('#mission-copy').click();
    assert.doesNotMatch(await page.evaluate(() => window.advantageClipboard[1]), /14\/16.*6\/6/u);
    const reply = 'I completed a calculation. [Download the file](sandbox:/mnt/data/claimed.py).';
    await page.locator('#mission-reply').fill(reply);
    await page.locator('#mission-import-reply').click();
    const files = page.locator('#mission-deliverables');
    await files.locator('input').waitFor({state:'visible'});
    assert.match(await page.locator('#mission-next').innerText(), /claimed\.py/u);
    assert.equal(await files.locator('ul li').count(), 0);
    const source = Buffer.from('\ufeff# Returned source\r\nraise RuntimeError("must not execute")\r\n');
    const input = files.locator('#mission-deliverable-import');
    const filename = 'frontier-battery-source-example.json';
    const sample = await (await page.request.get(base + filename)).body();
    await input.setInputFiles([{name:'claimed.py',mimeType:'text/plain',buffer:source},
      {name:filename,mimeType:'application/json',buffer:sample}]);
    const entries = page.locator('#mission-deliverable-list > li');
    await entries.last().waitFor({state:'visible'});
    assert.equal(await entries.count(), 2);
    assert.doesNotMatch(await page.locator('#mission-next').innerText(), /claimed\.py/u);
    await entries.first().locator('summary').click();
    const original = page.waitForEvent('download');
    await entries.first().getByRole('button',{name:/Download original text|Télécharger le texte original/u}).click();
    const sourceDownload = await original;
    assert.equal(sourceDownload.suggestedFilename(),'claimed.py');
    assert.deepEqual(await readFile(await sourceDownload.path()), source);
    await entries.last().locator('summary').click();
    await entries.last().getByRole('button',{name:/Check supplied battery measurements|Vérifier les mesures de batterie fournies/u}).click();
    const receipt = files.locator('[data-file-claim-review]');
    await receipt.waitFor({state:'visible'});
    assert.match(await receipt.innerText(), /example-pack-mass · (?:Contradicted|Contredit) · example-table/u);
    await receipt.getByRole('button',{name:/Keep check receipt|Conserver le relevé/u}).click();
    await page.waitForFunction(() => document.querySelectorAll('#mission-deliverable-list > li').length === 3);
    await destination(page,'mv-results');
    if (!await page.locator('#mission-keeper').evaluate(value => value.open)) await page.locator('#mission-keeper summary').click();
    const exported = page.waitForEvent('download');
    await page.locator('#mission-export').click();
    const mission = JSON.parse(await readFile(await (await exported).path()));
    assert.equal(mission.mission.originalAmbition, ambition);
    const delivered = mission.mission.workFiles;
    assert.equal(delivered.length, 3);
    assert.equal(delivered[0].sha256,createHash('sha256').update(source).digest('hex'));
    assert.equal(JSON.parse(delivered[2].content).inputSha256,delivered[1].sha256);
    await page.locator('#mission-import').setInputFiles(content('frontier-mission.json',mission));
    await files.waitFor({state:'visible'});
    assert.equal(await entries.count(),3);
    await entries.first().locator('summary').click();
    await entries.first().getByRole('button',{name:/Remove result file|Retirer le fichier livré/u}).click();
    assert.match(await page.locator('#mission-next').innerText(), /claimed\.py/u);
    await input.setInputFiles({name:'claimed.py',mimeType:'text/plain',buffer:source});
    await page.waitForFunction(() => document.querySelectorAll('#mission-deliverable-list > li').length === 3);
    assert.doesNotMatch(await page.locator('#mission-next').innerText(), /claimed\.py/u);
    assert.deepEqual(external,[]);
    await capture(page, language, width, 'actual-results-and-checks');
    await page.locator('#mission-new').click();
    checks.push({kind:'proof-of-advantage-ui',language,width,exactAmbition:true,
      editableBriefAndSelectableEvidence:true,missingSandboxArtifact:true,exactFileBytes:true,localEvidenceCheck:true,
      retainedReceiptAndRecovery:true,exactFileRemovalAndReturn:true,noExternalDispatch:true});
  } finally {
    page.off('request',watch);
    await page.evaluate(() => { delete navigator.clipboard.writeText; });
  }
}

async function pairedRevisionJourney(browser, language) {
  const page = await browser.newPage({viewport:dimensions(1440)});
  try {
    await page.addInitScript(fakeWallet);
    await page.addInitScript(() => {
      const fetchPublic = window.fetch.bind(window);
      const fixture = window.missionPairFixture = {operations:[]};
      window.fetch = async (url, options) => {
        const prefix = 'http://127.0.0.1:38463/api/frontier-missions/';
        if (!String(url).startsWith(prefix)) return fetchPublic(url, options);
        const action = url.slice(prefix.length);
        const body = JSON.parse(options.body);
        fixture.operations.push({action,body,credentials:options.credentials,referrerPolicy:options.referrerPolicy});
        const respond = value => new Response(JSON.stringify(value));
        if (action === 'pair') return respond({session:'S'.repeat(43),command_scope:'0'.repeat(24),
          scope:{},intelligence:{selection:null},expires_at:'2080-01-01T00:00:00Z'});
        if (action === 'prepare-intelligence') {
          const idempotency = options.headers['X-Frontier-Command'].split('.')[1];
          const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode('frontier-pages-mission-v1:' + idempotency)));
          const id = 'wf_' + [...digest.slice(0,12)].map(value => value.toString(16).padStart(2,'0')).join('');
          fixture.record = {id,ambition:body.ambition,original_ambition:body.original_ambition,language:body.language,
            status:'awaiting_consent',actions:0,model_calls:0,events:[],artifacts:[]};
          return respond({...fixture.record,setup_ticket:'T'.repeat(43)});
        }
        if (action === 'cancel' && body.id === fixture.record?.id) return respond({...fixture.record,status:'cancelled'});
        if (action === 'release') return respond({released:true});
        throw Error(`Unexpected isolated fixture operation ${action}`);
      };
    });
    await page.goto(base + (language === 'fr' ? 'fr.html' : ''));
    await page.locator('[data-connect="token"]').click();
    await page.locator('#member').waitFor({state:'visible'});
    const original = 'Build frontier AI LLM for Game Theory.';
    const revised = 'Evaluate a strategy using a public example.\nÉtablir un cas de vérification indépendant.';
    for (const ambition of [original, revised]) {
      await (await ambitionInput(page)).fill(ambition);
      await page.locator('#goal-submit').click();
    }
    await page.locator('#mission-configure').click();
    await page.locator('[data-frontier-connection="api"]').click();
    if (!await page.locator('#execution-manual-code').evaluate(node => node.open)) {
      await page.locator('#execution-manual-code summary').click();
    }
    await page.locator('#execution-code').fill('P'.repeat(43));
    await page.locator('#execution-code-form button').click();
    const link = page.locator('#intelligence-open-native');
    await link.waitFor({state:'visible'});
    const native = new URL(await link.getAttribute('href'));
    assert.equal(native.origin, 'http://127.0.0.1:38463');
    assert.deepEqual(Object.fromEntries(native.searchParams), {setup:'intelligence',route:'api',lang:language});
    assert.equal(native.hash, '#ticket=' + 'T'.repeat(43));
    const observed = () => page.evaluate(() => window.missionPairFixture.operations);
    const operations = await observed();
    assert.deepEqual(operations.map(row => row.action), ['pair','prepare-intelligence']);
    assert.deepEqual(operations[1], {action:'prepare-intelligence', body:{ambition:revised,language,original_ambition:original},
      credentials:'omit',referrerPolicy:'no-referrer'});
    await page.locator('#intelligence-cancel-native').click();
    await link.waitFor({state:'hidden'});
    await page.waitForFunction(() => window.missionPairFixture.operations.at(-1)?.action === 'cancel');
    assert.equal(await page.locator('#mission-ambition').textContent(), revised);
    assert.equal(await page.locator('#mission-original').textContent(), original);
    assert.deepEqual((await observed()).map(row => row.action), ['pair','prepare-intelligence','cancel']);
    checks.push({kind:'paired-browser-fixture',language,exactOriginalAndRevision:true,scopedNativeLink:true,reviewCanceled:true});
  } finally { await page.close(); }
}

async function revokedSourceRetry(browser, language) {
  const page = await browser.newPage({viewport:dimensions(1440)});
  try {
    await page.addInitScript(fakeWallet);
    await page.addInitScript(() => {
      const fetchPublic = window.fetch.bind(window);
      window.rehearsedSourceSubmissions = [];
      window.fetch = async (url, options) => {
        const endpoint = 'http://127.0.0.1:38463/api/frontier-missions/';
        if (!String(url).startsWith(endpoint)) return fetchPublic(url, options);
        const action = url.slice(endpoint.length);
        const respond = value => new Response(JSON.stringify(value));
        if (action === 'pair') return respond({session:'S'.repeat(43),command_scope:'0'.repeat(24),
          scope:{model:'local-fixture'},intelligence:{selection:{mode:'local',ready:true,model_label:'Local fixture'}},
          expires_at:'2080-01-01T00:00:00Z'});
        if (action === 'submit') {
          window.rehearsedSourceSubmissions.push(JSON.parse(options.body));
          throw new TypeError('Isolated connector response loss');
        }
        if (action === 'release') return respond({released:true});
        throw Error(`Unexpected local fixture operation ${action}`);
      };
    });
    await page.goto(base + (language === 'fr' ? 'fr.html' : ''));
    await page.locator('[data-connect="token"]').click();
    await page.locator('#mission-files summary').click();
    await page.locator('#mission-documents').setInputFiles({name:'revocable.txt',mimeType:'text/plain',buffer:Buffer.from('Private synthetic example')});
    await page.locator('#mission-document-list li').waitFor({state:'visible'});
    await page.locator('#mission-document-consent').check();
    await page.locator('#goal-text').fill('Compare one declared private source with its local measurement.');
    await page.locator('#goal-submit').click();
    await page.locator('#mission-inline-intelligence [data-frontier-connection="local"]').click();
    await page.locator('#execution-manual-code summary').click();
    await page.locator('#execution-code').fill('P'.repeat(43));
    await page.locator('#execution-code-form button').click();
    const retry = page.locator('#execution-retry');
    await retry.waitFor({state:'visible'});
    assert.deepEqual(await page.evaluate(() => window.rehearsedSourceSubmissions.map(row=>row.documents)),
      [[{name:'revocable.txt',text:'Private synthetic example'}]]);
    await page.locator('#mission-documents-remove').click();
    await retry.click();
    assert.match(await page.locator('#execution-status').textContent(), /sources (changed|ont changé)/u);
    assert.equal(await page.evaluate(() => window.rehearsedSourceSubmissions.length), 1);
    checks.push({kind:'private-source-retry-fixture',language,stoppedAfterRevocation:true,transmissions:1});
  } finally { await page.close(); }
}

async function pairedStatusRecovery(browser, language) {
  const page = await browser.newPage({viewport:dimensions(1440)});
  const origin = new URL(base).origin;
  const endpoint = 'http://127.0.0.1:38463/api/frontier-missions/';
  const operations = [];
  const runs = [];
  let heldStatus;
  try {
    await page.addInitScript(fakeWallet);
    await page.clock.install();
    await page.context().grantPermissions(['local-network-access'], {origin});
    await page.route(endpoint + '**', async route => {
      const request = route.request();
      const headers = {'access-control-allow-origin':origin, 'access-control-allow-methods':'POST',
        'access-control-allow-headers':'Content-Type, X-Frontier-Session, X-Frontier-Command',
        'access-control-allow-private-network':'true'};
      if (request.method() === 'OPTIONS') return route.fulfill({status:204, headers});
      assert.equal(request.method(),'POST');
      const action = request.url().slice(endpoint.length);
      const body = request.postDataJSON();
      operations.push({action, body, session:request.headers()['x-frontier-session']});
      const send = json => route.fulfill({status:200, headers, json});
      if (action === 'pair') return send({session:'S'.repeat(43),command_scope:'0'.repeat(24),
        scope:{model:'local-fixture'},intelligence:{selection:{mode:'local',ready:true,model_label:'Local fixture'}},
        expires_at:'2080-01-01T00:00:00Z'});
      if (action === 'submit') {
        const id = 'wf_' + String(runs.length + 1).padStart(24,'0');
        const record = {id,ambition:body.ambition,original_ambition:body.original_ambition ?? body.ambition,
          language:body.language,status:'running',worker_active:true,actions:0,model_calls:1,events:[],artifacts:[]};
        runs.push({record, polls:0});
        return send(record);
      }
      if (action === 'release') return send({released:true});
      const run = runs.find(item=>item.record.id===body.id);
      assert.ok(run, 'The browser must retain the original paired run ID');
      const terminal = {...run.record,status:'complete',worker_active:false};
      if (action === 'get') {
        if (++run.polls === 1) return route.abort('connectionreset');
        if (run === runs[1]) {
          assert.equal(heldStatus,undefined, 'There can be only one pending status read');
          heldStatus = () => send(terminal);
          return;
        }
        return send(terminal);
      }
      if (action === 'cancel') return send({...terminal,status:'cancelled'});
      if (action === 'export') return send({state:{...terminal,spec:{mission:{
        original_ambition:run.record.original_ambition,language:run.record.language,
      }}},files:{}});
      throw Error('Unexpected isolated fixture operation ' + action);
    });

    await page.goto(base + (language === 'fr' ? 'fr.html' : ''));
    await page.locator('[data-connect="token"]').click();
    await page.locator('#member').waitFor({state:'visible'});
    const original = 'Audit a fictional portable caption reader. Ω';
    const revision = 'Trace the same caption reader with a separate replay.';
    for (const ambition of [original, revision]) {
      await (await ambitionInput(page)).fill(ambition);
      await page.locator('#goal-submit').click();
    }
    await page.locator('#mission-configure').click();
    await page.locator('#mission-inline-intelligence [data-frontier-connection="local"]').click();
    await page.locator('#execution-manual-code summary').click();
    await page.locator('#execution-code').fill('P'.repeat(43));
    const isGet = request => request.url()===endpoint+'get' && request.method()==='POST';
    const execution = page.locator('#mission-execution');
    const exporting = page.locator('#execution-export');
    const firstReset = page.waitForEvent('requestfailed',{predicate:isGet});
    await page.locator('#execution-code-form button').click();
    assert.match((await firstReset).failure()?.errorText ?? '', /ERR_CONNECTION_RESET/u);
    try {
      await page.waitForFunction(()=>document.getElementById('mission-execution').dataset.state==='complete', null, {timeout:9000});
    } catch (error) {
      throw new Error('Status read did not recover after the network reset. ' + JSON.stringify({
        polls:runs[0]?.polls, state:await execution.getAttribute('data-state'), exportEnabled:await exporting.isEnabled(),
      }), {cause:error});
    }
    assert.equal(await exporting.isEnabled(),true);
    assert.equal(await page.locator('#mission-ambition').textContent(),revision);
    assert.equal(await page.locator('#mission-original').textContent(),original);
    const download = page.waitForEvent('download');
    await exporting.click();
    const saved = JSON.parse(await readFile(await (await download).path()));
    assert.equal(saved.state.ambition,revision);
    assert.equal(saved.state.spec.mission.original_ambition,original);
    assert.deepEqual(operations.map(item=>item.action), ['pair','submit','get','get','export']);
    assert.deepEqual(operations.slice(2,4).map(item=>item.body), [{id:runs[0].record.id},{id:runs[0].record.id}]);

    await page.locator('#mission-new').click();
    await page.locator('#goal-text').fill('Cancel the companion replay while a status read is pending.');
    const cancelRunReset = page.waitForEvent('requestfailed',{predicate:isGet});
    await page.locator('#goal-submit').click();
    assert.match((await cancelRunReset).failure()?.errorText ?? '', /ERR_CONNECTION_RESET/u);
    const second = await page.waitForRequest(request => isGet(request) && request.postDataJSON().id===runs[1].record.id);
    await page.locator('#execution-cancel').click();
    await page.waitForFunction(()=>document.getElementById('mission-execution').dataset.state==='cancelled');
    const lateResponse = page.waitForResponse(response=>response.request()===second);
    assert.equal(typeof heldStatus,'function');
    await heldStatus();
    await (await lateResponse).finished();
    await page.clock.fastForward(6000);
    assert.equal(await execution.getAttribute('data-state'),'cancelled');
    assert.equal(await exporting.isEnabled(),true);
    assert.deepEqual(operations.map(item=>item.action), ['pair','submit','get','get','export','submit','get','get','cancel']);
    assert.ok(operations.slice(1).every(item=>item.session==='S'.repeat(43)));
    checks.push({kind:'paired-status-recovery-fixture',language,statusReads:2,retries:1,
      exactOriginalAndRevision:true,exported:true,noDuplicateSubmission:true,lateStatusAfterCancelIgnored:true});
  } finally { await page.close(); }
}

async function universalMission(page, language, width) {
  const panel = page.locator('#frontier-mission-panel');
  const original = 'Build Frontier AI for Game Theory.';
  const initialRequests = [];
  const observe = request => { if (/^http:\/\/127\.0\.0\.1:(38461|11434|38463)\//u.test(request.url())) initialRequests.push(request.url()); };
  page.on('request', observe);
  try {
    await page.locator('#goal-text').fill(original);
    await page.locator('#goal-submit').click();
    await panel.waitFor({state:'visible'});
    assert.equal(await panel.locator('#mission-ambition').textContent(), original);
    assert.equal(await page.locator('#goal-result').isVisible(), false);
    assert.match(await page.locator('#mission-published-summary').innerText(), /−49[.,]5/u);
    assert.deepEqual(await page.locator('#mission-published-links a[download]').evaluateAll(links => links.map(link => link.getAttribute('href'))),
      ['frontier-game-theory-1.0.0.zip','frontier-game-observation-1.0.0.zip']);
    const prompt = page.locator('#mission-prompt');
    await prompt.waitFor({state:'visible'});
    assert.equal(await panel.getAttribute('data-state'), 'waiting');
    assert.match(await prompt.inputValue(), /Build Frontier AI for Game Theory\./u);
    assert.doesNotMatch(await prompt.inputValue(), /frontier\/mission-route-result-v1|requestId/u);
    const technical = page.locator('#mission-technical');
    const revealTechnical = async () => {
      if (!await technical.isVisible()) await technical.locator('xpath=ancestor::details[1]').locator(':scope > summary').click();
      await technical.check();
    };
    await revealTechnical();
    assert.match(await prompt.inputValue(), language === 'fr' ? /Écrivez en français/u : /Write text in English/u);
    assert.match(await prompt.inputValue(), language === 'fr' ? /Identifiant de l’exécution en cours/u : /Current mission run reference/u);
    assert.match(await prompt.inputValue(), /NOAA GFS(?: historical)? f024/u);
    assert.match(await prompt.inputValue(), /game-theory-verified-strategic-allocation/u);
    assert.equal(await page.locator('#mission-copy').isEnabled(), true);
    const requestId = (await prompt.inputValue()).match(/"requestId":"([a-f0-9]{64})"/u)[1];
    const reply = {schema:'frontier/mission-route-result-v1', requestId, route:'invention',
      objective:'Check a finite zero-sum game with two bounded alternatives.', assumptions:['Use the published payoff data.'],
      nextAction:'Compare the certificate bounds with a dense solver for a held game.',
      work:'Illustrative transport fixture <img src=x onerror=alert(1)>', capabilityIds:[]};
    await destination(page, 'mv-results');
    if (!await page.locator('#mission-keeper').evaluate(item => item.open)) await page.locator('#mission-keeper summary').click();
    const saving = page.waitForEvent('download');
    await page.locator('#mission-export').click();
    const saved = JSON.parse(await readFile(await (await saving).path()));
    assert.equal(saved.mission.originalAmbition, original);
    assert.equal(saved.mission.request.requestId, requestId);
    await page.locator('#mission-import').setInputFiles(content('frontier-mission.json', saved));
    await panel.waitFor({state:'visible'});
    await revealTechnical();
    assert.match(await prompt.inputValue(), new RegExp(requestId));
    assert.equal(await page.locator('#mission-assistant').getAttribute('href'), 'https://chatgpt.com/');
    await page.locator('#mission-reply').fill(JSON.stringify({...reply,requestId:'0'.repeat(64)}));
    await page.locator('#mission-import-reply').click();
    await page.waitForFunction(lang => document.getElementById('mission-handoff-status').textContent.includes(lang === 'fr' ? 'ne correspond' : 'does not match'), language);
    assert.equal(await panel.getAttribute('data-state'), 'waiting');
    assert.equal(await page.locator('#mission-keep-unverified').isVisible(), true);
    await page.locator('#mission-reply').fill(JSON.stringify(reply));
    await page.locator('#mission-import-reply').click();
    await page.waitForFunction(() => document.getElementById('frontier-mission-panel').dataset.state === 'review');
    assert.equal(await panel.getAttribute('data-route'), 'invention');
    assert.equal(await page.locator('#mission-work').textContent(), reply.work);
    assert.equal(await page.locator('#mission-work img').count(), 0);
    assert.match(await page.locator('#mission-status').textContent(), /Assisted result|Résultat assisté/u);
    assert.deepEqual(initialRequests, []);
    await capture(page, language, width, 'universal-mission');
    const stranger = (language === 'fr' ? 'Construire une preuve de conformité temporelle.\n' : 'Create an interoperable time-series certificate.\n') + 'Δ → α\n'.repeat(105);
    await (await ambitionInput(page)).fill(stranger);
    await page.locator('#goal-submit').click();
    assert.equal(await panel.locator('#mission-ambition').textContent(), stranger);
    assert.equal(await panel.locator('#mission-original').textContent(), original);
    await prompt.waitFor({state:'visible'});
    assert.equal(await panel.getAttribute('data-state'), 'waiting');
    await page.locator('#mission-cancel').click();
    assert.equal(await panel.getAttribute('data-state'), 'canceled');
    await page.locator('#mission-continue').click();
    await page.waitForFunction(() => ['ready','waiting'].includes(document.getElementById('frontier-mission-panel').dataset.state));
    await page.locator('#mission-new').click();
    assert.equal(await panel.isVisible(), false);
    assert.equal(await page.locator('#goal-text').inputValue(), '');
  } finally { page.off('request', observe); }
}

async function missionSourceRecovery(page, language) {
  const contacts = [];
  const observe = request => {
    if (request.method() === 'POST') contacts.push(new URL(request.url()).origin);
  };
  page.on('request', observe);
  try {
    const ambition = language === 'fr' ? 'Évaluer des relevés de débit à chaque traversée.' : 'Evaluate flow records across repeated traversals.';
    const source = {name:'flow-example.csv', text:'time,flow\n1,39\n2,41\n'};
    await page.locator('#mission-files summary').click();
    await page.locator('#mission-documents').setInputFiles({name:source.name, mimeType:'text/csv', buffer:Buffer.from(source.text)});
    await page.locator('#mission-document-list li').waitFor({state:'visible'});
    await page.locator('#goal-text').fill(ambition);
    await page.locator('#goal-submit').click();
    assert.equal(await page.locator('#mission-document-consent').isChecked(), false);
    assert.equal(await page.locator('#mission-inline-files #mission-document-list li').textContent(), source.name);
    await page.locator('#mission-inline-intelligence .intelligence-grid [data-frontier-assisted]').click();
    assert.equal(await page.locator('#mission-prompt').isVisible(), false);
    assert.equal(await page.locator('#mission-assistant').isVisible(), false);
    await page.locator('#mission-inline-intelligence [data-frontier-connection="api"]').click();
    assert.equal(await page.locator('#intelligence-open-native').isVisible(), false);
    await page.locator('#mission-document-consent').check();
    await destination(page, 'mv-results');
    if (!await page.locator('#mission-keeper').evaluate(item => item.open)) await page.locator('#mission-keeper summary').click();
    const down = page.waitForEvent('download');
    await page.locator('#mission-export').click();
    const saved = JSON.parse(await readFile(await (await down).path()));
    assert.equal(saved.mission.originalAmbition, ambition);
    assert.deepEqual(saved.mission.documents, [source]);
    await page.locator('#mission-import').setInputFiles(content('private-mission.json', saved));
    await page.locator('#mission-ambition').waitFor({state:'visible'});
    const files = page.locator('#mission-files');
    if (!await files.evaluate(node => node.open)) await files.locator(':scope > summary').click();
    assert.equal(await page.locator('#mission-document-list li').textContent(), source.name);
    assert.equal(await page.locator('#mission-document-consent').isChecked(), false);
    assert.deepEqual(contacts, []);
    await page.locator('#mission-new').click();
  } finally { page.off('request', observe); }
}

async function guidedJourney(page, language, width, started) {
  const fr = language === 'fr';
  assert.equal(await page.locator('#mv-export').isEnabled(), false);
  const context = page.context();
  let scriptedMs, saved;
  await context.setOffline(true);
  try {
    if (!await page.locator('#mission-examples').evaluate(item => item.open)) await page.locator('#mission-examples summary').click();
    await page.locator('[data-goal="endpoint"]').click();
    const result = page.locator('#goal-result');
    assert.equal(await result.getAttribute('data-record'), 'shift-autonomous-endpoint');
    assert.equal(await result.getAttribute('data-action'), 'demo');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'goal-result-title');
    assert.match(await page.locator('#goal-ambition').innerText(), /endpoint|service d’IA/i);
    assert.equal(await result.locator('#goal-source').getAttribute('href') !== '#mv-better', true);
    assert.match(await result.locator('[data-goal-fact="alternative"]').innerText(), /SQLite/);
    assert.match(await result.locator('#goal-evidence-state').innerText(), /ABSTAIN|abstention/i);
    await page.locator('#goal-action').click();
    const output = page.locator('#mv-screen-result');
    await output.waitFor({state:'visible'});
    assert.match(await output.innerText(), /140/);
    assert.match(await output.innerText(), /ABSTAIN|abstention/i);
    assert.match(await output.innerText(), /demonstration|démonstration/i);
    assert.match(await output.innerText(), /SQLite/);
    assert.match(await page.locator('.mf-steps [aria-current="step"]').innerText(), /Result|Résultat/);
    assert.equal(await page.locator('#my-frontier').isVisible(), true);
    assert.equal(await page.locator('#mv-tools').isVisible(), false);
    const metric = await output.locator('.mf-result-metric strong').boundingBox();
    const bar = await page.locator('.mf-bar').boundingBox();
    assert.ok(metric.y >= bar.y + bar.height, 'The sticky header must not obscure the outcome');
    await capture(page, language, width, 'guided-result');
    await output.locator('summary').press('Enter');
    assert.match(await output.locator('.mv-plan').innerText(), /100[\s\S]*500/);
    assert.match(await output.locator('details').innerText(), /147\.612074/);
    assert.match(await output.locator('a').last().getAttribute('href'), /^https:\/\/results\.mlcommons\.org\//);
    await output.locator('summary').press('Enter');
    assert.equal(await page.locator('#mv-export').isEnabled(), false);
    await page.locator('#mv-keep-result').click();
    assert.equal(await page.locator(':focus').getAttribute('id'), 'mv-consent');
    await page.locator('#mv-consent').check();
    await page.locator('#mv-consent').uncheck();
    assert.equal(await page.locator('#mv-export').isEnabled(), false);
    await page.locator('#mv-consent').check();
    const download = page.waitForEvent('download');
    await page.locator('#mv-export').click();
    const receipt = await readFile(await (await download).path());
    const proof = JSON.parse(receipt);
    assert.equal(proof.receipt.verification, 'matched-frozen-independent-sqlite-reference');
    assert.equal(proof.receipt.recorded_highest_load, 140);
    assert.equal(proof.receipt.complete_cost, null);
    assert.equal(proof.receipt.realized_member_value, null);
    assert.ok(!receipt.includes(Buffer.from('GB300')));
    assert.ok(!receipt.includes(Buffer.from('0x' + '12'.repeat(20))));
    await destination(page, 'mv-results');
    assert.equal(await page.locator('#mf-current-result').isVisible(), true);
    await page.locator('#mv-import').setInputFiles({name:'proof.json',mimeType:'application/json',buffer:receipt});
    await page.waitForFunction(() => document.getElementById('mv-receipt-status').textContent.includes('SQLite'));
    scriptedMs = Math.round(performance.now() - started);
    assert.ok(scriptedMs < 180_000);
    proof.receipt.recorded_highest_load = 141;
    await page.locator('#mv-import').setInputFiles(content('changed.json', proof));
    await page.waitForFunction(lang => document.getElementById('mv-receipt-status').textContent.includes(
      lang === 'fr' ? 'invalide' : 'altered'), language);
    proof.sha256 = await page.evaluate(async receipt => {
      const {fingerprint} = await import(new URL('outcome-receipt.mjs', location.href).href);
      return fingerprint(receipt);
    }, proof.receipt);
    await page.locator('#mv-import').setInputFiles(content('rehashed.json', proof));
    await page.waitForFunction(lang => document.getElementById('mv-receipt-status').textContent.includes(
      lang === 'fr' ? 'invalide' : 'altered'), language);

    await matchGoal(page, fr ? 'Retrouver une prévision NOAA' : 'Find a historical NOAA forecast',
      'shift-archive-point', 'tool');
    await capture(page, language, width, 'goal-match');
    await page.locator('#goal-action').click();
    assert.equal(await page.locator('#tool-archive .mf-instructions').evaluate(el => el.open), true);
    await matchGoal(page, fr ? 'Prévision NOAA hors ligne' : 'Retrieve a NOAA forecast offline',
      'shift-archive-point', 'review');
    await matchGoal(page, fr ? 'latence Endpoint pour du trafic réel' : 'Endpoint latency for real traffic',
      'shift-autonomous-endpoint', 'review');
    await matchGoal(page, fr ? 'Reconstituer une mesure manquante par processus gaussien' : 'Reconstruct a missing measurement with a Gaussian process',
      'shift-measurement-gap', 'review');
    assert.match(await result.locator('#goal-evidence-state').innerText(), /falsified|réfuté/i);
    const typed = 'NOAA';
    await matchGoal(page, typed, 'shift-archive-point', 'tool');
    await destination(page, 'mv-results');
    await page.locator('#goal-keeper summary').click();
    const goalDownload = page.waitForEvent('download');
    await page.locator('#goal-export').click();
    saved = JSON.parse(await readFile(await (await goalDownload).path()));
    assert.deepEqual(Object.keys(saved).sort(), ['goal','pin','schema']);
    assert.deepEqual(saved.goal, {text:typed});
    assert.equal(saved.pin.id, 'shift-archive-point');
    await page.locator('#goal-import').setInputFiles(content('goal.json', saved));
    await page.waitForFunction(lang => document.getElementById('goal-status').textContent.includes(
      lang === 'fr' ? 'concorde' : 'matches today'), language);
    const old = {...saved, pin:{...saved.pin, review:'0'.repeat(64)}};
    await destination(page, 'mv-results');
    await page.locator('#goal-import').setInputFiles(content('older.json', old));
    await page.waitForFunction(lang => document.getElementById('goal-status').textContent.includes(
      lang === 'fr' ? 'a changé' : 'has changed'), language);
    const missing = {...saved, pin:{...saved.pin, id:'removed-evidence'}};
    await destination(page, 'mv-results');
    await page.locator('#goal-import').setInputFiles(content('missing.json', missing));
    await page.waitForFunction(lang => document.getElementById('goal-status').textContent.includes(
      lang === 'fr' ? 'absentes' : 'unavailable'), language);
    await destination(page, 'mv-results');
    await page.locator('#goal-import').setInputFiles(content('invalid.json', {wallet:'invalid'}));
    await page.waitForFunction(lang => document.getElementById('goal-file-status').textContent.includes(
      lang === 'fr' ? 'Impossible' : 'could not be opened'), language);
    const unfamiliar = fr ? 'Accorder un harmonica avec de la cire d’abeille' : 'Tune a harmonica reed with beeswax';
    await matchGoal(page, unfamiliar, null);
    assert.equal(await page.locator('#mission-ambition').textContent(), unfamiliar);
    assert.ok((await page.locator('#mission-next').innerText()).trim());
    await page.locator('#mission-prompt').waitFor({state:'visible'});
  } finally {
    await context.setOffline(false);
  }
  const [viewportWidth, renderedWidth] = await page.evaluate(
    () => [document.documentElement.clientWidth, document.documentElement.scrollWidth]);
  assert.ok(renderedWidth <= viewportWidth);
  return {scriptedMs, saved};
}

async function rejectBrokenRun(page, language) {
  const fr = language === 'fr';
  if (await page.locator('#frontier-mission-panel').isVisible()) await page.locator('#mission-new').click();
  // Fail only the final result-digest call inside this isolated browser fixture.
  await page.evaluate(() => {
    const original = crypto.subtle.digest.bind(crypto.subtle);
    crypto.subtle.digest = async (algorithm, payload) => {
      if (new TextDecoder().decode(payload).includes('frontier/endpoint-result-v1')) throw Error('test interruption');
      return original(algorithm, payload);
    };
    window.restoreScreenDigest = () => { crypto.subtle.digest = original; };
  });
  if (!await page.locator('#mission-examples').evaluate(item => item.open)) await page.locator('#mission-examples summary').click();
  await page.locator('#mf-quick-run').click();
  await page.locator('#goal-action').click();
  await page.waitForFunction(phrase => document.getElementById('mv-run-status').textContent.includes(phrase),
    fr ? 'interrompue' : 'interrupted');
  assert.equal(await page.locator('#mv-screen-result').isVisible(), false);
  assert.equal(await page.locator('#mv-export').isEnabled(), false);
  await page.evaluate(() => window.restoreScreenDigest());
  await page.locator('#goal-action').click();
  await page.locator('#mv-screen-result').waitFor({state:'visible'});
  assert.match(await page.locator('#mv-screen-result').textContent(), /140/);
}

async function walletPaths(browser, language, width) {
  const page = await browser.newPage({ viewport:dimensions(width), reducedMotion:'reduce' });
  try {
    await page.clock.install();
    await page.addInitScript(fakeWallet);
    const response = await page.goto(base + (language === 'fr' ? 'fr.html' : ''));
    assert.equal(response.status(), 200);
    const token = page.locator('[data-connect="token"]');
    const club = page.locator('[data-connect="club"]');
    const clubPortal = page.locator('#enter-club');
    const member = page.locator('#member');
    const brief = page.locator('#brief-content');
    const tokenDenied = language === 'fr' ? /ne satisfait/ : /does not meet/;
    const clubDenied = language === 'fr' ? /ne détient pas/ : /does not meet/;
    const canceled = language === 'fr' ? /annulée/ : /canceled/;

    await page.evaluate(() => { window.walletScenario.chain = '0x2'; });
    await token.click();
    await page.waitForFunction(regex => new RegExp(regex).test(document.getElementById('status').textContent),
      language === 'fr' ? 'réseau principal Ethereum' : 'Select Ethereum Mainnet');
    assert.equal(await member.isVisible(), false);
    assert.equal(await page.evaluate(() => window.walletScenario.signed.length), 0);
    await page.evaluate(() => { window.walletScenario.chain = '0x1'; });
    await page.evaluate(() => { window.walletScenario.balance = 999_999n; });
    await token.click();
    await page.waitForFunction(regex => new RegExp(regex).test(document.getElementById('status').textContent), tokenDenied.source);
    assert.equal(await member.isVisible(), false);

    await page.evaluate(() => { window.walletScenario.balance = 1_000_000n; window.walletScenario.cancel = true; });
    await token.click();
    await page.waitForFunction(regex => new RegExp(regex).test(document.getElementById('status').textContent), canceled.source);
    assert.equal(await member.isVisible(), false);

    await page.evaluate(() => { window.walletScenario.cancel = false; });
    const started = performance.now();
    await token.click();
    await member.waitFor({ state: 'visible' });
    assert.equal(await page.locator(':focus').getAttribute('id'), 'workspace-title');
    assert.equal(await page.locator('#access').isVisible(), false);
    assert.equal(await page.locator('#member-preview').isVisible(), false);
    assert.equal(await page.locator('#member-nav').getAttribute('href'), '#member');
    assert.match(await page.locator('#member-route').innerText(), /\$AGIALPHA/);
    assert.match(await page.locator('#workspace-title').innerText(), /My Frontier|Ma frontière/i);
    assert.equal(await page.locator('#possibility-shifts').isVisible(), false);
    assert.equal(await page.locator('#mf-edition').isVisible(), false);
    assert.equal(await page.locator('[data-member-view]:visible').count(), 1);
    assert.equal(await page.locator('.mf-destinations [aria-current="page"]').getAttribute('href'), '#my-frontier');
    const goalInput = await page.locator('#goal-text').boundingBox();
    const goalSubmit = await page.locator('#goal-submit').boundingBox();
    assert.equal(await page.locator('#mf-quick-run').isVisible(), false);
    assert.match(await page.locator('#goal-submit').innerText(), /Activate FRONTIER Ω|Activer FRONTIER Ω/u);
    assert.ok([goalInput, goalSubmit].every(box => box.y >= 0 && box.y + box.height <= dimensions(width).height));
    await capture(page, language, width, 'arrival-token');
    await ownerConnectionJourney(page, language, width);
    if (width === (language === 'fr' ? 390 : 1440)) await proofOfAdvantageJourney(page, language, width);
    await universalMission(page, language, width);
    await missionSourceRecovery(page, language);
    const {scriptedMs, saved} = await guidedJourney(page, language, width, started);
    await rejectBrokenRun(page, language);
    await destination(page, 'mv-earlier');
    await page.locator('#open-brief').click();
    await brief.waitFor({ state: 'visible' });
    assert.match(await brief.innerText(), /1\.2/);
    assert.ok(await brief.locator('a').count() > 0);
    const manifest = await memberWorkbench(page, language);
    const admitted = manifest.briefs.find(row => row.id.startsWith('watch-arxiv-'));
    await matchGoal(page, admitted.source_version, admitted.id, 'review');
    assert.equal(admitted.evidence, 'source-identity-only');

    await foundryJourney(page, language, width);
    await page.locator('.mf-public-link').click();
    assert.equal(await page.locator('#possibility-shifts').isVisible(), true);
    assert.equal(await member.isVisible(), false);
    await page.locator('#member-nav').click();
    assert.equal(await page.locator('#my-frontier').isVisible(), true);
    assert.equal(await page.locator('#goal-result').getAttribute('data-record'), admitted.id);

    await page.clock.fastForward(301_000);
    await member.waitFor({ state: 'hidden' });
    assert.equal(await brief.textContent(), '');
    assert.equal(await page.locator('#mv-screen-result').textContent(), '');
    assert.equal(await page.locator('#mv-consent').isChecked(), false);
    assert.equal(await page.locator('#goal-text').inputValue(), '');
    assert.equal(await page.locator('#frontier-mission-panel').isVisible(), false);
    assert.equal(await page.locator('#mission-ambition').textContent(), '');
    assert.equal(await page.locator('#foundry-objective').inputValue(), '');
    assert.equal(await page.locator('#foundry-comparison').textContent(), '');
    assert.equal(await page.locator('#foundry-library-items li').count(), 0);
    assert.equal(await page.locator('#foundry-study-outcomes dd').count(), 0);
    assert.equal(await page.locator('#foundry-inventor-local').textContent(), '');
    assert.equal(await page.locator('#foundry-learning-status').textContent(), '');
    assert.equal(await page.locator('#foundry-learning-steps li').count(), 0);
    assert.equal(await page.locator('#foundry-activation-status').textContent(), '');
    assert.equal(await page.locator('#foundry-activation-steps li').count(), 0);
    assert.equal(await page.locator('#foundry-amplification-status').textContent(), '');
    assert.equal(await page.locator('#foundry-amplification-attempts li').count(), 0);
    assert.equal(await page.locator('#foundry-amplification-replay-status').textContent(), '');
    assert.equal(await page.locator('#foundry-substrate-replay-status').textContent(), '');
    assert.equal(await page.locator('#foundry-cascade-results').isVisible(), false);
    assert.equal(await page.locator('#foundry-factory-results').isVisible(), false);
    assert.equal(await page.locator('#goal-result').isVisible(), false);
    assert.equal(await page.locator('#goal-export').isEnabled(), false);
    assert.equal(await page.locator('#access').isVisible(), true);
    assert.equal(await page.locator('#member-nav').getAttribute('href'), '#access');

    assert.equal(await page.locator('#club-form').isVisible(), false);
    await clubPortal.click();
    assert.equal(await clubPortal.getAttribute('aria-expanded'), 'true');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'club-label');
    await page.locator('#club-label').fill('frontier-check');
    await page.evaluate(() => { window.walletScenario.expiration = true; });
    await club.click();
    await page.waitForFunction(regex => new RegExp(regex).test(document.getElementById('status').textContent), clubDenied.source);
    assert.equal(await member.isVisible(), false);

    await page.evaluate(() => { window.walletScenario.expiration = false; });
    await club.click();
    await member.waitFor({ state: 'visible' });
    assert.match(await page.locator('#member-route').innerText(), /AGI CLUB/);
    await capture(page, language, width, 'arrival-club');
    await page.locator('a[href="#opportunity-capture"]').press('Enter');
    const opportunity = page.locator('#opportunity-capture');
    assert.equal(await opportunity.isVisible(), true);
    const entry = await opportunity.evaluate(section => ({
      headingTop: section.querySelector('h4').getBoundingClientRect().top,
      headerBottom: document.querySelector('.mf-bar').getBoundingClientRect().bottom,
      disclosureOpen: section.querySelector('details').open
    }));
    assert.ok(entry.headingTop >= entry.headerBottom - 1);
    assert.equal(entry.disclosureOpen, false);
    const study = await (await page.request.get(base + 'opportunity-capture.json')).json();
    assert.ok(study.opportunities.length >= 2);
    assert.deepEqual(await opportunity.locator('[data-opportunity]').evaluateAll(cards =>
      cards.map(card => [card.dataset.opportunity, card.dataset.stage])),
    study.opportunities.map(row => [row.id, row.state]));
    await capture(page, language, width, 'opportunity-capture');
    await destination(page, 'mv-results');
    await page.locator('#goal-keeper summary').click();
    await page.locator('#goal-import').setInputFiles(content('recovered.json', saved));
    await page.waitForFunction(() => document.getElementById('goal-result').dataset.record === 'shift-archive-point'
      && !document.getElementById('goal-result').hidden);
    assert.equal(await page.locator('#goal-text').inputValue(), 'NOAA');
    await destination(page, 'mv-earlier');
    await page.locator('#open-brief').click();
    await brief.waitFor({ state: 'visible' });
    assert.match(await brief.innerText(), /1\.2/);
    assert.equal(await page.locator('#mf-edition').isVisible(), true);
    assert.ok(await page.locator('.mv-timeline a[href^="#decision-watch-"]').count() > 0);
    await destination(page, 'mv-tools');
    await page.locator('a[href="#foundry-cascade-results"]').press('Enter');
    assert.equal(await page.locator('#foundry-cascade-results').isVisible(), true);
    await destination(page, 'mv-tools');
    await page.locator('a[href="#foundry-factory-results"]').press('Enter');
    assert.equal(await page.locator('#foundry-factory-results').isVisible(), true);
    await page.locator('#lock').click();
    await member.waitFor({ state: 'hidden' });
    await club.click();
    await member.waitFor({ state: 'visible' });

    await page.evaluate(() => {
      window.walletScenario.account = '0x' + '34'.repeat(20);
      window.walletScenario.emit('accountsChanged', [window.walletScenario.account]);
    });
    await member.waitFor({ state: 'hidden' });
    assert.equal(await page.locator('#mf-edition').isVisible(), false);
    assert.equal(await page.locator('#access').isVisible(), true);
    await club.click();
    await page.waitForFunction(regex => new RegExp(regex).test(document.getElementById('status').textContent), clubDenied.source);
    assert.equal(await brief.textContent(), '');
    const state = await page.evaluate(() => ({
      methods: window.walletScenario.methods, signed: window.walletScenario.signed
    }));
    assert.ok(state.methods.every(m => ['eth_requestAccounts', 'eth_accounts', 'eth_getCode',
      'eth_chainId', 'eth_getBlockByNumber', 'eth_call', 'personal_sign'].includes(m)));
    const messages = state.signed.map(hex => Buffer.from(hex.slice(2), 'hex').toString());
    assert.ok(messages.every(message => message.includes('does not approve a transaction') && message.includes(new URL(base).origin)));
    assert.equal(new Set(messages).size, 3);
    checks.push({kind:'member-ui', language, width, provider:'isolated declared test wallet',
      eligibleRoutes:['AGI CLUB','AGIALPHA'], rejects:['wrong network','under balance','expired name','canceled signature'],
      brief:'001 v1.2', arrivalAboveFold:true, featuredBrief:true, downloadHashes:true, publicBenchmarkedScreen:140,
      scriptedFirstUseMs:scriptedMs, scriptedJourney:'sign in → goal → run → export → recheck',
      goalAwareRanking:true, savedGoalRecheck:true, missingEvidenceCheck:true, liveEvidenceFingerprints:true, restoredAfterSignIn:true,
      appShell:true, keyboardNavigation:true, publicAtlasReturn:true,
      executionFailureAndRetry:true, foundryOfflineReplay:true, foundryManualHandoffFixture:true,
      foundryNativeProject:true, foundryAssetReopen:true, foundryPortfolio:true, foundrySuccessorStudyReplay:true,
      foundryInventorPilot:true,
      cascadeEvidenceAndDownload:true,
      factoryEvidenceAndDownloads:true,
      opportunityCapture:true,
      universalMission:true, ownerConnectionJourney:true, assistedMissionFixture:true, ordinaryAssistedWork:true,
      assistedDefaultPrepared:true, noAutomaticShareOrClipboard:true,
      verifiedOriginalAssistedDownload:true, conversationalFollowUp:true, privateDocumentRecovery:true,
      inertAssistedTextArtifact:true, missionRecovery:true,
      offlineRunAndReceipt: true, receiptTamperDenial: true, rehashedReceiptDenial:true, archivedEditionDownloads:true,
      lock: true, expiry: true, reconnect: true, accountSwitchDenial: true });
  } finally {
    await page.close();
  }
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.FRONTIER_CHROME ?? '/usr/bin/google-chrome' });
  try {
    for (const language of ['en', 'fr']) {
      for (const width of [1440,390]) {
        await publicAtlas(browser, language, width);
        await walletPaths(browser, language, width);
      }
      await pairedRevisionJourney(browser, language);
      await revokedSourceRetry(browser, language);
      await pairedStatusRecovery(browser, language);
    }
    process.stdout.write(JSON.stringify(checks, null, 2) + '\n');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
