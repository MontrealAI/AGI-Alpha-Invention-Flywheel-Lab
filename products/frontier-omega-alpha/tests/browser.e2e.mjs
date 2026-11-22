import assert from 'node:assert/strict';
import { once } from 'node:events';
import { readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { resolve } from 'node:path';
import test from 'node:test';
import AxeBuilder from '@axe-core/playwright';
import { chromium } from 'playwright';
import { getBytes } from 'ethers';
import { createAccessServer } from '../access/server.mjs';
import { fakeMainnet, createWallet, testStore, clubNode, MINIMUM } from './fixtures.mjs';

process.umask(0o077);
const source = new URL('../../../docs/research/frontier-omega-alpha/', import.meta.url);
const files = {
  'index.html': 'text/html; charset=utf-8',
  'fr.html': 'text/html; charset=utf-8',
  'frontier.css': 'text/css',
  'frontier.js': 'text/javascript',
  'decrypt.js': 'text/javascript',
  'carina.webp': 'image/webp'
};

async function setup(t) {
  const { chain, rpcState } = fakeMainnet();
  const { store, wrappingKey, asset } = testStore(t);
  asset();
  let backend;
  const web = createServer((request, response) => {
    if (request.url.startsWith('/v1/')) return backend.emit('request', request, response);
    const list = /^\/(pilot|offline)\/(.*)$/.exec(request.url);
    if (!list || !Object.hasOwn(files, list[2] || 'index.html')) {
      response.writeHead(404);
      return response.end();
    }
    const name = list[2] || 'index.html';
    let data = readFileSync(new URL(name, source));
    if (list[1] === 'pilot' && name.endsWith('.html')) {
      data = data.toString('utf8').replace('name="frontier-api" content=""', 'name="frontier-api" content="same-origin"');
    }
    response.writeHead(200, { 'Content-Type': files[name] });
    return response.end(data);
  });
  web.listen(0, '127.0.0.1');
  await once(web, 'listening');
  const base = 'http://127.0.0.1:' + web.address().port;
  backend = createAccessServer({ siteUrl: base + '/pilot/', localHttp: true, chain, store, wrappingKey });
  backend.listen(0, '127.0.0.1');
  await once(backend, 'listening');
  t.after(() => Promise.all([web, backend].map(server => new Promise(resolveClose => server.close(resolveClose)))));
  const browser = await chromium.launch({ executablePath: process.env.FRONTIER_CHROMIUM || undefined });
  t.after(() => browser.close());
  return { rpcState, base, browser };
}

async function installWallet(page, wallet, chain = '0x1') {
  const calls = [];
  await page.exposeBinding('frontierWallet', async (_, request) => {
    calls.push(request.method);
    if (request.method === 'eth_requestAccounts' || request.method === 'eth_accounts') return [wallet.address];
    if (request.method === 'eth_chainId') return chain;
    if (request.method === 'personal_sign') return wallet.signMessage(getBytes(request.params[0]));
    throw Error('Unpermitted synthetic wallet request: ' + request.method);
  });
  await page.addInitScript(() => {
    const listeners = new Map();
    window.ethereum = {
      request: request => window.frontierWallet(request),
      on: (name, callback) => { listeners.set(name, callback); },
      removeListener: name => { listeners.delete(name); }
    };
    window.frontierWalletEvent = name => listeners.get(name)?.();
  });
  return calls;
}

async function assertAccessibility(page) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
  assert.deepEqual(results.violations.map(({ id, nodes }) => ({ id, nodes: nodes.map(node => node.target) })), []);
}

test('Bilingual landing is responsive, keyboard-accessible and offline without a configured service', async t => {
  const { base, browser } = await setup(t);
  const context = await browser.newContext({ viewport: { width: 1440, height: 980 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  const calls = await installWallet(page, createWallet());
  await page.goto(base + '/offline/');
  await page.getByRole('heading', { name: 'FRONTIER Ω ALPHA' }).waitFor();
  await page.getByRole('button', { name: 'Enter with $AGIALPHA' }).click();
  assert.deepEqual(calls, []);
  assert.match(await page.locator('#status').innerText(), /offline/);
  assert.equal(await page.locator('#member').isVisible(), false);
  await assertAccessibility(page);
  if (process.env.FRONTIER_SCREENSHOT_FILE) {
    await page.screenshot({ path: resolve(process.env.FRONTIER_SCREENSHOT_FILE), fullPage: true });
  }
  await page.getByRole('link', { name: 'Français' }).click();
  assert.equal(await page.locator('html').getAttribute('lang'), 'fr');
  await page.setViewportSize({ width: 360, height: 780 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.getByRole('link', { name: 'Aller au contenu' }).focus();
  await page.keyboard.press('Enter');
  assert.equal(new URL(page.url()).hash, '#main');
  await assertAccessibility(page);
  const wrongNetwork = await context.newPage();
  const wrongCalls = await installWallet(wrongNetwork, createWallet(), '0x89');
  await wrongNetwork.goto(base + '/pilot/fr.html');
  await wrongNetwork.getByRole('button', { name: 'Entrer avec $AGIALPHA' }).click();
  await wrongNetwork.getByText('Passez au réseau principal Ethereum dans votre portefeuille, puis réessayez.').waitFor();
  assert.equal(wrongCalls.includes('personal_sign'), false);
  assert.equal(await wrongNetwork.locator('#member').isVisible(), false);
});

test('AGI Club login opens and decrypts the English research area, then clears it on a wallet change', async t => {
  const { base, browser, rpcState } = await setup(t);
  const wallet = createWallet();
  rpcState.balance = 0n;
  rpcState.owners.set(clubNode('founder-2'), wallet.address);
  const context = await browser.newContext();
  const page = await context.newPage();
  const calls = await installWallet(page, wallet);
  await page.goto(base + '/pilot/');
  await page.getByLabel('Your AGI Club label').fill('founder-2');
  await page.getByRole('button', { name: 'Enter with AGI Club' }).click();
  await page.getByRole('heading', { name: 'Member research' }).waitFor();
  await page.getByRole('button', { name: /synthetic-record/ }).click();
  await page.getByRole('heading', { name: 'Synthetic member record' }).waitFor();
  assert.match(await page.locator('#record').innerText(), /<img src=x>/);
  assert.equal(await page.locator('#record img').count(), 0);
  const browserStorage = await page.evaluate(() => [localStorage.length, sessionStorage.length]);
  assert.deepEqual(browserStorage, [0, 0]);
  assert.deepEqual(new Set(calls), new Set(['eth_requestAccounts', 'eth_accounts', 'eth_chainId', 'personal_sign']));
  await assertAccessibility(page);
  const logout = page.waitForResponse(answer => answer.url().endsWith('/v1/logout'));
  await page.evaluate(() => window.frontierWalletEvent('accountsChanged'));
  assert.equal((await logout).status(), 200);
  assert.equal(await page.locator('#member').isVisible(), false);
  assert.equal(await page.locator('#record').innerText(), '');
  assert.match(await page.locator('#status').innerText(), /wallet account or network changed/);
});

test('French token path denies an insufficient wallet, opens a qualifying wallet, then closes on RPC failure', async t => {
  const { base, browser, rpcState } = await setup(t);
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await installWallet(page, createWallet());
  rpcState.balance = MINIMUM - 1n;
  await page.goto(base + '/pilot/fr.html');
  const access = page.getByRole('button', { name: 'Entrer avec $AGIALPHA' });
  await access.click();
  await page.getByText('Ce portefeuille ne satisfait à aucun des deux critères d’accès vérifiés.').waitFor();
  assert.equal(await page.locator('#member').isVisible(), false);
  rpcState.balance = MINIMUM;
  await access.click();
  await page.getByRole('heading', { name: 'Recherche réservée aux membres' }).waitFor();
  await page.getByRole('button', { name: /synthetic-record/ }).click();
  await page.getByRole('heading', { name: 'Dossier membre synthétique' }).waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await assertAccessibility(page);
  rpcState.outage = true;
  await page.getByRole('button', { name: /synthetic-record/ }).click();
  await page.getByText('La vérification est temporairement indisponible. Le contenu reste verrouillé.').waitFor();
  assert.equal(await page.locator('#member').isVisible(), false);
});
