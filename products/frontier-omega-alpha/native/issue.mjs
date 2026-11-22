import { getAddress } from 'ethers';
import { Mainnet } from '../access/chain.mjs';
import { decryptAsset, releaseKey } from '../access/crypto.mjs';
import { assertLibrary, assertRecord, enrollmentId, hash, LIBRARY_SCHEMA, MAX_MEMBERS, MAX_RELEASES, releaseTag, SIGNED_LIBRARY_SCHEMA } from './protocol.mjs';
import { validateRecord } from '../access/records.mjs';
import { encapsulate, validatePublicKey } from './hpke.mjs';
import { quantity, scanEnrollments } from './intake.mjs';
import { authenticateSignedEnrollment } from './signed-enrollment.mjs';

export function initialState(cursor) {
  return { cursor, active: {}, outcomes: {}, publication: null, releases: {} };
}

export async function advance({
  rpc, state, catalog, masterKey, revoked = [], now = Date.now, scanner = scanEnrollments,
  signedRequests = null, readerOrigin
}) {
  if (!Array.isArray(catalog) || !catalog.length || catalog.length > MAX_RELEASES) throw Error('Expected approved encrypted releases');
  if (!Array.isArray(revoked) || revoked.length > 1024 || !revoked.every(hash)) throw Error('Invalid enrollment revocation list');
  const revokedIds = new Set(revoked);
  const updated = structuredClone(state);
  const signed = signedRequests !== null;
  const schema = signed ? SIGNED_LIBRARY_SCHEMA : LIBRARY_SCHEMA;
  const proofField = signed ? 'proof' : 'tx';
  if (state.publication && state.publication.schema !== schema) throw Error('Publisher enrollment format changed');
  if (signed && (!Array.isArray(signedRequests) || signedRequests.length > 48)) throw Error('Invalid approved enrollment batch');
  function recordOutcome(id, candidate, result) {
    if (Object.hasOwn(updated.outcomes, id)) delete updated.outcomes[id];
    updated.outcomes[id] = { [proofField]: candidate[proofField], state: result, keys: {} };
    const oldest = Object.keys(updated.outcomes);
    if (oldest.length > MAX_MEMBERS) delete updated.outcomes[oldest[0]];
  }
  const records = [];
  const tags = new Set();
  const identifiers = new Set();
  for (const item of catalog) {
    assertRecord(item, true);
    // Authenticate the approved sealed catalog even when the active registry is empty.
    const approvedKey = releaseKey(item, masterKey);
    try {
      const plaintext = decryptAsset(item, approvedKey);
      try {
        const data = validateRecord(JSON.parse(plaintext));
        if (data.section !== item.section) throw Error('Approved release section disagrees with ciphertext');
      } finally {
        plaintext.fill(0);
      }
    } finally {
      approvedKey.fill(0);
    }
    const { wrapped, ...record } = item;
    record.tag = await releaseTag(record);
    const name = item.id + ':' + item.version;
    const old = updated.releases[name];
    if (identifiers.has(name) || (old && old !== record.tag)) throw Error('A published release version cannot be replaced');
    identifiers.add(name);
    tags.add(record.tag);
    records.push(record);
  }
  if (new Set([...Object.keys(updated.releases), ...identifiers]).size > 1024) {
    throw Error('The release version registry requires an authorized archival checkpoint');
  }

  const batch = signed ? { cursor: updated.cursor, events: [], caughtUp: true } : await scanner(rpc, updated.cursor, { now });
  const chain = new Mainnet(rpc, now);
  const snapshot = await chain.snapshot();
  const observed = new Map();

  if (signed) {
    for (let start = 0; start < signedRequests.length; start += 6) {
      const verified = await Promise.all(signedRequests.slice(start, start + 6).map(request =>
        authenticateSignedEnrollment(request, readerOrigin, chain, snapshot)));
      for (const event of verified) {
        if (!event) continue;
        observed.set(event.wallet + ':' + (event.label ?? ''), Promise.resolve(true));
        batch.events.push(event);
      }
    }
    batch.events.sort((a, b) => a.registeredAt - b.registeredAt || a.proof.localeCompare(b.proof));
  }
  updated.cursor = batch.cursor;

  function current(event) {
    const id = event.wallet + ':' + (event.label ?? '');
    if (!observed.has(id)) observed.set(id, chain.entitlement(getAddress(event.wallet), event.label, snapshot));
    return observed.get(id);
  }

  const previousMembers = Object.values(updated.active);
  for (let start = 0; start < previousMembers.length; start += 6) {
    const group = previousMembers.slice(start, start + 6);
    const entitled = await Promise.all(group.map(current));
    for (let i = 0; i < group.length; i++) {
      const member = group[i];
      if (entitled[i] && !revokedIds.has(member.id)) continue;
      recordOutcome(member.id, member, 'revoked');
      delete updated.active[member.wallet];
    }
  }

  // Prepare at most six wallet checks at a time; process verified events in chain order.
  for (let start = 0; start < batch.events.length; start += 6) {
    const group = batch.events.slice(start, start + 6);
    const entitled = await Promise.all(group.map(current));
    for (let i = 0; i < group.length; i++) {
      const event = group[i];
      const id = await enrollmentId(event.wallet, event.nonce);
      if (revokedIds.has(id)) {
        recordOutcome(id, event, 'revoked');
        continue;
      }
      const previous = updated.active[event.wallet];
      if (signed && previous && (event.registeredAt < previous.registeredAt ||
          (event.registeredAt === previous.registeredAt && event.proof <= previous.proof))) continue;
      const recentNonces = (previous?.usedNonces ?? []).filter(nonce => nonce.expiresAt >= event.registeredAt);
      if (recentNonces.some(nonce => nonce.value === event.nonce) || Object.hasOwn(updated.outcomes, id)) continue;
      if (!entitled[i]) {
        recordOutcome(id, event, 'denied');
        continue;
      }
      if ((!previous && Object.keys(updated.active).length >= MAX_MEMBERS) || recentNonces.length >= 32) {
        recordOutcome(id, event, 'capacity');
        continue;
      }
      if (previous) recordOutcome(previous.id, previous, 'superseded');
      updated.active[event.wallet] = { ...event, id, state: 'eligible', keys: {}, usedNonces: [...recentNonces, { value: event.nonce, expiresAt: event.expiresAt }] };
    }
  }

  const members = Object.values(updated.active);
  for (const member of members) {
    member.keys = Object.fromEntries(Object.entries(member.keys).filter(([tag]) => tags.has(tag)));
    const recipient = await validatePublicKey(member.publicKey);
    for (let index = 0; index < records.length; index++) {
      const { tag } = records[index];
      if (Object.hasOwn(member.keys, tag)) continue;
      const key = releaseKey(catalog[index], masterKey);
      try {
        member.keys[tag] = await encapsulate(recipient, key, member[proofField], tag, schema);
      } finally {
        key.fill(0);
      }
    }
    member.state = Object.keys(member.keys).length ? 'provisioned' : 'eligible';
  }

  const canonical = await rpc('eth_getBlockByNumber', [quantity(BigInt(snapshot.number)), false]);
  if (!hash(canonical?.hash) || canonical.hash !== snapshot.ref.blockHash || now() / 1_000 - snapshot.timestamp > 90) {
    throw Error('Entitlement block ceased to be canonical or fresh');
  }
  const anchor = await rpc('eth_getBlockByNumber', [quantity(batch.cursor.height), false]);
  if (anchor?.hash !== batch.cursor.hash) throw Error('Finalized enrollment checkpoint changed during provisioning');

  for (const record of records) updated.releases[record.id + ':' + record.version] = record.tag;
  const recipients = { ...updated.outcomes };
  for (const member of members) recipients[member.id] = { [proofField]: member[proofField], state: member.state, keys: member.keys };
  const publication = { schema, updatedAt: Math.floor(now() / 1_000), openEnrollment: batch.caughtUp === true && members.length < MAX_MEMBERS, records, recipients };
  assertLibrary(publication);
  // Refresh the public heartbeat hourly and on meaningful library changes.
  const old = state.publication;
  const meaningful = !old || JSON.stringify([old.openEnrollment, old.records, old.recipients]) !== JSON.stringify([publication.openEnrollment, records, recipients]);
  const refreshed = meaningful || publication.updatedAt - old.updatedAt >= 3600;
  updated.publication = refreshed ? publication : old;
  return { state: updated, library: updated.publication, changed: refreshed };
}
