import { copyFile, lstat, mkdir, readFile, writeFile } from 'node:fs/promises';
import { basename, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { assertLibrary, MAX_LIBRARY_BYTES, releaseTag } from './protocol.mjs';

const source = fileURLToPath(new URL('../../../docs/research/frontier-omega-alpha/', import.meta.url));
const entry = fileURLToPath(new URL('./reader.mjs', import.meta.url));
const sharedHost = 'montrealai.github.io';
const publicData = 'https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/library.json';
const staticFiles = ['index.html', 'fr.html', 'frontier.css', 'frontier.js', 'decrypt.js', 'carina.webp'];
const pageFiles = ['index.html', 'fr.html'];

export function readerAddress(value) {
  const reader = new URL(value);
  if (reader.protocol !== 'https:' || reader.hostname === sharedHost ||
      !/^[a-z0-9-]+(?:\.[a-z0-9-]+)+$/.test(reader.hostname) ||
      reader.hostname === 'github.com' || reader.hostname.endsWith('.localhost') || /^[0-9.]+$/.test(reader.hostname) ||
      reader.username || reader.password || reader.port || reader.hash || reader.search ||
      reader.pathname !== '/') throw Error('Use a dedicated GitHub Pages HTTPS origin at its root');
  return reader.href;
}

async function write(path, content) {
  await writeFile(path, content, { flag: 'wx' });
}

async function checkedLibrary(path) {
  const file = await lstat(path);
  if (!file.isFile() || file.size > MAX_LIBRARY_BYTES) throw Error('Invalid public encrypted snapshot');
  const value = assertLibrary(JSON.parse(await readFile(path, 'utf8')));
  for (const record of value.records) {
    if (record.tag !== await releaseTag(record)) throw Error('Invalid ciphertext release digest');
  }
  return value;
}

export async function stagePublic(root, path, reader) {
  const config = { reader: readerAddress(reader), data: publicData };
  const library = await checkedLibrary(path);
  const dest = resolve(root);
  if (basename(dest) !== 'frontier-omega-alpha' || !(await lstat(dest)).isDirectory()) {
    throw Error('Use the dedicated directory in the qualified Pages build');
  }
  await write(join(dest, 'library.json'), JSON.stringify(library) + '\n');
  await write(join(dest, 'native-config.json'), JSON.stringify(config) + '\n');
}

export async function bundleReader(target) {
  const { build } = await import('esbuild');
  return build({
    entryPoints: [entry], outfile: target, bundle: true, format: 'esm', platform: 'browser',
    target: 'es2022', external: ['node:crypto'], legalComments: 'eof', sourcemap: false, write: true
  });
}

export async function stageReader(output, reader) {
  const config = { reader: readerAddress(reader), data: publicData };
  await mkdir(output, { mode: 0o755 });
  for (const name of staticFiles) {
    if (!pageFiles.includes(name)) {
      await copyFile(join(source, name), join(output, name));
      continue;
    }
    const page = await readFile(join(source, name), 'utf8');
    if (!page.includes('name="frontier-api" content=""') || !page.includes("connect-src 'self'")) {
      throw Error('Source page was not the qualified public shell');
    }
    const locale = name === 'fr.html' ? 'index.html' : 'fr.html';
    const hosted = page
      .replace("connect-src 'self'", "connect-src 'self' " + new URL(publicData).origin)
      .replace('<link rel="canonical" href="https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/' + name + '">',
        '<link rel="canonical" href="' + config.reader + name + '">')
      .replace('href="https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/' + locale + '"',
        'href="' + config.reader + locale + '"');
    await write(join(output, name), hosted);
  }
  await write(join(output, 'native-config.json'), JSON.stringify(config) + '\n');
  await write(join(output, '.nojekyll'), '');
  await bundleReader(join(output, 'native-runtime.js'));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [kind, ...arguments_] = process.argv.slice(2);
  if (kind === 'public' && arguments_.length === 3) {
    await stagePublic(...arguments_);
  } else if (kind === 'reader' && arguments_.length === 2) {
    await stageReader(...arguments_);
  } else {
    throw Error('Use public <existing Pages subdirectory> <encrypted snapshot> <reader URL> or reader <new directory> <reader URL>');
  }
}
