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

async function memberWorkbench(page, language) {
  const workbench = page.locator('#member-value');
  assert.equal(await workbench.isVisible(), true);
  assert.match(await page.locator('#workspace-title').innerText(), /Member First Ω/i);
  assert.equal(await page.locator('.mf-verified').isVisible(), true);
  assert.match(await page.locator('.mf-disclosure').innerText(), /public/);
  assert.equal(await page.locator('.mv-nav a').count(), 4);
  const featured = page.locator('#mf-edition');
  await featured.waitFor({state:'visible'});
  assert.equal(await featured.locator('dl dt').count(), 5);
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
  await page.locator('#goal-text').fill(goal);
  await page.locator('#goal-text').press('Enter');
  const result = page.locator('#goal-result');
  assert.equal(await result.isVisible(), Boolean(record));
  if (record) assert.equal(await result.getAttribute('data-record'), record);
  if (action) assert.equal(await result.getAttribute('data-action'), action);
}

function content(name, item) {
  return {name, mimeType:'application/json', buffer:Buffer.from(JSON.stringify(item))};
}

async function guidedJourney(page, language, width, started) {
  const fr = language === 'fr';
  assert.equal(await page.locator('#mv-export').isEnabled(), false);
  const context = page.context();
  let scriptedMs, saved;
  await context.setOffline(true);
  try {
    await page.locator('[data-goal="endpoint"]').click();
    const result = page.locator('#goal-result');
    assert.equal(await result.getAttribute('data-record'), 'shift-autonomous-endpoint');
    assert.equal(await result.getAttribute('data-action'), 'demo');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'goal-result-title');
    assert.match(await result.locator('[data-goal-fact="alternative"]').innerText(), /SQLite/);
    assert.match(await result.locator('#goal-evidence-state').innerText(), /ABSTAIN|abstention/i);
    await page.locator('#goal-action').click();
    const output = page.locator('#mv-screen-result');
    await output.waitFor({state:'visible'});
    assert.match(await output.innerText(), /140/);
    assert.match(await output.innerText(), /ABSTAIN|abstention/i);
    assert.match(await output.innerText(), /demonstration|démonstration/i);
    assert.match(await output.innerText(), /SQLite/);
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
    await page.locator('#goal-import').setInputFiles(content('older.json', old));
    await page.waitForFunction(lang => document.getElementById('goal-status').textContent.includes(
      lang === 'fr' ? 'a changé' : 'has changed'), language);
    await page.locator('#goal-import').setInputFiles(content('invalid.json', {wallet:'invalid'}));
    await page.waitForFunction(lang => document.getElementById('goal-status').textContent.includes(
      lang === 'fr' ? 'Impossible' : 'could not be opened'), language);
    await matchGoal(page, fr ? 'Accorder un harmonica avec de la cire d’abeille' : 'Tune a harmonica reed with beeswax', null);
    assert.match(await page.locator('#goal-status').innerText(), /match|correspondance/i);
  } finally {
    await context.setOffline(false);
  }
  const [viewportWidth, renderedWidth] = await page.evaluate(
    () => [document.documentElement.clientWidth, document.documentElement.scrollWidth]);
  assert.ok(renderedWidth <= viewportWidth);
  return {scriptedMs, saved};
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
    const arrival = await page.locator('#mf-quick-run').boundingBox();
    const goalInput = await page.locator('#goal-text').boundingBox();
    const goalSubmit = await page.locator('#goal-submit').boundingBox();
    const scroll = await page.evaluate(() => scrollY);
    assert.ok(arrival.y >= 0 && arrival.y + arrival.height <= dimensions(width).height,
      `Recommended action beyond the ${language} ${width}px first screen. Scroll ${scroll}, box ${JSON.stringify(arrival)}`);
    assert.ok([goalInput, goalSubmit].every(box => box.y >= 0 && box.y + box.height <= dimensions(width).height));
    const {scriptedMs, saved} = await guidedJourney(page, language, width, started);
    if (language === 'en') {
      await page.locator('#goal-text').fill('');
      await page.locator('#goal-keeper').evaluate(details => { details.open = false; });
      await page.evaluate(() => scrollTo({top:0, behavior:'instant'}));
      await capture(page, language, width, 'arrival-token');
    }
    await page.locator('#open-brief').click();
    await brief.waitFor({ state: 'visible' });
    assert.match(await brief.innerText(), /1\.2/);
    assert.ok(await brief.locator('a').count() > 0);
    const manifest = await memberWorkbench(page, language);
    const admitted = manifest.briefs.find(row => row.id.startsWith('watch-arxiv-'));
    await matchGoal(page, admitted.source_version, admitted.id, 'review');
    assert.equal(admitted.evidence, 'source-identity-only');

    await page.clock.fastForward(301_000);
    await member.waitFor({ state: 'hidden' });
    assert.equal(await brief.textContent(), '');
    assert.equal(await page.locator('#mv-screen-result').textContent(), '');
    assert.equal(await page.locator('#mv-consent').isChecked(), false);
    assert.equal(await page.locator('#goal-text').inputValue(), '');
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
    if (language === 'fr') await capture(page, language, width, 'arrival-club');
    await page.locator('#goal-keeper summary').click();
    await page.locator('#goal-import').setInputFiles(content('recovered.json', saved));
    await page.waitForFunction(() => document.getElementById('goal-result').dataset.record === 'shift-archive-point'
      && !document.getElementById('goal-result').hidden);
    assert.equal(await page.locator('#goal-text').inputValue(), 'NOAA');
    await page.locator('#open-brief').click();
    await brief.waitFor({ state: 'visible' });
    assert.match(await brief.innerText(), /1\.2/);
    assert.equal(await page.locator('#mf-edition').isVisible(), true);
    assert.ok(await page.locator('.mv-timeline a[href^="#decision-watch-"]').count() > 0);
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
      goalAwareRanking:true, savedGoalRecheck:true, liveEvidenceFingerprints:true, restoredAfterSignIn:true,
      offlineRunAndReceipt: true, receiptTamperDenial: true, rehashedReceiptDenial:true,
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
    }
    process.stdout.write(JSON.stringify(checks, null, 2) + '\n');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
