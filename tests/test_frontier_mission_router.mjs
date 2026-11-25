import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createMissionPrompt, createMissionRequest, missionLocalEndpoints, missionRouteReceipt,
  missionRouteResult, missionRoutes, parseMissionResponse, runLocalMission, validateLocalMissionConfig}
  from '../docs/research/frontier-omega-alpha/frontier-mission-router.mjs';

const openAI = 'http://127.0.0.1:38461/v1/chat/completions';
const ollama = 'http://127.0.0.1:11434/api/chat';
const localConfig = {endpoint: openAI, model: 'local-instruct'};
const catalogue = [{id: 'linear-model', title: 'Fit a linear model', scope: 'One response variable'},
  {id: 'residual-check', title: 'Residual check', scope: 'Assess residuals against supplied targets'}];
const ambition = 'What determines whether an acoustic-map sensor stays accurate through the winter?';

const makeRequest = (overrides = {}) => createMissionRequest({missionId: 'example-mission-01', revision: 1,
  language: 'en', ambition, ...overrides});

function report(request, overrides = {}) {
  return JSON.stringify({schema: missionRouteResult, requestId: request.requestId, route: 'research',
    objective: 'Understand how sensor accuracy changes through the winter.', assumptions: [],
    nextAction: 'Record reference measurements during freeze-thaw cycles.',
    work: 'Separate drift caused by temperature from moisture ingress.', capabilityIds: [], ...overrides});
}

function openAIResponse(request, patch = {}) {
  return Response.json({model: localConfig.model, choices: [{finish_reason: 'stop',
    message: {role: 'assistant', content: report(request)}}], ...patch});
}

test('long original and revised ambitions are retained verbatim and bind the packet', async () => {
  const original = '  Mesurer la stabilité d’un réseau de mycorhizes.\n' + 'é'.repeat(10_000) + '\n';
  const revised = '  Au printemps, observer deux parcelles sans modifier leur arrosage.\n';
  const request = await makeRequest({language: 'fr', originalAmbition: original, ambition: revised,
    revision: 2, context: ['Note autorisée'], capabilities: catalogue});
  assert.equal(request.originalAmbition, original);
  assert.equal(request.ambition, revised);
  assert.match(request.requestId, /^[a-f0-9]{64}$/u);
  const prompt = createMissionPrompt(JSON.parse(JSON.stringify(request)));
  const lastLine = JSON.parse(prompt.slice(prompt.lastIndexOf('\n') + 1));
  assert.deepEqual(lastLine, {ambition: revised, originalAmbition: original,
    context: ['Note autorisée'], availableCapabilities: catalogue});
  assert.match(prompt, /Écrivez en français/u);
  assert.match(prompt, new RegExp(request.requestId, 'u'));
  const answer = report(request);
  const revisedRequest = await makeRequest({ambition: revised, revision: 3});
  await assert.rejects(parseMissionResponse(answer, revisedRequest), /ROUTE_BINDING/u);
  await assert.rejects(parseMissionResponse(answer, {...request, context: []}), /ROUTE_BINDING/u);
  await assert.rejects(makeRequest({ambition: 'é'.repeat(12_289)}), /ROUTE_REQUEST/u);
  await assert.rejects(makeRequest({credentials: 'discard-me'}), /ROUTE_REQUEST/u);
  await assert.rejects(makeRequest({capabilities: [catalogue[0], catalogue[0]]}), /ROUTE_CONTEXT/u);
});

test('all eight semantic routes preserve explicit provenance and scoped capability IDs', async () => {
  const request = await makeRequest({capabilities: catalogue});
  const selections = {direct: [], capability: ['linear-model'], composition: ['linear-model', 'residual-check'],
    adaptation: ['residual-check'], research: [], invention: [], continuing: [], clarify: []};
  assert.deepEqual(Object.keys(missionRoutes), Object.keys(selections));
  for (const [route, capabilityIds] of Object.entries(selections)) {
    const receipt = await parseMissionResponse('\x60\x60\x60json\n' + report(request, {route, capabilityIds}) +
      '\n\x60\x60\x60', request, {mode: 'manual'});
    assert.deepEqual(receipt.intelligence, {mode: 'manual', model: null});
    assert.equal(receipt.schema, missionRouteReceipt);
    assert.equal(receipt.route, route);
    assert.equal(receipt.requestId, request.requestId);
    assert.equal(receipt.missionId, request.missionId);
    assert.equal(receipt.revision, request.revision);
    assert.equal(receipt.verification, 'unverified');
    assert.equal(receipt.isOperationalApproval, false);
    assert.deepEqual(receipt.capabilityIds, capabilityIds);
  }
  const emptyCatalogue = await makeRequest();
  assert.equal((await parseMissionResponse(report(emptyCatalogue, {route: 'invention'}), emptyCatalogue)).route,
    'invention');
});

test('assisted import rejects unsupported, unbound or promoted results', async () => {
  const request = await makeRequest({capabilities: catalogue});
  for (const invalid of [{route:'__proto__'}, {route:'call-tool'}, {route:'composition',capabilityIds:['linear-model']},
    {route:'capability',capabilityIds:['published-claim']}, {route:'composition',capabilityIds:['linear-model','linear-model']},
    {route:'direct',capabilityIds:['residual-check']}, {verification:'accepted'}, {isOperationalApproval:true},
    {assumptions:['']}, {work:'x\u0000y'}, {work:'x'.repeat(12 * 1024 + 1)}, {nextAction:'  '}]) {
    await assert.rejects(parseMissionResponse(report(request, invalid), request), /ROUTE_RESPONSE/u);
  }
  await assert.rejects(parseMissionResponse(report(request, {requestId: '0'.repeat(64)}), request), /ROUTE_BINDING/u);
  await assert.rejects(parseMissionResponse(report(request), request, {mode:'local'}), /ROUTE_PROVENANCE/u);
  await assert.rejects(parseMissionResponse(report(request), request, {model:'unknown'}), /ROUTE_PROVENANCE/u);
  await assert.rejects(parseMissionResponse('x'.repeat(65537), request), /ROUTE_RESPONSE_SIZE/u);
  await assert.rejects(parseMissionResponse('extra prose\n' + report(request), request), /ROUTE_RESPONSE_JSON/u);
});

test('local dispatch allows two precise endpoints and requires per-dispatch authorization', async () => {
  const request = await makeRequest();
  for (const endpoint of ['http://localhost:38461/v1/chat/completions', 'https://127.0.0.1:38461/v1/chat/completions',
    'http://127.0.0.1:38461/v1/chat/completions?extra=1', 'http://127.0.0.1:38461/v1/another',
    'http://127.0.0.1:11434/v1/chat/completions', 'http://0x7f000001:38461/v1/chat/completions',
    'http://127.0.0.1:38461@127.0.0.1:38469/v1/chat/completions', 'https://api.example.org/v1/chat/completions']) {
    assert.throws(() => validateLocalMissionConfig({...localConfig, endpoint}), /LOCAL_CONFIG/u);
  }
  assert.deepEqual(Object.keys(missionLocalEndpoints), [openAI, ollama]);
  assert.throws(() => validateLocalMissionConfig({...localConfig, apiKey:'secret'}), /LOCAL_CONFIG/u);
  const shouldNotFetch = () => assert.fail('no HTTP request expected');
  await assert.rejects(runLocalMission(request, localConfig, {fetchImpl:shouldNotFetch}), /LOCAL_AUTHORIZATION/u);
  await assert.rejects(runLocalMission(request, {...localConfig, contextWindow:1100},
    {authorized:true, fetchImpl:shouldNotFetch}), /LOCAL_CONTEXT/u);
  await assert.rejects(runLocalMission(request, localConfig,
    {authorized:true, signal:AbortSignal.abort(),fetchImpl:shouldNotFetch}), /LOCAL_ABORTED/u);
  await assert.rejects(runLocalMission({...request, revision:2}, localConfig,
    {authorized:true,fetchImpl:shouldNotFetch}), /ROUTE_BINDING/u);
});

test('OpenAI-compatible local dispatch posts only to the allowlisted endpoint and records the reply', async () => {
  const request = await makeRequest();
  let calls = 0;
  const receipt = await runLocalMission(request, {...localConfig, maxOutputTokens:384, structuredOutput:true},
    {authorized:true, fetchImpl:async (url, init) => {
      calls += 1;
      assert.equal(url, openAI);
      assert.equal(init.method, 'POST');
      assert.deepEqual(init.headers, {'Content-Type':'application/json'});
      assert.equal(init.redirect, 'error');
      assert.equal(init.credentials, 'omit');
      assert.equal(init.cache, 'no-store');
      assert.equal(init.referrerPolicy, 'no-referrer');
      assert.equal(init.mode, 'cors');
      assert.ok(init.signal instanceof AbortSignal);
      const body = JSON.parse(init.body);
      assert.equal(body.model, localConfig.model);
      assert.equal(body.stream, false);
      assert.equal(body.max_tokens, 384);
      assert.deepEqual(body.response_format.json_schema.schema.properties.requestId.enum,[request.requestId]);
      assert.deepEqual(body.messages.map(message => message.role), ['system','user']);
      assert.equal(JSON.parse(body.messages[1].content).ambition, ambition);
      return openAIResponse(request);
    }});
  assert.equal(calls, 1);
  assert.deepEqual(receipt.intelligence, {mode:'local',model:localConfig.model});
  assert.equal(receipt.verification, 'unverified');
});

test('Ollama wire format selects its chat API and treats the reply as unverified', async () => {
  const request = await makeRequest();
  const model = 'some-model:tag';
  const receipt = await runLocalMission(request, {endpoint:ollama, model, structuredOutput:true},
    {authorized:true,fetchImpl:async (url, init) => {
      assert.equal(url, ollama);
      const body = JSON.parse(init.body);
      assert.equal(body.options.num_predict, 1024);
      assert.equal(body.format.properties.requestId.enum[0], request.requestId);
      assert.equal(body.stream, false);
      return Response.json({model, done:true, done_reason:'stop', message:{role:'assistant',content:report(request)}});
    }});
  assert.equal(receipt.intelligence.model, model);
  assert.equal(receipt.isOperationalApproval, false);
});

test('unavailable, redirected and mismatched local responses cannot produce a receipt', async () => {
  const request = await makeRequest();
  const abortedFetch = async () => { throw new TypeError('runtime inaccessible'); };
  const withReply = response => runLocalMission(request, localConfig, {authorized:true,fetchImpl:async () => response});
  await assert.rejects(runLocalMission(request, localConfig, {authorized:true,fetchImpl:abortedFetch}), /LOCAL_CONNECTION/u);
  await assert.rejects(withReply(new Response('unavailable',{status:503})), /LOCAL_HTTP/u);
  const redirected = openAIResponse(request);
  Object.defineProperty(redirected, 'redirected', {value:true});
  await assert.rejects(withReply(redirected), /LOCAL_ENDPOINT/u);
  await assert.rejects(withReply(openAIResponse(request, {model:'silently-replaced'})), /LOCAL_MODEL/u);
  await assert.rejects(withReply(openAIResponse(request,{choices:[{finish_reason:'length'}]})), /LOCAL_INCOMPLETE/u);
  await assert.rejects(withReply(openAIResponse(request,{choices:[{finish_reason:'stop',
    message:{role:'assistant',content:report(request),tool_calls:[{type:'function'}]}}]})), /LOCAL_RESPONSE/u);
  await assert.rejects(withReply(new Response('x'.repeat(65537))), /ROUTE_RESPONSE_SIZE/u);
  await assert.rejects(withReply(new Response('{}',{headers:{'Content-Length':'65537'}})), /ROUTE_RESPONSE_SIZE/u);
});

test('timeout and cancellation stop the request and leave no local receipt', async () => {
  const request = await makeRequest();
  const waitingFetch = (_, {signal}) => new Promise((_, reject) => {
    signal.addEventListener('abort', () => reject(signal.reason), {once:true});
  });
  await assert.rejects(runLocalMission(request, {...localConfig, timeoutMs:5},
    {authorized:true,fetchImpl:waitingFetch}), /LOCAL_TIMEOUT/u);
  const controller = new AbortController();
  await assert.rejects(runLocalMission(request, localConfig, {authorized:true, signal:controller.signal,
    fetchImpl:(url,init) => {
      const pending = waitingFetch(url,init);
      queueMicrotask(() => controller.abort());
      return pending;
    }}), /LOCAL_ABORTED/u);
});
