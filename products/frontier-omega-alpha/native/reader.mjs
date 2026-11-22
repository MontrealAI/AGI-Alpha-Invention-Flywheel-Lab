import { formatEther, getAddress } from 'ethers';
import { Mainnet, clubLabel } from '../access/chain.mjs';
import {
  address, assertLibrary, DESTINATION, encodeEnrollment, enrollmentId, hash, hex, MAX_LIBRARY_BYTES,
  releaseTag, toBase64, WINDOW_SECONDS
} from './protocol.mjs';
import { compareDevice, loadDevice } from './device.mjs';
import { decapsulate, makeDeviceKey } from './hpke.mjs';

const sharedOrigin = 'https://montrealai.github.io';
const enc = new TextDecoder('utf-8', { fatal: true });
const detected = new Set();
window.addEventListener('eip6963:announceProvider', event => {
  const { info, provider } = event.detail ?? {};
  if (info?.rdns === 'io.metamask' && provider?.isMetaMask === true && typeof provider.request === 'function') {
    detected.add(provider);
  }
});

function metaMask() {
  window.dispatchEvent(new Event('eip6963:requestProvider'));
  return detected.values().next().value ?? [...(window.ethereum?.providers ?? []), window.ethereum]
    .find(provider => provider?.isMetaMask === true && typeof provider.request === 'function');
}

export function validateReader(config, actual = location, loopbackTest = false) {
  const reader = new URL(config.reader);
  const data = new URL(config.data);
  const loopback = loopbackTest && reader.hostname === '127.0.0.1' && data.hostname === '127.0.0.1';
  if (reader.origin !== actual.origin || reader.origin === sharedOrigin ||
      ((!loopback || reader.protocol !== 'http:') && reader.protocol !== 'https:') ||
      ((!loopback || data.protocol !== 'http:') && data.protocol !== 'https:') ||
      [reader, data].some(url => url.username || url.password || url.search || url.hash) ||
      !reader.pathname.endsWith('/') || !data.pathname.endsWith('/library.json') ||
      !['', 'index.html', 'fr.html'].some(page => actual.pathname === reader.pathname + page) ||
      window.top !== window.self) throw Error('reader_origin');
  return data.href;
}

async function fetchLibrary(url) {
  const response = await fetch(url, {
    cache: 'no-store', redirect: 'error', credentials: 'omit', referrerPolicy: 'no-referrer',
    signal: AbortSignal.timeout(20_000)
  });
  if (!response.ok || !response.body || Number(response.headers.get('content-length')) > MAX_LIBRARY_BYTES) throw Error('publisher_offline');
  const reader = response.body.getReader();
  let size = 0;
  let text = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > MAX_LIBRARY_BYTES) {
      await reader.cancel();
      throw Error('publisher_offline');
    }
    text += enc.decode(value, { stream: true });
  }
  return assertLibrary(JSON.parse(text + enc.decode()));
}

function unsignedQuantity(value) {
  if (typeof value !== 'string' || !/^0x(?:0|[1-9a-f][0-9a-f]*)$/.test(value)) {
    throw Error('fee_unavailable');
  }
  return BigInt(value);
}

const quantity = value => '0x' + value.toString(16);

async function estimate(request, current, data) {
  const input = { from: current, to: DESTINATION, value: '0x0', data };
  const [gas, block, tip] = await Promise.all([
    request('eth_estimateGas', [input]), request('eth_getBlockByNumber', ['latest', false]),
    request('eth_maxPriorityFeePerGas', [])
  ]);
  const fee = unsignedQuantity(block?.baseFeePerGas);
  const priority = unsignedQuantity(tip);
  const limit = unsignedQuantity(gas);
  if (limit < 21_000n || limit > 50_000n || fee * 2n + priority <= 0n) throw Error('fee_unavailable');
  const max = fee * 2n + priority;
  return {
    payload: { ...input, gas: quantity(limit), maxFeePerGas: quantity(max), maxPriorityFeePerGas: quantity(priority) },
    gas: limit.toString(), maximum: formatEther(limit * max), estimate: formatEther(limit * (fee + priority)),
    quotedAt: Date.now()
  };
}

export async function connectReader(config, prefix, { loopbackTest = false } = {}) {
  const url = validateReader(config, location, loopbackTest);
  const wallet = metaMask();
  if (!wallet) throw Error('metamask_missing');
  const request = (method, params = []) => wallet.request({ method, params });
  const [owner] = await request('eth_requestAccounts');
  if (!address(owner?.toLowerCase())) throw Error('metamask_missing');
  const current = owner.toLowerCase();
  const chain = new Mainnet(request);
  const selectedLabel = prefix === null ? null : clubLabel(prefix);
  let saved = await loadDevice(current);
  let persisted = saved;
  if (saved && (!(saved.privateKey instanceof CryptoKey) || saved.privateKey.extractable ||
      saved.privateKey.type !== 'private' || saved.privateKey.algorithm.name !== 'ECDH')) throw Error('storage');

  async function account() {
    const [[first], network] = await Promise.all([request('eth_accounts'), request('eth_chainId')]);
    if (network !== '0x1') throw Error('network');
    if (first?.toLowerCase() !== current) throw Error('wallet_changed');
  }

  async function check() {
    await account();
    const block = await chain.snapshot();
    const path = await chain.entitlement(getAddress(current), saved ? saved.label : selectedLabel, block);
    if (!path) throw Error('ineligible');
    return block;
  }

  async function status({ checked = false } = {}) {
    if (!checked) await account();
    if (!saved) return { state: 'new' };
    const library = await fetchLibrary(url);
    const id = await enrollmentId(current, saved.nonce);
    const receipt = Object.hasOwn(library.recipients, id) ? library.recipients[id] : null;
    if (receipt?.state === 'provisioned') {
      await check();
      const entries = library.records.filter(record => Object.hasOwn(receipt.keys, record.tag));
      return {
        state: 'provisioned', wallet, entries, check,
        async open(entry) {
          await check();
          if (await releaseTag(entry) !== entry.tag) throw Error('release_unavailable');
          const key = await decapsulate(saved, receipt.keys[entry.tag], receipt.tx, entry.tag);
          try {
            return { ciphertext: entry, key: toBase64(key) };
          } finally {
            key.fill(0);
          }
        }
      };
    }
    if (receipt) return { state: receipt.state, tx: receipt.tx };
    if (!saved.tx && saved.phase === 'broadcasting') {
      return { state: saved.expiresAt > Date.now() / 1_000 ? 'awaiting_receipt' : 'expired_receipt' };
    }
    if (!saved.tx) return { state: 'new' };
    const mined = await request('eth_getTransactionReceipt', [saved.tx]);
    if (mined?.status === '0x0') return { state: 'failed', tx: saved.tx };
    if (mined?.status === '0x1' && mined.transactionHash === saved.tx && mined.from?.toLowerCase() === current &&
        mined.to?.toLowerCase() === DESTINATION) return { state: 'confirmed', tx: saved.tx };
    return { state: 'pending', tx: saved.tx };
  }

  async function requirePublisher() {
    const library = await fetchLibrary(url);
    const age = Date.now() / 1000 - library.updatedAt;
    if (!library.openEnrollment || !library.records.length || age > 2 * 60 * 60 || age < -60) throw Error('publisher_offline');
  }

  async function prepare(renew = false) {
    await account();
    await requirePublisher();
    const existing = await status({ checked: true });
    if (!renew && existing.state !== 'new') return existing;
    if (renew && !['superseded', 'failed', 'denied', 'capacity', 'expired_receipt', 'revoked'].includes(existing.state)) throw Error('unavailable');
    if (renew || !saved || saved.expiresAt < Date.now() / 1000 + 20 * 60) {
      const device = await makeDeviceKey();
      saved = { ...device, label: selectedLabel, nonce: hex(crypto.getRandomValues(new Uint8Array(16))),
        expiresAt: 0, phase: 'draft', tx: null };
    }
    const block = await check();
    if (!saved.expiresAt) saved.expiresAt = block.timestamp + WINDOW_SECONDS - 60;
    const data = encodeEnrollment({ ...saved, wallet: current });
    return { state: 'review', quote: await estimate(request, current, data) };
  }

  async function submit(quote) {
    await account();
    if (Date.now() - quote.quotedAt > 90_000) {
      await requirePublisher();
      await check();
      return { state: 'review', quote: await estimate(request, current, encodeEnrollment({ ...saved, wallet: current })) };
    }
    await requirePublisher();
    await check();
    if (quote.payload.data !== encodeEnrollment({ ...saved, wallet: current }) ||
        quote.payload.from !== current || quote.payload.to !== DESTINATION || quote.payload.value !== '0x0') throw Error('unavailable');
    const broadcasting = { ...saved, phase: 'broadcasting' };
    if (!await compareDevice(current, persisted, broadcasting)) throw Error('storage_busy');
    persisted = broadcasting;
    saved = broadcasting;
    let tx;
    try {
      tx = await request('eth_sendTransaction', [quote.payload]);
    } catch (error) {
      if (error.code === 4001) {
        const recoverable = { ...broadcasting, phase: 'draft' };
        if (await compareDevice(current, broadcasting, recoverable)) persisted = saved = recoverable;
        throw error;
      }
      return { state: 'awaiting_receipt' };
    }
    if (!hash(tx)) return { state: 'awaiting_receipt' };
    const submitted = { ...broadcasting, tx, phase: 'sent' };
    if (!await compareDevice(current, broadcasting, submitted)) return { state: 'awaiting_receipt' };
    persisted = saved = submitted;
    return { state: 'pending', tx };
  }

  await account();
  return { wallet, status, prepare, submit };
}
