import { createCipheriv, createDecipheriv, hkdfSync, randomBytes } from 'node:crypto';
import { fromBase64, keysAre, MAX_LIBRARY_BYTES, toBase64 } from './protocol.mjs';

const metadata = Buffer.from('FRONTIER Ω ALPHA GitHub publisher checkpoint v1', 'utf8');

function stateKey(masterKey) {
  return Buffer.from(hkdfSync('sha256', masterKey, new Uint8Array(32), metadata, 32));
}

export function sealState(state, masterKey) {
  const input = Buffer.from(JSON.stringify(state));
  if (input.length > MAX_LIBRARY_BYTES + 1024 * 1024) throw Error('Checkpoint exceeds the supported envelope');
  const iv = randomBytes(12);
  const key = stateKey(masterKey);
  try {
    const cipher = createCipheriv('aes-256-gcm', key, iv, { authTagLength: 16 });
    cipher.setAAD(metadata);
    const data = Buffer.concat([cipher.update(input), cipher.final(), cipher.getAuthTag()]);
    return { v: 1, iv: toBase64(iv), body: toBase64(data) };
  } finally {
    key.fill(0);
    input.fill(0);
  }
}

export function openState(sealed, masterKey) {
  if (!keysAre(sealed, ['v', 'iv', 'body']) || sealed.v !== 1) throw Error('Invalid publisher checkpoint');
  const iv = fromBase64(sealed.iv, 12);
  const data = fromBase64(sealed.body, MAX_LIBRARY_BYTES + 1024 * 1024 + 16);
  if (iv.length !== 12 || data.length <= 16) throw Error('Invalid checkpoint ciphertext');
  const key = stateKey(masterKey);
  try {
    const cipher = createDecipheriv('aes-256-gcm', key, iv, { authTagLength: 16 });
    cipher.setAAD(metadata);
    cipher.setAuthTag(data.subarray(data.length - 16));
    const bytes = Buffer.concat([cipher.update(data.subarray(0, data.length - 16)), cipher.final()]);
    try {
      const state = JSON.parse(bytes.toString('utf8'));
      if (!keysAre(state, ['cursor', 'active', 'outcomes', 'publication', 'releases'])) throw Error('Invalid publisher checkpoint state');
      return state;
    } finally {
      bytes.fill(0);
    }
  } finally {
    key.fill(0);
  }
}
