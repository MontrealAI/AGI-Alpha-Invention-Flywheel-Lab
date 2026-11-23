'use strict';

/* Run against the public Pages URLs. Wallet permissions are never requested
   from a real wallet. The provider fixture is isolated to its own browser page. */
const assert = require('node:assert/strict');
const { chromium } = require('playwright-core');

const base = process.env.FRONTIER_BROWSER_URL ??
  'https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/';
const checks = [];

async function publicAtlas(browser, language, width) {
  const path = language === 'fr' ? 'fr.html' : '';
  const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
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
    const viewport = await page.evaluate(() => ({
      width: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
      hasWallet: Boolean(window.ethereum),
      atlasBeforeGate: Boolean(document.getElementById('possibility-shifts').compareDocumentPosition(document.getElementById('access')) & Node.DOCUMENT_POSITION_FOLLOWING),
      anchorIDs: [...document.querySelectorAll('#possibility-shifts [data-atlas-record]')].map(card => card.id)
    }));
    assert.ok(viewport.scroll <= viewport.width);
    assert.equal(viewport.hasWallet, false);
    assert.equal(viewport.atlasBeforeGate, true);
    assert.equal(new Set(viewport.anchorIDs).size, count);

    await page.keyboard.press('Tab');
    assert.match(await page.locator(':focus').getAttribute('href'), /#main$/);
    await page.keyboard.press('Enter');
    assert.equal(await page.locator(':focus').getAttribute('id'), 'main');

    await page.locator('.hero-action').click();
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
    const files = ['atlas-ledger.json', 'atlas-release.json', 'member-brief-001.js'];
    for (const file of files) assert.equal((await page.request.get(base + file)).status(), 200);
    assert.deepEqual(errors, []);
    checks.push({ kind: 'public', language, viewport: width, redirect: response.url(), records: count,
      keyboard: true, filters: true, evidenceLinks: true });
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
  window.walletScenario = { balance: 1_000_000n, expiration: false, chain: '0x1', methods: [], signed: [] };
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
      if (method === 'eth_requestAccounts' || method === 'eth_accounts') return [account];
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
        if (data.slice(10) !== addressWord(account)) throw Error('Wrong balance account');
        return abi(state.balance * 10n ** 18n);
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

async function walletPaths(browser, language) {
  const page = await browser.newPage({ viewport: { width: 1100, height: 850 }, reducedMotion: 'reduce' });
  try {
    await page.clock.install();
    await page.addInitScript(fakeWallet);
    const response = await page.goto(base + (language === 'fr' ? 'fr.html' : ''));
    assert.equal(response.status(), 200);
    const token = page.locator('[data-connect="token"]');
    const club = page.locator('[data-connect="club"]');
    const member = page.locator('#member');
    const brief = page.locator('#brief-content');
    const denied = language === 'fr' ? /ne satisfait/ : /does not meet/;
    const canceled = language === 'fr' ? /annulée/ : /canceled/;

    await page.evaluate(() => { window.walletScenario.balance = 999_999n; });
    await token.click();
    await page.waitForFunction(regex => new RegExp(regex).test(document.getElementById('status').textContent), denied.source);
    assert.equal(await member.isVisible(), false);

    await page.evaluate(() => { window.walletScenario.balance = 1_000_000n; window.walletScenario.cancel = true; });
    await token.click();
    await page.waitForFunction(regex => new RegExp(regex).test(document.getElementById('status').textContent), canceled.source);
    assert.equal(await member.isVisible(), false);

    await page.evaluate(() => { window.walletScenario.cancel = false; });
    await token.click();
    await member.waitFor({ state: 'visible' });
    await page.locator('#open-brief').click();
    await brief.waitFor({ state: 'visible' });
    assert.match(await brief.innerText(), /1\.2/);
    assert.ok(await brief.locator('a').count() > 0);

    await page.clock.fastForward(301_000);
    await member.waitFor({ state: 'hidden' });
    assert.equal(await brief.textContent(), '');

    await page.locator('#club-label').fill('frontier-check');
    await page.evaluate(() => { window.walletScenario.expiration = true; });
    await club.click();
    await page.waitForFunction(regex => new RegExp(regex).test(document.getElementById('status').textContent), denied.source);
    assert.equal(await member.isVisible(), false);

    await page.evaluate(() => { window.walletScenario.expiration = false; });
    await club.click();
    await member.waitFor({ state: 'visible' });
    await page.locator('#open-brief').click();
    await brief.waitFor({ state: 'visible' });
    assert.match(await brief.innerText(), /1\.2/);
    assert.ok(await page.locator('.member-updates a[href^="#shift-"]').count() > 0);
    assert.ok(await page.locator('.member-updates a[href^="#watch-"]').count() > 0);
    await page.locator('#lock').click();
    await member.waitFor({ state: 'hidden' });
    await club.click();
    await member.waitFor({ state: 'visible' });

    await page.evaluate(() => window.walletScenario.emit('accountsChanged', []));
    await member.waitFor({ state: 'hidden' });
    assert.equal(await brief.textContent(), '');
    const state = await page.evaluate(() => ({
      methods: window.walletScenario.methods, signed: window.walletScenario.signed
    }));
    assert.ok(state.methods.every(m => ['eth_requestAccounts', 'eth_accounts', 'eth_getCode',
      'eth_chainId', 'eth_getBlockByNumber', 'eth_call', 'personal_sign'].includes(m)));
    const messages = state.signed.map(hex => Buffer.from(hex.slice(2), 'hex').toString());
    assert.ok(messages.every(message => message.includes('does not approve a transaction') && message.includes(new URL(base).origin)));
    assert.equal(new Set(messages).size, 3);
    checks.push({ kind: 'member-ui', language, provider: 'isolated declared test wallet',
      eligibleRoutes: ['AGI CLUB', 'AGIALPHA'], rejects: ['under balance', 'expired name', 'canceled signature'],
      brief: '001 v1.2', lock: true, expiry: true, reconnect: true, accountRevocation: true });
  } finally {
    await page.close();
  }
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.FRONTIER_CHROME ?? '/usr/bin/google-chrome' });
  try {
    for (const language of ['en', 'fr']) {
      for (const width of [1280, 390]) await publicAtlas(browser, language, width);
      await walletPaths(browser, language);
    }
    process.stdout.write(JSON.stringify(checks, null, 2) + '\n');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
