const test = require('node:test');
const assert = require('node:assert/strict');
const { constructDispatch, checkDispatch, economics } = require('../docs/research/alpha.js');
const scenario = () => ({ requestWh: 100000, budgetMicroUSD: 25000000, reliabilityPPM: 950000, participantFeeMicroUSD: 1000000, sites: [100, 150, 200, 250].map((rate, i) => ({ id: 'ABCD'[i], capacityWh: 40000, rateMicroUSDPerWh: rate })) });
test('the pool crosses the derated threshold while every individual site fails', () => {
  const request = scenario(), result = constructDispatch(request), receipt = checkDispatch(request, result);
  assert.equal(result.rawShiftWh, 105264);
  assert.equal(result.firmShiftWh, 100000);
  assert.equal(result.compensationMicroUSD, 18052800);
  assert.equal(receipt.soloSitesFeasible, 0);
  assert.equal(receipt.accepted, true);
});
test('fixed participation cost can make a cheap tiny offer uneconomic', () => {
  const request = scenario(); request.requestWh = 20; request.budgetMicroUSD = 5000000;
  request.sites = [1, 100, 0, 0].map((capacity, i) => ({ id: 'ABCD'[i], capacityWh: capacity, rateMicroUSDPerWh: [1, 10, 20, 30][i] }));
  const result = constructDispatch(request);
  assert.equal(result.schedules[0].deliveredWh[0], 1);
  assert.equal(result.rawShiftWh, 22);
  assert.equal(result.compensationMicroUSD, 1000220);
  assert.equal(checkDispatch(request, result).accepted, true);
});
test('insufficient capacity and an insufficient budget both reject instead of manufacturing acceptance', () => {
  const request = scenario(); request.requestWh = 200000;
  assert.throws(() => constructDispatch(request), /Capacity is insufficient/);
  request.requestWh = 100000; request.budgetMicroUSD = 18000000;
  assert.throws(() => constructDispatch(request), /above the declared/);
});
test('checker rejects lost energy, overcapacity, altered contract and forged compensation', () => {
  const request = scenario(), result = constructDispatch(request);
  for (const mutate of [
    r => { r.schedules[0].deliveredWh[2]--; },
    r => { r.schedules[0].deliveredWh[1]++; },
    r => { r.compensationMicroUSD = 0; },
    r => { r.scenario.requestWh--; },
    r => { r.firmShiftWh++; }
  ]) {
    const changed = structuredClone(result); mutate(changed);
    assert.throws(() => checkDispatch(request, changed));
  }
});
test('allocation equals a separately enumerated integer optimum on a small fresh contract', () => {
  const request = scenario(); request.requestWh = 5; request.budgetMicroUSD = 10000000;
  request.sites = [3, 2, 4, 1].map((capacity, i) => ({ id: 'ABCD'[i], capacityWh: capacity, rateMicroUSDPerWh: [11, 8, 20, 1][i] }));
  let best = Infinity;
  for (let a = 0; a <= 3; a++) for (let b = 0; b <= 2; b++) for (let c = 0; c <= 4; c++) for (let d = 0; d <= 1; d++) {
    const amounts = [a, b, c, d];
    if (Math.floor((a + b + c + d) * 0.95) < 5) continue;
    const cost = amounts.reduce((sum, amount, i) => sum + (amount ? amount * request.sites[i].rateMicroUSDPerWh + 1000000 : 0), 0);
    best = Math.min(best, cost);
  }
  assert.equal(constructDispatch(request).compensationMicroUSD, best);
});
test('negative, nonfinite and unsupported inputs fail closed', () => {
  for (const value of [-1, NaN, Infinity, 1.5, 10000001]) {
    const request = scenario(); request.sites[0].capacityWh = value;
    assert.throws(() => constructDispatch(request));
  }
});
test('economic comparison does not confuse margin, collections or human alternative value', () => {
  assert.deepEqual(economics(100, 50, 40, 50), { margin: 10, cash: -15, savings: 50, surplus: 60 });
  assert.deepEqual(economics(100, 30, 40, 100), { margin: -10, cash: -10, savings: 70, surplus: 60 });
  assert.throws(() => economics(1, 1, 1, 101));
  assert.throws(() => economics(Infinity, 1, 1, 100));
});
