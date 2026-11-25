// SPDX-License-Identifier: Apache-2.0
(() => {
  const copy = document.getElementById('copy-pairing');
  if (copy && navigator.clipboard) {
    copy.hidden = false;
    copy.addEventListener('click', async () => {
      const status = document.getElementById('copy-pairing-status');
      try {
        await navigator.clipboard.writeText(document.getElementById('manual-pairing-code').textContent);
        status.textContent = 'Code copied. · Code copié.';
      } catch {
        status.textContent = 'Select and copy the code above. · Sélectionnez et copiez le code ci-dessus.';
      }
    });
  }

  const content = document.getElementById('frontier-connection');
  const opener = window.opener;
  if (!content || !opener) return;

  const origin = content.dataset.origin;
  const status = document.getElementById('pairing-status');
  const approve = document.getElementById('approve-pairing');
  const cancel = document.getElementById('cancel-pairing');
  let channel, proof;

  function receive(event) {
    if (event.origin !== origin || event.source !== opener || event.ports.length !== 1
        || event.data?.type !== 'frontier-pair-request'
        || typeof event.data.proof !== 'string' || !/^[0-9a-f]{64}$/.test(event.data.proof)) return;
    window.removeEventListener('message', receive);
    channel = event.ports[0];
    proof = event.data.proof;
    status.textContent = status.dataset.ready;
    approve.disabled = false;
    approve.focus();
  }

  approve.addEventListener('click', async event => {
    if (!channel || !event.isTrusted || approve.disabled) return;
    approve.disabled = true;
    cancel.disabled = true;
    try {
      const session = await fetch('/api/session', {headers: {'X-Harness-Client': 'browser'},
        mode: 'same-origin', cache: 'no-store', redirect: 'error'});
      if (!session.ok) throw new Error('companion-session');
      const {token} = await session.json();
      const response = await fetch('/api/frontier-intelligence/pair-approve', {method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-Harness-Token': token},
        body: JSON.stringify({proof_sha256: proof, consent: true}),
        mode: 'same-origin', cache: 'no-store', redirect: 'error'});
      if (!response.ok) throw new Error('companion-approval');
      const {approval} = await response.json();
      status.textContent = status.dataset.success;
      channel.postMessage({approval});
    } catch {
      cancel.disabled = false;
      status.textContent = status.dataset.error;
      channel.postMessage({failed: true});
    }
  });

  cancel.addEventListener('click', () => {
    channel?.postMessage({cancelled: true});
    window.close();
  });
  window.addEventListener('message', receive);
  opener.postMessage({type: 'frontier-pair-ready'}, origin);
})();
