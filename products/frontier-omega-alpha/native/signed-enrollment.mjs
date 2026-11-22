import { getAddress, hashMessage } from 'ethers';
import { decodeEnrollment, encodeEnrollment, keysAre, WINDOW_SECONDS } from './protocol.mjs';
import { validatePublicKey } from './hpke.mjs';

export const SIGNED_ENROLLMENT = 'frontier-omega-alpha/signed-enrollment-v1';

function requestData(request, expectedOrigin) {
  if (!request || request.schema !== SIGNED_ENROLLMENT || !Number.isSafeInteger(request.issuedAt) ||
      request.issuedAt <= 0 || request.origin !== expectedOrigin) throw Error('Invalid device request');
  const origin = new URL(request.origin);
  if (origin.origin !== request.origin ||
      (origin.protocol !== 'https:' && !(origin.protocol === 'http:' && origin.hostname === '127.0.0.1'))) {
    throw Error('Invalid device request origin');
  }
  const data = decodeEnrollment(request.enrollment);
  const lifetime = data.expiresAt - request.issuedAt;
  if (lifetime <= 0 || lifetime > WINDOW_SECONDS) throw Error('Invalid device request lifetime');
  return { origin, data };
}

export function makeSignedEnrollment({ origin, issuedAt, ...data }) {
  const request = { schema: SIGNED_ENROLLMENT, origin, issuedAt, enrollment: encodeEnrollment(data) };
  requestData(request, origin);
  return request;
}

export function signedEnrollmentMessage(request, expectedOrigin) {
  const { origin, data } = requestData(request, expectedOrigin);
  // Compose the fixed EIP-4361 form on both Node and the static browser.
  return [
    origin.origin + ' wants you to sign in with your Ethereum account:',
    getAddress(data.wallet), '', 'Authorize this device to read encrypted FRONTIER Research.', '',
    'URI: ' + origin.href, 'Version: 1', 'Chain ID: 1', 'Nonce: ' + data.nonce.slice(2),
    'Issued At: ' + new Date(request.issuedAt * 1000).toISOString(),
    'Expiration Time: ' + new Date(data.expiresAt * 1000).toISOString(),
    'Resources:', '- urn:frontier-omega-alpha:signed-device:' + request.enrollment
  ].join('\n');
}

export async function authenticateSignedEnrollment(request, expectedOrigin, chain, snapshot) {
  if (!keysAre(request, ['schema', 'origin', 'issuedAt', 'enrollment', 'signature']) ||
      typeof request.signature !== 'string' || !/^0x(?:[0-9a-f]{2}){1,1024}$/i.test(request.signature)) {
    throw Error('Invalid signed device request');
  }
  const { data } = requestData(request, expectedOrigin);
  const now = Math.max(snapshot.timestamp, Math.floor(chain.now() / 1000));
  if (request.issuedAt > now + 12 || data.expiresAt <= now) return null;
  const message = signedEnrollmentMessage(request, expectedOrigin);
  const owner = getAddress(data.wallet);
  if (!await chain.signature(owner, message, request.signature, snapshot)) return null;
  if (!await chain.entitlement(owner, data.label, snapshot)) return null;
  await validatePublicKey(data.publicKey);
  return { ...data, registeredAt: request.issuedAt, proof: hashMessage(message) };
}
