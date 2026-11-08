#!/usr/bin/env node
'use strict';

// Read-only rendering QA for the authored 1.1.0 reader. Node built-ins only.
// Run on a standard Ubuntu Actions runner with an already installed Chrome:
//   node scripts/verify_learning_reader.cjs --site docs/research \
//     --output "$RUNNER_TEMP/learning-reader-browser-qa"
// The output directory must be new. No source files are edited, packages
// installed, external links followed, or existing browser profiles opened.
// CDP commands: https://chromedevtools.github.io/devtools-protocol/
// Pipe framing: Chrome reads NUL-delimited JSON on fd 3 and writes on fd 4.

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const { spawn, execFileSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');

const EDITION = '1.1.0';
const HTML = `learning-to-build-v${EDITION}.html`;
const PDF = `learning-to-build-v${EDITION}.pdf`;
const IMAGE = `learning-to-build-v${EDITION}-example.png`;
const REPOSITORY = 'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab';
const RELEASE = `${REPOSITORY}/releases/tag/learning-to-build-v${EDITION}`;
const SOURCE = `${REPOSITORY}/releases/download/learning-to-build-v${EDITION}/LEARNING_TO_BUILD_SOURCE.zip`;
const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 1000, mobile: false },
  { name: 'mobile', width: 390, height: 844, mobile: true },
];
const pause = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function options(argv) {
  const result = { site: path.join(__dirname, '../docs/research') };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--help') return { help: true };
    if (!['--site', '--output', '--chrome'].includes(argv[i]) || !argv[i + 1] || argv[i + 1].startsWith('--')) {
      throw new Error(`Unknown option or missing value: ${argv[i]}`);
    }
    result[argv[i].slice(2)] = argv[++i];
  }
  if (!result.output) throw new Error('--output is required and must name a new directory');
  return result;
}

function chromePath(explicit) {
  const candidates = explicit ? [explicit] : [process.env.CHROME_PATH, process.env.CHROME_BIN,
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/opt/google/chrome/chrome',
    '/usr/bin/chromium', '/usr/bin/chromium-browser'];
  for (const candidate of candidates.filter(Boolean)) {
    const paths = candidate.includes(path.sep) ? [path.resolve(candidate)] :
      (process.env.PATH || '').split(path.delimiter).map(directory => path.join(directory, candidate));
    for (const name of paths) {
      try {
        fs.accessSync(name, fs.constants.X_OK);
        if (fs.statSync(name).isFile()) return fs.realpathSync(name);
      } catch { /* Try the next installed path; never install a browser. */ }
    }
  }
  throw new Error(`No executable Chrome found${explicit ? ` at ${explicit}` : ''}; supply --chrome or CHROME_PATH. Nothing was installed.`);
}

class DevToolsPipe {
  constructor(child, onEvent) {
    this.child = child;
    this.nextId = 0;
    this.pending = new Map();
    this.buffer = '';
    this.failure = null;
    child.stdio[4].setEncoding('utf8');
    child.stdio[4].on('data', chunk => {
      this.buffer += chunk;
      let end;
      while ((end = this.buffer.indexOf('\0')) !== -1) {
        const text = this.buffer.slice(0, end);
        this.buffer = this.buffer.slice(end + 1);
        if (!text) continue;
        try {
          const message = JSON.parse(text);
          if (!message.id) { onEvent(message); continue; }
          const request = this.pending.get(message.id);
          if (!request) continue;
          clearTimeout(request.timer);
          this.pending.delete(message.id);
          if (message.error) request.reject(new Error(`${request.method}: ${message.error.message}`));
          else request.resolve(message.result);
        } catch (error) { this.fail(error); }
      }
    });
    for (const stream of [child.stdio[3], child.stdio[4]]) stream.on('error', error => this.fail(error));
    child.on('error', error => this.fail(error));
    child.on('exit', (code, signal) => this.fail(new Error(`Chrome exited (${code ?? signal}); see chrome-stderr.log`)));
  }

  fail(error) {
    this.failure ||= error;
    for (const request of this.pending.values()) {
      clearTimeout(request.timer);
      request.reject(error);
    }
    this.pending.clear();
  }

  send(method, params = {}, sessionId) {
    if (this.failure) return Promise.reject(this.failure);
    return new Promise((resolve, reject) => {
      const id = ++this.nextId;
      // A stalled browser command is an infrastructure failure, never a QA pass.
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Chrome command did not complete within 30 seconds: ${method}`));
      }, 30000);
      this.pending.set(id, { resolve, reject, timer, method });
      try {
        this.child.stdio[3].write(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }) + '\0');
      } catch (error) { this.fail(error); }
    });
  }

  async evaluate(sessionId, fn, ...args) {
    const result = await this.send('Runtime.evaluate', {
      expression: `(${fn.toString()})(${args.map(value => JSON.stringify(value)).join(',')})`,
      awaitPromise: true, returnByValue: true,
    }, sessionId);
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result.value;
  }
}

async function closeBrowser(child, cdp, closed) {
  let cutoff, killError;
  const stop = () => {
    try {
      // Only the process group created for this new, disposable browser.
      if (process.platform !== 'win32' && child.pid) process.kill(-child.pid, 'SIGKILL');
      else child.kill('SIGKILL');
    } catch (error) { if (error.code !== 'ESRCH') killError = error.message; }
  };
  const kill = setTimeout(stop, 5000);
  const timeout = new Promise(resolve => {
    cutoff = setTimeout(() => resolve({ code: null, signal: null, shutdown_timeout: true }), 10000);
  });
  if (cdp && !cdp.failure) cdp.send('Browser.close').catch(() => {});
  const result = await Promise.race([closed, timeout]);
  clearTimeout(kill);
  clearTimeout(cutoff);
  if (result.shutdown_timeout) {
    stop();
    cdp?.fail(new Error('Browser shutdown did not finish within 10 seconds'));
    // An inherited open pipe must not prevent the failed receipt being written.
    for (const stream of child.stdio) stream?.destroy();
    child.unref();
  }
  if (killError) result.kill_error = killError;
  return result;
}

async function settle(cdp, session) {
  await cdp.evaluate(session, async () => {
    await document.fonts.ready;
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}

async function openDocument(cdp, session, url) {
  const navigation = await cdp.send('Page.navigate', { url }, session);
  if (navigation.errorText) throw new Error(`Local reader navigation failed: ${navigation.errorText}`);
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    try {
      if (await cdp.evaluate(session, expected => location.href === expected && document.readyState !== 'loading', url)) {
        await settle(cdp, session);
        return;
      }
    } catch (error) {
      if (!/context|navigat/i.test(error.message)) throw error;
    }
    await pause(100);
  }
  throw new Error('Local reader did not finish DOM navigation within 30 seconds');
}

async function overflow(cdp, session) {
  return cdp.evaluate(session, () => {
    const root = document.documentElement;
    return { viewport_width: innerWidth, viewport_height: innerHeight, client_width: root.clientWidth,
      document_width: root.scrollWidth, body_width: document.body.scrollWidth,
      overflow_px: Math.max(0, root.scrollWidth - root.clientWidth, document.body.scrollWidth - root.clientWidth) };
  });
}

async function screenshot(cdp, session, selector, name, output) {
  await cdp.evaluate(session, selector => {
    const element = document.querySelector(selector);
    if (!element) throw new Error(`Screenshot section missing: ${selector}`);
    element.scrollIntoView({ block: 'start', behavior: 'instant' });
  }, selector);
  await settle(cdp, session);
  const clip = await cdp.evaluate(session, selector => {
    const rect = document.querySelector(selector).getBoundingClientRect();
    const y = selector === '.hero' ? 0 : Math.max(0, Math.floor(rect.top + scrollY) - 12);
    const bottom = Math.min(document.documentElement.scrollHeight, Math.ceil(rect.bottom + scrollY) + 12);
    return { x: 0, y, width: innerWidth, height: bottom - y, scale: 1 };
  }, selector);
  if (!(clip.width > 0 && clip.height > 0)) throw new Error(`Screenshot section has no area: ${selector}`);
  const result = await cdp.send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: true, clip }, session);
  const bytes = Buffer.from(result.data, 'base64');
  if (!bytes.subarray(0, 8).equals(Buffer.from('89504e470d0a1a0a', 'hex'))) throw new Error(`Invalid PNG from Chrome: ${name}`);
  const width = bytes.readUInt32BE(16), height = bytes.readUInt32BE(20);
  if (width !== clip.width || height !== clip.height) throw new Error(`Screenshot dimensions differ from requested clip: ${name}`);
  fs.writeFileSync(path.join(output, name), bytes, { flag: 'wx' });
  return { file: name, selector, width, height, sha256: hash(bytes), bytes: bytes.length, clip };
}

async function inspectViewport(cdp, viewport, context, receipt) {
  const result = { ...viewport, checks: [], images: [], disclosures: [], screenshots: [], runtime_errors: [], remote_requests: [] };
  receipt.viewports.push(result);
  const check = (name, pass, actual) => result.checks.push({ name, pass: Boolean(pass), ...(actual === undefined ? {} : { actual }) });
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId: session } = await cdp.send('Target.attachToTarget', { targetId, flatten: true });
  context.sessions.set(session, result);
  try {
    await cdp.send('Page.enable', {}, session);
    await cdp.send('Runtime.enable', {}, session);
    await cdp.send('Network.enable', {}, session);
    await cdp.send('Network.setBlockedURLs', { urls: ['http://*', 'https://*', 'ws://*', 'wss://*'] }, session);
    await cdp.send('Emulation.setDeviceMetricsOverride', { width: viewport.width, height: viewport.height,
      deviceScaleFactor: 1, mobile: viewport.mobile, screenWidth: viewport.width, screenHeight: viewport.height }, session);
    await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: viewport.mobile }, session);
    await cdp.send('Page.bringToFront', {}, session);
    await openDocument(cdp, session, context.url);
    const identity = await cdp.evaluate(session, (pdf, source, release) => {
      const clean = value => (value || '').replace(/\s+/g, ' ').trim();
      const links = [...document.querySelectorAll('a[href]')];
      return {
        title: document.title, h1: [...document.querySelectorAll('h1')].map(node => clean(node.innerText)),
        byline: clean(document.querySelector('.hero .byline')?.innerText),
        edition: clean([...document.querySelectorAll('#downloads dt')].find(node => clean(node.innerText) === 'Edition')?.nextElementSibling?.innerText),
        pdf_sha256: clean(document.querySelector('[data-pdf-sha]')?.innerText),
        pdf_links: links.filter(link => link.href === new URL(pdf, location.href).href).length,
        source_download: [...document.querySelectorAll('#downloads a[href]')].some(link => link.href === source),
        release_link: links.some(link => link.href === release),
        image_count: document.images.length, disclosure_count: document.querySelectorAll('details').length,
        method_disclosure_count: document.querySelectorAll('details.method').length,
        french_disclosure: Boolean(document.querySelector('details#francais')),
        citation_disclosure: Boolean(document.querySelector('details.citation')),
      };
    }, PDF, SOURCE, RELEASE);
    result.identity = identity;
    check('one visible research title', identity.h1.length === 1 && identity.h1[0] === 'LEARNING TO BUILD');
    check('edition in byline and download identity', identity.byline.includes(`Research edition ${EDITION}`) && identity.edition.startsWith(`${EDITION} `));
    check('PDF links and displayed hash bind the local edition', identity.pdf_links > 0 && identity.pdf_sha256 === context.pdfSha256);
    check('versioned source download and release links', identity.source_download && identity.release_link);
    const initial = await overflow(cdp, session);
    check('requested layout viewport', Math.abs(initial.viewport_width - viewport.width) <= 1 && Math.abs(initial.viewport_height - viewport.height) <= 1, initial);
    check('no horizontal document overflow', initial.overflow_px === 0, initial);

    for (let index = 0; index < identity.image_count; index++) {
      const image = await cdp.evaluate(session, async index => {
        const img = document.images[index];
        img.scrollIntoView({ block: 'center', behavior: 'instant' });
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        let decodeError = null;
        try { await img.decode(); } catch (error) { decodeError = String(error); }
        const rect = img.getBoundingClientRect();
        return { src: img.getAttribute('src'), current_src: img.currentSrc, complete: img.complete,
          natural_width: img.naturalWidth, natural_height: img.naturalHeight,
          rendered_width: rect.width, rendered_height: rect.height, decode_error: decodeError };
      }, index);
      result.images.push(image);
      check(`image ${index + 1} actually decodes and renders`, image.complete && !image.decode_error && image.natural_width > 0 && image.natural_height > 0 && image.rendered_width > 0 && image.rendered_height > 0);
    }
    check('authored evidence image is present', result.images.some(image => image.src === IMAGE));

    check('method, French and citation disclosures are present', identity.method_disclosure_count >= 7 && identity.french_disclosure && identity.citation_disclosure);
    for (let index = 0; index < identity.disclosure_count; index++) {
      const disclosure = await cdp.evaluate(session, index => {
        const details = document.querySelectorAll('details')[index], summary = details.querySelector('summary');
        if (!summary) throw new Error(`Disclosure ${index + 1} has no summary`);
        summary.scrollIntoView({ block: 'center', behavior: 'instant' });
        summary.focus({ preventScroll: true });
        return { summary: summary.innerText.trim(), initial_open: details.open, focused: document.activeElement === summary };
      }, index);
      await settle(cdp, session);
      const states = [];
      for (let attempt = 0; attempt < 2; attempt++) {
        await cdp.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13, text: '\r' }, session);
        await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 }, session);
        await settle(cdp, session);
        states.push(await cdp.evaluate(session, index => {
          const details = document.querySelectorAll('details')[index];
          return { open: details.open, content_visible: [...details.children].filter(node => node.tagName !== 'SUMMARY')
            .some(node => node.getClientRects().length && node.getBoundingClientRect().height > 0) };
        }, index));
        const measured = await overflow(cdp, session);
        check(`no document overflow after disclosure ${index + 1}, toggle ${attempt + 1}`, measured.overflow_px === 0,
          measured.overflow_px > 0 ? measured : undefined);
      }
      Object.assign(disclosure, { after_first_toggle: states[0].open, restored_open: states[1].open,
        content_visible_when_open: states.some(state => state.open && state.content_visible) });
      result.disclosures.push(disclosure);
      check(`disclosure ${index + 1} opens and closes with Enter`, disclosure.focused && states[0].open !== disclosure.initial_open &&
        states[1].open === disclosure.initial_open && disclosure.content_visible_when_open);
    }
    for (const [name, selector] of [['hero', '.hero'], ['evidence', '#evidence'], ['downloads', '#downloads']]) {
      result.screenshots.push(await screenshot(cdp, session, selector, `${viewport.name}-${name}.png`, context.output));
    }
    const final = await overflow(cdp, session);
    check('no document overflow after captures', final.overflow_px === 0, final);
    check('no page JavaScript exceptions', result.runtime_errors.length === 0);
    check('no attempted remote page requests', result.remote_requests.length === 0);
  } finally {
    await cdp.send('Target.closeTarget', { targetId }).catch(() => {});
    context.sessions.delete(session);
  }
}

async function main() {
  const args = options(process.argv.slice(2));
  if (args.help) {
    console.log('Usage: node scripts/verify_learning_reader.cjs [--site DIRECTORY] --output NEW_DIRECTORY [--chrome EXECUTABLE]\nRequires installed Chrome and Node.js; writes six PNGs, browser logs and READER_QA.json. Never installs software or follows external links.');
    return;
  }
  const site = fs.realpathSync(args.site), output = path.resolve(args.output);
  const parent = fs.realpathSync(path.dirname(output));
  const resolvedOutput = path.join(parent, path.basename(output));
  if (resolvedOutput === site || resolvedOutput.startsWith(site + path.sep)) throw new Error('QA output must be outside the reader source directory');
  fs.mkdirSync(output); // Refuse reuse; preserve any earlier failure artifacts.
  const start = process.hrtime.bigint();
  const receipt = { schema: 'learning-to-build/reader-browser-qa/v1', status: 'FAILED', started_at_utc: new Date().toISOString(),
    scope: 'Local authored HTML in fresh Chrome; desktop/mobile viewport emulation, decoded images, keyboard disclosures, overflow and link targets. Remote requests blocked. This does not verify live publication, remote downloads, embedded PDF rendering or scientific results.',
    node_version: process.version, script_sha256: hash(fs.readFileSync(__filename)), source_directory: site,
    remote_page_requests_blocked: true, transport: 'Chrome DevTools pipe', sources: {}, viewports: [] };
  let child, cdp, profile, closed;
  try {
    for (const name of [HTML, PDF, IMAGE]) {
      const filename = path.join(site, name);
      if (fs.lstatSync(filename).isSymbolicLink()) throw new Error(`Reader input must not be a symlink: ${name}`);
      const bytes = fs.readFileSync(filename);
      receipt.sources[name] = { bytes: bytes.length, sha256: hash(bytes) };
    }
    try { receipt.checkout_revision = execFileSync('git', ['-C', path.join(__dirname, '..'), 'rev-parse', 'HEAD'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim(); }
    catch { receipt.checkout_revision = null; } // Source hashes bind non-Git copies.
    const executable = chromePath(args.chrome);
    profile = fs.mkdtempSync(path.join(os.tmpdir(), 'learning-reader-chrome-'));
    const flags = ['--headless=new', '--remote-debugging-pipe', `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check',
      '--disable-background-networking', '--disable-component-update', '--disable-default-apps', '--disable-sync', '--disable-dev-shm-usage',
      '--no-sandbox', 'about:blank'];
    receipt.chrome_executable = executable;
    receipt.chrome_flags = flags.map(flag => flag.startsWith('--user-data-dir=') ? '--user-data-dir=<new disposable profile>' : flag);
    const stdout = fs.openSync(path.join(output, 'chrome-stdout.log'), 'wx');
    const stderr = fs.openSync(path.join(output, 'chrome-stderr.log'), 'wx');
    try { child = spawn(executable, flags, { stdio: ['ignore', stdout, stderr, 'pipe', 'pipe'], detached: process.platform !== 'win32' }); }
    finally { fs.closeSync(stdout); fs.closeSync(stderr); }
    closed = new Promise(resolve => child.once('close', (code, signal) => resolve({ code, signal })));
    const sessions = new Map();
    cdp = new DevToolsPipe(child, message => {
      const result = sessions.get(message.sessionId);
      if (!result) return;
      if (message.method === 'Runtime.exceptionThrown') result.runtime_errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
      if (message.method === 'Network.requestWillBeSent' && /^(https?|wss?):/.test(message.params.request.url)) result.remote_requests.push(message.params.request.url);
    });
    receipt.browser = await cdp.send('Browser.getVersion');
    const context = { sessions, output, url: pathToFileURL(path.join(site, HTML)).href, pdfSha256: receipt.sources[PDF].sha256 };
    for (const viewport of VIEWPORTS) await inspectViewport(cdp, viewport, context, receipt);
    receipt.status = receipt.viewports.length === 2 && receipt.viewports.every(viewport =>
      viewport.screenshots.length === 3 && viewport.checks.every(check => check.pass)) ? 'PASS' : 'FAILED';
  } catch (error) {
    receipt.error = { message: error.message, stack: error.stack };
  } finally {
    if (child) {
      receipt.browser_exit = await closeBrowser(child, cdp, closed);
      if (receipt.browser_exit.code !== 0) {
        receipt.status = 'FAILED';
        receipt.error ||= { message: 'Chrome did not exit cleanly; see browser_exit and chrome-stderr.log' };
      }
    }
    if (profile) {
      try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }); }
      catch (error) {
        receipt.status = 'FAILED';
        receipt.cleanup_error = error.message;
      }
    }
    receipt.finished_at_utc = new Date().toISOString();
    receipt.wall_seconds = Number(process.hrtime.bigint() - start) / 1e9;
    receipt.failed_checks = receipt.viewports.flatMap(viewport => viewport.checks.filter(check => !check.pass).map(check => `${viewport.name}: ${check.name}`));
    fs.writeFileSync(path.join(output, 'READER_QA.json'), JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
    console.log(JSON.stringify({ status: receipt.status, receipt: path.join(output, 'READER_QA.json'),
      screenshots: receipt.viewports.reduce((count, viewport) => count + viewport.screenshots.length, 0), failed_checks: receipt.failed_checks,
      ...(receipt.error ? { error: receipt.error.message } : {}) }));
    process.exitCode = receipt.status === 'PASS' ? 0 : 1;
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
