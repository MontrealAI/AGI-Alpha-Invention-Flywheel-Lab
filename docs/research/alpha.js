/* Browser-only, synthetic single-event preview. No API or payment connections. */
(function (scope) {
  'use strict';
  const SCALE = 1000000, RELIABILITY = 950000, PARTICIPANT_FEE = 1000000;
  function integer(value, name, maximum) {
    if (!Number.isSafeInteger(value) || value < 0 || value > maximum) throw new Error(name + ' is outside the supported preview range.');
    return value;
  }
  function validateScenario(scenario) {
    if (!scenario || !Array.isArray(scenario.sites) || scenario.sites.length !== 4) throw new Error('Exactly four site offers are required.');
    integer(scenario.requestWh, 'Requested energy', 30000000);
    if (!scenario.requestWh) throw new Error('Request at least 0.001 kWh.');
    integer(scenario.budgetMicroUSD, 'Budget', 1000000000000000);
    if (scenario.reliabilityPPM !== RELIABILITY || scenario.participantFeeMicroUSD !== PARTICIPANT_FEE) throw new Error('This preview uses a fixed 5% derating and $1 used-site fee.');
    scenario.sites.forEach((site, index) => {
      if (!site || site.id !== String.fromCharCode(65 + index)) throw new Error('Site identifiers must be A, B, C and D.');
      integer(site.capacityWh, 'Site capacity', 10000000);
      integer(site.rateMicroUSDPerWh, 'Compensation rate', 10000000);
    });
    return scenario;
  }
  function constructDispatch(input) {
    const scenario = validateScenario(input);
    const required = Math.floor((scenario.requestWh * SCALE + RELIABILITY - 1) / RELIABILITY);
    let best = null;
    for (let subset = 1; subset < 16; subset++) {
      const offers = scenario.sites.map((site, index) => ({ ...site, index })).filter(site => subset & (1 << site.index));
      offers.sort((a, b) => a.rateMicroUSDPerWh - b.rateMicroUSDPerWh || a.index - b.index);
      const moved = [0, 0, 0, 0];
      let remaining = required;
      for (const offer of offers) {
        moved[offer.index] = Math.min(offer.capacityWh, remaining);
        remaining -= moved[offer.index];
      }
      if (remaining) continue;
      const cost = moved.reduce((sum, amount, index) => sum + (amount ? amount * scenario.sites[index].rateMicroUSDPerWh + PARTICIPANT_FEE : 0), 0);
      const key = moved.join(',');
      if (!best || cost < best.compensationMicroUSD || (cost === best.compensationMicroUSD && key < best.key)) best = { moved, compensationMicroUSD: cost, key };
    }
    if (!best) throw new Error('Capacity is insufficient after the 5% derating. Reduce the requested shift or add capacity.');
    if (best.compensationMicroUSD > scenario.budgetMicroUSD) throw new Error('The lowest-cost dispatch needs $' + (best.compensationMicroUSD / SCALE).toFixed(2) + ', above the declared compensation budget.');
    const schedules = scenario.sites.map((site, index) => ({ id: site.id, baselineWh: [site.capacityWh, site.capacityWh, 0, 0], deliveredWh: [site.capacityWh - best.moved[index], site.capacityWh, best.moved[index], 0] }));
    const rawShiftWh = best.moved.reduce((a, b) => a + b, 0);
    return { schema: 'agi-alpha/flexibility-preview/v1', scope: 'synthetic-browser-single-event', scenario: JSON.parse(JSON.stringify(scenario)), schedules, rawShiftWh, firmShiftWh: Math.floor(rawShiftWh * RELIABILITY / SCALE), compensationMicroUSD: best.compensationMicroUSD };
  }
  function checkDispatch(scenario, delivery) {
    validateScenario(scenario);
    if (!delivery || delivery.schema !== 'agi-alpha/flexibility-preview/v1' || !Array.isArray(delivery.schedules) || delivery.schedules.length !== 4) throw new Error('The delivery is incomplete.');
    let totalShift = 0, totalCost = 0;
    scenario.sites.forEach((site, index) => {
      const schedule = delivery.schedules[index];
      if (!schedule || schedule.id !== site.id || !Array.isArray(schedule.baselineWh) || !Array.isArray(schedule.deliveredWh) || schedule.baselineWh.length !== 4 || schedule.deliveredWh.length !== 4) throw new Error('Each site requires its four-slot energy schedule.');
      const expectedBaseline = [site.capacityWh, site.capacityWh, 0, 0];
      for (let slot = 0; slot < 4; slot++) {
        if (schedule.baselineWh[slot] !== expectedBaseline[slot]) throw new Error('Baseline energy was changed.');
        integer(schedule.deliveredWh[slot], 'Scheduled energy', site.capacityWh);
      }
      if (schedule.deliveredWh.reduce((a, b) => a + b, 0) !== 2 * site.capacityWh) throw new Error('The schedule does not conserve device energy.');
      if (schedule.deliveredWh[1] !== site.capacityWh || schedule.deliveredWh[3] !== 0) throw new Error('Energy moved outside the permitted recovery slot.');
      const shift = site.capacityWh - schedule.deliveredWh[0];
      if (schedule.deliveredWh[2] !== shift) throw new Error('Shifted energy did not reach the recovery slot.');
      totalShift += shift;
      totalCost += shift ? shift * site.rateMicroUSDPerWh + PARTICIPANT_FEE : 0;
    });
    const firmShift = Math.floor(totalShift * RELIABILITY / SCALE);
    if (firmShift < scenario.requestWh) throw new Error('The derated response does not meet the requested energy.');
    if (totalCost > scenario.budgetMicroUSD) throw new Error('The verified compensation exceeds the budget.');
    if (delivery.rawShiftWh !== totalShift || delivery.firmShiftWh !== firmShift || delivery.compensationMicroUSD !== totalCost) throw new Error('Claimed totals do not match the delivered schedules.');
    if (JSON.stringify(delivery.scenario) !== JSON.stringify(scenario)) throw new Error('The delivery changed the requested contract.');
    return { accepted: true, energyConserved: true, capacitiesRespected: true, recoveryVerified: true, budgetRespected: true, deratedResponseWh: firmShift, compensationMicroUSD: totalCost, soloSitesFeasible: scenario.sites.filter(site => Math.floor(site.capacityWh * RELIABILITY / SCALE) >= scenario.requestWh).length, scope: 'same-browser separate checker; not external certification or native acceptance' };
  }
  function economics(h, p, c, collectedPercent) {
    [h, p, c, collectedPercent].forEach(value => { if (!Number.isFinite(value) || value < 0) throw new Error('Use finite nonnegative economic assumptions.'); });
    if (collectedPercent > 100) throw new Error('Collection cannot exceed 100%.');
    return { margin: p - c, cash: p * collectedPercent / 100 - c, savings: h - p, surplus: h - c };
  }
  const api = { constructDispatch, checkDispatch, economics };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  scope.AlphaPreview = api;
  if (typeof document === 'undefined') return;
  const $ = id => document.getElementById(id);
  if (!$('dispatch-form')) return;
  let currentDelivery = null;
  const money = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(value);
  const energy = value => new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 }).format(value / 1000);
  function exactInput(id, scale, maximum) {
    const raw = $(id).value.trim();
    if (!/^\d+(?:\.\d+)?$/.test(raw)) throw new Error('Enter a nonnegative number in every field.');
    const number = Number(raw), scaled = Math.round(number * scale);
    if (!Number.isFinite(number) || Math.abs(number * scale - scaled) > 0.000001) throw new Error('Use at most ' + Math.log10(scale) + ' decimal places.');
    return integer(scaled, $(id).labels[0]?.textContent.trim() || 'Value', maximum);
  }
  async function digest(text) {
    if (!scope.crypto?.subtle) return null;
    const bytes = await scope.crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
    return [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, '0')).join('');
  }
  function clearDelivery() {
    currentDelivery = null;
    $('dispatch-result').hidden = true;
    $('result-idle').hidden = false;
    $('dispatch-error').hidden = true;
    $('result-label').textContent = 'Ready to explore';
    $('result-label').className = 'label';
  }
  $('dispatch-form').addEventListener('input', clearDelivery);
  $('dispatch-form').addEventListener('submit', async event => {
    event.preventDefault();
    clearDelivery();
    try {
      const scenario = { requestWh: exactInput('request', 1000, 30000000), budgetMicroUSD: exactInput('budget', SCALE, 1000000000000000), reliabilityPPM: RELIABILITY, participantFeeMicroUSD: PARTICIPANT_FEE, sites: ['a', 'b', 'c', 'd'].map(id => ({ id: id.toUpperCase(), capacityWh: exactInput('capacity-' + id, 1000, 10000000), rateMicroUSDPerWh: exactInput('cost-' + id, 1000, 10000000) })) };
      const artifact = constructDispatch(scenario), acceptance = checkDispatch(scenario, artifact);
      const receipt = { ...artifact, acceptance };
      currentDelivery = JSON.stringify(receipt, null, 2) + '\n';
      const thisDelivery = currentDelivery;
      $('delivered').textContent = energy(acceptance.deratedResponseWh);
      $('compensation').textContent = money(acceptance.compensationMicroUSD / SCALE);
      $('solo').textContent = String(acceptance.soloSitesFeasible) + ' / 4';
      $('allocation-bars').replaceChildren();
      artifact.schedules.forEach((schedule, index) => {
        const amount = scenario.sites[index].capacityWh - schedule.deliveredWh[0];
        const row = document.createElement('div'), label = document.createElement('span'), track = document.createElement('div'), fill = document.createElement('div'), output = document.createElement('output');
        row.className = 'allocation-row'; label.textContent = schedule.id; track.className = 'allocation-track'; fill.className = 'allocation-fill'; fill.style.width = (scenario.sites[index].capacityWh ? amount / scenario.sites[index].capacityWh * 100 : 0) + '%'; output.textContent = energy(amount) + ' kWh';
        track.append(fill); row.append(label, track, output); $('allocation-bars').append(row);
      });
      $('acceptance-detail').textContent = 'Verified: per-device energy conserved, recovery in slot 3, all slot capacities respected, 5% derating applied and compensation within budget. ' + energy(artifact.rawShiftWh) + ' kWh shifted before derating. Site participation and capacity are supplied assumptions.';
      $('dispatch-result').hidden = false;
      $('result-idle').hidden = true;
      $('result-label').textContent = 'Accepted preview';
      $('result-label').className = 'label green';
      $('dispatch-proof').textContent = 'Computing artifact SHA-256…';
      const hash = await digest(thisDelivery);
      if (currentDelivery === thisDelivery) $('dispatch-proof').textContent = hash ? 'Artifact SHA-256: ' + hash + '. Identifies these bytes; does not certify physical delivery.' : 'SHA-256 unavailable in this browser context. The JSON includes the complete input, schedules and separate acceptance checks.';
    } catch (error) {
      $('dispatch-error').textContent = error.message;
      $('dispatch-error').hidden = false;
      $('result-label').textContent = 'Request not accepted';
      $('result-label').className = 'label';
    }
  });
  const reset = () => { $('dispatch-form').reset(); clearDelivery(); };
  $('reset-dispatch').addEventListener('click', reset);
  $('restore-default').addEventListener('click', reset);
  $('download-dispatch').addEventListener('click', () => {
    if (!currentDelivery) return;
    const url = URL.createObjectURL(new Blob([currentDelivery], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'agi-alpha-flexibility-dispatch.json'; document.body.append(link); link.click(); link.remove(); scope.setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  function updateEconomics() {
    try {
      const values = ['human-value', 'contract-price', 'complete-cost', 'collected-percent'].map(id => { if (!$(id).value.trim()) throw new Error('Complete each assumption.'); return Number($(id).value); });
      const result = economics(...values);
      $('margin').textContent = money(result.margin); $('cash-contribution').textContent = money(result.cash); $('buyer-savings').textContent = money(result.savings); $('surplus').textContent = money(result.surplus);
      $('economics-message').textContent = result.margin <= 0 ? 'The assumed price does not exceed complete allocated cost. Available capital would not change that margin.' : result.cash < 0 ? 'Positive accounting margin; negative cash contribution at this collection rate. Receivables cannot fund spending.' : 'Positive margin does not make uncollected revenue spendable. Reserves, payback and funding still require the native ledger.';
    } catch (error) { $('economics-message').textContent = error.message; ['margin', 'cash-contribution', 'buyer-savings', 'surplus'].forEach(id => { $(id).textContent = '—'; }); }
  }
  $('economics-form').addEventListener('input', updateEconomics);
  $('economics-form').addEventListener('submit', event => event.preventDefault());
  updateEconomics();
})(typeof globalThis !== 'undefined' ? globalThis : this);
