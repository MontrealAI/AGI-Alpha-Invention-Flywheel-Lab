export const DESTINATION = '0x0000000000000000000000000000000000000004';
export const MAINNET = 1;
export const TAG = '0x46524f4e544945520101';
export const WINDOW_SECONDS = 24 * 60 * 60;
export const MAX_FINALIZED_AGE_SECONDS = 45 * 60;
export const CIPHERTEXT_FORMAT = 'research-json.browser.v1';
export const LIBRARY_SCHEMA = 'frontier-omega-alpha/library-v1';
export const SIGNED_LIBRARY_SCHEMA = 'frontier-omega-alpha/signed-library-v1';
export const MAX_RELEASES = 12;
export const MAX_MEMBERS = 96;
export const MAX_LIBRARY_BYTES = 6 * 1024 * 1024;
export const SECTIONS = ['radar', 'opportunity', 'experiment', 'verification', 'compounding', 'archive'];

const text = new TextEncoder();
const readText = new TextDecoder('utf-8', { fatal: true });
const heading = 115;
const labelPattern = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
export const hash = value => typeof value === 'string' && /^0x[a-f0-9]{64}$/.test(value);
export const address = value => typeof value === 'string' && /^0x[a-f0-9]{40}$/.test(value);
export const hex = bytes => '0x' + Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');

export function bytes(value) {
  if (typeof value !== 'string' || !/^0x(?:[a-f0-9]{2})*$/.test(value)) throw Error('Invalid hexadecimal data');
  return Uint8Array.from(value.slice(2).match(/.{2}/g) ?? [], byte => Number.parseInt(byte, 16));
}

export function toBase64(value) {
  let binary = '';
  for (const byte of new Uint8Array(value)) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
}

export function fromBase64(value, limit) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_-]+$/.test(value) || value.length > Math.ceil(limit * 4 / 3)) {
    throw Error('Invalid base64url value');
  }
  const data = Uint8Array.from(atob(value.replaceAll('-', '+').replaceAll('_', '/')), c => c.charCodeAt(0));
  if (data.length > limit || toBase64(data) !== value) throw Error('Invalid base64url bytes');
  return data;
}

export const keysAre = (value, keys) => value && typeof value === 'object' && !Array.isArray(value) &&
  Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));

export function publicKeyBytes(value) {
  const key = fromBase64(value, 65);
  if (key.length !== 65 || key[0] !== 4) throw Error('Invalid P-256 key format');
  return key;
}

export function encodeEnrollment({ wallet, nonce, publicKey, expiresAt, label = null }) {
  if (!address(wallet) || !/^0x[a-f0-9]{32}$/.test(nonce) || nonce === '0x' + '0'.repeat(32) ||
      !Number.isInteger(expiresAt) || expiresAt <= 0 || expiresAt > 0xffffffff ||
      (label !== null && (typeof label !== 'string' || !labelPattern.test(label)))) throw Error('Invalid enrollment');
  const labelBytes = text.encode(label ?? '');
  const out = new Uint8Array(heading + labelBytes.length);
  out.set(bytes(TAG));
  out.set(bytes(wallet), 10);
  out.set(bytes(nonce), 30);
  new DataView(out.buffer).setUint32(46, expiresAt, false);
  out.set(publicKeyBytes(publicKey), 50);
  out.set(labelBytes, heading);
  return hex(out);
}

export function decodeEnrollment(value) {
  if (typeof value !== 'string' || !value.startsWith(TAG) || value.length < 2 + heading * 2 ||
      value.length > 2 + (heading + 63) * 2) throw Error('Not a registered enrollment format');
  const data = bytes(value);
  const result = {
    wallet: hex(data.slice(10, 30)),
    nonce: hex(data.slice(30, 46)),
    expiresAt: new DataView(data.buffer).getUint32(46, false),
    publicKey: toBase64(data.slice(50, 115)),
    label: data.length === heading ? null : readText.decode(data.slice(heading))
  };
  if (encodeEnrollment(result) !== value) throw Error('Noncanonical enrollment');
  return result;
}

export async function enrollmentId(wallet, nonce) {
  return hex(new Uint8Array(await crypto.subtle.digest('SHA-256', text.encode(JSON.stringify([TAG, wallet, nonce])))));
}

export function assetContext(record) {
  return [record.id, record.version, record.epoch, record.format, record.section];
}

export function envelopeContext(proof, tag, schema = LIBRARY_SCHEMA) {
  return text.encode(JSON.stringify([schema, MAINNET, proof, tag]));
}

export async function releaseTag(record) {
  const value = JSON.stringify([...assetContext(record), record.payload.iv, record.payload.body]);
  return hex(new Uint8Array(await crypto.subtle.digest('SHA-256', text.encode(value))));
}

export function assertRecord(record, wrapped = false) {
  const fields = ['id', 'version', 'epoch', 'format', 'section', 'payload', wrapped ? 'wrapped' : 'tag'];
  if (!keysAre(record, fields) || typeof record.id !== 'string' || !/^[a-z0-9][a-z0-9-]{0,79}$/.test(record.id) ||
      !Number.isSafeInteger(record.version) || record.version < 1 || typeof record.epoch !== 'string' || !/^[a-f0-9]{32}$/.test(record.epoch) ||
      record.format !== CIPHERTEXT_FORMAT || !SECTIONS.includes(record.section)) {
    throw Error('Invalid release metadata');
  }
  const boxValid = (box, length, minimum) => keysAre(box, ['iv', 'body']) &&
    fromBase64(box.iv, 12).length === 12 && fromBase64(box.body, length).length >= minimum;
  if (!boxValid(record.payload, 262144 + 16, 17) ||
      !(wrapped ? boxValid(record.wrapped, 48, 48) : hash(record.tag))) throw Error('Invalid release ciphertext');
}

export function assertLibrary(library) {
  if (!keysAre(library, ['schema', 'updatedAt', 'openEnrollment', 'records', 'recipients']) ||
      ![LIBRARY_SCHEMA, SIGNED_LIBRARY_SCHEMA].includes(library.schema) ||
      typeof library.openEnrollment !== 'boolean' || !Number.isSafeInteger(library.updatedAt) || library.updatedAt <= 0 ||
      !Array.isArray(library.records) || library.records.length > MAX_RELEASES ||
      !library.recipients || typeof library.recipients !== 'object' || Array.isArray(library.recipients) ||
      Object.keys(library.recipients).length > 2 * MAX_MEMBERS) throw Error('Invalid encrypted library');
  const tags = new Set();
  const versions = new Set();
  for (const record of library.records) {
    assertRecord(record);
    const release = record.id + ':' + record.version;
    if (tags.has(record.tag) || versions.has(release)) throw Error('Duplicate release');
    tags.add(record.tag);
    versions.add(release);
  }
  const proof = library.schema === SIGNED_LIBRARY_SCHEMA ? 'proof' : 'tx';
  for (const [id, entry] of Object.entries(library.recipients)) {
    if (!hash(id) || !keysAre(entry, [proof, 'state', 'keys']) || !hash(entry[proof]) ||
        !['eligible', 'provisioned', 'denied', 'revoked', 'superseded', 'capacity'].includes(entry.state) ||
        !entry.keys || typeof entry.keys !== 'object' || Array.isArray(entry.keys)) throw Error('Invalid registration receipt');
    const envelopes = Object.entries(entry.keys);
    if ((entry.state === 'provisioned') !== (envelopes.length > 0)) throw Error('Invalid enrollment status');
    for (const [tag, box] of envelopes) {
      if (!tags.has(tag) || !keysAre(box, ['enc', 'body']) ||
          publicKeyBytes(box.enc).length !== 65 || fromBase64(box.body, 48).length !== 48) throw Error('Invalid member envelope');
    }
  }
  return library;
}
