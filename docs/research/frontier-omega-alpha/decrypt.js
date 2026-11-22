const readBytes = value => Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), byte => byte.charCodeAt(0));

export async function decryptRelease(ciphertext, keyValue, entry) {
  const { id, version, epoch, format, payload } = ciphertext;
  if (id !== entry.id || version !== entry.version || !/^[a-f0-9]{32}$/.test(epoch) || format !== 'research-json.browser.v1') {
    throw Error('Incorrect release metadata');
  }
  const rawKey = readBytes(keyValue);
  if (rawKey.length !== 32) throw Error('Incorrect content key');
  try {
    const key = await crypto.subtle.importKey('raw', rawKey, 'AES-GCM', false, ['decrypt']);
    const iv = readBytes(payload.iv);
    if (iv.length !== 12) throw Error('Incorrect release nonce');
    const additionalData = new TextEncoder().encode(JSON.stringify(['frontier-omega-alpha:v1', id, version, epoch, format]));
    const decrypted = await crypto.subtle.decrypt({ name: 'AES-GCM', iv, additionalData, tagLength: 128 }, key, readBytes(payload.body));
    try {
      return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(decrypted));
    } finally {
      new Uint8Array(decrypted).fill(0);
    }
  } finally {
    rawKey.fill(0);
  }
}
