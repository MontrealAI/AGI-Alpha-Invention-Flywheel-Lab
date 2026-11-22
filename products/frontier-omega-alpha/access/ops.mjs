import { openSync, closeSync, readFileSync, writeFileSync, statSync } from 'node:fs';
import { Store, readKey, opaqueToken, privatePath, privateFile } from './store.mjs';
import { encryptAsset, rotateAsset } from './crypto.mjs';
import { validateRecord, validId, validVersion, maximumAssetBytes } from './records.mjs';
import { Mainnet, httpRpc } from './chain.mjs';

process.umask(0o077);
const [command, first, second, third, fourth] = process.argv.slice(2);
let store;
let key;
let nextKey;

try {
  if (command === 'keygen' && first && !second) {
    const file = openSync(privatePath(first), 'wx', 0o600);
    try {
      writeFileSync(file, JSON.stringify({ epoch: opaqueToken(16), key: opaqueToken() }));
    } finally {
      closeSync(file);
    }
    console.log('Created private wrapping key.');
  } else if (command === 'chain-check' && !first) {
    const chain = new Mainnet(httpRpc(process.env.FRONTIER_RPC_URL));
    const snapshot = await chain.snapshot();
    console.log(JSON.stringify(await chain.tokenIdentity(snapshot)));
  } else {
    store = new Store(process.env.FRONTIER_STATE_DIR);
    if (command === 'revoke-all' && !first) {
      store.revokeAll();
      console.log('Revoked all sessions and challenges.');
    } else if (command === 'withdraw' && validId(first) && validVersion(Number(second)) && !third) {
      console.log(JSON.stringify({ withdrawn: store.withdraw(first, Number(second)) }));
    } else if (command === 'rotate' && first && !second) {
      key = readKey(process.env.FRONTIER_KEK_FILE);
      nextKey = readKey(first);
      if (key.key.equals(nextKey.key)) throw Error('Rotation needs a newly generated wrapping key');
      const result = store.rotate(key.epoch, nextKey.epoch, envelope => rotateAsset(envelope, key.key, nextKey.key, nextKey.epoch));
      console.log(JSON.stringify({ rotated: result, accessRevoked: true }));
    } else if (['publish', 'publish-server'].includes(command) && validId(first) && validVersion(Number(second)) && third && !fourth) {
      key = readKey(process.env.FRONTIER_KEK_FILE);
      const path = privateFile(privatePath(third));
      if (statSync(path).size > maximumAssetBytes) throw Error('Asset exceeds the release size limit');
      const data = readFileSync(path);
      try {
        const record = validateRecord(JSON.parse(data));
        const format = command === 'publish' ? 'research-json.browser.v1' : 'research-json.server.v1';
        const box = encryptAsset({ id: first, version: Number(second), epoch: key.epoch, format }, data, key.key);
        store.insert(box, record.section);
      } finally {
        data.fill(0);
      }
      console.log('Stored encrypted research release.');
    } else {
      throw Error('Use keygen, chain-check, publish, publish-server, withdraw, rotate or revoke-all');
    }
  }
} catch {
  console.error('Operator command failed. Check input, file permissions, configured key epoch and RPC availability.');
  process.exitCode = 1;
} finally {
  store?.close();
  key?.key.fill(0);
  nextKey?.key.fill(0);
}
