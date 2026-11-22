import { createHash, randomBytes } from 'node:crypto';
import { Transaction, toBeHex, zeroPadValue } from 'ethers';
import { TOKEN } from '../access/chain.mjs';
import { encryptAsset } from '../access/crypto.mjs';
import { fakeMainnet, memberRecord } from './fixtures.mjs';
import { CIPHERTEXT_FORMAT, DESTINATION, encodeEnrollment, hex } from '../native/protocol.mjs';
import { makeDeviceKey } from '../native/hpke.mjs';

const blockHash = height => '0x' + createHash('sha256').update('block fixture ' + height).digest('hex');
const quantity = number => '0x' + number.toString(16);

export function fixtureChain(now = Date.now) {
  const { chain, rpcState } = fakeMainnet(now);
  const blocks = new Map();
  const receipts = new Map();
  const signed = new Map();
  const balances = new Map();
  let head = 100;
  const timestamp = () => Math.floor(now() / 1_000);

  function block(height, transactions) {
    return {
      number: quantity(height), hash: blockHash(height), parentHash: blockHash(height - 1),
      timestamp: quantity(timestamp()), transactions
    };
  }
  blocks.set(head, block(head, []));
  const cursor = { height: head, hash: blockHash(head), offset: null };

  async function mine(rawTransactions) {
    head++;
    const txs = rawTransactions.map((raw, index) => {
      const signedTx = Transaction.from(raw);
      const position = { blockHash: blockHash(head), blockNumber: quantity(head), transactionIndex: quantity(index) };
      const receipt = {
        ...position, transactionHash: signedTx.hash, status: '0x1',
        from: signedTx.from.toLowerCase(), to: signedTx.to.toLowerCase()
      };
      receipts.set(signedTx.hash, receipt);
      signed.set(signedTx.hash, raw);
      return { ...position, hash: signedTx.hash, from: receipt.from, to: receipt.to, value: quantity(signedTx.value),
        type: quantity(signedTx.type), input: signedTx.data };
    });
    blocks.set(head, block(head, txs));
    return txs.map(tx => tx.hash);
  }

  async function rpc(method, args) {
    if (rpcState.outage) throw Error('Synthetic RPC outage');
    if (method === 'eth_getBlockByNumber') {
      const found = blocks.get(args[0] === 'finalized' ? head : Number(args[0]));
      if (found) return found;
      return { ...await chain.rpc(method, ['latest', false]), baseFeePerGas: '0x2' };
    }
    if (method === 'eth_getRawTransactionByHash') return signed.get(args[0]) ?? null;
    if (method === 'eth_getTransactionReceipt') return receipts.get(args[0]) ?? null;
    if (method === 'eth_estimateGas') return '0x6400';
    if (method === 'eth_maxPriorityFeePerGas') return '0x1';
    const call = args[0];
    if (method === 'eth_call' && call.to === TOKEN && call.data.startsWith('0x70a08231')) {
      const target = '0x' + call.data.slice(-40);
      if (balances.has(target)) return zeroPadValue(toBeHex(balances.get(target)), 32);
    }
    return chain.rpc(method, args);
  }
  return { rpc, mine, cursor, blocks, balances, receipts, rpcState };
}

export async function createEnrollment(signer, options = {}) {
  const device = options.device ?? await makeDeviceKey();
  const wallet = (options.wallet ?? signer.address).toLowerCase();
  const info = { wallet, publicKey: device.publicKey, nonce: options.nonce ?? hex(randomBytes(16)),
    label: options.label ?? null, expiresAt: options.expiresAt ?? Math.floor(Date.now() / 1_000) + 1200 };
  const raw = await signEnrollment(signer, { data: encodeEnrollment(info), nonce: options.txNonce ?? 0 });
  return { device, info, raw, tx: Transaction.from(raw).hash };
}

export function signEnrollment(signer, { data, nonce = 0, value = 0n, to = DESTINATION }) {
  return signer.signTransaction({ chainId: 1, type: 2, nonce, to, data, value,
    gasLimit: 35000n, maxFeePerGas: 5n, maxPriorityFeePerGas: 1n });
}

export function assetFor(masterKey, version = 1, doc = memberRecord) {
  const box = encryptAsset({ id: 'synthetic-lab', version, epoch: randomBytes(16).toString('hex'), format: CIPHERTEXT_FORMAT },
    Buffer.from(JSON.stringify(doc)), masterKey);
  return { ...box, section: doc.section };
}
