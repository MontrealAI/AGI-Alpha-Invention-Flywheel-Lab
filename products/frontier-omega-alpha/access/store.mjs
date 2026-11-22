import { createHash, randomBytes } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { closeSync, lstatSync, mkdirSync, openSync, readFileSync, realpathSync } from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repository = realpathSync(fileURLToPath(new URL('../../../', import.meta.url)));
const digest = token => createHash('sha256').update(token).digest('hex');
export const opaqueToken = (size = 32) => randomBytes(size).toString('hex');

export function privatePath(value) {
  if (typeof value !== 'string' || !isAbsolute(value)) throw Error('Use an absolute private path');
  const path = resolve(value);
  let ancestor = path;
  while (true) {
    try {
      const storage = realpathSync(ancestor);
      if ([path, storage].some(item => item === repository || item.startsWith(repository + '/'))) {
        throw Error('Private data must be outside the checkout');
      }
      return path;
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
      ancestor = dirname(ancestor);
    }
  }
}

export function privateFile(path) {
  const stat = lstatSync(path);
  if (!stat.isFile() || (stat.mode & 0o077) || stat.uid !== process.getuid()) {
    throw Error('Private file must be owner-only and regular');
  }
  return path;
}

export function readKey(path) {
  const info = JSON.parse(readFileSync(privateFile(privatePath(path)), 'utf8'));
  if (!/^[a-f0-9]{32}$/.test(info.epoch) || !/^[a-f0-9]{64}$/.test(info.key)) throw Error('Invalid key file');
  return { epoch: info.epoch, key: Buffer.from(info.key, 'hex') };
}

export class Store {
  constructor(directory) {
    const path = privatePath(directory);
    mkdirSync(path, { recursive: true, mode: 0o700 });
    const stat = lstatSync(path);
    if (!stat.isDirectory() || (stat.mode & 0o077) || stat.uid !== process.getuid()) {
      throw Error('Use an owner-only state directory');
    }
    const dbPath = join(path, 'frontier.sqlite');
    try {
      closeSync(openSync(dbPath, 'wx', 0o600));
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
    }
    privateFile(dbPath);
    this.db = new DatabaseSync(dbPath);
    this.db.exec(`
      PRAGMA journal_mode=WAL;
      PRAGMA busy_timeout=5000;
      PRAGMA secure_delete=ON;
      CREATE TABLE IF NOT EXISTS state (
        singleton INTEGER PRIMARY KEY CHECK (singleton=1), access_epoch INTEGER NOT NULL, kek_epoch TEXT
      );
      INSERT OR IGNORE INTO state VALUES (1, 1, NULL);
      CREATE TABLE IF NOT EXISTS challenges (
        nonce_hash TEXT PRIMARY KEY, address TEXT NOT NULL, label TEXT, message TEXT NOT NULL,
        expires INTEGER NOT NULL, access_epoch INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY, address TEXT NOT NULL, label TEXT, expires INTEGER NOT NULL,
        access_epoch INTEGER NOT NULL, message TEXT, contract_signature TEXT
      );
      CREATE TABLE IF NOT EXISTS releases (
        id TEXT NOT NULL, version INTEGER NOT NULL, section TEXT NOT NULL, active INTEGER NOT NULL,
        kek_epoch TEXT NOT NULL, wrap_nonce TEXT NOT NULL, envelope TEXT NOT NULL,
        PRIMARY KEY (id, version), UNIQUE (kek_epoch, wrap_nonce)
      );
    `);
  }

  close() {
    this.db.close();
  }

  transaction(work) {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const result = work();
      this.db.exec('COMMIT');
      return result;
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  prune(now) {
    this.db.prepare('DELETE FROM challenges WHERE expires <= ?').run(now);
    this.db.prepare('DELETE FROM sessions WHERE expires <= ?').run(now);
  }

  challenge(nonce, address, label, message, expires) {
    this.db.prepare('INSERT INTO challenges SELECT ?, ?, ?, ?, ?, access_epoch FROM state').run(
      digest(nonce), address, label, message, expires
    );
  }

  consume(nonce, now) {
    return this.db.prepare(`
      DELETE FROM challenges WHERE nonce_hash = ? AND expires > ?
        AND access_epoch = (SELECT access_epoch FROM state) RETURNING *
    `).get(digest(nonce), now);
  }

  issue(challenge, signature, now, expires) {
    const token = opaqueToken();
    const result = this.db.prepare(`
      INSERT INTO sessions SELECT ?, ?, ?, ?, access_epoch, ?, ? FROM state
        WHERE access_epoch = ? AND ? > ?
    `).run(digest(token), challenge.address, challenge.label, expires,
      signature ? challenge.message : null, signature, challenge.access_epoch, challenge.expires, now);
    return result.changes ? token : null;
  }

  session(token, now) {
    return this.db.prepare(`
      SELECT * FROM sessions WHERE token_hash = ? AND expires > ?
        AND access_epoch = (SELECT access_epoch FROM state)
    `).get(digest(token), now);
  }

  revoke(token) {
    this.db.prepare('DELETE FROM sessions WHERE token_hash = ?').run(digest(token));
  }

  revokeAll() {
    this.transaction(() => this.invalidate());
  }

  invalidate() {
    this.db.exec('UPDATE state SET access_epoch=access_epoch+1; DELETE FROM sessions; DELETE FROM challenges;');
  }

  compatibleKey(epoch) {
    const current = this.db.prepare('SELECT kek_epoch FROM state').get().kek_epoch;
    return current === null || current === epoch;
  }

  insert(envelope, section) {
    this.transaction(() => {
      if (!this.compatibleKey(envelope.epoch)) throw Error('Use the current wrapping key');
      this.db.prepare('UPDATE state SET kek_epoch=?').run(envelope.epoch);
      this.db.prepare('INSERT INTO releases VALUES (?, ?, ?, 1, ?, ?, ?)').run(
        envelope.id, envelope.version, section, envelope.epoch, envelope.wrapped.iv, JSON.stringify(envelope)
      );
    });
  }

  catalog(epoch) {
    return this.db.prepare(`
      SELECT id, version, section FROM releases WHERE active=1 AND kek_epoch=?
        ORDER BY section, id, version DESC
    `).all(epoch);
  }

  asset(id, version, epoch) {
    const row = this.db.prepare('SELECT envelope FROM releases WHERE id=? AND version=? AND active=1 AND kek_epoch=?')
      .get(id, version, epoch);
    return row ? JSON.parse(row.envelope) : null;
  }

  withdraw(id, version) {
    return this.db.prepare('UPDATE releases SET active=0 WHERE id=? AND version=? AND active=1').run(id, version).changes;
  }

  rotate(oldEpoch, newEpoch, rotate) {
    if (oldEpoch === newEpoch) throw Error('Use a new wrapping key');
    return this.transaction(() => {
      if (!this.compatibleKey(oldEpoch)) throw Error('Use the current wrapping key');
      const items = this.db.prepare('SELECT * FROM releases WHERE active=1').all();
      for (const item of items) {
        if (item.kek_epoch !== oldEpoch) throw Error('Active release uses another key epoch');
        const envelope = rotate(JSON.parse(item.envelope));
        this.db.prepare('UPDATE releases SET kek_epoch=?, wrap_nonce=?, envelope=? WHERE id=? AND version=?')
          .run(newEpoch, envelope.wrapped.iv, JSON.stringify(envelope), item.id, item.version);
      }
      this.db.prepare('UPDATE state SET kek_epoch=?').run(newEpoch);
      this.invalidate();
      return items.length;
    });
  }
}
