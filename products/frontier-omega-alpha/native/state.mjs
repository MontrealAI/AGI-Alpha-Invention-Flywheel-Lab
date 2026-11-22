import { createCipheriv, createDecipheriv, createHash, hkdfSync, randomBytes } from 'node:crypto';
import { assertLibrary, fromBase64, keysAre, MAX_LIBRARY_BYTES, toBase64 } from './protocol.mjs';

const legacyLimit = MAX_LIBRARY_BYTES + 1024 * 1024;
const compactLimit = 512 * 1024;
export const checkpointEnvelopeBytes = Math.ceil((legacyLimit + 16) * 4 / 3) + 1024;

function context(version) {
  return Buffer.from(`FRONTIER Ω ALPHA GitHub publisher checkpoint v${version}`, 'utf8');
}

function stateKey(masterKey, metadata) {
  return Buffer.from(hkdfSync('sha256', masterKey, new Uint8Array(32), metadata, 32));
}

function snapshotDigest(library) {
  return createHash('sha256').update(JSON.stringify(library)).digest('hex');
}

export function sealState(state, masterKey) {
  // The other file at this Git revision holds the already encrypted records and envelopes.
  const { publication, active, ...checkpoint } = state;
  const devices = Object.fromEntries(Object.entries(active).map(([wallet, { keys, ...member }]) => [wallet, member]));
  const input = Buffer.from(JSON.stringify({ ...checkpoint, active: devices, digest: snapshotDigest(publication) }));
  if (input.length > compactLimit) throw Error('Checkpoint exceeds the supported envelope');
  const version = 2;
  const metadata = context(version);
  const iv = randomBytes(12);
  const key = stateKey(masterKey, metadata);
  try {
    const cipher = createCipheriv('aes-256-gcm', key, iv, { authTagLength: 16 });
    cipher.setAAD(metadata);
    const data = Buffer.concat([cipher.update(input), cipher.final(), cipher.getAuthTag()]);
    return { v: version, iv: toBase64(iv), body: toBase64(data) };
  } finally {
    key.fill(0);
    input.fill(0);
  }
}

export function openState(sealed, masterKey, library) {
  if (!keysAre(sealed, ['v', 'iv', 'body']) || ![1, 2].includes(sealed.v)) throw Error('Invalid publisher checkpoint');
  const iv = fromBase64(sealed.iv, 12);
  const limit = sealed.v === 1 ? legacyLimit : compactLimit;
  const data = fromBase64(sealed.body, limit + 16);
  if (iv.length !== 12 || data.length <= 16) throw Error('Invalid checkpoint ciphertext');
  const metadata = context(sealed.v);
  const key = stateKey(masterKey, metadata);
  try {
    const cipher = createDecipheriv('aes-256-gcm', key, iv, { authTagLength: 16 });
    cipher.setAAD(metadata);
    cipher.setAuthTag(data.subarray(data.length - 16));
    const bytes = Buffer.concat([cipher.update(data.subarray(0, data.length - 16)), cipher.final()]);
    try {
      const state = JSON.parse(bytes.toString('utf8'));
      const digest = snapshotDigest(assertLibrary(library));
      const fields = ['cursor', 'active', 'outcomes', 'releases'];
      if (sealed.v === 1) {
        if (!keysAre(state, [...fields, 'publication'])) throw Error('Invalid publisher checkpoint state');
        if (digest !== snapshotDigest(state.publication)) throw Error('Publisher checkpoint and public library disagree');
        return state;
      }
      if (!keysAre(state, [...fields, 'digest'])) throw Error('Invalid publisher checkpoint state');
      if (state.digest !== digest) throw Error('Publisher checkpoint and public library disagree');
      const { digest: _, ...checkpoint } = state;
      for (const member of Object.values(checkpoint.active)) {
        const receipt = library.recipients[member.id];
        if (!receipt || receipt.tx !== member.tx || receipt.state !== member.state) throw Error('Publisher checkpoint and public library disagree');
        member.keys = structuredClone(receipt.keys);
      }
      return { ...checkpoint, publication: library };
    } finally {
      bytes.fill(0);
    }
  } finally {
    key.fill(0);
  }
}
