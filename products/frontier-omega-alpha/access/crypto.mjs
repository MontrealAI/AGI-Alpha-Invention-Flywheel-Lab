import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';

const tagLength = 16;
const utf8 = value => Buffer.from(JSON.stringify(value), 'utf8');
const encode = value => value.toString('base64url');
const decode = value => Buffer.from(value, 'base64url');
const payloadAAD = ({ id, version, epoch, format }) => utf8(['frontier-omega-alpha:v1', id, version, epoch, format]);
const keyAAD = ({ id, version, epoch, format }) => utf8(['frontier-omega-alpha:key:v1', id, version, epoch, format]);

function seal(key, plaintext, aad) {
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', key, iv, { authTagLength: tagLength });
  cipher.setAAD(aad);
  const body = Buffer.concat([cipher.update(plaintext), cipher.final(), cipher.getAuthTag()]);
  return { iv: encode(iv), body: encode(body) };
}

function open(key, box, aad) {
  const iv = decode(box.iv);
  const bytes = decode(box.body);
  if (iv.length !== 12 || bytes.length < tagLength) throw Error('Invalid envelope');
  const cipher = createDecipheriv('aes-256-gcm', key, iv, { authTagLength: tagLength });
  cipher.setAAD(aad);
  cipher.setAuthTag(bytes.subarray(-tagLength));
  return Buffer.concat([cipher.update(bytes.subarray(0, -tagLength)), cipher.final()]);
}

export function encryptAsset(meta, plaintext, wrappingKey) {
  const contentKey = randomBytes(32);
  try {
    return { ...meta, payload: seal(contentKey, plaintext, payloadAAD(meta)), wrapped: seal(wrappingKey, contentKey, keyAAD(meta)) };
  } finally {
    contentKey.fill(0);
  }
}

export function releaseKey(envelope, wrappingKey) {
  return open(wrappingKey, envelope.wrapped, keyAAD(envelope));
}

export function rotateAsset(envelope, oldKey, newKey, epoch) {
  const contentKey = releaseKey(envelope, oldKey);
  try {
    const plaintext = open(contentKey, envelope.payload, payloadAAD(envelope));
    try {
      const { id, version, format } = envelope;
      return encryptAsset({ id, version, epoch, format }, plaintext, newKey);
    } finally {
      plaintext.fill(0);
    }
  } finally {
    contentKey.fill(0);
  }
}

export function decryptAsset(envelope, contentKey) {
  return open(contentKey, envelope.payload, payloadAAD(envelope));
}

export function rewrapAsset(envelope, oldKey, newKey) {
  const contentKey = releaseKey(envelope, oldKey);
  try {
    return { ...envelope, wrapped: seal(newKey, contentKey, keyAAD(envelope)) };
  } finally {
    contentKey.fill(0);
  }
}
