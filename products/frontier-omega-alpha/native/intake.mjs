import { Transaction } from 'ethers';
import { DESTINATION, TAG, MAX_FINALIZED_AGE_SECONDS, WINDOW_SECONDS, decodeEnrollment, hash } from './protocol.mjs';
import { validatePublicKey } from './hpke.mjs';

const MAX_BLOCKS = 120;
const MAX_SIGNALS = 48;
const BLOCK_CONCURRENCY = 6;
const MAX_RESPONSE_BYTES = 32 * 1024 * 1024;

export function boundedRpc(endpoint) {
  const url = new URL(endpoint);
  if (url.protocol !== 'https:' || url.username || url.password || url.hash) throw Error('Use a trusted HTTPS mainnet RPC');
  return async (method, params) => {
    const response = await fetch(url, {
      method: 'POST', redirect: 'error', signal: AbortSignal.timeout(15_000),
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params })
    });
    if (!response.ok || !response.body || Number(response.headers.get('content-length')) > MAX_RESPONSE_BYTES) {
      throw Error('Ethereum RPC unavailable');
    }
    const chunks = [];
    let size = 0;
    for await (const chunk of response.body) {
      size += chunk.length;
      if (size > MAX_RESPONSE_BYTES) throw Error('Ethereum RPC response exceeded the transport limit');
      chunks.push(chunk);
    }
    const packet = JSON.parse(Buffer.concat(chunks));
    if (packet?.id !== 1 || packet.jsonrpc !== '2.0' || packet.error || !Object.hasOwn(packet, 'result')) {
      throw Error('Invalid Ethereum RPC response');
    }
    return packet.result;
  };
}

function safeQuantity(value) {
  if (typeof value !== 'string' || !/^0x(?:0|[1-9a-f][0-9a-f]*)$/.test(value)) throw Error('Invalid Ethereum quantity');
  const result = Number(BigInt(value));
  if (!Number.isSafeInteger(result)) throw Error('Ethereum quantity exceeds supported range');
  return result;
}

export const quantity = value => '0x' + value.toString(16);

async function blockAt(rpc, blockTag, full = false) {
  const result = await rpc('eth_getBlockByNumber', [blockTag, full]);
  if (!hash(result?.hash) || !hash(result?.parentHash) || (full && !Array.isArray(result?.transactions))) {
    throw Error('Missing canonical block');
  }
  const height = safeQuantity(result.number);
  if (blockTag !== 'finalized' && height !== safeQuantity(blockTag)) throw Error('RPC returned a different block');
  return { ...result, height, time: safeQuantity(result.timestamp) };
}

export async function readFinalized(rpc, now = Date.now) {
  const [chain, head] = await Promise.all([rpc('eth_chainId', []), blockAt(rpc, 'finalized')]);
  if (chain !== '0x1' || now() / 1_000 - head.time > MAX_FINALIZED_AGE_SECONDS || head.time > now() / 1_000 + 12) {
    throw Error('Mainnet finalized head is missing or stale');
  }
  return head;
}

async function authenticate(rpc, tx, index, block) {
  const input = tx?.input;
  if (tx?.to?.toLowerCase() !== DESTINATION || tx.value !== '0x0' || tx.type !== '0x2' ||
      typeof input !== 'string' || !input.startsWith(TAG)) return null;

  let data;
  try {
    data = decodeEnrollment(input);
    if (data.expiresAt < block.time || data.expiresAt > block.time + WINDOW_SECONDS) return null;
    await validatePublicKey(data.publicKey);
  } catch {
    return null;
  }
  if (!hash(tx.hash) || tx.blockHash !== block.hash || safeQuantity(tx.blockNumber) !== block.height ||
      safeQuantity(tx.transactionIndex) !== index) throw Error('Transaction placement is inconsistent with the scanned block');

  const [raw, receipt] = await Promise.all([
    rpc('eth_getRawTransactionByHash', [tx.hash]),
    rpc('eth_getTransactionReceipt', [tx.hash])
  ]);
  if (typeof raw !== 'string' || raw.length > 8192 || receipt?.transactionHash !== tx.hash ||
      receipt.blockHash !== block.hash || safeQuantity(receipt.blockNumber) !== block.height ||
      safeQuantity(receipt.transactionIndex) !== index || receipt.to?.toLowerCase() !== DESTINATION) {
    throw Error('Transaction evidence is incomplete');
  }
  if (receipt.status === '0x0') return null;
  if (receipt.status !== '0x1') throw Error('Invalid transaction receipt');
  const signed = Transaction.from(raw);
  if (signed.hash !== tx.hash || signed.type !== 2 || signed.chainId !== 1n || signed.to !== DESTINATION ||
      signed.value !== 0n || signed.data !== input || !signed.from ||
      signed.from.toLowerCase() !== tx.from?.toLowerCase() || signed.from.toLowerCase() !== receipt.from?.toLowerCase()) {
    throw Error('Signed enrollment does not match the finalized receipt');
  }
  if (signed.from.toLowerCase() !== data.wallet) return null;
  return { ...data, tx: tx.hash, registeredAt: block.time };
}

export async function scanEnrollments(rpc, cursor, { now = Date.now, blocks = MAX_BLOCKS, signals = MAX_SIGNALS } = {}) {
  if (!Number.isInteger(blocks) || blocks < 1 || blocks > MAX_BLOCKS ||
      !Number.isInteger(signals) || signals < 1 || signals > MAX_SIGNALS) throw Error('Invalid scanner resource envelope');
  if (!Number.isSafeInteger(cursor?.height) || cursor.height < 1 || !hash(cursor.hash) ||
      !(cursor.offset === null || (Number.isSafeInteger(cursor.offset) && cursor.offset > 0))) {
    throw Error('Invalid enrollment checkpoint');
  }
  const [finalized, anchor] = await Promise.all([readFinalized(rpc, now), blockAt(rpc, quantity(cursor.height))]);
  if (anchor.hash !== cursor.hash || finalized.height < cursor.height ||
      (finalized.height === cursor.height && finalized.hash !== cursor.hash)) {
    throw Error('Finalized enrollment checkpoint changed. Stop provisioning and investigate.');
  }

  let progress = cursor;
  const events = [];
  let attempted = 0;
  const start = cursor.height + (cursor.offset === null ? 1 : 0);
  const last = Math.min(finalized.height, start + blocks - 1);
  for (let low = start; low <= last; low += BLOCK_CONCURRENCY) {
    const count = Math.min(BLOCK_CONCURRENCY, last - low + 1);
    const fetched = await Promise.all(Array.from({ length: count }, (_, i) => blockAt(rpc, quantity(low + i), true)));
    for (const block of fetched) {
      const partial = progress.offset !== null;
      if ((partial ? block.hash : block.parentHash) !== progress.hash ||
          (block.height === finalized.height && block.hash !== finalized.hash)) {
        throw Error('Enrollment blocks are not on the pinned finalized chain');
      }
      const offset = progress.offset ?? 0;
      if (offset && offset >= block.transactions.length) throw Error('Invalid transaction checkpoint');
      for (let index = offset; index < block.transactions.length; index++) {
        const tx = block.transactions[index];
        if (typeof tx?.input !== 'string') throw Error('Full block transaction data unavailable');
        if (tx.to?.toLowerCase() !== DESTINATION || !tx.input.startsWith(TAG)) continue;
        if (attempted === signals) {
          // With index zero the previous completed block is already a valid checkpoint.
          if (index > 0) progress = { height: block.height, hash: block.hash, offset: index };
          return { events, cursor: progress, caughtUp: progress.height === finalized.height && progress.offset === null };
        }
        attempted++;
        const event = await authenticate(rpc, tx, index, block);
        if (event) events.push(event);
      }
      progress = { height: block.height, hash: block.hash, offset: null };
    }
  }
  return { events, cursor: progress, caughtUp: progress.height === finalized.height && progress.offset === null };
}
