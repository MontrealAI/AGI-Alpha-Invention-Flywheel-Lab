/** Reference-bind a local receipt without returning its raw input or wallet identity. */
export function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value !== null && typeof value === 'object') {
    return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
  }
  return JSON.stringify(value);
}

export async function fingerprint(value) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical(value)));
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('');
}

const hash = /^[a-f0-9]{64}$/u;
const schema = 'frontier/outcome-receipt-v1';

export async function freezeScreen(input, tool, publicSample) {
  const input_sha256 = await fingerprint(input);
  const classification = input_sha256 === publicSample.input_sha256 ? 'controlled-public-replay' : 'local-self-reported';
  return Object.freeze({
    task: 'highest-documented-tested-load-in-one-scope',
    capability: 'endpoint-evidence-screen@' + tool.version,
    artifact_sha256: tool.sha256,
    input_sha256,
    scope_sha256: await fingerprint(input.scope),
    limits_sha256: await fingerprint([input.cutoff, input.minimum_tokens_per_s, input.maximum_p90_ttft_ms]),
    permissions: classification === 'controlled-public-replay' ? 'public-reference' : 'operator-attested',
    baseline: 'indexed-sqlite-exact-screen',
    classification,
    frozen_at: new Date().toISOString(),
  });
}

export async function outcome(plan, result, elapsed_ms, publicSample, consent) {
  if (!consent) throw new Error('EXPORT_CONSENT');
  const result_sha256 = await fingerprint(result);
  const publicCase = plan.classification === 'controlled-public-replay'
    && plan.input_sha256 === publicSample.input_sha256 && result_sha256 === publicSample.result_sha256;
  if (plan.classification === 'controlled-public-replay' && !publicCase) throw new Error('REFERENCE_MISMATCH');
  const receipt = {
    schema,
    plan,
    plan_sha256: await fingerprint(plan),
    result_sha256,
    comparator_result_sha256: publicCase ? publicSample.result_sha256 : null,
    verification: publicCase ? 'matched-frozen-independent-sqlite-reference' : 'operator-input-not-independently-adjudicated',
    recorded_at: new Date().toISOString(),
    accepted_tested_point: result.screening === 'QUALIFIED_TESTED_POINT',
    recorded_highest_load: publicCase ? result.highest_tested_load : null,
    failure_count: result.rows.filter(row => row.disposition !== 'qualified').length,
    elapsed_ms,
    complete_cost: null,
    realized_member_value: null,
    is_operational_approval: false,
  };
  return {receipt, sha256: await fingerprint(receipt)};
}

const hasFields = (value, names) => value !== null && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
const isHash = value => typeof value === 'string' && hash.test(value);
const isInstant = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u.test(value)
  && Number.isFinite(Date.parse(value));

export async function verifyOutcome(envelope) {
  if (!hasFields(envelope, ['receipt','sha256']) || !isHash(envelope.sha256)) return false;
  const r = envelope.receipt;
  if (!hasFields(r, ['schema','plan','plan_sha256','result_sha256','comparator_result_sha256','verification','recorded_at',
    'accepted_tested_point','recorded_highest_load','failure_count','elapsed_ms','complete_cost','realized_member_value','is_operational_approval'])
    || r.schema !== schema) return false;
  const plan = r.plan;
  if (!hasFields(plan, ['task','capability','artifact_sha256','input_sha256','scope_sha256','limits_sha256','permissions',
    'baseline','classification','frozen_at'])) return false;
  const publicCase = plan.classification === 'controlled-public-replay';
  const recognized = publicCase || plan.classification === 'local-self-reported';
  const expectedVerification = publicCase ? 'matched-frozen-independent-sqlite-reference' : 'operator-input-not-independently-adjudicated';
  return recognized && r.verification === expectedVerification
    && (publicCase ? r.comparator_result_sha256 === r.result_sha256 && Number.isSafeInteger(r.recorded_highest_load)
      && r.recorded_highest_load > 0 : r.comparator_result_sha256 === null && r.recorded_highest_load === null)
    && plan.task === 'highest-documented-tested-load-in-one-scope'
    && plan.capability === 'endpoint-evidence-screen@1.0.0' && plan.baseline === 'indexed-sqlite-exact-screen'
    && plan.permissions === (publicCase ? 'public-reference' : 'operator-attested')
    && typeof r.accepted_tested_point === 'boolean' && (!publicCase || r.accepted_tested_point)
    && Number.isSafeInteger(r.failure_count) && r.failure_count >= 0 && r.failure_count <= 10000
    && typeof r.elapsed_ms === 'number' && Number.isFinite(r.elapsed_ms) && r.elapsed_ms >= 0
    && isInstant(plan.frozen_at) && isInstant(r.recorded_at) && plan.frozen_at <= r.recorded_at
    && r.is_operational_approval === false && r.realized_member_value === null && r.complete_cost === null
    && [r.plan_sha256,r.result_sha256,plan.input_sha256,plan.scope_sha256,plan.limits_sha256,plan.artifact_sha256].every(isHash)
    && r.plan_sha256 === await fingerprint(plan) && envelope.sha256 === await fingerprint(r);
}
