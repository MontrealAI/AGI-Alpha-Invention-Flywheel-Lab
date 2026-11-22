import { Interface, Wallet, ZeroAddress } from 'ethers';
import { randomBytes } from 'node:crypto';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Mainnet, TOKEN, MINIMUM, REGISTRY, WRAPPER, clubNode } from '../access/chain.mjs';
import { Store } from '../access/store.mjs';
import { encryptAsset } from '../access/crypto.mjs';

const functions = new Interface([
  'function owner(bytes32) view returns (address)',
  'function ownerOf(uint256) view returns (address)',
  'function getData(uint256) view returns (address,uint32,uint64)',
  'function decimals() view returns (uint8)',
  'function symbol() view returns (string)',
  'function balanceOf(address) view returns (uint256)',
  'function isValidSignature(bytes32,bytes) view returns (bytes4)'
]);
const hash = '0x' + 'ab'.repeat(32);

export function fakeMainnet(clock = Date.now) {
  const rpcState = {
    chainId: '0x1', age: 0, canonical: true, balance: MINIMUM, decimals: 18n, symbol: 'AGIALPHA',
    tokenCode: '0x6080', contract: null, signatureValid: null, outage: false,
    owners: new Map(), wrapped: new Map()
  };
  const rpc = async (method, args) => {
    if (rpcState.outage) throw Error('Synthetic RPC outage');
    if (method === 'eth_chainId') return rpcState.chainId;
    if (method === 'eth_getBlockByNumber') {
      return { hash, number: '0x100', timestamp: '0x' + (Math.floor(clock() / 1000) - rpcState.age).toString(16) };
    }
    if (args[1].blockHash !== hash || args[1].requireCanonical !== true || !rpcState.canonical) {
      throw Error('Synthetic canonical block mismatch');
    }
    if (method === 'eth_getCode') {
      if (args[0] === TOKEN) return rpcState.tokenCode;
      return args[0] === rpcState.contract ? '0x6000' : '0x';
    }
    if (method !== 'eth_call') throw Error('Unexpected synthetic RPC method');
    const [{ to, data }] = args;
    const call = functions.parseTransaction({ data });
    const [node] = call.args;
    const result = value => functions.encodeFunctionResult(call.name, value);
    if (to === TOKEN) {
      if (call.name === 'decimals') return result([rpcState.decimals]);
      if (call.name === 'symbol') return result([rpcState.symbol]);
      if (call.name === 'balanceOf') return result([rpcState.balance]);
    }
    if (to === REGISTRY && call.name === 'owner') return result([rpcState.owners.get(node) ?? ZeroAddress]);
    if (to === WRAPPER) {
      const row = rpcState.wrapped.get('0x' + node.toString(16).padStart(64, '0'));
      if (call.name === 'ownerOf') return result([row.owner]);
      if (call.name === 'getData') return result([row.recordedOwner ?? row.owner, row.fuses ?? 0, row.expiry]);
    }
    if (to === rpcState.contract && call.name === 'isValidSignature') {
      return result([await rpcState.signatureValid(call.args) ? '0x1626ba7e' : '0xffffffff']);
    }
    throw Error('Unexpected synthetic contract');
  };
  return { rpcState, chain: new Mainnet(rpc, clock) };
}

export const memberRecord = {
  section: 'experiment',
  en: { title: 'Synthetic member record', paragraphs: ['Fixture only. <img src=x>'] },
  fr: { title: 'Dossier membre synthétique', paragraphs: ['Donnée de test uniquement. <img src=x>'] }
};

export function testStore(t) {
  const directory = mkdtempSync(join(tmpdir(), 'frontier-test-'));
  const store = new Store(directory);
  const wrappingKey = { epoch: randomBytes(16).toString('hex'), key: randomBytes(32) };
  const asset = function (id = 'synthetic-record', version = 1, mode = 'browser') {
    const meta = { id, version, epoch: wrappingKey.epoch, format: 'research-json.' + mode + '.v1' };
    const box = encryptAsset(meta, Buffer.from(JSON.stringify(memberRecord)), wrappingKey.key);
    store.insert(box, memberRecord.section);
    return box;
  };
  t.after(() => {
    store.close();
    wrappingKey.key.fill(0);
    rmSync(directory, { recursive: true, force: true });
  });
  return { directory, store, wrappingKey, asset };
}

export function createWallet() {
  return new Wallet('0x' + randomBytes(32).toString('hex'));
}

export { clubNode, MINIMUM, WRAPPER };
