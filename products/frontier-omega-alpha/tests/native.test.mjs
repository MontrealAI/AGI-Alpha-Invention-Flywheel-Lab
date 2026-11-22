import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { decryptAsset } from '../access/crypto.mjs';
import { scanEnrollments } from '../native/intake.mjs';
import { advance, initialState } from '../native/issue.mjs';
import { assertLibrary, bytes, decodeEnrollment, DESTINATION, encodeEnrollment, enrollmentId, hex } from '../native/protocol.mjs';
import { decapsulate, makeDeviceKey, suite } from '../native/hpke.mjs';
import { openState, sealState } from '../native/state.mjs';
import { readerAddress, stagePublic, stageReader } from '../native/stage.mjs';
import { createWallet, clubNode, memberRecord, MINIMUM } from './fixtures.mjs';
import { assetFor, createEnrollment, fixtureChain, signEnrollment } from './native-fixtures.mjs';

test('RFC 9180 interoperability with the CFRG P-256 / HKDF-SHA256 / AES-256-GCM vector', async () => {
  const v = JSON.parse(await readFile(new URL('./hpke-cfrg-p256.json', import.meta.url), 'utf8'));
  const decode = value => bytes('0x' + value);
  const key = await suite.kem.deserializePrivateKey(decode(v.skRm));
  const recipient = await suite.createRecipientContext({ recipientKey: key, enc: decode(v.enc), info: decode(v.info) });
  assert.equal(hex(new Uint8Array(await recipient.open(decode(v.ct), decode(v.aad)))), '0x' + v.pt);
});

test('Finalized intake verifies raw signing, bound wallet, destination, value and controls bounded recovery', async () => {
  const f = fixtureChain();
  const member = createWallet();
  const forged = await createEnrollment(createWallet(), { wallet: member.address });
  const eligible = await createEnrollment(member, { label: 'member-one' });
  const invalid = await signEnrollment(member, { data: encodeEnrollment(eligible.info), nonce: 1, value: 1n });
  const signatureMismatch = await createEnrollment(member, { txNonce: 2 });
  const expired = await createEnrollment(member, { txNonce: 3, expiresAt: Math.floor(Date.now()/1_000) - 1_000 });
  const [_, tx] = await f.mine([forged.raw, eligible.raw, invalid, signatureMismatch.raw, expired.raw]);
  f.receipts.get(signatureMismatch.tx).status = '0x0';

  const first = await scanEnrollments(f.rpc, f.cursor, { signals: 1 });
  assert.equal(first.events.length, 0, 'wallet in calldata is not evidence of sender control');
  assert.equal(first.cursor.offset, 1);
  const next = await scanEnrollments(f.rpc, first.cursor);
  assert.equal(next.caughtUp, true);
  assert.deepEqual(next.events.map(event => event.tx), [tx]);
  assert.deepEqual(decodeEnrollment(encodeEnrollment(eligible.info)), eligible.info);
  assert.equal(decodeEnrollment(encodeEnrollment(eligible.info)).label, 'member-one');
  await assert.rejects(scanEnrollments(f.rpc, { ...f.cursor, hash: '0x' + '01'.repeat(32) }), /checkpoint changed/);
  f.rpcState.chainId = '0x2';
  await assert.rejects(scanEnrollments(f.rpc, f.cursor), /Mainnet/);
});

test('Issuer enforces independent eligibility, envelopes, nonce idempotency, loss, key rotation and sealed recovery', async () => {
  const f = fixtureChain();
  const key = randomBytes(32);
  const catalog = [assetFor(key)];
  const tokenWallet = createWallet();
  const clubWallet = createWallet();
  const outside = createWallet();
  f.balances.set(clubWallet.address.toLowerCase(), 0n);
  f.balances.set(tokenWallet.address.toLowerCase(), MINIMUM);
  f.balances.set(outside.address.toLowerCase(), MINIMUM - 1n);
  f.rpcState.owners.set(clubNode('owner-1'), clubWallet.address);

  const enrollments = await Promise.all([
    createEnrollment(tokenWallet),
    createEnrollment(clubWallet, { label: 'owner-1' }),
    createEnrollment(outside, { label: 'fake' })
  ]);
  await f.mine(enrollments.map(x => x.raw));
  const issue = (state, releases = catalog, revoked = []) => advance({ rpc: f.rpc, state, catalog: releases, revoked, masterKey: key });
  const first = await issue(initialState(f.cursor));
  const ids = await Promise.all(enrollments.map(x => enrollmentId(x.info.wallet, x.info.nonce)));
  assert.deepEqual(ids.map(id => first.library.recipients[id].state), ['provisioned', 'provisioned', 'denied']);
  const record = first.library.records[0];
  const [token, club] = ids.map(id => first.library.recipients[id]);
  for (const [index, recipient] of [token, club].entries()) {
    const device = enrollments[index].device;
    assert.equal(device.privateKey.extractable, false);
    const cek = await decapsulate(device, recipient.keys[record.tag], recipient.tx, record.tag);
    assert.deepEqual(JSON.parse(decryptAsset(record, cek)), memberRecord);
    cek.fill(0);
    await assert.rejects(decapsulate(await makeDeviceKey(), recipient.keys[record.tag], recipient.tx, record.tag));
    await assert.rejects(decapsulate(device, recipient.keys[record.tag], '0x' + 'fe'.repeat(32), record.tag));
  }
  const published = JSON.stringify(first.library);
  assert.ok(!published.includes(memberRecord.en.title));
  assert.ok(!published.includes(catalog[0].wrapped.body));
  assert.throws(() => assertLibrary({ ...first.library, records: [{ ...record, wrapped: catalog[0].wrapped }] }));
  const stateBlob = sealState(first.state, key);
  assert.deepEqual(openState(stateBlob, key), first.state);
  assert.throws(() => openState(stateBlob, randomBytes(32)));
  assert.ok(!JSON.stringify(stateBlob).includes(tokenWallet.address.toLowerCase()));

  const repeated = await signEnrollment(tokenWallet, { data: encodeEnrollment(enrollments[0].info), nonce: 5 });
  await f.mine([repeated]);
  const replay = await issue(first.state);
  assert.equal(replay.changed, false);
  assert.equal(replay.library.recipients[ids[0]].tx, token.tx);
  f.balances.set(tokenWallet.address.toLowerCase(), MINIMUM - 1n);
  const secondVersion = [assetFor(key, 2)];
  const rotated = await issue(replay.state, secondVersion);
  assert.deepEqual(rotated.library.recipients[ids[0]], { tx: token.tx, state: 'revoked', keys: {} });
  assert.equal(rotated.library.recipients[ids[1]].state, 'provisioned');
  assert.equal(rotated.library.records[0].version, 2);
  assert.notEqual(rotated.library.records[0].tag, record.tag);
  await assert.rejects(issue(rotated.state, [assetFor(key, 2)]), /cannot be replaced/);

  const revoked = await issue(rotated.state, secondVersion, [ids[1]]);
  assert.equal(revoked.library.recipients[ids[1]].state, 'revoked');
  assert.deepEqual(revoked.library.recipients[ids[1]].keys, {});
  f.rpcState.outage = true;
  await assert.rejects(issue(rotated.state, secondVersion), /Synthetic RPC outage|cannot be replaced/);
  assert.equal(rotated.library.recipients[ids[0]].state, 'revoked');
});

test('Pages staging publishes only ciphertext and isolated reader assets', async t => {
  const root = await mkdtemp(join(tmpdir(), 'frontier-native-test-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const f = fixtureChain();
  const masterKey = randomBytes(32);
  const result = await advance({ rpc: f.rpc, state: initialState(f.cursor), catalog: [assetFor(masterKey)], masterKey });
  const file = join(root, 'snapshot.json');
  await writeFile(file, JSON.stringify(result.library));
  const publicPage = join(root, 'frontier-omega-alpha');
  await mkdir(publicPage);
  const trusted = 'https://frontier-demo.example.org/';
  await stagePublic(publicPage, file, trusted);
  assert.deepEqual((await readdir(publicPage)).sort(), ['library.json', 'native-config.json']);
  assert.throws(() => readerAddress('https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/'));
  assert.throws(() => readerAddress('http://frontier-demo.example.org/'));
  const reader = join(root, 'reader');
  await stageReader(reader, trusted);
  const files = (await readdir(reader)).sort();
  assert.deepEqual(files, ['.nojekyll','carina.webp','decrypt.js','fr.html','frontier.css','frontier.js',
    'index.html','native-config.json','native-runtime.js']);
  assert.ok((await readFile(join(reader, 'index.html'), 'utf8')).includes("connect-src 'self' https://montrealai.github.io"));
  assert.ok(!(await readFile(join(reader, 'native-runtime.js'), 'utf8')).includes('sourceMappingURL='));
  const tampered = structuredClone(result.library);
  tampered.records[0].tag = '0x' + 'bb'.repeat(32);
  await writeFile(file, JSON.stringify(tampered));
  await assert.rejects(stagePublic(publicPage, file, trusted), /release digest/);
});
