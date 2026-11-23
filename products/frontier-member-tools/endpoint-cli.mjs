import {readFile, stat} from 'node:fs/promises';
import {screen} from './endpoint-screen.mjs';
import {canonical} from './outcome-receipt.mjs';

const path = process.argv[2];
try {
  if (process.argv.length !== 3) throw Error('INPUT_FILE');
  const file = await stat(path);
  if (!file.isFile() || file.size > 256_000) throw Error('INPUT_FILE');
  const raw = await readFile(path, 'utf8');
  if (Buffer.byteLength(raw) > 256_000) throw Error('INPUT_FILE');
  console.log(canonical(screen(JSON.parse(raw))));
} catch (error) {
  console.error('Input rejected:', error instanceof SyntaxError ? 'JSON' : error.message);
  process.exitCode = 2;
}
