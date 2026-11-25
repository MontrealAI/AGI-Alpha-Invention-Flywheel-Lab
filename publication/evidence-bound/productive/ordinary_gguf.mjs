import {mkdtempSync, readFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {dirname, join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {performance} from 'node:perf_hooks';

const [packagePath, name, prefix, python, fileSizeCap] = process.argv.slice(2);
const {gguf} = await import(pathToFileURL(packagePath).href);
const bin = dirname(fileURLToPath(import.meta.url));
const source = JSON.parse(readFileSync(join(bin, 'REGISTRATION.json'), 'utf8')).sources[name];
const url = `https://huggingface.co/${source.repository}/resolve/${source.revision}/${source.filename}`;
const relevant = /^(?:general\.(?:architecture|alignment)|split\.count|[\w-]+\.(?:block_count|context_length|embedding_length|attention\.(?:head_count(?:_kv)?|key_length|value_length|sliding_window)))$/u;
const captures = [];
let transferred = 0;
const folder = mkdtempSync(join(tmpdir(), 'frontier-gguf-control-'));

function receive(input, options) {
  if (input !== url) throw new Error('the comparator must observe the same immutable object');
  const [, first, last] = /^bytes=(\d+)-(\d+)$/u.exec(options.headers.Range);
  const length = Number(last) - Number(first) + 1;
  if (length <= 0 || transferred + length > Number(fileSizeCap)) throw new Error('comparator acquisition exceeded the registered evidence limit');
  const output = join(folder, String(captures.length));
  const request = spawnSync(python, [join(bin, 'fetch_gguf_range.py'), name, first, last, output], {encoding:'utf8'});
  if (request.status !== 0) throw new Error(`approved source range ${first}-${last} could not be acquired`);
  const result = JSON.parse(request.stdout);
  captures.push(result);
  transferred += result.response_body_bytes;
  return new Response(readFileSync(output), {status:206, headers:{'content-range':result.content_range}});
}

function exactNumber(input) {
  if (Array.isArray(input)) return input.map(exactNumber);
  if (typeof input !== 'bigint') return input;
  const value = Number(input);
  if (!Number.isSafeInteger(value)) throw new Error('unsupported integer above exact JSON range');
  return value;
}

try {
  const started = performance.now();
  const raw = prefix === '-' ? await gguf(url, {fetch:receive}) : await gguf(prefix, {allowLocalFile:true});
  if (!raw.littleEndian || raw.metadata.version !== 3) throw new Error('unexpected comparator object version');
  const metadata = Object.fromEntries(
    Object.entries(raw.metadata).filter(([key]) => relevant.test(key)).map(([key, val]) => [key, exactNumber(val)]),
  );
  const tensors = raw.tensorInfos.map(item => ({name:item.name, dimensions:exactNumber(item.shape),
    dtype:item.dtype, offset:exactNumber(item.offset)}));
  process.stdout.write(JSON.stringify({
    index:{metadata, tensors, tensor_data_offset:exactNumber(raw.tensorDataOffset)},
    captures, wire_body_bytes:transferred, routine_wall_seconds:(performance.now() - started) / 1000,
  }));
} catch (error) {
  process.stdout.write(JSON.stringify({error:error.message, captures, wire_body_bytes:transferred}));
} finally {
  rmSync(folder, {recursive:true, force:true});
}
