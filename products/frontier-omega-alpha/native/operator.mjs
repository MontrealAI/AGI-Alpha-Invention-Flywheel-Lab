import { randomBytes } from 'node:crypto';
import { mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { privateFile, privatePath } from '../access/store.mjs';
import { encryptAsset, rewrapAsset } from '../access/crypto.mjs';
import { maximumAssetBytes, validateRecord, validId, validVersion } from '../access/records.mjs';
import { assertRecord, CIPHERTEXT_FORMAT, DESTINATION, fromBase64, hash, MAX_LIBRARY_BYTES } from './protocol.mjs';
import { advance, initialState } from './issue.mjs';
import { Mainnet } from '../access/chain.mjs';
import { boundedRpc, readFinalized } from './intake.mjs';
import { checkpointEnvelopeBytes, openState, sealState } from './state.mjs';

const [command, ...args] = process.argv.slice(2);
process.umask(0o077);

function readJson(path, maximum) {
  if (!statSync(path).isFile() || statSync(path).size > maximum) throw Error('Publisher input exceeds the supported size');
  return JSON.parse(readFileSync(path, 'utf8'));
}

function writeJson(path, value, maximum) {
  const json = JSON.stringify(value) + '\n';
  if (Buffer.byteLength(json) > maximum) throw Error('Publisher output exceeds the supported size');
  writeFileSync(path, json, { flag: 'wx', mode: 0o600 });
}

function master(name = 'FRONTIER_ALPHA_PUBLISH_KEY') {
  const key = fromBase64(process.env[name], 32);
  if (key.length !== 32) throw Error('Expected a 256-bit publisher key');
  return Buffer.from(key);
}

async function run(key, catalogPath, previousPath, publicPath, output) {
  const catalog = readJson(catalogPath, MAX_LIBRARY_BYTES);
  let state;
  if (previousPath === '-') {
    const height = Number(process.env.FRONTIER_ALPHA_ANCHOR_HEIGHT);
    const blockHash = process.env.FRONTIER_ALPHA_ANCHOR_HASH;
    if (!Number.isSafeInteger(height) || height < 1 || !hash(blockHash)) throw Error('Missing approved chain anchor');
    state = initialState({ height, hash: blockHash, offset: null });
  } else {
    state = openState(readJson(previousPath, checkpointEnvelopeBytes), key, readJson(publicPath, MAX_LIBRARY_BYTES));
  }
  const revoked = readJson(new URL('./revoked-enrollments.json', import.meta.url), 96 * 1024);
  const next = await advance({ rpc: boundedRpc(process.env.FRONTIER_ALPHA_RPC), state, catalog, revoked, masterKey: key });
  mkdirSync(privatePath(output), { mode: 0o700 });
  writeJson(join(output, 'state.json'), sealState(next.state, key), checkpointEnvelopeBytes);
  writeJson(join(output, 'library.json'), next.library, MAX_LIBRARY_BYTES);
  writeJson(join(output, 'result.json'), { changed: next.changed, height: next.state.cursor.height }, 512);
}

let key;
let nextKey;
try {
  if (command === 'keygen' && args.length === 1) {
    writeFileSync(privatePath(args[0]), randomBytes(32).toString('base64url') + '\n', { flag: 'wx', mode: 0o600 });
    console.log('Created a publisher key file. Keep it outside Git history.');
  } else if (command === 'preflight' && args.length === 0) {
    const rpc = boundedRpc(process.env.FRONTIER_ALPHA_RPC);
    const chain = new Mainnet(rpc);
    const finalized = await readFinalized(rpc);
    const sample = '0x46524f4e54494552';
    const echoed = await rpc('eth_call', [{ to: DESTINATION, value: '0x0', data: sample }, 'finalized']);
    if (echoed !== sample) throw Error('Ethereum RPC identity precompile verification failed');
    const token = await chain.tokenIdentity(await chain.snapshot());
    console.log(JSON.stringify({ anchorHeight: finalized.height, anchorHash: finalized.hash, identityPrecompile: DESTINATION, token }));
  } else {
    key = master();
    if (command === 'seal' && args.length === 4) {
      const [id, version, privateRecord, output] = args;
      if (!validId(id) || !validVersion(Number(version))) throw Error('Invalid release version');
      const path = privateFile(privatePath(privateRecord));
      if (statSync(path).size > maximumAssetBytes) throw Error('Private record exceeds the supported size');
      const source = readFileSync(path);
      try {
        const record = validateRecord(JSON.parse(source));
        const result = encryptAsset({ id, version: Number(version), epoch: randomBytes(16).toString('hex'),
          format: CIPHERTEXT_FORMAT }, source, key);
        writeJson(privatePath(output), { ...result, section: record.section }, 512 * 1024);
      } finally {
        source.fill(0);
      }
      console.log('Created a sealed release record.');
    } else if (command === 'rekey' && args.length === 4) {
      const [previous, publicPath, catalogPath, output] = args;
      nextKey = master('FRONTIER_ALPHA_NEXT_PUBLISH_KEY');
      if (key.equals(nextKey)) throw Error('Expected two distinct publisher keys');
      const state = openState(readJson(previous, checkpointEnvelopeBytes), key, readJson(publicPath, MAX_LIBRARY_BYTES));
      const catalog = readJson(catalogPath, MAX_LIBRARY_BYTES).map(item => {
        assertRecord(item, true);
        return rewrapAsset(item, key, nextKey);
      });
      mkdirSync(privatePath(output), { mode: 0o700 });
      writeJson(join(output, 'state.json'), sealState(state, nextKey), checkpointEnvelopeBytes);
      writeJson(join(output, 'catalog.json'), catalog, MAX_LIBRARY_BYTES);
      console.log('Prepared a new encrypted publisher checkpoint and wrapped release catalog.');
    } else if (command === 'run' && args.length === 4) {
      await run(key, ...args);
      console.log('Finished a bounded enrollment checkpoint.');
    } else {
      throw Error('Use keygen, preflight, seal, rekey or run');
    }
  }
} catch (error) {
  // RPC bodies, wallet identifiers, private records and credentials must not enter public logs.
  const approved = /^(?:Use |Expected |Invalid release version|Private record exceeds|Missing approved|Publisher checkpoint and|A published|Ethereum RPC|Invalid Ethereum RPC|Mainnet finalized|Finalized enrollment|Entitlement block ceased)/;
  console.error(approved.test(error.message) ? error.message : 'GitHub publisher stopped before state commit.');
  process.exitCode = 1;
} finally {
  key?.fill(0);
  nextKey?.fill(0);
}
