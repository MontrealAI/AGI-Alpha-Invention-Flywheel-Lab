import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import test from 'node:test';
import {opportunityOperation, runOpportunityOperation}
  from '../docs/research/frontier-omega-alpha/frontier-opportunity-operation.mjs';

const repo = 'test-org/public-model';
const revision = 'a'.repeat(40);
const plan = {
  kind: 'huggingface-model-inventory', repo, filename: 'model.gguf',
  requiredFilenames: ['configuration.txt'], comparisonFilename: 'alternate.gguf',
};
const api = 'https://huggingface.co/api/models/' + repo + '?blobs=true';
const raw = 'https://huggingface.co/' + repo + '/raw/' + revision + '/';
const hash = (algorithm, text) => createHash(algorithm).update(text).digest('hex');
const lfsDigest = 'b'.repeat(64);
const blob = (text) => hash('sha1', 'blob ' + Buffer.byteLength(text) + '\0' + text);
const lfs = (size) => 'version https://git-lfs.github.com/spec/v1\noid sha256:' + lfsDigest + '\nsize ' + size + '\n';

function fixture(patch = {}, rawPatch = {}) {
  const sourceBytes = {
    'model.gguf': lfs(10_000), 'alternate.gguf': lfs(13_000), 'configuration.txt': 'local configuration\n',
  };
  const data = {
    id: repo, sha: revision, private: false, gated: false, disabled: false,
    cardData: {license: 'apache-2.0'},
    siblings: Object.entries(sourceBytes).map(([rfilename, text]) => {
      const size = rfilename === 'model.gguf' ? 10_000 : rfilename === 'alternate.gguf' ? 13_000 : text.length;
      return {rfilename, size, blobId: blob(text), ...(rfilename.endsWith('.gguf') && {lfs: {size, sha256: lfsDigest}})};
    }),
    ...patch,
  };
  const sourceText = JSON.stringify(data);
  const calls = [];
  function fetchSource(url, options) {
    calls.push({url, options});
    if (url === api) return Promise.resolve(new Response(sourceText, {headers:{'content-type': 'application/json'}}));
    if (!url.startsWith(raw)) throw new Error('Unexpected acquisition');
    const filename = url.slice(raw.length);
    const text = rawPatch[filename] ?? sourceBytes[filename];
    return Promise.resolve(new Response(text, {headers:{'x-repo-commit': revision}}));
  }
  return {fetchSource, calls, sourceText};
}

test('acquires only public metadata and delivers source-bound sized artifacts', async () => {
  const {fetchSource, calls, sourceText} = fixture();
  const controller = new AbortController();
  const result = await runOpportunityOperation(plan, {
    fetchSource, signal:controller.signal, now:new Date('2026-11-26T10:00:00Z'),
  });
  assert.equal(result.totalBytes, 10_020);
  assert.equal(result.comparison.deltaBytes, 3_000);
  assert.equal(result.declaredLicense, 'apache-2.0');
  assert.equal(result.retrievedAt, '2026-11-26T10:00:00.000Z');
  assert.equal(result.artifacts[0].sha256, lfsDigest);
  assert.equal(result.artifacts[1].sha256, hash('sha256', 'local configuration\n'));
  assert.equal(result.source.sha256, hash('sha256', sourceText));
  assert.equal(result.qualification.weightBytesAcquired, false);
  assert.equal(JSON.parse(result.files[0].content).totalBytes, 10_020);
  assert.equal(result.files[1].content, sourceText);
  assert.deepEqual(calls.map(call => call.url), [api, raw + 'model.gguf', raw + 'configuration.txt', raw + 'alternate.gguf']);
  assert(calls.every(({options}) => options.credentials === 'omit' && options.redirect === 'error'
    && options.referrerPolicy === 'no-referrer' && options.signal === controller.signal));
});

test('withholds inventory on gated, ambiguous, mismatched and oversized source evidence', async () => {
  await assert.rejects(runOpportunityOperation(plan, fixture({gated: 'manual'})), {code:'source-access'});
  await assert.rejects(runOpportunityOperation(plan, fixture({id: 'not/source'})), {code:'source-identity'});
  await assert.rejects(runOpportunityOperation(plan, fixture({siblings: []})), {code:'artifact-unavailable'});
  await assert.rejects(runOpportunityOperation(plan, fixture({}, {'model.gguf':lfs(11_000)})), {code:'artifact-integrity'});
  await assert.rejects(runOpportunityOperation(plan, fixture({}, {'model.gguf':'a'.repeat(1025)})), {code:'source-too-large'});
});

test('validates path and revision intent before any network operation and observes abortion', async () => {
  const {fetchSource, calls} = fixture();
  const unsafe = {...plan, repo:'https://elsewhere.test/x'};
  assert.equal(opportunityOperation({operation:unsafe}), null);
  assert.equal(opportunityOperation({operation:{...plan, filename:'../file'}}), null);
  assert.equal(opportunityOperation({operation:{...plan, comparisonFilename:plan.filename}}), null);
  await assert.rejects(runOpportunityOperation(unsafe, {fetchSource}), {code:'invalid-operation'});
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(runOpportunityOperation(plan, {fetchSource, signal:controller.signal}), {name:'AbortError'});
  assert.equal(calls.length, 0);
});
