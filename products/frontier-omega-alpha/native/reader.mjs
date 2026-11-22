import { getAddress } from 'ethers';
import { Mainnet, clubLabel } from '../access/chain.mjs';
import {
  address, assertLibrary, enrollmentId, hex, MAX_LIBRARY_BYTES, releaseTag, SIGNED_LIBRARY_SCHEMA, toBase64, WINDOW_SECONDS
} from './protocol.mjs';
import { compareDevice, loadDevice } from './device.mjs';
import { decapsulate, makeDeviceKey } from './hpke.mjs';
import { authenticateSignedEnrollment, makeSignedEnrollment, signedEnrollmentMessage } from './signed-enrollment.mjs';

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
  const library = assertLibrary(JSON.parse(text + enc.decode()));
  if (library.schema !== SIGNED_LIBRARY_SCHEMA) throw Error('publisher_offline');
  return library;
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
  let draft;
  if (saved && (!(saved.privateKey instanceof CryptoKey) || saved.privateKey.extractable ||
      saved.privateKey.type !== 'private' || saved.privateKey.algorithm.name !== 'ECDH')) throw Error('storage');

  async function account() {
    const [[first], network] = await Promise.all([request('eth_accounts'), request('eth_chainId')]);
    if (network !== '0x1') throw Error('network');
    if (first?.toLowerCase() !== current) throw Error('wallet_changed');
  }

  async function check(label = saved ? saved.label : selectedLabel) {
    await account();
    const block = await chain.snapshot();
    const path = await chain.entitlement(getAddress(current), label, block);
    if (!path) throw Error('ineligible');
    return block;
  }

  async function status({ checked = false } = {}) {
    if (!checked) await account();
    if (!saved) return { state: 'new' };
    const library = await fetchLibrary(url);
    const id = await enrollmentId(current, saved.nonce);
    const receipt = Object.hasOwn(library.recipients, id) ? library.recipients[id] : null;
    if (receipt && receipt.proof !== saved.proof) throw Error('unavailable');
    if (receipt?.state === 'provisioned') {
      await check();
      const entries = library.records.filter(record => Object.hasOwn(receipt.keys, record.tag));
      return {
        state: 'provisioned', wallet, entries, check,
        async open(entry) {
          await check();
          if (await releaseTag(entry) !== entry.tag) throw Error('release_unavailable');
          const key = await decapsulate(saved, receipt.keys[entry.tag], receipt.proof, entry.tag, library.schema);
          try {
            return { ciphertext: entry, key: toBase64(key) };
          } finally {
            key.fill(0);
          }
        }
      };
    }
    if (receipt) return { state: receipt.state };
    if (saved.expiresAt <= Date.now() / 1000) return { state: 'expired_receipt' };
    return { state: 'pending', request: saved.request };
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
    if (renew && !['superseded', 'denied', 'capacity', 'expired_receipt', 'revoked'].includes(existing.state)) throw Error('unavailable');
    const block = await check(selectedLabel);
    const device = await makeDeviceKey();
    const payload = makeSignedEnrollment({
      origin: location.origin, issuedAt: block.timestamp, expiresAt: block.timestamp + WINDOW_SECONDS,
      wallet: current, label: selectedLabel, nonce: hex(crypto.getRandomValues(new Uint8Array(16))), publicKey: device.publicKey
    });
    draft = { device, payload, renew };
    return { state: 'review', message: signedEnrollmentMessage(payload, location.origin) };
  }

  async function submit() {
    if (!draft) throw Error('unavailable');
    await requirePublisher();
    const { device, payload, renew } = draft;
    if (Date.now() / 1000 - payload.issuedAt > 180) return prepare(renew);
    await check(selectedLabel);
    const message = signedEnrollmentMessage(payload, location.origin);
    const signature = await request('personal_sign', [hex(new TextEncoder().encode(message)), current]);
    const packet = { ...payload, signature };
    const snapshot = await check(selectedLabel);
    const verified = await authenticateSignedEnrollment(packet, location.origin, chain, snapshot);
    if (!verified) throw Error('unavailable');
    const { label, nonce, expiresAt, proof } = verified;
    const enrolled = { ...device, label, nonce, expiresAt, proof, request: packet };
    if (!await compareDevice(current, persisted, enrolled)) throw Error('storage_busy');
    persisted = saved = enrolled;
    draft = null;
    return { state: 'pending', request: packet };
  }

  await account();
  return { wallet, status, prepare, submit };
}
