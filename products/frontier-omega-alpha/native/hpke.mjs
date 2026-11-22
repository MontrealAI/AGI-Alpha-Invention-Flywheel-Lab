import { Aes256Gcm, CipherSuite, DhkemP256HkdfSha256, HkdfSha256 } from '@hpke/core';
import { envelopeContext, fromBase64, publicKeyBytes, toBase64 } from './protocol.mjs';

export const suite = new CipherSuite({ kem: new DhkemP256HkdfSha256(), kdf: new HkdfSha256(), aead: new Aes256Gcm() });
const info = new TextEncoder().encode('FRONTIER Ω ALPHA | Ethereum mainnet | member content key v1');

export async function validatePublicKey(publicKey) {
  // Web Crypto rejects malformed or off-curve P-256 points.
  return crypto.subtle.importKey('raw', publicKeyBytes(publicKey), { name: 'ECDH', namedCurve: 'P-256' }, true, []);
}

export async function makeDeviceKey() {
  const pair = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, false, ['deriveBits']);
  return { privateKey: pair.privateKey, publicKey: toBase64(await crypto.subtle.exportKey('raw', pair.publicKey)) };
}

export async function encapsulate(recipientPublicKey, key, tx, tag) {
  const sender = await suite.createSenderContext({ recipientPublicKey, info });
  return { enc: toBase64(sender.enc), body: toBase64(await sender.seal(key, envelopeContext(tx, tag))) };
}

export async function decapsulate(device, box, tx, tag) {
  const recipientKey = { privateKey: device.privateKey, publicKey: await validatePublicKey(device.publicKey) };
  const recipient = await suite.createRecipientContext({ recipientKey, enc: publicKeyBytes(box.enc), info });
  const key = new Uint8Array(await recipient.open(fromBase64(box.body, 48), envelopeContext(tx, tag)));
  if (key.length !== 32) throw Error('Invalid provisioned content key');
  return key;
}
