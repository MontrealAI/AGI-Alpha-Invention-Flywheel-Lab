import { createServer } from 'node:http';
import { pathToFileURL } from 'node:url';
import { getAddress, ZeroAddress } from 'ethers';
import { SiweMessage } from 'siwe';
import { Mainnet, clubLabel, httpRpc } from './chain.mjs';
import { Store, opaqueToken, readKey } from './store.mjs';
import { releaseKey, decryptAsset } from './crypto.mjs';
import { validId, validVersion, validateRecord } from './records.mjs';

const noncePattern = /^[a-f0-9]{32}$/;
const signaturePattern = /^0x(?:[a-f0-9]{2}){1,4096}$/i;
const routes = new Set(['challenge', 'verify', 'session', 'catalog', 'open', 'logout']);
const challengeLifetime = 2 * 60_000;
const sessionLifetime = 5 * 60_000;

class RequestError extends Error {
  constructor(status, code) {
    super(code);
    this.status = status;
  }
}

function configuredSite(value, localHttp) {
  const url = new URL(value);
  const isLocal = localHttp && ['127.0.0.1', 'localhost'].includes(url.hostname) && url.protocol === 'http:';
  if ((!isLocal && url.protocol !== 'https:') || url.search || url.hash || url.username || url.password) {
    throw Error('A canonical front-end HTTPS URL is required');
  }
  return url;
}

async function parseBody(request, fields = []) {
  if (request.headers['content-type']?.split(';')[0] !== 'application/json') {
    throw new RequestError(415, 'invalid_request');
  }
  const chunks = [];
  let length = 0;
  for await (const chunk of request) {
    length += chunk.length;
    if (length > 9000) throw new RequestError(413, 'invalid_request');
    chunks.push(chunk);
  }
  try {
    const value = JSON.parse(Buffer.concat(chunks));
    if (!value || Array.isArray(value) || typeof value !== 'object' ||
        Object.keys(value).length !== fields.length || !fields.every(key => Object.hasOwn(value, key))) throw Error();
    return value;
  } catch {
    throw new RequestError(400, 'invalid_request');
  }
}

function bearer(request) {
  const match = /^Bearer ([a-f0-9]{64})$/.exec(request.headers.authorization ?? '');
  if (!match) throw new RequestError(401, 'session_required');
  return match[1];
}

function rateLimit(clock) {
  let window = -1;
  const counts = new Map();
  return (group, ip, globalLimit, ipLimit) => {
    const current = Math.floor(clock() / 60_000);
    if (current !== window) {
      window = current;
      counts.clear();
    }
    const global = (counts.get(group) ?? 0) + 1;
    counts.set(group, global);
    if (global > globalLimit) throw new RequestError(429, 'rate_limit');
    const key = group + '/' + ip;
    const count = (counts.get(key) ?? 0) + 1;
    counts.set(key, count);
    if (count > ipLimit) throw new RequestError(429, 'rate_limit');
  };
}

function send(response, status, value) {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  response.end(JSON.stringify(value));
}

export function createAccessServer({ siteUrl, localHttp = false, chain, store, wrappingKey, clock = Date.now }) {
  const site = configuredSite(siteUrl, localHttp);
  const limit = rateLimit(clock);
  async function authorize(token) {
    const session = store.session(token, clock());
    if (!session) throw new RequestError(401, 'session_required');
    const snapshot = await chain.snapshot();
    if (session.contract_signature &&
        !await chain.signature(session.address, session.message, session.contract_signature, snapshot, true)) {
      store.revoke(token);
      throw new RequestError(403, 'ineligible');
    }
    const path = await chain.entitlement(session.address, session.label, snapshot);
    if (!path) {
      store.revoke(token);
      throw new RequestError(403, 'ineligible');
    }
    // Check once more after async reads in case the session expired or was revoked meanwhile.
    if (!store.session(token, clock())) throw new RequestError(401, 'session_required');
    return { path, expiresAt: session.expires, block: snapshot.number };
  }

  async function dispatch(route, request) {
    const ip = request.socket.remoteAddress;
    if (route === 'challenge') {
      limit('challenge', ip, 100, 40);
      const { address, label, language } = await parseBody(request, ['address', 'label', 'language']);
      if (!['en', 'fr'].includes(language)) throw new RequestError(400, 'invalid_request');
      let wallet;
      let club;
      try {
        if (typeof address !== 'string' || !/^0x[a-f0-9]{40}$/i.test(address)) throw Error();
        wallet = getAddress(address);
        if (wallet === ZeroAddress) throw Error();
        club = label === null ? null : clubLabel(label);
      } catch {
        throw new RequestError(400, 'invalid_identity');
      }
      const now = clock();
      const expires = now + challengeLifetime;
      const nonce = opaqueToken(16);
      const message = new SiweMessage({
        scheme: site.protocol.slice(0, -1),
        domain: site.host,
        address: wallet,
        statement: language === 'fr'
          ? 'Connectez-vous a FRONTIER OMEGA ALPHA. Cette signature ne permet aucune transaction.'
          : 'Sign in to FRONTIER OMEGA ALPHA. This signature does not authorize a transaction.',
        uri: site.href,
        version: '1',
        chainId: 1,
        nonce,
        issuedAt: new Date(now).toISOString(),
        expirationTime: new Date(expires).toISOString(),
        resources: [club ? 'urn:frontier-omega-alpha:club:' + club + '.club.agi.eth' : 'urn:frontier-omega-alpha:token']
      }).prepareMessage();
      store.challenge(nonce, wallet, club, message, expires);
      return { nonce, message };
    }
    if (route === 'verify') {
      limit('verify', ip, 100, 40);
      const { nonce, signature } = await parseBody(request, ['nonce', 'signature']);
      if (typeof nonce !== 'string' || typeof signature !== 'string' ||
          !noncePattern.test(nonce) || !signaturePattern.test(signature)) {
        throw new RequestError(400, 'invalid_request');
      }
      const challenge = store.consume(nonce, clock());
      if (!challenge) throw new RequestError(401, 'challenge_expired');
      const snapshot = await chain.snapshot();
      const type = await chain.signature(challenge.address, challenge.message, signature, snapshot);
      if (!type) throw new RequestError(401, 'invalid_signature');
      const path = await chain.entitlement(challenge.address, challenge.label, snapshot);
      if (!path) throw new RequestError(403, 'ineligible');
      if (!store.compatibleKey(wrappingKey.epoch)) throw Error('Key epoch unavailable');
      const now = clock();
      const expiresAt = now + sessionLifetime;
      const token = store.issue(challenge, type === 'contract' ? signature : null, now, expiresAt);
      if (!token) throw new RequestError(401, 'challenge_expired');
      return { token, path, expiresAt, block: snapshot.number };
    }

    const token = bearer(request);
    if (route === 'logout') {
      await parseBody(request);
      store.revoke(token);
      return { locked: true };
    }
    const data = await parseBody(request, route === 'open' ? ['id', 'version'] : []);
    if (route === 'open' && (!validId(data.id) || !validVersion(data.version))) {
      throw new RequestError(400, 'invalid_request');
    }
    limit('protected', ip, 480, 240);
    const access = await authorize(token);
    if (!store.compatibleKey(wrappingKey.epoch)) throw Error('Key epoch unavailable');
    if (route === 'session') return access;
    if (route === 'catalog') return { ...access, entries: store.catalog(wrappingKey.epoch) };
    const envelope = store.asset(data.id, data.version, wrappingKey.epoch);
    if (!envelope) throw new RequestError(404, 'release_unavailable');
    const key = releaseKey(envelope, wrappingKey.key);
    try {
      const { wrapped, ...ciphertext } = envelope;
      if (ciphertext.format === 'research-json.server.v1') {
        const bytes = decryptAsset(envelope, key);
        try {
          return { ...access, record: validateRecord(JSON.parse(bytes)) };
        } finally {
          bytes.fill(0);
        }
      }
      return { ...access, ciphertext, key: key.toString('base64url') };
    } finally {
      key.fill(0);
    }
  }

  let pending = 0;
  const server = createServer({ requestTimeout: 15000, headersTimeout: 10000, maxHeaderSize: 8192 }, async (request, response) => {
    response.setHeader('Cache-Control', 'no-store, private, max-age=0');
    response.setHeader('Pragma', 'no-cache');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('Referrer-Policy', 'no-referrer');
    response.setHeader('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'");
    response.setHeader('Vary', 'Origin');
    if (request.headers.origin !== site.origin) return send(response, 403, { error: 'origin_denied' });
    response.setHeader('Access-Control-Allow-Origin', site.origin);
    const route = /^\/v1\/([a-z]+)$/.exec(request.url)?.[1];
    if (!routes.has(route)) return send(response, 404, { error: 'not_found' });
    if (request.method === 'OPTIONS') {
      response.writeHead(204, {
        'Access-Control-Allow-Methods': 'POST',
        'Access-Control-Allow-Headers': 'authorization, content-type',
        'Access-Control-Max-Age': '120'
      });
      return response.end();
    }
    if (request.method !== 'POST') return send(response, 405, { error: 'method_denied' });
    if (pending >= 48) return send(response, 429, { error: 'rate_limit' });
    pending += 1;
    try {
      send(response, 200, await dispatch(route, request));
    } catch (error) {
      if (error instanceof RequestError) send(response, error.status, { error: error.message });
      else send(response, 503, { error: 'verification_unavailable' });
    } finally {
      pending -= 1;
    }
  });
  const timer = setInterval(() => {
    try {
      store.prune(clock());
    } catch {
      // A failed maintenance pass never makes expired rows valid.
    }
  }, 60_000).unref();
  server.on('close', () => clearInterval(timer));
  return server;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.umask(0o077);
  try {
    const chain = new Mainnet(httpRpc(process.env.FRONTIER_RPC_URL));
    const store = new Store(process.env.FRONTIER_STATE_DIR);
    const wrappingKey = readKey(process.env.FRONTIER_KEK_FILE);
    const port = Number(process.env.FRONTIER_PORT ?? '8787');
    if (!Number.isInteger(port) || port < 1024 || port > 65535) throw Error('Invalid port');
    const server = createAccessServer({
      siteUrl: process.env.FRONTIER_SITE_URL, chain, store, wrappingKey,
      localHttp: process.env.FRONTIER_LOCAL_HTTP === '1'
    });
    server.on('error', () => {
      console.error('Access service could not listen.');
      process.exitCode = 1;
    });
    server.listen(port, '127.0.0.1', () => console.log('Access service listening on loopback.'));
    for (const signal of ['SIGTERM', 'SIGINT']) {
      process.once(signal, () => server.close(() => {
        store.revokeAll();
        store.close();
        wrappingKey.key.fill(0);
      }));
    }
  } catch {
    console.error('Access service configuration is invalid.');
    process.exitCode = 1;
  }
}
