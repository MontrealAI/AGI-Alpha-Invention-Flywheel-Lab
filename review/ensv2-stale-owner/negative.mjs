import test from 'node:test';
import assert from 'node:assert/strict';
import { Interface } from 'ethers';
import { Mainnet, REGISTRY, clubNode } from '../access/chain.mjs';

// Synthetic protocol counterexample ONLY, not a live ENSv2 read,
// nor evidence that any particular AGI Club name has migrated.
const ownerAbi = new Interface(['function owner(bytes32) view returns (address)']);
const label = 'synthetic-stale-ens';
const oldOwner = '0x1111111111111111111111111111111111111111';
const newOwner = '0x2222222222222222222222222222222222222222';
const fixed = { ref: { blockHash: '0x' + '55'.repeat(32), requireCanonical: true }, timestamp: 1800000000 };

function legacyRpc(log) {
  return async (method, params) => {
    log.push({method, params});
    assert.equal(method, 'eth_call');
    assert.equal(params.length, 2);
    assert.deepEqual(params[1], fixed.ref);
    const [call] = params;
    assert.equal(call.to.toLowerCase(), REGISTRY.toLowerCase());
    const decoded = ownerAbi.parseTransaction({ data: call.data });
    assert.equal(decoded.name, 'owner');
    assert.equal(decoded.args[0].toLowerCase(), clubNode(label).toLowerCase());
    return ownerAbi.encodeFunctionResult('owner', [oldOwner]);
  };
}

test('REGISTERED v2 owner B differing from legacy v1 owner A is ignored by v1-only Club check', async () => {
  const hypotheticalMigration = Object.freeze({ status: 2, owner: newOwner });
  assert.equal(hypotheticalMigration.status, 2);
  const calls = [];
  const mainnet = new Mainnet(legacyRpc(calls), () => fixed.timestamp * 1000);
  assert.equal(await mainnet.ownsClub(oldOwner, label, fixed), true,
    'v1-only implementation still grants stale v1 owner A');
  assert.equal(await mainnet.ownsClub(newOwner, label, fixed), false,
    'v1-only implementation denies hypothetical current v2 owner B');
  assert.equal(calls.length, 2);
  assert.ok(calls.every(x => x.params[0].to.toLowerCase() === REGISTRY.toLowerCase()),
    'no v2 registry ownership or migration-status call');
});

test('RESERVED v2 name with unmigrated v1 owner A is legitimate compatibility control', async () => {
  const hypotheticalReservation = Object.freeze({ status: 1, owner: null });
  assert.equal(hypotheticalReservation.status, 1);
  const calls = [];
  const mainnet = new Mainnet(legacyRpc(calls), () => fixed.timestamp * 1000);
  assert.equal(await mainnet.ownsClub(oldOwner, label, fixed), true);
  assert.equal(calls.length, 1);
});
