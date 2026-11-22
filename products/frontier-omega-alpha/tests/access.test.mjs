import assert from 'node:assert/strict';
import test from 'node:test';
import { randomBytes } from 'node:crypto';
import { once } from 'node:events';
import { getAddress, hashMessage, namehash } from 'ethers';
import { SiweMessage } from 'siwe';
import { createAccessServer } from '../access/server.mjs';
import { releaseKey, rotateAsset } from '../access/crypto.mjs';
import { decryptRelease } from '../../../docs/research/frontier-omega-alpha/decrypt.js';
import { fakeMainnet, testStore, createWallet, memberRecord, clubNode, MINIMUM, WRAPPER } from './fixtures.mjs';

process.umask(0o077);
const origin = 'https://research.example.test';
const siteUrl = origin + '/frontier-omega-alpha/';

async function setup(t) {
  let time = Date.now();
  const clock = () => time;
  const { chain, rpcState } = fakeMainnet(clock);
  const { store, wrappingKey, asset } = testStore(t);
  const server = createAccessServer({ siteUrl, chain, store, wrappingKey, clock });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const target = 'http://127.0.0.1:' + server.address().port;
  t.after(() => new Promise(resolve => server.close(resolve)));
  const post = async (route, body, token, requestOrigin = origin) => {
    const headers = { Origin: requestOrigin, 'Content-Type': 'application/json' };
    if (token) headers.Authorization = 'Bearer ' + token;
    const result = await fetch(target + '/v1/' + route, { method: 'POST', body: JSON.stringify(body), headers });
    return { status: result.status, body: await result.json(), headers: result.headers };
  };
  const challenge = async (address, label = null, language = 'en') => {
    const response = await post('challenge', { address, label, language });
    assert.equal(response.status, 200, JSON.stringify(response.body));
    return response.body;
  };
  const login = async (wallet, label = null) => {
    const { nonce, message } = await challenge(wallet.address, label);
    return post('verify', { nonce, signature: await wallet.signMessage(message) });
  };
  return { post, challenge, login, store, wrappingKey, asset, rpcState, clock, advance: milliseconds => { time += milliseconds; } };
}

test('ENSv1 Registry verifies an unwrapped Club name and revokes the former owner after transfer', async t => {
  const s = await setup(t);
  const wallet = createWallet();
  assert.equal(clubNode(' MEMBER-2 '), namehash('member-2.club.agi.eth'));
  s.rpcState.balance = 0n;
  s.rpcState.owners.set(clubNode('member-2'), wallet.address);
  const { body, status } = await s.login(wallet, ' MEMBER-2 ');
  assert.equal(status, 200);
  assert.equal(body.path, 'club');
  assert.equal((await s.login(wallet, 'member-3')).status, 403);
  const forged = await s.post('challenge', { address: wallet.address, label: 'member-2.club.agi.eth', language: 'en' });
  assert.equal(forged.status, 400);
  const transferee = createWallet();
  s.rpcState.owners.set(clubNode('member-2'), transferee.address);
  assert.equal((await s.post('catalog', {}, body.token)).status, 403);
  assert.equal((await s.post('catalog', {}, body.token)).status, 401);
  assert.equal((await s.login(transferee, 'member-2')).body.path, 'club');
});

test('ENSv1 Name Wrapper verifies the owner, follows a transfer and expires an emancipated subname', async t => {
  const s = await setup(t);
  s.rpcState.balance = 0n;
  const wallet = createWallet();
  const label = 'wrapped';
  const node = clubNode(label);
  s.rpcState.owners.set(node, WRAPPER);
  s.rpcState.wrapped.set(node, { owner: wallet.address, fuses: 1 << 16, expiry: BigInt(Math.floor(s.clock() / 1000) + 60) });
  const access = await s.login(wallet, label);
  assert.equal(access.status, 200);
  s.rpcState.wrapped.get(node).recordedOwner = createWallet().address;
  assert.equal((await s.login(wallet, label)).status, 403);
  delete s.rpcState.wrapped.get(node).recordedOwner;
  const transferee = createWallet();
  s.rpcState.wrapped.get(node).owner = transferee.address;
  assert.equal((await s.post('session', {}, access.body.token)).status, 403);
  const transferred = await s.login(transferee, label);
  assert.equal(transferred.body.path, 'club');
  s.advance(60_000);
  assert.equal((await s.post('session', {}, transferred.body.token)).status, 403);
  s.rpcState.owners.set(node, transferee.address);
  assert.equal((await s.login(wallet, label)).status, 403);
  assert.equal((await s.login(transferee, label)).body.path, 'club');
});

test('ENSv1 wrapped subname subject to parental control keeps its owner when temporary fuses expire', async t => {
  const s = await setup(t);
  s.rpcState.balance = 0n;
  const wallet = createWallet();
  const node = clubNode('legacy');
  s.rpcState.owners.set(node, WRAPPER);
  const now = BigInt(Math.floor(s.clock() / 1000));
  s.rpcState.wrapped.set(node, { owner: wallet.address, expiry: now - 1n });
  assert.equal((await s.login(wallet, 'legacy')).body.path, 'club');
  s.rpcState.wrapped.get(node).expiry = 0n;
  assert.equal((await s.login(wallet, 'legacy')).body.path, 'club');
  s.rpcState.owners.delete(node);
  assert.equal((await s.login(wallet, 'legacy')).status, 403);
});

test('Token eligibility accepts integer equality and surplus, independently of Club', async t => {
  const s = await setup(t);
  const wallet = createWallet();
  assert.equal((await s.login(wallet)).body.path, 'token');
  s.rpcState.balance = MINIMUM + 1n;
  const access = await s.login(wallet, 'unowned-label');
  assert.equal(access.body.path, 'token');
  s.rpcState.balance = MINIMUM - 1n;
  assert.equal((await s.login(wallet)).status, 403);
  assert.equal((await s.post('catalog', {}, access.body.token)).status, 403);
});

test('Rejects wrong chain, unknown token deployment, changed decimals, stale and noncanonical blocks', async t => {
  const s = await setup(t);
  const wallet = createWallet();
  const cases = [['chainId', '0x89'], ['decimals', 6n], ['symbol', 'FAKE'], ['tokenCode', '0x'], ['age', 91], ['canonical', false]];
  for (const [key, invalid] of cases) {
    const value = s.rpcState[key];
    s.rpcState[key] = invalid;
    assert.equal((await s.login(wallet)).status, 503, key);
    s.rpcState[key] = value;
  }
  const label = 'member';
  s.rpcState.owners.set(clubNode(label), wallet.address);
  s.rpcState.decimals = 6n;
  assert.equal((await s.login(wallet, label)).body.path, 'club', 'A separately verified path remains valid');
});

test('SIWE binds exact wallet, origin, domain, URI, mainnet, label, nonce, and expiry', async t => {
  const s = await setup(t);
  const wallet = createWallet();
  const ch = await s.challenge(wallet.address, 'name', 'fr');
  const parsed = new SiweMessage(ch.message);
  assert.equal(parsed.domain, 'research.example.test');
  assert.equal(parsed.scheme, 'https');
  assert.equal(parsed.uri, siteUrl);
  assert.equal(parsed.chainId, 1);
  assert.equal(parsed.address, wallet.address);
  assert.equal(parsed.nonce, ch.nonce);
  assert.deepEqual(parsed.resources, ['urn:frontier-omega-alpha:club:name.club.agi.eth']);
  assert.match(parsed.statement, /Connectez-vous/);

  const signature = await wallet.signMessage(ch.message);
  assert.equal((await s.post('verify', { nonce: ch.nonce, signature }, null, 'https://elsewhere.example')).status, 403);
  const concurrent = await Promise.all([s.post('verify', { nonce: ch.nonce, signature }), s.post('verify', { nonce: ch.nonce, signature })]);
  assert.deepEqual(concurrent.map(result => result.status).sort(), [200, 401]);
  for (const transformation of [
    m => m.replaceAll('research.example.test', 'other.example.test'),
    m => m.replace('Chain ID: 1', 'Chain ID: 10'),
    m => m.replace('name.club.agi.eth', 'other.club.agi.eth')
  ]) {
    const next = await s.challenge(wallet.address, 'name');
    assert.equal((await s.post('verify', { nonce: next.nonce, signature: await wallet.signMessage(transformation(next.message)) })).status, 401);
  }
  const next = await s.challenge(wallet.address);
  assert.equal((await s.post('verify', { nonce: next.nonce, signature: await createWallet().signMessage(next.message) })).status, 401);
  const expired = await s.challenge(wallet.address);
  s.advance(120_000);
  assert.equal((await s.post('verify', { nonce: expired.nonce, signature: await wallet.signMessage(expired.message) })).status, 401);
});

test('Validates deployed ERC-1271 wallet signatures and rechecks current contract authority', async t => {
  const s = await setup(t);
  const contract = getAddress('0x0000000000000000000000000000000000001271');
  const { nonce, message } = await s.challenge(contract);
  s.rpcState.contract = contract;
  s.rpcState.signatureValid = ([hash, signature]) => hash === hashMessage(message) && signature === '0x1234';
  const access = await s.post('verify', { nonce, signature: '0x1234' });
  assert.equal(access.status, 200);
  assert.equal((await s.post('session', {}, access.body.token)).status, 200);
  s.rpcState.signatureValid = () => false;
  assert.equal((await s.post('session', {}, access.body.token)).status, 403);
});

test('Protected release requires a current session and returns only the requested content key', async t => {
  const s = await setup(t);
  const request = { id: 'synthetic-record', version: 1 };
  const box = s.asset();
  const second = s.asset('synthetic-record', 2);
  const payload = { ...box };
  delete payload.wrapped;
  const denied = await s.post('open', request);
  assert.equal(denied.status, 401);
  assert.equal(Object.hasOwn(denied.body, 'key'), false);
  await assert.rejects(decryptRelease(payload, randomBytes(32).toString('base64url'), request));
  const access = await s.login(createWallet());
  const catalog = await s.post('catalog', {}, access.body.token);
  assert.equal(catalog.body.entries.length, 2);
  assert.equal(JSON.stringify(catalog.body).includes(memberRecord.en.title), false);
  assert.equal((await s.post('open', { id: 'guessed', version: 1 }, access.body.token)).status, 404);
  const result = await s.post('open', request, access.body.token);
  assert.equal(result.status, 200);
  assert.equal(result.headers.get('cache-control'), 'no-store, private, max-age=0');
  assert.equal(result.headers.get('access-control-allow-origin'), origin);
  assert.equal(result.headers.get('set-cookie'), null);
  assert.equal(Object.hasOwn(result.body.ciphertext, 'wrapped'), false);
  assert.equal(JSON.stringify(result.body).includes(memberRecord.en.title), false);
  assert.deepEqual(await decryptRelease(result.body.ciphertext, result.body.key, request), memberRecord);
  const other = { ...second };
  delete other.wrapped;
  await assert.rejects(decryptRelease(other, result.body.key, { id: 'synthetic-record', version: 2 }));
  const tampered = structuredClone(result.body.ciphertext);
  const bytes = Buffer.from(tampered.payload.body, 'base64url');
  bytes[0] ^= 1;
  tampered.payload.body = bytes.toString('base64url');
  await assert.rejects(decryptRelease(tampered, result.body.key, request));
  await assert.rejects(decryptRelease({ ...result.body.ciphertext, epoch: 'ff'.repeat(16) }, result.body.key, request));
  s.advance(5 * 60_000);
  assert.equal((await s.post('open', request, access.body.token)).status, 401);
});

test('Server delivery never sends key and outage, logout, withdrawal and rotation fail closed', async t => {
  const s = await setup(t);
  s.asset('server-only', 1, 'server');
  s.asset();
  const wallet = createWallet();
  const { body: { token } } = await s.login(wallet);
  const serverDelivery = await s.post('open', { id: 'server-only', version: 1 }, token);
  assert.equal(serverDelivery.status, 200);
  assert.deepEqual(serverDelivery.body.record, memberRecord);
  assert.equal(Object.hasOwn(serverDelivery.body, 'key'), false);
  s.rpcState.outage = true;
  assert.equal((await s.post('open', { id: 'synthetic-record', version: 1 }, token)).status, 503);
  s.rpcState.outage = false;
  assert.equal((await s.post('logout', {}, token)).status, 200);
  assert.equal((await s.post('catalog', {}, token)).status, 401);
  const fresh = await s.login(wallet);
  s.store.withdraw('server-only', 1);
  assert.equal((await s.post('open', { id: 'server-only', version: 1 }, fresh.body.token)).status, 404);

  const next = { epoch: randomBytes(16).toString('hex'), key: randomBytes(32) };
  const original = s.store.asset('synthetic-record', 1, s.wrappingKey.epoch);
  const oldKey = releaseKey(original, s.wrappingKey.key).toString('base64url');
  s.store.rotate(s.wrappingKey.epoch, next.epoch,
    envelope => rotateAsset(envelope, s.wrappingKey.key, next.key, next.epoch));
  assert.equal((await s.post('catalog', {}, fresh.body.token)).status, 401);
  assert.equal(s.store.asset('synthetic-record', 1, s.wrappingKey.epoch), null);
  const rotated = s.store.asset('synthetic-record', 1, next.epoch);
  const newKey = releaseKey(rotated, next.key).toString('base64url');
  assert.notEqual(newKey, oldKey);
  assert.deepEqual(await decryptRelease(rotated, newKey, rotated), memberRecord);
  await assert.rejects(decryptRelease(rotated, oldKey, rotated));
});

test('Anonymous and unknown API routes expose no research, and auth flood is limited', async t => {
  const s = await setup(t);
  s.asset();
  assert.equal((await s.post('admin', {})).status, 404);
  assert.equal((await s.post('catalog', {})).status, 401);
  assert.equal((await s.post('catalog', {}, 'ab'.repeat(32), 'null')).status, 403);
  const address = createWallet().address;
  for (let count = 0; count < 40; count++) await s.challenge(address);
  assert.equal((await s.post('challenge', { address, label: null, language: 'en' })).status, 429);
});

test('An operator revocation during a protected RPC read prevents key release', async t => {
  const s = await setup(t);
  s.asset();
  const contract = getAddress('0x0000000000000000000000000000000000001271');
  s.rpcState.contract = contract;
  s.rpcState.signatureValid = () => true;
  const { nonce } = await s.challenge(contract);
  const { body } = await s.post('verify', { nonce, signature: '0x1234' });
  assert.ok(body.token);
  let entered;
  let finish;
  const reading = new Promise(resolve => { entered = resolve; });
  const answer = new Promise(resolve => { finish = resolve; });
  s.rpcState.signatureValid = () => {
    entered();
    return answer;
  };
  const request = s.post('open', { id: 'synthetic-record', version: 1 }, body.token);
  await reading;
  s.store.revokeAll();
  finish(true);
  const result = await request;
  assert.equal(result.status, 401);
  assert.equal(Object.hasOwn(result.body, 'key'), false);
});
