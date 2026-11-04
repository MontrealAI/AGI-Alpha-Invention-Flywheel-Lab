'use strict';
(() => {
  const ids = ['sample', 'contact', 'disturbance'];
  const controls = ids.map(id => document.getElementById(id));
  const text = (id, value) => { document.getElementById(id).textContent = value; };
  function update() {
    const [s, c, d] = controls.map(input => Number(input.value));
    if (![s, c, d].every(Number.isFinite)) return;
    ids.forEach((id, i) => text(`${id}-value`, controls[i].value));
    const plus = s + c + d, minus = s - c + d;
    const estimateS = (plus + minus) / 2, estimateC = (plus - minus) / 2;
    text('yplus', plus.toFixed(2)); text('yminus', minus.toFixed(2));
    text('estimated-s', estimateS.toFixed(2)); text('estimated-c', estimateC.toFixed(2));
    const verdict = document.getElementById('witness-verdict');
    verdict.classList.toggle('outside', d !== 0);
    text('witness-verdict', d === 0 ? 'Within the supplied two-effect model.' : 'Outside the supplied model: the original guarantee does not apply.');
    text('witness-explanation', d === 0 ? 'At zero measurement noise, the two effects are recovered exactly.' : `The common disturbance is mistaken for s. Actual first-coordinate error: ${Math.abs(estimateS-s).toFixed(2)}. More confidence cannot remove the missing distinction.`);
  }
  controls.forEach(input => input.addEventListener('input', update));
  document.getElementById('challenge').addEventListener('click', () => { controls[2].value = '0.5'; update(); });
  document.getElementById('reset').addEventListener('click', () => { [0.8, 0.3, 0].forEach((v,i) => { controls[i].value = String(v); }); update(); });
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(button.dataset.copy); button.textContent = 'Copied'; }
    catch (_) { button.textContent = 'Select the command and copy'; }
  }));
  update();
})();
