import assert from 'node:assert/strict';
import test from 'node:test';
import { randomBytes } from 'node:crypto';
import { SiweMessage } from 'siwe';
import { advance, initialState } from '../native/issue.mjs';
import { enrollmentId, SIGNED_LIBRARY_SCHEMA } from '../native/protocol.mjs';
import { openEnrollments, openState, sealEnrollments, sealState } from '../native/state.mjs';
import { authenticateSignedEnrollment, makeSignedEnrollment, signedEnrollmentMessage } from '../native/signed-enrollment.mjs';
import { decapsulate, encapsulate, makeDeviceKey, validatePublicKey } from '../native/hpke.mjs';
import { clubNode, createWallet, fakeMainnet, MINIMUM, WRAPPER } from './fixtures.mjs';
import { assetFor, fixtureChain } from './native-fixtures.mjs';

const origin = 'https://frontier-research.example.com';
const second = 1_795_385_000;

async function enrollment(signer, label = null) {
  const device = await makeDeviceKey();
  const request = makeSignedEnrollment({
    origin, issuedAt: second, expiresAt: second + 90, wallet: signer.address.toLowerCase(),
    nonce: '0x' + randomBytes(16).toString('hex'), publicKey: device.publicKey, label
  });
  const message = signedEnrollmentMessage(request, origin);
  const parsed = new SiweMessage(message);
  assert.equal(parsed.prepareMessage(), message);
  assert.equal(parsed.address, signer.address);
  assert.equal(parsed.chainId, 1);
  return { request: { ...request, signature: await signer.signMessage(message) }, device };
}

test('An off-chain MetaMask-style signature binds an ENSv1 wrapped owner to one encrypted device', async () => {
  const owner = createWallet();
  const { chain, rpcState } = fakeMainnet(() => second * 1000);
  const { request, device } = await enrollment(owner, 'member');
  const node = clubNode('member');
  rpcState.owners.set(node, WRAPPER);
  rpcState.wrapped.set(node, { owner: owner.address, fuses: 1 << 16, expiry: BigInt(second + 60) });
  rpcState.balance = 0n;
  const snapshot = await chain.snapshot();
  const accepted = await authenticateSignedEnrollment(request, origin, chain, snapshot);
  assert.equal(accepted.wallet, owner.address.toLowerCase());
  const clear = randomBytes(32);
  const tag = '0x' + randomBytes(32).toString('hex');
  const box = await encapsulate(await validatePublicKey(accepted.publicKey), clear, accepted.proof, tag);
  assert.deepEqual(Buffer.from(await decapsulate(device, box, accepted.proof, tag)), clear);
  await assert.rejects(async () => decapsulate(await makeDeviceKey(), box, accepted.proof, tag));
  rpcState.wrapped.get(node).owner = createWallet().address;
  assert.equal(await authenticateSignedEnrollment(request, origin, chain, snapshot), null);
});

test('The standalone token eligibility path rejects signature, origin, device, expiry and balance changes', async () => {
  const owner = createWallet();
  let time = second;
  const { chain, rpcState } = fakeMainnet(() => time * 1000);
  const { request } = await enrollment(owner);
  const original = await chain.snapshot();
  assert.ok(await authenticateSignedEnrollment(request, origin, chain, original));
  await assert.rejects(authenticateSignedEnrollment(request, 'https://other.example.com', chain, original));
  const different = await enrollment(owner);
  const rebinding = { ...request, enrollment: different.request.enrollment };
  assert.equal(await authenticateSignedEnrollment(rebinding, origin, chain, original), null);
  const signature = await createWallet().signMessage(signedEnrollmentMessage(request, origin));
  assert.equal(await authenticateSignedEnrollment({ ...request, signature }, origin, chain, original), null);
  rpcState.balance = MINIMUM - 1n;
  assert.equal(await authenticateSignedEnrollment(request, origin, chain, original), null);
  rpcState.balance = MINIMUM;
  time += 90;
  assert.equal(await authenticateSignedEnrollment(request, origin, chain, await chain.snapshot()), null);
});

test('Publisher opens only the sealed approved batch, deduplicates it and revokes future delivery', async () => {
  const owner = createWallet();
  const { request, device } = await enrollment(owner);
  const now = () => second * 1000;
  const f = fixtureChain(now);
  const key = randomBytes(32);
  const sealed = sealEnrollments([request], key);
  assert.equal(JSON.stringify(sealed).includes(request.signature), false);
  assert.deepEqual(openEnrollments(sealed, key), [request]);
  assert.throws(() => openEnrollments(sealed, randomBytes(32)));
  const run = state => advance({
    rpc: f.rpc, state, catalog, masterKey: key, now,
    signedRequests: openEnrollments(sealed, key), readerOrigin: origin
  });
  const catalog = [assetFor(key)];
  const approved = await run(initialState(f.cursor));
  assert.equal(approved.library.schema, SIGNED_LIBRARY_SCHEMA);
  const member = Object.values(approved.state.active)[0];
  const id = await enrollmentId(member.wallet, member.nonce);
  const receipt = approved.library.recipients[id];
  assert.equal(receipt.state, 'provisioned');
  assert.equal(Object.hasOwn(receipt, 'tx'), false);
  const record = approved.library.records[0];
  const delivered = await decapsulate(device, receipt.keys[record.tag], receipt.proof, record.tag, approved.library.schema);
  assert.equal(delivered.length, 32);
  delivered.fill(0);
  const restored = openState(sealState(approved.state, key), key, approved.library);
  assert.equal((await run(restored)).changed, false);
  f.rpcState.balance = MINIMUM - 1n;
  assert.deepEqual((await run(restored)).library.recipients[id], { proof: receipt.proof, state: 'revoked', keys: {} });
});
