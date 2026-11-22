import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { once } from 'node:events';
import { getBytes } from 'ethers';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import { advance, initialState } from '../native/issue.mjs';
import { SIGNED_LIBRARY_SCHEMA } from '../native/protocol.mjs';
import { bundleReader } from '../native/stage.mjs';
import { clubNode, createWallet, MINIMUM, WRAPPER } from './fixtures.mjs';
import { assetFor, fixtureChain } from './native-fixtures.mjs';

const pages = new URL('../../../docs/research/frontier-omega-alpha/', import.meta.url);
const mime = {
  'index.html': 'text/html', 'fr.html': 'text/html', 'carina.webp': 'image/webp',
  'frontier.css': 'text/css', 'frontier.js': 'text/javascript', 'decrypt.js': 'text/javascript'
};

async function staged(t) {
  const build = await mkdtemp(join(tmpdir(), 'frontier-native-browser-'));
  t.after(() => rm(build, { recursive: true, force: true }));
  const code = join(build, 'native-runtime.js');
  await bundleReader(code);
  const rpc = fixtureChain();
  const masterKey = randomBytes(32);
  const catalog = [assetFor(masterKey)];
  let state = initialState(rpc.cursor);
  let origin;
  async function publish(signedRequests = []) {
    const result = await advance({ rpc: rpc.rpc, state, catalog, masterKey, signedRequests, readerOrigin: origin });
    state = result.state;
    return result.library;
  }
  await publish();
  const publicHost = createServer((req, res) => {
    if (req.url !== '/library.json') {
      res.writeHead(404);
      return res.end();
    }
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    return res.end(JSON.stringify(state.publication));
  });
  publicHost.listen(0, '127.0.0.1');
  await once(publicHost, 'listening');
  const publicOrigin = 'http://127.0.0.1:' + publicHost.address().port;
  const web = createServer(async (req, res) => {
    const name = req.url === '/' ? 'index.html' : req.url.slice(1);
    if (name === 'native-config.json') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ reader: 'http://127.0.0.1:' + web.address().port + '/',
        data: publicOrigin + '/library.json', loopbackTest: true }));
    }
    if (name === 'native-runtime.js') {
      res.writeHead(200, { 'Content-Type': 'text/javascript' });
      return res.end(await readFile(code));
    }
    if (!Object.hasOwn(mime, name)) {
      res.writeHead(404);
      return res.end();
    }
    let data = await readFile(new URL(name, pages));
    if (name.endsWith('.html')) data = data.toString().replace("connect-src 'self'", "connect-src 'self' " + publicOrigin);
    res.writeHead(200, { 'Content-Type': mime[name] });
    return res.end(data);
  });
  web.listen(0, '127.0.0.1');
  await once(web, 'listening');
  origin = 'http://127.0.0.1:' + web.address().port;
  t.after(() => Promise.all([web, publicHost].map(server => new Promise(resolve => server.close(resolve)))));
  const browser = await chromium.launch({ executablePath: process.env.FRONTIER_CHROMIUM || undefined });
  t.after(() => browser.close());
  return { rpc, publish, browser, origin };
}

async function inject(page, signer, rpc) {
  const calls = [];
  await page.exposeBinding('stagedMetaMask', async (_, request) => {
    const { method, params = [] } = request;
    calls.push(method);
    if (method === 'eth_requestAccounts' || method === 'eth_accounts') return [signer.address];
    if (method === 'personal_sign') {
      assert.equal(params[1], signer.address.toLowerCase());
      return signer.signMessage(getBytes(params[0]));
    }
    return rpc.rpc(method, params);
  });
  await page.addInitScript(() => {
    const listeners = new Map();
    window.ethereum = { isMetaMask: true, request: params => window.stagedMetaMask(params),
      on: (event, callback) => { listeners.set(event, callback); },
      removeListener: event => { listeners.delete(event); } };
    window.testWalletEvent = event => listeners.get(event)?.();
  });
  return calls;
}

for (const language of ['en', 'fr']) {
  test('Isolated ' + language + ' reader decrypts after signed device provisioning with zero wallet writes', async t => {
    const stage = await staged(t);
    const wallet = createWallet();
    const english = language === 'en';
    const context = await stage.browser.newContext({ viewport: { width: english ? 1160 : 390, height: 850 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const calls = await inject(page, wallet, stage.rpc);
    if (english) {
      stage.rpc.balances.set(wallet.address.toLowerCase(), MINIMUM);
    } else {
      stage.rpc.balances.set(wallet.address.toLowerCase(), 0n);
      const node = clubNode('membre-1');
      stage.rpc.rpcState.owners.set(node, WRAPPER);
      stage.rpc.rpcState.wrapped.set(node, {
        owner: wallet.address,
        fuses: 1 << 16,
        expiry: BigInt(Math.floor(Date.now() / 1000) + 3600)
      });
    }
    await page.goto(stage.origin + (english ? '/' : '/fr.html'));
    async function enter() {
      if (!english) await page.getByLabel('Votre identifiant AGI Club').fill('membre-1');
      await page.getByRole('button', { name: english ? 'Enter with $AGIALPHA' : 'Entrer avec AGI Club' }).click();
    }
    await enter();
    const confirm = page.getByRole('button', { name: english ? 'Sign in MetaMask' : 'Signer dans MetaMask' });
    await confirm.waitFor();
    assert.equal(calls.includes('eth_sendTransaction'), false);
    assert.match(await page.locator('#native-controls').innerText(), english ? /uses no gas/ : /sans frais de gaz/);
    assert.equal(await page.locator('#member').isVisible(), false);
    const axe = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze();
    assert.deepEqual(axe.violations.map(({ id, nodes }) => [id, nodes.map(x => x.target)]), []);
    await confirm.click();
    const downloadButton = page.getByRole('button', { name: english ? 'Download signed request' : 'Télécharger la demande signée' });
    const [download] = await Promise.all([page.waitForEvent('download'), downloadButton.click()]);
    const request = JSON.parse(await readFile(await download.path(), 'utf8'));
    const refresh = page.getByRole('button', { name: english ? 'Check status now' : 'Vérifier maintenant' });
    await refresh.click();
    await page.getByText(english ? /Signed request ready/ : /La demande signée est prête/).waitFor();
    const encrypted = await stage.publish([request]);
    assert.equal(encrypted.schema, SIGNED_LIBRARY_SCHEMA);
    assert.equal(JSON.stringify(encrypted).includes('Synthetic member record'), false);
    assert.deepEqual(Object.values(encrypted.recipients).map(record => record.state), ['provisioned']);
    await refresh.click();
    const title = page.getByRole('heading', { name: english ? 'Member research' : 'Recherche réservée aux membres' });
    await title.waitFor();
    await page.getByRole('button', { name: /synthetic-lab/ }).click();
    await page.getByRole('heading', { name: english ? 'Synthetic member record' : 'Dossier membre synthétique' }).waitFor();
    assert.equal(await page.locator('#record img').count(), 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.reload();
    await enter();
    await title.waitFor();
    assert.equal(calls.filter(method => method === 'personal_sign').length, 1);
    assert.equal(calls.some(method => /sendTransaction|estimateGas|maxPriorityFeePerGas/.test(method)), false);
    await page.evaluate(() => window.testWalletEvent('accountsChanged'));
    assert.equal(await page.locator('#member').isVisible(), false);
    assert.deepEqual(errors, []);
  });
}

test('An ineligible MetaMask account receives no signature or wallet transaction request', async t => {
  const stage = await staged(t);
  const wallet = createWallet();
  stage.rpc.balances.set(wallet.address.toLowerCase(), MINIMUM - 1n);
  const context = await stage.browser.newContext();
  const page = await context.newPage();
  const calls = await inject(page, wallet, stage.rpc);
  await page.goto(stage.origin + '/');
  await page.getByRole('button', { name: 'Enter with $AGIALPHA' }).click();
  await page.getByText(/does not meet the verified AGI Club/).waitFor();
  assert.equal(calls.includes('eth_sendTransaction'), false);
  assert.equal(calls.includes('personal_sign'), false);
  assert.equal(calls.includes('eth_estimateGas'), false);
  assert.equal(await page.locator('#member').isVisible(), false);
});
